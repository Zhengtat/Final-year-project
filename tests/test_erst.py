"""CR-010 STOP 3: the eRST inventory, edge/signal schemas and KG guards (no network, no key, no model)."""

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from cumap.erst import audit as A
from cumap.erst import guards as G
from cumap.erst.edges import ErstEdge, ErstSignal
from cumap.erst.registry import (
    NO_RELATION,
    ErstRegistry,
    ErstRelation,
    UnknownErstLabel,
)
from cumap.expert_kg.lexicon import Lexicon

REPO = Path(__file__).parents[1]
FX = yaml.safe_load((REPO / "tests/fixtures/cr010_erst_fixtures.yaml").read_text())
PAPER = {
    r["label"]: r["symbol"]
    for r in json.loads((REPO / "tests/fixtures/erst_table_a1_paper.json").read_text())["rows"]
}
REG = ErstRegistry.load()


# ---------------------------------------------------------------- inventory
def test_inventory_has_32_labels_31_discourse_relations_and_a_technical_same_unit():
    rt = FX["registry_tests"]
    assert len(REG.labels) == rt["expected_label_count"] == 32
    assert len(REG.discourse_labels) == rt["expected_true_discourse_relation_count"] == 31
    assert (
        set(REG.labels) - set(REG.discourse_labels) == set(rt["technical_labels"]) == {"SAME-UNIT"}
    )
    assert set(REG.labels) == set(rt["must_include"])


def test_labels_and_nuclearity_symbols_equal_the_papers_table_a1():
    assert {r.label: r.primary_nuclearity_symbol for r in REG.relations} == PAPER
    assert len(PAPER) == 32


def test_hierarchy_is_coarse_dash_fine_for_every_discourse_relation():
    h = REG.hierarchy()
    assert len([c for c in h if c != "technical"]) == 14 and h["technical"] == ["SAME-UNIT"]
    for r in REG.relations:
        if r.is_true_discourse_relation:
            assert r.label == f"{r.coarse_class.upper()}-{r.fine_relation.upper()}"


def test_choice_set_is_the_31_relations_plus_no_relation_and_never_same_unit():
    cs = REG.choice_set()
    assert len(cs) == 32 and cs[-1] == NO_RELATION and "SAME-UNIT" not in cs


def test_nuclearity_distribution_matches_the_source():
    from collections import Counter

    assert Counter(r.primary_nuclearity_symbol for r in REG.relations) == {
        "→←": 19,
        "Λ": 7,
        "←": 3,
        "→": 3,
    }


@pytest.mark.parametrize(
    "label",
    ["CAUSAL-REASON", "causal-cause", "synonym_of", "same_as", "EQUIVALENT-TO", "", "SAME_UNIT"],
)
def test_unknown_labels_fail_closed(label):
    with pytest.raises(UnknownErstLabel):
        REG.get(label)
    assert label not in REG


def _rel(**kw):
    base = {
        "label": "CAUSAL-CAUSE",
        "coarse_class": "causal",
        "fine_relation": "cause",
        "primary_nuclearity_symbol": "→←",
        "is_true_discourse_relation": True,
        "definition": "d",
    }
    return {**base, **kw}


def test_loader_rejects_a_bad_symbol_a_bad_name_and_a_mislabelled_technical_label():
    ErstRelation(**_rel())
    for bad in (
        _rel(primary_nuclearity_symbol="<-"),
        _rel(label="CAUSAL-REASON"),
        _rel(is_true_discourse_relation=False),  # not in TECHNICAL_LABELS
        _rel(
            label="SAME-UNIT", coarse_class="technical", fine_relation="same-unit"
        ),  # technical but marked true
    ):
        with pytest.raises(ValidationError):
            ErstRelation(**bad)


def test_loader_rejects_duplicates_and_signal_kind_mismatch(tmp_path):
    raw = yaml.safe_load((REPO / "configs/erst_relations.yaml").read_text())
    raw["relations"].append(dict(raw["relations"][0]))
    p = tmp_path / "r.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True))
    with pytest.raises(ValueError, match="duplicate"):
        ErstRegistry.load(p)
    raw = yaml.safe_load((REPO / "configs/erst_relations.yaml").read_text())
    raw["signal_types"]["non_dm"].append("invented")
    p.write_text(yaml.safe_dump(raw, allow_unicode=True))
    with pytest.raises(ValueError, match="signal kinds"):
        ErstRegistry.load(p)


# ---------------------------------------------------------------- edges
def edge(label, **kw):
    base = {
        "edge_kind": "primary",
        "label": label,
        "evidence": "a quote",
        "nucleus_units": ["u1"],
        "satellite_unit": "u2",
        "satellite_position": "after",
        "from_unit": None,
        "to_unit": None,
        "signals": [],
        "concurrent_labels": [],
    }
    return {**base, **kw}


