# Extending Nexus-Nancy: Plugins & Local Tools

Nexus-Nancy is built to be extensible without requiring a heavy harness or Node.js. There are two primary ways to add new tools: **Option A (Installed Plugins)** and **Option B (Local Workspace Tools)**.

## Option A: Installed Plugins (Entry Points)
This is the standard way to distribute and share Nancy tools via `pip`. Any package that registers a `nexus_nancy.plugins` entry point will be automatically discovered by Nancy.

### Creating a Plugin (Recommended: Use Cookiecutter)

The easiest way to create a new plugin is with the official cookiecutter template:

```bash
pip install cookiecutter
cookiecutter https://github.com/AmberLee2427/Nexus-Nancy.git --directory extras/templates/plugin
```

This will prompt for:
- `name` - Plugin name (e.g., `chat-reloader`)
- `description` - One-line description
- `author` - Your name
- `email` - Your email

The template includes:
- `pyproject.toml` with proper entry point configuration
- CI workflow (verifies plugin loads)
- Release workflow (publishes to PyPI on GitHub release)
- Basic hello-world plugin to verify everything works

### Manual Plugin Creation

If you prefer to create from scratch:

1. Create a Python package.
2. Define a function or module that implements a `register_tools()` function returning a list of `ToolDefinition` objects.
3. Add the following to your `pyproject.toml`:
   ```toml
   [project.entry-points."nexus_nancy.plugins"]
   my_awesome_tool = "my_package.plugin_module"
   ```

## Option B: Local Workspace Tools (Drop-in Scripts)
Ideal for "Cluster" environments or quick prototyping. You can drop any `.py` file into your workspace, and Nancy will load it at startup.

### How to use:
1. Create the directory `.agents/tools/` in your workspace.
2. Add a Python file (e.g., `weather.py`).
3. Implement the `register_tools()` function:

```python
from nexus_nancy.tools import ToolDefinition

def get_weather(location, **kwargs):
    # Your logic here
    return f"The weather in {location} is perfect."

def register_tools():
    return [
        ToolDefinition(
            name="get_weather",
            description="Get the current weather for a location.",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            },
            handler=get_weather
        )
    ]
```

## How Nancy Discovers Tools
Every time you run `nnancy` or use the `doctor` command, Nancy performs a discovery sweep:
1. **Core**: Loads `bash`, `notebook_read`, etc.
2. **Plugins**: Scans all installed packages for entry points.
3. **Local**: Scans `.agents/tools/*.py`.

You can verify your tools are loaded by running:
```bash
nnancy doctor
```
Look for the `request_preflight` line to see the total tool count.
