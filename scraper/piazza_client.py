import logging
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
        if name.strip():
            return name.strip()
    except Exception:
        pass
    try:
        info = network.get_info()
        result = info.get("result", {})
        name = result.get("name") or result.get("num") or ""
        return name.strip()
    except Exception as e:
        logger.warning("Could not fetch course name: %s", e)
        return ""


def fetch_posts(network) -> list[dict]:
    try:
        feed = network.get_feed(limit=999, offset=0)
    except RequestError as e:
        raise RuntimeError(f"Failed to fetch Piazza feed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching feed: {e}") from e

    all_ids = [item["id"] for item in feed.get("feed", [])]
    logger.info("Fetching %d posts", len(all_ids))

    posts = []
    for post_id in all_ids:
        try:
            posts.append(network.get_post(post_id))
        except RequestError as e:
            logger.warning("Skipping post %s — request error: %s", post_id, e)
        except Exception as e:
            logger.warning("Skipping post %s — unexpected error: %s", post_id, e)

    logger.info("Successfully fetched %d posts", len(posts))
    return posts
