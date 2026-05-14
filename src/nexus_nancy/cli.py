from __future__ import annotations

import os
import runpy
import socket
import subprocess
import sys
import time
from pathlib import Path

from .app import build_state, run_prompt
from .config import (
    Config,
    bootstrap_local_files,
    instructions_path,
    load_config,
    open_config_in_editor,
    open_in_editor,
    open_secrets_in_editor,
)
from .doctor import run_doctor
from .tools import initialize_tools

try:
    from .tui import NancyTUI
except Exception:  # pragma: no cover
    NancyTUI = None


HELP = """Nexus-Nancy

Usage:
    nnancy [options]

Options:
    -t, --transcript       Include the full reasoning transcript in the output.
    <prompt>               The prompt text (e.g. `nnancy -t "Say hello"`).
                           If omitted, drops into the interactive TUI.

Commands:
    nnancy doctor          Run a diagnostic health check on the LLM and API key.
    nnancy instructions    Open the system prompt instructions file in your editor.
    nnancy config          Open the nnancy.yaml configuration file in your editor.
    nnancy secrets         Open the secrets file (API key) in your editor.

Interactive Chat Commands (in TUI):
    /new                   Start a fresh session in this process
    /handoff               Save handoff JSON snapshot
    /handoff PATH          Load prior handoff JSON
    /copy                  Open copy mode to select and yank transcript text
    /config                Open nnancy.yaml in your editor and append changes to session
    /key                   Set or replace your API key securely
    /quit, /exit           Exit the TUI session

Attachments:
    Use @relative/path to inline file content into your prompt
"""


class MockServerInstallError(RuntimeError):
    """Raised when the test-only mock server is requested outside a repo checkout."""


def _repo_mock_server_script(workspace_root: Path) -> Path:
    script_path = workspace_root / "tests" / "mock_llm_service.py"
    if not script_path.exists():
        raise MockServerInstallError(
            "mock server is test-only and repo-local. "
            "If you're trying to use mock-server flags from a general install, "
            "please fuck off back to a repository checkout where "
            "`tests/mock_llm_service.py` actually exists.\n"
            f"missing_path: {script_path}"
        )
    return script_path


