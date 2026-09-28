from __future__ import annotations

import yaml

from cumap.gold.mismatch_report import (
    agreement_by_category,
    collect_chain_link_type_counts,
    collect_match_type_counts,
    generate_mismatch_report,
)


def test_empty_dir_has_no_counts(tmp_path):
    assert collect_match_type_counts(tmp_path / "does-not-exist") == {}


def test_counts_match_types_and_missing(tmp_path):
    student_dir = tmp_path / "student_pilot"
    student_dir.mkdir()
    (student_dir / "a_1.yaml").write_text(
        yaml.safe_dump(
            {
                "edges": [{"match_type": "exact"}, {"match_type": "exact"}, {"match_type": None}],
                "missing_expected_edges": ["E-1"],
            }
        )
    )

    counts = collect_match_type_counts(student_dir)
    assert counts["exact"] == 2
    assert counts["(unset)"] == 1
    assert counts["missing"] == 1


def test_generate_report_handles_no_gold_yet(tmp_path):
    out_path = generate_mismatch_report(tmp_path / "no_such_dir", tmp_path / "report.md")
    text = out_path.read_text()
    assert "No gold student graphs found yet" in text


def test_collect_chain_link_type_counts(tmp_path):
    student_dir = tmp_path / "student_pilot"
    student_dir.mkdir()
    (student_dir / "a_1.yaml").write_text(
        yaml.safe_dump({"edges": [], "chain_links": [{"type": "cause"}, {"type": "cause"}, {"type": "purpose"}]})
    )
    counts = collect_chain_link_type_counts(student_dir)
    assert counts["cause"] == 2
    assert counts["purpose"] == 1


def test_agreement_by_category_groups_family_match_and_part_type_error_as_same_family():
    from collections import Counter

    match_counts = Counter({"exact": 3, "family_match": 2, "part_type_error": 1, "wrong_type": 4, "unsupported_extra": 1})
    categories = agreement_by_category(match_counts)
    assert categories["correct"] == 3
    assert categories["same_family_wrong_relation"] == 3  # family_match + part_type_error
    assert categories["wrong"] == 4
    assert categories["extra"] == 1


def test_report_includes_family_level_and_chain_link_sections(tmp_path):
    student_dir = tmp_path / "student_pilot"
    student_dir.mkdir()
    (student_dir / "a_1.yaml").write_text(
        yaml.safe_dump(
            {
                "edges": [{"match_type": "exact"}, {"match_type": "family_match"}],
                "chain_links": [{"type": "cause"}],
                "missing_expected_edges": [],
            }
        )
    )
    out_path = generate_mismatch_report(student_dir, tmp_path / "report.md")
    text = out_path.read_text()
    assert "By agreement category (family level)" in text
    assert "Chain-link types annotated" in text
    assert "same_family_wrong_relation" in text
