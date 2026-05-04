# TODO: Split Native Tool/Reasoning Route From Universal Harness Route

## Goal

Add an execution switcher that uses a native OpenAI-compatible tool/reasoning path when the configured model can be verified to support it, and falls back to the current universal dumb-model loop when those capabilities are unknown or unsupported.

## 1. Model Capability Configuration

Edit `src/nexus_nancy/config.py`.

- Add explicit config fields to `Config`: `execution_strategy`, `native_tools`, `reasoning_channel`, `parallel_tool_calls`, and `capability_probe`.
- Use `execution_strategy` values like `auto`, `native_openai`, and `universal`.
- Add the same fields to `default_config_yaml()` so fresh workspaces expose the route controls.
- Keep defaults conservative: `execution_strategy: auto`, `capability_probe: true`, and fallback to universal unless native support is verified.
- Confirm `_parse_flat_yaml()` handles the new string and boolean fields without special cases.

## 2. Capability Detection

Create `src/nexus_nancy/capabilities.py`.

- Define a small capability model with `native_tools`, `reasoning_channel`, `parallel_tool_calls`, `source`, and `verified` fields.
- Implement detection from explicit config overrides first.
- Add optional static rules only for known-good model/provider combinations if they are reliable enough to trust.
- Add an optional live probe against the configured provider when `capability_probe` is true.
- Keep the probe safe and cheap: no local tool execution, no workspace mutation, and no dependency on user files.
- Return unsupported/unknown on probe failure instead of crashing auto mode.
- Make forced native mode fail loudly when native support cannot be verified.

## 3. Execution Strategy Switcher

Create `src/nexus_nancy/execution.py` or add a small strategy layer in `src/nexus_nancy/app.py`.

- Define strategy names: `native_openai` and `universal`.
- Implement selection logic for `auto`, forced `native_openai`, and forced `universal`.
- In `auto`, use native only when capabilities are verified.
- In forced `universal`, always use the current dumb-model loop.
- In forced `native_openai`, error if the model config cannot verify native tool support.
- Keep shared `PromptResult`, `ToolCallRecord`, approval, sandbox, and transcript behavior so both routes remain inspectable.

## 4. Context Builders

Create `src/nexus_nancy/context.py` or keep minimal helpers in `app.py`.

- Split context construction into a universal context and a native OpenAI context.
- Reconstruct the system prompt for the selected route instead of reusing the current universal harness prompt unchanged.
- Universal context should keep the current rendered tools block, `[RESPONSE]`, `[EOT]`, and harness-readable protocol instructions.
- Native context should rely on native `tools` payloads and avoid over-instructing the dumb-model text protocol.
- Native context should have a route-specific system prompt that explains normal assistant behavior, local execution constraints, and response visibility without requiring `[RESPONSE]`/`[EOT]` wrappers.
- Ensure handoff/new-session flows rebuild `state.messages` with the correct route-specific system prompt after strategy selection.
- Edit `build_state()` in `src/nexus_nancy/app.py` to select capabilities/strategy before rendering the prompt.
- Consider adding a bundled native prompt template at `.agents/native_instructions.txt`.
- If adding the native template, update `bootstrap_local_files()` and `pyproject.toml` wheel/sdist inclusion.

## 5. Native OpenAI Tool Route

Edit `src/nexus_nancy/app.py`.

- Extract the current `_assistant_turn()` into universal-specific logic or rename it to `_assistant_turn_universal()`.
- Add `_assistant_turn_native_openai()`.
- Native route should call `llm.chat(state.messages, TOOL_SPECS)`, append assistant messages with native `tool_calls`, execute tool calls with existing `_handle_tool_call()`, append native `tool` messages with `tool_call_id`, and continue until no tool calls remain.
- **Implement a Reliability Parser (Safety Net)**: If `tool_calls` is empty but the assistant text contains valid JSON matching a tool schema, treat it as a "raw-function-call". This "model-proofs" the route against providers (like Ollama) that often fail to map native tokens to the formal API metadata.
- Use returned assistant content directly as visible response unless a native reasoning field needs separate handling.
- Do not parse native-route visible assistant text with the universal `[RESPONSE]` parser unless explicitly preserving a compatibility shim for a known reason.
- Preserve raw assistant logging, tool records, transcript events, and approval handling.

## 6. Universal Harness Route

Edit `src/nexus_nancy/app.py`.

- Keep current text-protocol behavior as the universal fallback.
- Ensure universal route still expects `[RESPONSE]...[/RESPONSE]`, treats non-response text as private/debug content, respects `[EOT]`, and can execute provider-emitted OpenAI-style tool calls.
- Rename constants/comments where useful so it is clear they belong to the universal route rather than every route.

## 7. LLM Client Support

Edit `src/nexus_nancy/llm.py`.

- Keep `chat()` as the OpenAI-compatible `/chat/completions` request function.
- Add request options if needed for `tool_choice`, `parallel_tool_calls`, `response_format`, or provider-specific reasoning fields.
- **Support Native Templating (Jinja2)**: Ensure the client can signal the provider to use native chat templates. This prevents "dialect" errors where the provider's generic translation layer incorrectly strips or modifies tool-calling tokens (e.g. Gemma 4's `<|channel>` calls).
- Add a lightweight capability probe helper or expose enough lower-level request behavior for `capabilities.py`.
- Avoid hard-coding `bash` as required in `_validate_tools()` for capability probes if probes use a synthetic tool.
- Preserve strict preflight validation for real requests.

