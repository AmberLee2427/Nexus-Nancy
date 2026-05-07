from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

if TYPE_CHECKING:
    from .config import Config


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        *,
        tool_choice: Optional[Any] = None,
        parallel_tool_calls: Optional[bool] = None,
        response_format: Optional[Dict[str, Any]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        require_bash_tool: bool = True,
    ) -> Dict[str, Any]:
        """Send a request to the LLM and return a standard OpenAI-compatible response dict."""
        pass

    @abstractmethod
    def probe_capabilities(self) -> Dict[str, bool]:
        """Return a dict indicating supported capabilities (e.g., native_tools, reasoning_channel)."""
        pass


PROVIDER_REGISTRY: Dict[str, Type[LLMProvider]] = {}


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
                print(f"warning: failed to load provider entry point {ep.name}: {exc}", file=sys.stderr)
    except Exception:
        # metadata.entry_points can fail in some environments; ignore.
        pass


def get_provider_class(name: str) -> Type[LLMProvider]:
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
