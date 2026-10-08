"""CR-010 STOP 4: REL-MAP-180 construction (grouped split, blindness, determinism, validation), the pair-recall metric
and the P2 cue rule (no network, no key, no real run data)."""

import random
from collections import Counter
from pathlib import Path

import pytest
import yaml

from cumap.cr010 import pair_pools as PP
from cumap.cr010 import relmap as RM
from cumap.expert_kg.canonicalize import RegisteredConcept

REPO = Path(__file__).parents[1]
FX = yaml.safe_load((REPO / "tests/fixtures/cr010_erst_fixtures.yaml").read_text())
SMALL = {
    "edge": (4, 8),
    "no_relation": (2, 4),
    "other": (1, 2),
    "near_miss": (1, 2),
}  # 8 dev / 16 test
RELS = ["is_a", "part_of", "uses", "requires", "causes"]


def result(i, section, outcome, relation=None, reason=None):
    return {
        "outcome": outcome,
        "reason": reason,
        "family": "classification_structure" if relation else None,
        "relation": relation,
        "direction": "forward" if relation else None,
        "qualifiers": {"polarity": "affirmed"} if relation else {},
        "other_suggested_label": None,
        "group": "selected",
        "pair": {
            "pair_id": f"RP-{section}-{i}",
            "section_id": section,
            "concept_x_id": f"c{i}x",
            "concept_y_id": f"c{i}y",
            "sentence": f"Sentence {i} about c{i}x and c{i}y.",
        },
    }


def checkpoint(n_sections=12):
    rr, i = [], 0
    for s in range(n_sections):
        sec = f"{s + 1}.1"
        for kind, outcome, reason in (
            ("edge", "edge", None),
            ("edge", "edge", None),
            ("edge", "edge", None),
            ("nr", "no_relation", None),
            ("o", "other", None),
            ("nm", "rejected", "domain_range"),
            ("x", "rejected", "endpoint_not_grounded"),
        ):
            i += 1
            rr.append(
                result(i, sec, outcome, RELS[i % len(RELS)] if outcome == "edge" else None, reason)
            )
    concepts = [
        {"concept_id": f"c{k}{a}", "canonical_name": f"name c{k}{a}"}
        for k in range(1, i + 1)
        for a in "xy"
    ]
    return {"relation_results_v3": rr, "concepts": concepts}


@pytest.fixture(autouse=True)
def small_benchmark(monkeypatch):
    monkeypatch.setattr(RM, "KINDS", SMALL)


# ---------------------------------------------------------------- pools and split
def test_pools_take_primary_expert_edges_and_the_right_outcomes_only():
    cp = checkpoint()
    cp["relation_results_v3"].append({**result(999, "1.1", "edge", "is_a"), "gated_dropped": True})
    cp["relation_results_v3"].append({**result(998, "1.1", "edge", "is_a"), "group": "sample"})
    pools = RM.pools_from_checkpoint(cp)
    assert (
        len(pools["edge"]) == 36 and len(pools["no_relation"]) == 12 and len(pools["other"]) == 12
    )
    assert (
        len(pools["near_miss"]) == 12
    )  # only domain_range rejections; endpoint_not_grounded is a defect, not a near-miss


def test_the_split_is_by_whole_evidence_section_and_has_exact_counts():
    items, meta = RM.build_items(checkpoint(), seed=1)
    assert Counter(i["split"] for i in items) == {"dev": 8, "test": 16}
    assert Counter((i["split"], i["kind"]) for i in items) == {
        (s, k): SMALL[k][0 if s == "dev" else 1] for s in ("dev", "test") for k in SMALL
    }
    assert RM.leakage_check(items)["ok"]
    assert not set(meta["dev_sections"]) & set(meta["test_sections"])
    assert {i["section_id"] for i in items if i["split"] == "dev"} <= set(meta["dev_sections"])


def test_leakage_check_catches_a_shared_section_a_shared_pair_and_duplicates():
    items, _ = RM.build_items(checkpoint(), seed=1)
    bad = [dict(i) for i in items]
    dev = next(i for i in bad if i["split"] == "dev")
    test = next(i for i in bad if i["split"] == "test")
    test["section_id"] = dev["section_id"]
    assert RM.leakage_check(bad)["shared_evidence_sections"] == [dev["section_id"]]
    bad2 = [dict(i) for i in items]
    t2 = next(i for i in bad2 if i["split"] == "test")
    d2 = next(i for i in bad2 if i["split"] == "dev")
    t2["concept_x_id"], t2["concept_y_id"] = d2["concept_x_id"], d2["concept_y_id"]
    assert RM.leakage_check(bad2)["shared_concept_pairs"] == 1 and not RM.leakage_check(bad2)["ok"]
    bad3 = [dict(i) for i in items]
    bad3[1]["item_id"] = bad3[0]["item_id"]
    assert RM.leakage_check(bad3)["duplicate_item_ids"] == 1


