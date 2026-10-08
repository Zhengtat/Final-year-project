"""CR-010 STOP 5: metric definitions, frozen reverse recovery, edge-quality arms, gate table, erst_direct validity.
Synthetic items only (no network, no key, no real annotations)."""

import pytest

from cumap.cr010 import stop5 as S
from cumap.erst.registry import ErstRegistry

RELS = {"is_a", "part_of", "uses", "causes"}


def item(
    i,
    rel,
    applies="no",
    e1="",
    e2="",
    direction="not_applicable",
    nuc="not_applicable",
    surv="no",
    losses=(),
    split="test",
    outcome="edge",
):
    d = {
        "item_id": f"RM{i:03d}",
        "split": split,
        "current_outcome": outcome,
        "name_x": "x",
        "name_y": "y",
        "a_current_semantic_relation_judgement": rel,
        "a_erst_applies_yes_no": applies,
        "a_erst_relation_1": e1,
        "a_erst_relation_2_optional": e2,
        "a_direction_judgement": direction,
        "a_nuclearity_judgement_if_relevant": nuc,
        "a_machine_useful_meaning_survives_yes_no": surv,
    }
    for c in S.LOSS_COLUMNS:
        d[f"a_{c}"] = "yes" if c in losses else ""
    return d


def test_mapping_metrics_follow_the_preregistered_definitions():
    items = [
        item(1, "is_a", "yes", "ELABORATION-ATTRIBUTE", surv="yes"),
        item(
            2,
            "part_of",
            "yes",
            "ELABORATION-ATTRIBUTE",
            surv="no",
            losses=("loss_part_whole_composition",),
        ),
        item(3, "uses", "no", surv="no"),  # silent loss: survives no, no category
        item(4, "none"),
        item(5, "other", "yes", "JOINT-LIST"),
    ]
    m = S.mapping_metrics(items, RELS)
    assert m["valid_relation_items"] == 3 and m["other_relation_items_outside_gates"] == 1
    assert m["erst_expressibility"]["k"] == 2 and m["semantic_preservation"]["k"] == 1
    assert m["mapping_loss_rate"]["rate"] == pytest.approx(2 / 3)
    assert m["critical_loss"]["k"] == 1 and m["silent_loss_survives_no_without_category"]["k"] == 1
    # both expressible items share a representation key but have different current relations -> both collide
    assert m["relation_collision_rate_among_expressible"]["k"] == 2


def test_reverse_recovery_is_fitted_on_dev_only_and_falls_back():
    dev = [
        item(i, "is_a", "yes", "ELABORATION-ATTRIBUTE", nuc="nucleus_a", split="dev")
        for i in range(3)
    ]
    dev += [item(10 + i, "uses", "no", split="dev") for i in range(2)]
    model = S.fit_recovery(dev, RELS)
    assert model["n_dev_items"] == 5 and model["NO_ERST"] == "uses" and model["global"] == "is_a"
    seen = item(20, "is_a", "yes", "ELABORATION-ATTRIBUTE", nuc="nucleus_a")
    assert S.recover(seen, model) == "is_a"
    other_dir = item(
        21, "is_a", "yes", "ELABORATION-ATTRIBUTE", direction="a_to_b", nuc="nucleus_a"
    )
    assert S.recover(other_dir, model) == "is_a"  # full key unseen -> (erst1, nuclearity) level
    unseen = item(22, "part_of", "yes", "CAUSAL-CAUSE")
    assert S.recover(unseen, model) == "is_a"  # global majority
    assert S.recover(item(23, "uses", "no"), model) == "uses"  # NO_ERST key


def test_macro_f1_and_represented_relations():
    held = [item(i, "is_a") for i in range(5)] + [item(10 + i, "uses") for i in range(2)]
    model = {"full": {}, "erst1_nuc": {}, "erst1": {}, "NO_ERST": "is_a", "global": "is_a"}
    r = S.reverse_eval(held, model, RELS)
    assert r["represented"]["is_a"] == {"n": 5, "recovered": 5, "recall": 1.0, "status": "PASS"}
    assert (
        r["represented"]["uses"]["status"] == "INSUFFICIENT_SUPPORT"
        and r["represented"]["uses"]["recovered"] == 0
    )
    assert 0 < r["macro_f1"] < 1


def test_edge_quality_counts_against_annotator_presence():
    held = [
        item(1, "is_a", outcome="edge"),
        item(2, "none", outcome="edge"),
        item(3, "uses", outcome="no_relation"),
        item(4, "none", outcome="no_relation"),
    ]
    q = S.edge_quality(held, S.current_predictions(held))
    assert (q["tp"], q["fp"], q["fn"], q["tn"]) == (1, 1, 1, 1) and q["precision"] == 0.5


def test_erst_direct_edge_needs_a_label_and_an_exact_quote():
    passage = "Packets are lost because buffers overflow."
    ok = {"label": "CAUSAL-CAUSE", "evidence": "because buffers overflow"}
    assert S.direct_edge_predicted(ok, passage) == (True, "edge")
    assert S.direct_edge_predicted({"label": S.NO_ERST, "evidence": None}, passage) == (
        False,
        "no_erst_relation",
    )
    assert (
        S.direct_edge_predicted(
            {"label": "CAUSAL-CAUSE", "evidence": "buffers never overflow"}, passage
        )[0]
        is False
    )


def test_schema_is_closed_and_offers_no_technical_label():
    schema = S.erst_direct_schema(ErstRegistry.load())
    base = {
        "label": "CAUSAL-CAUSE",
        "concurrent_label": None,
        "nuclearity": "nucleus_a",
        "evidence": "q",
        "signals": [],
        "confidence": 0.5,
    }
    assert schema.model_validate(base)
    for bad in (
        {"label": "SAME-UNIT"},
        {"label": "MADE-UP"},
        {"concurrent_label": S.NO_ERST},
        {"extra": 1},
    ):
        with pytest.raises(Exception):  # noqa: B017
            schema.model_validate({**base, **bad})


def test_gate_table_marks_unevaluable_gates_and_never_selects():
    m = S.mapping_metrics(
        [item(i, "is_a", "yes", "ELABORATION-ATTRIBUTE", surv="yes") for i in range(5)], RELS
    )
    rev = S.reverse_eval(
        [item(i, "is_a") for i in range(5)],
        {"full": {}, "erst1_nuc": {}, "erst1": {}, "NO_ERST": "is_a", "global": "is_a"},
        RELS,
    )
    cur = {"f1": 0.8, "precision": 0.9}
    g = {r["gate"]: r for r in S.gate_table(m, rev, cur, None, None)}
    assert g["Mapping agreement kappa"]["status"] == "NOT_EVALUABLE"
    assert g["eRST-direct edge-F1 difference"]["status"] == "NOT_EVALUABLE"
    assert g["eRST expressibility"]["status"] == "PASS"
    g2 = {r["gate"]: r for r in S.gate_table(m, rev, cur, {"f1": 0.7, "precision": 0.9}, None)}
    assert g2["eRST-direct edge-F1 difference"]["status"] == "FAIL"
    assert not hasattr(S, "select_architecture")
