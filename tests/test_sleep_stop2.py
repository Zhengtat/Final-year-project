"""CR-011 STOP 2: type map (non-transitive, Concept not a wildcard), candidate bookkeeping, bridge pairs, SLEEP-240 allocation /
family split / leakage / blind sheets, threshold policy. Synthetic data only (no network, no key, no real run)."""

import csv
from pathlib import Path

import numpy as np
import pytest

from cumap.expert_kg.alias_rules import AliasConfig
from cumap.sleep import candidates as C
from cumap.sleep import scorer as S
from cumap.sleep import sleep240 as Z
from cumap.sleep.snapshot import Node
from cumap.sleep.typecompat import TypeMap

TM = TypeMap.load()
CFG = AliasConfig.load()


def node(i, name, typ="Mechanism", chapter=1, definition=None, quotes=("q1", "q2")):
    return Node(
        id=i, name=name, aliases=[], type=typ, definition=definition, first_section=f"{chapter}.1",
        mentions=[{"quote": q, "role": "used", "section_id": f"{chapter}.1"} for q in quotes],
        description_history=[], chapter=chapter,
    )  # fmt: skip


# ---------------------------------------------------------------- type compatibility
def test_type_map_is_configured_and_concept_is_not_a_wildcard():
    assert TM.compatible("Protocol", "Protocol") and TM.compatible("Protocol", "Mechanism")
    assert TM.compatible("Mechanism", "Protocol")  # unordered
    assert TM.compatible("Component", "Concept") and TM.compatible("DataUnit", "Concept")
    assert TM.compatible("Parameter", "Property") and TM.compatible("Identifier", "Parameter")
    assert not TM.compatible("Concept", "Protocol")  # no wildcard
    assert not TM.compatible("Concept", "Mechanism")
    assert not TM.compatible("Component", "DataUnit")
    assert TM.positive_evidence("Concept", "Concept") == 0.0  # generic type is no identity evidence


def test_compatibility_is_not_transitive_and_the_cluster_check_sees_it():
    types = {"A": "Component", "B": "Concept", "C": "DataUnit"}
    assert TM.compatible("Component", "Concept") and TM.compatible("Concept", "DataUnit")
    assert TM.cluster_consistent(types) == [
        ("A", "C")
    ]  # the generic bridge does not hide the A-C conflict
    assert TM.cluster_consistent({"A": "Protocol", "B": "Mechanism"}) == []


# ---------------------------------------------------------------- candidates
def test_candidate_set_counts_each_source_separately_and_dedupes_pairs():
    cs = C.CandidateSet()
    cs.add("a", "b", "name_embedding")
    cs.add("b", "a", "token_overlap")
    cs.add("a", "c", "name_embedding")
    cs.add("a", "a", "r1_key")  # a self pair is never a candidate
    c = cs.counts()
    assert (
        c["union"] == 2
        and c["by_signal"]["name_embedding"] == 2
        and c["by_signal"]["token_overlap"] == 1
    )
    assert c["exclusive_by_signal"]["name_embedding"] == 1  # (a, c); (a, b) has two sources


def test_tokens_lemmatise_plurals():
    assert C.tokens("Routing Tables") == C.tokens("routing table")


# ---------------------------------------------------------------- bridge pairs
def test_bridge_pairs_are_the_risky_endpoints_of_a_strong_chain():
    strong = {frozenset(("A", "B")), frozenset(("B", "C"))}
    assert Z.bridge_pairs(strong, lambda x, y: True) == {frozenset(("A", "C"))}
    assert Z.bridge_pairs(strong, lambda x, y: False) == set()
    assert (
        Z.bridge_pairs(strong | {frozenset(("A", "C"))}, lambda x, y: True) == set()
    )  # already a strong edge


# ---------------------------------------------------------------- allocation, families, split
def synth_pool(n_per=60):
    pool = {}
    k = 0
    for s in Z.STRATA:
        for _ in range(n_per):
            pool[(f"n{k}", f"n{k + 1}")] = [s]
            k += 2
    return pool


def synth_nodes(pool):
    nodes = {}
    for a, b in pool:
        nodes[a] = node(a, f"concept {a}")
        nodes[b] = node(b, f"idea {b}")
    return nodes


def test_allocation_fills_each_stratum_to_forty_caps_node_reuse_and_is_deterministic():
    pool = synth_pool()
    items, rep = Z.allocate(pool)
    assert rep["shortfall"] == {} and len(items) == 240
    assert {s: sum(i.stratum == s for i in items) for s in Z.STRATA} == dict.fromkeys(Z.STRATA, 40)
    use = {}
    for it in items:
        for n in it.pair:
            use[n] = use.get(n, 0) + 1
    assert max(use.values()) <= Z.MAX_PAIRS_PER_NODE
    assert [i.pair for i in Z.allocate(pool)[0]] == [i.pair for i in items]


