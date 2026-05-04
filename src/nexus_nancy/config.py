from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass
class Config:
    model: str = "gpt-5.4-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    api_key_file: str = ".agents/secrets/openai.key"
    user_display_name: str = "USER"
    timeout_seconds: int = 120
    max_preflight_tokens: int = 120000
    sandbox_root: str = "."
    max_attachment_bytes: int = 120000
    execution_strategy: str = "auto"
    native_tools: bool | str = "auto"
    reasoning_channel: bool | str = "auto"
    parallel_tool_calls: bool | str = "auto"
    capability_probe: bool = True


def agents_dir(workspace_root: Path) -> Path:
    return workspace_root / ".agents"


def config_path(workspace_root: Path) -> Path:
    return agents_dir(workspace_root) / "nnancy.yaml"


def instructions_path(workspace_root: Path) -> Path:
    return agents_dir(workspace_root) / "instructions.txt"


def sandbox_allowlist_path(workspace_root: Path) -> Path:
    return agents_dir(workspace_root) / "sandbox_allowlist.txt"


def relay_instructions_path(workspace_root: Path) -> Path:
    return agents_dir(workspace_root) / "relay_instructions.txt"


def handoff_instructions_path(workspace_root: Path) -> Path:
    return agents_dir(workspace_root) / "hand-off_instructions.txt"


def default_config_yaml() -> str:
    return """model: gpt-5.4-mini
base_url: https://api.openai.com/v1
api_key_env: OPENAI_API_KEY
api_key_file: .agents/secrets/openai.key
user_display_name: USER
timeout_seconds: 120
max_preflight_tokens: 120000
sandbox_root: .
max_attachment_bytes: 120000
execution_strategy: auto
native_tools: auto
reasoning_channel: auto
parallel_tool_calls: auto
capability_probe: true
"""


def bootstrap_local_files(workspace_root: Path) -> None:
    a_dir = agents_dir(workspace_root)
    a_dir.mkdir(parents=True, exist_ok=True)

    cfg = config_path(workspace_root)
    if not cfg.exists():
        cfg.write_text(default_config_yaml(), encoding="utf-8")

    # Prompt templates ship inside the installed package and are copied into the
    # user's working directory on first run. We do not invent fallback prompt
    # text at runtime.
    _copy_bundled_agent_template_if_missing("instructions.txt", instructions_path(workspace_root))
    _copy_bundled_agent_template_if_missing(
        "relay_instructions.txt", relay_instructions_path(workspace_root)
    )
    _copy_bundled_agent_template_if_missing(
        "hand-off_instructions.txt", handoff_instructions_path(workspace_root)
    )

    allowlist = sandbox_allowlist_path(workspace_root)
    if not allowlist.exists():
        allowlist.write_text(
            "# One substring per line. If matched in command, "
            "sandbox substring blocks are skipped.\n",
            encoding="utf-8",
        )

    secrets_dir = agents_dir(workspace_root) / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)

    transcripts_dir = agents_dir(workspace_root) / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)


def _copy_bundled_agent_template_if_missing(template_name: str, destination: Path) -> None:
    if destination.exists():
        return
    destination.write_text(_bundled_agent_template_text(template_name), encoding="utf-8")


def _bundled_agent_template_text(template_name: str) -> str:
    packaged = resources.files("nexus_nancy").joinpath("default_agents").joinpath(template_name)
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")

    repo_source = Path(__file__).resolve().parents[2] / ".agents" / template_name
    if repo_source.exists():
        return repo_source.read_text(encoding="utf-8")

    raise RuntimeError(
        "Missing bundled agent template.\n"
        f"template_name: {template_name}\n"
        f"packaged_path: {packaged}\n"
        f"repo_fallback_path: {repo_source}"
    )


def load_config(workspace_root: Path) -> Config:
    bootstrap_local_files(workspace_root)
    path = config_path(workspace_root)
    raw = _parse_flat_yaml(path.read_text(encoding="utf-8"))

    cfg = Config()
    for key, val in raw.items():
        if hasattr(cfg, key):
            setattr(cfg, key, val)
    _resolve_config_paths(cfg, workspace_root)
    return cfg


