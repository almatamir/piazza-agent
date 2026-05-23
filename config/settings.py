import os
from dotenv import load_dotenv

load_dotenv()

# ─── Groq AI ──────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─── Supabase ─────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ─── Resend (email sender) ────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = "Piazza Agent <onboarding@resend.dev>"
EMAIL_SUBJECT = "Piazza Report — Course Summary"
