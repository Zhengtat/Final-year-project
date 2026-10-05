"""CR-010 STOP 2: candidate hints, the rescue stage, the N2 trigger, the paired bootstrap and the pre-registered
selection rule (no network, no key, no gold)."""

import dataclasses
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import spacy
import yaml

from cumap.concepts_v4.cards import Card, Node
from cumap.concepts_v4.verifier import VerifyCtx
from cumap.cr010 import nodes_exp as E
from cumap.cr010.candidates import recorded_keys, residual_candidates
from cumap.cr010.nodes_report import pick_theta
from cumap.cr010.rescue import (
    RescueLLM,
    decisions_to_output,
    merge_additions,
    run_rescue,
)
from cumap.eval.stats import micro_f1, paired_bootstrap_delta
from cumap.expert_kg.alias_rules import AliasConfig
from cumap.llm.prompts import load_prompt

REPO = Path(__file__).parents[1]
NLP = spacy.load("en_core_web_sm")
CFG = yaml.safe_load((REPO / "configs/cr010_node.yaml").read_text())
ACFG = AliasConfig.load()
TEXT = (
    "Inverted index construction. An inverted index maps each term to its postings list. "
    "The postings list stores document identifiers. A dictionary (DICT) holds the vocabulary. "
    "The dictionary is sorted. A stemmer is called a normalizer in some systems. "
    "The postings list is compressed; the index is stored on disk."
)
FINAL = {
    "existing_mentions": [],
    "not_mentions": [],
    "new_concepts": [
        {
            "name": "inverted index",
            "aliases": [],
            "node_type": "Concept",
            "role": "defined",
            "evidence": "An inverted index maps each term to its postings list",
            "para": "P1",
            "extraction_origin": "independent",
            "anchors": [],
            "independence_check": "x",
            "found_via_anchor": False,
        }
    ],
    "hint_responses": [],
}


def cands(**kw):
    return residual_candidates(TEXT, FINAL, NLP, heading="Index construction", cfg=ACFG, **kw)


def test_candidates_come_from_each_source_and_are_hints_only():
    by = {c.term: c for c in cands()}
    assert "heading" in by["index construction"].sources
    assert "acronym" in by["dict"].sources and "acronym" in by["dictionary"].sources
    assert "definitional" in by["normalizer"].sources
    assert any("noun_chunk" in c.sources for c in by.values())
    assert all(c.count >= 1 for c in by.values())  # every candidate occurs in the text
    assert not any(
        t.split()[0] in {"the", "a", "an"} or t.split()[-1] in {"in", "of"} for t in by
    )  # stops trimmed


def test_recorded_longer_term_does_not_hide_its_one_token_head():
    # exact coverage: 'inverted index' is recorded, 'index' is still a candidate; 'inverted index' itself is not
    by = {c.term: c for c in cands()}
    assert "index" in by and by["index"].one_token
    assert "inverted index" not in by
    assert recorded_keys(FINAL, ACFG)


def test_one_token_hints_can_be_disabled_for_n3():
    assert any(c.one_token for c in cands())
    assert not any(c.one_token for c in cands(include_one_token=False))


def test_chunk_only_candidates_need_the_minimum_count_and_the_cap_applies():
    by = {c.term for c in cands(chunk_min_count=99)}
    assert "postings list" not in by  # only a chunk source, seen 3 times < 99
    assert "index construction" in by  # a structural source needs no count
    assert len(cands(cap=2)) == 2
    assert [c.cid for c in cands(cap=3)] == ["c1", "c2", "c3"]


def test_candidate_ranking_is_deterministic_and_prefers_more_sources():
    a, b = cands(), cands()
    assert [c.term for c in a] == [c.term for c in b]
    assert len(a[0].sources) >= len(a[-1].sources)


# ---------------------------------------------------------------- rescue
def dec(**kw):
    base = {
        "candidate_id": "c1",
        "decision": "add_new",
        "name": "postings list",
        "aliases": [],
        "node_type": "DataUnit",
        "role": "used",
        "evidence": "maps each term to its postings list",
        "para": "P1",
        "node_id": None,
        "surface": None,
        "reason": "r",
    }
    return {**base, **kw}


