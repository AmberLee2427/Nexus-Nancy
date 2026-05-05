from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .sandbox import SandboxPolicy


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    # The actual implementation function.
    # Must accept (**args, sandbox=SandboxPolicy).
    handler: Any = None

    def __post_init__(self):
        if self.handler is None:
            # Core tools are handled in the legacy execute_tool loop for now,
            # but plugins must provide a handler.
            pass

    def to_openai_spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@runtime_checkable
class NancyPlugin(Protocol):
    def register_tools(self) -> list[ToolDefinition]: ...


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._load_core_tools()

    def _load_core_tools(self):
        core = [
            ToolDefinition(
                name="bash",
                description="Run a shell command with zsh -lc (or bash -lc) in the local sandbox.",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute locally.",
                        },
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                name="notebook_read",
                description="Read notebook cells and return a plain text summary.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Workspace-relative path to the notebook.",
                        },
                        "max_cells": {
                            "type": "integer",
                            "description": "Maximum number of cells to summarize.",
                            "default": 20,
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                name="notebook_set_cell",
                description="Replace the source of a code cell in a notebook by index.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Workspace-relative path to the notebook.",
                        },
                        "cell_index": {
                            "type": "integer",
                            "description": "Zero-based index of the code cell to replace.",
                        },
                        "source": {
                            "type": "string",
                            "description": "Full replacement source code for the target cell.",
                        },
                    },
                    "required": ["path", "cell_index", "source"],
                    "additionalProperties": False,
                },
            ),
        ]
        for t in core:
            self.register(t)

    def register(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def load_plugins(self, workspace_root: Path):
        # 1. Option A: Entry Points (Installed pip packages)
        self._load_entry_points()
        # 2. Option B: Local Scripts (.agents/tools/*.py)
        self._load_local_tools(workspace_root)

    def _load_entry_points(self):
        try:
            eps = metadata.entry_points(group="nexus_nancy.plugins")
            for ep in eps:
                try:
                    plugin = ep.load()
                    if hasattr(plugin, "register_tools"):
                        for tool in plugin.register_tools():
                            self.register(tool)
                except Exception as exc:
                    print(f"warning: failed to load entry point {ep.name}: {exc}", file=sys.stderr)
        except Exception:
            # metadata.entry_points can fail in some environments; ignore.
            pass

    def _load_local_tools(self, workspace_root: Path):
        tools_dir = workspace_root / ".agents" / "tools"
        if not tools_dir.exists() or not tools_dir.is_dir():
            return

        for path in tools_dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            try:
                module_name = f"nexus_nancy.dynamic.{path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "register_tools"):
                        for tool in module.register_tools():
                            self.register(tool)
            except Exception as exc:
                print(f"warning: failed to load local tool {path.name}: {exc}", file=sys.stderr)

    @property
    def specs(self) -> list[dict[str, Any]]:
        return [t.to_openai_spec() for t in self._tools.values()]

    @property
    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)


# Global registry instance
REGISTRY = ToolRegistry()

# Legacy compatibility exports (will be populated during startup)
TOOL_SPECS: list[dict[str, Any]] = []
TOOL_DEFINITION_MAP: dict[str, ToolDefinition] = {}


def initialize_tools(workspace_root: Path):
    global TOOL_SPECS, TOOL_DEFINITION_MAP
    REGISTRY.load_plugins(workspace_root)
    TOOL_SPECS[:] = REGISTRY.specs
    TOOL_DEFINITION_MAP.clear()
    TOOL_DEFINITION_MAP.update({t.name: t for t in REGISTRY.definitions})


def _load_nb(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_nb(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=True), encoding="utf-8")


