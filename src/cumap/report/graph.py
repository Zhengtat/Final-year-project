"""Deterministic graph layout (networkx, fixed seed) and SVG rendering for the report.

Two views share one renderer: a per-section relation graph (edges coloured by family,
dashed when negated, arrowheads) and the whole-run growth graph (node colour = chapter
where the concept was first introduced, size = number of sections mentioning it, cross-
chapter edges emphasised). The growth graph is rendered once with data-* attributes; the
page's JS only shows/hides elements (chapter slider, top-N filter, prerequisite halos).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from html import escape

import networkx as nx

from cumap.report.provenance import Provenance
from cumap.report.svg import slot, wrap_svg

FAMILY_ORDER = [
    "classification_structure",
    "function_means",
    "comparison",
    "dependency",
    "cause_effect",
    "mechanism_process",
    "pedagogical",
]
CHAPTER_SLOTS = {2: 0, 3: 1}  # ch2 blue, ch3 orange; other chapters fall back by order


def family_slot(family: str) -> int:
    return FAMILY_ORDER.index(family) if family in FAMILY_ORDER else len(FAMILY_ORDER)


def chapter_slot(chapter: int) -> int:
    return CHAPTER_SLOTS.get(chapter, (chapter - 1) % 8)


@dataclass
class GNode:
    id: str
    label: str
    chapter: int = 0
    size: int = 1  # sections mentioning
    aliases: list[str] = field(default_factory=list)
    prereq: bool = False
    rank: int = 0


@dataclass
class GEdge:
    id: str
    source: str
    target: str
    relation: str
    family: str
    negated: bool = False
    chapter: int = 0
    cross: bool = False


def layout(
    node_ids: list[str], edges: list[tuple[str, str]], *, width: int, height: int, seed: int = 42
) -> dict[str, tuple[float, float]]:
    """Each connected component gets its own Kamada-Kawai layout (deterministic, no seed needed) inside a box sized by its node
    count; boxes are shelf-packed largest-first, then everything is uniformly scaled to fit.
    Isolated nodes (input order preserved) go on a grid strip under the connected part.
    Same input -> same output (fixed seed, sorted iteration).
    """
    g = nx.Graph()
    g.add_edges_from(sorted(edges))
    connected = set(g.nodes)
    isolated = [n for n in node_ids if n not in connected]
    comps = sorted((sorted(c) for c in nx.connected_components(g)), key=lambda c: (-len(c), c[0]))
    main_h = height if not isolated else height * 0.72

    boxes: list[tuple[list[str], float, float]] = []
    for comp in comps:
        side = 70 + 60 * math.sqrt(len(comp)) if len(comp) > 2 else 130
        boxes.append((comp, side * (1.25 if len(comp) > 2 else 1.0), side))
    # shelf packing at a nominal row width proportional to the biggest box
    row_w = max(b[1] for b in boxes) * 1.4 if boxes else 1.0
    placed: list[tuple[list[str], float, float, float, float]] = []
    x = y = row_h = 0.0
    for comp, bw, bh in boxes:
        if x + bw > row_w and x > 0:
            x, y, row_h = 0.0, y + row_h, 0.0
        placed.append((comp, x, y, bw, bh))
        x += bw
        row_h = max(row_h, bh)
    total_w = max((px + bw for _, px, _, bw, _ in placed), default=1.0)
    total_h = max((py + bh for _, _, py, _, bh in placed), default=1.0)
    scale = min((width - 180) / total_w, (main_h - 96) / total_h)
    ox = 90 + ((width - 180) - total_w * scale) / 2
    pos: dict[str, tuple[float, float]] = {}
    for comp, px, py, bw, bh in placed:
        sub = g.subgraph(comp)
        if len(comp) == 1:
            raw = {comp[0]: (0.0, 0.0)}
        elif len(comp) == 2:
            raw = {comp[0]: (-1.0, 0.0), comp[1]: (1.0, 0.0)}
        else:
            raw = nx.kamada_kawai_layout(sub)
        xs = [v[0] for v in raw.values()]
        ys = [v[1] for v in raw.values()]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        for n, (vx, vy) in raw.items():
            fx = (vx - x0) / (x1 - x0) if x1 > x0 else 0.5
            fy = (vy - y0) / (y1 - y0) if y1 > y0 else 0.5
            pos[n] = (
                ox + (px + 0.06 * bw + fx * 0.88 * bw) * scale,
                56 + (py + 0.06 * bh + fy * 0.88 * bh) * scale,
            )
    cols = max(1, int((width - 60) // 44))
    base = 56 + total_h * scale + 30 if connected else 56
    for i, n in enumerate(isolated):
        pos[n] = (34 + (i % cols) * 44, base + (i // cols) * 30)
    return pos


def _node_radius(size: int) -> float:
    return 4 + 2.2 * math.sqrt(max(size, 1))


def _legend_row(items: list[tuple[str, str]], y: int, x: int = 12) -> str:
    out, cx = [], x
    for name, colour in items:
        out.append(f'<circle cx="{cx + 5}" cy="{y - 4}" r="5" fill="{colour}"/>')
        out.append(f'<text class="sm" x="{cx + 14}" y="{y}">{escape(name)}</text>')
        cx += 30 + 6.3 * len(name)
    return "".join(out)


def _edge_geometry(p: tuple[float, float], q: tuple[float, float], r_target: float):
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = math.hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d
    return p[0], p[1], q[0] - ux * (r_target + 3), q[1] - uy * (r_target + 3)


def render_section_graph(
    title: str,
    nodes: list[GNode],
    edges: list[GEdge],
    *,
    provenance: Provenance,
    label_source: str,
    width: int = 1000,
    height: int = 680,
) -> str:
    footer = provenance.footer(label_source)
    pos = layout(
        [n.id for n in nodes],
        [(e.source, e.target) for e in edges],
        width=width,
        height=height - 40,
    )
    families = sorted({e.family for e in edges}, key=family_slot)
    defs = "".join(
        f'<marker id="ar{family_slot(f)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" '
        f'fill="{slot(family_slot(f))}"/></marker>'
        for f in families
    )
    body = [f"<defs>{defs}</defs>"]
    by_id = {n.id: n for n in nodes}
    for e in edges:
        if e.source not in pos or e.target not in pos:
            continue
        x1, y1, x2, y2 = _edge_geometry(pos[e.source], pos[e.target], 8)
        c = slot(family_slot(e.family))
        dash = ' stroke-dasharray="6 4"' if e.negated else ""
        sn, tn = by_id[e.source].label, by_id[e.target].label
        tip = escape(f"{sn} —[{e.relation}{' (negated)' if e.negated else ''}]→ {tn}")
        body.append(
            f'<g class="edge" data-edge="{escape(e.id)}" style="cursor:pointer"><title>{tip}</title>'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" '
            f'stroke-width="2"{dash} marker-end="url(#ar{family_slot(e.family)})"/>'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="transparent" '
            f'stroke-width="14"/>'
            f'<text class="sm t2" x="{(x1 + x2) / 2:.1f}" y="{(y1 + y2) / 2 - 4:.1f}" '
            f'text-anchor="middle">{escape(e.relation)}</text></g>'
        )
    for n in nodes:
        if n.id not in pos:
            continue
        x, y = pos[n.id]
        body.append(
            f'<g><title>{escape(n.label)}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="8" '
            f'fill="var(--bg)" stroke="var(--ink2)" stroke-width="2"/>'
            f'<text class="sm" x="{x:.1f}" y="{y + 22:.1f}" text-anchor="middle" '
            f'style="paint-order:stroke;stroke:var(--bg);stroke-width:3px">{escape(n.label)}</text></g>'
        )
    body.append(_legend_row([(f, slot(family_slot(f))) for f in families], 36))
    if any(e.negated for e in edges):
        body.append(
            f'<text class="t2 sm" x="{width - 12}" y="36" text-anchor="end">dashed = negated</text>'
        )
    return wrap_svg(width, height, "".join(body), title, footer)


def render_growth_graph(
    title: str,
    nodes: list[GNode],
    edges: list[GEdge],
    *,
    provenance: Provenance,
    label_source: str,
    width: int = 1300,
    height: int = 1000,
    label_top: int = 35,
) -> str:
    """One SVG holding every node/edge with data-* attributes; ranked by `GNode.rank`
    (0 = most important). JS filters on data-ch / data-rank / data-cross / data-prereq.
    """
    footer = provenance.footer(label_source)
    ordered = sorted(nodes, key=lambda n: n.rank)
    pos = layout(
        [n.id for n in ordered],
        [(e.source, e.target) for e in edges],
        width=width,
        height=height - 60,
    )
    chapters = sorted({n.chapter for n in nodes})
    body = ['<g id="g-edges">']
    for e in edges:
        if e.source not in pos or e.target not in pos:
            continue
        x1, y1, x2, y2 = _edge_geometry(pos[e.source], pos[e.target], 6)
        cls = "xe" if e.cross else "e"
        stroke = "var(--ink)" if e.cross else "var(--ref)"
        sw = 2.4 if e.cross else 1.2
        body.append(
            f'<g class="edge {cls}" data-edge="{escape(e.id)}" data-ch="{e.chapter}" '
            f'data-cross="{int(e.cross)}" data-s="{escape(e.source)}" data-t="{escape(e.target)}" '
            f'style="cursor:pointer"><title>{escape(e.source)} —[{escape(e.relation)}]→ {escape(e.target)}</title>'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
            f'stroke-width="{sw}" opacity="0.8"/>'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="transparent" '
            f'stroke-width="10"/></g>'
        )
    body.append('</g><g id="g-nodes">')
    for n in ordered:
        if n.id not in pos:
            continue
        x, y = pos[n.id]
        r = _node_radius(n.size)
        alias = (
            f" · {len(n.aliases)} alias{'es' if len(n.aliases) != 1 else ''}" if n.aliases else ""
        )
        tip = escape(f"{n.label} · introduced ch{n.chapter} · in {n.size} section(s){alias}")
        halo = (
            f'<circle class="halo" cx="{x:.1f}" cy="{y:.1f}" r="{r + 5:.1f}" fill="none" '
            f'stroke="var(--ink)" stroke-width="2" stroke-dasharray="3 3"/>'
            if n.prereq
            else ""
        )
        label = (
            f'<text class="sm nl" x="{x:.1f}" y="{y + r + 12:.1f}" text-anchor="middle" '
            f'style="paint-order:stroke;stroke:var(--bg);stroke-width:3px">{escape(n.label)}</text>'
            if n.rank < label_top
            else ""
        )
        body.append(
            f'<g class="node" data-id="{escape(n.id)}" data-ch="{n.chapter}" data-rank="{n.rank}" '
            f'data-prereq="{int(n.prereq)}"><title>{tip}</title>{halo}'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{slot(chapter_slot(n.chapter))}" '
            f'stroke="var(--bg)" stroke-width="2"/>{label}</g>'
        )
    body.append("</g>")
    body.append(
        _legend_row([(f"first introduced ch{c}", slot(chapter_slot(c))) for c in chapters], 36)
    )
    return wrap_svg(width, height, "".join(body), title, footer)
