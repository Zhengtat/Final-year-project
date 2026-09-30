"""CR-006 §10: sphere-view figures and data for the demo report. Every chart carries the
provenance footer and the `Structural metric (no human labels)` tag (label_source
'structural_metric'); the 'no clear core' banner is drawn whenever the primary null check does
not say 'present'. Reads an organisation run directory only."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from html import escape
from itertools import pairwise
from pathlib import Path

from cumap.organisation.config import OrgConfig
from cumap.organisation.coreperiphery import BA_REFERENCE_DELTA_RHO, LABEL_PRESENT
from cumap.organisation.inputs import OrgInputs
from cumap.report.graph import chapter_slot
from cumap.report.provenance import Provenance
from cumap.report.svg import (
    STATUS,
    grouped_bar_svg,
    hbar_svg,
    slot,
    stacked_bar_svg,
    wrap_svg,
)

TAG = "structural_metric"
BOOK = "Computer Networks: A Systems Approach"
RINGS = ["centre", "inner", "middle", "outer", "unlinked", "background"]
DISC_RINGS = ["centre", "inner", "middle", "outer"]
LATE_NOTE = (
    "15 of the 87 chapter-2 edges were counted late: chapter-2 extraction missed concepts that "
    "appear in its text, so an edge whose sentence is in ch2 exists here only once both endpoints "
    "do (in ch3). CR-007's consistency rule should set first_chapter from first occurrence."
)


@dataclass
class OrgData:
    manifest: dict
    chapters: list[int]
    nodes: dict[int, list[dict]]
    events: dict[int, list[dict]]
    comms: dict[int, list[dict]]

    @property
    def org_id(self) -> str:
        return self.manifest["org_id"]

    def cp(self, ch: int) -> dict:
        return self.manifest["chapters"][str(ch)]["core_periphery"]

    def summary(self, ch: int) -> dict:
        return self.manifest["chapters"][str(ch)]


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_org(org_dir: Path) -> OrgData:
    manifest = json.loads((org_dir / "manifest.json").read_text(encoding="utf-8"))
    chapters = sorted(int(k) for k in manifest["chapters"])
    return OrgData(
        manifest,
        chapters,
        {c: _rows(org_dir / f"ch{c}" / "org_nodes.jsonl") for c in chapters},
        {c: _rows(org_dir / f"ch{c}" / "events.jsonl") for c in chapters},
        {c: _rows(org_dir / f"ch{c}" / "communities.jsonl") for c in chapters},
    )


def unlinked_text(org: OrgData, ch: int) -> str:
    s = org.summary(ch)
    return (
        f"{s['n_unlinked']} of {s['n_nodes']} concepts have no typed edge yet: see relation recall."
    )


def banner_for(org: OrgData, ch: int) -> str | None:
    return org.cp(ch)["banner"]


def _rank_map(rows: list[dict], key: str) -> dict[str, int]:
    ranked = sorted(
        (r for r in rows if r["ring"] not in ("unlinked", "background")),
        key=lambda r: (-r[key], r["name"]),
    )
    return {r["concept_id"]: i + 1 for i, r in enumerate(ranked)}


# ------------------------------------------------------------------------- charts
def topk_svg(org: OrgData, ch: int, prov: Provenance, k: int = 15) -> str:
    rows = org.nodes[ch]
    ranks = _rank_map(rows, "importance_adj")
    prev_ranks = _rank_map(org.nodes[ch - 1], "importance_adj") if (ch - 1) in org.nodes else {}
    top = sorted(
        (r for r in rows if r["concept_id"] in ranks), key=lambda r: ranks[r["concept_id"]]
    )[:k]
    items = []
    for r in top:
        pr = prev_ranks.get(r["concept_id"])
        if not prev_ranks:
            tag = ""
        elif pr is None:
            tag = "  new"
        else:
            d = pr - ranks[r["concept_id"]]
            tag = f"  ▲{d}" if d > 0 else (f"  ▼{-d}" if d < 0 else "  =")
        items.append((f"{r['name']}{tag}", r["importance_adj"], chapter_slot(r["first_chapter"])))
    return hbar_svg(
        f"Top {k} concepts at chapter {ch} (adjusted importance; ▲▼ = rank change vs previous chapter)",
        items,
        provenance=prov,
        label_source=TAG,
        xmax=1.0,
        width=720,
        label_w=250,
        note="Bar colour = chapter of first introduction (blue ch2, orange ch3).",
    )


def ring_composition_svg(org: OrgData, ch: int, prov: Provenance) -> str:
    counts: dict[int, Counter] = {}
    for r in org.nodes[ch]:
        counts.setdefault(r["first_chapter"], Counter())[r["ring"]] += 1
    intro = sorted(counts)
    series = {f"introduced ch{c}": [counts[c][ring] for ring in RINGS] for c in intro}
    return stacked_bar_svg(
        f"Ring composition at chapter {ch}, by chapter of introduction",
        RINGS,
        series,
        provenance=prov,
        label_source=TAG,
        width=720,
        height=330,
        series_colors={f"introduced ch{c}": chapter_slot(c) for c in intro},
    )


def stability_svg(org: OrgData, prov: Provenance) -> str | None:
    cats, jac, tau = [], [], []
    for ch in org.chapters:
        st = org.summary(ch)["stability"]
        if st["jaccard_core"] is None:
            continue
        cats.append(f"ch{ch - 1}→ch{ch}")
        jac.append(st["jaccard_core"])
        tau.append(max(st["kendall_tau"] or 0.0, 0.0))
    if not cats:
        return None
    return grouped_bar_svg(
        "Stability between chapters (core Jaccard, Kendall τ of importance)",
        cats,
        {"core Jaccard (centre + inner)": jac, "Kendall τ (shared nodes)": tau},
        provenance=prov,
        label_source=TAG,
        ymax=1.0,
        width=660,
        height=320,
        series_colors={"core Jaccard (centre + inner)": 0, "Kendall τ (shared nodes)": 2},
    )


def cp_fit_svg(org: OrgData, prov: Provenance) -> str:
    """Observed rho per chapter against both null bands (mean ± 2 SD) and the hub-heavy
    Barabasi-Albert reference range (primary-null mean + delta-rho 0.08-0.14)."""
    width, left, right = 820, 190, 30
    row_h, top = 104, 56
    lo, hi = -0.05, 0.55
    x = lambda v: left + (v - lo) / (hi - lo) * (width - left - right)
    body = []
    for t in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        body.append(
            f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 6}" y2="{top + row_h * len(org.chapters) - 20}"/>'
        )
        body.append(
            f'<text class="t2 sm" x="{x(t):.1f}" y="{top + row_h * len(org.chapters) - 6}" text-anchor="middle">{t:.1f}</text>'
        )
    for i, ch in enumerate(org.chapters):
        cp = org.cp(ch)
        y0 = top + i * row_h
        body.append(f'<text class="sm" x="12" y="{y0 + 24}" font-weight="600">Chapter {ch}</text>')
        body.append(f'<text class="t2 sm" x="12" y="{y0 + 42}">{escape(cp["label"])}</text>')
        p, s = cp["primary"], cp["secondary"]
        ba_lo, ba_hi = p["mean"] + BA_REFERENCE_DELTA_RHO[0], p["mean"] + BA_REFERENCE_DELTA_RHO[1]
        rows = [
            (
                0,
                "same-density null (mean ± 2 SD)",
                p["mean"] - 2 * p["sd"],
                p["mean"] + 2 * p["sd"],
                "var(--ref)",
            ),
            (
                1,
                "degree-preserving null",
                s["mean"] - 2 * s["sd"],
                s["mean"] + 2 * s["sd"],
                "var(--s3)",
            ),
            (2, "hub-heavy random graph (BA) reference", ba_lo, ba_hi, "var(--s4)"),
        ]
        for j, (_, name, a, b, colour) in enumerate(rows):
            yy = y0 + 8 + j * 20
            body.append(
                f"<g><title>{escape(name)}: {a:.3f} to {b:.3f}</title>"
                f'<rect x="{x(a):.1f}" y="{yy}" width="{max(x(b) - x(a), 2):.1f}" height="12" rx="3" fill="{colour}" opacity="0.55"/></g>'
            )
        body.append(
            f"<g><title>observed rho {cp['rho_obs']:.3f}</title>"
            f'<line x1="{x(cp["rho_obs"]):.1f}" x2="{x(cp["rho_obs"]):.1f}" y1="{y0 + 2}" y2="{y0 + 72}" stroke="var(--ink)" stroke-width="2.5"/>'
            f'<circle cx="{x(cp["rho_obs"]):.1f}" cy="{y0 + 36}" r="5" fill="var(--ink)"/></g>'
        )
        flip = x(cp["rho_obs"]) > width - 300
        anchor = "end" if flip else "start"
        body.append(
            f'<text class="sm" x="{x(cp["rho_obs"]) + (-9 if flip else 9):.1f}" y="{y0 + 88}" '
            f'text-anchor="{anchor}">observed ρ {cp["rho_obs"]:.3f} '
            f"(Δρ {p['delta_rho']:.2f} vs same-density null)</text>"
        )
    legend_y = top + row_h * len(org.chapters) + 14
    body.append(
        f'<rect x="{left}" y="{legend_y - 9}" width="10" height="10" rx="2" fill="var(--ref)" opacity="0.55"/>'
        f'<text class="sm" x="{left + 14}" y="{legend_y}">same-density null</text>'
        f'<rect x="{left + 140}" y="{legend_y - 9}" width="10" height="10" rx="2" fill="var(--s3)" opacity="0.55"/>'
        f'<text class="sm" x="{left + 154}" y="{legend_y}">degree-preserving null</text>'
        f'<rect x="{left + 290}" y="{legend_y - 9}" width="10" height="10" rx="2" fill="var(--s4)" opacity="0.55"/>'
        f'<text class="sm" x="{left + 304}" y="{legend_y}">hub-heavy random graph (Δρ 0.08 to 0.14)</text>'
    )
    body.append(
        f'<text class="t2 sm" x="12" y="{legend_y + 18}">Label rule (unchanged): z ≥ 2 and Δρ ≥ 0.10 = present. '
        "An observed ρ only modestly above the hub-heavy band means the core is mostly a few hubs.</text>"
    )
    height = legend_y + 62
    return wrap_svg(
        width,
        height,
        "".join(body),
        "Core–periphery fit per chapter against null models",
        prov.footer(TAG),
    )


def events_svg(org: OrgData, prov: Provenance) -> str:
    kinds = [
        "community_birth",
        "community_continue",
        "community_grow",
        "community_shrink",
        "community_merge",
        "community_split",
        "community_death",
    ]
    cats = [f"ch{c}" for c in org.chapters]
    series = {
        k.replace("community_", ""): [
            sum(1 for e in org.events[c] if e["type"] == k) for c in org.chapters
        ]
        for k in kinds
    }
    series = {k: v for k, v in series.items() if any(v)}
    return stacked_bar_svg(
        "Community events per chapter",
        cats,
        series,
        provenance=prov,
        label_source=TAG,
        width=660,
        height=320,
    )


def trajectory_svg(org: OrgData, names: list[str], prov: Provenance) -> str:
    """Slope graph of adjusted importance across chapters for the key concepts; late centralisers
    and fading concepts are highlighted (event-driven, not by rank)."""
    width, row_top, left, right = 760, 56, 190, 190
    chs = org.chapters
    by_name = {ch: {r["name"]: r for r in org.nodes[ch]} for ch in chs}
    late = {
        e["subject_ids"][0] for ch in chs for e in org.events[ch] if e["type"] == "late_centraliser"
    }
    fading = {e["subject_ids"][0] for ch in chs for e in org.events[ch] if e["type"] == "fading"}
    ph = 360
    xs = {ch: left + (width - left - right) * i / max(len(chs) - 1, 1) for i, ch in enumerate(chs)}
    y = lambda v: row_top + ph * (1 - v)
    body = [
        f'<line class="ax" x1="{left}" x2="{width - right}" y1="{row_top + ph}" y2="{row_top + ph}"/>'
    ]
    for ch in chs:
        body.append(
            f'<text class="t2 sm" x="{xs[ch]:.1f}" y="{row_top + ph + 16}" text-anchor="middle">ch{ch}</text>'
        )
    for name in names:
        pts = [
            (ch, by_name[ch][name])
            for ch in chs
            if name in by_name[ch] and by_name[ch][name]["ring"] not in ("unlinked", "background")
        ]
        if len(pts) < 1:
            continue
        cid = pts[0][1]["concept_id"]
        colour = "var(--s1)" if cid in late else ("var(--s2)" if cid in fading else "var(--ref)")
        width_l = 2.6 if cid in late or cid in fading else 1.3
        path = " ".join(f"{xs[c]:.1f},{y(r['importance_adj']):.1f}" for c, r in pts)
        body.append(
            f'<g><title>{escape(name)}</title><polyline points="{path}" fill="none" stroke="{colour}" stroke-width="{width_l}"/>'
        )
        for c, r in pts:
            body.append(
                f'<circle cx="{xs[c]:.1f}" cy="{y(r["importance_adj"]):.1f}" r="3.5" fill="{colour}" stroke="var(--bg)" stroke-width="1.5"/>'
            )
        body.append("</g>")
        first, lastp = pts[0], pts[-1]
        body.append(
            f'<text class="sm" x="{xs[first[0]] - 8:.1f}" y="{y(first[1]["importance_adj"]) + 4:.1f}" text-anchor="end">{escape(name)}</text>'
        )
        if len(pts) > 1:
            body.append(
                f'<text class="sm" x="{xs[lastp[0]] + 8:.1f}" y="{y(lastp[1]["importance_adj"]) + 4:.1f}">{escape(name)}</text>'
            )
    body.append(
        f'<rect x="{left}" y="34" width="10" height="10" rx="2" fill="var(--s1)"/><text class="sm" x="{left + 14}" y="43">late centraliser</text>'
        f'<rect x="{left + 130}" y="34" width="10" height="10" rx="2" fill="var(--s2)"/><text class="sm" x="{left + 144}" y="43">fading</text>'
        f'<rect x="{left + 200}" y="34" width="10" height="10" rx="2" fill="var(--ref)"/><text class="sm" x="{left + 214}" y="43">other</text>'
    )
    height = row_top + ph + 74
    return wrap_svg(
        width,
        height,
        "".join(body),
        "Adjusted importance across chapters, key concepts",
        prov.footer(TAG),
    )


# ------------------------------------------------------------------------- sphere disc
def ring_radii(cfg: OrgConfig) -> list[float]:
    """Radii of the ring boundaries (centre|inner, inner|middle, middle|outer) at the cumulative
    quantile shares, in the same units as node radii."""
    lay, sh = cfg.layout, cfg.rings.shares
    cum, out = 0.0, []
    for name in DISC_RINGS[:-1]:
        cum += sh[name]
        out.append(lay.r_min + cum * (lay.r_max - lay.r_min))
    return out


def sphere_svg(
    org: OrgData,
    inp: OrgInputs,
    ch: int,
    cfg: OrgConfig,
    prov: Provenance,
    *,
    basis: str = "adj",
    size: int = 760,
    label_top: int = 22,
) -> str:
    """Static sphere at chapter `ch` (0 = the book only). Default filter: centre, inner and
    middle rings, like the interactive view; the unlinked count is stated on the figure."""
    cx, cy = size / 2, size / 2 + 8
    scale = size * 0.42 / (ring_radii(cfg)[-1] * 1.08)  # fit the shown rings (outer hidden)
    body = []
    title = f"Knowledge sphere at chapter {ch}" if ch else "Knowledge sphere at the start"
    if ch == 0:
        body.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="var(--ink)"/>')
        body.append(
            f'<text class="sm" x="{cx}" y="{cy + 26}" text-anchor="middle">{escape(BOOK)}</text>'
        )
        body.append(
            f'<text class="t2 sm" x="{cx}" y="{cy + 44}" text-anchor="middle">a virtual centre label, not a knowledge-graph node; concepts appear from chapter {org.chapters[0]}</text>'
        )
        return wrap_svg(size, size, "".join(body), title, prov.footer(TAG))
    for r in ring_radii(cfg):
        body.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r * scale:.1f}" fill="none" stroke="var(--grid)" stroke-width="1"/>'
        )
    edges_r = [cfg.layout.r_min, *ring_radii(cfg), cfg.layout.r_max]
    for name, (r0, r1) in zip(
        ["centre", "inner", "middle", "outer"], pairwise(edges_r), strict=True
    ):
        body.append(
            f'<text class="t2 sm" x="{cx + 6}" y="{cy - (r0 + r1) / 2 * scale + 4:.1f}">{name}</text>'
        )
    rk, rd = ("ring_adj", "radius_adj") if basis == "adj" else ("ring_raw", "radius_raw")
    ik = "importance_adj" if basis == "adj" else "importance_raw"
    vis = [r for r in org.nodes[ch] if r[rk] in cfg.layout.default_visible_rings]
    pos = {
        r["concept_id"]: (
            cx + r[rd] * scale * math.cos(math.radians(r["angle_deg"])),
            cy + r[rd] * scale * math.sin(math.radians(r["angle_deg"])),
        )
        for r in vis
    }
    for e in inp.edges:
        if e.chapter <= ch and e.source in pos and e.target in pos:
            a, b = pos[e.source], pos[e.target]
            body.append(
                f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="var(--ref)" stroke-width="0.8" opacity="0.45"/>'
            )
    moved = {
        e["subject_ids"][0]: e["type"]
        for e in org.events[ch]
        if e["type"] in ("ring_in", "ring_out")
    }
    for r in sorted(vis, key=lambda r: r[ik]):
        x, y = pos[r["concept_id"]]
        rad = 3 + 8 * r[ik]
        new = r["first_chapter"] == ch and org.chapters[0] != ch
        tip = escape(
            f"{r['name']} · {r[rk]} · importance {r[ik]:.2f} · introduced ch{r['first_chapter']}"
        )
        body.append(
            f"<g><title>{tip}</title>"
            + (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad + 4:.1f}" fill="none" stroke="var(--ink)" stroke-width="1.5"/>'
                if new
                else ""
            )
            + f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{slot(chapter_slot(r["first_chapter"]))}" stroke="var(--bg)" stroke-width="1.5"/></g>'
        )
        mv = moved.get(r["concept_id"])
        if mv:
            d = -1 if mv == "ring_in" else 1
            body.append(
                f'<path d="M{x + rad + 3:.1f},{y + 4 * d:.1f} l4,{-8 * d} l4,{8 * d} z" fill="var(--ink)"/>'
            )
    placed: list[tuple[float, float, float, float]] = []
    for r in sorted(vis, key=lambda r: -r[ik])[:label_top]:
        x, y = pos[r["concept_id"]]
        w, h = 6.2 * len(r["name"]), 12.0
        box = (x - w / 2, y - 3 - 8 * r[ik] - 4 - h, x + w / 2, y - 3 - 8 * r[ik] - 4)
        if any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3] for q in placed):
            continue
        placed.append(box)
        body.append(
            f'<text class="sm" x="{x:.1f}" y="{y - 3 - 8 * r[ik] - 4:.1f}" text-anchor="middle" style="paint-order:stroke;stroke:var(--bg);stroke-width:3px">{escape(r["name"])}</text>'
        )
    s = org.summary(ch)
    shown, hidden = len(vis), s["n_eligible"] - len(vis)
    body.append(f'<text class="sm" x="12" y="{size - 66}">{escape(unlinked_text(org, ch))}</text>')
    body.append(
        f'<text class="t2 sm" x="12" y="{size - 48}">Showing centre, inner and middle rings ({shown} concepts); {hidden} outer-ring concepts hidden. Ring = quantile band of adjusted importance; rings are not tiers.</text>'
    )
    banner = banner_for(org, ch)
    if banner:
        body.append(
            f'<rect x="12" y="30" width="{size - 24}" height="22" rx="4" fill="{STATUS["warning"]}" opacity="0.35"/><text class="sm" x="20" y="45">{escape(banner)}</text>'
        )
    body.append(
        f'<circle cx="{size - 200}" cy="30" r="5" fill="{slot(0)}"/><text class="sm" x="{size - 190}" y="34">first in ch2</text>'
        f'<circle cx="{size - 110}" cy="30" r="5" fill="{slot(1)}"/><text class="sm" x="{size - 100}" y="34">first in ch3</text>'
    ) if not banner else None
    return wrap_svg(size, size, "".join(body), title, prov.footer(TAG))


# ------------------------------------------------------------------------- interactive payload
def sphere_payload(org: OrgData, inp: OrgInputs, cfg: OrgConfig) -> dict:
    """Compact JSON for the interactive Sphere mode. `sph[concept][chapter]` is
    [ring_adj, ring_raw, radius_adj, radius_raw, angle, imp_adj, imp_raw, pagerank, coreness,
     spread, bridging, exposure_sections, n_typed_edges, persistent_unlinked, persistent_periphery]."""
    edge = {e.edge_id: e for e in inp.edges}
    name = {c: k.name for c, k in inp.concepts.items()}
    sph: dict[str, dict[str, list]] = {}
    for ch in org.chapters:
        for r in org.nodes[ch]:
            comp = r["components"]
            sph.setdefault(r["concept_id"], {})[str(ch)] = [
                r["ring_adj"],
                r["ring_raw"],
                round(r["radius_adj"], 4),
                round(r["radius_raw"], 4),
                round(r["angle_deg"], 2),
                round(r["importance_adj"], 4),
                round(r["importance_raw"], 4),
                round(comp["pagerank"], 5),
                comp["coreness"],
                round(comp["spread"], 4),
                round(comp["bridging"], 4),
                r["exposure_sections"],
                r["n_typed_edges"],
                r["persistent_unlinked"],
                r["persistent_periphery"],
            ]
    why: dict[str, dict[str, list]] = {}
    for ch in org.chapters:
        for ev in org.events[ch]:
            if ev["type"].startswith("community_") or not ev["subject_ids"]:
                continue
            edges = [
                {
                    "id": i,
                    "rel": edge[i].relation,
                    "s": name[edge[i].source],
                    "t": name[edge[i].target],
                    "section": edge[i].section_id,
                }
                for i in ev["because_edge_ids"]
                if i in edge
            ]
            why.setdefault(str(ch), {}).setdefault(ev["subject_ids"][0], []).append(
                {
                    "type": ev["type"],
                    "from": ev["from_state"],
                    "to": ev["to_state"],
                    "delta": ev["delta_importance"],
                    "edges": edges,
                }
            )
    counts, cps = {}, {}
    for ch in org.chapters:
        s = org.summary(ch)
        counts[str(ch)] = {
            "n_nodes": s["n_nodes"],
            "n_edges": s["n_edges"],
            "n_unlinked": s["n_unlinked"],
            "n_eligible": s["n_eligible"],
            "n_background": s["n_background"],
            "unlinked_text": unlinked_text(org, ch),
            "persistent_unlinked": sum(1 for r in org.nodes[ch] if r["persistent_unlinked"]),
            "persistent_periphery": sum(1 for r in org.nodes[ch] if r["persistent_periphery"]),
        }
        cp = org.cp(ch)
        cps[str(ch)] = {
            "label": cp["label"],
            "banner": cp["banner"],
            "rho": cp["rho_obs"],
            "z": cp["primary"]["z"],
            "delta": cp["primary"]["delta_rho"],
            "present": cp["label"] == LABEL_PRESENT,
        }
    return {
        "org_id": org.org_id,
        "chapters": [0, *org.chapters],
        "book": BOOK,
        "tag": "Structural metric (no human labels)",
        "radius_basis": org.manifest["radius_basis"],
        "ring_radii": ring_radii(cfg),
        "r_min": cfg.layout.r_min,
        "r_max": cfg.layout.r_max,
        "visible_rings": cfg.layout.default_visible_rings,
        "sph": sph,
        "why": why,
        "counts": counts,
        "cp": cps,
        "edge_chapter": {e.edge_id: e.chapter for e in inp.edges},
        "late_note": LATE_NOTE,
        "ba_range": list(BA_REFERENCE_DELTA_RHO),
    }
