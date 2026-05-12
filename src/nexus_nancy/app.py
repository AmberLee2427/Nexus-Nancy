from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from .capabilities import detect_capabilities
from .config import (
    Config,
    handoff_instructions_path,
    load_sandbox_allowlist,
    open_config_in_editor,
    relay_instructions_path,
    render_prompt_template,
    replace_api_key,
)
from .context import build_native_openai_context, build_universal_context
from .execution import STRATEGY_NATIVE_OPENAI, STRATEGY_UNIVERSAL, select_execution_strategy
from .provider import LLMProvider, get_provider
from .sandbox import SandboxPolicy
from .session import SessionState
from .tools import REGISTRY, TOOL_SPECS, execute_tool, initialize_tools, validate_tool_arguments

EOT_TOKEN = "[EOT]"
MAX_NO_TOOL_ASSISTANT_MESSAGES_WITHOUT_EOT = 2
RESPONSE_BLOCK_RE = re.compile(r"\[RESPONSE\](.*?)\[/RESPONSE\]", re.DOTALL)


@dataclass
class ParsedAssistantContent:
    response_blocks: list[str]
    private_text: str
    has_eot: bool


@dataclass
class ToolApprovalRequest:
    call_id: str
    name: str
    arguments_text: str
    arguments: dict[str, Any]


@dataclass
class ToolApprovalDecision:
    action: str
    response_text: str = ""


@dataclass
class ToolCallRecord:
    name: str
    arguments_text: str
    arguments: dict[str, Any]
    status: str
    output: str

    @property
    def title(self) -> str:
        return f"{self.name} {self.arguments_text}"


@dataclass
class TranscriptEvent:
    kind: str
    text: str
    title: str


@dataclass
class PromptResult:
    response_blocks: list[str] = field(default_factory=list)
    private_blocks: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    system_messages: list[str] = field(default_factory=list)
    transcript_events: list[TranscriptEvent] = field(default_factory=list)

    def add_system(self, text: str) -> None:
        self.system_messages.append(text)
        self.transcript_events.append(TranscriptEvent(kind="system", title="SYS", text=text))

    def add_response(self, text: str) -> None:
        self.response_blocks.append(text)
        self.transcript_events.append(TranscriptEvent(kind="response", title="NANCY", text=text))

    def add_private(self, text: str, index: int, note: str = "") -> None:
        self.private_blocks.append(text)
        self.transcript_events.append(TranscriptEvent(kind="raw", title=f"RAW {index}", text=text))
        # Store the note in the event text or metadata if we had it,
        # but for now we'll just prefix the text with the note.
        if note:
            self.transcript_events[-1].text = f"note: {note}\n\n{text}"

    def add_tool(self, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)
        text = "\n".join(
            [
                f"status: {record.status}",
                f"tool: {record.name}",
                f"arguments: {record.arguments_text}",
                "output:",
                record.output,
            ]
        ).strip()
        self.transcript_events.append(
            TranscriptEvent(kind="debug", title=f"TOOL {record.status.upper()}", text=text)
        )

    @property
    def response_text(self) -> str:
        return "\n\n".join(block for block in self.response_blocks if block.strip()).strip()

    def to_cli_text(self) -> str:
        chunks: list[str] = []
        if self.response_text:
            chunks.append(self.response_text)
        if self.system_messages:
            chunks.append("\n".join(self.system_messages))
        return "\n\n".join(chunk for chunk in chunks if chunk.strip()).strip()


ToolApprovalHandler = Callable[[ToolApprovalRequest], ToolApprovalDecision]


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


def _extract_blocks(pattern: re.Pattern[str], text: str) -> list[str]:
    return [match.strip() for match in pattern.findall(text) if match.strip()]


def _parse_assistant_content(content: str) -> ParsedAssistantContent:
    has_eot = EOT_TOKEN in content
    stripped = content.replace(EOT_TOKEN, "")
    response_blocks = _extract_blocks(RESPONSE_BLOCK_RE, stripped)
    private_text = RESPONSE_BLOCK_RE.sub("", stripped)
    private_text = private_text.strip()
    return ParsedAssistantContent(
        response_blocks=response_blocks,
        private_text=private_text,
        has_eot=has_eot,
    )


def _tool_requires_approval(name: str, args: dict[str, Any], sandbox: SandboxPolicy) -> bool:
    if sandbox.yolo:
        return False
    if name == "bash":
        command = str(args.get("command", ""))
        return not sandbox.is_allowlisted(command)
    return True