def test_satellite_relations_need_one_nucleus_one_satellite_and_a_position():
    ErstEdge(**edge("CAUSAL-CAUSE"))
    ErstEdge(**edge("CAUSAL-CAUSE", satellite_position="before"))  # either direction is allowed
    for bad in (
        edge("CAUSAL-CAUSE", nucleus_units=["u1", "u3"]),
        edge("CAUSAL-CAUSE", satellite_unit=None),
        edge("CAUSAL-CAUSE", satellite_position=None),
    ):
        with pytest.raises(ValidationError):
            ErstEdge(**bad)


def test_multinuclear_relations_need_two_nuclei_and_no_satellite():
    ErstEdge(
        **edge(
            "JOINT-LIST",
            nucleus_units=["u1", "u2", "u3"],
            satellite_unit=None,
            satellite_position=None,
        )
    )
    for bad in (
        edge("JOINT-LIST", nucleus_units=["u1"], satellite_unit=None, satellite_position=None),
        edge("JOINT-LIST", nucleus_units=["u1", "u2"]),  # carries a satellite
    ):
        with pytest.raises(ValidationError):
            ErstEdge(**bad)


def test_fixed_orientation_symbols_are_enforced_for_primary_edges():
    ErstEdge(**edge("ELABORATION-ADDITIONAL", satellite_position="after"))  # ←
    ErstEdge(**edge("TOPIC-QUESTION", satellite_position="before"))  # →
    with pytest.raises(ValidationError):
        ErstEdge(**edge("ELABORATION-ADDITIONAL", satellite_position="before"))
    with pytest.raises(ValidationError):
        ErstEdge(**edge("TOPIC-QUESTION", satellite_position="after"))


def test_secondary_edges_keep_a_direction_and_never_a_fabricated_nuclearity():
    sec = edge(
        "JOINT-SEQUENCE",
        edge_kind="secondary",
        nucleus_units=[],
        satellite_unit=None,
        satellite_position=None,
        from_unit="u1",
        to_unit="u2",
    )
    ErstEdge(**sec)
    for bad in (
        {**sec, "nucleus_units": ["u1"]},
        {**sec, "satellite_unit": "u2"},
        {**sec, "satellite_position": "after"},
        {**sec, "to_unit": None},
        edge("CAUSAL-CAUSE", from_unit="u1", to_unit="u2"),  # a primary edge must not use from/to
    ):
        with pytest.raises(ValidationError):
            ErstEdge(**bad)


def test_edges_need_evidence_known_non_technical_labels_and_concurrent_labels_too():
    for bad in (
        edge("CAUSAL-CAUSE", evidence="  "),
        edge("CAUSAL-REASON"),
        edge("SAME-UNIT", nucleus_units=["u1", "u2"], satellite_unit=None, satellite_position=None),
        edge("CAUSAL-CAUSE", concurrent_labels=["NOPE"]),
        edge("CAUSAL-CAUSE", concurrent_labels=["SAME-UNIT"]),
    ):
        with pytest.raises(ValidationError):
            ErstEdge(**bad)
    ErstEdge(**edge("CAUSAL-CAUSE", concurrent_labels=["EXPLANATION-EVIDENCE"]))


# ---------------------------------------------------------------- signals
def test_signals_cover_dm_plus_seven_types_with_the_papers_subtypes():
    assert set(REG.signals) == {
        "discourse_marker",
        "graphical",
        "lexical",
        "morphological",
        "numerical",
        "reference",
        "semantic",
        "syntactic",
    }
    assert "antonymy" in REG.subtypes("semantic") and "reported speech" in REG.subtypes("syntactic")
    ErstSignal(kind="discourse_marker", subtype=None, anchor_text="but")
    ErstSignal(kind="semantic", subtype="antonymy", anchor_text="cheap ... expensive")
    ErstSignal(kind="graphical", subtype="layout", anchor_text=None)  # the one unanchored kind


@pytest.mark.parametrize(
    "kw",
    [
        {"kind": "discourse_marker", "subtype": "x", "anchor_text": "but"},
        {"kind": "discourse_marker", "subtype": None, "anchor_text": None},
        {"kind": "semantic", "subtype": "synonym_of", "anchor_text": "x"},
        {"kind": "semantic", "subtype": None, "anchor_text": "x"},
        {"kind": "semantic", "subtype": "antonymy", "anchor_text": None},
        {"kind": "invented", "subtype": None, "anchor_text": "x"},
    ],
)
def test_bad_signals_are_rejected(kw):
    with pytest.raises(ValidationError):
        ErstSignal(**kw)


def test_a_semantic_signal_never_licenses_a_domain_relation():
    for sub in REG.subtypes("semantic"):
        for rel in ("synonym_of", "part_of", "equivalent_to", "is_a"):
            assert G.signal_licenses_domain_relation("semantic", sub, rel) is False


# ---------------------------------------------------------------- guards
def allowed(label, effect, **kw):
    return G.check_kg_effect(REG, label, effect, **kw).allowed


def test_same_unit_has_no_kg_effect_at_all():
    assert not any(
        allowed("SAME-UNIT", e)
        for e in (G.PAIR_PRIORITY, G.SAME_CONCEPT_CANDIDATE, G.DOCUMENT_STRUCTURE, G.DOMAIN_EDGE)
    )


def test_a_label_alone_never_creates_a_domain_edge():
    for label in REG.discourse_labels:
        assert not allowed(label, G.DOMAIN_EDGE, relation="uses")


