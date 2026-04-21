from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shlex
import subprocess
import sys


DEFAULT_SYSTEM_PROMPT = (
    "You are Nexus-Nancy, a lightweight terminal coding assistant. "
    "Be concise, deterministic, and practical. Use tools only when needed."
)


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


def agents_dir(workspace_root: Path) -> Path:
    return workspace_root / ".agents"


def config_path(workspace_root: Path) -> Path:
    return agents_dir(workspace_root) / "nnancy.yaml"


def instructions_path(workspace_root: Path) -> Path:
    return agents_dir(workspace_root) / "instructions.txt"


def sandbox_allowlist_path(workspace_root: Path) -> Path:
    return agents_dir(workspace_root) / "sandbox_allowlist.txt"


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
"""


def bootstrap_local_files(workspace_root: Path) -> None:
    a_dir = agents_dir(workspace_root)
    a_dir.mkdir(parents=True, exist_ok=True)

    cfg = config_path(workspace_root)
    if not cfg.exists():
        cfg.write_text(default_config_yaml(), encoding="utf-8")

    instr = instructions_path(workspace_root)
    if not instr.exists():
        instr.write_text(DEFAULT_SYSTEM_PROMPT + "\n", encoding="utf-8")

    allowlist = sandbox_allowlist_path(workspace_root)
    if not allowlist.exists():
        allowlist.write_text(
            "# One substring per line. If matched in command, sandbox substring blocks are skipped.\n",
            encoding="utf-8",
        )

    secrets_dir = agents_dir(workspace_root) / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)

    tracsripts_dir = agents_dir(workspace_root) / "tracsripts"
    tracsripts_dir.mkdir(parents=True, exist_ok=True)


def load_config(workspace_root: Path) -> Config:
    bootstrap_local_files(workspace_root)
    path = config_path(workspace_root)
    raw = _parse_flat_yaml(path.read_text(encoding="utf-8"))

    cfg = Config()
    for key, val in raw.items():
        if hasattr(cfg, key):
            setattr(cfg, key, val)
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


def load_instructions(workspace_root: Path) -> str:
    bootstrap_local_files(workspace_root)
    return instructions_path(workspace_root).read_text(encoding="utf-8").strip()


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


def api_key_path(cfg: Config, workspace_root: Path) -> Path:
    return (workspace_root / cfg.api_key_file).resolve()


def replace_api_key(cfg: Config, workspace_root: Path, new_key: str) -> Path:
    key = new_key.strip()
    if not key:
        raise RuntimeError("key cannot be empty")

    key_file = api_key_path(cfg, workspace_root)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        # Best effort on non-POSIX filesystems.
        pass
    return key_file
