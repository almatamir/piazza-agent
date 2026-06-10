# Interview Prep — Piazza Agent

---

## 30-Second Pitch

Piazza Agent is an autonomous AI agent that monitors a university course forum, summarizes new posts using an LLM, and emails a structured digest to registered students twice a day. It runs entirely serverlessly — GitHub Actions for scheduling, Vercel for the signup UI, Supabase for storage, and Groq for AI. No backend server, no daemon, no manual intervention.

---

## File-by-File Breakdown

### `agent/run.py`
Entry point called by GitHub Actions as `python -m agent.run`. Sets up logging, applies `socket.setdefaulttimeout(30)` to prevent any network call from hanging indefinitely, then calls `run_all()`.

### `agent/runner.py`
The pipeline orchestrator. `run_all()` fetches all active users from Supabase, **groups them by Piazza account** (`piazza_email`), logs in once per unique account, then processes each user's course under the shared session.

`run_for_user(user, piazza_session)` is the full per-user flow:
1. Connect to the user's course using the shared Piazza session
2. Fetch the feed, filter to only posts where `nr > last_post_nr`
3. Download only those new posts individually
4. Load optional assignment context from Supabase
5. Summarize with Groq
6. Email the report via Gmail SMTP
7. Update the checkpoint

### `scraper/piazza_client.py`
Wraps `piazza-api`. Key functions:
- `piazza_login(email, password)` — creates a `Piazza` session object (called once per unique account)
- `get_network(session, course_id)` — connects the existing session to a specific course
- `fetch_posts(network, since_nr)` — gets the feed (metadata only, one request), filters by `nr > since_nr` before downloading anything, then fetches only new posts with 1.5s delay and exponential backoff retry (5s → 10s → 15s) on "too fast" errors

### `scraper/parser.py`
Converts raw Piazza API dicts (nested HTML) into clean flat dicts. Regex-strips HTML tags, unescapes entities, extracts: `nr`, `subject`, `body`, `instructor_answer`, `student_followups`, `tags`, `created`. Drops malformed posts silently and logs a count.

### `ai/groq_client.py`
Thin Groq SDK wrapper. `chat(prompt, system, max_tokens)` tries the primary model (`llama-3.3-70b-versatile`) first; on 429, falls back to `llama-3.1-8b-instant`. Temperature fixed at 0.3. `max_tokens` parameter controls output length — critical for keeping batch summaries small enough to merge safely.

### `ai/prompts.py`
All prompt templates:
- `SYSTEM_SUMMARIZER` — defines the AI persona and enforces the post-citation rule (`[#nr](url)` on every bullet)
- `build_summary_prompt(posts, tag, context, course_id)` — builds the batch prompt with post content and pre-formatted Piazza links embedded directly in the data
- `build_merge_prompt([summary_a, summary_b], tag)` — merges exactly 2 summaries at a time; dynamically caps each at `16000 // 2` chars as a safety net

### `ai/summarizer.py`
The most complex module. Three tiers:
1. **≤25 posts** → single `_chat_with_retry` call, `max_tokens=2500`
2. **>25 posts** → split into batches of 25, summarize each with `max_tokens=1200`, then `_progressive_merge`
3. **`_progressive_merge`** — folds summaries sequentially: `(s1+s2)→r`, `(r+s3)→r`, `(r+s4)→final`

**`_chat_with_retry`** wraps every Groq call:
- Sleeps 20s after every successful call (proactive TPM throttling)
- On 429 or 413: sleeps 60s and retries, up to 3 attempts total
- On any other error: raises immediately

### `ai/pdf_extractor.py`
One-off utility. Uses PyMuPDF (`fitz`) to extract text from an assignment PDF, sends it to Groq, and returns structured JSON: `title`, `topics`, `parts`, `submission_requirements`, `key_constraints`. Stored in Supabase `assignment_goals` table and later injected as context into the summarization prompt.

### `notifier/email_sender.py`
Gmail SMTP delivery via Python's built-in `smtplib`. `send_report(to, subject, body_md)` converts Markdown to HTML with a custom 30-line converter (no external library), then sends both HTML and plain-text parts. Authenticates with a Gmail App Password — no domain ownership required.

### `storage/supabase_client.py`
Singleton Supabase client. Initializes once from env vars, reused across all DB calls in a run.

### `storage/database.py`
All Supabase operations, all vault-aware:
- `get_all_active_users()` → calls `get_active_users()` RPC which joins `vault.decrypted_secrets`
- `update_last_post_nr(user_id, nr)` → direct table update
- `add_user(...)` → calls `add_user()` RPC which runs `vault.create_secret()` before inserting
- `get_goals(course_id)` / `save_goals(course_id, goals)` → `assignment_goals` table

### `config/settings.py`
Single source of truth. All env vars loaded from `.env` via `python-dotenv`. No logic — just string constants.

