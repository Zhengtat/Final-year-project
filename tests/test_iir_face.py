"""CR-003 §3 / CR-005 acceptance tests: iir_face loader, on small fixtures (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cumap.data.iir_face import (
    _annotation_filename,
    load_iir_face,
    parse_gold_concepts,
    parse_iir_sections,
)

FIXTURES = Path(__file__).parent / "fixtures" / "iir_face"


def test_parse_iir_sections_reads_tab_separated_rows():
    sections = parse_iir_sections(FIXTURES / "book_section_samples" / "iir.sections.txt")
    assert [s.section_id for s in sections] == ["iir_1", "iir_1_1", "iir_2_1"]
    assert [s.order_index for s in sections] == [0, 1, 2]


def test_parse_iir_sections_maps_chapter_num_and_title():
    sections = parse_iir_sections(FIXTURES / "book_section_samples" / "iir.sections.txt")
    s = sections[0]
    assert s.chapter_num == 1
    assert s.chapter_title == "Boolean retrieval"
    s2 = sections[2]
    assert s2.chapter_num == 2
    assert s2.chapter_title == "The term vocabulary and postings lists"


def test_parse_iir_sections_word_count_and_text():
    sections = parse_iir_sections(FIXTURES / "book_section_samples" / "iir.sections.txt")
    assert sections[0].text.startswith("Information retrieval is finding")
    assert sections[0].word_count == len(sections[0].text.split())


@pytest.mark.parametrize(
    "section_id,expected",
    [("iir_1", "iir-1.csv"), ("iir_1_1", "iir-1.1.csv"), ("iir_2_1", "iir-2.1.csv")],
)
def test_annotation_filename_mapping(section_id, expected):
    assert _annotation_filename(section_id) == expected


def test_parse_gold_concepts_majority_vote():
    df = parse_gold_concepts(FIXTURES / "annotation", ["iir_1"])
    row = df[df["concept"] == "information retrieval"].iloc[0]
    assert bool(row["is_gold"]) is True
    assert row["n_annotators_yes"] == 3

    not_gold = df[df["concept"] == "linearly scanning"].iloc[0]
    assert bool(not_gold["is_gold"]) is False


def test_parse_gold_concepts_keeps_aliases_separate_from_canonical():
    df = parse_gold_concepts(FIXTURES / "annotation", ["iir_1"])
    row = df[df["concept"] == "grepping"].iloc[0]
    assert row["aliases"] == ["grep"]


def test_parse_gold_concepts_2_of_3_is_gold():
    df = parse_gold_concepts(FIXTURES / "annotation", ["iir_1"])
    row = df[df["concept"] == "pattern matching"].iloc[0]
    assert row["n_annotators_yes"] == 2
    assert bool(row["is_gold"]) is True  # majority (>=2 of 3)


def test_parse_gold_concepts_across_multiple_sections():
    df = parse_gold_concepts(FIXTURES / "annotation", ["iir_1", "iir_1_1", "iir_2_1"])
    assert set(df["section_id"]) == {"iir_1", "iir_1_1", "iir_2_1"}
    assert len(df) == 4 + 2 + 2  # rows per fixture file


def test_parse_gold_concepts_handles_float_formatted_votes(tmp_path):
    """Real data has some rows as "1.0"/"0.0" instead of "1"/"0"."""
    annotation_dir = tmp_path / "annotation"
    annotation_dir.mkdir()
    (annotation_dir / "iir-9.csv").write_text(
        "Concepts,Annotator 1,Annotator 2,Annotator 3\n['index'],1.0,1,0.0\n"
    )
    df = parse_gold_concepts(annotation_dir, ["iir_9"])
    assert df.iloc[0]["n_annotators_yes"] == 2


def test_parse_gold_concepts_handles_unescaped_apostrophe(tmp_path):
    """Real data (iir-9.1.csv, chapter 9) has one row with an unescaped apostrophe
    inside a single-quoted item -- "['nonrelevant document's vector']" -- which
    breaks ast.literal_eval outright. Confirmed the only such row across all 86
    annotation files as fetched; falls back to treating the bracket content as one
    alias string, which is correct for this (single-item) case.
    """
    annotation_dir = tmp_path / "annotation"
    annotation_dir.mkdir()
    (annotation_dir / "iir-9.1.csv").write_text(
        "Concepts,Annotator 1,Annotator 2,Annotator 3\n['nonrelevant document's vector'],1,1,0.0\n"
    )
    df = parse_gold_concepts(annotation_dir, ["iir_9_1"])
    assert df.iloc[0]["concept"] == "nonrelevant document's vector"
    assert df.iloc[0]["aliases"] == []


def test_parse_gold_concepts_missing_annotation_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_gold_concepts(tmp_path, ["iir_99"])


def test_load_iir_face_end_to_end(tmp_path):
    raw_dir = tmp_path / "iir_face"
    (raw_dir / "IIR-dataset" / "book_section_samples").mkdir(parents=True)
    (raw_dir / "IIR-dataset" / "annotation").mkdir(parents=True)
    (raw_dir / "IIR-dataset" / "book_section_samples" / "iir.sections.txt").write_text(
        (FIXTURES / "book_section_samples" / "iir.sections.txt").read_text()
    )
    for f in (FIXTURES / "annotation").glob("*.csv"):
        (raw_dir / "IIR-dataset" / "annotation" / f.name).write_text(f.read_text())

    sections, gold = load_iir_face(raw_dir)
    assert len(sections) == 3
    assert len(gold) == 8
