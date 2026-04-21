from __future__ import annotations

import asyncio
import getpass
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static
from rich.text import Text

from .app import estimate_context_tokens, run_prompt
from .config import api_key_path, config_path, open_config_in_editor, replace_api_key
from .sandbox import SandboxPolicy
from .session import SessionState


class NancyTUI(App[None]):
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_transcript", "Clear"),
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
        background: #1c1327;
        color: #f1e8ff;
    }

    Header {
        background: #4f2f73;
        color: #f7eeff;
    }

    Footer {
        background: #322145;
        color: #e7d6fb;
    }

    #transcript {
        height: 1fr;
        background: #251a33;
        color: #efe5ff;
        border: round #6d4f92;
    }

    #status {
        height: 1;
        padding: 0 2;
        background: #2f2141;
        color: #d9c9ed;
    }

    #prompt {
        background: #2b1d3a;
        color: #f6ecff;
        border: round #8d6ab3;
    }
    """

    def __init__(self, state: SessionState, llm_client, sandbox: SandboxPolicy):
        super().__init__()
        self.state = state
        self.llm = llm_client
        self.sandbox = sandbox
        self.session_id = uuid4().hex[:10]
        self._plain_blocks: list[tuple[str, str]] = []

        out_dir = self.state.workspace_root / ".agents" / "tracsripts"
        out_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_path = out_dir / f"{self.session_id}.txt"
        self._persist_transcript()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield RichLog(id="transcript", auto_scroll=True, markup=True, highlight=False, wrap=True)
            yield Static("", id="status")
            yield Input(placeholder="Type prompt, /new, /handoff, /copy, /config, /key, /exit", id="prompt")
        yield Footer()

    async def on_mount(self) -> None:
        self._append("system", "Nexus-Nancy ready")
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
            self._append("system", f"opened config file: {config_path(self.state.workspace_root)}")
            self._refresh_status()
            return
        if text == "/key":
            await self.action_replace_key_interactive()
            self._refresh_status()
            return

        self._append("user", text)
        self._refresh_status()
        self.query_one("#status", Static).update("thinking...")

        try:
            reply = await asyncio.to_thread(run_prompt, self.state, self.llm, self.sandbox, text)
            self._append("assistant", reply)
        except Exception as exc:  # pragma: no cover
            self._append("error", str(exc))

        self._refresh_status()

    def action_clear_transcript(self) -> None:
        log = self.query_one("#transcript", RichLog)
        log.clear()
        self._plain_blocks = []
        self._append("system", "Nexus-Nancy ready")

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
            self._append("error", "key not changed: empty value")
            return
        if first != second:
            self._append("error", "key not changed: values do not match")
            return
        path = replace_api_key(self.state.cfg, self.state.workspace_root, first)
        self._append("system", f"api key replaced in: {path}")

    def action_scroll_down(self) -> None:
        self.query_one("#transcript", RichLog).scroll_down(animate=False)

    def action_scroll_up(self) -> None:
        self.query_one("#transcript", RichLog).scroll_up(animate=False)

    def action_page_down(self) -> None:
        self.query_one("#transcript", RichLog).scroll_page_down(animate=False)

    def action_page_up(self) -> None:
        self.query_one("#transcript", RichLog).scroll_page_up(animate=False)

    def action_scroll_top(self) -> None:
        self.query_one("#transcript", RichLog).scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        self.query_one("#transcript", RichLog).scroll_end(animate=False)

    def _append(self, role: str, text: str) -> None:
        transcript = self.query_one("#transcript", RichLog)
        role_color = {
            "assistant": "#c9a3ff",  # lavender
            "error": "#ffc1a6",      # peach
            "system": "#b9afc7",     # gray-lilac
            "user": "#ffe2ff",       # soft near-white
        }.get(role, "#efe5ff")
        markers = {
            "assistant": "NANCY",
            "user": (self.state.cfg.user_display_name or "USER").strip().upper(),
            "system": "SYS",
            "error": "ERR",
        }
        marker = markers.get(role, role.upper())
        self._plain_blocks.append((marker, text))
        self._persist_transcript()
        transcript.write("")
        transcript.write(Text(f"[{marker}]", style=role_color))
        for line in (text.splitlines() or [""]):
            transcript.write(Text(line, style=role_color))
        transcript.write("")

    def _refresh_status(self) -> None:
        status = self.query_one("#status", Static)
        mode = "yolo" if self.sandbox.yolo else "sandbox"
        cwd = Path.cwd().name
        tokens = estimate_context_tokens(self.state.messages, self.state.cfg.model)
        status.update(
            f"model={self.state.cfg.model} | mode={mode} | cwd={cwd} | "
            f"context_tokens~{tokens} | id={self.session_id}"
        )

    def _persist_transcript(self) -> None:
        lines: list[str] = [f"# Nexus-Nancy transcript id={self.session_id}"]
        for marker, text in self._plain_blocks:
            lines.append("")
            lines.append(f"[{marker}]")
            lines.extend(text.splitlines() or [""])
        self.transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