### `ui/index.html`
Static signup form deployed to Vercel. Fields: report email, Piazza login email, Piazza password, Piazza course URL. Submits JSON to `/api/signup`.

### `ui/api/signup.py`
Vercel serverless function (`BaseHTTPRequestHandler`). Validates all fields, parses the course ID from the Piazza URL, calls the `add_user` Supabase RPC (password goes directly to Vault — never stored plaintext), then fires `workflow_dispatch` via GitHub REST API for an immediate first report.

### `ui/api/unsubscribe.py`
Vercel serverless function. Accepts `{email}`, deletes the user's row from Supabase.

### `.github/workflows/agent.yml`
Two crons: `0 6 * * *` (09:00 Israel) and `0 14 * * *` (17:00 Israel). Supports `workflow_dispatch`. Python 3.11, pip cache, secrets injected as env vars, runs `python -m agent.run`, 15-minute timeout.

---

## Full System Flow

```
USER SIGNUP
  Browser → POST /api/signup (Vercel)
    → validate fields
    → parse course_id from Piazza URL
    → Supabase RPC add_user():
        vault.create_secret(password) → returns UUID
        INSERT users (email, piazza_email, password_secret_id, course_id)
    → GitHub REST API: POST workflow_dispatch → immediate first run

SCHEDULED RUN (twice daily via GitHub Actions)
  python -m agent.run
    → socket.setdefaulttimeout(30)
    → Supabase RPC get_active_users()
        JOIN vault.decrypted_secrets → returns plaintext passwords in memory only
    → Group users by piazza_email

  For each unique Piazza account:
    → piazza_login(email, password)  ← ONCE per account

    For each course under this account:
      → get_network(session, course_id)
      → get_feed()  → filter items where nr > last_post_nr
      → If 0 new: skip immediately (no post downloads)
      → Fetch only new posts (1.5s delay, retry on "too fast")
      → parse_posts(): strip HTML, extract fields
      → get_goals(course_id): optional assignment context from Supabase

      Summarize:
        ≤25 posts → _chat_with_retry(build_summary_prompt, max_tokens=2500)
        >25 posts →
          for each batch of 25:
            _chat_with_retry(build_summary_prompt, max_tokens=1200)
            sleep(20s)
          progressive merge:
            _chat_with_retry(merge(s1,s2), max_tokens=2000) → r
            _chat_with_retry(merge(r, s3), max_tokens=2000) → r
            ...

        On 429/413: sleep(60s), retry up to 3×
        On 70B 429: fallback to 8B automatically

      → Gmail SMTP: send HTML email
      → Supabase: update last_post_nr = max(nr) of fetched posts
      → sleep(10s) before next user

UNSUBSCRIBE
  POST /api/unsubscribe (Vercel)
    → DELETE FROM users WHERE email = ?
```

---

## Interview Questions & Answers

### Architecture & Design

**Q: Why no Flask/FastAPI backend? Why GitHub Actions?**

The agent runs twice a day for ~3 minutes. A persistent server would pay for 24/7 compute to execute a ~3-minute job. GitHub Actions gives free cron scheduling with zero ops — no server to maintain, no uptime to monitor. The tradeoff is imprecise timing (GitHub can delay cron runs by minutes to hours under load), which is fine for a digest but unacceptable for real-time systems. The signup/unsubscribe endpoints are infrequent and stateless, so Vercel serverless functions handle them perfectly.

**Q: You group users by Piazza account and login once. Why did you build it that way?**

Originally we logged in once per user — even if two users shared the same Piazza account. After 2 logins in rapid succession, Piazza started rate-limiting or hanging the 3rd login for 10+ minutes. Grouping by `piazza_email` and sharing a session means Piazza sees one human switching between course tabs, not 3 bots logging in repeatedly.

**Q: How does the checkpoint system work?**

Each user has a `last_post_nr` column in Supabase. After a successful run, it's updated to `max(nr)` of all posts processed. On the next run, `fetch_posts(network, since_nr=last_post_nr)` filters the feed before downloading — so posts already seen are never fetched individually. This matters because each individual post fetch costs 1.5 seconds. For a course with 76 posts where only 2 are new, the old approach fetched 76 × 1.5s = 114 seconds of content. The new approach fetches 2 × 1.5s = 3 seconds.

**Q: Walk me through what happens when a new user signs up.**

The signup form POSTs to the Vercel serverless endpoint. It validates the fields, extracts the course ID from the Piazza URL (everything after `/class/`), calls the Supabase `add_user()` RPC — which encrypts the password via Vault before inserting — then fires a `workflow_dispatch` event to GitHub to trigger an immediate agent run. The new user gets their first report within minutes of signing up rather than waiting for the next scheduled run.

**Q: What happens if the agent crashes halfway through processing users?**

