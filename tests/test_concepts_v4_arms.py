"""CR-009 §7.1/§11: comparison arms (mock client; no network, no key)."""

from pathlib import Path
from types import SimpleNamespace

import spacy

from cumap.concepts_v4 import arms
from cumap.llm.prompts import load_prompt

REPO = Path(__file__).parents[1]
NLP = spacy.load("en_core_web_sm")
BASE = load_prompt(REPO / "prompts", "concept_extraction", "v2")
SEC = {
    "section_id": "s1",
    "chapter_num": "1",
    "text": "A signal handler runs when the signal arrives. The kernel installs it. Each cell stores one bit.",
    "heading": "h",
}


def test_every_arm_is_marked_selection_ineligible():
    assert arms.SELECTION_ELIGIBLE is False


def test_c_sac_runs_only_quantity_and_format_checks_and_regenerates_at_most_once(monkeypatch):
    calls = []

    def gen(client, prompt, registry, nlp, sec, corrections="", fixture="default"):
        calls.append(corrections)
        return [
            {
                "canonical_name": f"x{i}",
                "node_type": "Concept",
                "role": "used",
                "evidence_quote": "A signal handler runs",
                "definition": None,
                "source": "llm",
            }
            for i in range(5)
        ]

    monkeypatch.setattr(arms, "_gen", gen)
    res = arms.run_c_sac(None, BASE, None, NLP, [SEC], progress=lambda *_: None)
    assert (
        res[0].calls == 2
        and len(calls) == 2
        and calls[0] == ""
        and calls[1].startswith("CORRECTIONS")
    )  # one regeneration, no more
    assert (
        res[0].items == []
    )  # every name was absent from its quote: the remaining flagged items are deleted


def test_c_sac_deletes_a_few_flagged_items_without_regenerating(monkeypatch):
    good = {
        "canonical_name": "signal handler",
        "node_type": "Concept",
        "role": "used",
        "evidence_quote": "A signal handler runs",
        "definition": None,
        "source": "llm",
    }
    bad = {**good, "canonical_name": "lock manager"}
    monkeypatch.setattr(
        arms,
        "_gen",
        lambda *a, **k: [
            good,
            good | {"canonical_name": "signal"},
            good | {"canonical_name": "handler"},
            bad,
        ],
    )
    res = arms.run_c_sac(
        None, BASE, None, NLP, [{**SEC, "text": "word " * 20}], progress=lambda *_: None
    )
    assert res[0].calls == 1 and [i["canonical_name"] for i in res[0].items] == [
        "signal handler",
        "signal",
        "handler",
    ]


def test_c_pive_adds_given_items_outright_accumulates_and_the_offline_arm_makes_no_extra_call(
    monkeypatch,
):
    n = {"calls": 0}

    def gen(client, prompt, registry, nlp, sec, corrections="", fixture="default"):
        n["calls"] += 1
        return [
            {
                "canonical_name": "handler",
                "node_type": "Concept",
                "role": "used",
                "evidence_quote": "The kernel calls the signal handler now",
                "definition": None,
                "source": "llm",
            }
        ]

    monkeypatch.setattr(arms, "_gen", gen)
    sec = {
        **SEC,
        "text": "The kernel calls the signal handler now. A cursor is called a latch here.",
    }
    on, off = arms.run_c_pive(None, BASE, None, NLP, [sec], progress=lambda *_: None)
    assert off[0].calls == 1 and any(
        i["canonical_name"] == "signal handler" for i in off[0].items
    )  # added offline, no re-prompt
    assert on[0].calls >= 2 and any(
        i["canonical_name"] == "signal handler" for i in on[0].items
    )  # added outright online
    assert on[0].hints and all(
        h["kind"] in {"longer_span", "missed_candidate"} for h in on[0].hints
    )  # no M1 (no cards)


def test_c_conexion_example_is_never_the_section_itself_nor_a_test_section_and_is_seeded():
    dev = [{"section_id": f"d{i}", "text": f"t{i}"} for i in range(5)]
    for t in dev:
        ex = arms.pick_example(dev, t)
        assert ex["section_id"] != t["section_id"] and ex["section_id"].startswith("d")
        assert arms.pick_example(dev, t)["section_id"] == ex["section_id"]  # fixed seed


def test_c_conexion_filter_keeps_only_concepts_present_in_the_text():
    text = "The inverted index maps terms to postings lists."
    assert arms.conexion_filter(
        ["inverted index, postings lists; spam filter", "* terms"], text
    ) == ["inverted index", "postings lists", "terms"]


def test_c_conexion_end_to_end_with_a_fake_client():
    class C:
        def parse(self, **kw):
            assert [m["role"] for m in kw["messages"]] == ["user", "assistant", "user"] and kw[
                "allow_escalation"
            ] is False
            return SimpleNamespace(
                output=arms.KeyphrasesLLM(keyphrases=["inverted index", "nonsense"])
            )

    dev = [
        {"section_id": "a", "text": "inverted index here"},
        {"section_id": "b", "text": "an inverted index and more"},
    ]
    res = arms.run_c_conexion(
        C(), dev, {"a": ["inverted index"], "b": ["x"]}, progress=lambda *_: None
    )
    assert [i["canonical_name"] for i in res[0].items] == ["inverted index"]


def test_the_conexion_scorer_reproduces_their_set_intersection_definition():
    p, r, f = arms.conexion_prf(["a", "b", "c", "d"], ["a", "b", "x"])
    assert (round(p, 3), round(r, 3), round(f, 3)) == (0.5, 0.667, 0.571)
    assert arms.conexion_prf([], ["a"]) == (0.0, 0.0, 0.0)
