"""CR-001 §7.3 acceptance tests: relation-agreement scoring (cumap eval relation-agreement)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from cumap.eval.relation_agreement import compute_agreement, write_agreement_report
from cumap.schemas.relations import RelationRegistry

V1_PATH = Path(__file__).parents[1] / "configs" / "relations_v1.yaml"


@pytest.fixture(scope="module")
def registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(V1_PATH)


def _sheet(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_perfect_agreement_gives_kappa_one(registry):
    rows_a = [
        {"item_id": f"RI-{i}", "relation": r, "direction": "x_to_y"}
        for i, r in enumerate(["causes", "causes", "is_a", "is_a", "prevents", "increases", "decreases", "no_relation"] * 3)
    ]
    rows_b = [dict(r) for r in rows_a]  # identical
    result = compute_agreement(_sheet(rows_a), _sheet(rows_b), registry)
    assert result["relation_kappa"] == pytest.approx(1.0)
    assert result["family_kappa"] == pytest.approx(1.0)
    assert result["direction_agreement_rate"] == pytest.approx(1.0)


def test_family_level_agreement_higher_than_relation_level_for_within_family_confusion(registry):
    # causes vs prevents: same family (cause_effect), different relation
    rows_a = [{"item_id": f"RI-{i}", "relation": "causes", "direction": "x_to_y"} for i in range(10)]
    rows_b = [{"item_id": f"RI-{i}", "relation": "prevents", "direction": "x_to_y"} for i in range(10)]
    result = compute_agreement(_sheet(rows_a), _sheet(rows_b), registry)
    assert result["relation_kappa"] < result["family_kappa"] or result["family_kappa"] == pytest.approx(1.0)


def test_confused_pairs_detects_over_20_percent_confusion(registry):
    # triggers vs causes confused in most items
    rows_a = [{"item_id": f"RI-{i}", "relation": "triggers", "direction": "x_to_y"} for i in range(8)] + [
        {"item_id": f"RI-{i}", "relation": "is_a", "direction": "x_to_y"} for i in range(8, 12)
    ]
    rows_b = [{"item_id": f"RI-{i}", "relation": "causes", "direction": "x_to_y"} for i in range(8)] + [
        {"item_id": f"RI-{i}", "relation": "is_a", "direction": "x_to_y"} for i in range(8, 12)
    ]
    result = compute_agreement(_sheet(rows_a), _sheet(rows_b), registry)
    confused_relations = {c["relation"] for c in result["confused_pairs"]}
    assert "triggers" in confused_relations
    assert "causes" in confused_relations
    assert "is_a" not in confused_relations  # perfect agreement on is_a


def test_direction_agreement_only_counts_items_with_matching_relation(registry):
    rows_a = [
        {"item_id": "RI-1", "relation": "causes", "direction": "x_to_y"},
        {"item_id": "RI-2", "relation": "causes", "direction": "x_to_y"},
        {"item_id": "RI-3", "relation": "is_a", "direction": "x_to_y"},  # relation mismatch, excluded
    ]
    rows_b = [
        {"item_id": "RI-1", "relation": "causes", "direction": "x_to_y"},  # direction agrees
        {"item_id": "RI-2", "relation": "causes", "direction": "y_to_x"},  # direction disagrees
        {"item_id": "RI-3", "relation": "part_of", "direction": "x_to_y"},
    ]
    result = compute_agreement(_sheet(rows_a), _sheet(rows_b), registry)
    assert result["direction_agreement_rate"] == pytest.approx(0.5)  # 1 of 2 comparable items agree


def test_missing_relation_treated_as_no_relation(registry):
    rows_a = [{"item_id": "RI-1", "relation": None, "direction": ""}]
    rows_b = [{"item_id": "RI-1", "relation": "no_relation", "direction": ""}]
    result = compute_agreement(_sheet(rows_a), _sheet(rows_b), registry)
    assert result["relation_kappa"] == pytest.approx(1.0)  # both effectively "no_relation"


def test_write_agreement_report_flags_low_kappa_relations(registry, tmp_path):
    rows_a = [{"item_id": f"RI-{i}", "relation": "triggers", "direction": "x_to_y"} for i in range(10)]
    rows_b = [{"item_id": f"RI-{i}", "relation": "causes", "direction": "x_to_y"} for i in range(10)]
    result = compute_agreement(_sheet(rows_a), _sheet(rows_b), registry)
    report_path = write_agreement_report(result, tmp_path / "report.md")
    text = report_path.read_text()
    assert "Cohen's κ" in text
    assert "confused" in text.lower()