Users already processed have their checkpoints updated, so they won't get duplicate reports. Users not yet processed simply don't get a report that run — they'll catch up at the next scheduled run. The runner wraps each user in a try/except, so one user's failure doesn't affect others. The only data loss scenario is if the run crashes after sending the email but before updating the checkpoint — the user would get a duplicate report at the next run. This is acceptable for a digest use case.

---

### Security

**Q: How are Piazza passwords stored and why does that matter?**

Via Supabase Vault, built on `pgsodium` (libsodium / XSalsa20 encryption). The plaintext password is never written to the `users` table. On signup, `vault.create_secret(password)` encrypts it using a key managed by Supabase at the infrastructure level — outside the database — and returns a UUID. That UUID is stored in `users.piazza_password_secret_id`. At query time, `get_active_users()` joins `vault.decrypted_secrets` to decrypt on the fly. A full database dump would only expose ciphertext — useless without Supabase's root key.

**Q: What are the remaining security risks?**

The `SUPABASE_SERVICE_KEY` in GitHub Actions secrets. Anyone with that key can call `get_active_users()` and receive decrypted passwords. This is unavoidable — the agent must read them at runtime. Vault protects against a database breach, not a compromised service key. A stricter design would use AWS Secrets Manager with per-secret IAM policies, but that's significant added complexity.

Also: passwords travel in process memory during the run and are visible in browser DevTools on signup (as POST body). The DevTools exposure is unavoidable for any login form and harmless since it requires physical access to that browser session. The memory exposure is equally unavoidable.

**Q: Why is `get_active_users()` defined with `SECURITY DEFINER`?**

`SECURITY DEFINER` means the function runs with the privileges of its creator (the Supabase service role), not the caller. Without it, a client-side key could try to call the function and — depending on RLS policies — potentially access vault data it shouldn't. With `SECURITY DEFINER`, only callers presenting the service role key get the decrypted output.

**Q: Could a malicious user submit a signup form and exfiltrate other users' data?**

No. The signup endpoint only calls `add_user()` which inserts a new row — it has no access to existing rows or vault secrets. The `get_active_users()` function is only callable with the service key, which never leaves the GitHub Actions environment. There's no endpoint that reads user data back to the client.

---

### AI & LLM

**Q: Walk me through the full summarization flow for 73 posts.**

73 posts exceed the batch size of 25, so: split into 3 batches (25, 25, 23). Each batch is summarized with `_chat_with_retry(max_tokens=1200)` — capping output so each summary stays small. After each call, we sleep 20s to let Groq's TPM window refresh. Then progressive merge: `merge(batch1, batch2)` → intermediate, `merge(intermediate, batch3)` → final report. Each merge call has exactly 2 inputs and uses `max_tokens=2000`. Total: 5 Groq API calls, ~100s of proactive sleeping, ~3-6 minutes total.

**Q: Why progressive merge instead of merging all summaries at once?**

Merging all N summaries at once creates an input proportional to N × summary_length. With 6 batches × 1200 tokens each = 7200 tokens input — which exceeds the fallback model's 6000 TPM limit, causing a 413 error. Progressive merge keeps every call at exactly 2 inputs, so the payload is always bounded at ~2400 tokens regardless of how many batches there are.

**Q: Why cap batch summaries at 1200 tokens but the final report at 2500?**

