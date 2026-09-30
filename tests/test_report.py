"""CR-005 §6 report tests: the page is self-contained, every chart carries a label-source tag
and provenance footer, nothing touches data/gold/, plus highlight/layout/data-assembly units.
Runs on a tiny synthetic run tree in tmp_path -- no real data, no network, no key.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import pytest

from cumap.config import get_settings, load_demo_slice
from cumap.eval.stats import wilson_ci
from cumap.expert_kg.face_eval import evaluate_mentions
from cumap.expert_kg.face_scorer import GoldConcept
from cumap.expert_kg.snapshots import ChapterSnapshot, SnapshotEdge, SnapshotNode, write_snapshot
from cumap.report.build import build_report
from cumap.report.data import (
    normalise_edge_mark,
    summarise_merge_marks,
    summarise_spotcheck,
)
from cumap.report.graph import GEdge, GNode, layout, render_section_graph
from cumap.report.provenance import LABEL_SOURCES, Provenance
from cumap.report.svg import grouped_bar_svg, hbar_svg
from cumap.report.viewer import Span, find_span, highlight_html

PROV = Provenance(run_id="r1", prompt_versions={"concepts": "v2"}, model="m", date="2026-01-01")
RUN = "run1"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _mention(name: str, role: str, section: str, quote: str) -> dict:
    return {
        "canonical_name": name,
        "node_type": "Concept",
        "role": role,
        "definition": None,
        "evidence_quote": quote,
        "section_id": section,
        "run_index": 0,
    }


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    sentence = "Networks consist of links between nodes."
    text2, text3 = f"{sentence} A link carries frames.", "A frame has a header."
    _write_jsonl(
        tmp_path / "data/interim/textbook_sections.jsonl",
        [
            {
                "section_id": "2.1",
                "chapter_num": 2,
                "section_title": "Links",
                "order_index": 1,
                "text": text2,
            },
            {
                "section_id": "3.1",
                "chapter_num": 3,
                "section_title": "Frames",
                "order_index": 2,
                "text": text3,
            },
        ],
    )
    mentions = {
        "2.1": [
            _mention("network", "defined", "2.1", "Networks consist of links"),
            _mention("link", "used", "2.1", "A link carries frames"),
        ],
        "3.1": [
            _mention("frame", "defined", "3.1", "A frame has a header"),
            _mention("link", "used", "3.1", "A frame"),
        ],
    }
    concepts = [
        {
            "concept_id": "c_network",
            "canonical_name": "network",
            "node_type": "Concept",
            "aliases": [],
            "first_introduced": "2.1",
            "mentions": [
                {"section_id": "2.1", "role": "defined", "quote": "q"},
                {"section_id": "3.1", "role": "used", "quote": "q"},
            ],
        },
        {
            "concept_id": "c_link",
            "canonical_name": "link",
            "node_type": "Concept",
            "aliases": ["links"],
            "first_introduced": "2.1",
            "mentions": [
                {"section_id": "2.1", "role": "used", "quote": "q"},
                {"section_id": "3.1", "role": "used", "quote": "q"},
            ],
        },
        {
            "concept_id": "c_frame",
            "canonical_name": "frame",
            "node_type": "Concept",
            "aliases": [],
            "first_introduced": "3.1",
            "mentions": [{"section_id": "3.1", "role": "defined", "quote": "q"}],
        },
    ]
    pair = {
        "pair_id": "RP-1",
        "section_id": "2.1",
        "concept_x_id": "c_network",
        "concept_y_id": "c_link",
        "sentence": sentence,
        "cooccurrence_count": 1,
        "cue_score": 1,
    }
    edge = {
        "pair": pair,
        "family": "classification_structure",
        "relation": "part_of",
        "direction": "reversed",
        "statement": "Links are parts of networks.",
        "evidence_quote": "consist of links",
        "qualifiers": {
            "polarity": "affirmed",
            "modality": "necessary",
            "conditions": [],
            "part_type": "component",
            "dimension": None,
            "surface_phrase": "consist of",
        },
    }
    checkpoint = {
        "run_id": RUN,
        "stage": "snapshots",
        "completed_section_ids": [],
        "mentions_by_section": mentions,
        "rejected_concepts": [],
        "concepts": concepts,
        "concept_first_chapter": {},
        "merges": [],
        "taxonomy_candidates": [],
        "rejected_relations": [],
        "pair_registry": [
            {
                "concept_x_id": "c_network",
                "concept_y_id": "c_link",
                "resolved": True,
                "reason": None,
                "evidence_sentences": [sentence],
                "edge": edge,
            },
            {
                "concept_x_id": "c_link",
                "concept_y_id": "c_frame",
                "resolved": True,
                "reason": "family_no_relation",
                "evidence_sentences": [],
                "edge": None,
            },
        ],
    }
    run_dir = tmp_path / "data/processed/kg" / RUN
    run_dir.mkdir(parents=True)
    (run_dir / "checkpoint.json").write_text(json.dumps(checkpoint))
    nodes = [
        SnapshotNode("c_network", "network", "Concept", 2, [], 1),
        SnapshotNode("c_link", "link", "Concept", 2, ["links"], 2),
    ]
    write_snapshot(
        ChapterSnapshot(
            RUN,
            2,
            nodes,
            [
                SnapshotEdge(
                    "RP-1",
                    "c_link",
                    "part_of",
                    "c_network",
                    "classification_structure",
                    2,
                    2,
                    "2.1",
                )
            ],
        ),
        run_dir / "snapshots",
    )
    write_snapshot(
        ChapterSnapshot(
            RUN,
            3,
            [
                SnapshotNode("c_frame", "frame", "Concept", 3, [], 1),
                SnapshotNode("c_link", "link", "Concept", 2, ["links"], 2),
            ],
        ),
        run_dir / "snapshots",
    )

    cfg = load_demo_slice().report
    for split, run in [("dev", cfg.iir_dev_run), ("test", cfg.iir_test_run)]:
        secs = cfg.iir_dev_sections if split == "dev" else cfg.iir_test_sections
        _write_jsonl(
            tmp_path / secs,
            [
                {
                    "section_id": f"iir_{split}",
                    "order_index": 1,
                    "text": "An inverted index maps terms to postings.",
                }
            ],
        )
        ev = evaluate_mentions(
            {
                f"iir_{split}": [
                    _mention("inverted index", "defined", f"iir_{split}", "inverted index"),
                    _mention("postings", "used", f"iir_{split}", "postings"),
                ]
            },
            [GoldConcept(f"iir_{split}", "inverted index"), GoldConcept(f"iir_{split}", "terms")],
            {f"iir_{split}": "An inverted index maps terms to postings."},
        )
        ev["run_id"] = run
        d = tmp_path / "data/processed/kg" / run
        d.mkdir(parents=True)
        (d / "face_eval.json").write_text(json.dumps(ev))
    _write_csv(
        tmp_path / cfg.merge_marks,
        [
            "id",
            "section_id",
            "alias_merged",
            "merged_into",
            "model_reason",
            "evidence_quote",
            "mark (ok/wrong)",
            "note",
        ],
        [
            [1, "2.1", "ISP", "Internet Service Provider", "r", "q", "ok", ""],
            [2, "2.1", "HDLC", "SDLC", "r", "q", "wrong", ""],
        ],
    )
    _write_csv(
        tmp_path / cfg.edge_sheet,
        [
            "id",
            "source_sentence",
            "triple_to_judge",
            "as_a_sentence",
            "mark (correct/incorrect/wrong-direction)",
            "note",
        ],
        [[1, "s", "t", "a", "correct", ""], [2, "s", "t", "a", "wrong-directon", ""]],
    )
    _write_csv(
        tmp_path / cfg.edge_key,
        ["id", "section", "family", "relation"],
        [[1, "2.1", "dependency", "requires"], [2, "2.1", "comparison", "contrasts_with"]],
    )
    (tmp_path / "data/gold").mkdir(parents=True)
    (tmp_path / "data/gold/sentinel.txt").write_text("human-owned")
    return tmp_path


@pytest.fixture
def built(tree: Path, tmp_path_factory) -> tuple[Path, Path]:
    out = tmp_path_factory.mktemp("out")
    html = build_report(RUN, get_settings(), load_demo_slice(), out_dir=out, root=tree)
    return html, tree


def test_html_is_self_contained(built):
    html = built[0].read_text(encoding="utf-8")
    assert not re.search(r'(?:src|href)\s*=\s*["\']?(?:https?:)?//', html)
    assert "@import" not in html and "<link" not in html
    assert not re.search(r"url\(\s*[\"']?https?:", html)
    assert re.findall(r"<script[^>]*>", html) == [
        '<script type="application/json" id="edge-data">',
        '<script type="application/json" id="steps-data">',
        "<script>",
    ]


def test_every_figure_has_provenance_footer_and_label_source(built):
    figs = sorted((built[0].parent / "figures").glob("*.svg"))
    assert len(figs) >= 15
    tags = tuple(LABEL_SOURCES.values())
    for f in figs:
        svg = f.read_text(encoding="utf-8")
        assert f"run {RUN}" in svg and "prompts:" in svg and "model:" in svg, f.name
        assert any(t in svg for t in tags), f.name


def test_chart_functions_require_a_valid_label_source():
    with pytest.raises(TypeError):
        grouped_bar_svg("t", ["a"], {"s": [1.0]}, provenance=PROV)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        hbar_svg("t", [("a", 1.0, 0)], provenance=PROV)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        grouped_bar_svg("t", ["a"], {"s": [1.0]}, provenance=PROV, label_source="vibes")
    with pytest.raises(ValueError):
        render_section_graph("t", [], [], provenance=PROV, label_source="")


def test_build_never_touches_data_gold(built):
    _, tree = built
    gold = tree / "data/gold"
    assert sorted(p.name for p in gold.iterdir()) == ["sentinel.txt"]
    assert (gold / "sentinel.txt").read_text() == "human-owned"
    src = Path(__file__).parents[1] / "src/cumap/report"
    assert not [p.name for p in src.glob("*.py") if "data/gold" in p.read_text()]


def test_build_is_deterministic(tree, tmp_path_factory):
    outs = []
    for _ in range(2):
        out = tmp_path_factory.mktemp("det")
        build_report(RUN, get_settings(), load_demo_slice(), out_dir=out, root=tree)
        outs.append({p.name: p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file()})
    assert outs[0] == outs[1]


def test_growth_graph_uses_directed_edges_and_marks_cross_chapter(built):
    html = built[0].read_text(encoding="utf-8")
    edges = json.loads(re.search(r'id="edge-data">(.*?)</script>', html, re.DOTALL).group(1))
    assert edges["RP-1"]["source"] == "link" and edges["RP-1"]["target"] == "network"
    # network is defined in 2.1 and used in 3.1 -> prerequisite candidate; link is never defined
    assert html.count('data-prereq="1"') == 1
    assert 'id="timebar"' in html and 'id="play"' in html and 'id="speed"' in html
    assert 'id="showall"' in html and 'id="showprereq"' in html
    steps = json.loads(re.search(r'id="steps-data">(.*?)</script>', html, re.DOTALL).group(1))
    assert [st["chapter"] for st in steps] == [2, 3]
    assert 'max="1"' in html  # two sections -> steps 0..1
    # link is first mentioned in section 0; frame first appears in section 1
    assert 'data-sec="1"' in html and 'data-sec="0"' in html


def test_growth_only_page_has_graph_and_no_other_tabs(built):
    html = (built[0].parent / "growth.html").read_text(encoding="utf-8")
    assert 'id="timebar"' in html and 'id="growth"' in html and 'id="steps-data"' in html
    assert 'id="t1"' not in html and 'id="t2"' not in html and "Concept extraction" not in html
    assert not re.search(r'(?:src|href)\s*=\s*["\']?(?:https?:)?//', html)


def test_growth3d_page_is_self_contained_and_has_clickable_concept_data(built):
    html = (built[0].parent / "growth3d.html").read_text(encoding="utf-8")
    assert '<canvas id="cv"' in html and 'id="timebar"' in html and 'id="panel"' in html
    assert not re.search(r'(?:src|href)\s*=\s*["\']?(?:https?:)?//', html)
    assert re.findall(r"<script[^>]*>", html) == [
        '<script type="application/json" id="d3d">',
        "<script>",
    ]
    d = json.loads(re.search(r'id="d3d">(.*?)</script>', html, re.DOTALL).group(1))
    assert {n["i"] for n in d["nodes"]} == set(d["concepts"]) == {"c_network", "c_link", "c_frame"}
    assert all(isinstance(n[k], float | int) for n in d["nodes"] for k in ("x", "y", "z"))
    link = d["concepts"]["c_link"]
    assert link["aliases"] == ["links"] and {m["sec"] for m in link["mentions"]} == {"2.1", "3.1"}
    assert d["edges"][0]["quote"] == "consist of links" and d["radius"] > 0


def test_layout3d_is_deterministic_finite_and_not_flat():
    from cumap.report.graph3d import layout3d

    ids = [f"n{i}" for i in range(20)]
    edges = [(f"n{i}", f"n{i + 1}") for i in range(9)] + [
        ("n0", "n5"),
        ("n10", "n11"),
        ("n12", "n13"),
    ]
    a = layout3d(ids, edges)
    assert a == layout3d(ids, edges) and set(a) == set(ids)
    assert all(math.isfinite(c) for p in a.values() for c in p)
    assert max(abs(a[f"n{i}"][2]) for i in range(10)) > 1.0  # main component uses the z axis


def test_animated_figure_reveals_nodes_at_their_section(built):
    svg = (built[0].parent / "figures" / "growth-animation.svg").read_text(encoding="utf-8")
    assert svg.count('attributeName="opacity"') >= 6 and "<script" not in svg
    assert 'begin="0.00s"' in svg and 'begin="1.20s"' in svg


def test_find_span_is_whitespace_tolerant_whole_word_and_case_insensitive():
    text = "The  packet\nheader and the Network are not a net."
    a, b = find_span(text, "packet header")
    assert text[a:b] == "packet\nheader"
    a, b = find_span(text, "net")
    assert text[a:b] == "net" and text[a - 2 : a] == "a "
    assert find_span(text, "network") is not None
    assert find_span(text, "missing term") is None


def test_highlight_escapes_html_and_drops_overlaps():
    text = "a <b>bold</b> & claim"
    out = highlight_html(text, [Span(3, 7, "x", 'tip "q"'), Span(5, 9, "y")])
    assert "<b>" not in out.replace(
        '<mark class="x" title="tip &quot;q&quot;">&lt;b&gt;</mark>', ""
    )
    assert out.count("<mark") == 1 and "&amp;" in out


def test_layout_is_deterministic_and_inside_canvas():
    ids = [f"n{i}" for i in range(14)]
    edges = [("n0", "n1"), ("n1", "n2"), ("n2", "n0"), ("n3", "n4"), ("n5", "n6"), ("n6", "n7")]
    a = layout(ids, edges, width=800, height=600)
    assert a == layout(ids, edges, width=800, height=600)
    assert set(a) == set(ids)
    assert all(0 <= x <= 800 and 0 <= y <= 700 for x, y in a.values())


def test_section_graph_dashes_negated_edges():
    nodes = [GNode("a", "A"), GNode("b", "B")]
    svg = render_section_graph(
        "t",
        nodes,
        [GEdge("e1", "a", "b", "requires", "dependency", negated=True)],
        provenance=PROV,
        label_source="model_output",
    )
    assert 'stroke-dasharray="6 4"' in svg and "negated" in svg


def test_owner_mark_summaries():
    assert [
        normalise_edge_mark(m)
        for m in ["ok", "correct", "wrong-directon", "wrong-direction", "incorrect", ""]
    ] == ["correct", "correct", "wrong_direction", "wrong_direction", "incorrect", "incorrect"]
    sheet = [
        {"id": "1", "mark (x)": "correct"},
        {"id": "2", "mark (x)": "wrong-direction"},
        {"id": "3", "mark (x)": "incorrect"},
    ]
    key = [{"id": "1", "family": "a"}, {"id": "2", "family": "b"}, {"id": "3", "family": "a"}]
    s = summarise_spotcheck(sheet, key)
    assert (s["strict"]["successes"], s["lenient"]["successes"], s["n"]) == (1, 2, 3)
    assert s["by_family"] == {"a": {"correct": 1, "incorrect": 1}, "b": {"wrong_direction": 1}}
    m = summarise_merge_marks(
        [
            {"alias_merged": "x", "merged_into": "y", "mark (ok/wrong)": "ok"},
            {"alias_merged": "p", "merged_into": "q", "mark (ok/wrong)": "wrong"},
        ]
    )
    assert m["ci"]["successes"] == 1 and m["wrong"][0]["alias"] == "p"
    w = wilson_ci(1, 2)
    assert m["ci"]["low"] == pytest.approx(w.low)


def test_face_eval_causes_and_metrics():
    ev = evaluate_mentions(
        {
            "s": [
                _mention("inverted index", "defined", "s", "q"),
                _mention("term frequency weight", "used", "s", "q"),
                _mention("postings", "mentioned", "s", "q"),
            ]
        },
        [
            GoldConcept("s", "inverted index"),
            GoldConcept("s", "term frequency"),
            GoldConcept("s", "dictionary"),
        ],
        {"s": "An inverted index. A term frequency weight. Postings."},
    )
    x = ev["metrics"]["exact"]["micro"]
    assert (x["tp"], x["fp"], x["fn"]) == (1, 2, 2)
    assert ev["cause_counts"]["false_positive"]["over-specific (contains a gold term)"] == 1
    assert (
        ev["cause_counts"]["false_negative"]["prediction is more specific than the gold term"] == 1
    )
