"""CR-006 §13 output models. One row per concept per chapter (OrgNodeState) and one per
restructuring event. `because_*` fields carry the edge and section IDs that caused a move."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Ring = Literal["centre", "inner", "middle", "outer", "unlinked", "background"]

LABEL_STRUCTURAL = "Structural metric (no human labels)"
LABEL_OWNER_IMPORTANCE = "Owner importance check (n=40)"


class ImportanceComponents(BaseModel):
    pagerank: float
    coreness: int
    spread: float
    bridging: float
    percentiles: dict[str, float]  # per component, within the snapshot's eligible nodes


class OrgNodeState(BaseModel):
    org_id: str
    chapter: int
    concept_id: str
    node_type: Literal["Concept", "Principle"]
    first_chapter: int
    exposure_sections: int
    n_typed_edges: int
    components: ImportanceComponents
    importance_raw: float
    importance_adj: float
    ring: Ring
    radius: float
    angle_deg: float
    community_id_coarse: str | None
    community_id_fine: str | None
    background_flag: bool
    persistent_periphery: bool
    name: str = ""  # display convenience; not part of the CR's minimal schema


class RestructureEvent(BaseModel):
    org_id: str
    chapter: int
    type: Literal[
        "node_new",
        "ring_in",
        "ring_out",
        "enter_centre",
        "leave_centre",
        "late_centraliser",
        "fading",
        "community_continue",
        "community_grow",
        "community_shrink",
        "community_merge",
        "community_split",
        "community_birth",
        "community_death",
    ]
    subject_ids: list[str]  # concept or community IDs
    from_state: str | None = None
    to_state: str | None = None
    delta_importance: float | None = None
    because_edge_ids: list[str] = []
    because_section_ids: list[str] = []
