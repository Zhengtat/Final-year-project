"""CR-017 STOP 1 ($0, no model call, no scorer change): audit what the frozen CR-012 P&D-E2E gold and E0 runs can support.

(1) hierarchy gold: explicit `is_a` gold edges, closure size, chains, cycles, coverage per section (gold only; nothing inferred from predictions);
(2) inventory of PREDICTED is_a edges and of gold is_a endpoint availability (counts only, no hierarchy score);
(3) relation-macro population: gold edges whose endpoint nodes exist and whose pair reached the classifier, with the classifier outcome (edge / other / no_relation / rejected) and per-class support.
Reads frozen artefacts only; writes reports/cr017/*.json."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scoring as S

ROOT = Path(".")
SETS = [
    ("pilot", "data/gold/pd_e2e_pilot_blind.csv", ["1.5", "2.6"]),
    (
        "heldout",
        "data/gold/pd_e2e_test_blind.csv",
        ["4.4", "4.5", "5.4", "6.3", "7.1", "8.2", "9.3"],
    ),
]


def closure(edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    ch: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        ch[a].add(b)
    out: set[tuple[str, str]] = set()

    def walk(src: str, cur: str, seen: frozenset) -> None:
        for p in ch.get(cur, ()):
            if p in seen:
                continue
            out.add((src, p))
            walk(src, p, seen | {p})

    for a in list(ch):
        walk(a, a, frozenset({a}))
    return out


def has_cycle(edges: set[tuple[str, str]]) -> bool:
    ch: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        ch[a].add(b)
    for a in list(ch):
        stack, seen = list(ch[a]), set()
        while stack:
            x = stack.pop()
            if x == a:
                return True
            if x not in seen:
                seen.add(x)
                stack += list(ch.get(x, ()))
    return False


def max_depth(edges: set[tuple[str, str]]) -> int:
    ch: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        ch[a].add(b)
    memo: dict[str, int] = {}

    def d(x: str, path=()):
        if x in memo:
            return memo[x]
        v = 0 if not ch.get(x) else 1 + max(d(p, path + (x,)) for p in ch[x] if p not in path)
        memo[x] = v
        return v

    return max((d(a) for a in list(ch)), default=0)


def main() -> dict:
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    reg = PD.registry()
    sym = {r.name for r in reg.all_relations() if r.symmetric}
    out: dict = {
        "hierarchy_gold": {},
        "predicted_is_a": {},
        "relation_population": {"per_section": {}},
        "taxonomy_relation_inventory": {},
    }
    inv = [
        r.name
        for r in reg.all_relations()
        if getattr(r, "family", "") == "classification_structure"
    ]
    out["taxonomy_relation_inventory"] = {
        "classification_structure_family": inv,
        "is_a": "Source is a kind/subtype of target (the only subsumption relation in registry v1.3)",
        "instantiates": "NOT in the active registry (CR-004 patch reserved, never applied)",
    }
    gold_support: Counter = Counter()
    outcome_by_gold: dict[str, Counter] = defaultdict(Counter)
    tot_reach = 0
    for name, sheet, sections in SETS:
        gold, problems = PD.load_gold(ROOT / sheet, secs, reg)
        assert not problems, problems[:2]
        for sid in sections:
            g = gold[sid]
            isa = {
                (r.src_concept, r.tgt_concept)
                for r in g.relations
                if r.relation == "is_a" and r.src_concept and r.tgt_concept
            }
            cl = closure(isa)
            names = {c.concept_id: c.name for c in g.concepts}
            in_isa = {x for e in isa for x in e}
            out["hierarchy_gold"][sid] = {
                "set": name, "gold_concepts": len(g.concepts), "gold_relation_rows": len(g.relations), "is_a_edges": len(isa), "ancestor_pairs_after_closure": len(cl), "pairs_added_by_closure": len(cl) - len(isa),
                "concepts_in_is_a_edges": len(in_isa), "max_chain_depth": max_depth(isa), "cycle_in_gold": has_cycle(isa), "children_with_two_or_more_parents": sum(1 for c in {a for a, b in isa} if sum(1 for a, b in isa if a == c) > 1),
                "example_chain": next((f"{names[a]} -> {names[b]} -> {names[c]}" for a, b in sorted(isa) for b2, c in sorted(isa) if b == b2 and a != c), None),
            }  # fmt: skip
            # ---- predicted side (E0 run), inventory only
            rid = f"cr012_{name}_{sid.replace('.', '_')}_E0"
            cp = PG.load_run(rid)
            pg = PG.graph_for_sections(cp, {sid: secs[sid]})[sid]
            nodes, edges = pg["nodes"], pg["edges"]
            al = S.align_nodes(nodes, g.mentions)
            n2c, c2n = al["node_to_concept"], al["concept_to_nodes"]
            pred_isa = [e for e in edges if e.relation == "is_a"]
            both_exist = [e for e in isa if e[0] in c2n and e[1] in c2n]
            prop = PG.proposed_pairs(cp, sid)
            reached_isa = [
                e
                for e in both_exist
                if any(frozenset((a, b)) in prop for a in c2n[e[0]] for b in c2n[e[1]])
            ]
            out["predicted_is_a"][sid] = {"predicted_edges_total": len(edges), "predicted_is_a_edges": len(pred_isa), "predicted_is_a_edges_with_both_endpoints_mapped_to_gold_concepts": sum(1 for e in pred_isa if n2c.get(e.src) and n2c.get(e.tgt)),
                                          "gold_is_a_edges": len(isa), "gold_is_a_edges_with_both_endpoint_nodes_present": len(both_exist), "gold_is_a_edges_whose_pair_reached_the_classifier": len(reached_isa)}  # fmt: skip
            # ---- relation population: gold edges with endpoints present whose pair reached the classifier
            res_by_pair: dict[frozenset, list[dict]] = defaultdict(list)
            for r in cp["relation_results_v3"]:
                if r.get("group", "selected") == "selected" and r["pair"]["section_id"] == sid:
                    res_by_pair[
                        frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
                    ].append(r)
            reached = 0
            per_sec = Counter()
            seen = set()
            for rel in g.relations:
                if (
                    not (rel.src_concept and rel.tgt_concept)
                    or rel.src_concept not in c2n
                    or rel.tgt_concept not in c2n
                ):
                    continue
                key = (frozenset((rel.src_concept, rel.tgt_concept)), rel.relation)
                if key in seen:
                    continue
                seen.add(key)
                hits = [
                    x
                    for a in c2n[rel.src_concept]
                    for b in c2n[rel.tgt_concept]
                    for x in res_by_pair.get(frozenset((a, b)), [])
                ]
                if not hits:
                    continue
                reached += 1
                gold_support[rel.relation] += 1
                pick = next(
                    (h for h in hits if h["outcome"] == "edge" and h["relation"] == rel.relation),
                    hits[0],
                )
                label = pick["relation"] if pick["outcome"] == "edge" else f"<{pick['outcome']}>"
                outcome_by_gold[rel.relation][label] += 1
                per_sec[pick["outcome"]] += 1
            tot_reach += reached
            out["relation_population"]["per_section"][sid] = {
                "gold_edges": len(
                    {
                        (frozenset((r.src_concept, r.tgt_concept)), r.relation)
                        for r in g.relations
                        if r.src_concept and r.tgt_concept
                    }
                ),
                "reached_classifier": reached,
                "classifier_outcome_of_reached": dict(per_sec),
            }
    ht = out["hierarchy_gold"]
    out["hierarchy_gold_totals"] = {
        k: sum(v[k] for v in ht.values())
        for k in (
            "gold_concepts",
            "gold_relation_rows",
            "is_a_edges",
            "ancestor_pairs_after_closure",
            "pairs_added_by_closure",
            "concepts_in_is_a_edges",
        )
    } | {
        "sections_with_is_a": sum(1 for v in ht.values() if v["is_a_edges"]),
        "sections": len(ht),
        "sections_with_chain_depth_2_or_more": sum(
            1 for v in ht.values() if v["max_chain_depth"] >= 2
        ),
        "cycles_in_gold": sum(v["cycle_in_gold"] for v in ht.values()),
    }
    out["relation_population"]["reached_gold_edges_total"] = tot_reach
    out["relation_population"]["gold_relation_support_among_reached"] = dict(
        gold_support.most_common()
    )
    out["relation_population"]["classifier_output_by_gold_relation"] = {
        k: dict(v) for k, v in sorted(outcome_by_gold.items())
    }
    Path("reports/cr017/stop1_audit.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    o = main()
    print(json.dumps(o["hierarchy_gold_totals"], indent=1))
    print(
        o["relation_population"]["reached_gold_edges_total"],
        o["relation_population"]["gold_relation_support_among_reached"],
    )
    for k, v in o["predicted_is_a"].items():
        print(k, v)
