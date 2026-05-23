# 📚 Piazza Agent — Project Planning

## 🎯 Project Goal
An autonomous AI agent that:
1. Connects to a Piazza course page using the user's credentials
2. Scans questions and instructor answers
3. Generates a smart summary report with key highlights
4. Runs automatically twice a day and sends email updates
5. Exposes a chat interface to ask questions about the course content

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Scheduler                         │
│              (every 12 hours)                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Piazza Agent                       │
│  1. Fetch new posts from Piazza                     │
│  2. Compare to last checkpoint                      │
│  3. Send new content to AI for analysis             │
│  4. Save to database                                │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
           ▼                          ▼
   Update Database             Send Email Report
   (SQLite)                    (Gmail SMTP)
           │
           ▼
   Streamlit UI
   (Report view + Chat)
```

---

## 📁 Project File Structure

```
piazza-agent/
│
├── .env                          # API keys — NOT in Git!
├── .gitignore
├── README.md
├── PLANNING.md                   # This file
├── requirements.txt
│
├── config/
│   └── settings.py               # Global settings (timing, email, etc.)
│
├── scraper/
│   ├── __init__.py
│   ├── piazza_client.py          # Piazza login + post fetching
│   └── parser.py                 # Convert raw data to structured JSON
│
├── ai/
│   ├── __init__.py
│   ├── groq_client.py            # Groq API connection (free)
│   ├── summarizer.py             # Summarize questions + extract highlights
│   └── prompts.py                # All prompts in one place
│
├── agent/
│   ├── __init__.py
│   ├── checkpoint.py             # Track what was already processed
│   ├── scheduler.py              # APScheduler — run every 12 hours
│   └── agent.py                  # Main agent logic
│
├── notifier/
│   ├── __init__.py
│   ├── email_sender.py           # Send HTML email report
│   └── templates/
│       └── report.html           # Email HTML template
│
├── storage/
│   ├── __init__.py
│   ├── database.py               # SQLite — posts + checkpoints
│   └── piazza.db                 # Auto-created, NOT in Git
│
└── ui/
    ├── app.py                    # Streamlit main app
    └── components/
        ├── report_view.py        # Display latest report
        └── chat_view.py          # Chat with course data
```

---

## 🔑 .env File Template

```env
# Groq API — Free at https://console.groq.com
GROQ_API_KEY=your_key_here

# Piazza credentials
PIAZZA_EMAIL=your@email.com
PIAZZA_PASSWORD=your_password

# Gmail — use App Password (not your real password)
# Guide: https://support.google.com/accounts/answer/185833
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Agent settings
CHECK_INTERVAL_HOURS=12
NOTIFY_EMAIL=destination@email.com
```

---

## 📦 requirements.txt

```
piazza-api==1.3
groq
apscheduler
streamlit
python-dotenv
jinja2
```

---

## 🛠️ Tech Stack Decisions

| Component | Tool | Why |
|-----------|------|-----|
| AI Model | Groq (Llama 3.3 70B) | Free, fast, great quality |
| Scheduling | APScheduler | Simple, runs inside Python |
| Database | SQLite | Zero setup, file-based |
| Email | Gmail SMTP | Free, no external service |
| UI | Streamlit | Fast to build, looks professional |
| Piazza access | piazza-api library | Unofficial but works |

---

## 📋 Work Plan — Step by Step

### ✅ Phase 1 — Setup (Day 1)
- [ ] Create GitHub repo
- [ ] Create base files: `.gitignore`, `README.md`, `requirements.txt`
- [ ] Set up `.env` with keys
- [ ] Write `config/settings.py`

### ✅ Phase 2 — Scraper (Days 2–3)
- [ ] `piazza_client.py` — login + fetch posts from course ID
- [ ] Extract course ID from URL: `https://piazza.com/class/{course_id}`
- [ ] `parser.py` — extract question, student body, instructor answer, date, post ID
- [ ] Test: print 5 questions to console

### ✅ Phase 3 — AI Summarizer (Days 4–5)
- [ ] `groq_client.py` — connect to Groq API
- [ ] `prompts.py` — write summarization prompts
- [ ] `summarizer.py` — send batch of questions, receive structured report
- [ ] Test: summarize 10 questions

### ✅ Phase 4 — Storage + Checkpoint (Day 6)
- [ ] `database.py` — SQLite tables: `posts`, `checkpoints`, `reports`
- [ ] `checkpoint.py` — save last seen post ID + timestamp

### ✅ Phase 5 — Agent + Scheduler (Days 7–8)
- [ ] `agent.py` — main loop: fetch → compare → analyze → notify
- [ ] `scheduler.py` — APScheduler every 12 hours
- [ ] Test: manual run, verify only new posts are processed

### ✅ Phase 6 — Email Notifier (Day 9)
- [ ] `report.html` — clean HTML email template
- [ ] `email_sender.py` — Gmail SMTP
- [ ] Test: send real email with sample report

### ✅ Phase 7 — UI (Days 10–12)
- [ ] `app.py` — Streamlit with 2 tabs
- [ ] `report_view.py` — display latest AI report
- [ ] `chat_view.py` — ask questions about course content

### ✅ Phase 8 — Polish (Days 13–14)
- [ ] Full README with screenshots and architecture diagram
- [ ] Clean code + docstrings
- [ ] Final push to GitHub

---

## 💡 How to Use This File with Claude Code

Start every Claude Code session with:
```
Read PLANNING.md. We are building the Piazza Agent project.
Today we are working on: [file name]
Here is the context: [paste any relevant details]
```

---

## ⚠️ Important Notes

- User credentials are stored **locally only** in `.env` — never committed to Git
- The agent only accesses courses the user is already enrolled in
- Add this to README: *"Credentials are stored locally and never sent to any external server"*

---

## 🌟 What Makes This Project Stand Out

1. **Autonomous AI Agent** — runs independently, not just on-demand
2. **End-to-end pipeline** — from raw data to email delivery
3. **Real problem solved** — students actually need this
4. **Clean architecture** — modular, each layer replaceable
5. **Documented prompts** — shows understanding of LLM engineering
