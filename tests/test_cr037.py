"""CR-037 DRAFT: the U5 identity judge. Mock fixtures only; nothing here has been run against a real model (no network, no key)."""

import re
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError
from test_concepts_v4_runner import (
    BANK,
    BF,
    GEN,
    NLP,
    ConceptGeneratorV4LLM,
    ConceptRun,
    LoopConfig,
    gen_out,
    mention,
    new,
)
from test_cr035 import StubEmbed, cand, lex

from cumap.concepts_v4 import cr009_run, pd_run
from cumap.expert_kg import identity_judge as IJ
from cumap.expert_kg.canonicalize import ConceptRegistry, canonicalize_mention
from cumap.llm.client import LLMClient

SENT = {
    "same": "A dictionary, also called a lookup table, is stored on disk.",
    "narrower": "A hash table is a dictionary that uses hashing.",
    "broader": "Every vehicle needs fuel or a battery.",
    "new": "The driver steers the vehicle.",
    "not_a_concept": "The thing was parked outside.",
}


def judge(tmp_settings, fixtures_dir, fixture, sentence):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    return IJ.judge_pair(
        client, IJ.load_judge_prompt(), domain="databases", surface="lookup table", target_name="dictionary", target_aliases=[],
        target_type="Component", target_gloss="A dictionary maps terms to postings", sentence=sentence, fixture_name=fixture,
    )  # fmt: skip


# ---------------------------------------------------------------- schema and prompt
def test_schema_is_a_closed_choice_built_from_the_config_with_every_field_required():
    opts = IJ.judge_options()
    assert opts == ("same", "narrower", "broader", "new", "not_a_concept")
    schema = IJ.build_identity_judge_schema()
    ok = {"decision": "same", "evidence_quote": "q", "reason": "r", "confidence": 0.9}
    assert schema.model_validate(ok).decision == "same"
    for bad in (
        {**ok, "decision": "maybe"},
        {**ok, "extra": 1},
        {k: v for k, v in ok.items() if k != "reason"},
    ):
        with pytest.raises(ValidationError):
            schema.model_validate(bad)
    assert all(
        f.is_required() for f in schema.model_fields.values()
    )  # no defaults (CLAUDE.md OpenAI usage)
    assert IJ.build_identity_judge_schema(("same", "new")).model_fields[
        "decision"
    ].annotation.__args__ == ("same", "new")


def test_prompt_is_a_draft_with_static_content_first_and_per_item_content_last():
    p = IJ.load_judge_prompt()
    assert (p.task, p.version, p.schema) == (
        "identity_judge",
        "v1",
        "IdentityJudgeLLM",
    ) and "DRAFT" in p.notes
    body = p.body
    for word in IJ.judge_options():
        assert word in body
    assert set(re.findall(r"\{(\w+)\}", body)) == {
        "domain",
        "surface",
        "target_name",
        "target_aliases",
        "target_type",
        "target_gloss",
        "evidence",
    }
    first_placeholder = min(
        body.index("{" + k + "}") for k in ("domain", "surface", "target_name", "evidence")
    )
    assert (
        body.index("Rules:") < body.index("Examples") < first_placeholder
    )  # instructions and examples first, the case last
    assert body.rstrip().endswith("{evidence}")
    assert "trades_off_with" not in body
    rendered = p.render(
        domain="d",
        surface="s",
        target_name="t",
        target_aliases="none",
        target_type="Component",
        target_gloss="g",
        evidence="e",
    )
    assert "TERM: s" in rendered and "{" not in rendered


def test_the_draft_prompt_file_is_new_and_the_adjudicator_prompts_are_untouched():
    from pathlib import Path

    assert Path("prompts/identity_judge/v1.md").exists()
    assert (
        Path("prompts/rejected_link_adjudicator/v2.md").exists()
        and Path("prompts/canonicalize/v2.md").exists()
    )


