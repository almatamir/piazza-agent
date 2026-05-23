import logging
import os
from datetime import datetime

from scraper.piazza_client import get_network, fetch_posts
from scraper.parser import parse_posts
from ai.summarizer import summarize
from notifier.email_sender import send_report
from storage import checkpoint
from config import settings

logger = logging.getLogger(__name__)


def run(tag: str = "hw1") -> None:
    logger.info("Agent started — tag: %s", tag)

    last_nr = checkpoint.load()
    logger.info("Last seen post nr: %s", last_nr)

    network = get_network()
    raw_posts = fetch_posts(network)
    all_posts = parse_posts(raw_posts)

    new_posts = [p for p in all_posts if last_nr is None or p["nr"] > last_nr]
    tagged = [p for p in new_posts if tag in p["tags"]]

    if not tagged:
        logger.info("No new posts for tag '%s' — skipping.", tag)
        return

    logger.info("%d new posts found for tag '%s'", len(tagged), tag)

    summary = summarize(tagged, tag)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    report_path = f"reports/summary_{tag}_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.md"
    os.makedirs("reports", exist_ok=True)

    full_report = (
        f"# Piazza Report\n\n"
        + summary
        + f"\n\n---\n\nGenerated: {timestamp} | New posts: {len(tagged)}"
    )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    subject = f"{settings.EMAIL_SUBJECT} [{tag}] — {datetime.now().strftime('%Y-%m-%d')}"
    send_report(subject, full_report)

    os.remove(report_path)
    logger.info("Report sent and deleted: %s", report_path)

    max_nr = max(p["nr"] for p in all_posts)
    checkpoint.save(max_nr)
    logger.info("Agent finished.")
