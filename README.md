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

1. **Logs in** to Piazza with your credentials
2. **Fetches** all posts newer than the last run
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
  Supabase (users table)
        │
        ▼
GitHub Actions cron (06:00 + 14:00 UTC)
        │
        ├── Piazza API → fetch new posts
        ├── Groq LLaMA 70B → summarize & cluster
        └── Resend → deliver email report
```

---

## Stack

| Layer | Tech |
|---|---|
| Scraper | [`piazza-api`](https://github.com/hfaran/piazza-api) |
| AI | Groq — `llama-3.3-70b-versatile` |
| Email delivery | [Resend](https://resend.com) |
| Database | [Supabase](https://supabase.com) (PostgreSQL) |
| Scheduler | GitHub Actions cron |
| Signup UI | Vercel (HTML + Python serverless) |

---

## Project structure

```
piazza-agent/
├── agent/
│   ├── run.py          # GitHub Actions entry point
│   └── runner.py       # per-user pipeline orchestration
├── ai/
│   ├── groq_client.py  # Groq API wrapper
│   ├── prompts.py      # system prompt + report builder
│   └── summarizer.py   # batching + merge logic
├── scraper/
│   ├── piazza_client.py # login + feed fetching
│   └── parser.py        # HTML stripping + post normalization
├── notifier/
│   └── email_sender.py  # Resend delivery + markdown→HTML
├── storage/
│   ├── database.py      # Supabase CRUD
│   └── supabase_client.py
├── config/
│   └── settings.py      # env-based config
├── ui/
│   ├── index.html        # signup landing page
│   └── api/signup.py     # Vercel serverless handler
└── .github/workflows/
    └── agent.yml         # cron schedule
```

---

## Self-hosting

### 1. Clone & install

```bash
git clone https://github.com/your-username/piazza-agent.git
cd piazza-agent
pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Fill in `.env`:

```env
GROQ_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
RESEND_API_KEY=...
```

### 3. Set up Supabase

Create a `users` table:

```sql
create table users (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  piazza_email text not null,
  piazza_password text not null,
  piazza_course_id text not null,
  last_post_nr integer default 0,
  active boolean default true,
  created_at timestamptz default now()
);
```

### 4. Add GitHub Actions secrets

In your repo → **Settings → Secrets → Actions**, add:

- `GROQ_API_KEY`
- `RESEND_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

The agent will then run automatically at **09:00 and 17:00 Israel time** every day.

### 5. Deploy the signup UI (optional)

```bash
cd ui
vercel deploy
```

Set the same four environment variables in Vercel's project settings.

---

## Running manually

```bash
python -m agent.run
```

Or trigger a run from the GitHub Actions tab using **Run workflow**.

---

## Key design decisions

- **Per-user isolation** — credentials are passed directly at runtime, never shared between users
- **Checkpoint system** — each user's `last_post_nr` is stored in Supabase so only new posts are processed each run
- **Batching** — when a course has many posts, they are split into batches of 13 and merged into a single report to stay within LLM token limits
- **No local scheduler** — GitHub Actions handles all scheduling; no daemon process needed
