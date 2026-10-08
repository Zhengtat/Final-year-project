"""CR-010 STOP 3: schemas for an eRST-compatible discourse relation between discourse units, and for signals.
Every edge carries an evidence quote (rule 3). Primary edges keep nuclearity from the inventory's symbol; secondary
edges keep only a direction and never get a fabricated nuclearity. SAME-UNIT is never an edge. Unknown labels and
unknown signal types fail closed."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from cumap.erst.registry import (
    ErstRegistry,
    Nuclearity,
    SignalKind,
    UnknownErstLabel,
)


@lru_cache(maxsize=1)
def _registry() -> ErstRegistry:
    return ErstRegistry.load()


class ErstSignal(BaseModel):
    """What in the text signals the relation: a discourse marker, or one of seven non-DM types with a subtype."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: SignalKind
    subtype: str | None
    anchor_text: str | None

    @model_validator(mode="after")
    def _valid(self) -> ErstSignal:
        reg = _registry()
        if self.kind == "discourse_marker":
            if self.subtype is not None:
                raise ValueError("a discourse marker has no subtype")
        else:
            if self.subtype not in reg.subtypes(self.kind):
                raise ValueError(f"{self.subtype!r} is not a {self.kind} subtype")
        unanchored = {tuple(x) for x in reg.meta["signals"]["unanchored_allowed"]}
        if not self.anchor_text and (self.kind, self.subtype) not in unanchored:
            raise ValueError("this signal needs an anchor (the tokens that signal the relation)")
        return self


class ErstEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    edge_kind: Literal["primary", "secondary"]
    label: str
    evidence: str
    # primary edges: nucleus/satellite structure from the inventory's nuclearity
    nucleus_units: list[str]
    satellite_unit: str | None
    satellite_position: Literal["before", "after"] | None
    # secondary edges: a direction only (no nuclearity)
    from_unit: str | None
    to_unit: str | None
    signals: list[ErstSignal]
    concurrent_labels: list[str]

    @model_validator(mode="after")
    def _valid(self) -> ErstEdge:
        reg = _registry()
        for lab in [self.label, *self.concurrent_labels]:
            rel = reg.get(lab)  # UnknownErstLabel is a ValueError: fail closed
            if not rel.is_true_discourse_relation:
                raise ValueError(f"{lab} is technical, not a discourse relation")
        if not self.evidence.strip():
            raise ValueError("an eRST edge needs an evidence quote")
        rel = reg.get(self.label)
        if self.edge_kind == "secondary":
            if self.nucleus_units or self.satellite_unit or self.satellite_position:
                raise ValueError("a secondary edge records a direction only, never nuclearity")
            if not (self.from_unit and self.to_unit):
                raise ValueError("a secondary edge needs from_unit and to_unit")
            return self
        if self.from_unit or self.to_unit:
            raise ValueError("a primary edge uses nucleus_units/satellite_unit, not from/to")
        kind = rel.nuclearity
        if kind is Nuclearity.MULTINUCLEAR:
            if len(self.nucleus_units) < 2 or self.satellite_unit or self.satellite_position:
                raise ValueError(f"{self.label} is multinuclear: >= 2 nuclei and no satellite")
            return self
        if len(self.nucleus_units) != 1 or not self.satellite_unit or not self.satellite_position:
            raise ValueError(
                f"{self.label} needs one nucleus, one satellite and the satellite position"
            )
        fixed = {Nuclearity.SATELLITE_AFTER: "after", Nuclearity.SATELLITE_BEFORE: "before"}
        if kind in fixed and self.satellite_position != fixed[kind]:
            raise ValueError(
                f"{self.label} ({kind.value}) has the satellite {fixed[kind]} its nucleus, not "
                f"{self.satellite_position}"
            )
        return self


__all__ = ["ErstEdge", "ErstSignal", "UnknownErstLabel"]
