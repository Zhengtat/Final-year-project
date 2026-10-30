"""CR-063 grounding variant `IDXR1S-P1` (rule 35: reported beside `IDXR1-P1`, never instead of it unless the owner decides).

`MentionMatcher` tokens are runs of letters and digits, so every placed span ends at a word and a name ending in symbols ("Vector Space
Model ( VSM )", "RNMT+", "weighted A*") loses them. This variant takes the frozen `IDXR1-P1` placement and extends each placed span of a node
over the trailing symbols of one of the node's forms when (a) the span's R1 key equals that form's R1 key and (b) the following text tokens
spell exactly those symbols (spacing ignored). Spans of other nodes lying inside an extended span are dropped (rule 17, longest match).
Domain-free; the frozen matchers and scorers are not edited."""

from __future__ import annotations

import dataclasses
import re

from cumap.cr012 import scoring as S
from cumap.cr012.types import PRF
from cumap.cr019 import variants as V
from cumap.expert_kg.alias_rules import AliasConfig, r1_key

VARIANT = "IDXR1S-P1"
_CFG = AliasConfig.load()
_TRAIL = re.compile(r"[\w]((?:\s*[^\w\s])+)\s*$")


def trailing_symbols(form: str) -> str:
    """The symbols a form ends with, spacing removed ("X ( VSM )" -> ")", "RNMT+" -> "+"); "" when it ends with a word."""
    m = _TRAIL.search(form or "")
    return re.sub(r"\s+", "", m.group(1)) if m else ""


def extend_span(tokens: list[str], sp: tuple[int, int], forms: list[str]) -> tuple[int, int]:
    s, e = sp
    k = r1_key(" ".join(tokens[s:e]), _CFG)
    for f in forms:
        sym = trailing_symbols(f)
        if not sym or r1_key(f, _CFG) != k:
            continue
        acc, j = "", e
        while j < len(tokens) and len(acc) < len(sym):
            acc += tokens[j]
            j += 1
        if acc == sym:
            return (s, j)
    return sp


def predict(doc, cp: dict) -> dict:
    pred = V.sc_predict_indexed(doc, cp, "r1key")
    forms = {
        c["concept_id"]: [c["canonical_name"], *(c.get("aliases") or [])] for c in cp["concepts"]
    }
    ext: dict[str, set] = {}
    grown: list[tuple[int, int, str]] = []
    for n in pred["nodes"]:
        out = set()
        for sp in n.mentions:
            new = extend_span(doc.tokens, sp, forms.get(n.node_id, []))
            out.add(new)
            if new != sp:
                grown.append((*new, n.node_id))
        ext[n.node_id] = out
    dropped = 0
    for a, b, _owner in grown:
        for nid, sps in ext.items():
            inside = {x for x in sps if a <= x[0] and x[1] <= b and x != (a, b)}
            if inside:
                dropped += len(inside)
                ext[nid] = sps - inside
    nodes = [
        dataclasses.replace(n, mentions=tuple(sorted(ext[n.node_id])))
        for n in pred["nodes"]
        if ext[n.node_id]
    ]
    stats = {**pred["stats"], "spans_extended": len(grown), "nested_spans_dropped": dropped}
    return {**pred, "nodes": nodes, "stats": stats}


def score(doc, gold, cp: dict, sym: set[str]) -> dict:
    """Same accounting as `cr019.variants.sc_score` for an `IDX*-P1` variant: unplaced edges count as false positives."""
    pred = predict(doc, cp)
    ids = {n.node_id for n in pred["nodes"]}
    edges = [e for e in pred["edges"] if e.src in ids and e.tgt in ids]
    lost = len(pred["edges"]) - len(edges)
    rels, unplaced = S.project_edges_to_mentions(pred["nodes"], edges)
    res = S.score_scinlp_unit(gold, S.project_nodes_to_mentions(pred["nodes"]), rels, sym)
    r = res["rel"]
    res["rel"] = PRF(
        r.tp, r.fp + unplaced + lost + pred["stats"]["edges_without_node_or_quote"], r.fn
    )
    return {"scores": res, "pred": pred}
