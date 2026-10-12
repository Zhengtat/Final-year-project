"""CR-013 derived trace model. A `TraceEvent` is a normalised record of something that happened (or did not happen) to one object at one pipeline stage,
backfilled ONLY from retained artifacts. Nothing here infers an unrecorded decision: absent values stay `None` and are rendered `NOT_RECORDED`.

`layer` says how the event was obtained (Research D1/D2):
  RECORDED  read directly from a retained artifact;
  REPLAYED  recomputed by the frozen deterministic code and verified to reproduce the retained selected set exactly (never "originally recorded");
  JOINED    an exact, run-scoped, deterministic join (method and key stored)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"
NOT_RECORDED = "NOT_RECORDED"
Stage = Literal["source", "generator", "verifier", "correction", "pruner", "canonicalisation", "pair_generation", "pair_selection", "relation_classification", "validation", "graph_commit", "organisation", "proposal", "boundary_repair"]  # fmt: skip
CR014_STAGES: tuple[str, ...] = (
    "proposal",
    "boundary_repair",
)  # additive vocabulary for new CR-014 runs only
STAGES: tuple[str, ...] = tuple(s for s in Stage.__args__ if s not in CR014_STAGES)  # type: ignore[attr-defined]  # historical CR-013 stages, unchanged
Outcome = Literal[
    "accepted",
    "corrected",
    "rejected",
    "merged",
    "blocked",
    "selected",
    "not_selected",
    "no_relation",
    "emitted",
    "not_recorded",
]
Authority = Literal["RULE", "MODEL", "SCORE", "HUMAN", "STRUCTURAL", "UNKNOWN"]
Layer = Literal["RECORDED", "REPLAYED", "JOINED"]


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    run_id: str
    dataset_mode: Literal["pd", "scinlp", "other"]
    document_id: str
    section_id: str | None = None
    stage: Stage
    object_type: Literal["span", "mention", "concept", "pair", "edge", "organisation_record"]
    object_id: str
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    action: str
    outcome: Outcome
    reason_code: str | None = None
    rule_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    score: float | None = None
    threshold: float | None = None
    rank: int | None = None
    eligible_count: int | None = None
    budget: int | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    config_hash: str | None = None
    registry_version: str | None = None
    authority: Authority = "UNKNOWN"
    source_artifact: str
    source_locator: str | None = None
    layer: Layer = "RECORDED"
    join: dict | None = None  # {"method": ..., "key": ...} for JOINED events
    attrs: dict = Field(default_factory=dict)  # stage-specific recorded values (never inferred)

    def get(self, path: str):
        """Dotted-path field access (`rank`, `attrs.surface`); None when absent."""
        cur: object = self.model_dump()
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return cur


def make_event_id(
    run_id: str,
    stage: str,
    object_id: str,
    action: str,
    locator: str | None,
    layer: str = "RECORDED",
) -> str:
    key = "\x1f".join([run_id, stage, object_id, action, locator or "", layer])
    return "te_" + hashlib.sha1(key.encode()).hexdigest()[:16]


class TraceStore:
    """In-memory trace with indexes; JSONL persistence; deterministic ordering (sorted by event_id)."""

    def __init__(self, events: list[TraceEvent] | None = None):
        self.events: dict[str, TraceEvent] = {}
        self.by_object: dict[str, list[str]] = defaultdict(list)
        self.by_stage: dict[str, list[str]] = defaultdict(list)
        for e in events or []:
            self.add(e)

    def add(self, e: TraceEvent) -> None:
        if e.event_id in self.events:
            raise ValueError(
                f"duplicate event id {e.event_id} ({e.stage} {e.object_id} {e.action})"
            )
        self.events[e.event_id] = e
        self.by_object[e.object_id].append(e.event_id)
        self.by_stage[e.stage].append(e.event_id)

    def for_object(
        self, object_id: str, stage: str | None = None, layer: str | None = None
    ) -> list[TraceEvent]:
        out = [self.events[i] for i in self.by_object.get(object_id, [])]
        return [
            e
            for e in out
            if (stage is None or e.stage == stage) and (layer is None or e.layer == layer)
        ]

    def __len__(self) -> int:
        return len(self.events)

    def to_jsonl(self, path: Path) -> str:
        lines = [
            json.dumps(self.events[i].model_dump(), sort_keys=True, ensure_ascii=False)
            for i in sorted(self.events)
        ]
        text = "\n".join(lines) + "\n"
        path.write_text(text, encoding="utf-8")
        return hashlib.sha256(text.encode()).hexdigest()

    @classmethod
    def from_jsonl(cls, path: Path) -> TraceStore:
        return cls(
            [
                TraceEvent.model_validate(json.loads(x))
                for x in path.read_text(encoding="utf-8").splitlines()
                if x.strip()
            ]
        )
