from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import Config


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        tool_choice: Any | None = None,
        parallel_tool_calls: bool | None = None,
        response_format: dict[str, Any] | None = None,
        extra_body: dict[str, Any] | None = None,
        require_bash_tool: bool = True,
    ) -> dict[str, Any]:
        """Send a request to the LLM and return a standard OpenAI-compatible response dict."""
        pass

    @abstractmethod
    def probe_capabilities(self) -> dict[str, bool]:
        """Return a dict indicating supported capabilities.
        (e.g., native_tools, reasoning_channel).
        """
        pass


PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {}


def register_providers() -> None:
    """Discover and register LLM providers from entry points."""
    # 1. Register built-in providers
    from .llm import NativeOpenAIProvider

    PROVIDER_REGISTRY["native_openai"] = NativeOpenAIProvider

    # 2. Load from entry points
    try:
        eps = metadata.entry_points(group="nexus_nancy.providers")
        for ep in eps:
            try:
                provider_cls = ep.load()
                if isinstance(provider_cls, type) and issubclass(provider_cls, LLMProvider):
                    PROVIDER_REGISTRY[ep.name] = provider_cls
            except Exception as exc:
                print(
                    f"warning: failed to load provider entry point {ep.name}: {exc}",
                    file=sys.stderr,
                )
    except Exception as exc:
        # metadata.entry_points can fail in some environments; report it.
        print(f"warning: failed to list provider entry points: {type(exc).__name__}: {exc}", file=sys.stderr)


def get_provider_class(name: str) -> type[LLMProvider]:
    """Get a provider class by name, registering if necessary."""
    if not PROVIDER_REGISTRY:
        register_providers()

    if name not in PROVIDER_REGISTRY:
        raise RuntimeError(f"Unknown provider: {name}. Available: {list(PROVIDER_REGISTRY.keys())}")

    return PROVIDER_REGISTRY[name]


def get_provider(cfg: Config, workspace_root: Path) -> LLMProvider:
    """Initialize the correct provider based on configuration."""
    provider_class = get_provider_class(cfg.provider)
    return provider_class(cfg, workspace_root)
