# Interview Prep — Piazza Agent

---

## Project Summary (30-second pitch)

Piazza Agent is an autonomous AI agent that monitors a university course forum (Piazza), summarizes new posts using an LLM, and emails a structured digest to registered students on a schedule. It runs entirely serverlessly — no backend server, no daemon. GitHub Actions acts as the scheduler, Vercel hosts the signup UI, Supabase stores users, and Groq runs the AI.

---

## File-by-File Breakdown

### `agent/run.py`
The entry point. Called by GitHub Actions as `python -m agent.run`. Sets up logging and calls `run_all()`. One job: bootstrap and hand off.

### `agent/runner.py`
The pipeline orchestrator. `run_all()` fetches all active users from Supabase and calls `run_for_user()` for each with a 15-second cooldown between users to avoid Piazza rate limits.

`run_for_user()` is the full per-user flow:
1. Login to Piazza
2. Fetch all posts
3. Filter to only posts newer than the user's checkpoint (`last_post_nr`)
4. Optionally load assignment context from the DB
5. Summarize with Groq
6. Email the report
7. Update the checkpoint

### `scraper/piazza_client.py`
Wraps the `piazza-api` library. Handles login, course connection, and post fetching. Key detail: Piazza rate-limits aggressive scrapers, so the fetcher waits 1.5 seconds between posts and retries up to 3 times with backoff (5s → 10s → 15s) on "too fast" errors instead of silently dropping posts.

### `scraper/parser.py`
Converts raw Piazza API responses (nested dicts with HTML content) into clean flat dicts. Strips HTML tags with regex, extracts subject, body, instructor answer, student follow-ups, tags, and post number (`nr`). Silently drops malformed posts and logs a count.

### `ai/groq_client.py`
Thin wrapper around the Groq SDK. Implements a singleton client and a `chat(prompt, system)` function. Primary model: `llama-3.3-70b-versatile`. If it returns a 429 (rate limit), automatically retries with `llama-3.1-8b-instant`. Temperature is fixed at 0.3 for consistent, factual output.

### `ai/prompts.py`
All prompt logic lives here.
- `SYSTEM_SUMMARIZER` — defines the AI's role and the strict rule that every bullet must end with `([#nr](url))`
- `build_summary_prompt()` — builds the per-batch prompt, embeds post content and Piazza links directly
- `build_merge_prompt()` — merges multiple batch summaries. Dynamically caps each summary's length so the combined prompt fits within the fallback model's 6k token limit

### `ai/summarizer.py`
Handles batching. If ≤13 posts: single Groq call. If >13: splits into batches of 13, summarizes each independently, then calls `build_merge_prompt` to merge into one unified report.

### `ai/pdf_extractor.py`
One-off utility (not in the main pipeline). Uses PyMuPDF to extract text from assignment PDFs, sends it to Groq, and gets back structured JSON with topics, parts, and constraints. Stored in Supabase and injected as context into future summarization prompts.

### `notifier/email_sender.py`
Delivers the report via Gmail SMTP using Python's built-in `smtplib`. Includes a lightweight Markdown-to-HTML converter (handles headers, bold, links, bullets) — no external Markdown library needed. Sends both HTML and plain-text parts.

### `storage/supabase_client.py`
Singleton Supabase client. Initializes once from env vars.

### `storage/database.py`
All Supabase CRUD:
- `get_all_active_users()` — calls the `get_active_users` SQL RPC, which joins `users` with `vault.decrypted_secrets` to return passwords decrypted at query time
- `update_last_post_nr()` — saves the checkpoint after a successful run
- `add_user()` — calls the `add_user` SQL RPC, which creates a Vault secret for the password and inserts the user with only the secret's UUID stored in the table
- `get_goals() / save_goals()` — reads/writes assignment context from the `assignment_goals` table

### `config/settings.py`
Single source of truth for all configuration. Reads from `.env` via `python-dotenv`. No logic — just constants.

### `ui/index.html`
Static signup page deployed on Vercel. Single HTML form: report email, Piazza login, Piazza password, Piazza course URL.

### `ui/api/signup.py`
Vercel Python serverless function. Validates fields, extracts the course ID from the Piazza URL, calls the `add_user` Supabase RPC (password goes straight to Vault), then optionally triggers the GitHub Actions workflow via the GitHub REST API so new users get their first report immediately.

### `ui/api/unsubscribe.py`
Vercel Python serverless function. Deletes the user's row from Supabase — removes them from all future runs.

### `.github/workflows/agent.yml`
Runs on two crons: `0 6 * * *` (09:00 Israel) and `0 14 * * *` (17:00 Israel). Also supports `workflow_dispatch` for manual triggers. Injects all secrets as env vars and runs `python -m agent.run`.

---

## System Flow (Full)

```
New user signs up on Vercel page
  → POST /api/signup
  → Supabase: vault.create_secret(password) → store UUID in users table
  → GitHub API: trigger workflow_dispatch (immediate first run)

GitHub Actions cron fires (twice daily)
  → python -m agent.run
  → Supabase RPC get_active_users() — joins vault to decrypt passwords
  → For each user:
      → Piazza login with decrypted credentials
      → Fetch all posts (feed → individual posts, 1.5s delay, retry on rate limit)
      → Parse: strip HTML, extract fields
      → Filter: keep only posts where nr > last_post_nr
      → Load assignment goals from Supabase (optional)
      → Summarize:
          ≤13 posts → single Groq call
          >13 posts → batch (13/batch) → summarize each → merge
          On 429 → fallback to llama-3.1-8b
      → Gmail SMTP → send HTML email
      → Supabase: update last_post_nr to max nr seen
      → Sleep 15s before next user
```

---

## Interview Questions & Answers

### Architecture & Design

