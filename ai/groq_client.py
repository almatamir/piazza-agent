import logging
from groq import Groq
from config import settings

logger = logging.getLogger(__name__)

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

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Groq API call failed: {e}") from e
