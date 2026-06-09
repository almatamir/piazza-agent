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

1. **Logs in** to Piazza with each user's credentials
2. **Fetches** all posts newer than the last run (per-user checkpoint)
3. **Summarizes** them with Groq AI — grouping by topic, surfacing instructor answers, flagging open questions
4. **Emails** a structured, fully self-contained report with links to every source post

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
        ├── Piazza API → fetch new posts (with retry on rate limit)
        ├── Groq LLaMA 70B → summarize & cluster (fallback: LLaMA 8B)
        └── Gmail SMTP → deliver email report
```

---

## Stack

| Layer | Tech |
|---|---|
| Scraper | [`piazza-api`](https://github.com/hfaran/piazza-api) |
| AI | Groq — `llama-3.3-70b-versatile` (fallback: `llama-3.1-8b-instant`) |
| Email delivery | Gmail SMTP |
| Database | [Supabase](https://supabase.com) (PostgreSQL + Vault encryption) |
| Scheduler | GitHub Actions cron |
| Signup UI | Vercel (HTML + Python serverless) |

---

## Project structure

```
piazza-agent/
├── agent/
│   ├── run.py               # GitHub Actions entry point
│   └── runner.py            # per-user pipeline orchestration
├── ai/
│   ├── groq_client.py       # Groq API wrapper with model fallback
│   ├── prompts.py           # system prompt + report prompt builder
│   ├── summarizer.py        # batching + merge logic
│   └── pdf_extractor.py     # extracts assignment goals from PDFs
├── scraper/
│   ├── piazza_client.py     # login, feed fetching, rate-limit retry
│   └── parser.py            # HTML stripping + post normalization
├── notifier/
│   └── email_sender.py      # Gmail SMTP delivery + markdown→HTML
├── storage/
│   ├── database.py          # Supabase CRUD via RPC (vault-aware)
│   └── supabase_client.py   # singleton Supabase client
├── config/
│   └── settings.py          # env-based configuration
├── ui/
│   ├── index.html           # signup landing page
│   ├── vercel.json          # Vercel routing config
│   └── api/
│       ├── signup.py        # Vercel serverless signup handler
│       └── unsubscribe.py   # Vercel serverless unsubscribe handler
└── .github/workflows/
    └── agent.yml            # cron schedule + secrets injection
```

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

Fill in `.env`:

```env
GROQ_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

### 3. Set up Supabase

Enable the **Vault** extension, then run:

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

-- Assignment goals (optional — used for PDF context)
create table assignment_goals (
  course_id text primary key,
  goals_json jsonb
);

-- RPC: read active users with decrypted passwords
create or replace function get_active_users()
returns table (id uuid, email text, piazza_email text, piazza_password text, piazza_course_id text, last_post_nr bigint, active boolean)
language sql security definer as $$
  select u.id, u.email, u.piazza_email,
         ds.decrypted_secret::text,
         u.piazza_course_id, u.last_post_nr, u.active
  from users u
  join vault.decrypted_secrets ds on ds.id = u.piazza_password_secret_id
  where u.active = true;
$$;

-- RPC: insert new user with vault-encrypted password
create or replace function add_user(p_email text, p_piazza_email text, p_piazza_password text, p_piazza_course_id text)
returns uuid language plpgsql security definer as $$
declare
  v_secret_id uuid;
  v_user_id uuid;
begin
  v_secret_id := vault.create_secret(p_piazza_password, 'piazza_pwd_' || gen_random_uuid()::text);
  insert into users (email, piazza_email, piazza_password_secret_id, piazza_course_id)
  values (p_email, p_piazza_email, v_secret_id, p_piazza_course_id)
  returning id into v_user_id;
  return v_user_id;
end;
$$;
```

### 4. GitHub Actions secrets

In your repo → **Settings → Secrets → Actions**, add:

- `GROQ_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

The agent will run automatically at **09:00 and 17:00 Israel time** every day.

### 5. Deploy the signup UI (optional)

```bash
cd ui
vercel deploy
```

Set the same environment variables in Vercel's project settings.

---

## Running manually

```bash
python -m agent.run
```

Or trigger from the GitHub Actions tab using **Run workflow**.

---

## Key design decisions

- **Vault-encrypted credentials** — Piazza passwords are stored encrypted via Supabase Vault (pgsodium/libsodium). The plaintext never exists in the database; decryption happens at query time through a secure RPC function.
- **Per-user checkpoint** — each user stores their own `last_post_nr` so only genuinely new posts are processed each run. New users get a full catchup on signup.
- **Batching with merge** — posts are split into batches of 13 for summarization, then merged in a second LLM call to stay within token limits.
- **Model fallback** — if the primary LLaMA 70B model is rate limited, the agent automatically retries with LLaMA 8B.
- **Rate-limit retry** — Piazza API throttles aggressive fetching. The scraper detects "too fast" errors and retries with exponential backoff (5s → 10s → 15s) instead of silently dropping posts.
- **No local scheduler** — GitHub Actions handles all scheduling; no daemon or server needed.
- **Mandatory post citations** — every AI-generated bullet must end with `([#nr](url))`, enforced in both the system and user prompt.
