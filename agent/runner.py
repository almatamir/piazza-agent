import logging
import os
from datetime import datetime

from scraper.piazza_client import get_network, fetch_posts
from scraper.parser import parse_posts
from ai.summarizer import summarize
from notifier.email_sender import send_report
from storage.database import get_all_active_users, update_last_post_nr, get_goals
from config import settings

logger = logging.getLogger(__name__)


def run_for_user(user: dict) -> None:
    user_id = user["id"]
    email = user["email"]
    last_post_nr = user.get("last_post_nr", 0)
    course_id = user["piazza_course_id"]

    logger.info("Running for user %s (course: %s, last_nr: %d)", email, course_id, last_post_nr)

    import os as _os
    _os.environ["PIAZZA_EMAIL"] = user["piazza_email"]
    _os.environ["PIAZZA_PASSWORD"] = user["piazza_password"]
    _os.environ["PIAZZA_COURSE_ID"] = course_id

    from importlib import reload
    from config import settings as s
    reload(s)

    try:
        network = get_network()
        raw_posts = fetch_posts(network)
        all_posts = parse_posts(raw_posts)
    except Exception as e:
        logger.error("Failed to fetch posts for user %s: %s", email, e)
        return

    new_posts = [p for p in all_posts if p["nr"] > last_post_nr]

    if not new_posts:
        logger.info("No new posts for user %s — skipping", email)
        return

    logger.info("%d new posts for user %s", len(new_posts), email)

    goals = get_goals(course_id)
    assignment_context = ""
    if goals:
        topics = goals.get("topics", [])
        assignment_context = "Assignment topics:\n" + "\n".join(f"- {t}" for t in topics)

    try:
        summary = summarize(new_posts, tag="all", assignment_context=assignment_context)
    except Exception as e:
        logger.error("Summarization failed for user %s: %s", email, e)
        return

    timestamp = datetime.now().strftime("%Y-%m-%d")
    subject = f"{settings.EMAIL_SUBJECT} — {timestamp}"
    full_report = (
        f"# Piazza Report\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | New posts: {len(new_posts)}\n\n---\n\n"
        + summary
    )

    original_notify = settings.NOTIFY_EMAIL
    settings.NOTIFY_EMAIL = email
    try:
        send_report(subject, full_report)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", email, e)
        settings.NOTIFY_EMAIL = original_notify
        return
    settings.NOTIFY_EMAIL = original_notify

    max_nr = max(p["nr"] for p in all_posts)
    try:
        update_last_post_nr(user_id, max_nr)
    except Exception as e:
        logger.error("Failed to update checkpoint for user %s: %s", email, e)

    logger.info("Done for user %s", email)


def run_all() -> None:
    logger.info("Runner started — fetching all active users")
    try:
        users = get_all_active_users()
    except Exception as e:
        logger.error("Could not fetch users from Supabase: %s", e)
        return

    if not users:
        logger.info("No active users found")
        return

    logger.info("Processing %d users", len(users))
    for user in users:
        try:
            run_for_user(user)
        except Exception as e:
            logger.error("Unexpected error for user %s: %s", user.get("email"), e)

    logger.info("Runner finished")
