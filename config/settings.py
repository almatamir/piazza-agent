import os
from dotenv import load_dotenv

load_dotenv()

# ─── Piazza ───────────────────────────────────────────────
PIAZZA_EMAIL = os.getenv("PIAZZA_EMAIL")
PIAZZA_PASSWORD = os.getenv("PIAZZA_PASSWORD")
PIAZZA_COURSE_ID = os.getenv("PIAZZA_COURSE_ID")

# ─── Groq AI ──────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─── Supabase ─────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# ─── Resend (sender) ──────────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = "Piazza Agent <onboarding@resend.dev>"
EMAIL_SUBJECT = "Piazza Report — Course Summary"

# ─── Report destination ────────────────────────────────────
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "tamiralma@icloud.com")

# ─── Scheduler ────────────────────────────────────────────
_raw_times = os.getenv("RUN_TIMES", "09:00,17:00")
RUN_TIMES = [t.strip() for t in _raw_times.split(",") if t.strip()]

# ─── Assignment PDF (optional) ────────────────────────────
ASSIGNMENT_PDF_PATH = os.getenv("ASSIGNMENT_PDF_PATH", "assignment.pdf")

# ─── Tag Descriptions ─────────────────────────────────────
TAG_DESCRIPTIONS = {
    "hw1":             "Homework 1 — all questions related to the first assignment",
    "student":         "Student questions (all topics)",
    "logistics":       "Administrative info — deadlines, submission guidelines",
    "instructor-note": "Official announcements from the course staff",
    "other":           "Miscellaneous — questions that don't fit other categories",
    "pin":             "Pinned posts — important, read first",
}

# ─── Validation ───────────────────────────────────────────
REQUIRED_VARS = [
    "PIAZZA_EMAIL",
    "PIAZZA_PASSWORD",
    "PIAZZA_COURSE_ID",
    "GROQ_API_KEY",
    "RESEND_API_KEY",
    "NOTIFY_EMAIL",
]

def validate():
    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your values."
        )