def _handle_tool_call(
    state: SessionState,
    call: dict[str, Any],
    sandbox: SandboxPolicy,
    tool_approval: ToolApprovalHandler | None,
) -> tuple[ToolCallRecord, dict[str, Any], str | None]:
    name = call["function"]["name"]
    args_text = call["function"].get("arguments") or "{}"
    injected_user: str | None = None

    try:
        raw_args = json.loads(args_text)
    except json.JSONDecodeError as exc:
        # Tool argument failures should quote the real parser error. Do not
        # replace this with a vague "invalid tool call" message.
        output = f"error: tool arguments were not valid JSON ({exc})"
        return (
            ToolCallRecord(
                name=name,
                arguments_text=args_text,
                arguments={},
                status="error",
                output=output,
            ),
            {"role": "tool", "tool_call_id": call["id"], "content": output},
            None,
        )

    normalized_args, validation_error = validate_tool_arguments(name, raw_args)
    if validation_error:
        # Keep validator output explicit because the exact missing/wrong field is
        # the actionable part.
        output = f"error: {validation_error}"
        return (
            ToolCallRecord(
                name=name,
                arguments_text=args_text,
                arguments=raw_args if isinstance(raw_args, dict) else {},
                status="error",
                output=output,
            ),
            {"role": "tool", "tool_call_id": call["id"], "content": output},
            None,
        )

    assert normalized_args is not None

    if _tool_requires_approval(name, normalized_args, sandbox) and tool_approval is not None:
        decision = tool_approval(
            ToolApprovalRequest(
                call_id=call["id"],
                name=name,
                arguments_text=args_text,
                arguments=normalized_args,
            )
        )
        if decision.action == "deny":
            # Approval decisions are part of the observable protocol history and
            # should stay visible in plain text.
            output = f"error: user denied tool call '{name}'"
            return (
                ToolCallRecord(
                    name=name,
                    arguments_text=args_text,
                    arguments=normalized_args,
                    status="denied",
                    output=output,
                ),
                {"role": "tool", "tool_call_id": call["id"], "content": output},
                None,
            )
        if decision.action == "respond":
            response_text = decision.response_text.strip()
            if not response_text:
                output = "error: user chose respond but supplied no response text"
                return (
                    ToolCallRecord(
                        name=name,
                        arguments_text=args_text,
                        arguments=normalized_args,
                        status="error",
                        output=output,
                    ),
                    {"role": "tool", "tool_call_id": call["id"], "content": output},
                    None,
                )
            output = "tool execution skipped: user responded instead"
            injected_user = response_text
            return (
                ToolCallRecord(
                    name=name,
                    arguments_text=args_text,
                    arguments=normalized_args,
                    status="responded",
                    output=output,
                ),
                {"role": "tool", "tool_call_id": call["id"], "content": output},
                injected_user,
            )

    output = execute_tool(name, normalized_args, sandbox)
    status = "executed" if not output.startswith("error:") else "error"
    return (
        ToolCallRecord(
            name=name,
            arguments_text=args_text,
            arguments=normalized_args,
            status=status,
            output=output,
        ),
        {"role": "tool", "tool_call_id": call["id"], "content": output},
        injected_user,
    )


