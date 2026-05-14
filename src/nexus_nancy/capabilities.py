from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import Config


@dataclass(frozen=True)
class ModelCapabilities:
    native_tools: bool = False
    reasoning_channel: bool = False
    parallel_tool_calls: bool = False
    source: str = "fallback"
    verified: bool = False
    detail: str = "native tool support is unknown"


class CapabilityProbeClient(Protocol):
    def probe_capabilities(self) -> dict[str, bool]: ...


def _explicit_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "on", "1"}:
            return True
        if lowered in {"false", "no", "off", "0"}:
            return False
    return None


def _optional_feature(value: object, *, default: bool = False) -> bool:
    explicit = _explicit_bool(value)
    return default if explicit is None else explicit


def detect_capabilities(
    cfg: Config,
    workspace_root: Path | None = None,
    probe_client: CapabilityProbeClient | None = None,
) -> ModelCapabilities:
    native_override = _explicit_bool(cfg.native_tools)
    if native_override is not None:
        return ModelCapabilities(
            native_tools=native_override,
            reasoning_channel=_optional_feature(cfg.reasoning_channel),
            parallel_tool_calls=_optional_feature(cfg.parallel_tool_calls),
            source="config override",
            verified=native_override,
            detail=(
                "native tool support enabled by config"
                if native_override
                else "native tool support disabled by config"
            ),
        )

    if cfg.capability_probe:
        client = probe_client
        if client is None:
            if workspace_root is None:
                raise RuntimeError("workspace_root required for live capability probe")
            from .provider import get_provider

            client = get_provider(cfg, workspace_root)

        try:
            p_caps = client.probe_capabilities()
            if p_caps.get("native_tools"):
                # If the user explicitly set a feature, use it; otherwise trust the probe.
                has_reasoning = _optional_feature(
                    cfg.reasoning_channel, default=p_caps.get("reasoning_channel", False)
                )
                return ModelCapabilities(
                    native_tools=True,
                    reasoning_channel=has_reasoning,
                    parallel_tool_calls=_optional_feature(cfg.parallel_tool_calls, default=True),
                    source="live probe",
                    verified=True,
                    detail=(
                        f"provider verified: native_tools=True, reasoning_channel={has_reasoning}"
                    ),
                )
            return ModelCapabilities(
                source="live probe",
                detail="provider did not return a native tool call during probe",
            )
        except Exception as exc:
            return ModelCapabilities(
                source="probe failure",
                detail=f"capability probe failed: {type(exc).__name__}: {exc}",
            )

    return ModelCapabilities(source="fallback", detail="capability probe disabled")


def require_native_capabilities(capabilities: ModelCapabilities) -> None:
    if capabilities.verified and capabilities.native_tools:
        return
    raise RuntimeError(
        "execution_strategy=native_openai requires verified native tool support.\n"
        f"capability_source: {capabilities.source}\n"
        f"capability_detail: {capabilities.detail}"
    )
