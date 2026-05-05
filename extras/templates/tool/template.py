#!/usr/bin/env python3
"""
Template tool for Nexus-Nancy.

Copy this file to your workspace's .agents/tools/ directory.
Rename it to match your tool name.

Usage:
    1. Copy to: .agents/tools/mytool.py
    2. Edit the tool functions and register_tools() below
    3. Run 'nnancy doctor' to verify it loads
"""

from nexus_nancy.tools import ToolDefinition


def hello(name: str = "World") -> str:
    """A simple hello world tool for testing."""
    return f"Hello, {name}!"


def register_tools():
    """Register your tools here. Each tool needs a ToolDefinition."""
    return [
        ToolDefinition(
            name="hello",
            description="A simple hello world tool. Use this to verify your tool loads correctly.",
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
            handler=hello,
            # slash_command: Optional command users can type directly (e.g., "/hello")
            # If set, tool can be called by model (as tool) or user (as slash command)
            slash_command=None
        )
    ]