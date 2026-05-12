import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from nexus_nancy.provider import LLMProvider
from nexus_nancy.tools import ToolDefinition
from nexus_nancy.config import Config
from .auth import CodexAuth, CLIENT_ID

class CodexProvider(LLMProvider):
    def __init__(self, cfg, workspace_root: Path):
        self.cfg = cfg
        self.workspace_root = workspace_root
        self.secret_path = workspace_root / ".agents/secrets/codex.json"
        self._load_secrets()

    def _load_secrets(self):
        if not self.secret_path.exists():
            self.access_token = None
            self.org_id = None
            self.account_id = None
            return

        data = json.loads(self.secret_path.read_text())
        self.access_token = data.get("access_token")
        self.org_id = data.get("organization_id")
        self.account_id = data.get("chatgpt_account_id")

    def _get_headers(self) -> Dict[str, str]:
        if not self.access_token:
            raise RuntimeError("Codex secrets missing. Run /codex-login first.")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "chatgpt-account-id": self.account_id,
            "openai-organization": self.org_id,
            "openai-beta": "responses=experimental",
            "user-agent": "Codex/0.129.0 (darwin; arm64)",
            "x-openai-client-id": CLIENT_ID,
        }

    def fetch_models(self) -> List[Dict[str, Any]]:
        headers = self._get_headers()
        with httpx.Client(timeout=self.cfg.timeout_seconds) as client:
            resp = client.get("https://chatgpt.com/backend-api/models", headers=headers)
            resp.raise_for_status()
            return resp.json().get("models", [])

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        instructions = ""
        input_messages = []
        for msg in messages:
            if msg["role"] == "system":
                instructions = msg["content"]
            else:
                input_messages.append({
                    "type": "message",
                    "role": msg["role"],
                    "content": [{"type": "input_text", "text": msg["content"]}]
                })

        payload = {
            "model": self.cfg.model,
            "instructions": instructions,
            "input": input_messages,
            "stream": True
        }
        if tools:
            payload["tools"] = tools

        headers = self._get_headers()
        headers["Accept"] = "text/event-stream"

        full_content = ""
        tool_calls = []
        
        with httpx.Client(timeout=self.cfg.timeout_seconds) as client:
            with client.stream("POST", "https://chatgpt.com/backend-api/codex/responses", json=payload, headers=headers) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data: "): continue
                    try:
                        data = json.loads(line[6:])
                        kind = data.get("kind")
                        if kind == "response.output_text.delta":
                            full_content += data.get("delta", "")
                        elif kind == "response.output_item.done":
                            item = data.get("item", {})
                            if item.get("type") == "function_call":
                                tool_calls.append({
                                    "id": item.get("call_id"),
                                    "type": "function",
                                    "function": {"name": item.get("name"), "arguments": item.get("arguments")}
                                })
                    except: continue

        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"[RESPONSE]{full_content}[/RESPONSE][EOT]",
                    "tool_calls": tool_calls if tool_calls else None
                },
                "finish_reason": "stop"
            }]
        }

    def probe_capabilities(self) -> Dict[str, bool]:
        return {"native_tools": True, "reasoning_channel": True}

def register_providers():
    return {"codex": CodexProvider}

def register_tools():
    def codex_login_handler(**kwargs):
        sandbox = kwargs.get("sandbox")
        root = Path(sandbox.root) if sandbox else Path.cwd()
        return CodexAuth(root).run()

    def codex_list_models_handler(**kwargs):
        sandbox = kwargs.get("sandbox")
        root = Path(sandbox.root) if sandbox else Path.cwd()
        provider = CodexProvider(Config(), root)
        models = provider.fetch_models()
        if not models:
            return "No models found or authentication required."
        
        lines = ["Available Codex Models:"]
        for m in models:
            slug = m.get("slug")
            title = m.get("title", "Untitled")
            lines.append(f"- {slug} ({title})")
        return "\n".join(lines)

    return [
        ToolDefinition(
            name="codex_login",
            description="Login to OpenAI Codex via Device Code flow.",
            parameters={"type": "object", "properties": {}},
            handler=codex_login_handler,
            slash_command="/codex-login"
        ),
        ToolDefinition(
            name="codex_list_models",
            description="List available OpenAI Codex models.",
            parameters={"type": "object", "properties": {}},
            handler=codex_list_models_handler,
            slash_command="/codex-models"
        )
    ]
