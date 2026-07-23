"""
Thin wrapper around the Groq API.

We use:
  - gemma2-9b-it            -> fast/cheap model for structured extraction & simple classification
  - llama-3.3-70b-versatile -> stronger model for reasoning tasks (root cause, CAPA, chat)

Both are exposed through the same helper so nodes/routers don't need to know
about the Groq SDK directly.
"""
import json
import logging
from typing import Optional

from groq import Groq

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("aivoa.llm")

_client: Optional[Groq] = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Create a key at https://console.groq.com and "
                "add it to backend/.env (see .env.example)."
            )
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def chat_completion(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.2,
    json_mode: bool = False,
    max_tokens: int = 1024,
) -> str:
    """Call Groq chat completions and return the raw text content."""
    client = get_client()
    model = model or settings.GROQ_EXTRACTION_MODEL

    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return response.choices[0].message.content


def chat_completion_json(messages: list[dict], model: str = None, temperature: float = 0.1) -> dict:
    """Call the model and parse a JSON object out of the response, tolerating minor formatting slips."""
    raw = chat_completion(messages, model=model, temperature=temperature, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Some models wrap JSON in markdown fences despite json_mode; strip and retry.
        cleaned = raw.strip().strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from LLM response: %s", raw)
            return {}
