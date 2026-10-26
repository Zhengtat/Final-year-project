"""CR-058 stage funnel for ONE SciNLP paper ($0, read-only, no model call). Every count is additive over papers, so the page pools any set.

Concept stages: the concepts that exist after a stage are placed with the `IDXR1-P1` rule (recorded evidence quotes + the CR-019 occurrence
index, R1-key matching) and scored against the gold mentions with the frozen CR-012 entity-strict scorer. SciNLP has no identity gold, so
concept P / R / F1 are mention level. The last stage (consolidation) is the production prediction and must equal the CR-043 scorecard.

Relation stages: a selected pair (two final nodes, one sentence) is gold-positive when a gold relation links a placed mention of one node to
a placed mention of the other; its gold labels are those relations (with direction). Each gold relation is also followed through the
stages (endpoints placed, pair selected, family, choice, checks, assembly, credited); "pair recall" at a stage = gold relations that reach
it / gold relations whose endpoints are both placed."""

from __future__ import annotations

import bisect
from collections import Counter

from cumap.cr012 import scoring as S
from cumap.cr012.types import PRF, UnitGold
from cumap.cr019 import variants as V
from cumap.cr054.recall import key

CONCEPT_STAGES = (
    "generator_first_pass",
    "verifier_first_pass",
    "corrective_round",
    "pruner",
    "consolidation",
)
GOLD_REL_STAGES = (
    "gold",
    "endpoints_placed",
    "pair_selected",
    "family_right",
    "choice_right",
    "checks_passed",
    "assembled",
    "credited",
)
FAMILY = "scinlp"  # the one semantic family of the SciNLP registry; no_relation / other are the negative answers


def prf_d(x: PRF) -> dict:
    return {"tp": x.tp, "fp": x.fp, "fn": x.fn}


def _unit(section_id: str) -> str:
    return section_id.split("#")[0]


def items_to_concepts(items: list[dict], doc_key: str, nodes: dict | None = None) -> list[dict]:
    """Generator / verifier items -> checkpoint-style concepts, one per R1 key of the concept name.

    A new concept counts under its own name; an existing mention counts under the card node it names (`node_id` in the v4 node store),
    as the node store records it, so the item stages and the node-store stage place the same concept the same way."""
    by: dict[str, dict] = {}
    for it in items:
        node = (nodes or {}).get(it.get("node_id") or "")
        name = node["name"] if node else it.get("name") or it.get("surface")
        if not name:
            continue
        k = key(name) or name.lower()
        c = by.setdefault(k, {"concept_id": f"s_{k}", "canonical_name": name, "aliases": [],
                              "node_type": it.get("node_type") or "method", "mentions": []})  # fmt: skip
        for a in [*((node or {}).get("aliases") or []), *(it.get("aliases") or [])]:
            if a and a != c["canonical_name"] and a not in c["aliases"]:
                c["aliases"].append(a)
        c["mentions"].append(
            {"section_id": doc_key, "quote": it.get("evidence") or name, "role": it.get("role")}
        )
    return list(by.values())


def nodes_to_concepts(nodes: list[dict], doc_key: str) -> list[dict]:
    """v4 generator-stage nodes -> checkpoint-style concepts (section ids folded to the paper)."""
    out = []
    for n in nodes:
        ms = [{"section_id": doc_key, "quote": m.get("evidence") or n["name"], "role": m.get("role")}
              for m in n.get("mentions") or []] or [{"section_id": doc_key, "quote": n["name"], "role": None}]  # fmt: skip
        out.append({"concept_id": n["id"], "canonical_name": n["name"], "aliases": list(n.get("aliases") or []),
                    "node_type": n.get("node_type") or "method", "mentions": ms})  # fmt: skip
    return out


def _iter_items(out: dict | None) -> list[dict]:
    out = out or {}
    return [*(out.get("new_concepts") or []), *(out.get("existing_mentions") or [])]


