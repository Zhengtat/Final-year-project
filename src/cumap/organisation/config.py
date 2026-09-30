"""configs/organisation.yaml as typed models (CR-006 §14). Weights and thresholds are fixed
before the face-validity check and never tuned on it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = REPO_ROOT / "configs" / "organisation.yaml"

RING_ORDER = ["centre", "inner", "middle", "outer"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GraphCfg(_Strict):
    layers: list[str]
    include_prerequisite_layer: bool = False
    node_filter: Literal["checked", "anchored"] = "checked"
    edge_weight: Literal["family_prior_x_confidence"] = "family_prior_x_confidence"


class ComponentCfg(_Strict):
    weight: float
    damping: float | None = None
    roles: list[str] | None = None
    community_level: Literal["coarse", "fine"] | None = None


class ExposureCfg(_Strict):
    enabled: bool = True
    covariate: Literal["log1p_sections_since_first_seen"] = "log1p_sections_since_first_seen"


class DirectionCfg(_Strict):
    toward_target: list[str]
    toward_source: list[str]
    default: Literal["both"] = "both"


class ImportanceCfg(_Strict):
    components: dict[str, ComponentCfg]
    pagerank_direction: DirectionCfg
    exposure_correction: ExposureCfg
    radius_basis: Literal["raw", "adjusted"] = "adjusted"

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> ImportanceCfg:
        total = sum(c.weight for c in self.components.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"importance component weights must sum to 1.0, got {total}")
        return self


class GenericGuardCfg(_Strict):
    enabled: bool = True
    min_section_share: float = 0.5
    require_never_defined: bool = True
    max_edges_per_appearance_quantile: float = 0.25
    overrides_keep: list[str] = []
    overrides_generic: list[str] = []


class RingsCfg(_Strict):
    method: Literal["quantile", "kshell"] = "quantile"
    shares: dict[str, float]
    core_for_fit: list[str]

    @model_validator(mode="after")
    def _shares_sum_to_one(self) -> RingsCfg:
        if set(self.shares) != set(RING_ORDER):
            raise ValueError(f"ring shares must cover exactly {RING_ORDER}")
        if abs(sum(self.shares.values()) - 1.0) > 1e-9:
            raise ValueError("ring shares must sum to 1.0")
        return self


class ResolutionCfg(_Strict):
    coarse: float
    fine: float


class CommunitiesCfg(_Strict):
    algorithm: Literal["leiden"] = "leiden"
    resolution: ResolutionCfg
    seed: int = 42
    match_jaccard: float = 0.3
    changed_below_jaccard: float = 0.7


class PresentIfCfg(_Strict):
    z_at_least: float
    delta_rho_at_least: float


class NullCfg(_Strict):
    primary: Literal["same_density_random"] = "same_density_random"
    secondary: Literal["degree_preserving_rewire"] = "degree_preserving_rewire"
    iterations: int = 200
    present_if: PresentIfCfg
    seed: int = 42


class LayoutCfg(_Strict):
    shape: Literal["disc"] = "disc"
    r_min: float = 0.08
    r_max: float = 1.0
    sector_by: Literal["community_coarse"] = "community_coarse"
    max_angle_shift_deg: float = 20.0
    default_visible_rings: list[str] = ["centre", "inner", "middle"]
    seed: int = 42


class EventsCfg(_Strict):
    late_centraliser_gap_chapters: int = 1
    persistent_unlinked_min_snapshots: int = 2
    persistent_periphery_min_snapshots: int = 2


class FaceValidityCfg(_Strict):
    n_centre_inner: int = 20
    n_outer: int = 20
    stratify_by: str = "first_chapter"
    bootstrap_resamples: int = 2000
    seed: int = 42


class ValidationCfg(_Strict):
    face_validity: FaceValidityCfg


class OrgConfig(_Strict):
    version: int
    graph: GraphCfg
    importance: ImportanceCfg
    generic_guard: GenericGuardCfg
    rings: RingsCfg
    communities: CommunitiesCfg
    null_model: NullCfg
    layout: LayoutCfg
    events: EventsCfg
    validation: ValidationCfg

    def config_hash(self) -> str:
        blob = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()[:12]


def load_config(path: Path | None = None) -> OrgConfig:
    return OrgConfig(**yaml.safe_load((path or DEFAULT_PATH).read_text()))
