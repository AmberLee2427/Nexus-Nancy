from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Config, api_key_path, load_instructions, load_sandbox_allowlist, open_in_editor, replace_api_key
from .llm import LLMClient
from .sandbox import SandboxPolicy
from .session import SessionState
from .token_count import estimate_context_tokens
from .tools import TOOL_SPECS, execute_tool


def _attach_files(text: str, workspace_root: Path, max_bytes: int) -> str:
    parts = text.split()
    appended: list[str] = []
    for part in parts:
        if not part.startswith("@") or len(part) < 2:
            continue
        rel = part[1:]
        path = (workspace_root / rel).resolve()
        if workspace_root not in [path, *path.parents] or not path.exists() or not path.is_file():
            appended.append(f"[attachment error] {rel}: not found or outside workspace")
            continue
        data = path.read_bytes()[:max_bytes]
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            content = data.decode("utf-8", errors="replace")
        appended.append(f"\n\n[attachment: {rel}]\n{content}\n[/attachment]")
    return text + "".join(appended)


def _assistant_turn(state: SessionState, llm: LLMClient, sandbox: SandboxPolicy) -> str:
    while True:
        result = llm.chat(state.messages, TOOL_SPECS)
        message = result["choices"][0]["message"]

        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if content:
            assistant_msg["content"] = content
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        state.messages.append(assistant_msg)

        if not tool_calls:
            return content

        for call in tool_calls:
            name = call["function"]["name"]
            args_text = call["function"].get("arguments") or "{}"
            try:
                args = json.loads(args_text)
            except json.JSONDecodeError:
                args = {}
            tool_out = execute_tool(name, args, sandbox)
            state.log.write(f"tool:{name}", tool_out)
            state.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": tool_out,
                }
            )


def run_prompt(
    state: SessionState,
    llm: LLMClient,
    sandbox: SandboxPolicy,
    user_text: str,
) -> str:
    if user_text.strip() == "/config":
        path = api_key_path(state.cfg, state.workspace_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        open_in_editor(path)
        return f"opened key file: {path}"

    if user_text.strip().startswith("/key"):
        _, _, new_value = user_text.strip().partition(" ")
        new_value = new_value.strip()
        if not new_value:
            return "usage: /key YOUR_NEW_API_KEY"
        path = replace_api_key(state.cfg, state.workspace_root, new_value)
        return f"api key replaced in: {path}"

    if user_text.strip() == "/new":
        state.reset(state.log.root)
        return "started new session"

    if user_text.strip().startswith("/handoff"):
        _, _, maybe_path = user_text.strip().partition(" ")
        maybe_path = maybe_path.strip()
        if maybe_path:
            path = (state.workspace_root / maybe_path).resolve()
            if not path.exists():
                return f"handoff file not found: {maybe_path}"
            data = json.loads(path.read_text(encoding="utf-8"))
            state.messages = data.get("messages", state.messages)
            return f"loaded handoff from {maybe_path}"

        payload = {
            "model": state.cfg.model,
            "base_url": state.cfg.base_url,
            "system_prompt": state.system_prompt,
            "messages": state.messages[-30:],
        }
        handoff_text = json.dumps(payload, indent=2)
        out = state.log.root / "handoff.json"
        out.write_text(handoff_text, encoding="utf-8")
        return f"handoff saved to {out}"

    enriched = _attach_files(user_text, state.workspace_root, state.cfg.max_attachment_bytes)
    state.messages.append({"role": "user", "content": enriched})
    state.log.write("user", enriched)

    answer = _assistant_turn(state, llm, sandbox)
    state.log.write("assistant", answer)
    return answer


def build_state(cfg: Config, yolo: bool) -> tuple[SessionState, LLMClient, SandboxPolicy]:
    workspace_root = Path.cwd().resolve()
    logs_dir = workspace_root / "logs"
    instructions = load_instructions(workspace_root)
    state = SessionState.create(cfg, instructions, workspace_root, logs_dir)
    llm = LLMClient(cfg, workspace_root)
    allowlist = load_sandbox_allowlist(workspace_root)
    sandbox = SandboxPolicy(root=workspace_root, yolo=yolo, allowlist_substrings=allowlist)
    return state, llm, sandbox
