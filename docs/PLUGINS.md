# Extending Nexus-Nancy

Nexus-Nancy is built to be extensible. There are two ways to add capabilities: **Tools** and **Plugins**.

## Terminology

| Type | Description |
|------|-------------|
| **Extension** | Umbrella term for any capability added to Nancy |
| **Tool** | Simple, low-dependency script triggered by model or user |
| **Plugin** | Pip-installable package with optional dependencies, can be passive/background |
| **Provider** | Plugin that implements a custom LLM backend (e.g., Gemini, Codex) |

## Quick Reference

| | Tool | Plugin | Provider |
|---|---|---|---|
| **Distribution** | Single `.py` file in `.agents/tools/` | Pip package | Pip package |
| **Dependencies** | None (besides nexus-nancy) | Any pip package | Any pip package |
| **Activation** | Triggered | Passive/Background | Via `nnancy.yaml` config |
| **Dev cost** | Low | Medium | High |
| **Best for** | Simple commands | Background services | Custom API backends |

**When to use which:**
- **Tool**: You need something simple with no dependencies, quick to prototype
- **Plugin**: You need external libraries (embeddings, APIs, etc.) or want background processing

## Option 1: Tools (Local Scripts)

Ideal for cluster environments, quick prototyping, or simple commands. Copy a `.py` file to `.agents/tools/`.

### Quick Start

1. Create `.agents/tools/` in your workspace (if it doesn't exist)
2. Add a Python file with `register_tools()` function
3. Run `nnancy doctor` to verify it loads

```python
from nexus_nancy.tools import ToolDefinition

def get_weather(location: str) -> str:
    return f"The weather in {location} is perfect."

def register_tools():
    return [
        ToolDefinition(
            name="get_weather",
            description="Get the current weather for a location.",
            parameters={
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"]
            },
            handler=get_weather,
            slash_command="/weather"  # Optional: also callable as /weather
        )
    ]
```

### Using Slash Commands

Tools can be called both by the model and directly by users:

```python
ToolDefinition(
    name="reload",
    description="Reload the chat session",
    handler=reload_chat,
    slash_command="/reload"  # User can type this directly
)
```

- `/reload` - user calls directly
- Model can also call `reload` as a tool

## Option 2: Plugins (Pip Packages)

For more complex extensions that need external dependencies or run as background services.

### Creating a Plugin (Recommended: Cookiecutter)

```bash
pip install cookiecutter
cookiecutter https://github.com/AmberLee2427/nancy-plugin-template
```

This creates a ready-to-go plugin repo with:
- `pyproject.toml` with entry point configuration
- CI workflow (verifies plugin loads)
- Release workflow (publishes to PyPI on release)
- Hello-world template to verify everything works

### Manual Plugin Creation

1. Create a Python package
2. Add `register_tools()` function
3. Configure entry point in `pyproject.toml`:
   ```toml
   [project.entry-points."nexus_nancy.plugins"]
   my_plugin = "my_package.plugin"
   ```

### Background Services

Plugins can run passively in the background. For example, a memory indexer:

```python
class MemoryIndexer:
    def __init__(self):
        self.embeddings = load_embeddings_library()
        # Initialize in background

    def on_message(self, message):
        # Index message for later retrieval
        pass

# Nancy can call this periodically or it can hook into message processing
```

### LLM Providers

Providers allow Nancy to speak to non-standard backends (like the unofficial ChatGPT Codex API, or Google Gemini) while keeping the core logic clean.

1. Implement the `LLMProvider` interface (see `nexus_nancy.provider`).
2. Export `register_providers()` from your plugin:
   ```python
   def register_providers():
       return {
           "my_custom_provider": MyProviderClass
       }
   ```
3. Add the provider entry point to `pyproject.toml`:
   ```toml
   [project.entry-points."nexus_nancy.providers"]
   my_plugin = "my_package.plugin"
   ```
4. Switch to your provider in `nnancy.yaml`:
   ```yaml
   provider: my_custom_provider
   ```

## How Nancy Discovers Extensions

Every startup, Nancy scans:
1. **Core**: `bash`, `notebook_read`, etc.
2. **Plugins**: Installed packages with `nexus_nancy.plugins` entry point
3. **Tools**: `.agents/tools/*.py` files

Verify with:
```bash
nnancy doctor
```

Look for `tools=N` in the `request_preflight` line.

## Examples

### Tool: chat-reloader
Simple script, no dependencies. Available as both tool (`reload`) and slash command (`/reload`).

### Plugin: Memory Indexer
Needs embeddings library (numpy, etc.), runs passively to index conversation history for retrieval later.

## For More Details

- **Extras**: Copy tools from `extras/tools/` or use templates in `extras/templates/`
- **Templates**: See `extras/templates/tool/` for tools, `extras/templates/plugin/` for plugins