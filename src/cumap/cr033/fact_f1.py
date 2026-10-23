"""CR-033 SciNLP concept-level fact F1 `FACT-C1-SURF-R1` ($0, scorer only, no model call). Definition pre-registered in DECISIONS.md.

Gold: mention-level relations collapsed to unique (source concept, relation, target concept) facts (symmetric relations unordered). Prediction: the placed
predicted relations of the graph mapped to the same concepts. Concept identity is inferred from strings (CR-008 R1 key plus acronym <-> long form within a
paper, `cr032.scinlp_t1.r1_identity`), so the score is always labelled `SURF-R1`; it is a companion to, never a replacement of, the `IDX-P1` headline."""

from __future__ import annotations

from cumap.cr012 import scoring as S
from cumap.cr012.types import PRF, Span, UnitGold
from cumap.cr032.scinlp_t1 import Ident


def fact_key(rel: str, a: str, b: str, sym: set[str]) -> tuple:
    return (rel, frozenset((a, b))) if rel in sym else (rel, a, b)


def gold_facts(gold: UnitGold, ident: Ident, sym: set[str]) -> set[tuple]:
    return {fact_key(r.relation, ident(r.src_span), ident(r.tgt_span), sym) for r in gold.relations}


def fact_score(
    gold: UnitGold,
    rels: list[tuple],
    n_unplaced: int,
    variant: str,
    ident: Ident,
    sym: set[str],
) -> dict:
    """`rels`: placed predicted mention-level relations (src_span, tgt_span, label, ...). A predicted concept with no gold concept keeps a synthetic
    id (its facts can only be false positives). Unplaced predicted edges are false positives in every variant but FROZEN (rule 35)."""
    gold_nodes = {ident(m.span) for m in gold.mentions} | {
        ident(sp) for r in gold.relations for sp in (r.src_span, r.tgt_span)
    }

    def pident(sp: Span) -> str:
        k = ident(sp)
        return k if k in gold_nodes else "pred:" + k

    g = gold_facts(gold, ident, sym)
    p: dict[tuple, list[tuple]] = {}
    for s, t, rel, *_ in rels:
        p.setdefault(fact_key(rel, pident(s), pident(t), sym), []).append((s, t, rel))
    tp = g & set(p)
    gold_strict = {S._rel_key(r.src_span, r.tgt_span, r.relation, sym) for r in gold.relations}
    strict_tp = sum(
        1 for k in tp if any(S._rel_key(s, t, rel, sym) in gold_strict for s, t, rel in p[k])
    )
    extra = 0 if variant == "FROZEN" else n_unplaced
    return {
        "prf": PRF(len(tp), len(set(p) - g) + extra, len(g - set(p))),
        "gold_facts": len(g),
        "gold_mention_relations": len(gold.relations),
        "pred_facts": len(p),
        "pred_facts_with_synthetic_concept": sum(
            1 for k in p if any(str(x).startswith("pred:") for x in _nodes(k))
        ),
        "tp_facts": len(tp),
        "tp_facts_with_strict_evidence_match": strict_tp,
        "unplaced_counted_as_fp": extra,
    }


def _nodes(k: tuple):
    return list(k[1]) if isinstance(k[1], frozenset) else [k[1], k[2]]


def pool(units: dict[str, dict]) -> dict:
    prf = PRF(
        sum(u["prf"].tp for u in units.values()),
        sum(u["prf"].fp for u in units.values()),
        sum(u["prf"].fn for u in units.values()),
    )
    keys = (
        "gold_facts", "gold_mention_relations", "pred_facts", "pred_facts_with_synthetic_concept",
        "tp_facts", "tp_facts_with_strict_evidence_match", "unplaced_counted_as_fp",
    )  # fmt: skip
    out = {k: sum(u[k] for u in units.values()) for k in keys}
    out["evidence_match_share"] = (
        out["tp_facts_with_strict_evidence_match"] / out["tp_facts"] if out["tp_facts"] else None
    )
    return {"prf": prf, **out}
