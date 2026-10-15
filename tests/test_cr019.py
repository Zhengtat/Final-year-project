"""CR-019: occurrence index and grounding-consistent evaluation variants (no network, no key)."""

import copy
import json
from pathlib import Path

import pytest

from cumap.cr012.adapters import SciNLPDoc, detokenise
from cumap.cr012.types import PredEdge, PredNode
from cumap.cr019 import stage_b as SB
from cumap.cr019 import variants as V
from cumap.cr019.occurrences import AMBIGUOUS, UNIQUE, WINDOW, build_index, spans_by_node


def concept(cid, name, quotes, unit="u", aliases=()):
    return {
        "concept_id": cid, "canonical_name": name, "aliases": list(aliases), "node_type": "Concept",
        "mentions": [{"section_id": unit, "quote": q} for q in quotes],
    }  # fmt: skip


def test_index_uses_longest_match_and_marks_positions():
    text = "The bit rate is high.\n\nA bit is small. The bit rate drops."
    cs = [
        concept("c_bit", "bit", ["A bit is small"]),
        concept("c_rate", "bit rate", ["The bit rate is high"]),
    ]
    sents = [(0, 21), (23, 38), (39, 57)]
    occ, stats = build_index(cs, text, "u", sents)
    got = [(o.concept_id, text[o.start : o.end], o.paragraph, o.sentence) for o in occ]
    assert got == [
        ("c_rate", "bit rate", 0, 0),
        ("c_bit", "bit", 1, 1),
        ("c_rate", "bit rate", 1, 2),
    ]
    assert all(o.assignment == UNIQUE for o in occ) and stats["unique"] == 3


def test_shared_surface_is_owned_by_the_node_whose_evidence_window_contains_it_else_ambiguous():
    text = "Link bandwidth is 10 Mbps. Radio bandwidth is 20 MHz. Bandwidth matters."
    cs = [
        concept("c_link_bw", "bandwidth", ["Link bandwidth is 10 Mbps"]),
        concept("c_radio_bw", "bandwidth", ["Radio bandwidth is 20 MHz"]),
    ]
    occ, stats = build_index(cs, text, "u", [(0, 26), (27, 53), (54, 72)])
    assert [(o.concept_id, o.assignment) for o in occ] == [
        ("c_link_bw", WINDOW),
        ("c_radio_bw", WINDOW),
        (None, AMBIGUOUS),
    ]
    assert stats["ambiguous"] == 1


def test_index_never_writes_mentions_or_aliases():
    cs = [concept("c_a", "frame", ["a frame"]), concept("c_b", "header", ["the header"])]
    before = copy.deepcopy(cs)
    build_index(cs, "a frame and the header and a frame", "u", [(0, 34)])
    assert cs == before


def test_only_nodes_with_a_recorded_mention_in_the_unit_are_indexed():
    cs = [concept("c_a", "frame", ["a frame"]), concept("c_b", "header", ["x"], unit="other")]
    occ, _ = build_index(cs, "a frame and the header", "u", [(0, 22)])
    assert set(spans_by_node(occ)) == {"c_a"}


def test_quote_is_located_at_the_occurrence_that_contains_both_endpoints():
    text = "A uses B. C. A uses B."
    assert V._locate_quote(text, "A uses B", [(13, 14)], [(20, 21)]) == (13, 21)
    assert V._locate_quote(text, "A uses B", [(99, 100)], [(20, 21)]) == (
        0,
        8,
    )  # first occurrence when none contains both
    assert V._locate_quote(text, "missing", [], []) is None


def _doc(sentences):
    text, offs, ends = detokenise(sentences)
    toks = [t for s in sentences for t in s]
    return SciNLPDoc("d", toks, ends, text, offs, len(toks))


def test_p3_places_the_nearest_pair_in_every_cooccurring_sentence_and_counts_unplaced():
    doc = _doc([["A", "x", "B", "y", "A"], ["B", "z", "A"], ["C"]])
    nodes = [PredNode("a", "d", "method", "A", ((0, 1), (4, 5), (7, 8))), PredNode("b", "d", "method", "B", ((2, 3), (5, 6))), PredNode("c", "d", "method", "C", ((8, 9),))]  # fmt: skip
    rels, unplaced = V.project_p3(
        doc,
        nodes,
        [PredEdge("d", "a", "b", "UsedFor", None), PredEdge("d", "a", "c", "UsedFor", None)],
    )
    assert sorted((r[0], r[1]) for r in rels) == [
        ((0, 1), (2, 3)),
        ((7, 8), (5, 6)),
    ]  # sentence 0: nearest of A@0/A@4 to B@2 is a tie -> first; sentence 1
    assert unplaced == 1


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/cr019/stage_a.json"


