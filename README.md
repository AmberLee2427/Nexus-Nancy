# Nexus-Nancy

Nexus-Nancy is a seriously lightweight, pip-installable terminal agent focused on OpenAI-style API compatibility and local tool execution.

## Design goals

- Minimal TUI and command surface
- Single provider protocol: OpenAI-compatible `/chat/completions`
- Primary tool: shell (`bash`) with sandbox defaults
- Notebook-aware local tools for `.ipynb` read/edit workflows
- Context controls: `/new` and `/handoff`
- Plain-text session logs
- Attachment shorthand: `@path/to/file`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configure

On first run in any directory, Nexus-Nancy creates local files in `.agents/`:

- `.agents/nnancy.yaml`
- `.agents/instructions.txt`
- `.agents/sandbox_allowlist.txt`

API key resolution order:

1. local key file from `api_key_file` (default `.agents/secrets/openai.key`)
2. env var from `api_key_env` (default `OPENAI_API_KEY`)

For shared environments, using the local key file is recommended.

Before any provider call, Nexus-Nancy runs strict preflight validation: API key/base URL sanity, required message structure (system + user), tool spec integrity (including `bash`), and request-size guard via `max_preflight_tokens`.

Set `user_display_name` in `.agents/nnancy.yaml` to control the user label shown in the TUI transcript (default: `USER`).

Edit these with:

```bash
nnancy config
nnancy instructions
```

## Usage

```bash
nnancy
nnancy -t "summarize @README.md"
nnancy doctor
nnancy config
nnancy instructions
```

`nnancy doctor` checks workspace bootstrap files, sandbox root, API key source, key-file permissions, and base URL health via `<base_url>/models`.

`sandbox_allowlist.txt` supports one substring per line. If a substring appears in a command, substring-based sandbox blocks are bypassed for that command.

Interactive mode uses a Python Textual TUI when running in a real terminal. If TTY support is missing (for example some notebook terminal environments), it automatically falls back to a plain line-input mode.

The TUI status line shows model, mode (`sandbox`/`yolo`), current working directory, and approximate context token count.
Each TUI session gets an `id` shown in that status line.

Transcripts are always saved for posterity at:

- `.agents/tracsripts/<id>.txt`

Use `Ctrl+Y` in TUI to show copy mode info with the current transcript path.
`Ctrl+Y` suspends the TUI and opens the transcript in your terminal (`less` if available, else `cat`) so native terminal text selection/copy works, then returns to the app.

Default model is `gpt-5.4-mini`. Context token estimate uses `tiktoken` when available and falls back to a simple character heuristic otherwise.

Inside the prompt:

- `/new` starts a fresh in-process context
- `/handoff` writes a JSON continuation snapshot to `logs/handoff.json`
- `/handoff path/to/handoff.json` loads prior context
- `@relative/path` inlines file content into your prompt

## Notes

- Tool execution is local.
- Sandbox mode is default.
- Chat logs are written to `logs/session-*.log`.
- `nnancy yolo` exists but is intentionally not advertised in help output.
