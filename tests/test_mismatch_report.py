from __future__ import annotations

import yaml

from cumap.gold.mismatch_report import collect_match_type_counts, generate_mismatch_report


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
