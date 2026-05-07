# Implementation Plan: Pluggable LLM Providers

This document outlines the architectural refactor to transition Nexus-Nancy from a hardcoded LLM client to a pluggable provider system. This allows the core to remain a pristine, standard OpenAI-compatible client while delegating "hacky" implementations (like the Codex backend API spoofing) or alternative models (Gemini, Anthropic) to external plugins.

## Phase 1: Define the Provider Interface

Create a new file `src/nexus_nancy/provider.py` to define the base interface that all LLM providers must implement.

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

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
```

## Phase 2: Refactor Core to `NativeOpenAIProvider`

Modify the existing `src/nexus_nancy/llm.py`. 
1. Rename `LLMClient` to `NativeOpenAIProvider`.
2. Make it inherit from `LLMProvider`.
3. Strip out **all** Codex-specific authentication and header injection logic (remove `auth_type`, `OpenAI-Organization`, `OpenAI-Account` headers).
4. It should only read the standard `api_key` and forward payloads to the configured `base_url`.

## Phase 3: Update Configuration

Modify `src/nexus_nancy/config.py`:
1. Add a `provider: str = "native_openai"` field to the `Config` dataclass.
2. Remove the `auth_type` and `codex_session_file` fields entirely.
3. Update `default_config_yaml()` to reflect these changes.

## Phase 4: Build the Plugin Registry for Providers

Modify how extensions are loaded (likely in `src/nexus_nancy/tools.py` or a new `plugin.py`).
1. Currently, plugins export `register_tools()`. 
2. Add support for plugins to also export `register_providers() -> Dict[str, Type[LLMProvider]]`.
3. Create a global `PROVIDER_REGISTRY` dict. Add the built-in `NativeOpenAIProvider` to it under the name `"native_openai"`.
4. Iterate over discovered entry points and populate the registry with external providers.

## Phase 5: The Factory Method

Create a factory function in `provider.py` (or similar) that initializes the correct provider based on the configuration:

```python
def get_provider(cfg: Config, workspace_root: Path) -> LLMProvider:
    provider_class = PROVIDER_REGISTRY.get(cfg.provider)
    if not provider_class:
        raise RuntimeError(f"Unknown LLM provider requested: {cfg.provider}")
    return provider_class(cfg, workspace_root)
```

## Phase 6: Update Consumers

1. **`app.py` & `cli.py` & `tui.py`:** Replace instantiations of `LLMClient(cfg, workspace_root)` with `get_provider(cfg, workspace_root)`. Ensure they treat the returned object exactly as they did before, as the interface remains identical.
2. **`doctor.py`:** Update the health checks. Remove the hardcoded Codex auth check. The doctor should probably ask the instantiated provider if it is healthy, or fall back to checking the standard `api_key` if it's the `native_openai` provider.

## Phase 7: Purge the Hack

1. Delete `src/nexus_nancy/auth.py` completely.
2. Remove any CLI commands related to `auth login` from `cli.py`.

## Phase 8: (External) Build the Codex Plugin

The user will use the existing `nancy-plugin-template` cookiecutter to create a completely separate package (e.g., `nancy-provider-codex`).

This external plugin will:
1. Handle the 2-step OAuth login flow (if necessary) or provide CLI commands to set it up.
2. Implement an `LLMProvider` that routes traffic to `https://chatgpt.com/backend-api/codex/responses`.
3. Inject the necessary spoofed headers (`Copilot-Integration-Id`, etc.).
4. Parse the non-standard Server-Sent Events stream and re-package it into a clean OpenAI-compatible dictionary before returning it to Nancy.
5. Export it via `register_providers() { return {"codex": CodexProvider} }`.

Once installed via pip, the user simply sets `provider: codex` in their `nnancy.yaml`, and the plugin takes over the networking seamlessly.