def card(nid="n1", name="dictionary"):
    return Card(
        Node(
            id=nid, name=name, aliases=[], node_type="Component", first_section="s0", first_order=0
        ),
        True,
    )


def vctx(cards=()):
    return VerifyCtx(
        section_text=TEXT,
        paragraphs={"P1": TEXT},
        cards=list(cards),
        lexicon=None,
        nlp=NLP,
        rho=0.0,
    )


def test_decisions_to_output_drops_incomplete_and_unknown_node():
    out, bad = decisions_to_output(
        [
            dec(),
            dec(candidate_id="c2", evidence=None),
            dec(candidate_id="c3", decision="link_existing", node_id="zzz", surface="dictionary"),
            dec(candidate_id="c4", decision="reject"),
        ],
        [card()],
    )
    assert [c["name"] for c in out["new_concepts"]] == ["postings list"]
    assert (
        out["new_concepts"][0]["anchors"] == []
        and out["new_concepts"][0]["extraction_origin"] == "independent"
    )
    assert bad == 2 and out["existing_mentions"] == []


def test_merge_verifies_quotes_deduplicates_and_prunes():
    extra, _ = decisions_to_output(
        [
            dec(),  # good
            dec(
                candidate_id="c2", name="stemmer", evidence="this quote is not in the text"
            ),  # F2 -> dropped
            dec(
                candidate_id="c3",
                name="inverted index",
                evidence="An inverted index maps each term",
            ),  # dup
            dec(
                candidate_id="c4",
                name="dictionary",
                evidence="A dictionary (DICT) holds the vocabulary",
            ),
        ],
        [],
    )
    merged, f = merge_additions(
        FINAL, extra, vctx(), ACFG, pruner=lambda n: 0.05 if n == "dictionary" else 0.9, tau=0.1
    )
    names = [c["name"] for c in merged["new_concepts"]]
    assert names == ["inverted index", "postings list"]
    assert (
        f["proposed"] == 4
        and f["verified"] == 3
        and f["deduplicated"] == 1
        and f["pruned"] == 1
        and f["kept"] == 1
    )
    assert f["kept_names"] == ["postings list"]
    assert len(FINAL["new_concepts"]) == 1  # the input is never mutated


