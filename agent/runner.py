import logging
import time
from collections import defaultdict
from datetime import datetime

from scraper.piazza_client import piazza_login, get_network, fetch_posts, get_course_name
from scraper.parser import parse_posts
from ai.summarizer import summarize
from notifier.email_sender import send_report
from storage.database import get_all_active_users, update_last_post_nr, get_goals

logger = logging.getLogger(__name__)


def run_for_user(user: dict, piazza_session) -> None:
    user_id = user["id"]
    email = user["email"]
    last_post_nr = user.get("last_post_nr") or 0
    course_id = user["piazza_course_id"]

    logger.info("Running for user %s (course: %s, last_nr: %s)", email, course_id, last_post_nr)

    try:
        network = get_network(piazza_session, course_id)
        course_name = get_course_name(network)
        raw_posts = fetch_posts(network, since_nr=last_post_nr)
        new_posts = parse_posts(raw_posts)
    except Exception as e:
        logger.error("Failed to fetch posts for user %s: %s", email, e)
        return

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
        summary = summarize(new_posts, tag="all", assignment_context=assignment_context, course_id=course_id)
    except Exception as e:
        logger.error("Summarization failed for user %s: %s", email, e)
        return

    timestamp = datetime.now().strftime("%Y-%m-%d")
    course_label = course_name or course_id
    subject = f"Piazza Report | {course_label} — {timestamp}"
    full_report = (
        summary
        + f"\n\n---\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | New posts: {len(new_posts)}"
    )

    try:
        send_report(to=email, subject=subject, body_md=full_report)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", email, e)
        return

    max_nr = max(p["nr"] for p in new_posts)
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

    # Group by piazza_email so we login once per account
    by_account = defaultdict(list)
    for user in users:
        by_account[user["piazza_email"]].append(user)

    logger.info("Processing %d users across %d Piazza account(s)", len(users), len(by_account))

    for piazza_email, account_users in by_account.items():
        try:
            piazza_session = piazza_login(piazza_email, account_users[0]["piazza_password"])
        except Exception as e:
            logger.error("Failed to login to Piazza as %s: %s", piazza_email, e)
            continue

        for user in account_users:
            try:
                run_for_user(user, piazza_session)
            except Exception as e:
                logger.error("Unexpected error for user %s: %s", user.get("email"), e)
            time.sleep(10)

    logger.info("Runner finished")
