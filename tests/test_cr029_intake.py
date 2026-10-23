"""CR-029: same_concept queue reader and lexicon intake sheet (no network, no key, no write to data/gold/)."""

import csv
import json

import pytest
import yaml

from cumap.expert_kg import lexicon_intake as li
from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.lexicon_proposals import propose_from_marks


def _c(cid, name, typ="Concept", quote="q"):
    return {
        "concept_id": cid, "canonical_name": name, "node_type": typ, "aliases": [],
        "mentions": [{"section_id": "1.3", "quote": quote}],
    }  # fmt: skip


def _cp():
    return {
        "concepts": [
            _c("c_datagram", "datagram", "DataUnit", "a datagram is a packet"),
            _c("c_message", "message", "DataUnit"),
            _c("c_router", "router"),
            _c("c_gateway", "gateway"),
            _c("c_link", "link", "Component", "the link is shared"),
        ],
        "merges": [
            {"stage": "canonicalize_v4", "concept_id": "c_link", "alias": "physical link", "section_id": "1.3",
             "llm_called": True, "auto_merged": False, "rule_id": None, "reason": "SECRET-REASON", "similarity": 0.91,
             "evidence_quote": None},
            {"stage": "canonicalize_v4", "concept_id": "c_router", "alias": "gateway device", "section_id": "1.3",
             "llm_called": False, "auto_merged": True, "rule_id": "R0", "reason": None, "similarity": None,
             "evidence_quote": "called a router or gateway device"},
            {"stage": "generator", "concept_id": "c_router", "alias": "x", "section_id": "1.3", "rule_id": "G-link"},
        ],
        "merge_review": [],
        "taxonomy_candidates": [
            {"concept_id": "c_router", "matched_concept_id": "c_link", "decision": "narrower", "reason": "SECRET", "section_id": "1.3"}
        ],
        "relation_results_v3": [
            {"outcome": "same_concept", "reason": "queued_for_merge", "statement": "s",
             "evidence_quote": "datagram may be thought of as a synonym for message",
             "pair": {"pair_id": "RP-1.3-1", "section_id": "1.3", "concept_x_id": "c_datagram",
                      "concept_y_id": "c_message", "sentence": "datagram may be thought of as a synonym for message"}},
            {"outcome": "edge", "pair": {"pair_id": "RP-2", "section_id": "1.3", "concept_x_id": "c_router", "concept_y_id": "c_link"}},
        ],
    }  # fmt: skip


def _lex(tmp_path, entries=None):
    p = tmp_path / "lex.yaml"
    p.write_text(yaml.safe_dump({"version": "t", "same": [], "different": [], **(entries or {})}))
    return Lexicon.load(p, AliasConfig.load())


def test_reader_lists_each_same_concept_result_with_sentence_and_quote():
    q = li.same_concept_queue(_cp())
    assert len(q) == 1 and q[0]["x_name"] == "datagram" and "synonym" in q[0]["evidence_quote"]


def test_a_queued_pair_produces_one_row_and_the_sheet_is_blind(tmp_path):
    lex = _lex(tmp_path)
    cands = li.collect(_cp(), None, lex)
    sheet, info = li.build_sheet(cands, lex)
    dg = [c for c in sheet if {c.a, c.b} == {"datagram", "message"}]
    assert len(dg) == 1 and dg[0].source["kind"] == "same_concept_queue"
    csv_path, key_path = li.write_sheet("fx", sheet, info, tmp_path / "out")
    text = csv_path.read_text() + ""
    assert "SECRET" not in text and "0.91" not in text and "same_as_target" not in text
    assert next(csv.reader(text.splitlines())) == li.SHEET_COLUMNS
    key = json.loads(key_path.read_text())
    assert key["seed"] == li.DEFAULT_SEED and "SECRET-REASON" in key_path.read_text()
    with pytest.raises(FileExistsError):
        li.write_sheet("fx", sheet, info, tmp_path / "out")


