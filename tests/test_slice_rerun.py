"""CR-007 §6 slice re-run pieces (no network, no key): section loading, propagation, selection,
preflight and the PairRegistry adapter (only the selected group enters the graph)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from cumap.expert_kg import slice_rerun as sr
from cumap.expert_kg.pipeline import Checkpoint
from cumap.schemas.relations import RelationRegistry

ROOT = Path(__file__).resolve().parents[1]
REG = RelationRegistry.from_yaml(ROOT / "configs" / "relations_v1.1.yaml")

TEXT = {
    "1.1": "A switch forwards each frame. The router connects two networks.",
    "2.1": "A frame has a header. The switch stores the frame.",
}


def embed(text: str) -> np.ndarray:
    v = np.zeros(8)
    v[hash(text.split(":")[0]) % 8] = 1.0
    return v


def write_sections(path: Path) -> None:
    rows = [
        {
            "section_id": sid,
            "chapter_num": int(sid.split(".")[0]),
            "order_index": i,
            "text": text,
            "heading_path": [sid],
        }
        for i, (sid, text) in enumerate(TEXT.items())
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def mention(section: str, role: str, quote: str) -> dict:
    return {
        "section_id": section,
        "role": role,
        "quote": quote,
        "definition": None,
        "source": "llm",
    }


def concept(cid: str, name: str, ntype: str, mentions: list[dict]) -> dict:
    return {
        "concept_id": cid,
        "canonical_name": name,
        "node_type": ntype,
        "definition": None,
        "first_introduced": mentions[0]["section_id"],
        "aliases": [],
        "mentions": mentions,
        "description_history": [],
    }


def checkpoint() -> Checkpoint:
    cp = Checkpoint(run_id="t", stage="relations")
    cp.concepts = [
        concept(
            "c_switch", "switch", "Component", [mention("1.1", "defined", "A switch forwards")]
        ),
        concept("c_frame", "frame", "DataUnit", [mention("1.1", "used", "each frame")]),
        concept("c_router", "router", "Component", [mention("1.1", "used", "The router")]),
    ]
    return cp


def test_load_sections_filters_chapters_and_keeps_book_order(tmp_path):
    p = tmp_path / "s.jsonl"
    write_sections(p)
    assert [s.section_id for s in sr.load_sections(p, [1, 2])] == ["1.1", "2.1"]
    only = sr.load_sections(p, [2])
    assert [s.section_id for s in only] == ["2.1"] and only[0].domain == "computer networking"


def test_propagation_adds_mentioned_tags_in_other_sections(tmp_path):
    p = tmp_path / "s.jsonl"
    write_sections(p)
    sections = sr.load_sections(p, [1, 2])
    cp = checkpoint()
    cp.mentions_by_section = {
        "1.1": [
            {
                "canonical_name": "switch",
                "node_type": "Component",
                "role": "defined",
                "quote": "A switch forwards",
                "definition": None,
                "source": "llm",
            }
        ],
        "2.1": [],
    }
    added = sr.propagate_stage(cp, sections)
    assert added >= 1
    assert any(m["role"] == "mentioned" for m in cp.mentions_by_section["2.1"])


def test_preflight_relations_counts_only_unclassified_pairs():
    cp = checkpoint()
    cp.selected_pairs = [{"x": 1}] * 3
    cp.sample_pairs = [{"x": 1}] * 2
    cp.relation_results_v3 = [{}] * 1
    out = sr.preflight_relations(cp)
    assert out["pairs"] == 5 and out["already_classified"] == 1
    assert abs(out["est_usd_upper"] - 4 * sr.USD_PER_PAIR) < 1e-9


def pair_dict(x: str, y: str, pid: str) -> dict:
    return {
        "pair_id": pid,
        "section_id": "1.1",
        "concept_x_id": x,
        "concept_y_id": y,
        "sentence": "A switch forwards each frame.",
        "cooccurrence_count": 1,
        "cue_score": 1,
    }


def edge_result(group: str, x: str, y: str, pid: str) -> dict:
    return {
        "outcome": "edge",
        "reason": None,
        "family": "mechanism_process",
        "relation": "acts_on",
        "direction": "forward",
        "statement": "A switch forwards each frame.",
        "evidence_quote": "A switch forwards each frame",
        "qualifiers": {
            "polarity": "affirmed",
            "modality": "always",
            "conditions": [],
            "part_type": None,
            "dimension": None,
            "action_type": "forward",
            "surface_phrase": "forwards",
            "corrects_intuition": False,
            "intuition": None,
        },
        "pair": pair_dict(x, y, pid),
        "group": group,
    }


def test_only_the_selected_group_enters_the_graph():
    cp = checkpoint()
    cp.relation_results_v3 = [
        edge_result("selected", "c_switch", "c_frame", "RP-1"),
        edge_result("sample", "c_router", "c_frame", "RP-2"),
        {
            **edge_result("selected", "c_switch", "c_router", "RP-3"),
            "outcome": "other",
            "reason": "x",
        },
    ]
    reg = sr.build_pair_registry(cp)
    edges = [p for p in reg.all() if p.edge is not None]
    assert len(reg.all()) == 2  # the sample pair is never registered
    assert len(edges) == 1 and edges[0].edge.relation == "acts_on"


def test_select_stage_respects_budget_and_reports_stats(tmp_path):
    p = tmp_path / "s.jsonl"
    write_sections(p)
    sections = sr.load_sections(p, [1, 2])
    cp = checkpoint()
    stats = sr.select_stage(cp, sections, REG, embed, budget=2, min_per_section=1, sample=1)
    assert stats["budget"] == 2 and len(cp.selected_pairs) <= 2
    keys = {frozenset((q["concept_x_id"], q["concept_y_id"])) for q in cp.selected_pairs}
    assert all(
        frozenset((q["concept_x_id"], q["concept_y_id"])) not in keys for q in cp.sample_pairs
    )
