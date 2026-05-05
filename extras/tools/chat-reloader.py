#!/usr/bin/env python3
"""
Chat Reloader tool for Nexus-Nancy.

Provides a /reload command to restart the current conversation.

Usage:
    Copy to: .agents/tools/chat-reloader.py
    Run: nnancy doctor (to verify it loads)
    Use in chat: /reload
"""

import os
import sys

from nexus_nancy.tools import ToolDefinition


def reload_chat(reason: str = "") -> str:
    """
    Reload the current chat session by restarting Nancy.

    This tool triggers a session restart. The user will need to
    start a new conversation after this executes.

    Args:
        reason: Optional reason for reloading (displayed to user)

    Returns:
        Confirmation message
    """
    reason_msg = f" Reason: {reason}" if reason else ""
    print(f"\n[Chat Reloader] Session reload triggered.{reason_msg}")
    print("[Chat Reloader] Exiting to allow restart...")
    sys.exit(0)


def register_tools():
    """Register the chat reloader tool."""
    return [
        ToolDefinition(
            name="reload",
            description="Reload the current chat session. Use when conversation gets stuck, context is corrupted, or you want to start fresh. Optional reason parameter to log why reload was needed.",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for reloading (will be displayed)"
                    }
                },
                "required": []
            },
            handler=reload_chat,
            slash_command="/reload"
        )
    ]