def test_allocation_reports_a_shortfall_instead_of_inventing_items():
    pool = synth_pool()
    first = Z.STRATA[0]
    some = {p: m for p, m in pool.items() if first not in m}
    some |= dict([(p, m) for p, m in pool.items() if first in m][:10])
    _items, rep = Z.allocate(some)
    assert rep["shortfall"] == {first: 30}


def test_family_split_is_exactly_80_160_and_never_splits_a_family():
    pool = synth_pool()
    items, _ = Z.allocate(pool)
    nodes = synth_nodes(pool)
    Z.families(items, nodes, CFG)
    sp = Z.split(items)
    assert sp["status"] == "ok"
    assert (
        sum(i.split == "dev" for i in items) == 80
        and sum(i.split == "heldout" for i in items) == 160
    )
    fam_splits = {}
    for it in items:
        fam_splits.setdefault(it.family, set()).add(it.split)
    assert all(len(v) == 1 for v in fam_splits.values())
    assert Z.leakage_check(items, nodes, CFG)["ok"]


def test_variants_of_one_identity_problem_share_a_family():
    nodes = {
        "a": node("a", "bit rate"),
        "b": node("b", "bit-rate"),
        "c": node("c", "baud"),
        "d": node("d", "symbol"),
    }
    items = [Z.Item(("a", "c"), Z.STRATA[0], ()), Z.Item(("b", "d"), Z.STRATA[1], ())]
    Z.families(items, nodes, CFG)
    assert items[0].family == items[1].family  # "bit rate" and "bit-rate" share an R1 key


def test_leakage_check_flags_a_shared_normalised_form():
    nodes = {
        "a": node("a", "bit rate"),
        "b": node("b", "bit-rate"),
        "c": node("c", "x"),
        "d": node("d", "y"),
    }
    items = [
        Z.Item(("a", "c"), Z.STRATA[0], (), family="F1", split="dev"),
        Z.Item(("b", "d"), Z.STRATA[1], (), family="F2", split="heldout"),
    ]
    assert not Z.leakage_check(items, nodes, CFG)["ok"]


def test_blind_sheets_follow_the_contract_and_double_annotation_is_80_of_160(tmp_path):
    pool = synth_pool()
    items, _ = Z.allocate(pool)
    nodes = synth_nodes(pool)
    Z.families(items, nodes, CFG)
    Z.split(items)
    out = Z.sheets(items, nodes, "run", tmp_path)
    assert (
        out["dev"]["rows"] == 80
        and out["heldout"]["rows"] == 160
        and out["double_annotation_heldout"] == 80
    )
    for name in ("dev", "heldout"):
        Z.assert_blind(tmp_path / f"sleep240_{name}_blind_sheet.csv")
    header = next(csv.reader((tmp_path / "sleep240_dev_blind_sheet.csv").open()))
    assert header == Z.BLIND_COLUMNS
    assert not any(
        c in header for c in ("stratum", "score", "source", "arm", "split", "merge_probability")
    )
    man = list(csv.DictReader((tmp_path / "sleep240_manifest_DO_NOT_SHARE.csv").open()))
    assert len(man) == 240 and {r["split"] for r in man} == {"dev", "heldout"}


# ---------------------------------------------------------------- threshold policy
def test_auto_merge_is_disabled_when_the_safety_criterion_cannot_be_met():
    rng = np.random.default_rng(0)
    y = (rng.random(60) < 0.6).astype(int)
    p = np.clip(0.5 + 0.1 * rng.standard_normal(60), 0, 1)  # uninformative
    op = S.choose_thresholds(p, y)
    assert op.t_auto is None and op.auto_status.startswith("DISABLED")


def test_auto_merge_is_enabled_only_with_enough_clean_positives_for_the_wilson_bound():
    y = np.array([1] * 80 + [0] * 40)
    p = np.array([0.99] * 80 + [0.10] * 40)
    op = S.choose_thresholds(p, y)
    assert op.t_auto == pytest.approx(0.99) and op.auto_status.startswith("ENABLED")
    few = S.choose_thresholds(np.array([0.99] * 10 + [0.1] * 10), np.array([1] * 10 + [0] * 10))
    assert few.t_auto is None  # 10 clean positives cannot reach Wilson lower 0.95


def test_no_pipeline_module_builds_a_gold_path():
    for f in Path("src/cumap/sleep").glob("*.py"):
        src = f.read_text()
        assert "data/gold" not in src and '"gold"' not in src
        assert "openai" not in src.lower()
