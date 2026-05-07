# Implementation Plan: Nancy Codex Provider Plugin

This plan describes how to build a standalone plugin for Nexus-Nancy that enables native use of OpenAI Codex (`backend-api`) tokens by spoofing the official Codex CLI identity.

## Target Details
- **Client ID**: `app_EMoamEEZ73f0CkXaXp7hrann`
- **Backend URL**: `https://chatgpt.com/backend-api/codex/responses`
- **Auth Strategy**: 2-step Device Code flow (Login -> Extract Org/Account -> Relogin with `organization` param).

---

## Phase 1: Plugin Initialization
- [ ] Create a new directory `extras/plugins/nancy-provider-codex` (or use the cookiecutter template).
- [ ] Set up `pyproject.toml` with the `nexus_nancy.providers` entry point:
  ```toml
  [project.entry-points."nexus_nancy.providers"]
  codex = "nancy_codex.plugin"
  ```

## Phase 2: Authentic Codex Auth Flow
- [ ] Implement `CodexAuth` manager in `src/nancy_codex/auth.py`.
- [ ] **Step 1: Discovery**: 
    - Request device code from `https://auth.openai.com/api/accounts/deviceauth/usercode`.
    - Poll `https://auth.openai.com/api/accounts/deviceauth/token`.
    - Extract `access_token` and `id_token`.
    - Parse JWT `id_token` to find the nested `https://api.openai.com/auth` claim containing `organization_id` and `chatgpt_account_id`.
- [ ] **Step 2: Scoped Token**:
    - Re-run the auth flow but inject the `organization=org-xxx` parameter into the initial authorization URL (this is how Codex CLI gets a scoped token that can talk to the backend).
- [ ] Store the final `access_token`, `organization_id`, and `account_id` in `.agents/secrets/codex.json`.

## Phase 3: The Codex LLMProvider
- [ ] Implement `CodexProvider(LLMProvider)` in `src/nancy_codex/plugin.py`.
- [ ] **Header Spoofing**: Inject these headers on every request:
  ```json
  {
    "Authorization": "Bearer <access_token>",
    "chatgpt-account-id": "<account_id>",
    "openai-organization": "<organization_id>",
    "openai-beta": "responses=experimental",
    "user-agent": "Codex/0.129.0 (darwin; arm64)",
    "x-openai-client-id": "app_EMoamEEZ73f0CkXaXp7hrann"
  }
  ```
- [ ] **Payload Translation**:
    - Convert OpenAI's `messages` array into the `backend-api` format:
        - `instructions` = system prompt.
        - `input` = list of `{"type": "message", "role": "...", "content": [{"type": "input_text", "text": "..."}]}`.
    - Convert `tools` into the simplified backend `tools` array.

## Phase 4: Stream Translation (SSE)
- [ ] Implement a generator to parse the `text/event-stream` from OpenAI.
- [ ] Map `response.output_text.delta` -> `choices[0].delta.content`.
- [ ] Map `response.output_item.done` (type: function_call) -> `choices[0].delta.tool_calls`.
- [ ] Map `response.completed` -> Final metadata/usage.

## Phase 5: Integration & CLI
- [ ] Add a `register_providers()` function to `plugin.py` returning `{"codex": CodexProvider}`.
- [ ] Add a `register_tools()` function that provides a `/codex-login` slash command to trigger the Phase 2 auth flow.

---

## Delegation Instructions for Subagents
1. **Subagent 1 (Auth)**: Focus on `auth.py`. Implement the 2-step Device Code flow using `httpx`. Ensure it correctly parses the nested JWT claims.
2. **Subagent 2 (Provider)**: Focus on `plugin.py`. Implement the `LLMProvider` interface. Use the translation logic identified by the research agent.
3. **Subagent 3 (Refinement)**: Review the combined work, ensure `pyproject.toml` is correct, and run a test with a mock backend-api if possible.
