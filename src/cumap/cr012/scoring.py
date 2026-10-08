"""CR-012 scorers. Two, never mixed:

* `score_scinlp_unit` - the CR-012 SciNLP strict scorer (mention level, NOT the official scorer: the audited repository has none).
  Entity strict = exact span (+ type for typed). Relation strict = exact source span, exact target span, relation, direction unless
  symmetric; Rel+ also requires the endpoint types. No identity clusters are inferred from strings or aliases.
* `score_graph_unit` - the P&D-E2E canonical-graph scorer behind the headline `STRICT_E2E_EDGE_F1`: a predicted edge is correct only
  when source concept, target concept, endpoint types, relation and direction are all correct (orientation ignored for symmetric).

Counting rules (fixed here, tested): predicted items are de-duplicated by their match key; every predicted item beyond the first
that maps to an already matched gold item is a false positive (so a split canonical node costs precision); a gold item counts as
recalled at most once.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import product

from cumap.cr012.types import PRF, GoldMention, PredEdge, PredNode, Span, UnitGold


# ---------------------------------------------------------------- shared helpers
def prf(tp: int, fp: int, fn: int) -> PRF:
    return PRF(tp, fp, fn)


def _inside(inner: Span, outer: Span | None) -> bool:
    return outer is not None and outer[0] <= inner[0] and inner[1] <= outer[1]


def _rel_key(src: Span, tgt: Span, rel: str, symmetric: set[str]) -> tuple:
    return (frozenset((src, tgt)), rel) if rel in symmetric else (src, tgt, rel)


# ---------------------------------------------------------------- SciNLP strict scorer
def project_edges_to_mentions(
    nodes: list[PredNode], edges: list[PredEdge]
) -> tuple[list[tuple[Span, Span, str, str, str]], int]:
    """Project predicted canonical-node edges back to evidence-grounded source mentions: only mentions that lie inside the edge's
    own evidence span are used (every combination of an in-evidence source mention and target mention is one predicted mention-
    level relation). An edge without an evidence span, or with no mention of one endpoint inside it, cannot be grounded and is
    counted, not guessed. Returns (relations as (src_span, tgt_span, relation, src_type, tgt_type), ungrounded edge count)."""
    by_id = {n.node_id: n for n in nodes}
    out, ungrounded = [], 0
    for e in edges:
        s, t = by_id.get(e.src), by_id.get(e.tgt)
        if not s or not t:
            ungrounded += 1
            continue
        ms = [m for m in s.mentions if _inside(m, e.evidence_span)]
        mt = [m for m in t.mentions if _inside(m, e.evidence_span)]
        if not ms or not mt:
            ungrounded += 1
            continue
        out += [(a, b, e.relation, s.type, t.type) for a, b in product(ms, mt) if a != b]
    return out, ungrounded


def project_nodes_to_mentions(nodes: list[PredNode]) -> list[tuple[Span, str]]:
    return sorted({(m, n.type) for n in nodes for m in n.mentions})


def score_scinlp_unit(
    gold: UnitGold,
    pred_mentions: list[tuple[Span, str]],
    pred_relations: list[tuple[Span, Span, str, str, str]],
    symmetric: set[str],
) -> dict:
    gold_type = {m.span: m.type for m in gold.mentions}
    gm_span, pm_span = set(gold_type), {s for s, _t in pred_mentions}
    gm_typed, pm_typed = {(m.span, m.type) for m in gold.mentions}, set(pred_mentions)
    ent = prf(len(gm_span & pm_span), len(pm_span - gm_span), len(gm_span - pm_span))
    ent_t = prf(len(gm_typed & pm_typed), len(pm_typed - gm_typed), len(gm_typed - pm_typed))
    g_rel = {_rel_key(r.src_span, r.tgt_span, r.relation, symmetric) for r in gold.relations}
    g_rel_plus = {
        (
            *_rel_key(r.src_span, r.tgt_span, r.relation, symmetric),
            frozenset({gold_type.get(r.src_span), gold_type.get(r.tgt_span)})
            if r.relation in symmetric
            else (gold_type.get(r.src_span), gold_type.get(r.tgt_span)),
        )
        for r in gold.relations
    }
    p_rel, p_rel_plus = set(), set()
    for s, t, rel, st, tt in pred_relations:
        k = _rel_key(s, t, rel, symmetric)
        p_rel.add(k)
        p_rel_plus.add((*k, frozenset({st, tt}) if rel in symmetric else (st, tt)))
    rel = prf(len(g_rel & p_rel), len(p_rel - g_rel), len(g_rel - p_rel))
    rel_plus = prf(
        len(g_rel_plus & p_rel_plus), len(p_rel_plus - g_rel_plus), len(g_rel_plus - p_rel_plus)
    )
    return {"entity_strict": ent, "entity_typed": ent_t, "rel": rel, "rel_plus": rel_plus}


def aggregate_documents(per_doc: dict[str, dict], metric: str) -> dict:
    """D1: micro P/R/F1 over all documents, per-document P/R/F1, macro mean, min / max document F1. CI_status for a 3-document test
    split is NOT_EVALUABLE_SMALL_N; no entity / edge bootstrap, no dev + test pooling."""
    docs = {d: v[metric] for d, v in per_doc.items()}
    micro = prf(
        sum(x.tp for x in docs.values()),
        sum(x.fp for x in docs.values()),
        sum(x.fn for x in docs.values()),
    )
    f1s = [x.f1 for x in docs.values()]
    n = len(docs)
    return {
        "metric": metric,
        "documents": n,
        "micro": micro.to_dict(),
        "per_document": {d: x.to_dict() for d, x in sorted(docs.items())},
        "macro_mean": {
            k: sum(getattr(x, k) for x in docs.values()) / n for k in ("precision", "recall", "f1")
        }
        if n
        else None,
        "min_document_f1": min(f1s) if f1s else None,
        "max_document_f1": max(f1s) if f1s else None,
        "CI_status": "NOT_EVALUABLE_SMALL_N" if n < 10 else "EVALUABLE_DOCUMENT_BOOTSTRAP",
    }


# ---------------------------------------------------------------- P&D-E2E canonical-graph scorer
def align_nodes(nodes: list[PredNode], gold_mentions: list[GoldMention]) -> dict:
    """Map each predicted node to a gold concept through EXACT mention-span matches. A node whose mentions hit two gold concepts is a
    false merge (maps to nothing); a gold concept reached by two nodes is a split. Identity is never inferred from strings."""
    span_to_c = {m.span: m.concept_id for m in gold_mentions if m.concept_id}
    hit: dict[str, set[str]] = {
        n.node_id: {span_to_c[s] for s in n.mentions if s in span_to_c} for n in nodes
    }
    node_to_c = {nid: next(iter(c)) for nid, c in hit.items() if len(c) == 1}
    c_to_nodes: dict[str, list[str]] = defaultdict(list)
    for nid, c in node_to_c.items():
        c_to_nodes[c].append(nid)
    return {
        "node_to_concept": node_to_c,
        "concept_to_nodes": dict(c_to_nodes),
        "false_merge_nodes": sorted(nid for nid, c in hit.items() if len(c) >= 2),
        "unmatched_nodes": sorted(nid for nid, c in hit.items() if not c),
        "split_concepts": sorted(c for c, ns in c_to_nodes.items() if len(ns) > 1),
    }


def _edge_key(src: str, tgt: str, rel: str, symmetric: set[str]) -> tuple:
    return (frozenset((src, tgt)), rel) if rel in symmetric else (src, tgt, rel)


def score_graph_unit(
    gold: UnitGold,
    nodes: list[PredNode],
    edges: list[PredEdge],
    symmetric: set[str],
    proposed_pairs: set[frozenset[str]] | None = None,
    typed: bool = True,
) -> dict:
    """Strict E2E edge P/R/F1 plus the secondary diagnostics for one P&D-E2E section."""
    al = align_nodes(nodes, gold.mentions)
    c_type = {c.concept_id: c.type for c in gold.concepts}
    node_by = {n.node_id: n for n in nodes}
    n2c = al["node_to_concept"]
    # ---- concepts / nodes
    matched_c = set(n2c.values())
    typed_c = {c for nid, c in n2c.items() if node_by[nid].type == c_type.get(c)}
    node_tp = len(matched_c)
    canon = prf(node_tp, len(nodes) - node_tp, len(c_type) - node_tp)
    canon_typed = prf(len(typed_c), len(nodes) - len(typed_c), len(c_type) - len(typed_c))
    g_ment, p_ment = (
        {(m.span, m.type) for m in gold.mentions},
        {(s, n.type) for n in nodes for s in n.mentions},
    )
    concept_mentions = prf(len(g_ment & p_ment), len(p_ment - g_ment), len(g_ment - p_ment))
    # ---- headline: strict E2E edges
    gold_keys = {
        _edge_key(r.src_concept, r.tgt_concept, r.relation, symmetric): r
        for r in gold.relations
        if r.src_concept and r.tgt_concept
    }
    matched, correct_pred = set(), 0
    for e in edges:
        cs, ct = n2c.get(e.src), n2c.get(e.tgt)
        if cs is None or ct is None or cs == ct:
            continue
        if typed and (
            node_by[e.src].type != c_type.get(cs) or node_by[e.tgt].type != c_type.get(ct)
        ):
            continue
        k = _edge_key(cs, ct, e.relation, symmetric)
        if k in gold_keys and k not in matched:
            matched.add(k)
            correct_pred += 1
    strict = prf(correct_pred, len(edges) - correct_pred, len(gold_keys) - len(matched))
    # ---- identity (mention pairs over gold mentions) and B-cubed
    ident = identity_metrics(gold, nodes)
    # ---- pair recall: gold edges whose endpoint nodes exist; reached = pair proposed for classification
    c_node = al["concept_to_nodes"]
    eligible = [
        r for r in gold_keys.values() if r.src_concept in c_node and r.tgt_concept in c_node
    ]
    reached = 0
    if proposed_pairs is not None:
        for r in eligible:
            if any(
                frozenset((a, b)) in proposed_pairs
                for a in c_node[r.src_concept]
                for b in c_node[r.tgt_concept]
            ):
                reached += 1
    pair_recall = {
        "gold_edges": len(gold_keys),
        "missing_endpoint_excluded": len(gold_keys) - len(eligible),
        "denominator": len(eligible),
        "reached_classification": reached if proposed_pairs is not None else None,
        "pair_recall": (reached / len(eligible))
        if proposed_pairs is not None and eligible
        else None,
    }
    # ---- relation conditional on correct gold endpoints
    cond = Counter()
    confusion: Counter = Counter()
    pred_by_pair: dict[frozenset[str], list[PredEdge]] = defaultdict(list)
    for e in edges:
        cs, ct = n2c.get(e.src), n2c.get(e.tgt)
        if cs and ct and cs != ct:
            pred_by_pair[frozenset((cs, ct))].append(e)
    for r in gold_keys.values():
        cand = pred_by_pair.get(frozenset((r.src_concept, r.tgt_concept)), [])
        if not cand:
            continue
        cond["gold_with_proposed_edge"] += 1
        exact = [e for e in cand if e.relation == r.relation]
        pick = exact[0] if exact else cand[0]
        confusion[(r.relation, pick.relation)] += 1
        if exact:
            cond["relation_correct"] += 1
            e = exact[0]
            same_dir = n2c.get(e.src) == r.src_concept
            if r.relation in symmetric or same_dir:
                cond["direction_correct"] += 1
    return {
        "strict_e2e_edge": strict,
        "canonical_node": canon,
        "canonical_node_typed": canon_typed,
        "concept_mentions_typed": concept_mentions,
        "identity": ident,
        "pair_recall": pair_recall,
        "relation_conditional": dict(cond),
        "relation_confusion": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())},
        "alignment": {k: al[k] for k in ("false_merge_nodes", "unmatched_nodes", "split_concepts")},
    }


def identity_metrics(gold: UnitGold, nodes: list[PredNode]) -> dict:
    """Pairwise identity P/R/F1 and B-cubed over gold mentions. Predicted clusters are the node mention sets restricted to gold
    mentions; a gold mention no node covers is its own singleton predicted cluster."""
    g_cluster = {m.span: m.concept_id for m in gold.mentions if m.concept_id}
    spans = sorted(g_cluster)
    p_cluster: dict[Span, str] = {}
    for n in nodes:
        for s in n.mentions:
            if s in g_cluster:
                p_cluster.setdefault(s, n.node_id)
    for s in spans:
        p_cluster.setdefault(s, f"single:{s}")
    tp = fp = fn = 0
    for i, a in enumerate(spans):
        for b in spans[i + 1 :]:
            g_same, p_same = g_cluster[a] == g_cluster[b], p_cluster[a] == p_cluster[b]
            tp += g_same and p_same
            fp += (not g_same) and p_same
            fn += g_same and (not p_same)
    pair = prf(tp, fp, fn)
    members_g: dict[str, set[Span]] = defaultdict(set)
    members_p: dict[str, set[Span]] = defaultdict(set)
    for s in spans:
        members_g[g_cluster[s]].add(s)
        members_p[p_cluster[s]].add(s)
    if not spans:
        return {"pairwise": pair.to_dict(), "bcubed": None}
    bp = sum(
        len(members_p[p_cluster[s]] & members_g[g_cluster[s]]) / len(members_p[p_cluster[s]])
        for s in spans
    ) / len(spans)
    br = sum(
        len(members_p[p_cluster[s]] & members_g[g_cluster[s]]) / len(members_g[g_cluster[s]])
        for s in spans
    ) / len(spans)
    bf = 2 * bp * br / (bp + br) if bp + br else 0.0
    return {"pairwise": pair.to_dict(), "bcubed": {"precision": bp, "recall": br, "f1": bf}}


def pool_graph_units(units: dict[str, dict], key: str = "strict_e2e_edge") -> PRF:
    """Micro-pool a PRF over sections (counts add; this is the headline aggregation, bootstrap is by section)."""
    return prf(
        sum(u[key].tp for u in units.values()),
        sum(u[key].fp for u in units.values()),
        sum(u[key].fn for u in units.values()),
    )