def _parse_flat_yaml(text: str) -> dict[str, object]:
    data: dict[str, object] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.lower() in {"true", "false"}:
            data[key] = value.lower() == "true"
            continue
        if value.isdigit():
            data[key] = int(value)
            continue
        data[key] = value
    return data


def _resolve_config_path_value(workspace_root: Path, value: str) -> str:
    raw = _unquote(value.strip())
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (workspace_root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return str(candidate)


def _resolve_config_paths(cfg: Config, workspace_root: Path) -> None:
    # Normalize path-like config values at load time so every downstream caller
    # sees real absolute paths instead of ambiguous workspace-relative shorthands.
    cfg.api_key_file = _resolve_config_path_value(workspace_root, str(cfg.api_key_file))
    cfg.sandbox_root = _resolve_config_path_value(workspace_root, str(cfg.sandbox_root))


def load_instructions(workspace_root: Path) -> str:
    bootstrap_local_files(workspace_root)
    path = instructions_path(workspace_root)
    if not path.exists():
        raise RuntimeError(
            "Missing system prompt file. Refusing to invent one.\n"
            f"expected_path: {path}"
        )
    # Instructions are loaded verbatim from the workspace. This project does
    # not try to hide the prompt or launder it into something safer-looking.
    return path.read_text(encoding="utf-8").strip()


def render_prompt_template(template: str, variables: dict[str, str]) -> str:
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def load_sandbox_allowlist(workspace_root: Path) -> list[str]:
    bootstrap_local_files(workspace_root)
    path = sandbox_allowlist_path(workspace_root)
    items: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        items.append(stripped)
    return items


def resolve_api_key(cfg: Config, workspace_root: Path) -> tuple[str | None, str]:
    key_file = api_key_path(cfg, workspace_root)
    if key_file.exists() and key_file.is_file():
        key = key_file.read_text(encoding="utf-8").strip()
        if key:
            return key, f"file:{key_file}"

    env_key = os.environ.get(cfg.api_key_env)
    if env_key:
        return env_key, f"env:{cfg.api_key_env}"

    return None, "missing"


def open_in_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR", "").strip()
    if editor:
        cmd = shlex.split(editor) + [str(path)]
        subprocess.run(cmd, check=True)
        return

    if sys.platform == "darwin":
        subprocess.run(["open", "-e", str(path)], check=True)
        return

    subprocess.run(["nano", str(path)], check=True)


def open_config_in_editor(workspace_root: Path) -> Path:
    path = config_path(workspace_root)
    open_in_editor(path)
    _normalize_config_paths_on_save(path, workspace_root)
    return path


def _normalize_config_paths_on_save(path: Path, workspace_root: Path) -> None:
    text = path.read_text(encoding="utf-8")
    raw = _parse_flat_yaml(text)

    updates: dict[str, str] = {}
    api_key_file = str(raw.get("api_key_file", "")).strip()
    sandbox_root = str(raw.get("sandbox_root", "")).strip()

    if api_key_file:
        updates["api_key_file"] = str(
            (workspace_root / _unquote(api_key_file)).expanduser().resolve()
        )
    if sandbox_root:
        updates["sandbox_root"] = str(
            (workspace_root / _unquote(sandbox_root)).expanduser().resolve()
        )

    if not updates:
        return

    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        before, _, _ = line.partition(":")
        key = before.strip()
        if key not in updates:
            continue
        indent = before[: len(before) - len(before.lstrip())]
        lines[idx] = f"{indent}{key}: {updates[key]}"

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def api_key_path(cfg: Config, workspace_root: Path) -> Path:
    return (workspace_root / cfg.api_key_file).resolve()


def replace_api_key(cfg: Config, workspace_root: Path, new_key: str) -> Path:
    key = new_key.strip()
    if not key:
        raise RuntimeError("key cannot be empty")

    key_file = api_key_path(cfg, workspace_root)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    # Secrets are stored as plain local files by design. We do permissions
    # hygiene, but we do not pretend this is anything other than a file write.
    key_file.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        # Best effort on non-POSIX filesystems.
        pass
    return key_file