def _json_objects_from_text(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    stripped = text.strip()
    candidates = [stripped]

    fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(fenced)

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            objects.append(parsed)

    for idx, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(stripped[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)

    return objects


def _raw_function_call_from_text(content: str) -> dict[str, Any] | None:
    for obj in _json_objects_from_text(content):
        fn = obj.get("function") if isinstance(obj.get("function"), dict) else {}
        name = obj.get("name") or obj.get("tool") or fn.get("name")
        args = obj.get("arguments")
        if args is None:
            args = obj.get("args")
        if args is None:
            args = fn.get("arguments")
        if not isinstance(name, str):
            continue
        if isinstance(args, str):
            args_text = args
            try:
                decoded_args = json.loads(args_text)
            except json.JSONDecodeError:
                continue
        elif isinstance(args, dict):
            decoded_args = args
            args_text = json.dumps(args, ensure_ascii=False)
        else:
            continue
        _, validation_error = validate_tool_arguments(name, decoded_args)
        if validation_error:
            continue
        return {
            "id": f"raw_call_{uuid4().hex[:12]}",
            "type": "function",
            "function": {"name": name, "arguments": args_text},
        }
    return None


def _assistant_turn_universal(
    state: SessionState,
    llm: LLMProvider,
    sandbox: SandboxPolicy,
    tool_approval: ToolApprovalHandler | None = None,
) -> PromptResult:
    result = PromptResult()
    private_index = 0
    no_tool_assistant_messages_without_eot = 0

    while True:
        api_result = llm.chat(state.messages, TOOL_SPECS)
        message = api_result["choices"][0]["message"]

        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if content:
            assistant_msg["content"] = content
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        state.messages.append(assistant_msg)
        # Persist raw assistant content before any parsing/rendering so protocol
        # mistakes remain inspectable in logs and transcripts.
        state.log.write("assistant_raw", content or "<empty>")

        parsed = _parse_assistant_content(content)
        for block in parsed.response_blocks:
            result.add_response(block)
        if parsed.private_text:
            private_text = parsed.private_text
            for response_block in parsed.response_blocks:
                private_text = private_text.replace(response_block, "")
            private_text = private_text.strip()
        else:
            private_text = ""
        if private_text:
            private_index += 1
            result.add_private(
                private_text,
                private_index,
                note=(
                    "The model produced text outside of the formal [RESPONSE] protocol blocks. "
                    "This content is displayed here to preserve the model's internal "
                    "chain-of-thought and any unstructured output that was not intended "
                    "as part of the final user-facing response."
                ),
            )

        if (
            state.cfg.model == "mock-shakespeare"
            and not tool_calls
            and (not parsed.response_blocks or not parsed.has_eot)
        ):
            raise RuntimeError(
                "mock server protocol violation.\n"
                "expected: user-facing text inside [RESPONSE]...[/RESPONSE] followed by [EOT]\n"
                f"model: {state.cfg.model}\n"
                f"base_url: {state.cfg.base_url}\n"
                "raw_content:\n"
                f"{content or '<empty>'}"
            )

        if tool_calls:
            no_tool_assistant_messages_without_eot = 0
            for call in tool_calls:
                record, tool_message, injected_user = _handle_tool_call(
                    state, call, sandbox, tool_approval
                )
                result.add_tool(record)
                # Tool output is recorded verbatim because command failures and
                # provider/tool protocol mismatches are usually debugged from the
                # exact plain-text output.
                state.log.write(f"tool:{record.name}", record.output)
                state.messages.append(tool_message)
                if injected_user:
                    state.messages.append({"role": "user", "content": injected_user})
                    state.log.write("user", injected_user)
            continue

        if parsed.has_eot:
            return result

        no_tool_assistant_messages_without_eot += 1
        if no_tool_assistant_messages_without_eot >= MAX_NO_TOOL_ASSISTANT_MESSAGES_WITHOUT_EOT:
            return result


def _assistant_turn_native_openai(
    state: SessionState,
    llm: LLMProvider,
    sandbox: SandboxPolicy,
    tool_approval: ToolApprovalHandler | None = None,
) -> PromptResult:
    result = PromptResult()
    private_index = 0

    while True:
        api_result = llm.chat(
            state.messages,
            TOOL_SPECS,
            parallel_tool_calls=bool(getattr(state.capabilities, "parallel_tool_calls", False)),
        )
        message = api_result["choices"][0]["message"]
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        # Logic for transparency: Put everything except the visible content
        # into the diagnostic 'raw' block. This includes reasoning_content,
        # tool_calls, and any provider-specific fields.
        raw_payload = {k: v for k, v in message.items() if k != "content"}
        if len(raw_payload) > 1:  # More than just "role": "assistant"
            private_index += 1
            raw_text = json.dumps(raw_payload, indent=2, ensure_ascii=False)
            result.add_private(
                raw_text,
                private_index,
                note=(
                    "This block contains the model's native reasoning and structural metadata "
                    "as delivered by the provider. It represents the internal logic, thinking "
                    "process, and tool-calling parameters used to formulate the final answer."
                ),
            )
            state.log.write("assistant_raw_metadata", raw_text)

        raw_call = None if tool_calls else _raw_function_call_from_text(content)
        if raw_call is not None:
            tool_calls = [raw_call]

        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if content and raw_call is None:
            assistant_msg["content"] = content
        elif content:
            assistant_msg["content"] = content
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        state.messages.append(assistant_msg)
        state.log.write("assistant_raw", content or "<empty>")

        if tool_calls:
            if content:
                private_index += 1
                # Show the raw content (including any <|think|> tags) in the
                # diagnostic transcript view.
                result.add_private(content, private_index)
            for call in tool_calls:
                record, tool_message, injected_user = _handle_tool_call(
                    state, call, sandbox, tool_approval
                )
                result.add_tool(record)
                state.log.write(f"tool:{record.name}", record.output)
                state.messages.append(tool_message)
                if injected_user:
                    state.messages.append({"role": "user", "content": injected_user})
                    state.log.write("user", injected_user)
            continue

        if content.strip():
            # For the final turn with no tools, the content is the visible response.
            result.add_response(content.strip())
        return result


def _assistant_turn_for_strategy(
    state: SessionState,
    llm: LLMProvider,
    sandbox: SandboxPolicy,
    tool_approval: ToolApprovalHandler | None = None,
) -> PromptResult:
    if state.execution_strategy == STRATEGY_NATIVE_OPENAI:
        return _assistant_turn_native_openai(state, llm, sandbox, tool_approval)
    return _assistant_turn_universal(state, llm, sandbox, tool_approval)


def run_prompt(
    state: SessionState,
    llm: LLMProvider,
    sandbox: SandboxPolicy,
    user_text: str,
    *,
    tool_approval: ToolApprovalHandler | None = None,
) -> PromptResult:
    command = user_text.strip()

    # Check for extensible slash commands from tools first
    if command.startswith("/"):
        cmd_parts = command.split()
        cmd_name = cmd_parts[0]
        tool = REGISTRY.get_slash_command(cmd_name)
        if tool and tool.handler:
            # Parse arguments: "/reload reason=foo bar" -> {"reason": "foo bar"}
            args = {}
            for part in cmd_parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    args[key] = value
                else:
                    args[part] = ""
            try:
                result = tool.handler(**args)
                if result is None:
                    raise RuntimeError(
                        f"tool handler for '{cmd_name}' returned None; "
                        "handlers must return a string (even if empty) to acknowledge the command"
                    )
                return PromptResult(system_messages=[result])
            except Exception as e:
                # Include the exception type for technical users (scientists)
                error_type = type(e).__name__
                return PromptResult(
                    system_messages=[f"error executing {cmd_name}: {error_type}: {e}"]
                )

    # Built-in slash commands
    if command == "/config":
        path = open_config_in_editor(state.workspace_root)
        return PromptResult(system_messages=[f"opened config file: {path}"])

    if command.startswith("/key"):
        _, _, new_value = command.partition(" ")
        new_value = new_value.strip()
        if not new_value:
            return PromptResult(system_messages=["usage: /key YOUR_NEW_API_KEY"])
        path = replace_api_key(state.cfg, state.workspace_root, new_value)
        return PromptResult(system_messages=[f"api key replaced in: {path}"])

    if command == "/new":
        state.reset(state.log.root)
        return PromptResult(system_messages=["started new session"])

    if command.startswith("/handoff"):
        _, _, maybe_path = command.partition(" ")
        maybe_path = maybe_path.strip()
        if maybe_path:
            path = (state.workspace_root / maybe_path).resolve()
            if not path.exists():
                return PromptResult(system_messages=[f"handoff file not found: {maybe_path}"])
            data = json.loads(path.read_text(encoding="utf-8"))
            state.messages = data.get("messages", state.messages)
            return PromptResult(system_messages=[f"loaded handoff from {maybe_path}"])

        chat_history = state.messages[:]
        assistant_raw_blocks = [
            m for m in chat_history if m.get("role") == "assistant" and m.get("content")
        ]
        tool_outputs = [m for m in chat_history if m.get("role") == "tool"]
        if not assistant_raw_blocks:
            assistant_raw_blocks = [
                {"role": "assistant", "content": "No assistant raw content present."}
            ]
        if not tool_outputs:
            tool_outputs = [{"role": "tool", "content": "No tool call outputs present."}]

        handoff_prompt = handoff_instructions_path(state.workspace_root).read_text(encoding="utf-8")

        todo_path = state.workspace_root / ".agents/TODO.md"
        todo = (
            todo_path.read_text(encoding="utf-8").strip()
            if todo_path.exists()
            else "(No todo list present)"
        )

        summary_model = getattr(
            state.cfg,
            "summary_model",
            getattr(state.cfg, "model", "gpt-4o-mini"),
        )
        summary_cfg = Config(
            model=summary_model,
            **{key: value for key, value in state.cfg.__dict__.items() if key != "model"},
        )
        summary_llm = get_provider(summary_cfg, state.workspace_root)
        summary_messages = [
            {"role": "system", "content": handoff_prompt},
            {
                "role": "user",
                "content": (
                    f"Here is the conversation history:\n\n{json.dumps(chat_history, indent=2)}"
                    "\n\nHere is the raw assistant content:\n\n"
                    f"{json.dumps(assistant_raw_blocks, indent=2)}"
                    f"\n\nHere are the tool call outputs:\n\n{json.dumps(tool_outputs, indent=2)}"
                    f"\n\nThe current todo list is:\n{todo}"
                ),
            },
        ]
        try:
            summary_result = summary_llm.chat(summary_messages, tools=[])
            summary_content = summary_result["choices"][0]["message"].get(
                "content", "(No summary returned)"
            )
        except Exception as exc:
            summary_content = f"(Summary failed: {exc})"

        summary_match = re.search(r"\[SUMMARY\](.*?)\[/SUMMARY\]", summary_content, re.DOTALL)
        todo_match = re.search(r"\[TODO\](.*?)\[/TODO\]", summary_content, re.DOTALL)
        summary_text = summary_match.group(1).strip() if summary_match else summary_content.strip()
        todo_text = todo_match.group(1).strip() if todo_match else "(No todo found in summary)"

        summary_path = state.workspace_root / ".agents/SUMMARY.md"
        todo_path = state.workspace_root / ".agents/TODO.md"
        summary_path.write_text(summary_text, encoding="utf-8")
        todo_path.write_text(todo_text, encoding="utf-8")

        relay_prompt_template = relay_instructions_path(state.workspace_root).read_text(
            encoding="utf-8"
        )
        relay_prompt = render_prompt_template(
            relay_prompt_template,
            {
                "instructions": state.system_prompt,
                "summary": summary_text,
                "todo": todo_text,
            },
        )
        logs_dir = state.workspace_root / "logs"
        new_state = SessionState.create(state.cfg, relay_prompt, state.workspace_root, logs_dir)
        new_state.execution_strategy = state.execution_strategy
        new_state.capabilities = state.capabilities
        new_state.messages.append(
            {"role": "user", "content": f"[SUMMARY]\n{summary_text}\n[/SUMMARY]"}
        )
        new_state.messages.append({"role": "user", "content": f"[TODO]\n{todo_text}\n[/TODO]"})
        state.cfg = new_state.cfg
        state.system_prompt = new_state.system_prompt
        state.workspace_root = new_state.workspace_root
        state.log = new_state.log
        state.messages = new_state.messages
        return PromptResult(
            system_messages=[
                "Handoff complete. Summary and todo saved. New session started with relay prompt."
            ]
        )

    # Catch unrecognized slash commands before they fall through to the LLM
    if command.startswith("/"):
        return PromptResult(
            system_messages=[
                f"error: unknown command '{command.split()[0]}'. "
                "If this is a plugin command, ensure the plugin is installed and loaded correctly."
            ]
        )

    enriched = _attach_files(user_text, state.workspace_root, state.cfg.max_attachment_bytes)
    state.messages.append({"role": "user", "content": enriched})
    # Log the expanded user message, not a cleaned version, so attachments and
    # inline prompt context can be audited after the fact.
    state.log.write("user", enriched)

    answer = _assistant_turn_for_strategy(state, llm, sandbox, tool_approval=tool_approval)
    if answer.response_text:
        # Visible assistant text gets its own log channel, but the raw assistant
        # content above remains authoritative for debugging.
        state.log.write("assistant_visible", answer.response_text)
    for note in answer.system_messages:
        state.log.write("system", note)
    return answer


def build_state(cfg: Config, yolo: bool) -> tuple[SessionState, LLMProvider, SandboxPolicy]:
    workspace_root = Path.cwd().resolve()
    initialize_tools(workspace_root)
    logs_dir = workspace_root / "logs"
    capabilities = detect_capabilities(cfg, workspace_root)
    selection = select_execution_strategy(cfg, capabilities)
    if selection.selected == STRATEGY_UNIVERSAL:
        instructions = build_universal_context(cfg, workspace_root)
    else:
        instructions = build_native_openai_context(cfg)
    state = SessionState.create(cfg, instructions, workspace_root, logs_dir)
    state.execution_strategy = selection.selected
    state.capabilities = selection.capabilities
    llm = get_provider(cfg, workspace_root)
    allowlist = load_sandbox_allowlist(workspace_root)
    sandbox_root = Path(cfg.sandbox_root).expanduser()
    if not sandbox_root.is_absolute():
        sandbox_root = (workspace_root / sandbox_root).resolve()
    else:
        sandbox_root = sandbox_root.resolve()
    sandbox = SandboxPolicy(root=sandbox_root, yolo=yolo, allowlist_substrings=allowlist)
    return state, llm, sandbox
