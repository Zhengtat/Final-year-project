"""CR-014 Stage A: proposal registry invariants (no network, no gold)."""

import pytest

from cumap.cr014.proposal import add, definitional_hits, norm_surface, u1_registry
from cumap.cr014.stage_a import contains, overlap_match
from cumap.expert_kg.alias_rules import AliasConfig


@pytest.fixture(scope="module")
def nlp():
    spacy = pytest.importorskip("spacy")
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("en_core_web_sm not installed")


def test_same_span_from_two_sources_is_one_candidate_with_union_provenance():
    reg: dict = {}
    add(reg, "s", "Sliding Window", "a", "the sliding window protocol")
    add(reg, "s", "sliding  window", "b", "the sliding window protocol")
    assert list(reg) == ["sliding window"]
    assert reg["sliding window"].proposal_sources == {"a", "b"}
    assert reg["sliding window"].start_offset == 4


def test_u1_is_noisy_but_keeps_subspans_and_hyphenated_terms(nlp):
    sec = {
        "section_id": "s",
        "text": "A database-style searching system uses an inverted index.",
        "heading": "",
    }
    keys = set(u1_registry(sec, set(), nlp, AliasConfig.load()))
    assert {"inverted index", "index", "database-style searching"} <= keys
    assert all(len(k.split()) <= 4 for k in keys)


def test_overlap_requires_containment_and_ignores_stopword_singletons():
    assert contains(["inverted", "index"], ["index"])
    assert overlap_match({"index"}, {"inverted index"}, set())
    assert not overlap_match({"the"}, {"the index"}, {"the"})


def test_definitional_hits_are_normalised(nlp):
    assert all(h == norm_surface(h) for h in definitional_hits("A router is called a gateway."))


def test_union_families_cover_every_candidate_and_never_reject(nlp):
    from cumap.cr014.union import build_section_union

    sec = {
        "section_id": "s",
        "text": "An inverted index maps terms to documents. The inverted index is built once.",
        "heading": "",
    }
    u = build_section_union(
        sec, set(), nlp, AliasConfig.load(), ["inverted index", "not in the text"]
    )
    in_fam = {m for f in u.families for m in f.members}
    assert in_fam == {c.cid for c in u.cands.values()}  # every candidate sits in a family
    assert "not in the text" not in u.cands  # an unevidenced proposal can never be verified
    assert "llm_iter0" in u.cands["inverted index"].sources and u.cands["inverted index"].count == 2
    assert all(
        sec["text"][c.start_offset : c.end_offset].lower() == c.surface for c in u.cands.values()
    )


def test_verifier_and_boundary_calls_use_the_mock_backend_and_validate_schema(nlp, monkeypatch):
    from pathlib import Path

    from cumap.config import get_settings
    from cumap.cr014.llm_stage import Usage, run_boundary, run_verifier
    from cumap.cr014.stage_b import SB
    from cumap.cr014.union import build_section_union
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    monkeypatch.setenv("CUMAP_LLM_BACKEND", "mock")
    client = LLMClient(get_settings(), run_id="t")
    sec = {"section_id": "s", "text": "An inverted index maps terms to documents.", "heading": ""}
    u = build_section_union(sec, set(), nlp, AliasConfig.load(), [])
    pv = load_prompt(Path("prompts"), "cr014_concept_verifier", "v1")
    pb = load_prompt(Path("prompts"), "cr014_boundary_repair", "v1")
    usage = Usage()
    cs = sorted(u.cands.values(), key=lambda c: c.cid)
    v = run_verifier(client, pv, u, "h", cs, SB, {}, "d", usage)
    b = run_boundary(client, pb, u, "h", u.families[:2], {c.cid: c for c in cs}, SB, "d", usage)
    assert usage.calls == 2 and not usage.errors
    assert set(v) <= {c.cid for c in cs} and set(b) <= {f.fid for f in u.families}


def test_pilot_score_span_exact_and_boundary_categories(tmp_path):
    from cumap.cr014.pilot_score import classify_boundary, load_gold, place, score

    sents = tmp_path / "s.csv"
    sents.write_text(
        "sentence_id,section_id,char_start,char_end,sentence_text\n"
        "s1,sec,0,40,A router forwards packets to a switch.\n",
        encoding="utf-8",
    )
    sheet = tmp_path / "g.csv"
    sheet.write_text(
        "row_type,sentence_id,span_text,occurrence,concept_id,canonical_name,node_type,aliases,nested_valid,boundary_notes\n"
        "MENTION,s1,router,1,C1,,,,,\nMENTION,s1,packets,1,C2,,,,,\nMENTION,s1,switch,1,C3,,,,,\n",
        encoding="utf-8",
    )
    gold = load_gold(sheet, sents)
    text = "A router forwards packets to a switch."
    assert [(text[m.start : m.end]) for m in gold] == ["router", "packets", "switch"]
    r = score({"sec": place(["router", "packets"], text)}, gold, {"sec": text})
    assert (
        r["mention_span_exact"]["tp"],
        r["mention_span_exact"]["fp"],
        r["mention_span_exact"]["fn"],
    ) == (2, 0, 1)
    r2 = score(
        {"sec": place(["A router", "packets"], text)}, gold, {"sec": text}
    )  # "A router" is over-specific
    assert r2["false_positive_boundary_categories"] == {"over_specific_contains_gold": 1}
    assert classify_boundary((2, 8), [(2, 8)]) == "over_specific_contains_gold"
    assert classify_boundary((0, 8), [(2, 8)]) == "over_specific_contains_gold"
    assert classify_boundary((3, 5), [(2, 8)]) == "over_general_inside_gold"
    assert classify_boundary((20, 25), [(2, 8)]) == "no_overlap"
