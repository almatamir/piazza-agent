import logging
from piazza_api import Piazza
from piazza_api.exceptions import AuthenticationError, RequestError
from config import settings

logger = logging.getLogger(__name__)


def get_network():
    """Login to Piazza and return the course network object."""
    if not settings.PIAZZA_EMAIL or not settings.PIAZZA_PASSWORD:
        raise ValueError("PIAZZA_EMAIL and PIAZZA_PASSWORD must be set in .env")
    if not settings.PIAZZA_COURSE_ID:
        raise ValueError("PIAZZA_COURSE_ID must be set in .env")

    try:
        p = Piazza()
        p.user_login(email=settings.PIAZZA_EMAIL, password=settings.PIAZZA_PASSWORD)
        logger.info("Logged in to Piazza as %s", settings.PIAZZA_EMAIL)
    except AuthenticationError as e:
        raise RuntimeError(f"Piazza login failed — check your email/password in .env: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error during Piazza login: {e}") from e

    try:
        network = p.network(settings.PIAZZA_COURSE_ID)
        logger.info("Connected to course: %s", settings.PIAZZA_COURSE_ID)
        return network
    except Exception as e:
        raise RuntimeError(
            f"Could not access course '{settings.PIAZZA_COURSE_ID}' — "
            f"make sure the Course ID is correct and you are enrolled: {e}"
        ) from e


def fetch_posts(network, since_id: str | None = None) -> list[dict]:
    """
    Returns all posts newer than since_id.
    If since_id is None, fetches all posts in the course.
    """
    try:
        feed = network.get_feed(limit=999, offset=0)
    except RequestError as e:
        raise RuntimeError(f"Failed to fetch Piazza feed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching feed: {e}") from e

    all_ids = [item["id"] for item in feed.get("feed", [])]

    if since_id and since_id in all_ids:
        cutoff = all_ids.index(since_id)
        all_ids = all_ids[:cutoff]
        logger.info("Fetching %d new posts since checkpoint %s", len(all_ids), since_id)
    else:
        logger.info("No checkpoint — fetching all %d posts", len(all_ids))

    posts = []
    for post_id in all_ids:
        try:
            post = network.get_post(post_id)
            posts.append(post)
        except RequestError as e:
            logger.warning("Skipping post %s — request error: %s", post_id, e)
        except Exception as e:
            logger.warning("Skipping post %s — unexpected error: %s", post_id, e)

    logger.info("Successfully fetched %d posts", len(posts))
    return posts
