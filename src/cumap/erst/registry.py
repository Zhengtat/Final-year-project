"""CR-010 STOP 3: the eRST relation inventory (`configs/erst_relations.yaml`, Zeldes et al. 2024, Appendix A Table A.1)
and the signal taxonomy (`configs/erst_signals.yaml`, Table 1). This is a SEPARATE inventory of discourse relations
between discourse units; it is never merged into `RelationRegistry` (the domain-semantic concept relations). Unknown
labels fail closed. `SAME-UNIT` is a technical device for discontinuous units, not a discourse relation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from cumap.config import REPO_ROOT

RELATIONS_PATH = REPO_ROOT / "configs" / "erst_relations.yaml"
SIGNALS_PATH = REPO_ROOT / "configs" / "erst_signals.yaml"
NO_RELATION = "NO_ERST_RELATION"
TECHNICAL_LABELS = frozenset({"SAME-UNIT"})


class UnknownErstLabel(ValueError):
    """An eRST label that is not in the inventory: always rejected, never mapped or guessed."""


class Nuclearity(str, Enum):
    """The source legend: '←' satellite relations that only go left-to-right, '→' the opposite, '→←' a satellite
    relation in either direction, 'Λ' multinuclear. Reading used here (the arrow points at the nucleus; consistent with
    the definitions of all six fixed-orientation rows): '←' = nucleus first, satellite after; '→' = satellite first."""

    SATELLITE_AFTER = "←"
    SATELLITE_BEFORE = "→"
    SATELLITE_EITHER = "→←"
    MULTINUCLEAR = "Λ"


class ErstRelation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str
    coarse_class: str
    fine_relation: str
    primary_nuclearity_symbol: str
    is_true_discourse_relation: bool
    definition: str

    @property
    def nuclearity(self) -> Nuclearity:
        return Nuclearity(self.primary_nuclearity_symbol)

    @model_validator(mode="after")
    def _consistent(self) -> ErstRelation:
        technical = self.label in TECHNICAL_LABELS
        if self.is_true_discourse_relation == technical:
            raise ValueError(
                f"{self.label}: technical labels are exactly {sorted(TECHNICAL_LABELS)}"
            )
        if technical:
            # the package files SAME-UNIT under a 'technical' bucket, not under a discourse coarse class
            if self.coarse_class != "technical":
                raise ValueError(
                    f"{self.label}: a technical label must sit in the 'technical' bucket"
                )
        elif (
            self.label
            != f"{self.coarse_class.upper()}-{self.fine_relation.upper().replace('_', '-')}"
        ):
            # the source's naming rule for discourse relations: <coarse-class>-<fine-grained>
            raise ValueError(f"{self.label}: not <coarse-class>-<fine-relation>")
        Nuclearity(self.primary_nuclearity_symbol)  # raises on any symbol outside the legend
        return self


class ErstSignalSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subtypes: list[str]


SignalKind = Literal[
    "discourse_marker",
    "graphical",
    "lexical",
    "morphological",
    "numerical",
    "reference",
    "semantic",
    "syntactic",
]


class ErstRegistry:
    def __init__(
        self, relations: list[ErstRelation], signals: dict[str, ErstSignalSpec], meta: dict
    ):
        labels = [r.label for r in relations]
        if len(set(labels)) != len(labels):
            raise ValueError("duplicate eRST labels")
        self._by_label = {r.label: r for r in relations}
        self.relations = relations
        self.signals = signals
        self.meta = meta

    @classmethod
    def load(cls, path: Path = RELATIONS_PATH, signals_path: Path = SIGNALS_PATH) -> ErstRegistry:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        rels = [ErstRelation(**r) for r in raw["relations"]]
        legend = set(raw["nuclearity_legend"])
        if not {r.primary_nuclearity_symbol for r in rels} <= legend:
            raise ValueError("a nuclearity symbol is outside the registry's own legend")
        sig = yaml.safe_load(signals_path.read_text(encoding="utf-8"))
        specs = {k: ErstSignalSpec(**v) for k, v in sig["signal_kinds"].items()}
        declared = {"discourse_marker", *raw["signal_types"]["non_dm"]}
        if declared != set(specs):
            raise ValueError("signal kinds differ between the relation and signal files")
        return cls(rels, specs, {**{k: raw[k] for k in ("registry_id", "source")}, "signals": sig})

    # ---- fail-closed lookup
    def get(self, label: str) -> ErstRelation:
        try:
            return self._by_label[label]
        except KeyError:
            raise UnknownErstLabel(f"{label!r} is not an eRST label") from None

    def __contains__(self, label: str) -> bool:
        return label in self._by_label

    @property
    def labels(self) -> list[str]:
        return [r.label for r in self.relations]

    @property
    def discourse_labels(self) -> list[str]:
        return [r.label for r in self.relations if r.is_true_discourse_relation]

    def choice_set(self) -> list[str]:
        """What an eRST classifier may answer: the true discourse relations plus NO_ERST_RELATION. The technical
        SAME-UNIT is never a choice."""
        return [*self.discourse_labels, NO_RELATION]

    def hierarchy(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for r in self.relations:
            out.setdefault(r.coarse_class, []).append(r.label)
        return out

    def subtypes(self, kind: str) -> list[str]:
        return self.signals[kind].subtypes