def concept_stage_sets(v4: dict, cp: dict, doc_key: str) -> dict[str, list[dict]]:
    """The concepts that exist after each concept stage, as checkpoint-style concepts.

    generator_first_pass: union over sections of iteration 0's raw output; verifier_first_pass: iteration 0 after the code verifier;
    corrective_round: each section's final items (hints, regeneration, verifier, carry-forward); pruner: the growing generator-stage
    nodes; consolidation: the checkpoint concepts (canonicalisation and merges), i.e. the production prediction."""
    secs = list(v4["sections"].values())
    first = [x for s in secs for x in _iter_items((s.get("iterations") or [{}])[0].get("output"))]
    ver = [x for s in secs for x in _iter_items((s.get("iterations") or [{}])[0].get("verified"))]
    fin = [x for s in secs for x in _iter_items(s.get("final"))]
    pruned = {p.get("id") for p in v4.get("pruned") or [] if isinstance(p, dict)}
    grow = [n for n in v4["nodes"].values() if n.get("growing", True) and n["id"] not in pruned]
    return {
        "generator_first_pass": items_to_concepts(first, doc_key, v4["nodes"]),
        "verifier_first_pass": items_to_concepts(ver, doc_key, v4["nodes"]),
        "corrective_round": items_to_concepts(fin, doc_key, v4["nodes"]),
        "pruner": nodes_to_concepts(grow, doc_key),
        "consolidation": cp["concepts"],
    }


def concept_prf(doc, gold: UnitGold, concepts: list[dict], sym: set[str]) -> tuple[PRF, int]:
    """(entity-strict PRF of the placed mentions, node count) for one concept set under the IDXR1-P1 placement."""
    pred = V.sc_predict_indexed(doc, {"concepts": concepts, "relation_results_v3": []}, "r1key")
    res = S.score_scinlp_unit(gold, S.project_nodes_to_mentions(pred["nodes"]), [], sym)
    return res["entity_strict"], len(concepts)


def gold_surface_keys(doc, gold: UnitGold) -> set[str]:
    return {key(" ".join(doc.tokens[m.span[0] : m.span[1]])) for m in gold.mentions}


def verifier_drops(v4: dict, gkeys: set[str], final_keys: set[str]) -> dict:
    """Items the code verifier removed, split into gold concepts (correct items dropped) and the rest (wrong items dropped).

    An item is a gold concept when one of its forms has the R1 key of a gold mention surface of the paper. `recovered` = the item's
    form is back in the paper's final concepts anyway (found again in a later iteration or by another item)."""
    out: Counter = Counter()
    rules: dict[str, Counter] = {"correct": Counter(), "wrong": Counter()}
    examples: dict[str, list[str]] = {"correct": [], "wrong": []}
    for s in v4["sections"].values():
        for r in s.get("rejected") or []:
            it = r.get("item") or {}
            forms = {
                key(x) for x in [it.get("name"), it.get("surface"), *(it.get("aliases") or [])] if x
            }
            kind = "concept" if r.get("kind") == "new_concepts" else "mention"
            ok = "correct" if forms & gkeys else "wrong"
            out[f"{kind}_{ok}"] += 1
            if forms & final_keys:
                out[f"{kind}_{ok}_recovered"] += 1
            for rule in r.get("rules") or []:
                rules[ok][rule] += 1
            name = it.get("name") or it.get("surface") or ""
            if len(examples[ok]) < 40 and name:
                examples[ok].append(f"{name} [{','.join(r.get('rules') or [])}]")
    hints: Counter = Counter()
    for s in v4["sections"].values():
        hints["added"] += int(s.get("hints_added") or 0)
        hints["rejected"] += int(s.get("hints_rejected") or 0)
        hints["restored"] += int(s.get("restored") or 0)
        hints["unresolved"] += len(s.get("unresolved_hints") or [])
        for rule, n in (s.get("flags_by_rule") or {}).items():
            hints[f"flag_{rule}"] += int(n) if isinstance(n, int) else len(n)
    return {"counts": dict(out), "rules": {k: dict(v) for k, v in rules.items()},
            "examples": examples, "hints": dict(hints)}  # fmt: skip


