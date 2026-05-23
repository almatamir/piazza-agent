import logging
from groq import Groq
from config import settings

logger = logging.getLogger(__name__)

FALLBACK_MODEL = "llama-3.1-8b-instant"  # 500k TPD — used when 70b hits daily limit

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is missing from .env")
        try:
            _client = Groq(api_key=settings.GROQ_API_KEY)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Groq client: {e}") from e
    return _client


def chat(prompt: str, system: str = "") -> str:
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for model in [settings.GROQ_MODEL, FALLBACK_MODEL]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
            )
            if model != settings.GROQ_MODEL:
                logger.warning("Used fallback model %s (primary model rate limited)", model)
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and model != FALLBACK_MODEL:
                logger.warning("Rate limit on %s — retrying with fallback model", model)
                continue
            raise RuntimeError(f"Groq API call failed: {e}") from e

    raise RuntimeError("All Groq models failed")
