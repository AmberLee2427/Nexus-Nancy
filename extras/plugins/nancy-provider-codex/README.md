# Nancy Provider: Codex

A Nexus-Nancy plugin that enables native use of OpenAI Codex (via `backend-api`) by spoofing the official Codex CLI identity.

## Installation

1. Install this plugin in your Nexus-Nancy environment:
   ```bash
   pip install -e extras/plugins/nancy-provider-codex
   ```

2. Run Nancy and execute the login flow:
   ```bash
   # In Nancy TUI
   /codex-login
   ```

3. Update your `nnancy.yaml` to use the provider:
   ```yaml
   provider: codex
   model: gpt-4o  # Or any other supported backend model
   ```

## Why this exists
Standard OpenAI API keys cost money per token. ChatGPT Plus subscriptions ($20/mo) provide access to high-end models via the internal "Codex" backend used by tools like GitHub Copilot. This plugin allows Nexus-Nancy to "piggyback" on that subscription by mimicking the official OpenAI Codex CLI.