def test_restatement_may_only_queue_a_candidate_and_never_an_equivalence_edge():
    assert allowed("RESTATEMENT-REPETITION", G.SAME_CONCEPT_CANDIDATE)
    assert not allowed("CAUSAL-CAUSE", G.SAME_CONCEPT_CANDIDATE)
    for label in ("RESTATEMENT-REPETITION", "RESTATEMENT-PARTIAL"):
        assert not allowed(
            label, G.DOMAIN_EDGE, relation="equivalent_to", independent_domain_evidence=True
        )
        assert not allowed(
            label, G.DOMAIN_EDGE, relation="part_of", independent_domain_evidence=True
        )


def test_list_condition_organisation_attribution_and_contrast_guards():
    assert not allowed(
        "JOINT-LIST", G.DOMAIN_EDGE, relation="contrasts_with", independent_domain_evidence=True
    )
    assert not allowed(
        "JOINT-LIST", G.DOMAIN_EDGE, relation="trades_off_with", independent_domain_evidence=True
    )
    assert not allowed(
        "CONTINGENCY-CONDITION",
        G.DOMAIN_EDGE,
        relation="prerequisite_of",
        independent_domain_evidence=True,
    )
    assert allowed(
        "CONTINGENCY-CONDITION",
        G.DOMAIN_EDGE,
        relation="requires",
        independent_domain_evidence=True,
    )
    assert not allowed(
        "ORGANIZATION-HEADING", G.DOMAIN_EDGE, relation="part_of", independent_domain_evidence=True
    )
    assert allowed("ORGANIZATION-HEADING", G.DOCUMENT_STRUCTURE) and not allowed(
        "CAUSAL-CAUSE", G.DOCUMENT_STRUCTURE
    )
    assert not allowed("ATTRIBUTION-POSITIVE", G.DOMAIN_EDGE, relation="uses")
    assert allowed(
        "ATTRIBUTION-POSITIVE", G.DOMAIN_EDGE, relation="uses", independent_domain_evidence=True
    )
    assert not allowed(
        "ADVERSATIVE-CONTRAST",
        G.DOMAIN_EDGE,
        relation="contrasts_with",
        independent_domain_evidence=True,
    )
    assert allowed(
        "ADVERSATIVE-CONTRAST",
        G.DOMAIN_EDGE,
        relation="contrasts_with",
        independent_domain_evidence=True,
        grounded_dimension=True,
    )


def test_pair_priority_is_always_allowed_and_unknown_labels_raise():
    assert all(allowed(label, G.PAIR_PRIORITY) for label in REG.discourse_labels)
    with pytest.raises(UnknownErstLabel):
        G.check_kg_effect(REG, "NOPE", G.PAIR_PRIORITY)
    assert not allowed("CAUSAL-CAUSE", "invented_effect")


def test_merge_gate_defers_to_the_lexicon_on_the_lexicons_own_forms():
    lex = Lexicon.load()
    for a, b in (
        ("High-Level Data Link Control (HDLC)", "Synchronous Data Link Control (SDLC)"),
        ("Internet", "internetworking"),
        ("CRC", "error-detecting code"),
    ):
        assert lex.is_different(a, b)
        assert not G.merge_gate(lex, a, b).allowed
    assert G.merge_gate(lex, "frame", "packet").allowed is (not lex.is_different("frame", "packet"))
    assert G.merge_gate(None, "a", "b").allowed


# ---------------------------------------------------------------- the audit
def test_audit_without_the_paper_text_has_no_failed_check_and_marks_source_checks_skipped():
    a = A.run_audit(None)
    assert a["failed_checks"] == 0
    skipped = {c["id"] for c in a["checks"] if c["status"] == "skipped"}
    assert {
        "F1_definitions_vs_paper",
        "H1_signal_types_vs_paper",
        "I1_secondary_edge_rule_vs_paper",
    } <= skipped
    ids = {c["id"] for c in a["checks"]}
    assert {
        "A1_counts",
        "B1_labels_equal_paper_table_A1",
        "J1_semantic_guards",
        "K3_equivalent_to_stays_retired",
        "L1_unknown_labels_fail_closed",
    } <= ids


@pytest.mark.skipif(not A.PAPER_TXT.exists(), reason="the local copy of the paper is not present")
def test_audit_against_the_local_paper_text_passes_every_source_check():
    a = A.run_audit(A.PAPER_TXT.read_text(encoding="utf-8", errors="replace"))
    assert a["failed_checks"] == 0
    assert not [c for c in a["checks"] if c["kind"] == "source" and c["status"] != "pass"]


def test_equivalent_to_is_absent_from_the_active_registry_and_no_label_collides_with_a_domain_name():
    a = A.run_audit(None)
    by = {c["id"]: c for c in a["checks"]}
    assert by["K3_equivalent_to_stays_retired"]["status"] == "pass"
    assert by["K2_no_label_equals_a_domain_relation_name"]["status"] == "pass"
    assert by["K1_mapping_targets_are_inventory_labels"]["status"] == "pass"