# ---------------------------------------------------------------- the call (mock backend fixtures)
@pytest.mark.parametrize("name", ["same", "narrower", "broader", "new", "not_a_concept"])
def test_each_of_the_five_answers_is_returned_with_its_verified_quote(
    tmp_settings, fixtures_dir, name
):
    r = judge(tmp_settings, fixtures_dir, name, SENT[name])
    assert r.decision == name == r.raw_decision and r.input_hash


def test_a_quote_that_is_not_in_the_sentence_makes_the_answer_no_decision(
    tmp_settings, fixtures_dir
):
    r = judge(tmp_settings, fixtures_dir, "badquote", SENT["same"])
    assert r.decision == "no_decision" and r.raw_decision == "same"


# ---------------------------------------------------------------- input A wiring
S1 = {
    "section_id": "s1",
    "chapter_num": 1,
    "order_index": 0,
    "text": "A dictionary maps each term to its postings.",
}
S2 = {
    "section_id": "s2",
    "chapter_num": 1,
    "order_index": 1,
    "text": "A dictionary, or lookup table, is stored on disk.",
}


def run_a(answer, judge_mode="v1", resolver="u1", policy="off"):
    calls = []
    schema = IJ.build_identity_judge_schema()

    def parse(**kw):
        calls.append(kw["task"])
        if kw["task"] == "identity_judge":
            q = "A dictionary, or lookup table, is stored on disk"
            return SimpleNamespace(
                output=schema.model_validate(
                    {"decision": answer, "evidence_quote": q, "reason": "r", "confidence": 0.7}
                ),
                input_hash="h",
            )
        if kw["task"] == "concept_generator":
            tail = kw["messages"][0]["content"].split("Section text (numbered paragraphs):")[-1]
            o = gen_out(mentions=[mention("n_0001", "lookup table", "A dictionary, or lookup table, is stored on disk")]) if "lookup table" in tail else gen_out([new("dictionary", "A dictionary maps each term to its postings", role="defined")])  # fmt: skip
            return SimpleNamespace(output=ConceptGeneratorV4LLM.model_validate(o))
        raise AssertionError(f"unexpected task {kw['task']}")

    out = ConceptRun(
        SimpleNamespace(parse=parse), GEN, BANK, LoopConfig(form="G1", instructions={}, max_iterations=0), nlp=NLP, embed_fn=lambda t: np.zeros(4),
        lexicon=None, domain="databases", backfill_prompt=BF, rho=0.0, strict_g_links=True, rejected_link_policy=policy,
        identity_resolver=resolver, identity_judge=judge_mode,
    ).run([S1, S2], backfill=False)  # fmt: skip
    return out, calls


def test_judge_same_links_the_mention_and_adds_the_alias():
    out, calls = run_a("same")
    assert (
        "lookup table" in out.store.nodes["n_0001"].aliases and calls.count("identity_judge") == 1
    )
    j = [m for m in out.merges if m["rule_id"] == "G-link-judged"]
    assert [m["decision"] for m in j] == ["same"] and j[0]["input_hash"] == "h"


@pytest.mark.parametrize("answer", ["narrower", "broader", "new"])
def test_judge_narrower_broader_new_give_a_new_node(answer):
    out, _ = run_a(answer)
    assert "lookup table" not in out.store.nodes["n_0001"].aliases
    assert any(n.name == "lookup table" for n in out.store.nodes.values())
    assert [m["decision"] for m in out.merges if m["rule_id"] == "G-link-judged"] == [answer]


def test_judge_not_a_concept_drops_the_link_on_input_a():
    out, _ = run_a("not_a_concept")
    assert (
        not any(n.name == "lookup table" for n in out.store.nodes.values())
        and "lookup table" not in out.store.nodes["n_0001"].aliases
    )


def test_judge_off_keeps_the_adjudicator_path_and_makes_no_judge_call():
    out, calls = run_a("same", judge_mode="off")
    assert "identity_judge" not in calls and [m["rule_id"] for m in out.merges] == [
        "G-link-rejected"
    ]
    _out2, calls2 = run_a("same", resolver="legacy")  # the judge needs the u1 resolver
    assert "identity_judge" not in calls2


