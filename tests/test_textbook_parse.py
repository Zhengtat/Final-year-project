from __future__ import annotations

from pathlib import Path

from cumap.textbook.parse import parse_textbook

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "textbook"


def test_parses_all_leaf_sections_in_book_order():
    sections = parse_textbook(FIXTURE_ROOT)

    assert [s.section_id for s in sections] == ["1.1", "1.2"]
    assert [s.order_index for s in sections] == [0, 1]
    assert all(s.chapter_num == 1 and s.chapter_title == "Widgets" for s in sections)


def test_strips_directives_and_literal_blocks_keeps_prose():
    sections = parse_textbook(FIXTURE_ROOT)
    intro = next(s for s in sections if s.section_id == "1.1")

    assert "figure::" not in intro.text
    assert "widget.spin()" not in intro.text
    assert "mechanical" in intro.text  # bold markup unwrapped to plain text
    assert "**" not in intro.text
    assert "gizmo" in intro.text
    assert "sprocket" in intro.text
    assert "in practice" in intro.text  # inline literal unwrapped
    assert "``" not in intro.text


def test_captures_emphasized_terms():
    sections = parse_textbook(FIXTURE_ROOT)
    intro = next(s for s in sections if s.section_id == "1.1")

    assert "mechanical" in intro.emphasized_terms
    assert "gizmo" in intro.emphasized_terms


def test_subheadings_kept_as_text_not_separate_sections():
    sections = parse_textbook(FIXTURE_ROOT)
    details = next(s for s in sections if s.section_id == "1.2")

    assert len(sections) == 2  # 1.2.1 did not become its own Section
    assert "Spin Rate" in details.text
    assert "spin rate of a widget" in details.text


def test_no_section_has_empty_text():
    sections = parse_textbook(FIXTURE_ROOT)
    assert all(s.text.strip() and s.word_count > 0 for s in sections)
