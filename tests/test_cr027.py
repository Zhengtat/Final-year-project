"""CR-027: backfill is a policy switch for new production runs (no network, no key)."""

from types import SimpleNamespace

import yaml
from test_concepts_v4_runner import (
    BANK,
    BF,
    GEN,
    NLP,
    S1,
    S2,
    BackfillLLM,
    ConceptGeneratorV4LLM,
    ConceptRun,
    LoopConfig,
    embed,
    gen_out,
    mention,
    new,
)

from cumap.concepts_v4 import cr009_run
from cumap.config import REPO_ROOT


def _calls(backfill: bool) -> list[str]:
    s1 = {**S1, "text": "Terms are stored in a dictionary. The index speeds up queries."}
    s2 = {**S2, "text": "A dictionary maps each term to its postings."}
    calls: list[str] = []

    def parse(**kw):
        text = kw["messages"][0]["content"]
        calls.append(kw["task"])
        if kw["task"] == "concept_backfill":
            return SimpleNamespace(
                output=BackfillLLM.model_validate(
                    {
                        "existing_mentions": [
                            mention("n_0002", "dictionary", "Terms are stored in a dictionary")
                        ],
                        "hint_responses": [],
                    }
                )
            )
        tail = text.split("Section text (numbered paragraphs):")[-1]
        if "stored in a dictionary" in tail:
            o = gen_out([new("index", "The index speeds up queries", para="P1")])
        else:
            o = gen_out(
                [new("dictionary", "A dictionary maps each term to its postings", role="defined")]
            )
        return SimpleNamespace(output=ConceptGeneratorV4LLM.model_validate(o))

    ConceptRun(
        SimpleNamespace(parse=parse),
        GEN,
        BANK,
        LoopConfig(form="G1", instructions={}, max_iterations=0),
        nlp=NLP,
        embed_fn=embed,
        lexicon=None,
        domain="databases",
        backfill_prompt=BF,
        rho=0.0,
    ).run([s1, s2], backfill=backfill)
    return calls


def test_switch_off_makes_no_backfill_call_and_on_makes_one():
    assert "concept_backfill" not in _calls(False)
    assert _calls(True).count("concept_backfill") == 1


def test_production_policy_has_backfill_off_and_a_missing_key_keeps_it_on():
    pol = yaml.safe_load((REPO_ROOT / "configs/concept_policy.yaml").read_text())
    assert pol["backfill"] is False and cr009_run._backfill_enabled() is False
    assert cr009_run._backfill_enabled({}) is True  # old policy files keep today's behaviour
    assert cr009_run._backfill_enabled({"backfill": True}) is True


def test_backfill_prompt_is_kept():
    assert (REPO_ROOT / "prompts/concept_backfill/v1.md").exists()
