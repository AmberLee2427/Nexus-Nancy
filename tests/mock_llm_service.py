from __future__ import annotations

import json
import random
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4


SHAKESPEARE_QUOTES = [
    "To be, or not to be: that is the question.",
    "The lady doth protest too much, methinks.",
    "All the world's a stage, and all the men and women merely players.",
    "Brevity is the soul of wit.",
    "Some are born great, some achieve greatness, and some have greatness thrust upon them.",
    "What's in a name? That which we call a rose by any other name would smell as sweet.",
    "Cowards die many times before their deaths; the valiant never taste of death but once.",
]


def _mask_key(key: str) -> str:
    if len(key) <= 7:
        return key
    return f"{key[:8]}***{key[-4:]}"


def _auth_error_invalid_key(key: str | None) -> tuple[int, dict[str, Any]]:
    shown = _mask_key(key or "<missing>")
    return (
        401,
        {
            "error": {
                "message": (
                    "Incorrect API key provided: "
                    f"{shown}. You can find your API key at "
                    "https://mock.nexus-nancy.local/account/api-keys."
                ),
                "type": "invalid_request_error",
                "param": None,
                "code": "invalid_api_key",
            }
        },
    )


def _auth_error_no_funds() -> tuple[int, dict[str, Any]]:
    return (
        429,
        {
            "error": {
                "message": (
                    "You exceeded your current quota, please check your plan and billing details."
                ),
                "type": "insufficient_quota",
                "param": None,
                "code": "insufficient_quota",
            }
        },
    )


def _extract_bearer_key(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    key = parts[1].strip()
    return key or None


def _extract_tool_test_yaml(user_text: str) -> str | None:
    """Find fenced code block for tool test YAML.

    Accepted fences:
    - ```tool_test.yml
    - ```yaml
    - ```yml

    Prefer a tool_test.yml fence when present.
    """
    pattern = re.compile(r"```([^\n]*)\n(.*?)\n```", re.DOTALL)
    matches = pattern.findall(user_text)
    if not matches:
        return None

    normalized: list[tuple[str, str]] = [(lang.strip().lower(), body) for lang, body in matches]

    for lang, body in normalized:
        if "tool_test.yml" in lang:
            return body

    for lang, body in normalized:
        if lang in {"yaml", "yml"}:
            return body

    return None


def _parse_bash_commands(yaml_text: str) -> list[str]:
    """Parse expected minimal YAML format:

    bash:
      - command one
      - command two
    """
    lines = yaml_text.splitlines()
    in_bash = False
    commands: list[str] = []

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if re.match(r"^bash\s*:\s*$", stripped):
            in_bash = True
            continue

        if in_bash:
            # Stop if a new top-level key begins.
            if re.match(r"^[A-Za-z0-9_.-]+\s*:\s*$", stripped) and not stripped.startswith("-"):
                break

            match = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if match:
                cmd = match.group(1).strip()
                if cmd:
                    commands.append(cmd)

    return commands


def _extract_commands_from_messages(messages: list[dict[str, Any]]) -> list[str]:
    # Use the most recent user message containing a valid tool block.
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        yaml_block = _extract_tool_test_yaml(content)
        if not yaml_block:
            continue
        commands = _parse_bash_commands(yaml_block)
        if commands:
            return commands
    return []


def _chat_completion_response(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages") or []
    commands = _extract_commands_from_messages(messages)
    model = body.get("model", "mock-shakespeare")

    if commands:
        tool_calls = []
        for command in commands:
            tool_calls.append(
                {
                    "id": f"call_{uuid4().hex[:12]}",
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "arguments": json.dumps({"command": command}),
                    },
                }
            )

        message = {
            "role": "assistant",
            "content": "Executing requested tool test commands.",
            "tool_calls": tool_calls,
        }
    else:
        message = {
            "role": "assistant",
            "content": random.choice(SHAKESPEARE_QUOTES),
        }

    return {
        "id": f"chatcmpl_{uuid4().hex}",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if commands else "stop",
            }
        ],
    }


class MockLLMHandler(BaseHTTPRequestHandler):
    server_version = "NexusNancyMock/0.1"

    def _require_auth(self) -> tuple[bool, str | None]:
        key = _extract_bearer_key(self.headers.get("Authorization"))
        if not key:
            status, payload = _auth_error_invalid_key(None)
            self._send_json(status, payload)
            return False, None

        if "$" in key:
            status, payload = _auth_error_no_funds()
            self._send_json(status, payload)
            return False, key

        if "claude_is_better_than_chatgpt" in key:
            status, payload = _auth_error_invalid_key(key)
            self._send_json(status, payload)
            return False, key

        return True, key

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": {"message": "not found"}})
            return

        ok, _ = self._require_auth()
        if not ok:
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)

        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": {"message": "invalid JSON body"}})
            return

        response = _chat_completion_response(body)
        self._send_json(200, response)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            ok, _ = self._require_auth()
            if not ok:
                return
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {"id": "mock-shakespeare", "object": "model", "owned_by": "nexus-nancy"}
                    ],
                },
            )
            return
        self._send_json(404, {"error": {"message": "not found"}})

    def log_message(self, format: str, *args: Any) -> None:
        # Keep test output clean.
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    host = "127.0.0.1"
    port = 8008
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])

    server = ThreadingHTTPServer((host, port), MockLLMHandler)
    print(f"Mock LLM listening on http://{host}:{port}")
    print("Chat endpoint: /v1/chat/completions")
    print("Models endpoint: /v1/models")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
