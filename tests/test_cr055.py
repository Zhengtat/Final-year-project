"""CR-055: concept-recall switches (carry-forward rule, quote repair, M6 hint) and profile v4 (no network, no key)."""

import yaml

from cumap.concepts_v4.loop import LoopConfig, _carry_forward
from cumap.concepts_v4.verifier import VerifyCtx, _find_exact, _m6
from cumap.config import REPO_ROOT


def _item(name):
    return {
        "name": name,
        "aliases": [],
        "node_type": "method",
        "role": "used",
        "evidence": name,
        "para": "P1",
    }


def _out(*names):
    return {
        "existing_mentions": [],
        "not_mentions": [],
        "new_concepts": [_item(n) for n in names],
        "hint_responses": [],
    }


def test_contained_rule_restores_an_item_that_only_shares_a_word():
    clean = {("new_concepts", "grid search"): ("new_concepts", _item("grid search"))}
    new = _out("beam search")
    assert _carry_forward(new, clean, set(), "any_word")[1] == 0
    out, n = _carry_forward(new, clean, set(), "contained")
    assert n == 1 and {c["name"] for c in out["new_concepts"]} == {"beam search", "grid search"}
    assert (
        _carry_forward(_out("grid search algorithm"), clean, set(), "contained")[1] == 0
    )  # a containing span replaced it
    assert LoopConfig().carry_forward_rule == "any_word"  # default unchanged


def test_quote_repair_returns_the_texts_own_substring_and_is_off_by_default():
    t = "tasks such as question answering , natural language inference"
    q = "question answering, natural language inference"
    assert _find_exact(q, t) is None
    assert _find_exact(q, t, repair=True) == "question answering , natural language inference"


def test_m6_hints_uncovered_acronyms_and_listed_terms_only_when_on():
    t = "We train an LSTM with n-gram features and report accuracy ; BERT is a baseline ."
    ctx = VerifyCtx(
        section_text=t,
        paragraphs={"P1": t},
        cards=[],
        lexicon=None,
        nlp=None,
        m6=True,
        m6_terms=("n-gram", "accuracy"),
    )
    assert [h.text for h in _m6(_out("BERT", "accuracy"), ctx)] == ["LSTM", "n-gram"]
    assert VerifyCtx(section_text=t, paragraphs={}, cards=[], lexicon=None, nlp=None).m6 is False


def test_profile_v4_is_v3_plus_prompt_v6_and_the_recall_block():
    p3 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v3.yaml").read_text())
    p4 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v4.yaml").read_text())
    assert p4["generator_prompt"]["version"] == "v6_scinlp" and p4["concept_recall"]["form"] == "G1"
    skip = ("generator_prompt", "status", "concept_recall")
    assert {k: v for k, v in p4.items() if k not in skip} == {
        k: v for k, v in p3.items() if k not in skip
    }
    g2 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v4_g2.yaml").read_text())
    assert g2["concept_recall"] == {**p4["concept_recall"], "form": "G2"}
