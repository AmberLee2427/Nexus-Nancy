from __future__ import annotations

from .config import Config, load_instructions, render_prompt_template
from .tools import render_tools_block


def build_universal_context(cfg: Config, workspace_root) -> str:
    instructions_template = load_instructions(workspace_root)
    return render_prompt_template(
        instructions_template,
        {
            "user_display_name": cfg.user_display_name,
            "sandbox_root": cfg.sandbox_root,
            "tools": render_tools_block(),
        },
    )


def build_native_openai_context(cfg: Config) -> str:
    return "\n".join(
        [
            "You are Nexus-Nancy, a lightweight terminal coding assistant.",
            "Be concise, deterministic, practical, and transparent about local tooling limits.",
            "",
            f"Your user is {cfg.user_display_name}.",
            f"Your sandbox directory is `{cfg.sandbox_root}`.",
            "",
            "Use the native tool-calling interface when local information or actions are needed.",
            "Do not describe a tool call as completed unless the local tool result "
            "has been returned.",
            "Tool execution is local, sandboxed by default, and may require user approval.",
            "",
            "Respond to the user with normal assistant text.",
            "Do not use the universal text-wrapper protocol for visible responses or turns.",
            "Logs and transcripts are plain local files in this workspace.",
            "Remind the user if they appear to disclose sensitive information unintentionally.",
        ]
    )
