import logging
import re
from datetime import datetime
from html import unescape

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def parse_post(raw: dict) -> dict | None:
    """Converts a raw Piazza post into a clean structured dict. Returns None on failure."""
    try:
        history = raw.get("history", [{}])
        if not history:
            return None

        subject = _strip_html(history[0].get("subject", ""))
        body = _strip_html(history[0].get("content", ""))

        children = raw.get("children", [])
        instructor_answer = ""
        student_followups = []

        for child in children:
            try:
                child_type = child.get("type", "")
                if child_type == "i_answer":
                    child_history = child.get("history", [{}])
                    if child_history:
                        instructor_answer = _strip_html(child_history[0].get("content", ""))
                elif child_type == "followup":
                    text = _strip_html(child.get("subject", ""))
                    if text:
                        student_followups.append(text)
            except Exception as e:
                logger.debug("Skipping child element in post %s: %s", raw.get("id"), e)

        try:
            created_raw = raw.get("created", "")
            created = datetime.strptime(created_raw, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M")
        except Exception:
            created = raw.get("created", "unknown date")

        return {
            "id": raw.get("id", ""),
            "nr": raw.get("nr", ""),
            "subject": subject,
            "body": body,
            "instructor_answer": instructor_answer,
            "student_followups": student_followups,
            "created": created,
            "tags": raw.get("tags", []),
        }

    except Exception as e:
        logger.warning("Failed to parse post (id=%s): %s", raw.get("id", "?"), e)
        return None


def parse_posts(raw_posts: list[dict]) -> list[dict]:
    """Parse a list of raw posts, silently dropping any that fail."""
    if not raw_posts:
        return []

    parsed = [parse_post(p) for p in raw_posts]
    valid = [p for p in parsed if p is not None]

    dropped = len(raw_posts) - len(valid)
    if dropped:
        logger.warning("Dropped %d posts due to parse errors", dropped)

    return valid