# ---------------------------------------------------------------- input B wiring
def b_client(answers):
    seq = iter(answers)
    schema = IJ.build_identity_judge_schema()
    calls = []

    def parse(**kw):
        calls.append(kw["messages"][0]["content"])
        a = next(seq)
        return SimpleNamespace(
            output=schema.model_validate(
                {
                    "decision": a,
                    "evidence_quote": "A gateway links two networks",
                    "reason": "r",
                    "confidence": 0.7,
                }
            ),
            input_hash="h",
        )

    return SimpleNamespace(parse=parse, backend_call_count=0), calls


def b_registry():
    reg = ConceptRegistry(StubEmbed())
    reg.add_new(cand("router", "A router forwards packets"))
    reg.add_new(cand("hub", "A hub repeats bits"))
    return reg


def judge_b(answers, name="gateway", quote="A gateway links two networks", review_below=0.7, **kw):
    client, calls = b_client(answers)
    reg = b_registry()
    o = canonicalize_mention(client, None, reg, cand(name, quote), type_aware=True, review_below=review_below, identity_resolver="u1", judge_prompt=IJ.load_judge_prompt(), **kw)  # fmt: skip
    return o, calls, reg


def test_b_same_merges_with_rule_u5_and_the_judge_prompt_carries_the_term_last():
    o, calls, reg = judge_b(["same"], review_below=None, similarity_threshold=0.0)
    assert (o.decision, o.rule_id, o.llm_called) == ("same", "U5", True) and len(reg) == 2
    assert (
        calls[0].rstrip().endswith("A gateway links two networks") and "TERM: gateway" in calls[0]
    )


def test_b_narrower_and_broader_make_a_new_node_with_a_taxonomy_outcome():
    for a in ("narrower", "broader"):
        o, _, reg = judge_b([a], similarity_threshold=0.0)
        assert o.decision == a and o.matched_concept_id and len(reg) == 3


def test_b_new_goes_on_to_the_next_candidate_then_ends_as_a_new_concept():
    o, calls, reg = judge_b(["new", "new"], similarity_threshold=0.0)
    assert o.decision == "different" and len(calls) == 2 and len(reg) == 3


def test_b_not_a_concept_is_only_a_flag_and_the_node_is_kept():
    o, _, reg = judge_b(["not_a_concept"], similarity_threshold=0.0)
    assert o.decision == "different" and "review flag" in o.reason and len(reg) == 3


def test_b_a_same_below_the_review_band_goes_to_review_not_a_merge():
    o, _, reg = judge_b(
        ["same"], similarity_threshold=-1.0
    )  # StubEmbed gives similarity near 0 for an unrelated name: below the 0.70 band
    assert o.decision == "review" and o.review and len(reg) == 3


def test_b_candidates_below_the_offer_threshold_are_never_judged():
    o, calls, reg = judge_b(
        [], name="switch", quote="A switch forwards frames", similarity_threshold=0.6
    )
    assert calls == [] and o.decision == "different" and len(reg) == 3


# ---------------------------------------------------------------- switches
def test_switch_defaults_are_off_and_the_judge_needs_the_u1_resolver(tmp_path):
    assert (
        IJ.resolve_judge_mode() == "off"
        and IJ.resolve_judge_mode("v1") == "v1"
        and IJ.resolve_judge_mode(False) == "off"
    )
    with pytest.raises(ValueError):
        IJ.resolve_judge_mode("v2")
    assert cr009_run._identity_resolver() == "legacy"
    store = SimpleNamespace(nodes={})
    out = SimpleNamespace(store=store, merges=[])
    with pytest.raises(ValueError, match="needs identity_resolver u1"):
        pd_run.canonicalise(
            out,
            [],
            lex(tmp_path),
            None,
            None,
            StubEmbed(),
            None,
            identity_resolver="legacy",
            identity_judge="v1",
        )