def _resolve_workspace_path(root: Path, raw_path: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("path must be a non-empty string")

    candidate = (root / raw_path).resolve()
    if root not in [candidate, *candidate.parents]:
        raise ValueError(f"path escapes sandbox root: {raw_path}")
    return candidate


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
        # Keep tool failures short but exact. The numeric index matters.
        return f"error: cell_index {cell_index} out of range"
    cell = cells[cell_index]
    if cell.get("cell_type") != "code":
        return f"error: cell {cell_index} is not a code cell"
    cell["source"] = [line + "\n" for line in source.splitlines()]
    _save_nb(path, nb)
    return f"updated {path} code cell {cell_index}"


def run_bash(command: str, sandbox: SandboxPolicy) -> str:
    import shutil

    ok, reason = sandbox.validate(command)
    if not ok:
        # Surface the sandbox reason directly. Users need the actual block
        # predicate, not a generic refusal.
        return f"error: {reason}"

    shell_cmd = "zsh" if shutil.which("zsh") else "bash"
    proc = subprocess.run(
        [shell_cmd, "-lc", command],
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


def render_tools_block() -> str:
    lines = [
        "Tool calls must use valid JSON arguments that match the schema exactly.",
        "Missing required keys, wrong types, or unknown keys are rejected locally.",
        "",
    ]
    for tool in REGISTRY.definitions:
        schema = tool.parameters
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        lines.append(f"- {tool.name}")
        lines.append(f"  Description: {tool.description}")
        lines.append("  Arguments:")
        for key, spec in props.items():
            type_name = spec.get("type", "any")
            required_label = "required" if key in required else "optional"
            default = spec.get("default")
            default_text = f"; default={default!r}" if default is not None else ""
            desc = spec.get("description", "").strip()
            description = desc or "No description."
            lines.append(
                f"    - {key} ({type_name}, {required_label}{default_text}): {description}"
            )
    return "\n".join(lines)


def validate_tool_arguments(name: str, args: Any) -> tuple[dict[str, Any] | None, str | None]:
    tool = REGISTRY.get(name)
    if tool is None:
        return None, f"unknown tool '{name}'"
    if not isinstance(args, dict):
        return None, "tool arguments must decode to a JSON object"

    schema = tool.parameters
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    allow_extra = bool(schema.get("additionalProperties", True))

    normalized: dict[str, Any] = {}
    for key in args:
        if key not in properties and not allow_extra:
            return None, f"unexpected argument '{key}' for tool '{name}'"

    for key, spec in properties.items():
        if key not in args:
            if key in required:
                return None, f"missing required argument '{key}' for tool '{name}'"
            if "default" in spec:
                normalized[key] = spec["default"]
            continue

        value = args[key]
        expected = spec.get("type")
        if expected == "string":
            if not isinstance(value, str):
                return None, f"argument '{key}' for tool '{name}' must be a string"
        elif expected == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                return None, f"argument '{key}' for tool '{name}' must be an integer"
        normalized[key] = value

    if allow_extra:
        for key, value in args.items():
            if key not in normalized:
                normalized[key] = value

    return normalized, None


def execute_tool(name: str, args: dict[str, Any], sandbox: SandboxPolicy) -> str:
    normalized_args, error = validate_tool_arguments(name, args)
    if error:
        return f"error: {error}"
    assert normalized_args is not None

    tool = REGISTRY.get(name)
    if tool and tool.handler:
        try:
            return str(tool.handler(**normalized_args, sandbox=sandbox))
        except Exception as exc:
            return f"error: {exc}"

    if name == "bash":
        return run_bash(normalized_args["command"], sandbox)

    if name == "notebook_read":
        path = _resolve_workspace_path(sandbox.root, normalized_args["path"])
        if not path.exists() or not path.is_file():
            return f"error: notebook not found: {normalized_args['path']}"
        return notebook_read(path, int(normalized_args["max_cells"]))

    if name == "notebook_set_cell":
        path = _resolve_workspace_path(sandbox.root, normalized_args["path"])
        if not path.exists() or not path.is_file():
            return f"error: notebook not found: {normalized_args['path']}"
        return notebook_set_cell(
            path,
            int(normalized_args["cell_index"]),
            str(normalized_args["source"]),
        )

    # Unknown tool names should stay explicit in logs/transcripts because they
    # indicate a prompt/runtime mismatch.
    return f"error: unknown tool '{name}'"