@pytest.mark.skipif(not REPORT.exists(), reason="Stage A report not generated in this checkout")
def test_stage_a_reproduces_frozen_numbers_accounts_for_every_edge_and_leaves_sources_unchanged():
    r = json.loads(REPORT.read_text())
    sa = r["stage_a"]["scinlp"]
    assert r["sources_unchanged"] is True
    assert all(sa["frozen_check"].values())
    assert all(
        all(v.values())
        for t, v in ((t, r["stage_a"]["pd"][t]["frozen_check"]) for t in ("heldout", "pilot"))
    )
    for v in V.SC_VARIANTS:
        e = sa[v]["edges"]
        assert e["placed"] + e["unplaced"] == e["predicted"]
    assert sa["FROZEN"]["edges"]["unplaced_counted_as_fp"] is False
    assert all(sa[v]["edges"]["unplaced_counted_as_fp"] for v in V.SC_VARIANTS if v != "FROZEN")


# ---------------------------------------------------------------- Stage B (multi-sentence evidence)


def test_passage_puts_the_original_sentence_first_then_others_in_text_order_capped_at_k():
    sents = ["A then B.", "Only A.", "B and A again.", "A, B once more.", "B with A last."]
    cids = [{"a", "b"}, {"a"}, {"a", "b"}, {"a", "b"}, {"a", "b"}]
    pair = {"concept_x_id": "a", "concept_y_id": "b", "sentence": "B and A again."}
    text, n = SB.passage(sents, cids, pair, k=3)
    assert text.split("\n") == ["B and A again.", "A then B.", "A, B once more."] and n == 3


def test_passage_keeps_a_sentence_span_evidence_as_the_first_line():
    sents = ["A here.", "B there.", "A and B."]
    pair = {"concept_x_id": "a", "concept_y_id": "b", "sentence": "A here. B there."}
    text, n = SB.passage(sents, [{"a"}, {"b"}, {"a", "b"}], pair, k=3)
    assert text.split("\n") == ["A here. B there.", "A and B."] and n == 2


def test_new_prompt_versions_exist_and_keep_the_render_slots():
    from cumap.llm.prompts import load_prompt

    for task, v in zip(
        ("relation_family", "relation_choice", "relation_qualifiers"),
        SB.MULTI_VERSIONS,
        strict=True,
    ):
        p = load_prompt(Path("prompts"), task, v)
        assert p.version == v and "{sentence}" in p.body


def test_relations_stage_defaults_are_the_production_versions():
    import inspect

    from cumap.expert_kg.slice_rerun import relations_stage

    sig = inspect.signature(relations_stage)
    assert sig.parameters["prompt_versions"].default == ("v3", "v4", "v4")
    assert sig.parameters["evidence_fn"].default is None and sig.parameters["limit"].default is None


# ---------------------------------------------------------------- R1-key matching (spelling variants)
from cumap.cr019.occurrences import R1KeyMatcher
from cumap.expert_kg.alias_rules import AliasConfig


def test_r1_key_matcher_finds_hyphen_space_and_concatenated_variants_with_guards():
    m = R1KeyMatcher(
        {"prefix-tuning": "p", "IT": "it", "adapter": "a", "LMs": "lm", "LM": "lm"},
        AliasConfig.load(),
    )
    t = "We propose prefixtuning. Prefix tuning and Prefix-Tuning beat it; the adapter, adapter-tuning; an LM and LMs."
    got = [(x.surface, x.concept_id) for x in m.find(t)]
    assert got == [
        ("prefixtuning", "p"),
        ("Prefix tuning", "p"),
        ("Prefix-Tuning", "p"),
        ("adapter", "a"),
        ("LM", "lm"),
        ("LMs", "lm"),
    ]


def test_index_r1key_mode_matches_variants_but_token_mode_is_unchanged():
    cs = [concept("c_p", "prefix-tuning", ["we propose prefix-tuning"])]
    text = "we propose prefix-tuning. Later prefixtuning wins."
    tok, _ = build_index(cs, text, "u", [(0, 25), (26, 50)])
    r1, _ = build_index(cs, text, "u", [(0, 25), (26, 50)], matching="r1key")
    assert [text[o.start : o.end] for o in tok] == ["prefix-tuning"]
    assert [text[o.start : o.end] for o in r1] == ["prefix-tuning", "prefixtuning"]
