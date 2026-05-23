SYSTEM_SUMMARIZER = """
You are an AI assistant that summarizes Piazza forum posts for university students.
You receive a list of questions and instructor answers from a course forum.
Always respond in English.

Core goal: the student reading your report should get a complete answer to every question
without ever needing to open the original post. Write as if the original posts will be deleted
after you summarize them.

Formatting rules:
- Use bullet points. Each bullet = one question or topic.
- Structure every bullet as: [Topic/Question] — [Full answer including conditions, exceptions, and reasoning].
- Include the instructor's exact ruling AND the reason they gave, if any.
- If a question had nuance or follow-ups, capture all of it in the bullet.
- Never write a vague bullet like "check your code" — always say exactly what to check and why.
- Always end each bullet with its post link: ([#nr](url))
"""


def _post_url(nr: int | str, course_id: str) -> str:
    return f"https://piazza.com/class/{course_id}?cid={nr}"


def build_merge_prompt(summaries: list[str], tag: str) -> str:
    parts = "\n\n---\n\n".join(
        f"Batch {i+1}:\n{s}" for i, s in enumerate(summaries)
    )
    return f"""
Below are {len(summaries)} partial summaries of Piazza posts tagged "{tag}".
Each was written independently from a subset of the posts.

{parts}

---

Merge these into a single, unified report using the same structure:
- Identify common topics across batches and combine them under one section header.
- Remove any duplicate points — keep the most complete version.
- Preserve all post links ([#nr](url)) exactly as they appear.
- Keep the ❓ Open Questions and ✅ Pre-Submission Checklist sections at the end.

The final report should read as if it was written from all posts at once.
"""


def build_summary_prompt(posts: list[dict], tag: str, assignment_context: str = "", course_id: str = "") -> str:
    context_block = ""
    if assignment_context:
        context_block = f"""
--- Assignment Context ---
{assignment_context}
--------------------------

"""

    posts_block = ""
    for p in posts:
        answer_text = p["instructor_answer"] if p["instructor_answer"] else "No instructor answer yet"
        url = _post_url(p["nr"], course_id)
        posts_block += (
            f"[#{p['nr']}]({url}) — {p['subject']}\n"
            f"Q: {p['body'][:600]}\n"
            f"A: {answer_text[:800]}\n\n"
        )

    return f"""
{context_block}Below are {len(posts)} Piazza posts tagged "{tag}".

{posts_block}
---

Write a structured report. The student will read ONLY this report — treat it as the single source of truth.

Every bullet must be fully self-contained:
- State what was asked, then give the complete answer.
- Include conditions, exceptions, and the instructor's reasoning.
- A student who reads the bullet should be able to act on it immediately.
Every bullet must end with: ([#nr](url))

--- HOW TO STRUCTURE THE REPORT ---

Step 1: Read all posts and find natural clusters — groups of posts that deal with the same topic, component, or concept. Do not use predefined categories. Derive the clusters entirely from what the students actually asked about.

Step 2: Name each cluster based on what the posts in it are actually about. The name should be specific enough that a student immediately knows whether it's relevant to them.

Step 3: Write one section per cluster using this header:
### 📌 [Cluster Name]

Step 4: Under each cluster, write a bullet for every post in that cluster. Every bullet must be complete and self-contained.

Step 5: End the report with these two fixed sections:

## ❓ Open Questions
Posts with no instructor answer. Write the full question so the student knows exactly what is unresolved.
If none, write: No open questions.

## ✅ Pre-Submission Checklist
Up to 8 specific, actionable checks derived from the most important points in the report.
Each check should tell the student exactly what to look at — not generic advice.
"""
