from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TextLog:
    root: Path
    file_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.file_path = self.root / f"session-{ts}.log"
        # Session logs are intentionally plain text artifacts for inspection by
        # humans. Do not compact, sanitize, or hide diagnostic content here.
        self.file_path.write_text(
            f"# Nexus-Nancy session {ts}\\n", encoding="utf-8"
        )

    def write(self, role: str, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        with self.file_path.open("a", encoding="utf-8") as f:
            # Write the exact payload received. The log is meant to expose wires,
            # not cover them up.
            f.write(f"\\n[{stamp}] {role}\\n{text}\\n")
