"""CR-012 STOP 3 scorer validation ($0): only SciNLP train / dev and the P&D pilot gold are used; the SciNLP test split and the P&D
held-out sections are never touched. For each scorer a perfect prediction must score 1.0 and each controlled corruption must move the score
by a value fixed in advance by construction.

    uv run python -m cumap.cr012.scorer_validation --pilot <owner-reviewed pilot sheet>
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.types import PredEdge, PredNode, UnitGold

OUT = REPO_ROOT / "reports/cr012/scorer_validation.json"


# ---------------------------------------------------------------- SciNLP (train + dev)
def scinlp_gold_as_prediction(g: UnitGold) -> tuple[list, list, list[PredNode], list[PredEdge]]:
    """Predicted mentions / mention-level relations that equal the gold, and the same thing as canonical nodes (one node per gold mention,
    no identity) plus edges whose evidence span covers both endpoints, to exercise the projection."""
    mentions = [(m.span, m.type) for m in g.mentions]
    typ = {m.span: m.type for m in g.mentions}
    rels = [
        (r.src_span, r.tgt_span, r.relation, typ[r.src_span], typ[r.tgt_span]) for r in g.relations
    ]
    nodes = [
        PredNode(f"n{i}", g.unit, m.type, f"m{i}", (m.span,)) for i, m in enumerate(g.mentions)
    ]
    nid = {m.span: f"n{i}" for i, m in enumerate(g.mentions)}
    edges = [
        PredEdge(
            g.unit,
            nid[r.src_span],
            nid[r.tgt_span],
            r.relation,
            (min(r.src_span[0], r.tgt_span[0]), max(r.src_span[1], r.tgt_span[1])),
        )
        for r in g.relations
    ]
    return mentions, rels, nodes, edges


def validate_scinlp() -> dict:
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    res: dict = {"splits": {}}
    rng = random.Random(0)
    for split in ("train", "dev"):  # the test split is never loaded here
        gold = ad.gold(split)
        per_perfect, per_proj, per_drop, per_shift, per_swap, per_rev = {}, {}, {}, {}, {}, {}
        for key, g in gold.items():
            m, r, nodes, edges = scinlp_gold_as_prediction(g)
            per_perfect[key] = S.score_scinlp_unit(g, m, r, sym)
            pr, _ung = S.project_edges_to_mentions(nodes, edges)
            per_proj[key] = S.score_scinlp_unit(g, S.project_nodes_to_mentions(nodes), pr, sym)
            keep = [x for i, x in enumerate(r) if i % 10 != 0]  # drop every 10th relation
            per_drop[key] = S.score_scinlp_unit(g, m, keep, sym)
            per_shift[key] = S.score_scinlp_unit(
                g, [((s[0], s[1] + 1), t) for s, t in m], r, sym
            )  # every span one token too long
            other = [x for x in ad.relation_registry() if x not in sym]
            swapped = [
                (
                    a,
                    b,
                    rng.choice([o for o in other if o != rel]) if rel not in sym else rel,
                    st,
                    tt,
                )
                for a, b, rel, st, tt in r
            ]
            per_swap[key] = S.score_scinlp_unit(g, m, swapped, sym)
            rev = [(b, a, rel, tt, st) for a, b, rel, st, tt in r]
            per_rev[key] = S.score_scinlp_unit(g, m, rev, sym)

        def micro(per, metric):
            return S.aggregate_documents(per, metric)["micro"]

        n_dir = sum(1 for g in gold.values() for x in g.relations if x.relation not in sym)
        n_sym = sum(1 for g in gold.values() for x in g.relations if x.relation in sym)
        res["splits"][split] = {
            "documents": len(gold),
            "gold_relations": n_dir + n_sym,
            "perfect": {
                k: micro(per_perfect, k)["f1"]
                for k in ("entity_strict", "entity_typed", "rel", "rel_plus")
            },
            "projected_from_nodes_and_evidence_spans": {
                k: micro(per_proj, k)["f1"] for k in ("entity_strict", "rel", "rel_plus")
            },
            "drop_every_10th_relation": {
                "rel_recall": micro(per_drop, "rel")["recall"],
                "rel_precision": micro(per_drop, "rel")["precision"],
            },
            "spans_one_token_too_long": {
                "entity_strict_f1": micro(per_shift, "entity_strict")["f1"],
                "entity_strict_tp": micro(per_shift, "entity_strict")["tp"],
            },
            "random_wrong_relation_for_directional_gold": {
                "rel_precision": micro(per_swap, "rel")["precision"],
                "rel_recall": micro(per_swap, "rel")["recall"],
                "symmetric_unchanged": n_sym,
            },
            "all_relations_reversed": {
                "rel_recall": micro(per_rev, "rel")["recall"],
                "expected_recall_if_only_symmetric_survive": n_sym / (n_dir + n_sym),
            },
        }
    return res


# ---------------------------------------------------------------- P&D pilot
def validate_pilot(sheet: Path) -> dict:
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    gold, problems = PD.load_gold(sheet, secs, PD.registry())
    sym = {r.name for r in PD.registry().all_relations() if r.symmetric}
    out: dict = {"sheet_problems": problems, "sections": {}}
    for sid, g in gold.items():
        # perfect: one node per gold concept carrying all its mentions, edges as in gold
        by_c: dict[str, list] = {}
        for m in g.mentions:
            by_c.setdefault(m.concept_id, []).append(m.span)
        ctype = {c.concept_id: c.type for c in g.concepts}
        nodes = [PredNode(c, sid, ctype[c], c, tuple(sorted(sp))) for c, sp in by_c.items()]
        uniq: dict = {}
        for r in (
            g.relations
        ):  # qualifier variants of one (source, target, relation) are one headline edge
            uniq.setdefault(
                (r.src_concept, r.tgt_concept, r.relation),
                PredEdge(sid, r.src_concept, r.tgt_concept, r.relation, qualifiers=r.qualifiers),
            )
        edges = list(uniq.values())
        pairs = {frozenset((r.src_concept, r.tgt_concept)) for r in g.relations}
        perfect = S.score_graph_unit(g, nodes, edges, sym, proposed_pairs=pairs)
        # corruptions with exactly known effects
        n = len(edges)
        drop = S.score_graph_unit(g, nodes, edges[: n - n // 10], sym)["strict_e2e_edge"]
        rev_e = [PredEdge(sid, e.tgt, e.src, e.relation) for e in edges]
        rev = S.score_graph_unit(g, nodes, rev_e, sym)["strict_e2e_edge"]
        n_sym = sum(1 for e in edges if e.relation in sym)
        # split one multi-mention concept into two nodes: canonical-node precision falls, strict edges are unaffected
        multi = next((c for c, sp in by_c.items() if len(sp) > 1), None)
        split_nodes = [x for x in nodes if x.node_id != multi]
        if multi:
            sp = sorted(by_c[multi])
            split_nodes += [
                PredNode(multi, sid, ctype[multi], multi, (sp[0],)),
                PredNode(multi + "_b", sid, ctype[multi], multi, tuple(sp[1:])),
            ]
        split = S.score_graph_unit(g, split_nodes, edges, sym)
        # false merge of two concepts into one node
        ids = list(by_c)
        fm_nodes = [x for x in nodes if x.node_id not in ids[:2]] + [
            PredNode(
                "merged", sid, ctype[ids[0]], "merged", tuple(sorted(by_c[ids[0]] + by_c[ids[1]]))
            )
        ]
        fm = S.score_graph_unit(g, fm_nodes, edges, sym)
        out["sections"][sid] = {
            "gold_counts": {
                "concepts": len(g.concepts),
                "mentions": len(g.mentions),
                "relations": n,
                "symmetric_relations": n_sym,
            },
            "perfect": {
                "strict_f1": perfect["strict_e2e_edge"].f1,
                "canonical_f1": perfect["canonical_node"].f1,
                "identity_pairwise_f1": perfect["identity"]["pairwise"]["f1"],
                "bcubed_f1": perfect["identity"]["bcubed"]["f1"],
                "pair_recall": perfect["pair_recall"]["pair_recall"],
            },
            "drop_10pct_edges": {
                "recall": drop.recall,
                "precision": drop.precision,
                "expected_recall": (n - n // 10) / n,
            },
            "all_edges_reversed": {
                "recall": rev.recall,
                "expected_recall_if_only_symmetric_survive": n_sym / n,
            },
            "split_one_concept": {
                "canonical_node_precision_drop": perfect["canonical_node"].precision
                - split["canonical_node"].precision,
                "strict_f1_unchanged": split["strict_e2e_edge"].f1 == perfect["strict_e2e_edge"].f1,
                "split_concepts": split["alignment"]["split_concepts"],
            },
            "false_merge_two_concepts": {
                "false_merge_nodes": fm["alignment"]["false_merge_nodes"],
                "strict_recall": fm["strict_e2e_edge"].recall,
                "identity_pairwise_precision": fm["identity"]["pairwise"]["precision"],
            },
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True)
    a = ap.parse_args()
    res = {"scinlp_train_dev": validate_scinlp(), "pd_pilot": validate_pilot(Path(a.pilot))}
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str)[:5000])


if __name__ == "__main__":
    main()
