"""CR-021: promote a rejected G-link that names a MORE SPECIFIC term (no network, no key)."""

from pathlib import Path
from types import SimpleNamespace

import yaml

from cumap.concepts_v4.cards import Node, NodeStore
from cumap.concepts_v4.runner import ConceptRun, RunOutput, more_specific
from cumap.expert_kg.alias_rules import AliasConfig


def node(i, name, aliases=(), typ="method"):
    return Node(i, name, list(aliases), typ, "s", 0)


def test_more_specific_accepts_extended_terms_only():
    assert more_specific("adapter-tuning", node("n1", "adapter"))
    assert more_specific("File Transfer Protocol", node("n1", "protocol"))
    assert more_specific("deep neural network", node("n1", "neural network"))
    assert not more_specific("summarization", node("n1", "text summarization"))  # shortened
    assert not more_specific("hosts", node("n1", "node"))  # different word
    assert not more_specific(
        "Approximate k-Nearest Neighbor ( AKNN ) search",
        node("n1", "Approximate k-Nearest Neighbor search"),
    )
    assert not more_specific("adapters", node("n1", "adapter"))  # plural is the same term


def _run(store):
    stub = SimpleNamespace(alias_cfg=AliasConfig.load())
    out = RunOutput(store)
    meta = {"new_nodes": [], "mentions": []}
    return stub, out, meta


def test_promotion_creates_a_typed_node_with_the_generators_mention_and_logs_the_rule():
    store = NodeStore()
    target = store.add(node(store.new_id(), "adapter"))
    stub, out, meta = _run(store)
    m = {
        "surface": "adapter-tuning",
        "role": "used",
        "para": "P1",
        "evidence": "and adapter-tuning ( ADAPTER )",
    }
    ConceptRun._promote(stub, out, meta, "u", 3, m, target)
    new = store.nodes[meta["new_nodes"][0]]
    assert (new.name, new.node_type, new.added_via_hint) == (
        "adapter-tuning",
        "method",
        "promoted_rejected_link",
    )
    assert (
        new.mentions[0]["evidence"] == m["evidence"] and new.mentions[0]["linked_by"] == "generator"
    )
    assert (
        out.merges[-1]["rule_id"] == "G-link-rejected-promoted"
        and out.merges[-1]["rejected_target"] == target.id
    )
    assert target.mentions == [] and target.aliases == []  # the rejected target is never touched


def test_a_second_rejection_of_the_same_term_reroutes_to_the_promoted_node():
    store = NodeStore()
    target = store.add(node(store.new_id(), "adapter"))
    stub, out, meta = _run(store)
    m = {"surface": "adapter-tuning", "role": "used", "para": "P1", "evidence": "e1"}
    ConceptRun._promote(stub, out, meta, "u", 3, m, target)
    ConceptRun._promote(
        stub, out, meta, "u", 4, {**m, "surface": "Adapter tuning", "evidence": "e2"}, target
    )
    assert len(store.nodes) == 2 and out.merges[-1]["rule_id"] == "G-link-rejected-rerouted"
    assert [x["evidence"] for x in store.nodes[meta["new_nodes"][0]].mentions] == ["e1", "e2"]


def test_production_switch_is_off_until_adopted():
    assert (
        yaml.safe_load(Path("configs/concept_policy.yaml").read_text())["promote_rejected_links"]
        is False
    )


# ---------------------------------------------------------------- option 1: measured adjudicator
def test_adjudicator_split_is_stratified_and_deterministic():
    from collections import Counter

    from cumap.cr021 import adjudicator as A

    if not A.GOLD.exists():
        import pytest

        pytest.skip("owner marks not in this checkout")
    a, b = A.load_rows(), A.load_rows()
    assert [r["split"] for r in a] == [r["split"] for r in b]
    splits_of = {}
    for r in a:
        splits_of.setdefault(r["key"], set()).add(r["split"])
    assert all(
        len(v) == 1 for v in splits_of.values()
    )  # an item listed twice never straddles the split
    c = Counter((r["split"], r["gold"]) for r in a)
    assert all(
        abs(c[("dev", g)] - c[("heldout", g)]) <= 3 for g in A.LABELS
    )  # stratified; the one duplicate move is documented


def test_adjudicator_rejects_a_quote_not_in_the_sentence(monkeypatch):
    from cumap.config import get_settings
    from cumap.cr021 import adjudicator as A
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    monkeypatch.setenv("CUMAP_LLM_BACKEND", "mock")
    get_settings.cache_clear()
    client = LLMClient(get_settings(), run_id="test_cr021")
    prompt = load_prompt(Path("prompts"), "rejected_link_adjudicator", "v1")
    row = {"key": "k", "split": "dev", "dataset": "scinlp_test", "run_id": "none", "section_id": "none", "surface": "adapter-tuning",
           "rejected_target": "adapter", "target_type": "method", "evidence": "we compare with adapter-tuning here"}  # fmt: skip
    monkeypatch.setattr(A, "render_inputs", lambda r: {"domain": "nlp", "surface": r["surface"], "target_name": "adapter", "target_aliases": "none",
                                                       "target_type": "method", "target_gloss": "none", "evidence": r["evidence"]})  # fmt: skip
    assert A.adjudicate(client, prompt, row)["decision"] == "new_concept"
    row["evidence"] = "no such words"
    out = A.adjudicate(client, prompt, row)
    assert out["decision"] == "no_decision" and out["raw_decision"] == "new_concept"
    get_settings.cache_clear()


def test_production_policy_is_adjudicate_with_the_adopted_prompt():
    from cumap.concepts_v4.rejected_links import ADOPTED_VERSION

    pol = yaml.safe_load(Path("configs/concept_policy.yaml").read_text())
    assert pol["rejected_link_policy"] == "adjudicate" and pol["promote_rejected_links"] is False
    assert Path(f"prompts/rejected_link_adjudicator/{ADOPTED_VERSION}.md").exists()


def test_adjudicated_new_concept_is_promoted_and_logged(monkeypatch):
    from cumap.config import get_settings
    from cumap.llm.client import LLMClient

    monkeypatch.setenv("CUMAP_LLM_BACKEND", "mock")
    get_settings.cache_clear()
    store = NodeStore()
    target = store.add(node(store.new_id(), "adapter"))
    stub = SimpleNamespace(
        alias_cfg=AliasConfig.load(),
        client=LLMClient(get_settings(), run_id="test_cr021"),
        domain="nlp",
    )
    stub._promote = lambda *a: ConceptRun._promote(stub, *a)
    out, meta = RunOutput(store), {"new_nodes": [], "mentions": []}
    m = {
        "surface": "adapter-tuning",
        "role": "used",
        "para": "P1",
        "evidence": "we compare with adapter-tuning here",
    }
    ConceptRun._adjudicate(
        stub, out, meta, "u", 2, m, target, {"P1": "We compare with adapter-tuning here."}
    )
    assert [x["rule_id"] for x in out.merges] == ["G-link-adjudicated", "G-link-rejected-promoted"]
    assert (
        out.merges[0]["decision"] == "new_concept"
        and store.nodes[meta["new_nodes"][0]].name == "adapter-tuning"
    )
    get_settings.cache_clear()