def _start_mock_server(script_path: Path, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, str(script_path), str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_mock_server(
    process: subprocess.Popen[str],
    port: int,
    timeout_seconds: float = 5.0,
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                "mock server failed to start: "
                f"returncode={process.returncode}\n"
                f"stdout:\n{stdout or '<empty>'}\n"
                f"stderr:\n{stderr or '<empty>'}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)

    process.terminate()
    stdout, stderr = process.communicate(timeout=2)
    raise RuntimeError(
        "mock server did not become ready before timeout: "
        f"port={port}\n"
        f"stdout:\n{stdout or '<empty>'}\n"
        f"stderr:\n{stderr or '<empty>'}"
    )


def _config_with_mock_server(cfg: Config, port: int) -> Config:
    return Config(
        model="mock-shakespeare",
        base_url=f"http://127.0.0.1:{port}/v1",
        api_key_env=cfg.api_key_env,
        api_key_file=cfg.api_key_file,
        user_display_name=cfg.user_display_name,
        timeout_seconds=cfg.timeout_seconds,
        max_preflight_tokens=cfg.max_preflight_tokens,
        sandbox_root=cfg.sandbox_root,
        max_attachment_bytes=cfg.max_attachment_bytes,
        execution_strategy=cfg.execution_strategy,
        native_tools=cfg.native_tools,
        reasoning_channel=cfg.reasoning_channel,
        parallel_tool_calls=cfg.parallel_tool_calls,
        capability_probe=cfg.capability_probe,
        provider="native_openai",
    )


def _parse_args(
    argv: list[str],
) -> tuple[bool, str | None, bool, str | None, int | None, str | None, str | None]:
    yolo = False
    prompt = None
    show_help = False
    command = None
    mock_port: int | None = None
    mock_prompt: str | None = None
    run_tool: str | None = None

    args = list(argv)
    if args and args[0] == "yolo":
        yolo = True
        args = args[1:]

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"instructions", "config", "secrets", "doctor"}:
            command = arg
            i += 1
        elif arg == "run":
            command = "run"
            if i + 1 >= len(args):
                raise SystemExit("run requires a tool name")
            run_tool = args[i + 1]
            i += 2
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
        elif arg in {"-m", "--mock-server"}:
            command = "mock-server"
            if i + 1 < len(args) and args[i + 1].isdigit():
                mock_port = int(args[i + 1])
                i += 2
            else:
                i += 1
        elif arg == "-tm":
            command = "test-mock"
            if i + 1 < len(args) and args[i + 1].isdigit():
                mock_port = int(args[i + 1])
                i += 1
            if i + 1 >= len(args):
                raise SystemExit("-tm requires a prompt string")
            mock_prompt = args[i + 1]
            i += 2
        elif arg == "-t":
            if i + 1 >= len(args):
                raise SystemExit("-t requires a prompt string")
            prompt = args[i + 1]
            i += 2
        else:
            raise SystemExit(f"unknown arg: {arg}")

    return yolo, prompt, show_help, command, mock_port, mock_prompt, run_tool


def main() -> None:
    # Most modern terminal emulators (including Nexus/Jupyter) support 24-bit TrueColor
    # but don't always advertise it via COLORTERM. If we don't force it, hex codes
    # get rounded to the nearest 256-color match, which often turns Nancy's purples blue.
    if not os.environ.get("COLORTERM"):
        term = os.environ.get("TERM", "")
        if "256color" in term or "truecolor" in term or "xterm" in term:
            os.environ["COLORTERM"] = "truecolor"

    yolo, single_prompt, show_help, command, mock_port, mock_prompt, run_tool = _parse_args(sys.argv[1:])
    workspace_root = Path.cwd().resolve()
    bootstrap_local_files(workspace_root)
    initialize_tools(workspace_root)

    if show_help:
        print(HELP)
        return

    def fail(exc: Exception | str) -> None:
        # Do not sanitize or paraphrase startup/request failures here. The raw
        # message is usually the only useful thing the user has.
        if isinstance(exc, Exception):
            message = f"{type(exc).__name__}: {exc}"
        else:
            message = exc
        print(f"error: {message}", file=sys.stderr, flush=True)
        raise SystemExit(1)

    if command == "run" and run_tool:
        from .tools import REGISTRY
        from .sandbox import SandboxPolicy
        from .config import load_sandbox_allowlist
        
        cfg = load_config(workspace_root)
        allowlist = load_sandbox_allowlist(workspace_root)
        sandbox_root_path = Path(cfg.sandbox_root).expanduser()
        if not sandbox_root_path.is_absolute():
            sandbox_root_path = (workspace_root / sandbox_root_path).resolve()
        else:
            sandbox_root_path = sandbox_root_path.resolve()
        sandbox = SandboxPolicy(root=sandbox_root_path, yolo=yolo, allowlist_substrings=allowlist)

        tool = REGISTRY._tools.get(run_tool)
        if not tool:
            # Also try looking up by slash command
            tool = REGISTRY.get_slash_command(f"/{run_tool}")
            if not tool:
                fail(f"unknown tool: {run_tool}")

        if not tool.handler:
            fail(f"tool {run_tool} has no handler")

        try:
            result = tool.handler(sandbox=sandbox)
            if result:
                print(result)
        except Exception as exc:
            fail(exc)
        return

    if command == "instructions":
        open_in_editor(instructions_path(workspace_root))
        return

    if command == "config":
        open_config_in_editor(workspace_root)
        return

    if command == "secrets":
        open_secrets_in_editor(workspace_root)
        return

    if command == "mock-server":
        argv_backup: list[str] | None = None
        try:
            script_path = _repo_mock_server_script(workspace_root)
            # Test-only convenience command. Run the repo-local script verbatim
            # instead of trying to hide or abstract away the test harness.
            argv_backup = sys.argv[:]
            sys.argv = [str(script_path)]
            if mock_port is not None:
                sys.argv.append(str(mock_port))
            runpy.run_path(str(script_path), run_name="__main__")
        except MockServerInstallError as exc:
            fail(exc)
        finally:
            if argv_backup is not None:
                sys.argv = argv_backup
        return

    cfg = load_config(workspace_root)

    if command == "test-mock":
        process: subprocess.Popen[str] | None = None
        port = mock_port or 8008
        try:
            script_path = _repo_mock_server_script(workspace_root)
            process = _start_mock_server(script_path, port)
            _wait_for_mock_server(process, port)
            mock_cfg = _config_with_mock_server(cfg, port)
            state, llm, sandbox = build_state(mock_cfg, yolo=yolo)
            result = run_prompt(state, llm, sandbox, mock_prompt or "")
            print(result.to_cli_text())
        except Exception as exc:
            fail(exc)
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        return

    if command == "doctor":
        try:
            report = run_doctor(cfg, workspace_root)
            print(report.render())
            raise SystemExit(0 if report.ok else 1)
        except Exception as exc:
            fail(exc)

    try:
        state, llm, sandbox = build_state(cfg, yolo=yolo)
    except Exception as exc:
        fail(exc)

    if single_prompt:
        try:
            result = run_prompt(state, llm, sandbox, single_prompt)
            print(result.to_cli_text())
        except Exception as exc:
            fail(exc)
        return

    # Textual needs a real TTY; fallback to simple input loop otherwise.
    if NancyTUI is not None and sys.stdin.isatty() and sys.stdout.isatty():
        try:
            NancyTUI(state, llm, sandbox).run()
            return
        except Exception as exc:
            fail(exc)

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
            result = run_prompt(state, llm, sandbox, text)
            print(result.to_cli_text())
        except Exception as exc:
            print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
