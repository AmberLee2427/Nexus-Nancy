# Nancy Provider: Codex

A Nexus-Nancy plugin that enables native use of OpenAI Codex (via `backend-api`) by spoofing the official Codex CLI identity.

## Installation

1. Navigate to your `Nexus-Nancy` clone on the Nexus:
   ```bash
   cd ~/Code/Nexus-Nancy  # Or wherever you cloned it
   ```

2. Install this plugin in your environment:
   ```bash
   pip install -e extras/plugins/nancy-provider-codex
   ```

3. Run Nancy and execute the login flow:
   ```bash
   # In Nancy TUI
   /codex-login
   ```

4. Update your `nnancy.yaml` to use the provider:
   ```yaml
   provider: codex
   model: gpt-5.5-instant  # See below for how to find the latest models
   ```

## Finding Latest Models

OpenAI releases new models frequently. To see exactly which models are available to your account:

1. Run Nancy and type:
   ```bash
   /codex-models
   ```
2. Copy the "slug" (e.g., `gpt-5.5-pro`) of the model you want.
3. Update the `model` field in your `nnancy.yaml` with that slug.
4. Restart Nancy.

## Why this exists
Standard OpenAI API keys cost money per token. ChatGPT Plus subscriptions ($20/mo) provide access to high-end models via the internal "Codex" backend used by tools like GitHub Copilot. This plugin allows Nexus-Nancy to "piggyback" on that subscription by mimicking the official OpenAI Codex CLI.
