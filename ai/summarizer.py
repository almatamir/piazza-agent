import logging
from ai.groq_client import chat
from ai.prompts import SYSTEM_SUMMARIZER, build_summary_prompt, build_merge_prompt

logger = logging.getLogger(__name__)

BATCH_SIZE = 13


def _summarize_batch(posts: list[dict], tag: str, batch_num: int, assignment_context: str = "", course_id: str = "") -> str:
    logger.info("Summarizing batch %d (%d posts)", batch_num, len(posts))
    prompt = build_summary_prompt(posts, tag, assignment_context, course_id)
    return chat(prompt, system=SYSTEM_SUMMARIZER)


def summarize(posts: list[dict], tag: str, assignment_context: str = "", course_id: str = "") -> str:
    if not posts:
        return f"No posts found for tag '{tag}'."

    logger.info("Summarizing %d posts for tag '%s'", len(posts), tag)

    if len(posts) <= BATCH_SIZE:
        try:
            result = chat(build_summary_prompt(posts, tag, assignment_context, course_id), system=SYSTEM_SUMMARIZER)
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

    logger.info("Merging %d batch summaries (pairwise)", len(batch_summaries))
    try:
        merged = _pairwise_merge(batch_summaries, tag)
        logger.info("Merge completed successfully")
        return merged
    except Exception as e:
        logger.error("Merge failed: %s", e)
        raise


def _pairwise_merge(summaries: list[str], tag: str) -> str:
    round_num = 1
    while len(summaries) > 1:
        next_round = []
        for i in range(0, len(summaries), 2):
            if i + 1 < len(summaries):
                logger.info("Merge round %d: combining summaries %d and %d", round_num, i + 1, i + 2)
                merged = chat(build_merge_prompt([summaries[i], summaries[i + 1]], tag), system=SYSTEM_SUMMARIZER)
                next_round.append(merged)
            else:
                next_round.append(summaries[i])
        summaries = next_round
        round_num += 1
    return summaries[0]
