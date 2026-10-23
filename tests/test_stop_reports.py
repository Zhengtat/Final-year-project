"""CR-007 STOP 4 / STOP 5 report builders on a tiny synthetic run (no network, no key)."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from cumap.expert_kg import stop4, stop5
from cumap.schemas.relations import RelationRegistry

ROOT = Path(__file__).resolve().parents[1]
REG = RelationRegistry.from_yaml(ROOT / "configs" / "relations_v1.1.yaml")


def result(
    pid,
    group,
    outcome,
    relation="part_of",
    reason=None,
    family="classification_structure",
    ci=False,
):
    return {
        "outcome": outcome,
        "reason": reason,
        "family": family,
        "relation": relation,
        "direction": "forward",
        "statement": "s",
        "evidence_quote": "q",
        "qualifiers": {
            "polarity": "affirmed",
            "corrects_intuition": ci,
            "intuition": "x" if ci else None,
        },
        "pair": {
            "pair_id": pid,
            "section_id": "1.1",
            "concept_x_id": "a",
            "concept_y_id": "b",
            "sentence": "A is part of B.",
        },
        "direction_": None,
        "group": group,
    }


def make_run(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    (run / "snapshots").mkdir(parents=True)
    concepts = [
        {
            "concept_id": cid,
            "canonical_name": cid.upper(),
            "node_type": "Concept",
            "definition": None,
            "first_introduced": "1.1",
            "aliases": [],
            "description_history": [],
            "mentions": [{"section_id": "1.1", "role": "defined", "quote": "q"}],
        }
        for cid in ("a", "b", "c")
    ]
    res = [
        result("P1", "selected", "edge"),
        result("P2", "selected", "other"),
        result("P3", "selected", "rejected", reason="domain_range"),
        result("P4", "sample", "edge", ci=True),
    ]
    cp = {
        "run_id": "t",
        "concepts": concepts,
        "relation_results_v3": res,
        "concept_first_chapter": {"a": 1, "b": 1, "c": 1},
        "merges": [
            {
                "concept_id": "a",
                "alias": "A2",
                "section_id": "1.1",
                "llm_called": True,
                "overridden": False,
                "auto_merged": False,
                "similarity": 0.8,
            }
        ],
        "merge_review": [
            {
                "concept_id": "c",
                "alias": "C2",
                "candidate_name": "A",
                "quote": "q",
                "section_id": "1.1",
                "similarity": 0.6,
            }
        ],
        "related_candidates": [],
        "selection_stats": {"unique_candidate_pairs": 10},
    }
    (run / "checkpoint.json").write_text(json.dumps(cp))
    for ch in (1, 2, 3):
        d = run / "snapshots" / f"ch{ch}"
        d.mkdir()
        edges = (
            [
                {
                    "edge_id": "P1",
                    "source_concept_id": "a",
                    "relation": "part_of",
                    "target_concept_id": "b",
                    "family": "classification_structure",
                    "section_id": "1.1",
                }
            ]
            if ch == 1
            else []
        )
        (d / "edges.jsonl").write_text("\n".join(json.dumps(e) for e in edges))
    return run


def sections(tmp_path: Path) -> Path:
    p = tmp_path / "s.jsonl"
    p.write_text(json.dumps({"section_id": "1.1", "chapter_num": 1, "order_index": 0}))
    return p


def test_stop4_report_and_blind_sheets(tmp_path):
    run = make_run(tmp_path)
    out = stop4.build(run, sections(tmp_path), REG, tmp_path / "r.md", tmp_path / "checks")
    text = (tmp_path / "r.md").read_text()
    assert "edge accepted" in text and "1 / 3 = 33.3%" in text  # 1 edge of 3 selected pairs
    assert "corrects_intuition" not in text  # counts are held back from the report
    assert out["merge_rows"] == 2 and out["edge_rows"] == 1
    sheet = (tmp_path / "checks" / "cr007_edge_sheet.csv").read_text()
    assert "part_of" in sheet and "model" not in sheet.lower()  # blind: only the triple


def test_gate_rule_is_applied_as_written():
    assert stop5.gate_decision(5, 8, 7) == "keep"
    assert stop5.gate_decision(5, 5, 4) == "keep"  # exactly 80%
    assert stop5.gate_decision(13, 8, 6).startswith("drop")  # 75%
    assert stop5.gate_decision(4, 4, 4).startswith("drop")  # too few instances, 100% correct
    assert stop5.gate_decision(9, 0, 0).startswith("drop")  # nothing sampled


def test_gate_table_and_merge_buckets():
    edges = [{"relation": "identifies", "family": "f", "mark": "correct"}] * 4 + [
        {"relation": "acts_on", "family": "f", "mark": "incorrect"}
    ]
    rows = stop5.gate_table(edges, Counter({"identifies": 6, "acts_on": 3}), ["identifies"])
    assert rows[0]["decision"] == "keep" and rows[1]["decision"] == "report only"
    merges = [
        {"source": "merged", "mark": "different", "section": "1", "alias": "x", "name": "y"},
        {"source": "band", "mark": "same", "section": "1", "alias": "p", "name": "q"},
    ]
    out = stop5.merge_errors_by_bucket(merges, {("x", "1", "y"): 0.72, ("p", "1", "q"): 0.61})
    assert out[(">=0.70", "merged", "different")] == 1 and out[("<0.70", "band", "same")] == 1


def write_sheets(d: Path) -> None:
    d.mkdir()
    with (d / "cr007_edge_sheet.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "id",
                "source_sentence",
                "triple_to_judge",
                "as_a_sentence",
                "mark (correct/incorrect)",
                "note",
            ]
        )
        w.writerow([1, "s", "A -[part_of]-> B", "", "correct", ""])
    with (d / "cr007_edge_key.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "pair_id", "section", "family", "relation", "evidence_quote"])
        w.writerow([1, "P1", "1.1", "classification_structure", "part_of", "q"])
    with (d / "cr007_merge_sheet.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["id", "section", "name_A", "name_B", "evidence", "mark (same/different)", "note"]
        )
        w.writerow([1, "1.1", "A2", "A", "q", "Same", ""])
        w.writerow([2, "1.1", "C2", "A", "q", "same", ""])
    with (d / "cr007_merge_key.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "source"])
        w.writerow([1, "merged"])
        w.writerow([2, "band"])


def test_stop5_report_flags_provisional_marks_and_lists_flagged_edges(tmp_path):
    run = make_run(tmp_path)
    sheets = tmp_path / "checks"
    write_sheets(sheets)
    log = tmp_path / "calls.jsonl"
    log.write_text("")
    stop5.build_report(
        run, sheets, gated=["identifies"], tiers={}, log_path=log, out_md=tmp_path / "s5.md"
    )
    text = (tmp_path / "s5.md").read_text()
    assert "PROVISIONAL" in text  # not under data/gold
    assert "| identifies | 0 | 0 | 0 | n/a | drop" in text
    # CR-008 item 2: the legacy per-pair flag (P4 carries corrects_intuition=True) is ignored by the report
    assert "flagged of" not in text and "corrects_intuition" not in text.split("## 4.")[1].split(
        "## 5."
    )[0].replace("`corrects_intuition` count", "")
    assert "misconception stage has not run" in text
    assert "<0.70 | band | same | 1" in text


def test_marked_sheets_are_never_overwritten(tmp_path):
    run = make_run(tmp_path)
    checks = tmp_path / "checks"
    stop4.build(run, sections(tmp_path), REG, tmp_path / "r.md", checks)
    sheet = checks / "cr007_edge_sheet.csv"
    rows = list(csv.reader(sheet.open()))
    rows[1][-2] = "correct"  # the owner marks one edge
    with sheet.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    before = sheet.read_text()
    out = stop4.build(run, sections(tmp_path), REG, tmp_path / "r2.md", checks)
    assert out["sheets"].startswith("kept")  # the report is rebuilt, the marked sheet is untouched
    assert sheet.read_text() == before
    try:
        stop4.guard_marked_sheets(checks)
        raise AssertionError("expected a refusal")
    except FileExistsError:
        pass
