from __future__ import annotations

import asyncio
import getpass
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Footer, Header, Input, Label, Static

from .app import PromptResult, ToolApprovalDecision, ToolApprovalRequest, run_prompt
from .config import config_path, open_config_in_editor, replace_api_key
from .sandbox import SandboxPolicy
from .session import SessionState
from .token_count import estimate_context_tokens


class ToolApprovalScreen(ModalScreen[ToolApprovalDecision]):
    CSS = """
    ToolApprovalScreen {
        align: center middle;
    }

    #approval-dialog {
        width: 88;
        max-width: 96;
        padding: 1 2;
        background: #1f1824;
        border: round #d6b24d;
    }

    #approval-title {
        text-style: bold;
        color: #ffe49a;
        padding-bottom: 1;
    }

    #approval-body {
        background: #17111c;
        color: #f3ebff;
        border: round #5c4566;
        padding: 1;
        margin-bottom: 1;
    }

    #approval-error {
        color: #ffb3a2;
        height: auto;
        margin-top: 1;
    }

    #approval-buttons {
        grid-size: 3;
        grid-gutter: 1 2;
        margin-top: 1;
    }
    """

    def __init__(self, request: ToolApprovalRequest) -> None:
        super().__init__()
        self.request = request

    def compose(self) -> ComposeResult:
        with Grid(id="approval-dialog"):
            yield Label("Approve tool call?", id="approval-title")
            yield Static(self._body_text(), id="approval-body")
            yield Input(
                placeholder="Optional reply to the model if you choose Respond",
                id="approval-response",
            )
            with Grid(id="approval-buttons"):
                yield Button("Yes", variant="success", id="approve-yes")
                yield Button("No", variant="error", id="approve-no")
                yield Button("Respond", variant="warning", id="approve-respond")
            yield Static("", id="approval-error")

    def _body_text(self) -> str:
        return (
            "This tool call is outside the current allowlist.\n\n"
            f"tool: {self.request.name}\n"
            f"arguments: {self.request.arguments_text}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve-yes":
            self.dismiss(ToolApprovalDecision(action="approve"))
            return
        if event.button.id == "approve-no":
            self.dismiss(ToolApprovalDecision(action="deny"))
            return
        response = self.query_one("#approval-response", Input).value.strip()
        if not response:
            self.query_one("#approval-error", Static).update(
                "Enter a response first, or choose Yes/No."
            )
            return
        self.dismiss(ToolApprovalDecision(action="respond", response_text=response))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "approval-response":
            return
        response = event.value.strip()
        if not response:
            self.query_one("#approval-error", Static).update(
                "Enter a response first, or choose Yes/No."
            )
            return
        self.dismiss(ToolApprovalDecision(action="respond", response_text=response))


class NancyTUI(App[None]):
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_transcript", "Clear"),
        Binding("ctrl+r", "toggle_debug", "Debug"),
        Binding("ctrl+y", "copy_mode", "Copy"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("pagedown", "page_down", "PgDn", show=False),
        Binding("pageup", "page_up", "PgUp", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
    ]

    CSS = """
    Screen {
        layout: vertical;
        background: #140d21;
        color: #f2e9fb;
    }

    Header {
        background: #4a2870;
        color: #f8def6;
    }

    Footer {
        background: #27163b;
        color: #e7d4f6;
    }

    #transcript {
        height: 1fr;
        background: #120a1c;
        border: round #7e53ad;
        padding: 0 1;
    }

    #status {
        height: auto;
        padding: 0 2;
        background: #221333;
        color: #e5d6f5;
    }

    #prompt {
        background: #1b1029;
        color: #f7efff;
        border: round #b06ae0;
    }

    .block {
        margin: 1 0;
        padding: 0 1;
        border: round #6f5588;
    }

    .user-block {
        background: #28142f;
        color: #ffe4f2;
        border: round #cc79c7;
    }

    .system-block {
        background: #1b1526;
        color: #d6c9e4;
        border: round #68567c;
    }

    .error-block {
        background: #341522;
        color: #ffd6e2;
        border: round #d46a8b;
    }

    .response-block {
        background: #191126;
        color: #f1e8ff;
        border: round #9961d6;
    }

    .tool-block {
        background: #181325;
        color: #efe3ff;
        border: round #8d76cf;
    }

    .raw-block {
        background: #17111f;
        color: #ded2ec;
        border: round #8262a8;
    }

    .debug-block {
        margin: 1 0;
        border: round #745b92;
        background: #14101d;
    }

    .debug-body {
        padding: 0 1;
        color: #d8cee6;
    }
    """

    def __init__(self, state: SessionState, llm_client, sandbox: SandboxPolicy):
        super().__init__()
        self.state = state
        self.llm = llm_client
        self.sandbox = sandbox
        self.session_id = uuid4().hex[:10]
        self._plain_blocks: list[tuple[str, str]] = []
        self._debug_widgets: list[Collapsible] = []
        self._debug_collapsed = True
        self._raw_count = 0

        out_dir = self.state.workspace_root / ".agents" / "transcripts"
        out_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_path = out_dir / f"{self.session_id}.txt"
        self._persist_transcript()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield VerticalScroll(id="transcript")
            yield Static("", id="status")
            yield Input(
                placeholder="Type prompt, /new, /handoff, /copy, /config, /key, /exit",
                id="prompt",
            )
        yield Footer()

    async def on_mount(self) -> None:
        await self._append_block("system", "SYS", "Nexus-Nancy ready")
        await self._append_block(
            "system",
            "SYS",
            "Logs and transcripts are plain local files in this workspace. "
            "Anyone with access here can read them.",
        )
        self._refresh_status()
        self.query_one("#prompt", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text in {"/quit", "/exit"}:
            self.exit()
            return
        if text == "/copy":
            await self.action_copy_mode()
            self._refresh_status()
            return
        if text == "/config":
            await self.action_open_config_file()
            await self._append_block(
                "system",
                "SYS",
                f"opened config file: {config_path(self.state.workspace_root)}",
            )
            self._refresh_status()
            return
        if text == "/key":
            await self.action_replace_key_interactive()
            self._refresh_status()
            return

        user_marker = (self.state.cfg.user_display_name or "USER").strip().upper()
        await self._append_block("user", user_marker, text)
        self._refresh_status()
        self.query_one("#status", Static).update("thinking...")

        try:
            result = await asyncio.to_thread(
                run_prompt,
                self.state,
                self.llm,
                self.sandbox,
                text,
                tool_approval=self._tool_approval_from_worker,
            )
            await self._render_prompt_result(result)
        except Exception as exc:  # pragma: no cover
            # Preserve the original exception text exactly. The TUI is a display
            # surface, not an editorial layer.
            await self._append_block("error", "ERR", str(exc))

        self._refresh_status()

    async def action_clear_transcript(self) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        await transcript.remove_children()
        self._plain_blocks = []
        self._debug_widgets = []
        self._raw_count = 0
        self._debug_collapsed = True
        await self._append_block("system", "SYS", "Nexus-Nancy ready")
        await self._append_block(
            "system",
            "SYS",
            "Logs and transcripts are plain local files in this workspace. "
            "Anyone with access here can read them.",
        )

    async def action_copy_mode(self) -> None:
        with self.suspend():
            print(f"\nCopy mode: {self.transcript_path}")
            print("Native terminal selection is active while TUI is suspended.\n")
            if shutil.which("less"):
                subprocess.run(["less", str(self.transcript_path)], check=False)
            else:
                subprocess.run(["cat", str(self.transcript_path)], check=False)

    async def action_open_config_file(self) -> None:
        with self.suspend():
            open_config_in_editor(self.state.workspace_root)

    async def action_replace_key_interactive(self) -> None:
        with self.suspend():
            first = getpass.getpass("New API key (input hidden): ").strip()
            second = getpass.getpass("Confirm API key: ").strip()
        if not first:
            await self._append_block("error", "ERR", "key not changed: empty value")
            return
        if first != second:
            await self._append_block("error", "ERR", "key not changed: values do not match")
            return
        path = replace_api_key(self.state.cfg, self.state.workspace_root, first)
        await self._append_block("system", "SYS", f"api key replaced in: {path}")

    def action_toggle_debug(self) -> None:
        self._debug_collapsed = not self._debug_collapsed
        for widget in self._debug_widgets:
            widget.collapsed = self._debug_collapsed

    def action_scroll_down(self) -> None:
        self.query_one("#transcript", VerticalScroll).scroll_down(animate=False)

    def action_scroll_up(self) -> None:
        self.query_one("#transcript", VerticalScroll).scroll_up(animate=False)

    def action_page_down(self) -> None:
        self.query_one("#transcript", VerticalScroll).scroll_page_down(animate=False)

    def action_page_up(self) -> None:
        self.query_one("#transcript", VerticalScroll).scroll_page_up(animate=False)

    def action_scroll_top(self) -> None:
        self.query_one("#transcript", VerticalScroll).scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        self.query_one("#transcript", VerticalScroll).scroll_end(animate=False)

    async def _render_prompt_result(self, result: PromptResult) -> None:
        if result.transcript_events:
            for event in result.transcript_events:
                if event.kind == "raw":
                    self._raw_count += 1
                    await self._append_raw_block(
                        self._raw_count, self._format_private_block(event.text)
                    )
                    continue
                if event.kind == "debug":
                    await self._append_debug_block(event.title, event.text)
                    continue
                await self._append_block(event.kind, event.title, event.text)
            return

        for note in result.system_messages:
            await self._append_block("system", "SYS", note)
        for block in result.response_blocks:
            await self._append_block("response", "NANCY", block)
        for block in result.private_blocks:
            # Raw assistant spill outside protocol blocks is intentionally shown.
            # Hiding or prettifying it would destroy debugging value.
            self._raw_count += 1
            await self._append_raw_block(self._raw_count, self._format_private_block(block))
        for record in result.tool_calls:
            await self._append_debug_block(
                f"TOOL {record.status.upper()}", self._format_tool_record(record)
            )

    async def _append_block(self, kind: str, title: str, text: str) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        widget = Static(Text(text or ""), classes=f"block {kind}-block")
        widget.border_title = title
        self._plain_blocks.append((title, text))
        self._persist_transcript()
        await transcript.mount(widget)
        transcript.scroll_end(animate=False)

    async def _append_raw_block(self, index: int, text: str) -> None:
        await self._append_debug_block(f"RAW {index}", text)

    async def _append_debug_block(self, title: str, text: str) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        body = Static(Text(text or ""), classes="debug-body")
        widget = Collapsible(
            body,
            title=title,
            collapsed=True,
            classes="debug-block",
        )
        widget.collapsed = self._debug_collapsed
        self._debug_widgets.append(widget)
        self._plain_blocks.append((title, text))
        self._persist_transcript()
        await transcript.mount(widget)
        transcript.scroll_end(animate=False)

    async def _request_tool_approval(self, request: ToolApprovalRequest) -> ToolApprovalDecision:
        self.query_one("#status", Static).update("waiting for tool approval...")
        decision = await self.push_screen_wait(ToolApprovalScreen(request))
        self._refresh_status()
        return decision or ToolApprovalDecision(action="deny")

    def _tool_approval_from_worker(self, request: ToolApprovalRequest) -> ToolApprovalDecision:
        return self.call_from_thread(self._request_tool_approval, request)

    def _format_private_block(self, text: str) -> str:
        # Keep the ugly labels. This is debug output, not polished UI copy.
        return "\n".join(
            [
                "kind: assistant_raw",
                "note: assistant emitted text outside [RESPONSE]...[/RESPONSE]",
                "",
                text,
            ]
        ).strip()

    def _format_tool_record(self, record) -> str:
        # Tool records stay fielded and explicit on purpose. This should read
        # more like notebook output or a traceback payload than a chat bubble.
        return "\n".join(
            [
                f"status: {record.status}",
                f"tool: {record.name}",
                f"arguments: {record.arguments_text}",
                "output:",
                record.output,
            ]
        ).strip()

    def _refresh_status(self) -> None:
        status = self.query_one("#status", Static)
        mode = "yolo" if self.sandbox.yolo else "sandbox"
        cwd = Path.cwd().name
        tokens = estimate_context_tokens(self.state.messages, self.state.cfg.model)
        debug_state = "collapsed" if self._debug_collapsed else "expanded"
        route = getattr(self.state, "execution_strategy", "universal")
        status.update(
            f"model={self.state.cfg.model} | route={route} | mode={mode} | cwd={cwd} | "
            f"context_tokens~{tokens} | debug={debug_state} | id={self.session_id}"
        )

    def _persist_transcript(self) -> None:
        lines: list[str] = [f"# Nexus-Nancy transcript id={self.session_id}"]
        for marker, text in self._plain_blocks:
            lines.append("")
            lines.append(f"[{marker}]")
            lines.extend(text.splitlines() or [""])
        self.transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
