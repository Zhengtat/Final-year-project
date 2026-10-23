"""CR-012 benchmark-local schema profile (Research ruling 2026-10-10). `CUMAP_BENCHMARK_PROFILE` (a path to the profile yaml) switches the
UNCHANGED CR-009 stages to a benchmark schema: node types, generator prompt variant (node-type line only), no few-shot bank, empty lexicon,
no canonical overrides, and the benchmark relation registry (through `CUMAP_RELATION_REGISTRY`). With the variable unset nothing changes."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT


@dataclass(frozen=True)
class Profile:
    name: str
    entity_types: tuple[str, ...]
    relation_registry: Path
    domain: str
    prompt_task: str
    prompt_version: str
    symmetric: frozenset[str]
    tau: float
    strict_g_links: bool
    raw: dict


def load_profile(path: Path) -> Profile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    g = raw["generator_prompt"]
    return Profile(
        raw["name"], tuple(raw["entity_types"]), REPO_ROOT / raw["relation_registry"], raw["domain"], g["task"], g["version"],
        frozenset(raw["symmetric"]), float(raw["pruner"]["tau"]), bool(raw["strict_g_links"]), raw,
    )  # fmt: skip


def active_profile() -> Profile | None:
    p = os.environ.get("CUMAP_BENCHMARK_PROFILE")
    return load_profile(Path(p)) if p else None


def file_hashes(paths: dict[str, str]) -> dict[str, str]:
    return {k: hashlib.sha256((REPO_ROOT / v).read_bytes()).hexdigest() for k, v in paths.items()}
