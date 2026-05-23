import logging
import re
import resend
from config import settings

logger = logging.getLogger(__name__)


def _markdown_to_html(md: str) -> str:
    lines = md.splitlines()
    html_lines = []
    for line in lines:
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', line)
        if line.startswith("## "):
            line = f"<h2>{line[3:]}</h2>"
        elif line.startswith("### "):
            line = f"<h3>{line[4:]}</h3>"
        elif line.startswith("* ") or line.startswith("- "):
            line = f"<li>{line[2:]}</li>"
        elif line.strip() == "":
            line = "<br>"
        else:
            line = f"<p>{line}</p>"
        html_lines.append(line)
    return "\n".join(html_lines)


def send_report(to: str, subject: str, body_md: str) -> None:
    if not settings.RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY must be set in .env")

    resend.api_key = settings.RESEND_API_KEY

    header_html = (
        '<h1 style="font-family:sans-serif;font-size:28px;font-weight:700;'
        'margin:0 0 20px 0;color:#111;">Piazza Report</h1>'
    )

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to,
            "subject": subject,
            "html": header_html + "\n" + _markdown_to_html(body_md),
            "text": "Piazza Report\n\n" + body_md,
        })
        logger.info("Report emailed to %s", to)
    except Exception as e:
        raise RuntimeError(f"Failed to send email via Resend: {e}") from e
