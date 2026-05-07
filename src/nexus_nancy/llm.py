from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import Config, resolve_api_key
from .provider import LLMProvider
from .token_count import estimate_context_tokens


class NativeOpenAIProvider(LLMProvider):
    def __init__(self, cfg: Config, workspace_root: Path):
        self.cfg = cfg
        self.workspace_root = workspace_root
        
        self.api_key, self.api_key_source = resolve_api_key(cfg, workspace_root)
        self.base_url = cfg.base_url.rstrip("/")
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
                "Invalid base_url in config. Expected absolute URL like https://api.openai.com/v1"
            )

        if len(self.api_key.strip()) < 12 and self.api_key.lower() not in {
            "local",
            "none",
            "false",
        }:
            raise RuntimeError("API key looks too short. Refusing request.")

    def _validate_tools(self, tools: list[dict[str, Any]], *, require_bash: bool = True) -> None:
        if not tools:
            return

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
        if require_bash and "bash" not in names:
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
                f"estimated {est_tokens} tokens > max_preflight_tokens "
                f"{self.cfg.max_preflight_tokens}"
            )

    def _validate_request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        require_bash_tool: bool = True,
    ) -> None:
        self._validate_client_config()
        self._validate_tools(tools, require_bash=require_bash_tool)
        self._validate_messages(messages)

    def _api_key_preview(self) -> str:
        if not self.api_key:
            return "<missing>"
        if len(self.api_key) <= 7:
            return self.api_key
        return f"{self.api_key[:8]}***{self.api_key[-4:]}"

    def _format_error_dict(self, data: dict[str, Any]) -> str:
        # Keep error payloads as plain JSON text. Scientists can read structured
        # errors; this code should not "help" by flattening, truncating, or
        # rewriting them into friendly summaries.
        return json.dumps(data, indent=4, ensure_ascii=False, default=str)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        response_format: dict[str, Any] | None = None,
        extra_body: dict[str, Any] | None = None,
        require_bash_tool: bool = True,
    ) -> dict[str, Any]:
        tool_specs = tools or []
        self._validate_request(messages, tool_specs, require_bash_tool=require_bash_tool)
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": 0,
        }
        if tool_specs:
            payload["tools"] = tool_specs
            payload["tool_choice"] = "auto" if tool_choice is None else tool_choice
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = parallel_tool_calls
        if response_format is not None:
            payload["response_format"] = response_format
        if extra_body:
            payload.update(extra_body)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        request_url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=self.cfg.timeout_seconds) as client:
            try:
                resp = client.post(
                    request_url,
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                # Show the provider's body verbatim. The full structured error is
                # the product here; replacing it with a cute summary would make
                # debugging materially worse.
                detail = exc.response.text.strip()
                if not detail:
                    detail = self._format_error_dict(
                        {
                            "status_code": exc.response.status_code,
                            "reason_phrase": exc.response.reason_phrase,
                            "request_url": request_url,
                        }
                    )
                raise RuntimeError(
                    f"LLM request failed with HTTP {exc.response.status_code}: {detail}"
                ) from exc
            except httpx.HTTPError as exc:
                # Transport failures rarely come with a server body, so we emit
                # our own raw dict with the exact connection context. Again: no
                # simplification, no coddling, no one-line euphemisms.
                detail = self._format_error_dict(
                    {
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                        "request_url": request_url,
                        "base_url": self.cfg.base_url,
                        "api_key_source": self.api_key_source,
                        "api_key_preview": self._api_key_preview(),
                    }
                )
                raise RuntimeError(f"LLM request failed: {detail}") from exc

    def probe_capabilities(self) -> dict[str, bool]:
        probe_tool = {
            "type": "function",
            "function": {
                "name": "capability_probe",
                "description": "Return whether native tool calling is available.",
                "parameters": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
            },
        }
        messages = [
            {
                "role": "system",
                "content": "You are a capability probe. Use the provided tool if available.",
            },
            {"role": "user", "content": "Call capability_probe with ok=true and think about it."},
        ]
        try:
            result = self.chat(
                messages,
                [probe_tool],
                tool_choice={"type": "function", "function": {"name": "capability_probe"}},
                require_bash_tool=False,
            )
            message = result["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []

            has_tools = any(
                call.get("function", {}).get("name") == "capability_probe" for call in tool_calls
            )
            # Detect if the server used the dedicated reasoning_content field.
            has_reasoning = bool(message.get("reasoning_content"))

            return {"native_tools": has_tools, "reasoning_channel": has_reasoning}
        except Exception:
            return {"native_tools": False, "reasoning_channel": False}
