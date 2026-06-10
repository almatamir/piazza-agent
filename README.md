# Piazza Agent

> An autonomous AI agent that reads your course Piazza, summarizes everything that matters, and delivers it to your inbox — twice a day, automatically.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/Scheduler-GitHub_Actions-black?style=flat-square&logo=githubactions)
![Groq](https://img.shields.io/badge/AI-Groq_LLaMA_70B-orange?style=flat-square)
![Vercel](https://img.shields.io/badge/UI-Vercel-black?style=flat-square&logo=vercel)
![Supabase](https://img.shields.io/badge/DB-Supabase-3ECF8E?style=flat-square&logo=supabase&logoColor=white)

---

## What it does

Every morning and afternoon, the agent:

1. **Logs in** to Piazza once per account and reuses the session across all enrolled courses
2. **Fetches** only posts newer than the last run — filtered at the feed level before any individual download
3. **Summarizes** them with Groq AI — grouping by topic, surfacing instructor answers, flagging open questions
4. **Emails** a structured, fully self-contained report with clickable links to every source post

You never need to open Piazza to know what's going on.

---

## Report structure

Each email includes:

- `📌` **Topic clusters** — posts grouped by what they're actually about (derived dynamically, not hardcoded)
- `❓` **Open Questions** — unanswered posts, written out in full so you know exactly what's unresolved
- `✅` **Pre-Submission Checklist** — up to 8 actionable checks pulled from the most important instructor answers

Every bullet cites its source post: `[#42](https://piazza.com/class/xyz?cid=42)`

---

## Architecture

```
Signup form (Vercel)
        │
        ▼
  Supabase (users table + Vault encrypted passwords)
        │
        ▼
GitHub Actions cron (06:00 + 14:00 UTC)
        │
        ▼
  Group users by Piazza account → login ONCE per account
        │
        ├── For each course:
        │     ├── Piazza feed → filter by nr > checkpoint (skip already-seen)
        │     ├── Fetch only new posts (1.5s/post, retry on rate limit)
        │     ├── Groq LLaMA 70B → batch summarize (fallback: LLaMA 8B)
        │     │     └── Progressive merge: fold summaries one at a time
        │     └── Gmail SMTP → deliver HTML email
        │
        └── Supabase: update last_post_nr checkpoint per user
```

---

## Stack

| Layer | Tech | Notes |
|---|---|---|
| Scraper | [`piazza-api`](https://github.com/hfaran/piazza-api) | Session shared across courses, feed-level pre-filtering |
| AI | Groq `llama-3.3-70b-versatile` | Falls back to `llama-3.1-8b-instant` on 429 |
| AI orchestration | Custom batching + progressive merge | 25 posts/batch, 20s between calls, 3× retry on 429/413 |
| Email delivery | Gmail SMTP (`smtplib`) | App password auth, sends HTML + plain text |
| Database | [Supabase](https://supabase.com) PostgreSQL | Vault-encrypted passwords via pgsodium/libsodium |
| Scheduler | GitHub Actions cron | Free, no persistent server needed |
| Signup UI | Vercel serverless Python | Triggers immediate workflow run on signup |

---

## Project structure

```
piazza-agent/
├── agent/
│   ├── run.py               # Entry point: logging + socket timeout + run_all()
│   └── runner.py            # Groups users by Piazza account, runs pipeline per user
├── ai/
│   ├── groq_client.py       # Groq SDK wrapper: singleton, model fallback, max_tokens
│   ├── prompts.py           # System prompt + batch/merge prompt builders
│   ├── summarizer.py        # Batching, _chat_with_retry, progressive merge
│   └── pdf_extractor.py     # Extracts assignment goals from PDFs (one-off utility)
├── scraper/
│   ├── piazza_client.py     # Login, feed fetch, nr-level filtering, retry backoff
│   └── parser.py            # HTML stripping + post normalization
├── notifier/
│   └── email_sender.py      # Gmail SMTP + custom Markdown→HTML converter
├── storage/
│   ├── database.py          # Supabase CRUD via vault-aware RPC functions
│   └── supabase_client.py   # Singleton Supabase client
├── config/
│   └── settings.py          # All env vars in one place
├── ui/
│   ├── index.html           # Signup landing page (static)
│   ├── vercel.json          # Route config
│   └── api/
│       ├── signup.py        # Vercel serverless: validate → vault → trigger workflow
│       └── unsubscribe.py   # Vercel serverless: delete user row
└── .github/workflows/
    └── agent.yml            # Cron + workflow_dispatch + secrets injection
```

---

## Key design decisions

### Feed-level checkpoint filtering
The Piazza feed API returns post numbers (`nr`) before fetching content. We filter at the feed level so posts already seen are never downloaded individually — avoiding the 1.5s/post cost entirely for users with nothing new.

```python
# Before: fetch all 76 posts, then discard 74
raw_posts = fetch_posts(network)
new_posts = [p for p in all_posts if p["nr"] > last_post_nr]

# After: only download the 2 new ones
raw_posts = fetch_posts(network, since_nr=last_post_nr)
```

### Single Piazza session per account
All users sharing the same Piazza login are processed under one session. Previously, logging in 3× with the same account caused Piazza to rate-limit or hang the 3rd login for 10+ minutes.

### Vault-encrypted credentials
Piazza passwords are stored encrypted via Supabase Vault (pgsodium/libsodium). The plaintext never exists in the `users` table — only a UUID pointing to the vault secret. Decryption happens at query time through a `SECURITY DEFINER` RPC function inaccessible to client-side keys.

### Progressive LLM merge
Batch summaries are folded one at a time rather than all at once:
```
batch1_summary + batch2_summary → merged_12
merged_12 + batch3_summary      → merged_123
...
```
Each merge call has exactly 2 inputs, keeping the payload well within the 6,000 TPM limit of the fallback model.

### Groq rate limit strategy
Three layers:
1. **Model fallback** — primary 70B hits 429 → retry with 8B
2. **Output cap** — `max_tokens=1200` on batch calls keeps each summary small enough to merge safely
3. **`_chat_with_retry`** — 20s sleep after every call; 60s sleep + up to 3 retries on 429/413

### Network timeout
`socket.setdefaulttimeout(30)` applied at startup prevents piazza-api HTTP calls from hanging indefinitely if Piazza doesn't respond.

---

## Self-hosting

### 1. Clone & install

```bash
git clone https://github.com/your-username/piazza-agent.git
cd piazza-agent
pip install -r requirements.txt
```

### 2. Environment variables

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

### 3. Set up Supabase

Enable the **Vault** extension, then run in the SQL editor:

```sql
-- Users table
create table users (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  piazza_email text not null,
  piazza_password_secret_id uuid,
  piazza_course_id text not null,
  last_post_nr integer default 0,
  active boolean default true,
  created_at timestamptz default now()
);

-- Assignment goals (optional)
create table assignment_goals (
  course_id text primary key,
  goals_json jsonb
);

-- RPC: read active users with decrypted passwords
create or replace function get_active_users()
returns table (id uuid, email text, piazza_email text, piazza_password text,
               piazza_course_id text, last_post_nr bigint, active boolean)
language sql security definer as $$
  select u.id, u.email, u.piazza_email,
         ds.decrypted_secret::text,
         u.piazza_course_id, u.last_post_nr, u.active
  from users u
  join vault.decrypted_secrets ds on ds.id = u.piazza_password_secret_id
  where u.active = true;
$$;

-- RPC: insert new user with vault-encrypted password
create or replace function add_user(
  p_email text, p_piazza_email text,
  p_piazza_password text, p_piazza_course_id text
)
returns uuid language plpgsql security definer as $$
declare
  v_secret_id uuid;
  v_user_id uuid;
begin
  v_secret_id := vault.create_secret(
    p_piazza_password, 'piazza_pwd_' || gen_random_uuid()::text
  );
  insert into users (email, piazza_email, piazza_password_secret_id, piazza_course_id)
  values (p_email, p_piazza_email, v_secret_id, p_piazza_course_id)
  returning id into v_user_id;
  return v_user_id;
end;
$$;
```

### 4. GitHub Actions secrets

Repo → **Settings → Secrets → Actions**:

- `GROQ_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

### 5. Deploy the signup UI (optional)

```bash
cd ui && vercel deploy
```

Set the same env vars in Vercel project settings.

---

## Running manually

```bash
python -m agent.run
```

Or trigger from the GitHub Actions tab → **Run workflow**.
