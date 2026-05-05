"""A Nexus-Nancy plugin template."""

from nexus_nancy.tools import ToolDefinition


def hello(name: str = "World") -> str:
    """A simple hello world plugin for testing."""
    return f"Hello from plugin, {name}!"


def register_tools():
    """Register plugin tools. Called by Nancy at startup."""
    return [
        ToolDefinition(
            name="plugin_hello",
            description="A hello world plugin. Use to verify your plugin loads correctly.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to greet",
                        "default": "World"
                    }
                },
                "required": []
            },
            handler=hello
        )
    ]