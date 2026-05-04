# Changelog

## [1.0.0] - 2026-05-04

### Added
- **Native OpenAI Route**: Full support for models with native tool-calling and reasoning channels (e.g., Gemma 4).
- **ChatGPT Plus OAuth (Codex)**: New `nnancy auth login` command to authenticate via $20/mo subscription.
- **Dynamic Plugin System**: Discover tools from `.agents/tools/*.py` or installed Python entry points.
- **System Doctor**: Real-time diagnostic check for LLM health, API keys, and model capabilities.
- **Transparent Reasoning**: Internal model chain-of-thought is now preserved and visible in the TUI/transcripts.
- **Reliability Parser**: Safety net to catch JSON tool calls even when models fail to emit formal metadata.

### Changed
- **Config Refactor**: Support for `auth_type`, `execution_strategy`, and granular model capability overrides.
- **TUI Update**: Informative startup diagnostics and collapsible health snapshot.
- **Documentation**: New guides for Models & Auth and Plugins.

### Fixed
- Improved API key resolution and path normalization.
- Enhanced notebook editing reliability.
