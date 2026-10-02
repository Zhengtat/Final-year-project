"""CR-008 §4/§8: re-keying consolidates edges, rejects merge self-loops, migrates equivalent_to,
and deletes nothing (no network, no key)."""

from __future__ import annotations

from pathlib import Path

import yaml

from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.rekey import rekey_run
from cumap.expert_kg.roles import SectionText
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
REG = RelationRegistry.from_yaml(REPO / "configs/relations_v1.3.yaml")
TEXT = "The ARP cache is a table. The ARP table maps addresses. A switch forwards frames."
SECTIONS = [SectionText("s1", 1, 0, TEXT)]


def concept(cid, name, typ="Component", aliases=()):
    return {
        "concept_id": cid,
        "canonical_name": name,
        "node_type": typ,
        "definition": None,
        "first_introduced": "s1",
        "aliases": list(aliases),
        "description_history": [],
        "mentions": [
            {"section_id": "s1", "role": "used", "quote": name, "definition": None, "source": "llm"}
        ],
    }


def result(pid, x, y, relation, quote, outcome="edge", direction="forward"):
    return {
        "outcome": outcome,
        "reason": None,
        "family": "classification_structure",
        "relation": relation,
        "direction": direction,
        "statement": "s",
        "evidence_quote": quote,
        "qualifiers": {},
        "group": "selected",
        "pair": {
            "pair_id": pid,
            "section_id": "s1",
            "concept_x_id": x,
            "concept_y_id": y,
            "sentence": quote,
        },
    }


def checkpoint(concepts, results):
    return {
        "run_id": "r0",
        "concepts": concepts,
        "concept_first_chapter": {c["concept_id"]: 1 for c in concepts},
        "merges": [],
        "merge_review": [],
        "taxonomy_candidates": [],
        "related_candidates": [],
        "selected_pairs": [r["pair"] for r in results],
        "sample_pairs": [],
        "relation_results_v3": results,
    }


def ctx(tmp_path, same=(), different=()):
    path = tmp_path / "lex.yaml"
    path.write_text(
        yaml.safe_dump({"version": "t", "same": list(same), "different": list(different)})
    )
    lex = Lexicon.load(path, AliasConfig.load())
    return AliasContext.build(lex, {"s1": TEXT}, {"s1": 1}, [], lex.cfg)


def same(i, forms):
    return {"id": i, "forms": forms, "scope": "book:pd6e", "status": "approved", "source": "t"}


def run(tmp_path, concepts, results, **lex):
    return rekey_run(checkpoint(concepts, results), ctx(tmp_path, **lex), REG, SECTIONS, "r1")


def base(tmp_path, results, extra=()):
    concepts = [
        concept("c_cache", "ARP cache"),
        concept("c_table", "ARP table"),
        concept("c_sw", "switch"),
        concept("c_fr", "frame", "DataUnit"),
        *extra,
    ]
    return run(tmp_path, concepts, results, same=[same("s1", ["ARP cache", "ARP table"])])


def test_merge_keeps_every_form_and_old_ids(tmp_path):
    res = base(tmp_path, [])
    nodes = {c["concept_id"]: c for c in res.checkpoint["concepts"]}
    assert len(nodes) == 3 and res.report["merges_per_rule"] == {"R0": 1}
    survivor = next(c for c in nodes.values() if c["merged_from"])
    assert {survivor["canonical_name"], *survivor["aliases"]} == {"ARP cache", "ARP table"}
    assert survivor["alias_provenance"][0]["rule_id"] == "R0"
    assert (
        survivor["merged_from"][0] not in nodes
    )  # nothing deleted: the old id is kept in merged_from


def test_edges_are_consolidated_with_all_evidence(tmp_path):
    results = [
        result("P1", "c_cache", "c_fr", "has_property", "q1"),
        result("P2", "c_table", "c_fr", "has_property", "q2"),
    ]
    res = base(tmp_path, results)
    rr = res.checkpoint["relation_results_v3"]
    assert [r.get("consolidated_into") for r in rr] == [None, "P1"]
    assert [e["quote"] for e in rr[0]["evidence_all"]] == ["q1", "q2"]
    assert len(rr) == 2  # the duplicate stays in the run data


def test_merge_created_self_loop_is_rejected(tmp_path):
    res = base(tmp_path, [result("P1", "c_cache", "c_table", "contrasts_with", "q")])
    r = res.checkpoint["relation_results_v3"][0]
    assert (r["outcome"], r["reason"]) == ("rejected", "merge_self_loop")
    assert res.report["counts"]["merge_self_loop"] == 1


def test_equivalent_to_migration_cases(tmp_path):
    concepts_extra = [
        concept("c_a", "cloudification", "Concept"),
        concept("c_b", "softwarization", "Concept"),
        concept("c_r", "routing table"),
        concept("c_f", "forwarding table"),
    ]
    results = [
        result("P1", "c_cache", "c_table", "equivalent_to", "q"),  # merged by R0
        result("P2", "c_a", "c_b", "equivalent_to", "q"),  # owner sheet
        result("P3", "c_r", "c_f", "equivalent_to", "q"),  # lexicon different -> retired
    ]
    diff = [
        {
            "id": "d1",
            "forms": ["routing table", "forwarding table"],
            "kind": "book_distinguishes",
            "why": "t",
            "scope": "book:pd6e",
            "status": "approved",
            "source": "t",
        }
    ]
    res = run(
        tmp_path,
        [concept("c_cache", "ARP cache"), concept("c_table", "ARP table"), *concepts_extra],
        results,
        same=[same("s1", ["ARP cache", "ARP table"])],
        different=diff,
    )
    mig = {e["pair_id"]: e["migration"] for e in res.checkpoint["rekey"]["equivalence"]}
    assert mig == {"P1": "merged_by_rule", "P2": "owner_sheet", "P3": "retired_lexicon_different"}
    assert all(
        r["outcome"] != "edge" for r in res.checkpoint["relation_results_v3"]
    )  # 0 equivalent_to edges


def test_acyclicity_is_rechecked_after_merge(tmp_path):
    concepts = [
        concept("c_cache", "ARP cache"),
        concept("c_table", "ARP table"),
        concept("c_x", "switch"),
        concept("c_y", "frame", "Component"),
    ]
    results = [
        result("P1", "c_cache", "c_x", "is_a", "q1"),
        result("P2", "c_x", "c_table", "is_a", "q2"),
    ]
    res = run(tmp_path, concepts, results, same=[same("s1", ["ARP cache", "ARP table"])])
    assert res.report["cycles"] >= 1