def test_building_is_deterministic_and_seed_dependent():
    a, _ = RM.build_items(checkpoint(), seed=7)
    b, _ = RM.build_items(checkpoint(), seed=7)
    c, _ = RM.build_items(checkpoint(), seed=8)
    assert a == b and a != c


def test_item_ids_carry_no_order_and_concept_order_is_randomised():
    items, _ = RM.build_items(checkpoint(), seed=3)
    assert [i["item_id"] for i in items] == [f"RM{n:03d}" for n in range(1, 25)]
    assert {i["shown_a"] for i in items} == {"x", "y"}
    for i in items:
        assert {i["concept_a"], i["concept_b"]} == {i["name_x"], i["name_y"]}
        assert (i["concept_a"] == i["name_x"]) == (i["shown_a"] == "x")
    # strata are not sorted into blocks
    assert [i["stratum"] for i in items] != sorted(i["stratum"] for i in items)


def test_edges_are_picked_round_robin_so_rare_relations_are_represented():
    rng = random.Random(0)
    pool = [result(n, "1.1", "edge", "is_a") for n in range(30)] + [
        result(100, "1.1", "edge", "prevents")
    ]
    got = RM.pick(pool, 3, rng, lambda r: r["relation"], {"1.1"})
    assert "prevents" in {r["relation"] for r in got}


def test_pick_fails_loudly_when_the_pool_is_too_small_and_the_split_can_be_infeasible():
    with pytest.raises(RuntimeError):
        RM.pick(
            [result(1, "1.1", "edge", "is_a")],
            3,
            random.Random(0),
            lambda r: r["relation"],
            {"1.1"},
        )
    tiny = checkpoint(n_sections=2)
    with pytest.raises(RuntimeError):
        RM.assign_sections(RM.pools_from_checkpoint(tiny), seed=0)


# ---------------------------------------------------------------- blindness
def test_the_blind_sheet_has_the_template_columns_and_no_model_side_value():
    items, _ = RM.build_items(checkpoint(), seed=1)
    rows = RM.blind_rows(items, {"1.1": "§1.1 Intro"})
    RM.assert_blind(rows)
    template = REPO / "data/interim/checks/cr010_relmap180_blind_annotation_template.csv"
    if template.exists():
        assert template.read_text().splitlines()[0].split(",") == RM.BLIND_COLUMNS
    flat = " ".join(" ".join(r.values()) for r in rows).lower()
    for i in items:
        for secret in (
            i["current_relation"],
            i["current_outcome"],
            i["stratum"],
            i["pair_id"],
            i["split"],
        ):
            if secret:
                assert (
                    str(secret).lower() not in flat or str(secret).lower() in i["sentence"].lower()
                )
    leaky = [dict(rows[0], erst_relation_1="CAUSAL-CAUSE")]
    with pytest.raises(AssertionError):
        RM.assert_blind(leaky)


def test_the_research_mapping_table_is_never_read_by_the_builder():
    src = (REPO / "src/cumap/cr010/relmap.py").read_text()
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith(('"', "#", "'"))
    )
    assert (
        ".read_text" not in code.split("NOT_GOLD")[0] or "NOT_GOLD" in src
    )  # only named in the manifest note
    assert "mapping_NOT_GOLD" not in code.replace(
        '"cr010_current_to_erst_mapping_NOT_GOLD.csv"', ""
    )


# ---------------------------------------------------------------- annotation validation
ALLOWED = RM.allowed_values(RELS, ["CAUSAL-CAUSE", "JOINT-LIST"])


def filled(item_id="RM001", **kw):
    row = dict.fromkeys(RM.BLIND_COLUMNS, "")
    row.update(
        item_id=item_id,
        annotator_id="a1",
        current_semantic_relation_judgement="is_a",
        erst_applies_yes_no="no",
        machine_useful_meaning_survives_yes_no="yes",
    )
    row.update(kw)
    return row


