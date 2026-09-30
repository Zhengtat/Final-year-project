"""CR-006 §13-§14: `cumap kg organise`. Reads content snapshots (read-only), writes only
under data/processed/kg/<run_id>/organisation/<org_id>/. Never modifies a concept, an edge or
evidence, never re-runs extraction, and makes no API call."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from cumap.organisation import communities as comm
from cumap.organisation.config import OrgConfig
from cumap.organisation.coreperiphery import GraphSpec, assess
from cumap.organisation.events import (
    NodeSnap,
    mean_displacement,
    node_events,
    stability,
    update_persistence,
)
from cumap.organisation.importance import build_snap_graph, compute_importance
from cumap.organisation.inputs import OrgInputs, load_inputs
from cumap.organisation.layout import LayoutState, band_angle, layout_angles, to_xy
from cumap.organisation.rings import assign_rings, radii
from cumap.organisation.schemas import (
    LABEL_STRUCTURAL,
    ImportanceComponents,
    OrgNodeState,
    RestructureEvent,
)
from cumap.schemas.relations import RelationRegistry


def code_version() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
            or "nogit"
        )
    except (OSError, subprocess.CalledProcessError):
        return "nogit"


def make_org_id(kg_run_id: str, mode: str, cfg: OrgConfig, version: str) -> str:
    blob = f"{kg_run_id}|{mode}|{cfg.config_hash()}|{version}"
    return "org_" + hashlib.sha1(blob.encode()).hexdigest()[:8]


@dataclass
class ChapterResult:
    chapter: int
    nodes: list[OrgNodeState]
    events: list[RestructureEvent]
    community_rows: list[dict]
    summary: dict


@dataclass
class OrgRun:
    org_id: str
    org_dir: Path
    chapters: list[ChapterResult] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def organise(
    inp: OrgInputs,
    cfg: OrgConfig,
    *,
    org_id: str,
    mode: str = "provisional",
    kg_run_id: str = "",
    version: str = "",
    progress=None,
) -> tuple[list[ChapterResult], dict]:
    if mode != "provisional":
        raise NotImplementedError(
            "principle mode replays the snapshots with the approved principles and waits for "
            "CR-004 STOP C (CR-006 §11); only --mode provisional is available"
        )
    results: list[ChapterResult] = []
    prev_snap: dict[str, NodeSnap] | None = None
    prev_layout: LayoutState | None = None
    prev_groups: dict[str, dict[str, frozenset[str]]] = {"coarse": {}, "fine": {}}
    counters = {"coarse": [0], "fine": [0]}
    ever_central: set[str] = set()
    streak_unl: dict[str, int] = {}
    streak_per: dict[str, int] = {}
    prev_xy: dict[str, tuple[float, float]] = {}
    use_adj = cfg.importance.radius_basis == "adjusted"

    for ch in inp.chapters:
        if progress:
            progress(f"chapter {ch}: importance")
        sg = build_snap_graph(inp, ch, cfg)
        imp = compute_importance(sg, cfg)
        n = sg.spec.n
        names = [inp.concepts[c].name for c in sg.ids]
        linked = sg.n_edges_per_node > 0
        basis = imp.adj if use_adj else imp.raw
        rings_by = {
            k: assign_rings(v, imp.eligible, linked, imp.background, imp.coreness, names, cfg)
            for k, v in (("raw", imp.raw), ("adj", imp.adj))
        }
        rad_by = {
            k: radii(v, imp.eligible, rings_by[k], cfg)
            for k, v in (("raw", imp.raw), ("adj", imp.adj))
        }
        chosen = "adj" if use_adj else "raw"
        rings, rad = rings_by[chosen], rad_by[chosen]

        # communities (persistent ids) over linked nodes
        linked_ids = {c for c, k in zip(sg.ids, linked, strict=True) if k}
        track: dict[str, comm.TrackResult] = {}
        for level, membership, prefix in (
            ("coarse", imp.coarse_membership, "K"),
            ("fine", imp.fine_membership, "F"),
        ):
            groups = comm.groups_from_membership(sg.ids, membership, linked_ids)
            track[level] = comm.track_communities(
                prev_groups[level] or None, groups, counters[level], prefix, cfg.communities
            )
            prev_groups[level] = track[level].state
        comm_coarse = {c: cid for cid, ms in track["coarse"].state.items() for c in ms}
        comm_fine = {c: cid for cid, ms in track["fine"].state.items() for c in ms}

        # layout for eligible nodes
        elig_ids = [c for c, e in zip(sg.ids, imp.eligible, strict=True) if e]
        elig_set = set(elig_ids)
        groups_layout: dict[str, list[str]] = {}
        for c in elig_ids:
            if c in comm_coarse:
                groups_layout.setdefault(comm_coarse[c], []).append(c)
        adj: dict[tuple[str, str], float] = {}
        for a, b, w in zip(sg.spec.u, sg.spec.v, sg.spec.w, strict=True):
            ca, cb = sg.ids[a], sg.ids[b]
            if ca in elig_set and cb in elig_set and ca != cb:
                key = (ca, cb) if ca < cb else (cb, ca)
                adj[key] = adj.get(key, 0.0) + w
        angles, prev_layout = layout_angles(prev_layout, groups_layout, adj, cfg)

        idx = {c: i for i, c in enumerate(sg.ids)}
        xy: dict[str, tuple[float, float]] = {}
        node_angle: dict[str, float] = {}
        for c in sg.ids:
            i = idx[c]
            if rings[i] in {"unlinked", "background"}:
                node_angle[c] = band_angle(c)
            else:
                node_angle[c] = angles.get(c, band_angle(c))
            xy[c] = to_xy(float(rad[i]), node_angle[c])

        # node snapshot for events / stability
        nbrs: dict[str, set[str]] = {c: set() for c in sg.ids}
        for a, b in zip(sg.spec.u, sg.spec.v, strict=True):
            nbrs[sg.ids[a]].add(sg.ids[b])
            nbrs[sg.ids[b]].add(sg.ids[a])
        cur = {
            c: NodeSnap(
                c,
                names[idx[c]],
                inp.concepts[c].first_chapter,
                rings[idx[c]],
                float(_pct(basis, imp.eligible)[idx[c]]),
                bool(imp.eligible[idx[c]]),
                int(sg.n_edges_per_node[idx[c]]),
                nbrs[c],
            )
            for c in sg.ids
        }
        new_edges = [e for e in inp.edges if e.chapter == ch]
        events = node_events(org_id, ch, prev_snap, cur, new_edges, ever_central, cfg)
        for level in ("coarse", "fine"):
            for ce in track[level].events:
                events.append(
                    RestructureEvent(
                        org_id=org_id,
                        chapter=ch,
                        type=ce.type,
                        subject_ids=ce.subject_ids,
                        from_state=ce.from_state,
                        to_state=ce.to_state,
                    )
                )
        flag_unl, flag_per = update_persistence(streak_unl, streak_per, cur, cfg)
        ever_central |= {c for c, s in cur.items() if s.ring in {"centre", "inner"}}

        # core-periphery test on the eligible subgraph
        if progress:
            progress(f"chapter {ch}: core-periphery null models ({cfg.null_model.iterations} x 2)")
        sub_index = {c: k for k, c in enumerate(elig_ids)}
        su, sv, sw, sm = [], [], [], []
        for a, b, w, m in zip(sg.spec.u, sg.spec.v, sg.spec.w, sg.spec.mode, strict=True):
            if sg.ids[a] in sub_index and sg.ids[b] in sub_index:
                su.append(sub_index[sg.ids[a]])
                sv.append(sub_index[sg.ids[b]])
                sw.append(w)
                sm.append(m)
        sub_spec = GraphSpec(len(elig_ids), su, sv, sw, sm)
        eligible_pos = [idx[c] for c in elig_ids]
        core_mask = np.array([rings[i] in cfg.rings.core_for_fit for i in eligible_pos])
        cp = assess(
            sub_spec, sg.spread[eligible_pos], sg.exposure[eligible_pos], cfg, core_mask=core_mask
        )

        stab = stability(prev_snap, cur, mean_displacement(prev_xy, xy) if prev_xy else None)

        states: list[OrgNodeState] = []
        for c in sg.ids:
            i = idx[c]
            states.append(
                OrgNodeState(
                    org_id=org_id,
                    chapter=ch,
                    concept_id=c,
                    node_type=inp.concepts[c].node_type
                    if inp.concepts[c].node_type in ("Concept", "Principle")
                    else "Concept",
                    first_chapter=inp.concepts[c].first_chapter,
                    exposure_sections=int(sg.exposure[i]),
                    n_typed_edges=int(sg.n_edges_per_node[i]),
                    components=ImportanceComponents(
                        pagerank=float(imp.pagerank[i]),
                        coreness=int(imp.coreness[i]),
                        spread=float(sg.spread[i]),
                        bridging=float(imp.bridging[i]),
                        percentiles={k: float(v[i]) for k, v in imp.pcts.items()},
                    ),
                    importance_raw=float(imp.raw[i]),
                    importance_adj=float(imp.adj[i]),
                    ring=rings[i],
                    radius=float(rad[i]),
                    angle_deg=float(node_angle[c]),
                    community_id_coarse=comm_coarse.get(c),
                    community_id_fine=comm_fine.get(c),
                    background_flag=bool(imp.background[i]),
                    persistent_unlinked=c in flag_unl,
                    persistent_periphery=c in flag_per,
                    ring_raw=rings_by["raw"][i],
                    ring_adj=rings_by["adj"][i],
                    radius_raw=float(rad_by["raw"][i]),
                    radius_adj=float(rad_by["adj"][i]),
                    name=names[i],
                )
            )

        crow = []
        for level in ("coarse", "fine"):
            for cid, members in sorted(track[level].state.items()):
                top = sorted(
                    (m for m in members if cur[m].eligible),
                    key=lambda m: (-cur[m].basis, cur[m].name),
                )[:3]
                crow.append(
                    {
                        "org_id": org_id,
                        "chapter": ch,
                        "level": level,
                        "community_id": cid,
                        "size": len(members),
                        "members": sorted(members),
                        "label": [cur[m].name for m in top],
                        "changed": cid in track[level].changed,
                        "jaccard_to_previous": track[level].jaccard.get(cid),
                    }
                )

        summary = {
            "chapter": ch,
            "n_nodes": n,
            "n_edges": len(sg.spec.u),
            "n_eligible": int(imp.eligible.sum()),
            "n_unlinked": int((~linked).sum()),
            "n_background": int(imp.background.sum()),
            "background_ids": [c for c, b in zip(sg.ids, imp.background, strict=True) if b],
            "modularity_coarse": comm.modularity(sg.spec, imp.coarse_membership),
            "modularity_fine": comm.modularity(sg.spec, imp.fine_membership),
            "core_periphery": cp.to_dict(),
            "stability": stab,
            "radius_basis": cfg.importance.radius_basis,
            "label_source": LABEL_STRUCTURAL,
        }
        results.append(ChapterResult(ch, states, events, crow, summary))
        prev_snap, prev_xy = cur, xy

    manifest = {
        "org_id": org_id,
        "kg_run_id": kg_run_id,
        "mode": mode,
        "config_hash": cfg.config_hash(),
        "code_version": version,
        "seeds": {
            "communities": cfg.communities.seed,
            "null_model": cfg.null_model.seed,
            "layout": cfg.layout.seed,
        },
        "radius_basis": cfg.importance.radius_basis,
        "label_source": LABEL_STRUCTURAL,
        "chapters": {str(r.chapter): r.summary for r in results},
    }
    return results, manifest


def _pct(basis: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    from cumap.organisation.importance import percentile

    return percentile(basis, eligible)


def run_organisation(
    run_dir: Path,
    sections_jsonl: Path,
    registry: RelationRegistry,
    cfg: OrgConfig,
    *,
    mode: str = "provisional",
    through_chapter: int | None = None,
    version: str | None = None,
    progress=None,
) -> OrgRun:
    version = version or code_version()
    inp = load_inputs(run_dir, sections_jsonl, registry, cfg, through_chapter=through_chapter)
    org_id = make_org_id(run_dir.name, mode, cfg, version)
    results, manifest = organise(
        inp,
        cfg,
        org_id=org_id,
        mode=mode,
        kg_run_id=run_dir.name,
        version=version,
        progress=progress,
    )
    org_dir = run_dir / "organisation" / org_id
    for r in results:
        d = org_dir / f"ch{r.chapter}"
        _write_jsonl(d / "org_nodes.jsonl", [s.model_dump() for s in r.nodes])
        _write_jsonl(d / "communities.jsonl", r.community_rows)
        _write_jsonl(d / "events.jsonl", [e.model_dump() for e in r.events])
    (org_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=float), encoding="utf-8"
    )
    return OrgRun(org_id, org_dir, results, manifest)
