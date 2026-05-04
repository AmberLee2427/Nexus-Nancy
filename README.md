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
- `.agents/sandbox_allowlist.txt`
- `.agents/instructions.txt`
- `.agents/relay_instructions.txt`
- `.agents/hand-off_instructions.txt`

The prompt templates are bundled inside the installed package and copied into the working directory on first run. Nexus-Nancy does not invent ad hoc fallback prompt text at runtime.

API key resolution order:

1. local key file from `api_key_file` (default `.agents/secrets/openai.key`)
2. env var from `api_key_env` (default `OPENAI_API_KEY`)

For shared environments, using the local key file is recommended.

Before any provider call, Nexus-Nancy runs strict preflight validation: API key/base URL sanity, required message structure (system + user), tool spec integrity (including `bash`), and request-size guard via `max_preflight_tokens`.
The live system prompt is read from `.agents/instructions.txt` and rendered at runtime, including a dynamically generated tools block.

Set `user_display_name` in `.agents/nnancy.yaml` to control the user label shown in the TUI transcript (default: `USER`).

Execution routing is controlled in `.agents/nnancy.yaml`:

- `execution_strategy: auto` uses native OpenAI-style tool calls only after support is verified.
- `execution_strategy: universal` always uses the compatibility text harness.
- `execution_strategy: native_openai` requires verified native tool support and fails loudly otherwise.
- `native_tools`, `reasoning_channel`, and `parallel_tool_calls` default to `auto`; set a boolean only when you want an explicit override.
- `capability_probe: true` enables a cheap live probe that asks the provider to return a synthetic tool call without executing any local tool.

Edit these with:

```bash
nnancy config
nnancy instructions
```

For API key management during chat sessions:

- `/config` opens `.agents/nnancy.yaml`
- `/key` replaces the API key value (does not print current key)

## Guides

- [Models & Authentication](docs/MODELS_AND_AUTH.md) - Using Gemma 4, ChatGPT Plus ($20/mo), and standard API.
- [Extending Nancy](docs/PLUGINS.md) - How to write and install custom tools.
- [Capability Detection](docs/CAPABILITIES.md) - How Nancy detects tool-calling and reasoning support.

## Usage

```bash
nnancy
nnancy -t "summarize @README.md"
nnancy doctor
nnancy config
nnancy instructions
```

`nnancy doctor` checks workspace bootstrap files, sandbox root, API key source, key-file permissions, selected execution route, detected capability status, and base URL health via `<base_url>/models`.

`sandbox_allowlist.txt` supports one substring per line. If a substring appears in a command, substring-based sandbox blocks are bypassed for that command.

Interactive mode uses a Python Textual TUI when running in a real terminal. If TTY support is missing (for example some notebook terminal environments), it automatically falls back to a plain line-input mode.

The TUI status line shows model, mode (`sandbox`/`yolo`), current working directory, and approximate context token count.
Each TUI session gets an `id` shown in that status line.

Transcripts are always saved for posterity at:

- `.agents/transcripts/<id>.txt`

These transcripts and the `logs/session-*.log` files are plain local files.
Anyone with access to the workspace can read them.

Use `Ctrl+Y` in TUI to show copy mode info with the current transcript path.
`Ctrl+Y` suspends the TUI and opens the transcript in your terminal (`less` if available, else `cat`) so native terminal text selection/copy works, then returns to the app.

Default model is `gpt-5.4-mini`. Context token estimate uses `tiktoken` when available and falls back to a simple character heuristic otherwise.

Inside the prompt:

- `/new` starts a fresh in-process context
- `/handoff` writes a JSON continuation snapshot to `logs/handoff.json`
- `/handoff path/to/handoff.json` loads prior context
- `/config` opens workspace config file `.agents/nnancy.yaml`
- `/key NEW_API_KEY` replaces API key file contents
- `@relative/path` inlines file content into your prompt

Universal assistant protocol:

- User-visible assistant text must be inside `[RESPONSE]...[/RESPONSE]`
- Any other assistant text is treated as private raw/debug output
- Each completed assistant turn must end with `[EOT]`
- Tool calls must use JSON arguments that exactly match the surfaced tool schema

Native OpenAI route:

- Native mode sends tools through the OpenAI-compatible `tools` payload.
- Assistant text is shown directly and is not parsed for `[RESPONSE]` wrappers.
- If a provider returns a valid JSON tool call in plain text instead of `tool_calls`, Nexus-Nancy treats it as a raw function call safety net.
- Local models such as Gemma or Llama variants are most reliable when their backend supports native chat templates, for example llama.cpp with Jinja templating enabled.
- Providers that claim OpenAI compatibility may still reject tools, ignore tools, or return malformed calls; leave `execution_strategy: auto` unless native support is known or verified.

In the Textual TUI, you can also run `/key` with no argument to set the key via hidden prompts (value + confirmation) without echoing the key to screen.

## Notes

- Tool execution is local.
- Sandbox mode is default.
- Chat logs are written to `logs/session-*.log`.
- In the TUI, only `[RESPONSE]` blocks are shown as assistant replies; non-response assistant text and tool output are shown as collapsed raw/debug blocks.
- Tool calls outside the allowlist prompt for `yes`, `no`, or `respond` approval in sandbox mode.
- `nnancy yolo` exists but is intentionally not advertised in help output.
