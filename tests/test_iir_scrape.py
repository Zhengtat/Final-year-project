"""CR-007 §3.1 scraper tests on an offline fixture book (tests/fixtures/iir_html): the tree walk,
the subtree / annotated-descendant rule, the intro rule, and the gold-presence gate."""

from pathlib import Path

import pytest

from cumap.data.iir_face import _annotation_filename
from cumap.data.iir_scrape import (
    annotated_path,
    build_tree,
    child_tree,
    gold_presence,
    own_body,
    parse_toc,
    scrape_chapter,
    scrape_iir,
    section_id,
)

FIX = Path(__file__).parent / "fixtures" / "iir_html"


def fetch(slug: str) -> str:
    return (FIX / slug.split("#")[0]).read_text(encoding="utf-8")


def test_toc_and_tree_come_from_child_links_not_a_next_chain():
    assert parse_toc(fetch("toc.html")) == {1: "ch7-1.html", 2: "ch8-1.html"}
    tree = child_tree(fetch("ch7-1.html"))
    assert [(d, h) for d, h, _ in tree][:4] == [
        (1, "s71.html"),
        (2, "s711.html"),
        (2, "s712.html"),
        (1, "s72.html"),
    ]
    nodes = build_tree(7, "ch7-1.html", fetch)
    assert set(nodes) == {
        (7,),
        (7, 1),
        (7, 1, 1),
        (7, 1, 2),
        (7, 2),
    }  # references (and its child) skipped
    assert "Bibliography" not in " ".join(n.own_text for n in nodes.values())
    assert own_body(fetch("s71.html")) == "Section 7.1 own text about gadgets."


def test_annotated_section_is_own_page_plus_unannotated_descendants():
    ids = [
        "iir-7.1",
        "iir-7.2",
    ]  # 7.1 has no annotated children: its subtree (7.1.1, 7.1.2) is included
    gold = {
        "iir_7_1": [("inverted gizmos", []), ("postings sprockets", [])],
        "iir_7_2": [("vector cogs", [])],
    }
    secs = {s.section_id: s for s in scrape_chapter(7, "ch7-1.html", ids, gold, fetch)}
    s71 = secs["iir_7_1"]
    assert (
        "gadgets" in s71.text and "inverted gizmos" in s71.text and "postings sprockets" in s71.text
    )
    assert "vector cogs" not in s71.text and s71.n_pages == 3
    # no bare iir-7 annotation: the FIRST annotated section also carries the chapter intro
    assert "Chapter seven intro" in s71.text and "Chapter seven intro" not in secs["iir_7_2"].text
    assert s71.excluded_reason is None and s71.presence == 1.0


def test_annotated_descendant_is_a_separate_section_not_folded_into_its_parent():
    ids = ["iir-7.1", "iir-7.1.1", "iir-7.1.2", "iir-7.2"]
    gold = {
        "iir_7_1": [("gadgets", [])],
        "iir_7_1_1": [("inverted gizmos", [])],
        "iir_7_1_2": [("postings sprockets", [])],
    }
    secs = {s.section_id: s for s in scrape_chapter(7, "ch7-1.html", ids, gold, fetch)}
    assert "gizmos" not in secs["iir_7_1"].text and "gizmos" in secs["iir_7_1_1"].text
    assert secs["iir_7_1_2"].text == "Subsection two discusses postings sprockets."


def test_bare_chapter_annotation_means_the_intro_is_its_own_section():
    secs = {
        s.section_id: s
        for s in scrape_chapter(
            8,
            "ch8-1.html",
            ["iir-8", "iir-8.1"],
            {"iir_8": [("relevance feedback", [])], "iir_8_1": [("Rocchio algorithm", [])]},
            fetch,
        )
    }
    assert "relevance feedback" in secs["iir_8"].text and "Rocchio" not in secs["iir_8"].text
    assert "bare intro" not in secs["iir_8_1"].text and secs["iir_8_1"].presence == 1.0


def test_gold_presence_gate_excludes_and_lists_never_scores_silently():
    gold = {
        "iir_7_2": [
            ("vector cogs", []),
            ("term a", ["alias b"]),
            ("missing one", []),
            ("missing two", []),
        ]
    }
    (s,) = scrape_chapter(7, "ch7-1.html", ["iir-7.2"], gold, fetch)
    assert s.presence == 0.25 and s.excluded_reason and "below the 90% gate" in s.excluded_reason
    (ok,) = scrape_chapter(7, "ch7-1.html", ["iir-7.2"], {"iir_7_2": [("vector cogs", [])]}, fetch)
    assert ok.excluded_reason is None
    (nogold,) = scrape_chapter(7, "ch7-1.html", ["iir-7.2"], {}, fetch)
    assert nogold.excluded_reason == "no gold concepts to check the text against"


def test_variant_b_recovers_a_section_whose_intro_text_sits_on_an_ancestor_page():
    ids = [
        "iir-7.1.1",
        "iir-7.1.2",
    ]  # 7.1 itself is un-annotated: its own page text is not in either subtree
    gold = {
        "iir_7_1_1": [("inverted gizmos", []), ("gadgets", [])],
        "iir_7_1_2": [("postings sprockets", [])],
    }
    secs = {s.section_id: s for s in scrape_chapter(7, "ch7-1.html", ids, gold, fetch)}
    s = secs["iir_7_1_1"]
    assert (
        s.presence_a == 0.5 and s.variant == "B" and s.presence == 1.0 and s.excluded_reason is None
    )
    assert secs["iir_7_1_2"].variant == "A"


def test_scrape_iir_walks_chapters_from_the_toc_and_helpers():
    out = scrape_iir({1: ["iir-1.1"], 2: ["iir-2"]}, {}, fetch, toc_slug="toc.html")
    assert [s.section_id for s in out] == ["iir_1_1", "iir_2"]
    assert annotated_path("iir-12.1.1") == annotated_path("iir_12_1_1") == (12, 1, 1)
    assert section_id((16, 4, 1)) == "iir_16_4_1"
    assert (
        gold_presence("The Rocchio  Algorithm", [("rocchio algorithm", [])]) == 1.0
        and gold_presence("x", []) is None
    )


def test_annotation_filenames_support_three_levels():
    assert _annotation_filename("iir_12_1_1") == "iir-12.1.1.csv"
    assert (
        _annotation_filename("iir_6") == "iir-6.csv"
        and _annotation_filename("iir_4_2") == "iir-4.2.csv"
    )
    with pytest.raises(ValueError):
        _annotation_filename("iir_x")
