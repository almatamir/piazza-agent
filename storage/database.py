import logging
from storage.supabase_client import get_client

logger = logging.getLogger(__name__)


def get_all_active_users() -> list[dict]:
    try:
        res = get_client().table("users").select("*").eq("active", True).execute()
        return res.data or []
    except Exception as e:
        raise RuntimeError(f"Failed to fetch users: {e}") from e


def update_last_post_nr(user_id: str, last_post_nr: int) -> None:
    try:
        get_client().table("users").update({"last_post_nr": last_post_nr}).eq("id", user_id).execute()
        logger.info("Updated last_post_nr=%d for user %s", last_post_nr, user_id)
    except Exception as e:
        raise RuntimeError(f"Failed to update checkpoint for user {user_id}: {e}") from e


def add_user(email: str, piazza_email: str, piazza_password: str, piazza_course_id: str) -> dict:
    try:
        res = get_client().table("users").insert({
            "email": email,
            "piazza_email": piazza_email,
            "piazza_password": piazza_password,
            "piazza_course_id": piazza_course_id,
        }).execute()
        return res.data[0]
    except Exception as e:
        raise RuntimeError(f"Failed to add user: {e}") from e


def get_goals(course_id: str) -> dict | None:
    try:
        res = get_client().table("assignment_goals").select("goals_json").eq("course_id", course_id).execute()
        if res.data:
            return res.data[0]["goals_json"]
        return None
    except Exception as e:
        logger.warning("Could not fetch goals for course %s: %s", course_id, e)
        return None


def save_goals(course_id: str, goals: dict) -> None:
    try:
        get_client().table("assignment_goals").upsert({
            "course_id": course_id,
            "goals_json": goals,
        }).execute()
        logger.info("Saved goals for course %s", course_id)
    except Exception as e:
        raise RuntimeError(f"Failed to save goals: {e}") from e
