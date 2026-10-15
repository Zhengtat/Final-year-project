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