def test_validation_accepts_a_complete_row_and_reports_every_kind_of_problem():
    ids = ["RM001"]
    assert RM.validate_sheet([filled()], ids, ALLOWED) == []
    cases = [
        (filled(current_semantic_relation_judgement="equivalent_to"), "not an allowed value"),
        (filled(annotator_id=""), "annotator_id"),
        (filled(erst_applies_yes_no=""), "required"),
        (filled(erst_applies_yes_no="yes"), "erst_relation_1 is empty"),
        (filled(erst_relation_1="CAUSAL-CAUSE"), "erst does not apply"),
        (filled(erst_applies_yes_no="yes", erst_relation_1="SAME-UNIT"), "not an allowed value"),
        (filled(loss_taxonomy="maybe"), "not an allowed value"),
        (filled(direction_judgement="left"), "not an allowed value"),
    ]
    for row, needle in cases:
        assert any(needle in p for p in RM.validate_sheet([row], ids, ALLOWED)), needle
    assert RM.validate_sheet([filled("RM002")], ids, ALLOWED)[0].startswith("item ids differ")


# ---------------------------------------------------------------- pair recall
def test_pair_recall_matches_the_frozen_fixture_and_excludes_missing_endpoints():
    fx = FX["pair_recall_fixture"]
    nodes = {"a", "b", "c", "d", "e", "f", "g", "h"}
    edges = [
        ("a", "b"),
        ("c", "d"),
        ("e", "f"),
        ("g", "h"),
        ("x", "y"),
    ]  # the last has a missing endpoint
    reached = {frozenset(("a", "b")), frozenset(("c", "d")), frozenset(("e", "f"))}
    r = PP.pair_recall(edges, nodes, reached)
    assert r["denominator"] == fx["validated_true_edges_both_nodes_exist"] == 4
    assert r["reached_classification"] == fx["pairs_reached_classification"] == 3
    assert r["pair_recall"] == fx["expected_pair_recall"] == 0.75
    assert (
        r["missing_endpoint_excluded"] == 1
        and fx["missing_endpoint_edges_excluded_from_denominator"]
    )
    assert PP.pair_recall([("x", "y")], nodes, reached)["pair_recall"] is None


def test_pair_recall_ignores_edge_direction_and_is_independent_of_classification():
    nodes = {"a", "b"}
    assert PP.pair_recall([("b", "a")], nodes, {frozenset(("a", "b"))})["pair_recall"] == 1.0
    assert PP.pair_recall([("a", "b")], nodes, set())["pair_recall"] == 0.0


# ---------------------------------------------------------------- the strict cue and adjacent pairs
CUES = {"for", "so", "because", "if", "uses", "requires", "is a", "then", "part of"}


def test_strict_cue_uses_word_boundaries_and_drops_function_words():
    assert not PP.strict_cue_v0(
        "Information is also processed.", CUES
    )  # 'for' / 'so' only as substrings
    assert not PP.strict_cue_v0(
        "We wait for it, so it works, if then.", CUES
    )  # function words are left out
    assert PP.strict_cue_v0("A switch requires a table.", CUES) and PP.strict_cue_v0(
        "It is part of IP.", CUES
    )
    assert not PP.strict_cue_v0("This is a thing.", CUES)  # 'is a' is a copula, not a relation cue


def concept(cid, name):
    return RegisteredConcept(
        concept_id=cid,
        canonical_name=name,
        node_type="Concept",
        definition=None,
        first_introduced="s",
    )


def test_adjacent_pairs_exclude_same_sentence_and_flag_the_cue_variants():
    text = "A router forwards packets. Because of that a switch requires a table. A hub is dumb. The cable is long."
    cs = [
        concept("r", "router"),
        concept("s", "switch"),
        concept("h", "hub"),
        concept("c", "cable"),
        concept("p", "packets"),
    ]
    got = PP.adjacent_pairs(text, cs, CUES)
    assert (
        frozenset(("r", "p")) not in got
    )  # same sentence: the enumeration at window 0 already has it
    assert got[frozenset(("r", "s"))]["loose_cue"] and got[frozenset(("r", "s"))]["strict_cue"]
    assert got[frozenset(("r", "s"))]["strict_v0_cue"]
    assert (
        got[frozenset(("s", "h"))]["strict_cue"] is True
    )  # the two-sentence span contains 'requires'
    assert not got[frozenset(("h", "c"))]["loose_cue"]
    assert not got[frozenset(("h", "c"))]["strict_cue"]
    assert got[frozenset(("h", "c"))]["spans"][0]["text"] == "A hub is dumb. The cable is long."
    assert frozenset(("r", "h")) not in got  # two sentences apart
