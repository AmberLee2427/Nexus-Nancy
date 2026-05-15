# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Nexus-Nancy is a lightweight terminal AI agent (TUI) for OpenAI-compatible endpoints. It is a single Python package (`nexus-nancy`) with a `src` layout. See `README.md` for full usage and config details.

### Dev environment

- **Python ≥3.10** required. The venv lives at `.venv/`.
- Install dev dependencies: `pip install -e ".[dev]"`
- The `nnancy` CLI entry point is registered via `pyproject.toml` `[project.scripts]`.

### Running checks

| Task | Command |
|------|---------|
| Lint | `ruff check .` |
| Format check | `ruff format --check .` |
| Tests | `PYTHONPATH=src pytest -v` |

**Note:** Pre-existing lint/format issues exist in `extras/plugins/nancy-provider-codex/src/nancy_codex/plugin.py` and `src/nexus_nancy/tui.py`. These are in the upstream code.

### Running the application

- **Mock server test (one-shot):** `nnancy -tm "your prompt"` — starts a mock LLM server, sends the prompt, prints the response, and shuts down.
- **Mock server (standalone):** `python tests/mock_llm_service.py` or `nnancy -m` — runs on `127.0.0.1:8008`.
- **Interactive TUI:** `nnancy` (requires a real TTY and a configured API key).
- **API key:** Must be set in `.agents/secrets/openai.key` or via `OPENAI_API_KEY` env var. For mock server testing, any dummy key of ≥12 chars works (e.g. `sk-mock-test-key-dummy`).

### Known gotchas

- **tiktoken requires egress to `openaipublic.blob.core.windows.net`** to download encoding data on first use. This domain is blocked in Cloud Agent VMs. Without it, `nnancy -tm` and any LLM chat path fail with an `SSLError`. Workaround: temporarily hide tiktoken from the import path (rename `tiktoken` dir in site-packages) so the built-in character-heuristic fallback in `token_count.py` is used. This does not affect `pytest` — all 16 tests pass without tiktoken data.
- The `.agents/` directory (config, keys, prompts) is auto-bootstrapped by `nnancy` on first run from the working directory.
- Tests use the mock LLM server at `tests/mock_llm_service.py`; no external API key is needed for the test suite.
