# Changelog

## [1.1.0] - 2026-05-04

### Added
- [Add new features here]

### Changed
- [Add changes here]

### Fixed
- [Add bug fixes here]

### Security
- [Add security fixes here]


## [1.0.4] - 2026-05-04

### Added
- [Add new features here]

### Changed
- [Add changes here]

### Fixed
- [Add bug fixes here]

### Security
- [Add security fixes here]


## [1.0.3] - 2026-05-04

### Changed
- Removed test-only `mock` server flags (`-m`, `-tm`) from the public CLI help text. These flags were only meant for internal repository testing and shouldn't clutter the user-facing documentation.


## [1.0.2] - 2026-05-04

### Changed
- Expanded CLI help text to comprehensively list all available interactive chat commands (`/copy`, `/config`, `/key`, `/quit`, etc.).

### Fixed
- Fixed a 404 error during `nnancy auth login` caused by an incorrect OpenAI Auth0 domain (`auth0.openai.com` -> `auth.openai.com`).


## [1.0.1] - 2026-05-04

### Fixed
- Fixed a bug where the `bash` tool would crash with a `FileNotFoundError` on CI environments (like Ubuntu GitHub Actions runners) that don't have `zsh` installed by default. It now falls back gracefully to `bash`.

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