## 8. Doctor Diagnostics

Edit `src/nexus_nancy/doctor.py`.

- Show selected execution strategy.
- Show detected native tools, reasoning channel, and parallel tool call capability status.
- Show capability source: config override, live probe, static rule, or fallback.
- Add a doctor check that explains when the app will use universal fallback.
- Ensure doctor remains useful even if capability probing fails.

## 9. CLI and TUI Visibility

Edit `src/nexus_nancy/cli.py` and `src/nexus_nancy/tui.py`.

- Surface selected route in TUI status, for example `route=native_openai` or `route=universal`.
- Keep normal single-prompt CLI output clean; expose route details through doctor and errors rather than every response.
- In TUI transcript/debug panels, show native tool calls and universal parsed tool calls consistently.

## 10. Mock Provider Updates

Edit `tests/mock_llm_service.py`.

- Add mock models or modes for capability testing: native tools supported, tools rejected, tools ignored, and malformed tool calls.
- Add `/v1/models` metadata if useful for static detection.
- Keep `mock-shakespeare` as the universal fallback/protocol test model.

## 11. Test Suite Setup

Edit `pyproject.toml`.

- Add `pytest` to dev dependencies.
- Add `build` to dev dependencies if wheel verification should run from the same environment.
- Add pytest config if needed.
- Create test files under `tests/`.

## 12. Unit Tests

Create `tests/test_config.py`.

- Verify config parses new strategy/capability fields.
- Verify defaults are conservative.

Create `tests/test_capabilities.py`.

- Verify explicit config override forces native support.
- Verify unsupported/unknown provider falls back to universal.
- Verify probe failure does not crash auto mode.
- Verify forced native mode errors when support cannot be verified.

Create `tests/test_context.py`.

- Verify universal context includes tool text protocol and `[RESPONSE]`/`[EOT]` requirements.
- Verify native context does not include unnecessary dumb-model protocol requirements.
- Verify switching routes reconstructs the system prompt and does not keep stale universal/native instructions in `state.messages[0]`.

Create `tests/test_execution_strategy.py`.

- Verify `auto` chooses native when verified.
- Verify `auto` chooses universal when native support is not verified.
- Verify forced universal always uses universal.
- Verify forced native fails loudly if unsupported.

## 13. Integration Tests

Create `tests/test_native_route.py`.

- Verify native route executes a returned `bash` tool call.
- Verify native route appends assistant/tool messages in OpenAI-compatible shape.
- Verify tool approval denial is handled correctly.
- Verify malformed native tool args produce visible tool error records.

Create `tests/test_universal_route.py`.

- Verify universal route still parses `[RESPONSE]`.
- Verify universal route still hides private text from visible CLI output.
- Verify universal route still respects `[EOT]`.
- Verify existing mock `-tm` behavior still works.

Create `tests/test_doctor.py`.

- Verify doctor output reports selected route and capability status.

## 14. Local Verification

Run from repo checkout:

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check .
nnancy -tm "Say something"
nnancy -tm "Run this tool test:\n```tool_test.yml\nbash:\n  - pwd\n```"
nnancy doctor
```

Manually verify:

- `execution_strategy: universal` uses the old harness behavior.
- `execution_strategy: auto` falls back cleanly with `mock-shakespeare`.
- `execution_strategy: native_openai` fails clearly against a mock/model that cannot verify native tools.
- Native route logs raw assistant content and tool outputs as inspectably as the universal route.

## 15. Fresh Wheel Verification

Run from a clean temp directory, not the repo checkout:

```bash
python -m pip install build
python -m build
python -m venv /tmp/nnancy-wheel-test
/tmp/nnancy-wheel-test/bin/pip install dist/nexus_nancy-*.whl
mkdir /tmp/nnancy-smoke
cd /tmp/nnancy-smoke
/tmp/nnancy-wheel-test/bin/nnancy --help
/tmp/nnancy-wheel-test/bin/nnancy doctor
```

Verify from the wheel install:

- `.agents/nnancy.yaml` includes the new strategy/capability fields.
- All bundled prompt templates copy correctly on first run.
- No repo-local files are required except intentionally test-only mock server files.
- `nnancy doctor` does not crash if capability probing cannot reach the provider.
- Forced universal mode works with only installed package files.
- Forced native mode gives a clear error when the provider/model cannot verify native tool support.

## 16. Documentation

Edit `README.md`.

- Explain `execution_strategy`.
- Document `auto`, `native_openai`, and `universal`.
- Explain that universal is the compatibility fallback and native is used only when verified.
- **Reliability Notes**: Document that for local models (Gemma 4, Llama 3.1), reliable tool calling requires a backend that supports native templates (like `llama.cpp --jinja`) and that the app includes a fallback JSON-in-text parser to handle "finish_reason: stop" quirks.
- Add troubleshooting notes for providers that claim OpenAI compatibility but reject tools or return malformed tool calls.
