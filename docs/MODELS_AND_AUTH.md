# Models & Authentication

Nexus-Nancy supports multiple ways to connect to LLMs, from high-performance local servers to cost-effective ChatGPT Plus subscriptions.

## 1. Local LLM (Gemma 4 / Llama 3)
Ideal for private, high-speed execution.

### Start the Llama Server
```bash
llama-server -m /path/to/model.gguf --port 8089 --jinja --reasoning-format deepseek --think
```

### Configure Nancy
```yaml
# .agents/nnancy.yaml
model: my-local-model
base_url: http://localhost:8089/v1
auth_type: api_key
api_key_file: none
```

---

## 2. ChatGPT Plus Subscription ($20/mo)
Nexus-Nancy can bridge directly to your ChatGPT Plus subscription using **OpenAI Codex OAuth**. This avoids per-token API billing and allows you to use your flat-rate subscription.

### Login
Run the following command on your local machine:
```bash
nnancy auth login
```
This will open your browser to OpenAI's authorization page. Once you log in, Nancy will capture the session tokens and store them securely in `.agents/secrets/codex.json`.

### Configure Nancy
```yaml
# .agents/nnancy.yaml
auth_type: codex
model: gpt-5.4  # Or latest available via Codex
```

Nancy will automatically handle token usage and refreshing. Note that this method is subject to your subscription's message caps (e.g., 80 messages / 3 hours).

---

## 3. Standard OpenAI API
Standard usage-based billing.

```yaml
# .agents/nnancy.yaml
auth_type: api_key
api_key_env: OPENAI_API_KEY
base_url: https://api.openai.com/v1
```

## Model Switching Strategy
Nancy follows a **Minimalist Configuration** philosophy. We do not provide commands to switch models (e.g., `nnancy use gpt-4`). Instead, we encourage users to edit the `.agents/nnancy.yaml` file directly. 

This ensures:
1. **Source of Truth**: The config file always reflects the current state.
2. **Explicitness**: You always know which model is active and what it costs.
3. **Admin-Free**: No complex hidden state to manage across different cluster nodes.
