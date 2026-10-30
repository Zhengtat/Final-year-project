"""CR-063 position-tolerant evaluation `IDXR1T{N}-P1` (owner, 2026-10-30): a predicted mention is the same as a gold mention when its
character start and end are each within N characters of the gold mention's. Evaluation only (SciNLP gold); reported beside `IDXR1-P1`
(rule 35). The prediction is the frozen `IDXR1-P1` one; matching spans are snapped to their gold span one-to-one (smallest total offset
first, ties in text order); relation endpoints use the same map; then the frozen strict scorer runs unchanged."""

from __future__ import annotations

from cumap.cr012 import scoring as S
from cumap.cr012.types import PRF
from cumap.cr019 import variants as V


def snap_map(doc, gold_spans: set, pred_spans: set, n: int) -> dict:
    """{predicted span: gold span} for predicted spans within n characters at both ends of a gold span (one-to-one)."""
    off = doc.token_offsets
    ch = lambda sp: (off[sp[0]][0], off[sp[1] - 1][1])  # noqa: E731
    exact = pred_spans & gold_spans
    free_g = sorted(gold_spans - exact)
    cands = []
    for p in sorted(pred_spans - exact):
        pa, pb = ch(p)
        for g in free_g:
            ga, gb = ch(g)
            if abs(pa - ga) <= n and abs(pb - gb) <= n:
                cands.append((abs(pa - ga) + abs(pb - gb), pa, p, g))
    out, used_g, used_p = {}, set(), set()
    for _d, _pa, p, g in sorted(cands):
        if p in used_p or g in used_g:
            continue
        out[p] = g
        used_p.add(p)
        used_g.add(g)
    return out


def score(doc, gold, cp: dict, sym: set[str], n: int) -> dict:
    """Same accounting as `cr019.variants.sc_score(..., "IDXR1-P1")`, with spans snapped within n characters."""
    base = V.sc_score(doc, gold, cp, sym, "IDXR1-P1")
    pred = base["pred"]
    pm = S.project_nodes_to_mentions(pred["nodes"])
    rels, _unplaced = S.project_edges_to_mentions(pred["nodes"], pred["edges"])
    m = snap_map(doc, {g.span for g in gold.mentions}, {s for s, _t in pm}, n)
    pm2 = sorted({(m.get(s, s), t) for s, t in pm})
    rels2 = [(m.get(a, a), m.get(b, b), rel, st, tt) for a, b, rel, st, tt in rels]
    res = S.score_scinlp_unit(gold, pm2, rels2, sym)
    r, r0 = res["rel"], base["scores"]["rel"]
    strict_fp_extra = r0.fp - S.score_scinlp_unit(gold, pm, rels, sym)["rel"].fp  # unplaced edges counted as FP by IDXR1-P1
    res["rel"] = PRF(r.tp, r.fp + strict_fp_extra, r.fn)
    return {"scores": res, "snapped": len(m)}
