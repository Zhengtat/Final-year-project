"""CR-011 type compatibility (Research ruling 2026-10-08): a configured map, `Concept` is generic and NOT a wildcard, and
compatibility is NOT transitive. COMPATIBLE only means "the type does not veto"; it never adds identity evidence."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT

CONFIG = REPO_ROOT / "configs/sleep_consolidation_v1.yaml"


@dataclass(frozen=True)
class TypeMap:
    pairs: frozenset[frozenset[str]]
    generic: str = "Concept"

    @classmethod
    def load(cls, path: Path = CONFIG) -> TypeMap:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))["type_compatibility"]
        return cls(
            frozenset(frozenset(p) for p in raw["cross_type_compatible"]),
            raw.get("generic_type", "Concept"),
        )

    def compatible(self, a: str, b: str) -> bool:
        return a == b or frozenset((a, b)) in self.pairs

    def positive_evidence(self, a: str, b: str) -> float:
        """Generic types contribute zero positive identity evidence."""
        return 0.0 if self.generic in (a, b) else (1.0 if a == b else 0.0)

    def cluster_consistent(self, types: dict[str, str]) -> list[tuple[str, str]]:
        """Every cross-pair of the whole proposed cluster must be compatible (non-transitive): returns the incompatible
        member pairs (empty = consistent). `types` maps node id -> type."""
        return [
            (x, y)
            for x, y in combinations(sorted(types), 2)
            if not self.compatible(types[x], types[y])
        ]
