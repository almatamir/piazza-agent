import json
import logging
import os

import fitz
from ai.groq_client import chat

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """
You are reading an assignment PDF for a university course.
Extract the following in JSON format:

{
  "title": "assignment name",
  "topics": ["topic1", "topic2", ...],
  "parts": [
    {"name": "Part 1", "description": "what this part is about"},
    ...
  ],
  "submission_requirements": ["requirement1", "requirement2", ...],
  "key_constraints": ["constraint1", "constraint2", ...]
}

topics: main concepts or techniques the assignment covers
parts: each distinct section/part of the assignment
submission_requirements: files to submit, naming rules, format
key_constraints: rules students must follow (e.g. "use raw OpenAI SDK only")

Return only valid JSON. No markdown fences, no extra text.
"""


def extract_text_from_pdf(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    try:
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"Failed to read PDF: {e}") from e


def extract_goals(pdf_path: str) -> dict:
    logger.info("Extracting goals from: %s", pdf_path)
    text = extract_text_from_pdf(pdf_path)

    prompt = f"Assignment PDF content:\n\n{text[:6000]}\n\n{EXTRACT_PROMPT}"
    try:
        raw = chat(prompt)
        goals = json.loads(raw)
        logger.info("Goals extracted: %d topics, %d parts", len(goals.get("topics", [])), len(goals.get("parts", [])))
        return goals
    except json.JSONDecodeError as e:
        raise RuntimeError(f"AI returned invalid JSON: {e}\nRaw output: {raw}") from e
    except Exception as e:
        raise RuntimeError(f"Goal extraction failed: {e}") from e
