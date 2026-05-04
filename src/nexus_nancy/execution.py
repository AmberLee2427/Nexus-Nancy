from __future__ import annotations

from dataclasses import dataclass

from .capabilities import ModelCapabilities, require_native_capabilities
from .config import Config

STRATEGY_AUTO = "auto"
STRATEGY_NATIVE_OPENAI = "native_openai"
STRATEGY_UNIVERSAL = "universal"


@dataclass(frozen=True)
class ExecutionSelection:
    requested: str
    selected: str
    capabilities: ModelCapabilities


def select_execution_strategy(cfg: Config, capabilities: ModelCapabilities) -> ExecutionSelection:
    requested = str(cfg.execution_strategy).strip().lower()
    if requested not in {STRATEGY_AUTO, STRATEGY_NATIVE_OPENAI, STRATEGY_UNIVERSAL}:
        raise RuntimeError(
            "Invalid execution_strategy. Expected one of: auto, native_openai, universal.\n"
            f"got: {cfg.execution_strategy!r}"
        )

    if requested == STRATEGY_UNIVERSAL:
        selected = STRATEGY_UNIVERSAL
    elif requested == STRATEGY_NATIVE_OPENAI:
        require_native_capabilities(capabilities)
        selected = STRATEGY_NATIVE_OPENAI
    elif capabilities.verified and capabilities.native_tools:
        selected = STRATEGY_NATIVE_OPENAI
    else:
        selected = STRATEGY_UNIVERSAL

    return ExecutionSelection(
        requested=requested,
        selected=selected,
        capabilities=capabilities,
    )
