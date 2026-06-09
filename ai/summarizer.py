import logging
import time
from ai.groq_client import chat
from ai.prompts import SYSTEM_SUMMARIZER, build_summary_prompt, build_merge_prompt

logger = logging.getLogger(__name__)

BATCH_SIZE = 25
POST_CALL_DELAY = 20  # seconds after every successful Groq call to let TPM window refresh
RETRY_DELAY = 60      # seconds to wait on 429/413 before retrying
MAX_RETRIES = 3


def _chat_with_retry(prompt: str, system: str, max_tokens: int) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = chat(prompt, system=system, max_tokens=max_tokens)
            time.sleep(POST_CALL_DELAY)
            return result
        except Exception as e:
            error_str = str(e)
            is_retriable = "429" in error_str or "413" in error_str
            if is_retriable and attempt < MAX_RETRIES:
                logger.warning(
                    "Groq rate/size error (attempt %d/%d) — waiting %ds before retry: %s",
                    attempt, MAX_RETRIES, RETRY_DELAY, error_str[:200],
                )
                time.sleep(RETRY_DELAY)
            else:
                raise
    raise RuntimeError("All Groq retry attempts failed")


def _summarize_batch(posts: list[dict], tag: str, batch_num: int, assignment_context: str = "", course_id: str = "") -> str:
    logger.info("Summarizing batch %d (%d posts)", batch_num, len(posts))
    prompt = build_summary_prompt(posts, tag, assignment_context, course_id)
    return _chat_with_retry(prompt, system=SYSTEM_SUMMARIZER, max_tokens=1200)


def _progressive_merge(summaries: list[str], tag: str) -> str:
    result = summaries[0]
    for i, next_summary in enumerate(summaries[1:], start=2):
        logger.info("Progressive merge: folding in batch %d", i)
        result = _chat_with_retry(
            build_merge_prompt([result, next_summary], tag),
            system=SYSTEM_SUMMARIZER,
            max_tokens=2000,
        )
    return result


def summarize(posts: list[dict], tag: str, assignment_context: str = "", course_id: str = "") -> str:
    if not posts:
        return f"No posts found for tag '{tag}'."

    logger.info("Summarizing %d posts for tag '%s'", len(posts), tag)

    if len(posts) <= BATCH_SIZE:
        try:
            result = _chat_with_retry(
                build_summary_prompt(posts, tag, assignment_context, course_id),
                system=SYSTEM_SUMMARIZER,
                max_tokens=2500,
            )
            logger.info("Summary generated successfully")
            return result
        except Exception as e:
            logger.error("Summarization failed: %s", e)
            raise

    batches = [posts[i:i + BATCH_SIZE] for i in range(0, len(posts), BATCH_SIZE)]
    logger.info("Split into %d batches of up to %d posts", len(batches), BATCH_SIZE)

    batch_summaries = []
    for i, batch in enumerate(batches, 1):
        try:
            summary = _summarize_batch(batch, tag, i, assignment_context, course_id)
            batch_summaries.append(summary)
        except Exception as e:
            logger.error("Batch %d failed: %s", i, e)
            raise

    logger.info("Progressive merge of %d batch summaries", len(batch_summaries))
    try:
        merged = _progressive_merge(batch_summaries, tag)
        logger.info("Merge completed successfully")
        return merged
    except Exception as e:
        logger.error("Merge failed: %s", e)
        raise
