from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .logging_text import TextLog


@dataclass
class SessionState:
    cfg: Config
    system_prompt: str
    workspace_root: Path
    log: TextLog
    messages: list[dict] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        cfg: Config,
        system_prompt: str,
        workspace_root: Path,
        logs_dir: Path,
    ) -> "SessionState":
        state = cls(
            cfg=cfg,
            system_prompt=system_prompt,
            workspace_root=workspace_root,
            log=TextLog(logs_dir),
            messages=[{"role": "system", "content": system_prompt}],
        )
        state.log.write("system", system_prompt)
        return state

    def reset(self, logs_dir: Path) -> None:
        self.log = TextLog(logs_dir)
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.log.write("system", self.system_prompt)
