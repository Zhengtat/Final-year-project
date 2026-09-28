from __future__ import annotations

from pathlib import Path

from cumap.gold.validate import normalise_whitespace, validate_gold_dir, verify_quote

FIXTURES = Path(__file__).parent / "fixtures" / "gold"

SECTIONS = {
    "6.3": "This section describes slow start.\n\ncwnd roughly doubles every RTT during this phase.",
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
    issues = validate_gold_dir(FIXTURES / "good", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    assert issues == []


def test_bad_expert_fixture_reports_unverified_quote_and_unknown_relation():
    issues = validate_gold_dir(FIXTURES / "bad", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    messages = [str(i) for i in issues]
    assert any("evidence quote not found" in m for m in messages)
    assert any("unknown relation" in m for m in messages)


def test_bad_student_fixture_reports_unverified_evidence_span():
    issues = validate_gold_dir(FIXTURES / "bad", sections_by_id=SECTIONS, answers_by_id=ANSWERS)
    messages = [str(i) for i in issues]
    assert any("evidence_span text not found" in m for m in messages)


def test_empty_gold_dir_has_no_issues(tmp_path):
    (tmp_path / ".gitkeep").touch()
    assert validate_gold_dir(tmp_path) == []


def test_nonexistent_gold_dir_has_no_issues(tmp_path):
    assert validate_gold_dir(tmp_path / "does-not-exist") == []
