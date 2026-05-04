from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

import bashlex

BLOCKED_COMMANDS = {
    "sudo",
    "su",
    "doas",
    "curl",
    "wget",
    "nc",
    "ncat",
    "netcat",
    "scp",
    "ssh",
    "rsync",
}

BLOCKED_OPERATORS = {"|", "||", "&", "&&", ";", "`", "$(", "<(", ">("}


def _bash_syntax_ok(command: str) -> tuple[bool, str]:
    try:
        bashlex.parse(command)
    except Exception as exc:
        # Bubble the parser complaint through unchanged so syntax failures stay
        # specific instead of being collapsed into "bad command."
        return False, f"bash parser rejected command ({exc})"

    proc = subprocess.run(
        ["zsh", "-n", "-c", command],
        text=True,
        capture_output=True,
    )
    if proc.returncode == 0:
        return True, ""
    return False, (proc.stderr or "invalid shell syntax").strip()


@dataclass
class SandboxPolicy:
    root: Path
    yolo: bool = False
    allowlist_substrings: list[str] | None = None

    def _is_allowlisted(self, command: str) -> bool:
        if not self.allowlist_substrings:
            return False
        return any(item in command for item in self.allowlist_substrings)

    def is_allowlisted(self, command: str) -> bool:
        return self._is_allowlisted(command)

    def validate(self, command: str) -> tuple[bool, str]:
        if self.yolo:
            return True, ""

        stripped = command.strip()
        if not stripped:
            return False, "empty command"

        allowlisted = self._is_allowlisted(stripped)

        syntax_ok, syntax_reason = _bash_syntax_ok(stripped)
        if not syntax_ok:
            return False, f"blocked by sandbox: {syntax_reason}"

        lowered = f" {stripped.lower()} "
        dangerous_phrases = [
            " rm -rf /",
            " rm -rf ~",
            " chmod -r 777 /",
            " chmod -R 777 /",
            " mkfs",
            " dd if=",
        ]
        for phrase in dangerous_phrases:
            if phrase in lowered and not allowlisted:
                return False, f"blocked by sandbox: phrase '{phrase.strip()}'"

        for op in BLOCKED_OPERATORS:
            if op in stripped and not allowlisted:
                return False, f"blocked by sandbox: shell operator '{op}'"

        try:
            tokens = shlex.split(stripped)
        except Exception as exc:
            # Keep the shell tokenizer error visible; it is often the only clue
            # about what quoting or escaping went wrong.
            return False, f"blocked by sandbox: parse failure ({exc})"

        if not tokens:
            return False, "empty command"

        cmd = tokens[0]
        if cmd in BLOCKED_COMMANDS and not allowlisted:
            return False, f"blocked by sandbox: command '{cmd}'"

        for token in tokens:
            if token in {"..", "../"} or token.startswith("../"):
                return False, "blocked path traversal token"
            if token.startswith("~"):
                return False, "blocked home-directory token"
            if token.startswith("/"):
                try:
                    p = Path(token).resolve()
                    if self.root not in [p, *p.parents]:
                        return False, f"blocked path outside sandbox: {token}"
                except Exception:
                    return False, f"blocked malformed path token: {token}"

        return True, ""
