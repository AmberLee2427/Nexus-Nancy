from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .sandbox import SandboxPolicy


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in sandbox. Primary tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notebook_read",
            "description": "Read notebook cells as plain text summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_cells": {"type": "integer", "default": 20},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notebook_set_cell",
            "description": "Replace a code cell source in a notebook by index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "cell_index": {"type": "integer"},
                    "source": {"type": "string"},
                },
                "required": ["path", "cell_index", "source"],
            },
        },
    },
]


def _load_nb(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_nb(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=True), encoding="utf-8")


def notebook_read(path: Path, max_cells: int = 20) -> str:
    nb = _load_nb(path)
    cells = nb.get("cells", [])
    lines: list[str] = [f"Notebook: {path}", f"Cells: {len(cells)}"]
    for idx, c in enumerate(cells[:max_cells]):
        ctype = c.get("cell_type", "unknown")
        src = "".join(c.get("source", []))
        snippet = src.strip().replace("\n", " ")[:140]
        lines.append(f"[{idx}] {ctype}: {snippet}")
    return "\n".join(lines)


def notebook_set_cell(path: Path, cell_index: int, source: str) -> str:
    nb = _load_nb(path)
    cells = nb.get("cells", [])
    if cell_index < 0 or cell_index >= len(cells):
        return f"error: cell_index {cell_index} out of range"
    cell = cells[cell_index]
    if cell.get("cell_type") != "code":
        return f"error: cell {cell_index} is not a code cell"
    cell["source"] = [line + "\n" for line in source.splitlines()]
    _save_nb(path, nb)
    return f"updated {path} code cell {cell_index}"


def run_bash(command: str, sandbox: SandboxPolicy) -> str:
    ok, reason = sandbox.validate(command)
    if not ok:
        return f"error: {reason}"

    proc = subprocess.run(
        ["zsh", "-lc", command],
        cwd=str(sandbox.root),
        text=True,
        capture_output=True,
    )
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    return (
        f"exit_code={proc.returncode}\n"
        f"stdout:\n{out if out else '<empty>'}\n"
        f"stderr:\n{err if err else '<empty>'}"
    )


def execute_tool(name: str, args: dict[str, Any], sandbox: SandboxPolicy) -> str:
    if name == "bash":
        return run_bash(args.get("command", ""), sandbox)

    if name == "notebook_read":
        return notebook_read(sandbox.root / args["path"], int(args.get("max_cells", 20)))

    if name == "notebook_set_cell":
        return notebook_set_cell(
            sandbox.root / args["path"],
            int(args["cell_index"]),
            str(args["source"]),
        )

    return f"error: unknown tool '{name}'"
