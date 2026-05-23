import json
import logging
import os

logger = logging.getLogger(__name__)

CHECKPOINT_FILE = "storage/checkpoint.json"


def load() -> int | None:
    """Return the last seen post nr, or None if no checkpoint exists."""
    if not os.path.exists(CHECKPOINT_FILE):
        return None
    try:
        with open(CHECKPOINT_FILE) as f:
            return json.load(f).get("last_nr")
    except Exception as e:
        logger.warning("Could not read checkpoint: %s", e)
        return None


def save(last_nr: int) -> None:
    """Persist the highest post nr we have processed."""
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    try:
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump({"last_nr": last_nr}, f)
        logger.info("Checkpoint saved: last_nr=%d", last_nr)
    except Exception as e:
        logger.error("Could not save checkpoint: %s", e)
        raise
