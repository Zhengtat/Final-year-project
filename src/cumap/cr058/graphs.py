"""CR-058: gold graph and built graph of one SciNLP paper, with what was missed ($0, read-only).

Gold graph: SciNLP gold has mention-level relations and no identity gold, so gold mentions are grouped into pseudo-nodes by the CR-032 rule
(R1 name key plus unambiguous acronym <-> long form in the paper's own text; identity inferred from strings, labelled as such on the page).
Built graph: the run's final nodes placed under `IDXR1-P1` and its assembled edges. A built node matches the gold pseudo-node that shares
the most mention spans with it. Both graphs share one layout so the same concept sits in the same place in both panels."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

import networkx as nx

from cumap.cr012 import scoring as S
from cumap.cr032 import scinlp_t1 as ST
from cumap.cr054.recall import key
from cumap.cr058.funnel import _assembled, _endpoints

STAGE_LABEL = {
    "endpoints_placed": "N: an endpoint concept missing or wrong span",
    "pair_selected": "P: pair never classified",
    "family_right": "F: family step said no relation / other",
    "choice_right": "C: wrong relation or direction",
    "checks_passed": "K: dropped by a code check",
    "assembled": "A: dropped in assembly or unplaced",
    "credited": "E: right fact, evidence sentence not credited",
}


def _txt(doc, sp) -> str:
    return " ".join(doc.tokens[sp[0] : sp[1]])


def mention_losses(doc, gold, cp: dict, spans: set, trace: dict | None) -> dict:
    """{gold span: (stage, detail)} for every gold mention not placed exactly (the CR-054 trace; `trace` None = no concept-stage file)."""
    final = {
        key(f) for c in cp["concepts"] for f in [c["canonical_name"], *(c.get("aliases") or [])]
    }
    out = {}
    for m in gold.mentions:
        if m.span in spans:
            continue
        k = key(_txt(doc, m.span))
        over = [a for a in spans if a[0] < m.span[1] and m.span[0] < a[1]]
        if over:
            a = max(over, key=lambda x: min(x[1], m.span[1]) - max(x[0], m.span[0]))
            out[m.span] = ("span", "built: " + _txt(doc, a))
        elif k in final:
            out[m.span] = ("node_not_placed", "")
        elif trace is None:
            out[m.span] = ("not_found", "")
        elif k in trace["proposed"]:
            why = sorted(trace["dropped"].get(k, set())) or sorted(trace["merged"].get(k, set()))
            out[m.span] = ("lost_after_generator", ",".join(why) or (
                "not_in_final_graph" if k in trace["gen_nodes"] else "dropped_in_later_iteration"))  # fmt: skip
        elif k in trace["hints"]:
            out[m.span] = ("hint_rejected", trace["hints"][k][:120])
        else:
            out[m.span] = ("never_proposed", "")
    return out


def _layout(
    nodes: list[str], edges: list[tuple[str, str]], seed: int = 7
) -> dict[str, list[float]]:
    """Connected nodes by a seeded spring layout in the upper area; isolated nodes on a grid below (x, y in [0, 1000])."""
    G = nx.Graph()
    G.add_nodes_from(nodes)
    G.add_edges_from((a, b) for a, b in edges if a != b)
    linked = [n for n in nodes if G.degree(n) > 0]
    pos: dict[str, list[float]] = {}
    height = 600.0
    if linked:
        sub = G.subgraph(linked)
        p = nx.spring_layout(sub, seed=seed, k=1.6 / math.sqrt(max(len(linked), 1)), iterations=200)
        xs, ys = [v[0] for v in p.values()], [v[1] for v in p.values()]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        for n, (x, y) in p.items():
            pos[n] = [round(40 + 920 * (x - x0) / ((x1 - x0) or 1), 1), round(40 + (height - 80) * (y - y0) / ((y1 - y0) or 1), 1)]  # fmt: skip
    iso = sorted(n for n in nodes if n not in pos)
    cols = 24
    for i, n in enumerate(iso):
        pos[n] = [
            round(30 + (i % cols) * (940 / (cols - 1)), 1),
            round(height + 30 + (i // cols) * 34, 1),
        ]
    return pos


def build(
    doc, gold, cp: dict, pred: dict, lost_at: list[str], sym: set[str], trace: dict | None
) -> dict:
    """Graph payload for the page (plain JSON)."""
    ident, _ = ST.r1_identity(doc)
    gtype: dict[str, Counter] = defaultdict(Counter)
    gsurf: dict[str, Counter] = defaultdict(Counter)
    gspans: dict[str, list] = defaultdict(list)
    for m in gold.mentions:
        gid = "g:" + ident(m.span)
        gtype[gid][m.type] += 1
        gsurf[gid][_txt(doc, m.span)] += 1
        gspans[gid].append(m.span)
    nodes = pred["nodes"]
    spans = {sp for n in nodes for sp in n.mentions}
    losses = mention_losses(doc, gold, cp, spans, trace)
    by_gspan = {m.span: "g:" + ident(m.span) for m in gold.mentions}
    gold_nodes, missed = [], []
    for gid, sps in gspans.items():
        exact = sum(sp in spans for sp in sps)
        partial = sum(sp in losses and losses[sp][0] == "span" for sp in sps)
        st = "found" if exact else "partial" if partial else "missed"
        loss = Counter(losses[sp][0] for sp in sps if sp in losses)
        gold_nodes.append({"id": gid, "label": gsurf[gid].most_common(1)[0][0], "type": gtype[gid].most_common(1)[0][0],
                           "n": len(sps), "found": exact, "status": st, "loss": dict(loss),
                           "surfaces": [s for s, _ in gsurf[gid].most_common(6)]})  # fmt: skip
    for m in gold.mentions:
        if m.span in losses:
            stg, why = losses[m.span]
            missed.append({"text": _txt(doc, m.span), "type": m.type, "stage": stg, "detail": why,
                           "node": by_gspan[m.span]})  # fmt: skip
    built_nodes, to_union = [], {}
    for n in nodes:
        hits = Counter(by_gspan[sp] for sp in n.mentions if sp in by_gspan)
        gid = hits.most_common(1)[0][0] if hits else None
        to_union[n.node_id] = gid or "b:" + n.node_id
        built_nodes.append({"id": "b:" + n.node_id, "u": to_union[n.node_id], "label": n.name, "type": n.type,
                            "n": len(n.mentions), "gold_mentions": sum(hits.values()),
                            "status": "gold" if gid else "non_gold", "gold_id": gid})  # fmt: skip
    gold_edges: dict[tuple, dict] = {}
    for g, at in zip(gold.relations, lost_at, strict=True):
        a, b = by_gspan[g.src_span], by_gspan[g.tgt_span]
        k = (*sorted((a, b)), g.relation) if g.relation in sym else (a, b, g.relation)
        e = gold_edges.setdefault(k, {"s": k[0], "t": k[1], "rel": g.relation, "sym": g.relation in sym,
                                      "n": 0, "credited": 0, "lost": Counter(), "example": ""})  # fmt: skip
        e["n"] += 1
        if at == "credited":
            e["credited"] += 1
        else:
            e["lost"][at] += 1
        if not e["example"]:
            e["example"] = f"{_txt(doc, g.src_span)} -[{g.relation}]-> {_txt(doc, g.tgt_span)}"
    gk = {S._rel_key(r.src_span, r.tgt_span, r.relation, sym) for r in gold.relations}
    left = Counter((e.src, e.tgt, e.relation) for e in pred["edges"])
    by_triple = defaultdict(list)
    for e in pred["edges"]:
        by_triple[(e.src, e.tgt, e.relation)].append(e)
    ids = {n.node_id for n in nodes}
    built_edges = []
    for r in cp["relation_results_v3"]:
        if not _assembled(r):
            continue
        s, t = _endpoints(r)
        tri = (s, t, r["relation"])
        placed = left[tri] > 0
        ok = False
        if placed:
            left[tri] -= 1
            e = by_triple[tri][left[tri]]
            rels, _ = S.project_edges_to_mentions(nodes, [e])
            ok = any(S._rel_key(a, b, rel, sym) in gk for a, b, rel, _x, _y in rels)
        if s not in ids or t not in ids:
            continue  # an endpoint with no placed mention: counted as an unplaced FP in the scores, not drawable
        built_edges.append({"s": "b:" + s, "t": "b:" + t, "rel": r["relation"], "sym": r["relation"] in sym,
                            "status": "correct" if ok else "wrong", "placed": placed,
                            "quote": (r.get("evidence_quote") or "")[:240]})  # fmt: skip
    union_nodes = list(gspans) + [u for u in to_union.values() if u.startswith("b:")]
    union_edges = [(e["s"], e["t"]) for e in gold_edges.values()] + [
        (to_union[e["s"][2:]], to_union[e["t"][2:]]) for e in built_edges
    ]
    pos = _layout(sorted(set(union_nodes)), union_edges)
    ge = []
    for e in gold_edges.values():
        status = "credited" if e["credited"] else e["lost"].most_common(1)[0][0]
        ge.append({**e, "lost": dict(e["lost"]), "status": status})
    return {"gold_nodes": gold_nodes, "built_nodes": built_nodes, "gold_edges": ge, "built_edges": built_edges,
            "pos": pos, "missed_mentions": missed}  # fmt: skip