def test_lexicon_different_pair_produces_no_row(tmp_path):
    lex = _lex(tmp_path, {"different": [{"id": "D1", "forms": ["datagram", "message"], "kind": "confusable",
                                         "scope": "book:pd6e", "status": "approved", "source": "t"}]})  # fmt: skip
    sheet, info = li.build_sheet(li.collect(_cp(), None, lex), lex)
    assert not [c for c in sheet if {c.a, c.b} == {"datagram", "message"}]
    assert info["skipped"]["lexicon_covered"] >= 1


def test_lexicon_same_pair_and_already_marked_pairs_are_skipped(tmp_path):
    lex = _lex(tmp_path, {"same": [{"id": "S1", "forms": ["physical link", "link"], "scope": "book:pd6e",
                                    "status": "approved", "source": "t"}]})  # fmt: skip
    cfg = lex.cfg
    marked = {frozenset((li.r1_key("datagram", cfg), li.r1_key("message", cfg)))}
    sheet, info = li.build_sheet(li.collect(_cp(), None, lex), lex, already_marked=marked)
    names = [{c.a, c.b} for c in sheet]
    assert {"physical link", "link"} not in names and {"datagram", "message"} not in names
    assert info["skipped"]["already_marked"] == 1


def test_cap_and_seeded_sample_are_reproducible(tmp_path):
    lex = _lex(tmp_path)
    cp = _cp()
    cp["taxonomy_candidates"] = [
        {"concept_id": "c_router", "matched_concept_id": "c_link", "decision": "narrower", "reason": "r", "section_id": f"1.{i}"}
        for i in range(30)
    ]  # fmt: skip
    cp["concepts"] += [_c(f"c_{i}", f"term {i}") for i in range(30)]
    for i, t in enumerate(cp["taxonomy_candidates"]):
        t["concept_id"] = f"c_{i}"
    a, _ia = li.build_sheet(li.collect(cp, None, lex), lex, seed=3)
    b, _ = li.build_sheet(li.collect(cp, None, lex), lex, seed=3)
    assert [(c.a, c.b) for c in a] == [(c.a, c.b) for c in b]
    assert sum(c.group == "u5_sample_narrower_broader_new" for c in a) == 5
    small, info = li.build_sheet(li.collect(cp, None, lex), lex, cap=3)
    assert len(small) == 3 and len(info["overflow_for_next_sheet"]) > 0


def test_never_writes_under_gold(tmp_path):
    with pytest.raises(ValueError):
        li.write_sheet("x", [], {}, tmp_path / "data" / "gold")


def test_marked_sheet_becomes_entries_with_sources_and_a_different_mark_blocks_the_pair(tmp_path):
    sheet = tmp_path / "lexicon_intake_fx.csv"
    sheet.write_text(
        "id,section,name_a,name_b,type_a,type_b,quote,mark,note\n"
        "1,1.3,datagram,message,DataUnit,DataUnit,datagram may be a synonym for message,different,distinct units\n"
        "2,1.3,router,gateway,Concept,Concept,router or gateway,same,\n"
        "3,1.3,link,router,Concept,Concept,x,neither,\n"
        "4,1.3,a,b,Concept,Concept,x,,\n"
    )
    rows, neither = li.marked_rows(sheet, "intake-fx")
    assert len(rows) == 2 and len(neither) == 1
    entries, skipped = propose_from_marks(rows, AliasConfig.load())
    assert not skipped and len(entries) == 2
    assert all("owner mark: intake-fx sheet row" in e["source"] for e in entries)
    lex = _lex(tmp_path, {"different": [e for e in entries if e["id"].startswith("D-")]
                          and [{**e, "kind": "confusable"} for e in entries if e["id"].startswith("D-")]})  # fmt: skip
    assert lex.is_different("datagram", "message")
    sheet2, _ = li.build_sheet(li.collect(_cp(), None, lex), lex)
    assert not [c for c in sheet2 if {c.a, c.b} == {"datagram", "message"}]
