import logging
import time
from piazza_api import Piazza
from piazza_api.exceptions import AuthenticationError, RequestError

logger = logging.getLogger(__name__)


def get_network(piazza_email: str, piazza_password: str, course_id: str):
    try:
        p = Piazza()
        p.user_login(email=piazza_email, password=piazza_password)
        logger.info("Logged in to Piazza as %s", piazza_email)
    except AuthenticationError as e:
        raise RuntimeError(f"Piazza login failed for {piazza_email}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error during Piazza login: {e}") from e

    try:
        network = p.network(course_id)
        logger.info("Connected to course: %s", course_id)
        return network
    except Exception as e:
        raise RuntimeError(
            f"Could not access course '{course_id}' — check the course ID and enrollment: {e}"
        ) from e


def get_course_name(network) -> str:
    try:
        info = network._rpc.request("network.get", {"id": network._nid})
        result = info.get("result", {})
        name = result.get("name") or result.get("num") or ""
        return name.strip()
    except Exception as e:
        logger.warning("Could not fetch course name: %s", e)
        return ""


def fetch_posts(network, since_nr: int = 0) -> list[dict]:
    try:
        feed = network.get_feed(limit=999, offset=0)
    except RequestError as e:
        raise RuntimeError(f"Failed to fetch Piazza feed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching feed: {e}") from e

    feed_items = feed.get("feed", [])
    new_items = [item for item in feed_items if item.get("nr", 0) > since_nr]
    logger.info("Feed: %d total posts, %d new since nr %d", len(feed_items), len(new_items), since_nr)

    if not new_items:
        return []

    all_ids = [item["id"] for item in new_items]
    logger.info("Fetching %d new posts", len(all_ids))

    posts = []
    for post_id in all_ids:
        for attempt in range(4):
            try:
                posts.append(network.get_post(post_id))
                break
            except RequestError as e:
                if "too fast" in str(e).lower() and attempt < 3:
                    wait = 5 * (attempt + 1)
                    logger.info("Rate limited — waiting %ds before retry (post %s)", wait, post_id)
                    time.sleep(wait)
                else:
                    logger.warning("Skipping post %s — request error: %s", post_id, e)
                    break
            except Exception as e:
                logger.warning("Skipping post %s — unexpected error: %s", post_id, e)
                break
        time.sleep(1.5)

    logger.info("Successfully fetched %d posts", len(posts))
    return posts
