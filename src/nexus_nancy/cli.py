from __future__ import annotations

import sys
from pathlib import Path

from .app import build_state, run_prompt
from .config import (
    api_key_path,
    bootstrap_local_files,
    instructions_path,
    load_config,
    open_in_editor,
)
from .doctor import run_doctor

try:
    from .tui import NancyTUI
except Exception:  # pragma: no cover
    NancyTUI = None


HELP = """Nexus-Nancy

Usage:
    nnancy
    nnancy -t \"your prompt\"
    nnancy doctor
    nnancy instructions
    nnancy config

Commands:
    /new                Start a fresh session in this process
    /handoff            Save handoff JSON snapshot
    /handoff PATH       Load prior handoff JSON

Attachments:
    Use @relative/path to inline file content into your prompt
"""


def _parse_args(argv: list[str]) -> tuple[bool, str | None, bool, str | None]:
    yolo = False
    prompt = None
    show_help = False
    command = None

    args = list(argv)
    if args and args[0] == "yolo":
        yolo = True
        args = args[1:]

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"instructions", "config", "doctor"}:
            command = arg
            i += 1
        elif arg in {"-h", "--help"}:
            show_help = True
            i += 1
        elif arg in {"--instructions", "--edit-instructions"}:
            command = "instructions"
            i += 1
        elif arg in {"--config", "--edit-config"}:
            command = "config"
            i += 1
        elif arg == "--doctor":
            command = "doctor"
            i += 1
        elif arg == "-t":
            if i + 1 >= len(args):
                raise SystemExit("-t requires a prompt string")
            prompt = args[i + 1]
            i += 2
        else:
            raise SystemExit(f"unknown arg: {arg}")

    return yolo, prompt, show_help, command


def main() -> None:
    yolo, single_prompt, show_help, command = _parse_args(sys.argv[1:])
    workspace_root = Path.cwd().resolve()
    bootstrap_local_files(workspace_root)

    if show_help:
        print(HELP)
        return

    def fail(message: str) -> None:
        print(f"error: {message}", file=sys.stderr, flush=True)
        raise SystemExit(1)

    if command == "instructions":
        open_in_editor(instructions_path(workspace_root))
        return

    if command == "config":
        cfg = load_config(workspace_root)
        key_path = api_key_path(cfg, workspace_root)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            key_path.write_text("", encoding="utf-8")
        open_in_editor(key_path)
        return

    cfg = load_config(workspace_root)

    if command == "doctor":
        report = run_doctor(cfg, workspace_root)
        print(report.render())
        raise SystemExit(0 if report.ok else 1)

    try:
        state, llm, sandbox = build_state(cfg, yolo=yolo)
    except Exception as exc:
        fail(str(exc))

    if single_prompt:
        try:
            print(run_prompt(state, llm, sandbox, single_prompt))
        except Exception as exc:
            fail(str(exc))
        return

    # Textual needs a real TTY; fallback to simple input loop otherwise.
    if NancyTUI is not None and sys.stdin.isatty() and sys.stdout.isatty():
        try:
            NancyTUI(state, llm, sandbox).run()
            return
        except Exception as exc:
            fail(str(exc))

    while True:
        try:
            text = input("nnancy> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not text:
            continue
        if text in {"/quit", "/exit"}:
            return

        try:
            print(run_prompt(state, llm, sandbox, text))
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
