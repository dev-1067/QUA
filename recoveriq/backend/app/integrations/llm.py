"""Optional LLM analyser for borrower notes (translation + sentiment). Used only when
ANTHROPIC_API_KEY is set; any failure falls back to the offline lexicon analyser."""
from __future__ import annotations

import json
import logging

from ..config import settings

log = logging.getLogger("recoveriq.llm")

SCHEMA = {
    "type": "object",
    "properties": {
        "english_text": {"type": "string"},
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "score": {"type": "number"},
        "reason_category": {"type": "string", "enum": [
            "job_loss", "medical", "business_loss", "family_event", "dispute",
            "willful_default", "will_pay", "unreachable", "other"]},
    },
    "required": ["english_text", "sentiment", "score", "reason_category"],
    "additionalProperties": False,
}

SYSTEM = ("You analyse short notes written by loan-collection field agents in India. Notes may be in "
          "English, Hindi, Marathi or romanised Hinglish. Translate the note faithfully to English, rate the "
          "borrower's repayment mood (score from -1 very negative to 1 very positive) and pick the single best "
          "reason category. Do not add facts that are not in the note.")

_client = None


def available() -> bool:
    return bool(settings.anthropic_api_key)


def analyse(text: str, language: str) -> dict | None:
    global _client
    if not available():
        return None
    try:
        import anthropic

        if _client is None:
            _client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=20.0, max_retries=1)
        resp = _client.messages.create(
            model=settings.llm_model,
            max_tokens=1024,
            system=SYSTEM,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": f"Language hint: {language}\nNote:\n{text}"}],
        )
        if resp.stop_reason == "refusal":
            return None
        body = next((b.text for b in resp.content if b.type == "text"), None)
        if not body:
            return None
        data = json.loads(body)
        data["score"] = max(-1.0, min(1.0, float(data["score"])))
        data["analyzer"] = f"llm:{settings.llm_model}"
        return data
    except Exception as exc:  # network, auth, quota: the lexicon analyser takes over
        log.warning("LLM analysis unavailable, using lexicon: %s", exc)
        return None