Batch summaries are intermediate products — they get consumed by the merge step. Keeping them short (1200 tokens) ensures two of them fit comfortably within 6000 tokens for the merge call. The final report has no downstream size constraint (it's just an email), so we give it more room (2500 tokens) to be comprehensive.

**Q: How do you handle Groq rate limits? Walk through the layers.**

Three layers: (1) **Model fallback** — the primary 70B model has a lower TPM limit; on 429 we immediately retry with the 8B model. (2) **Proactive throttling** — `_chat_with_retry` sleeps 20 seconds after every successful call, spreading requests across time so we don't burst through the TPM window. (3) **Reactive retry** — if we still hit 429 or 413, we sleep 60 seconds and retry the same request up to 3 times before failing hard.

**Q: Why temperature 0.3?**

Lower temperature = more deterministic output. For a factual digest of forum posts, we want the model to accurately reproduce what was said, not creatively rephrase it. High temperature increases the risk of the model hallucinating details, inventing instructor rulings that weren't stated, or paraphrasing answers in misleading ways. 0.3 is a common choice for summarization tasks; 0.0 would be fully deterministic but sometimes produces repetitive text.

**Q: How do you guarantee every bullet includes a post link?**

Two-layer enforcement. First, the system prompt (`SYSTEM_SUMMARIZER`) states the rule: every bullet must end with `([#nr](url))`. Second, `build_summary_prompt` embeds the formatted Piazza link (`[#42](https://piazza.com/class/xyz?cid=42)`) directly next to each post's content in the prompt — so the model sees the exact string it needs to copy rather than having to construct it from memory.

**Q: What is the `pdf_extractor.py` for and how does it fit in?**

It's a one-off utility run manually before a new assignment cycle. It reads a PDF assignment spec using PyMuPDF, sends the extracted text to Groq, and gets back structured JSON: topics, parts, constraints. That JSON is stored in the `assignment_goals` table and later injected as context into `build_summary_prompt`. This means the summarizer understands what the assignment is actually about — it can flag posts that relate to submission requirements or specific constraints rather than just grouping them generically.

---

### Scraping & Rate Limiting

**Q: Why fetch each post individually? Why not a bulk endpoint?**

The `piazza-api` feed endpoint returns only metadata (IDs, post numbers, subjects) — not the full content. Instructor answers, student follow-ups, and full post bodies require individual fetches per post. This is a Piazza API design limitation. There is no bulk content endpoint.

**Q: What happens when Piazza says "too fast"?**

The scraper catches `RequestError` and checks if "too fast" appears in the message. If so, it waits `5 × (attempt + 1)` seconds — 5s, 10s, 15s — and retries up to 3 times before skipping that post. Previously the code silently dropped rate-limited posts, which caused entire courses to be summarized with missing data.

**Q: How did you discover the Piazza login hang and fix it?**

The GitHub Actions logs showed the run stuck for 10+ minutes with the last log line being "Running for user X" — before even the "Logged in to Piazza" line. That meant `p.user_login()` was hanging inside the `piazza-api` library. The root cause: Piazza was throttling repeated logins from the same account (we had 3 logins per run). The fix was session sharing — login once per unique account and reuse the `Piazza` object for all courses. We also added `socket.setdefaulttimeout(30)` so any future hanging network call fails after 30 seconds rather than blocking indefinitely.

---

### General Engineering

**Q: What's the worst-case runtime and does it fit in GitHub Actions' 15-minute limit?**

With 3 users sharing 1 Piazza account and the largest course having 76 new posts:
- 1 login
- Fetching 76 posts: 76 × 1.5s = ~2 minutes + retries
- Summarization: 3 batches × (Groq call + 20s sleep) + 2 merge calls = ~3 minutes
- Email delivery: ~2s
- Two more courses (if no new posts): near-instant (feed check only)

Total: ~5-6 minutes in the normal case. Worst case with Groq retries (3 × 60s): ~9 minutes. Still within the 15-minute timeout, but with limited headroom as the user base grows.

**Q: What would break first at 100 users?**

The Groq free tier. 100 users × 3 batches × 1 Groq call each = 300 API calls per run. Even with 20s delays that's 100 minutes of wall time — far over the 15-minute GitHub Actions timeout. Solution: upgrade to Groq's paid tier (500k TPM vs 6k), or parallelize users across multiple workflow jobs.

**Q: What would break first at 1,000 users?**

Two things simultaneously: (1) Piazza would ban the shared account — even with session sharing, 1,000 course fetches from one account looks like a bot. Solution: each user provides their own Piazza credentials and we use deduplication (if 10 users share a course, fetch once and send to all 10). (2) The GitHub Actions single-job architecture doesn't scale — we'd need a job matrix or a proper queue-based worker.

**Q: How would you add deduplication for users in the same course?**

Group users not just by `piazza_email` but also by `piazza_course_id`. For each unique course, fetch and summarize once. Then send the same report to all users enrolled in that course. The checkpoint update becomes: update `last_post_nr` for all users in the group. This reduces Piazza API calls from N (one per user) to M (one per unique course), where M ≤ N.

**Q: Why use Vercel for the signup UI instead of a GitHub Pages static site?**

The signup form needs server-side logic — it writes to Supabase and triggers a GitHub Actions workflow. A static site can't do that without exposing credentials in frontend JavaScript. Vercel serverless Python functions give us a proper backend handler without running a server. The alternative would be a dedicated API endpoint, which adds infrastructure to maintain.

**Q: Why did you write your own Markdown-to-HTML converter instead of using a library?**

The reports use a small, predictable subset of Markdown: headers, bold, links, and bullet points. A full Markdown library (like `markdown2` or `mistune`) adds a dependency for functionality we use maybe 10%. The custom converter is 30 lines and handles everything we need. No version conflicts, no transitive dependencies, no surprises.

**Q: GitHub Actions cron doesn't run at exact times — is that a problem?**

For this use case, no. A digest that arrives at 09:15 instead of 09:00 is indistinguishable from the user's perspective. If exact timing were required (e.g., trading signals, time-sensitive alerts), the fix would be to use an external reliable cron service (like cron-job.org) to trigger `workflow_dispatch` via the GitHub API at the exact scheduled time — GitHub just executes on demand, which is precise.
