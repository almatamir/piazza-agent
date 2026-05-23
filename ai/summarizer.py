import logging
from ai.groq_client import chat
from ai.prompts import SYSTEM_SUMMARIZER, build_summary_prompt, build_merge_prompt

logger = logging.getLogger(__name__)

BATCH_SIZE = 13


def _summarize_batch(posts: list[dict], tag: str, batch_num: int, assignment_context: str = "") -> str:
    logger.info("Summarizing batch %d (%d posts)", batch_num, len(posts))
    prompt = build_summary_prompt(posts, tag, assignment_context)
    return chat(prompt, system=SYSTEM_SUMMARIZER)


def summarize(posts: list[dict], tag: str, assignment_context: str = "") -> str:
    if not posts:
        return f"No posts found for tag '{tag}'."

    logger.info("Summarizing %d posts for tag '%s'", len(posts), tag)

    if len(posts) <= BATCH_SIZE:
        try:
            result = chat(build_summary_prompt(posts, tag, assignment_context), system=SYSTEM_SUMMARIZER)
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
            summary = _summarize_batch(batch, tag, i, assignment_context)
            batch_summaries.append(summary)
        except Exception as e:
            logger.error("Batch %d failed: %s", i, e)
            raise

    logger.info("Merging %d batch summaries", len(batch_summaries))
    try:
        merged = chat(build_merge_prompt(batch_summaries, tag), system=SYSTEM_SUMMARIZER)
        logger.info("Merge completed successfully")
        return merged
    except Exception as e:
        logger.error("Merge failed: %s", e)
        raise
