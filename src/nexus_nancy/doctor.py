from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path

import httpx

from .capabilities import detect_capabilities
from .config import (
    Config,
    config_path,
    handoff_instructions_path,
    instructions_path,
    relay_instructions_path,
    resolve_api_key,
    sandbox_allowlist_path,
)
from .execution import select_execution_strategy
from .llm import LLMClient
from .tools import TOOL_SPECS


@dataclass
class DoctorReport:
    ok: bool
    lines: list[str]

    def render(self) -> str:
        # Doctor output is meant to be copied into terminals/issues verbatim.
        # Keep the fielded lines blunt and complete rather than "friendly."
        return "\n".join(self.lines)


def _fmt_status(ok: bool) -> str:
    return "OK" if ok else "FAIL"


def _masked_key(key: str | None) -> str:
    if not key:
        return "missing"
    if len(key) <= 8:
        return "present"
    return f"{key[:4]}...{key[-4:]}"


def run_doctor(cfg: Config, workspace_root: Path) -> DoctorReport:
    lines: list[str] = []
    failures = 0

    cfg_path = config_path(workspace_root)
    instr_path = instructions_path(workspace_root)
    relay_path = relay_instructions_path(workspace_root)
    handoff_path = handoff_instructions_path(workspace_root)

    checks: list[tuple[str, bool, str]] = []
    checks.append(("workspace", workspace_root.exists(), str(workspace_root)))
    checks.append(("config_file", cfg_path.exists(), str(cfg_path)))
    checks.append(("instructions_file", instr_path.exists(), str(instr_path)))
    checks.append(("relay_instructions_file", relay_path.exists(), str(relay_path)))
    checks.append(("handoff_instructions_file", handoff_path.exists(), str(handoff_path)))

    key, key_source = resolve_api_key(cfg, workspace_root)
    checks.append(("api_key", bool(key), f"source={key_source}; value={_masked_key(key)}"))

    allowlist = sandbox_allowlist_path(workspace_root)
    checks.append(("sandbox_allowlist", allowlist.exists(), str(allowlist)))

    key_file = (workspace_root / cfg.api_key_file).resolve()
    if key_source.startswith("file:") and key_file.exists():
        mode = stat.S_IMODE(key_file.stat().st_mode)
        perms_ok = (mode & 0o077) == 0
        checks.append(("api_key_file_perms", perms_ok, f"{key_file} mode={oct(mode)}"))

    sandbox_root = (workspace_root / cfg.sandbox_root).resolve()
    checks.append(("sandbox_root", sandbox_root.exists(), str(sandbox_root)))

    capabilities = detect_capabilities(cfg, workspace_root)
    route_ok = True
    try:
        selection = select_execution_strategy(cfg, capabilities)
        route_info = (
            f"requested={selection.requested}; selected={selection.selected}; "
            f"capability_source={capabilities.source}; verified={capabilities.verified}; "
            f"native_tools={capabilities.native_tools}; "
            f"reasoning_channel={capabilities.reasoning_channel}; "
            f"parallel_tool_calls={capabilities.parallel_tool_calls}; "
            f"detail={capabilities.detail}"
        )
    except Exception as exc:
        route_ok = False
        route_info = str(exc)
    checks.append(("execution_route", route_ok, route_info))

    # URL health check: /models typically exists on OpenAI-compatible servers.
    base = cfg.base_url.rstrip("/")
    models_url = f"{base}/models"
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    url_ok = False
    url_info = "not checked"
    try:
        with httpx.Client(timeout=min(cfg.timeout_seconds, 20)) as client:
            resp = client.get(models_url, headers=headers)
        # 200 indicates ready; 401/403 still proves endpoint reachability.
        url_ok = resp.status_code in {200, 401, 403}
        url_info = f"{models_url} -> HTTP {resp.status_code}"
    except Exception as exc:  # pragma: no cover
        url_ok = False
        # Preserve the raw exception text. Doctor is diagnostic output, not UX.
        url_info = f"{models_url} -> error: {exc}"
    checks.append(("base_url_health", url_ok, url_info))

    # Preflight payload validation check (no network call).
    preflight_ok = False
    preflight_info = "not checked"
    try:
        client = LLMClient(cfg, workspace_root)
        test_messages = [
            {"role": "system", "content": "doctor preflight system"},
            {"role": "user", "content": "doctor preflight user"},
        ]
        client._validate_request(test_messages, TOOL_SPECS)
        preflight_ok = True
        preflight_info = (
            "payload validator passed "
            f"(tools={len(TOOL_SPECS)}, max_preflight_tokens={cfg.max_preflight_tokens})"
        )
    except Exception as exc:  # pragma: no cover
        preflight_ok = False
        # Preflight failures should surface the exact message that blocked the
        # request so users can act on it directly.
        preflight_info = str(exc)
    checks.append(("request_preflight", preflight_ok, preflight_info))

    lines.append("Nexus-Nancy doctor")
    lines.append("")
    lines.append(f"model: {cfg.model}")
    lines.append(f"base_url: {cfg.base_url}")
    lines.append(f"execution_strategy: {cfg.execution_strategy}")
    lines.append("")

    for name, ok, info in checks:
        lines.append(f"[{_fmt_status(ok)}] {name}: {info}")
        if not ok:
            failures += 1

    ok = failures == 0
    lines.append("")
    lines.append(f"overall: {_fmt_status(ok)}")
    return DoctorReport(ok=ok, lines=lines)
