from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from .config import Config, resolve_api_key
from .token_count import estimate_context_tokens


class LLMClient:
    def __init__(self, cfg: Config, workspace_root):
        self.cfg = cfg
        self.api_key, self.api_key_source = resolve_api_key(cfg, workspace_root)
        self._validate_client_config()

    def _validate_client_config(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "Missing API key. Set environment variable "
                f"{self.cfg.api_key_env} or write key to {self.cfg.api_key_file}."
            )

        parsed = urlparse(self.cfg.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError(
                "Invalid base_url in config. Expected absolute URL like "
                "https://api.openai.com/v1"
            )

        if len(self.api_key.strip()) < 12:
            raise RuntimeError("API key looks too short. Refusing request.")

    def _validate_tools(self, tools: list[dict[str, Any]]) -> None:
        if not tools:
            raise RuntimeError("No tools provided in payload. Refusing request.")

        names: list[str] = []
        for item in tools:
            if item.get("type") != "function":
                raise RuntimeError("Invalid tool spec type. Refusing request.")
            fn = item.get("function") or {}
            name = fn.get("name")
            if not isinstance(name, str) or not name:
                raise RuntimeError("Tool spec missing function name. Refusing request.")
            names.append(name)

        if len(set(names)) != len(names):
            raise RuntimeError("Duplicate tool names detected. Refusing request.")
        if "bash" not in names:
            raise RuntimeError("Primary 'bash' tool missing from payload. Refusing request.")

    def _validate_messages(self, messages: list[dict[str, Any]]) -> None:
        if not messages:
            raise RuntimeError("No messages in payload. Refusing request.")

        valid_roles = {"system", "user", "assistant", "tool"}
        has_system = False
        has_user = False
        for idx, msg in enumerate(messages):
            role = msg.get("role")
            if role not in valid_roles:
                raise RuntimeError(f"Invalid message role at index {idx}: {role!r}")
            if role == "system":
                has_system = True
            if role == "user":
                has_user = True

            content = msg.get("content")
            tool_calls = msg.get("tool_calls")
            if content is None and not tool_calls:
                raise RuntimeError(f"Message at index {idx} has no content/tool_calls")
            if isinstance(content, str) and not content.strip() and role in {"system", "user"}:
                raise RuntimeError(f"Empty {role} message at index {idx}")

        if not has_system:
            raise RuntimeError("System prompt missing from payload. Refusing request.")
        if not has_user:
            raise RuntimeError("No user message in payload. Refusing request.")

        est_tokens = estimate_context_tokens(messages, self.cfg.model)
        if est_tokens > self.cfg.max_preflight_tokens:
            raise RuntimeError(
                "Request too large before send: "
                f"estimated {est_tokens} tokens > max_preflight_tokens {self.cfg.max_preflight_tokens}"
            )

    def _validate_request(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> None:
        self._validate_client_config()
        self._validate_tools(tools)
        self._validate_messages(messages)

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        self._validate_request(messages, tools)
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.cfg.timeout_seconds) as client:
            try:
                resp = client.post(
                    f"{self.cfg.base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text.strip()
                raise RuntimeError(
                    f"LLM request failed with HTTP {exc.response.status_code}: {detail[:300]}"
                ) from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(f"LLM request failed: {exc}") from exc