def consolidation_stats(v4: dict, cp: dict) -> dict:
    """Generator-link decisions (v4 merge log, with their own rule ids: accepted `G-link`, `G-link-rejected`, adjudicated, promoted) and
    canonicalisation merges (checkpoint merge log). The checkpoint log also copies every generator-stage entry relabelled `G-link`
    (the known merge-log relabelling, CR-035), so those copies are skipped here, not counted twice."""
    links: Counter = Counter()
    for m in v4.get("merges") or []:
        links[m.get("rule_id") or "unknown"] += 1
    merges: Counter = Counter()
    for m in cp.get("merges") or []:
        rid = m.get("rule_id")
        if rid and rid.startswith("G-link"):
            continue
        merges[rid or ("R4 (LLM judge)" if m.get("llm_called") else "exact")] += 1
    return {"nodes_before": len(v4["nodes"]), "nodes_after": len(cp["concepts"]),
            "links": dict(links), "merges": dict(merges)}  # fmt: skip


def _endpoints(r: dict) -> tuple[str, str]:
    x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
    return (y, x) if r.get("direction") == "reversed" else (x, y)


def _assembled(r: dict) -> bool:
    """The assembly filter of the scorers: selected group, not gated or consolidated away, not negated."""
    return (
        r["outcome"] == "edge"
        and r.get("group", "selected") == "selected"
        and not r.get("gated_dropped")
        and not r.get("consolidated_into")
        and (r.get("qualifiers") or {}).get("polarity") != "negated"
    )