class FakeClient:
    def __init__(self, decisions):
        self.decisions, self.calls = decisions, []

    def parse(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(output=RescueLLM.model_validate({"decisions": self.decisions}))


def test_run_rescue_uses_the_client_with_static_prompt_first_and_candidates_last():
    prompt = load_prompt(REPO / "prompts", "concept_rescue", "v1")
    cs = cands()[:2]
    fc = FakeClient([dec(candidate_id=cs[0].cid), dec(candidate_id="zz")])
    res = run_rescue(
        fc,
        prompt,
        {"section_id": "s", "heading": "H"},
        {"P1": TEXT},
        [card()],
        FINAL,
        cs,
        domain="ir",
    )
    text = fc.calls[0]["messages"][0]["content"]
    assert fc.calls[0]["task"] == "concept_rescue" and fc.calls[0]["allow_escalation"] is False
    assert text.index("Outcomes:") < text.index("=== THIS SECTION ===") < text.index("CANDIDATES")
    assert text.rstrip().splitlines()[-1].startswith(cs[-1].cid)  # per-item content last
    assert [d["candidate_id"] for d in res.decisions] == [
        cs[0].cid
    ]  # unknown candidate ids are ignored
    assert res.calls == 1 and len(res.out["new_concepts"]) == 1


def test_run_rescue_without_candidates_makes_no_call_and_a_failed_call_adds_nothing():
    prompt = load_prompt(REPO / "prompts", "concept_rescue", "v1")
    fc = FakeClient([])
    assert (
        run_rescue(fc, prompt, {"section_id": "s"}, {}, [], FINAL, [], domain="ir").calls == 0
        and not fc.calls
    )

    class Boom:
        def parse(self, **kw):
            raise ValueError("bad")

    r = run_rescue(
        Boom(), prompt, {"section_id": "s"}, {"P1": TEXT}, [], FINAL, cands()[:1], domain="ir"
    )
    assert r.error and not r.out["new_concepts"]


# ---------------------------------------------------------------- N2 trigger and variant
def test_trigger_counts_items_per_100_words():
    text = " ".join(["w"] * 200)
    fin = {"new_concepts": [1, 2, 3], "existing_mentions": [4]}  # 4 items / 200 words = 2.0 per 100
    assert (
        E.triggered(fin, text, 2.5)
        and not E.triggered(fin, text, 2.0)
        and E.triggered(fin, text, None)
    )


def test_n2_prompt_variant_changes_only_the_cache_label():
    base = load_prompt(REPO / "prompts", "concept_generator", "v4")
    v = dataclasses.replace(base, version=f"{base.version}-{CFG['n2']['sample_label']}")
    assert v.body == base.body and v.version != base.version


def test_pick_theta_takes_the_smallest_value_within_the_tie_band_and_ignores_all():
    rows = {
        t: {"exact": {"f1": f}}
        for t, f in {"1.0": 0.50, "1.5": 0.51, "2.0": 0.52, "all": 0.60}.items()
    }
    assert (
        pick_theta(rows, CFG) == 1.0
    )  # 0.52 - 0.50 = 0.02 is inside the tie band; 'all' is never selected


# ---------------------------------------------------------------- bootstrap
def counts(tp, fp, fn, n=12):
    return {f"s{i}": (tp, fp, fn) for i in range(n)}


def test_paired_bootstrap_is_zero_for_identical_systems_and_positive_for_a_clear_gain():
    r0 = paired_bootstrap_delta(counts(5, 5, 5), counts(5, 5, 5), n=500, seed=1)
    assert r0["delta"] == 0 and r0["lo95"] <= 0 <= r0["hi95"]
    r1 = paired_bootstrap_delta(counts(5, 5, 5), counts(8, 5, 2), n=500, seed=1)
    assert r1["delta"] > 0 and r1["lo95"] > 0
    assert paired_bootstrap_delta(counts(5, 5, 5), counts(8, 5, 2), n=500, seed=1) == r1  # seeded


def test_paired_bootstrap_needs_the_same_sections_and_micro_f1_matches_the_definition():
    with pytest.raises(ValueError):
        paired_bootstrap_delta({"a": (1, 1, 1)}, {"b": (1, 1, 1)})
    assert micro_f1([(2, 1, 1), (2, 1, 1)]) == pytest.approx(2 * 4 / (2 * 4 + 2 + 2))
    assert np.isclose(micro_f1([]), 0.0)


# ---------------------------------------------------------------- the pre-registered selection rule
def row(f1, base=0.50, lo=-0.05, prec_drop=0.0):
    return {"delta": f1 - base, "lo95": lo, "precision_drop": prec_drop, "f1": f1}


def test_no_arm_qualifying_means_no_change():
    assert E.select_node_arm({"N1": row(0.51), "N2": row(0.505)}, CFG)[0] == "N0"


def test_gain_threshold_or_positive_bootstrap_bound_qualifies_but_precision_drop_vetoes():
    assert E.select_node_arm({"N1": row(0.53)}, CFG)[0] == "N1"  # +0.03
    assert E.select_node_arm({"N1": row(0.51, lo=0.001)}, CFG)[0] == "N1"  # bound > 0
    assert (
        E.select_node_arm({"N1": row(0.55, prec_drop=0.03)}, CFG)[0] == "N0"
    )  # precision drop > 0.02


def test_simpler_arm_wins_inside_the_tie_band_and_better_arm_wins_outside_it():
    assert (
        E.select_node_arm({"N1": row(0.54), "N2": row(0.55)}, CFG)[0] == "N1"
    )  # within 0.02: N1 is simpler
    assert (
        E.select_node_arm({"N1": row(0.53), "N2": row(0.56)}, CFG)[0] == "N2"
    )  # 0.03 apart: the better one


def test_cr010_code_never_touches_gold_or_the_network():
    for f in (REPO / "src/cumap/cr010").glob("*.py"):
        src = f.read_text()
        assert "data/gold" not in src and "openai" not in src.lower()
