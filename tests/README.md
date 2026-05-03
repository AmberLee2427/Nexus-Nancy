# Mock LLM Test Server

This directory contains the local mock OpenAI-compatible server used for testing Nexus-Nancy against a known endpoint.

Default listen address:

```text
http://127.0.0.1:8008/v1
```

## Start It

From the repo root, you can start the mock server either way:

```bash
nnancy -m
```

or

```bash
nnancy --mock-server
```

These commands run the repo-local script in `tests/mock_llm_service.py`.
They are intentionally repo-only. If you try `nnancy -m` from a general install without the test files present, the CLI will refuse.

If you want a one-shot harness test without editing `.agents/nnancy.yaml`, use:

```bash
nnancy -tm "some text to make the mock server try to use tools"
```

This starts the repo-local mock server, temporarily points Nancy at it, runs a single prompt, prints the result, and shuts the mock server down.

If you want a different port:

```bash
nnancy -m 8009
```

or for the one-shot path:

```bash
nnancy -tm 8009 "some text to make the mock server try to use tools"
```

or directly:

```bash
python tests/mock_llm_service.py
python tests/mock_llm_service.py 8009
```

Stop it with `Ctrl+C`.

## Matching Config

If you use the default port, `.agents/nnancy.yaml` should point at:

```yaml
base_url: http://127.0.0.1:8008/v1
model: mock-shakespeare
```

## What It Exposes

- `POST /v1/chat/completions`
- `GET /v1/models`

The mock server is intentionally crude. It exists to test request formatting, key handling, tool-call flow, and raw error reporting.
