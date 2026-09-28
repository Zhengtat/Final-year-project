"""Loads versioned prompt files: prompts/<task>/<version>.md with YAML front-matter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class PromptTemplate:
    task: str
    version: str
    schema: str
    notes: str
    body: str

    def render(self, **placeholders: str) -> str:
        """Simple `{placeholder}` substitution (str.format_map, missing keys raise)."""
        return self.body.format_map(placeholders)


def load_prompt(prompts_dir: Path, task: str, version: str) -> PromptTemplate:
    path = prompts_dir / task / f"{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"No prompt file at {path}")

    raw = path.read_text()
    match = _FRONT_MATTER_RE.match(raw)
    if not match:
        raise ValueError(f"{path} is missing YAML front-matter (---\\n...\\n---\\n<body>)")

    meta = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()

    return PromptTemplate(
        task=meta.get("task", task),
        version=meta.get("version", version),
        schema=meta.get("schema", ""),
        notes=meta.get("notes", ""),
        body=body,
    )