**Q: Why did you choose GitHub Actions as the scheduler instead of running a server?**

A: The agent only needs to run twice a day — a persistent server would be paying for compute 24/7 to run a 1-minute job. GitHub Actions gives us free cron scheduling on existing infrastructure with zero ops overhead. The tradeoff is that cron timing isn't exact (GitHub can delay runs by minutes to hours under load), which is acceptable for a daily digest but would be wrong for anything time-sensitive.

**Q: Why is there no Flask or FastAPI backend?**

A: The system has no need for a persistent backend. The signup/unsubscribe endpoints are simple, infrequent operations — Vercel serverless functions handle them with zero cold-start issues at this scale. The agent itself is a batch job, not a service. Adding a server would introduce cost, uptime concerns, and complexity for no benefit.

**Q: How does the checkpoint system work and why is it per-user?**

A: Each user has a `last_post_nr` column. After a run, it's updated to the highest post number seen. On the next run, only posts with `nr > last_post_nr` are processed. It's per-user because users register at different times — a student who signs up mid-semester should get a catchup report on all existing posts, not just future ones.

**Q: Why batch posts into groups of 13 instead of sending everything at once?**

A: LLMs have token limits. A course with 100 posts at ~600 chars each would easily exceed the context window. Batching keeps each individual API call small and predictable. The merge step then combines batch summaries into one unified report — this adds one extra LLM call but avoids context overflow entirely.

---

### Security

**Q: How are Piazza passwords stored?**

A: Via Supabase Vault, which is built on `pgsodium` (libsodium). The plaintext password is never written to the `users` table. On signup, we call a `vault.create_secret()` SQL function that encrypts the password with a key managed by Supabase at the infrastructure level and returns a UUID. That UUID is stored in the `users` table. At query time, the `get_active_users()` RPC joins with `vault.decrypted_secrets` to decrypt on the fly. Even a full database dump would only expose encrypted ciphertext.

**Q: What's still a security risk in this system?**

A: The `SUPABASE_SERVICE_KEY` in GitHub Actions secrets. Anyone with that key can call the `get_active_users()` RPC and receive decrypted passwords. This is unavoidable — the agent needs to read passwords at runtime to log into Piazza. The vault protects against database breaches, not against a compromised service key. A future improvement would be storing passwords in a dedicated secrets manager (like AWS Secrets Manager) where access can be scoped per-secret.

**Q: Can a user see someone else's Piazza password?**

A: No. The `get_active_users()` RPC is defined with `SECURITY DEFINER`, meaning it runs with the privileges of its creator (the service role), not the caller. The `vault.decrypted_secrets` view is not directly accessible to client-side Supabase keys. Only the server-side service key used by GitHub Actions can call the RPC.

---

### AI & LLM

**Q: How do you handle LLM rate limits?**

A: Two layers. First, `groq_client.py` catches 429 errors from the primary model (`llama-3.3-70b-versatile`) and automatically retries with a fallback model (`llama-3.1-8b-instant`). Second, the merge prompt is dynamically truncated so it always fits within the fallback model's smaller token-per-minute limit (6,000 TPM). Each batch summary is capped at `16000 // num_batches` characters before being passed to the merge call.

**Q: How do you ensure the AI always includes post links in its output?**

A: Two-layer enforcement. The system prompt (`SYSTEM_SUMMARIZER`) states the rule explicitly. The user prompt (`build_summary_prompt`) repeats it and embeds the Piazza links directly in the post data passed to the model — so the model has the formatted `[#nr](url)` strings right next to each post's content and just has to copy them.

**Q: Why temperature 0.3?**

A: Lower temperature makes the model more deterministic and factual — appropriate for a digest where we want accurate summaries of what was actually said, not creative reinterpretation. High temperature would risk the model hallucinating details or paraphrasing instructor answers inaccurately.

---

### Scraping & Rate Limiting

**Q: How do you handle Piazza's rate limiting?**

A: Three mechanisms: (1) a 1.5-second sleep between every individual post fetch, (2) a 15-second cooldown between users since all users share the same Piazza account and the rate limit is per-account, (3) exponential backoff retry — when a "too fast" error is detected, the code waits 5s, 10s, then 15s before giving up on that post. Previously the code silently dropped rate-limited posts; now it retries them.

**Q: Why do you fetch each post individually instead of using a bulk API?**

A: The `piazza-api` library's feed endpoint returns metadata (IDs, subjects) but not the full post content including instructor answers and follow-ups. To get the complete data needed for summarization, each post must be fetched individually. This is a limitation of the Piazza API design — there's no bulk content endpoint.

---

### General Engineering

**Q: What would break first if this scaled to 1,000 users?**

A: The Piazza account would get banned. All users currently share a single Piazza login, so 1,000 users fetching 100 posts each means 100,000 individual API calls per run from one account. Piazza would likely detect and block this. The fix would be to use each student's own Piazza credentials (which is the current design) but add deduplication — if two users are enrolled in the same course, fetch the posts once and send to both.

**Q: What's the worst-case runtime for one run?**

A: With the current 3 users and largest course having ~76 posts: fetching = 76 × 1.5s = ~2 minutes, plus retries. Add batching and Groq calls (~30s each × 6 batches + merge). Total per user: ~4-5 minutes. Three users + 15s gaps: ~15 minutes. That's right at the GitHub Actions timeout. If more users or larger courses are added, the 15-minute timeout could be hit.

**Q: How would you improve this system if you had more time?**

A: (1) Deduplication — detect when multiple users share a course and fetch once. (2) Per-course scheduling instead of per-user — one Piazza session per course per run. (3) Webhook instead of cron — Piazza doesn't expose webhooks, but if it did, running on-demand would be more efficient than polling. (4) Better rate limit handling — track remaining quota and pre-emptively slow down rather than reacting to errors.
