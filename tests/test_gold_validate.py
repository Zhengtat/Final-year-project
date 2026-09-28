from __future__ import annotations

from pathlib import Path

from cumap.gold.validate import normalise_whitespace, validate_gold_dir, verify_quote

FIXTURES = Path(__file__).parent / "fixtures" / "gold"

SECTIONS = {
    "6.3": "This section describes slow start.\n\ncwnd roughly doubles every RTT during this phase.",
    "4.2": "IPv6 defines extension header fields for optional functionality.",
}
ANSWERS = {
    "a_test0001": "My answer: cwnd roughly doubles every RTT, which is exponential growth.",
}


def test_verify_quote_exact_substring():
    assert verify_quote("hello world", "say hello world now") is True


def test_verify_quote_ignores_incidental_whitespace():
    assert verify_quote("hello   world", "say hello\nworld now") is True


def test_verify_quote_rejects_absent_text():
    assert verify_quote("goodbye", "say hello world now") is False


def test_normalise_whitespace_collapses_runs():
    assert normalise_whitespace("a   b\n\tc") == "a b c"


def test_good_fixtures_pass():
    result = validate_gold_dir(FIXTURES / "good", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    assert result.issues == []
    assert bool(result) is True


def test_bad_expert_fixture_reports_unverified_quote_and_unknown_relation():
    result = validate_gold_dir(FIXTURES / "bad", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    messages = [str(i) for i in result.issues]
    assert any("evidence quote not found" in m for m in messages)
    assert any("unknown relation" in m for m in messages)
    assert bool(result) is False


def test_bad_student_fixture_reports_unverified_evidence_span():
    result = validate_gold_dir(FIXTURES / "bad", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    messages = [str(i) for i in result.issues]
    assert any("evidence_span text not found" in m for m in messages)


def test_empty_gold_dir_has_no_issues(tmp_path):
    (tmp_path / ".gitkeep").touch()
    assert validate_gold_dir(tmp_path).issues == []


def test_nonexistent_gold_dir_has_no_issues(tmp_path):
    assert validate_gold_dir(tmp_path / "does-not-exist").issues == []


# ---------------------------------------------------------------------------
# CR-001 §5: version-aware validation
# ---------------------------------------------------------------------------


def test_v0_file_gets_a_hint_not_a_failure():
    result = validate_gold_dir(FIXTURES / "good", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    assert result.issues == []
    assert any("v0 file" in h and "migrate-v1" in h for h in result.hints)


def test_v1_good_fixture_passes_with_qualifiers_and_chain_links():
    result = validate_gold_dir(FIXTURES / "v1_good", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    assert result.issues == []
    assert result.hints == []  # v1 file, no migration hint expected


def test_v1_bad_fixture_reports_missing_part_type_and_dangling_chain_link():
    result = validate_gold_dir(FIXTURES / "v1_bad", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    messages = [str(i) for i in result.issues]
    assert any("missing required qualifier 'part_type'" in m for m in messages)
    assert any("from_edge_id" in m and "not found" in m for m in messages)
    assert any("relation_family" in m and "!=" in m for m in messages)


def test_force_version_1_applies_v1_rules_to_a_v0_shaped_file():
    """The good fixture has no registry_version key (implicit v0). Its expert edge
    (has_property) has no required qualifiers under v1 either, but its student edge
    has no surface_phrase — required on every StudentEdge under v1 — so forcing v1
    rules surfaces exactly that one issue. Proves --registry v1 actually changes
    which rules run (the same file is issue-free when validated as v0, above).
    """
    result = validate_gold_dir(FIXTURES / "good", sections_by_id=SECTIONS, answers_by_id=ANSWERS, force_version=1)
    messages = [str(i) for i in result.issues]
    assert len(result.issues) == 1
    assert "missing required surface_phrase" in messages[0]
    assert result.hints == []  # forced version means no "this is v0" hint


def test_force_version_1_flags_missing_qualifiers_on_an_otherwise_v0_file(tmp_path):
    gold_dir = tmp_path / "gold"
    (gold_dir / "expert_pilot").mkdir(parents=True)
    (gold_dir / "expert_pilot" / "q_x.yaml").write_text(
        """
edges:
  - edge_id: E-X
    source_id: c_a
    target_id: c_b
    relation: part_of
    layer: taxonomy
    statement: "a is part of b"
    criticality: core
    evidence: []
    validation: {}
    origin: manual
"""
    )
    result = validate_gold_dir(gold_dir, force_version=1)
    messages = [str(i) for i in result.issues]
    assert any("missing required qualifier 'part_type'" in m for m in messages)
