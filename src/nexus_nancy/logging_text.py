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
        self.file_path.write_text(
            f"# Nexus-Nancy session {ts}\\n", encoding="utf-8"
        )

    def write(self, role: str, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(f"\\n[{stamp}] {role}\\n{text}\\n")