def relation_funnel(doc, gold: UnitGold, cp: dict, sym: set[str]) -> dict:
    """Pair-level step counts and the per-gold-relation stage funnel for one paper (IDXR1-P1 placement)."""
    scored = V.sc_score(doc, gold, cp, sym, "IDXR1-P1")
    pred = scored["pred"]
    owner: dict = {}
    for n in pred["nodes"]:
        for sp in n.mentions:
            owner.setdefault(sp, set()).add(n.node_id)
    labels: dict[frozenset, list[tuple[str, str, str]]] = {}
    for g in gold.relations:
        for a in owner.get(g.src_span, ()):
            for b in owner.get(g.tgt_span, ()):
                if a != b:
                    labels.setdefault(frozenset((a, b)), []).append((g.relation, a, b))

    def right_choice(r: dict) -> bool:
        if not r.get("relation"):
            return False
        s, t = _endpoints(r)
        return any(rel == r["relation"] and (s == a or rel in sym)
                   for rel, a, _b in labels.get(frozenset((s, t)), []))  # fmt: skip

    placed = {(e.src, e.tgt, e.relation) for e in pred["edges"]}
    left = Counter(
        (e.src, e.tgt, e.relation) for e in pred["edges"]
    )  # placed edges, consumed in result order
    pairs: Counter = Counter()
    checks: dict[str, Counter] = {"correct": Counter(), "wrong": Counter()}
    by_pair: dict[frozenset, list[dict]] = {}
    for r in cp["relation_results_v3"]:
        if r.get("group", "selected") != "selected":
            continue
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        by_pair.setdefault(frozenset((x, y)), []).append(r)
        pos = frozenset((x, y)) in labels
        pairs["selected"] += 1
        pairs["selected_positive" if pos else "selected_negative"] += 1
        fam = r.get("family") == FAMILY
        pairs[f"family_{'tp' if pos and fam else 'fn' if pos else 'fp' if fam else 'tn'}"] += 1
        if not fam:
            continue
        chose = bool(r.get("relation")) and r["outcome"] in ("edge", "rejected")
        rc = right_choice(r)
        if not chose:
            pairs["choice_declined_" + ("positive" if pos else "negative")] += 1
            continue
        pairs[
            "choice_right" if rc else ("choice_wrong_label" if pos else "choice_on_negative")
        ] += 1
        ok = "correct" if rc else "wrong"
        if r["outcome"] == "rejected":
            checks[ok][r.get("reason") or "unknown"] += 1
            pairs[f"checks_dropped_{ok}"] += 1
            continue
        pairs[f"checks_passed_{ok}"] += 1
        if not _assembled(r):
            pairs[f"assembly_dropped_{ok}"] += 1
        elif left[(*_endpoints(r), r["relation"])] <= 0:
            pairs[f"unplaced_{ok}"] += 1
        else:
            left[(*_endpoints(r), r["relation"])] -= 1
            pairs[f"in_graph_{ok}"] += 1
    rels, _ = S.project_edges_to_mentions(pred["nodes"], pred["edges"])
    credited = {S._rel_key(s, t, rel, sym) for s, t, rel, _a, _b in rels}
    stage: Counter = Counter()
    lost_at: list[str] = []
    for g in gold.relations:
        reached = ["gold"]
        A, B = owner.get(g.src_span, set()), owner.get(g.tgt_span, set())
        combos = [(a, b) for a in A for b in B if a != b]
        if combos:
            reached.append("endpoints_placed")
            rs = [r for a, b in combos for r in by_pair.get(frozenset((a, b)), [])]
            if rs:
                reached.append("pair_selected")

                def match(r: dict, g=g, A=A, B=B) -> bool:
                    s, t = _endpoints(r)
                    return r.get("relation") == g.relation and (
                        (s in A and t in B) or (g.relation in sym and s in B and t in A)
                    )

                if any(r.get("family") == FAMILY for r in rs):
                    reached.append("family_right")
                    hit = [r for r in rs if r.get("family") == FAMILY and match(r)]
                    if hit:
                        reached.append("choice_right")
                        if any(r["outcome"] == "edge" for r in hit):
                            reached.append("checks_passed")
                            if any(
                                _assembled(r) and (*_endpoints(r), r["relation"]) in placed
                                for r in hit
                            ):
                                reached.append("assembled")  # fmt: skip
        if S._rel_key(g.src_span, g.tgt_span, g.relation, sym) in credited:
            reached = list(GOLD_REL_STAGES)
        stage.update(reached)
        lost_at.append(
            GOLD_REL_STAGES[len(reached)] if len(reached) < len(GOLD_REL_STAGES) else "credited"
        )
    same = Counter()
    for g, at in zip(gold.relations, lost_at, strict=True):
        if at == "pair_selected":
            ss = bisect.bisect_right(doc.sentence_ends, g.src_span[0]) == bisect.bisect_right(doc.sentence_ends, g.tgt_span[0])  # fmt: skip
            same["same_sentence" if ss else "cross_sentence"] += 1
    return {
        "pairs": dict(pairs),
        "checks": {k: dict(v) for k, v in checks.items()},
        "gold_stages": {k: stage.get(k, 0) for k in GOLD_REL_STAGES},
        "not_selected_split": dict(same),
        "lost_at": lost_at,
        "selection_stats": {
            k: v for k, v in (cp.get("selection_stats") or {}).items() if isinstance(v, int)
        },
        "edges": scored["edges"],
        "relation_strict": prf_d(scored["scores"]["rel"]),
        "concept_strict": prf_d(scored["scores"]["entity_strict"]),
        "pred": pred,
    }


def concept_funnel(doc, gold: UnitGold, cp: dict, v4: dict, sym: set[str]) -> dict:
    sets = concept_stage_sets(v4, cp, doc.doc_key)
    stages = {}
    for name in CONCEPT_STAGES:
        p, n = concept_prf(doc, gold, sets[name], sym)
        stages[name] = {**prf_d(p), "nodes": n}
    final_keys = {
        key(f) for c in cp["concepts"] for f in [c["canonical_name"], *(c.get("aliases") or [])]
    }
    return {
        "stages": stages,
        "verifier": verifier_drops(v4, gold_surface_keys(doc, gold), final_keys),
        "pruned": len(v4.get("pruned") or []),
        "consolidation": consolidation_stats(v4, cp),
    }
