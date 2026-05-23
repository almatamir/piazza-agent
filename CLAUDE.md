# Piazza Agent — Claude Code Guidelines

## Code Language Rule
**All code files must be in English only.**
This includes: variable names, comments, log messages, string literals, error messages, and docstrings.

Hebrew is allowed only inside prompt strings that are sent to the AI model (e.g. in `ai/prompts.py` the `SYSTEM_SUMMARIZER` may instruct the model to reply in Hebrew — that is fine). All surrounding Python code must remain in English.

## Project Overview
An autonomous AI agent that scrapes Piazza posts, summarizes them with Groq AI, and emails a structured report on a schedule.

## Key Files
- `config/settings.py` — all configuration loaded from `.env`
- `scraper/piazza_client.py` — Piazza login and post fetching
- `scraper/parser.py` — converts raw posts to structured dicts
- `ai/summarizer.py` — Groq-powered summarization
- `agent/runner.py` — main pipeline: fetches users from Supabase, runs the agent for each
- `agent/run.py` — entry point called by GitHub Actions cron
- `notifier/email_sender.py` — Resend API email delivery
- `storage/database.py` — Supabase CRUD (users, checkpoints, goals)
- `ui/index.html` + `ui/api/signup.py` — Vercel-hosted signup page

## Scheduling
Reports run via GitHub Actions cron (`.github/workflows/agent.yml`) at 06:00 and 14:00 UTC.
No local scheduler — do not add APScheduler or similar.

## .env vs .env.example
- `.env` — real credentials, never committed (gitignored)
- `.env.example` — placeholder template, safe to commit

## Report — Post Citations Rule
Every bullet point or highlight in any generated report MUST include a Piazza post reference and link.

Format: `[#nr](https://piazza.com/class/{course_id}?cid={nr})`

- The `nr` is the post number visible on Piazza (not the internal `id`)
- Links must be real and clickable — no placeholders
- This applies to all four report sections: Main Topics, Instructor Takeaways, Open Questions, Action Items
- Never write a claim or summary point without citing its source post

## Error Handling
Use try/except on all external calls (Piazza API, Groq API, Resend). Log warnings for recoverable errors, raise RuntimeError for fatal ones. Never silently swallow exceptions.
