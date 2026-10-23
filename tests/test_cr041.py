"""CR-041: owner-marked intake sheet -> a NEW lexicon version (no network, no key, no write to data/gold/)."""

import csv
import hashlib
import json

import pytest
import yaml

from cumap.config import REPO_ROOT
from cumap.expert_kg import lexicon_intake as li
from cumap.expert_kg.lexicon import Lexicon, LexiconError, production_lexicon_path

BASE = {
    "version": "0.3",
    "changelog": ["0.3 base"],
    "same": [
        {"id": "S-1", "canonical": "local area network", "forms": ["LAN", "local area network"],
         "scope": "book:pd6e", "status": "approved", "source": "owner mark: base row 1"},
    ],
    "different": [
        {"id": "D-1", "forms": ["frame", "packet"], "kind": "confusable", "scope": "book:pd6e",
         "status": "approved", "source": "owner mark: base row 2"},
    ],
}  # fmt: skip


def _base(tmp_path):
    p = tmp_path / "term_lexicon.yaml"
    p.write_text(yaml.safe_dump(BASE, sort_keys=False), encoding="utf-8")
    return p


def _sheet(tmp_path, rows):
    p = tmp_path / "lexicon_intake_demo.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=li.SHEET_COLUMNS)
        w.writeheader()
        for i, (a, b, mark, note) in enumerate(rows, 1):
            w.writerow({"id": i, "section": "1.3", "name_a": a, "name_b": b, "type_a": "Concept", "type_b": "Concept",
                        "quote": f"{a} {b}", "mark": mark, "note": note})  # fmt: skip
    return p


def test_marks_become_entries_and_conflicts_are_left_out(tmp_path):
    lex = Lexicon.load(_base(tmp_path))
    sheet = _sheet(tmp_path, [
        ("sendQ", "send queue", "same", ""),
        ("datagram", "message", "different", "kind of (message is generic)"),
        ("IP layer", "network layer", "Different", "instance (IP) vs generic layer 3"),
        ("data link protocol", "link-level protocol", "same", ""),  # an earlier sheet said different
        ("LAN", "local area network", "same", ""),  # already covered
        ("connectionless manner", "connectionless approach", "neither", "phrasing"),
        ("x", "y", "", ""),  # unmarked: ignored
    ])  # fmt: skip
    prior = li.prior_owner_marks(tmp_path, lex.cfg)  # no earlier sheets here
    key = frozenset(
        (li.r1_key("data link protocol", lex.cfg), li.r1_key("link-level protocol", lex.cfg))
    )
    prior[key] = {False}
    entries, left = li.entries_from_marks(sheet, "lexicon intake demo", lex, prior)
    ids = {e["id"]: e for e in entries}
    assert set(ids) == {
        "S-lexicon_intake_demo-1",
        "D-lexicon_intake_demo-2",
        "D-lexicon_intake_demo-3",
    }
    assert all(" " not in i for i in ids)
    assert ids["D-lexicon_intake_demo-2"]["kind"] == "kind_of"
    assert ids["D-lexicon_intake_demo-3"]["kind"] == "instance_of"
    assert ids["D-lexicon_intake_demo-2"]["why"].startswith("owner mark: kind of")
    assert "lexicon intake demo sheet row 1" in ids["S-lexicon_intake_demo-1"]["source"]
    assert [r["a"] for r in left["cross_sheet_conflict"]] == ["data link protocol"]
    assert [r["a"] for r in left["covered"]] == ["LAN"]
    assert [r["a"] for r in left["neither"]] == ["connectionless manner"]


def test_prior_marks_read_earlier_sheets_but_not_the_current_one(tmp_path):
    cfg = Lexicon.load(_base(tmp_path)).cfg
    with (tmp_path / "cr007_merge_sheet.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["id", "section", "name_A", "name_B", "evidence", "mark (same/different)", "note"]
        )
        w.writerow([8, "2.5", "data link protocol", "Link-level protocol", "", "different", ""])
    _sheet(tmp_path, [("a", "b", "same", "")])
    prior = li.prior_owner_marks(tmp_path, cfg, exclude="lexicon_intake_demo.csv")
    key = frozenset((li.r1_key("data link protocol", cfg), li.r1_key("link-level protocol", cfg)))
    assert prior[key] == {False}
    assert frozenset((li.r1_key("a", cfg), li.r1_key("b", cfg))) not in prior


def test_new_version_is_a_new_file_and_the_base_is_untouched(tmp_path):
    base = _base(tmp_path)
    before = hashlib.sha256(base.read_bytes()).hexdigest()
    lex = Lexicon.load(base)
    entries, _ = li.entries_from_marks(
        _sheet(tmp_path, [("sendQ", "send queue", "same", "")]), "lexicon intake demo", lex, {}
    )
    out = tmp_path / "term_lexicon_v0.4.yaml"
    new = li.write_lexicon_version(base, out, "0.4", entries, "0.4 test")
    assert new.version == "0.4" and len(new.entries) == 3
    assert hashlib.sha256(base.read_bytes()).hexdigest() == before
    assert new.same_set("sendQ") == new.same_set("send queue") is not None
    with pytest.raises(FileExistsError):
        li.write_lexicon_version(base, out, "0.4", entries, "again")
    with pytest.raises(FileExistsError):
        li.write_lexicon_version(base, base, "0.4", entries, "in place")


def test_a_contradicting_mark_is_refused_and_no_file_is_left(tmp_path):
    base = _base(tmp_path)
    bad = [{"id": "S-x-1", "canonical": "frame", "forms": ["frame", "packet"], "scope": "book:pd6e", "status": "approved",
            "source": "owner mark: x"}]  # fmt: skip
    out = tmp_path / "term_lexicon_v0.4.yaml"
    with pytest.raises(LexiconError):
        li.write_lexicon_version(base, out, "0.4", bad, "contradiction")
    assert not out.exists()


def test_production_lexicon_path_reads_the_policy():
    assert production_lexicon_path({}) == REPO_ROOT / "configs/term_lexicon.yaml"
    assert (
        production_lexicon_path({"term_lexicon": "configs/x.yaml"}) == REPO_ROOT / "configs/x.yaml"
    )


def test_repo_state_v03_frozen_and_v04_is_production():
    v03 = REPO_ROOT / "configs/term_lexicon.yaml"
    handoff = json.loads((REPO_ROOT / "reports/cr011_sleep/CR012_EVAL_HANDOFF.json").read_text())
    pinned = handoff["configs"]["term_lexicon"]["sha256"]
    assert (
        hashlib.sha256(v03.read_bytes()).hexdigest() == pinned
    )  # v0.3 is never edited (CR-011 handoff)
    assert Lexicon.load(v03).version == "0.3"
    prod = production_lexicon_path()
    assert prod.name == "term_lexicon_v0.4.yaml"
    lex = Lexicon.load(prod)
    assert lex.version == "0.4"
    assert lex.same_set("recvQ") == lex.same_set("receive queue") is not None
    assert lex.is_different("datagram", "message")
    # the owner's row 10 conflicts with the CR-007 sheet ("different") and is left out
    assert lex.same_set("data link protocol") is None or lex.same_set(
        "data link protocol"
    ) != lex.same_set("link-level protocol")
