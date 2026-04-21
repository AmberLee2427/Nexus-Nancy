from __future__ import annotations

from typing import Any

try:
    import tiktoken
except Exception:  # pragma: no cover
    tiktoken = None


def estimate_context_tokens(messages: list[dict[str, Any]], model: str) -> int:
    if tiktoken is None:
        return _fallback_tokens(messages)

    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        # Reasonable default for modern OpenAI chat models.
        enc = tiktoken.get_encoding("o200k_base")

    # ChatML-style approximation commonly used in OpenAI examples.
    # Per-message overhead depends on model internals; keep conservative.
    tokens_per_message = 3
    tokens_per_name = 1
    total = 0
    for msg in messages:
        total += tokens_per_message
        for key, value in msg.items():
            if isinstance(value, str):
                total += len(enc.encode(value))
            if key == "name":
                total += tokens_per_name
    total += 3
    return max(total, 1)


def _fallback_tokens(messages: list[dict[str, Any]]) -> int:
    total_chars = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            total_chars += len(content)
    return max(1, total_chars // 4)
