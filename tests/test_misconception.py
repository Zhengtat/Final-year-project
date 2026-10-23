"""CR-008 §5/§8: the textbook misconception layer (mock LLM; no network, no key)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.misconception import (
    build_misconception_llm,
    check_item,
    consistent,
    expert_edges,
    run_stage,
    scan_cues,
)
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
REG = RelationRegistry.from_yaml(REPO / "configs/relations_v1.3.yaml")
PROMPT = load_prompt(REPO / "prompts", "misconception_structuring", "v2")
SCHEMA = build_misconception_llm(REG)

TEXT = (
    "A switch forwards frames. It is tempting to think that a hub also forwards each frame only to its "
    "destination, but a hub repeats every frame to all ports.\n\n"
    "Latency is not bandwidth. A hub is not a switch. The switch does not forward by IP address."
)
SECTIONS = [("s1", TEXT)]


def concept(cid, name, typ="Component"):
    return {
        "concept_id": cid,
        "canonical_name": name,
        "node_type": typ,
        "definition": None,
        "first_introduced": "s1",
        "aliases": [],
        "mentions": [],
        "description_history": [],
    }


CONCEPTS = [
    concept("c_hub", "hub"),
    concept("c_sw", "switch"),
    concept("c_fr", "frame", "DataUnit"),
    concept("c_lat", "latency", "Property"),
    concept("c_bw", "bandwidth", "Property"),
]


def edge(pid, x, rel, y, quote, pol="affirmed", direction="forward", group="selected", **extra):
    return {
        "outcome": "edge",
        "relation": rel,
        "direction": direction,
        "statement": f"{x} {rel} {y}",
        "evidence_quote": quote,
        "family": "mechanism_process",
        "qualifiers": {
            "polarity": pol,
            "modality": "always",
            "conditions": [],
            "part_type": None,
            "dimension": None,
            "surface_phrase": quote,
        },
        "group": group,
        "pair": {
            "pair_id": pid,
            "section_id": "s1",
            "concept_x_id": x,
            "concept_y_id": y,
            "sentence": quote,
        },
        **extra,
    }


E_SW = edge("P1", "c_sw", "acts_on", "c_fr", "A switch forwards frames")
E_CONTRAST = edge("P2", "c_lat", "contrasts_with", "c_bw", "Latency is not bandwidth")


def cp(extra_edges=()):
    return {"concepts": CONCEPTS, "relation_results_v3": [E_SW, E_CONTRAST, *extra_edges]}


class Fake:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), 0

    def parse(self, **kw):
        a = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        return SimpleNamespace(output=kw["schema"].model_validate(a))


BASE = {
    "is_warning": False,
    "reason": "plain fact",
    "intuition": None,
    "wrong_source": None,
    "wrong_relation": None,
    "wrong_target": None,
    "wrong_polarity": None,
    "wrong_modality": None,
    "wrong_conditions": [],
    "perturbation_type": None,
    "prevalence_cue": "none",
    "misconception_quote": None,
    "correction_quote": None,
    "contradicts": [],
    "proposed_correct": False,
    "pce_source": None,
    "pce_relation": None,
    "pce_target": None,
    "pce_polarity": None,
    "pce_quote": None,
}
WARN = {
    **BASE,
    "is_warning": True,
    "reason": "warns",
    "intuition": "a hub forwards per destination",
    "wrong_source": "c_hub",
    "wrong_relation": "acts_on",
    "wrong_target": "c_fr",
    "wrong_polarity": "affirmed",
    "wrong_modality": "always",
    "perturbation_type": "substituted_concept",
    "prevalence_cue": "stated_possible",
    "misconception_quote": "It is tempting to think that a hub also forwards each frame only to its destination",
    "correction_quote": "a hub repeats every frame to all ports",
    "contradicts": ["E:P1"],
}


def lex(tmp_path, different=()):
    path = tmp_path / "lex.yaml"
    path.write_text(yaml.safe_dump({"version": "t", "same": [], "different": list(different)}))
    return Lexicon.load(path, AliasConfig.load())


def diff(forms):
    return {
        "id": "d1",
        "forms": forms,
        "kind": "confusable",
        "why": "t",
        "scope": "book:pd6e",
        "status": "approved",
        "source": "t",
    }


def test_cue_scan_finds_each_family_and_the_lexicon_family(tmp_path):
    cands = scan_cues(SECTIONS, lex(tmp_path, [diff(["hub", "switch"])]))
    fams = {f for c in cands for f in c.families}
    assert {"tempting_belief", "negated_identity", "lexicon_different"} <= fams
    assert len({c.sentence for c in cands}) == len(cands)


def test_negated_plain_fact_stops_at_is_warning_false(tmp_path):
    layer = run_stage(Fake(BASE), PROMPT, REG, cp(), SECTIONS, lex(tmp_path))
    assert layer["items"] == [] and layer["not_warning"] and layer["stats"]["warnings"] == 0


def test_warning_becomes_a_layer_item_linked_to_the_correct_edge(tmp_path):
    state = cp()
    layer = run_stage(Fake(WARN), PROMPT, REG, state, SECTIONS, lex(tmp_path))
    assert layer["items"], layer
    it = layer["items"][0]
    assert (
        it["layer"] == "misconception"
        and it["contradicts"] == ["E:P1"]
        and it["status"] == "proposed"
    )
    assert it["origin"] == "textbook_warning"
    assert (
        len(state["relation_results_v3"]) == 2
    )  # excluded from the expert edges (nothing appended)
    assert set(expert_edges(state["relation_results_v3"])) == {"E:P1", "E:P2"}


def test_item_without_contradicts_never_enters_the_layer(tmp_path):
    bad = {**WARN, "contradicts": []}
    layer = run_stage(Fake(bad), PROMPT, REG, cp(), SECTIONS, lex(tmp_path), limit=1)
    assert layer["items"] == [] and layer["needs_review"]


def test_one_corrective_reprompt_then_owner_sheet(tmp_path):
    bad = {**WARN, "misconception_quote": "not in the text"}
    fake = Fake(bad, bad)
    layer = run_stage(fake, PROMPT, REG, cp(), SECTIONS, lex(tmp_path), limit=1)
    assert fake.calls == 2 and layer["needs_review"] and not layer["items"]
    fake2 = Fake(bad, WARN)  # the corrective answer passes
    assert run_stage(fake2, PROMPT, REG, cp(), SECTIONS, lex(tmp_path), limit=1)["items"]


def _ctx(edges):
    by_id = {c["concept_id"]: c for c in CONCEPTS}
    return {"shown": set(by_id), "edges": edges, "by_id": by_id}


@pytest.mark.parametrize(
    ("ptype", "wrong", "ok"),
    [
        ("polarity_flip", {"src": "c_sw", "rel": "acts_on", "tgt": "c_fr", "pol": "negated"}, True),
        (
            "polarity_flip",
            {"src": "c_sw", "rel": "acts_on", "tgt": "c_fr", "pol": "affirmed"},
            False,
        ),
        ("reversed", {"src": "c_fr", "rel": "acts_on", "tgt": "c_sw", "pol": "affirmed"}, True),
        (
            "substituted_concept",
            {"src": "c_hub", "rel": "acts_on", "tgt": "c_fr", "pol": "affirmed"},
            True,
        ),
        ("wrong_relation", {"src": "c_sw", "rel": "uses", "tgt": "c_fr", "pol": "affirmed"}, True),
        (
            "modality_error",
            {"src": "c_sw", "rel": "acts_on", "tgt": "c_fr", "pol": "affirmed", "mod": "possible"},
            True,
        ),
        (
            "condition_error",
            {"src": "c_sw", "rel": "acts_on", "tgt": "c_fr", "pol": "affirmed", "cond": ["x"]},
            True,
        ),
    ],
)
def test_perturbation_consistency(ptype, wrong, ok, tmp_path):
    ce = {
        "src": "c_sw",
        "rel": "acts_on",
        "tgt": "c_fr",
        "pol": "affirmed",
        "mod": "always",
        "cond": [],
    }
    w = {"mod": "always", "cond": [], **wrong}
    names = {c["concept_id"]: c["canonical_name"] for c in CONCEPTS}
    assert consistent(ptype, w, ce, REG, None, names) is ok


def test_conflation_needs_a_contrast_edge_or_lexicon_pair(tmp_path):
    names = {c["concept_id"]: c["canonical_name"] for c in CONCEPTS}
    w = {
        "src": "c_lat",
        "rel": "conflated_with",
        "tgt": "c_bw",
        "pol": "affirmed",
        "mod": None,
        "cond": [],
    }
    ce = {
        "src": "c_lat",
        "rel": "contrasts_with",
        "tgt": "c_bw",
        "pol": "affirmed",
        "mod": "always",
        "cond": [],
    }
    assert consistent("conflation", w, ce, REG, None, names)
    other = {
        "src": "c_sw",
        "rel": "acts_on",
        "tgt": "c_fr",
        "pol": "affirmed",
        "mod": "always",
        "cond": [],
    }
    assert not consistent("conflation", w, other, REG, None, names)
    assert consistent(
        "conflation", w, other, REG, lex(tmp_path, [diff(["latency", "bandwidth"])]), names
    )


def test_conflation_proposes_a_lexicon_entry(tmp_path):
    conf = {
        **WARN,
        "wrong_source": "c_lat",
        "wrong_relation": "conflated_with",
        "wrong_target": "c_bw",
        "perturbation_type": "conflation",
        "contradicts": ["E:P2"],
        "misconception_quote": "Latency is not bandwidth",
        "correction_quote": "Latency is not bandwidth",
    }
    layer = run_stage(Fake(conf), PROMPT, REG, cp(), SECTIONS, lex(tmp_path))
    assert layer["proposed_lexicon"] and layer["proposed_lexicon"][0]["status"] == "proposed"


def test_identical_wrong_edge_is_rejected():
    same = {
        **WARN,
        "wrong_source": "c_sw",
        "wrong_target": "c_fr",
        "perturbation_type": "polarity_flip",
    }
    out = SCHEMA.model_validate(same)
    errs = check_item(out, _ctx({"E:P1": E_SW}), TEXT, REG, None)
    assert any("identical" in e or "polarity_flip" in e for e in errs)


def test_proposed_correct_edge_goes_through_the_verifier(tmp_path):
    prop = {
        **WARN,
        "contradicts": [],
        "proposed_correct": True,
        "pce_source": "c_hub",
        "pce_relation": "acts_on",
        "pce_target": "c_fr",
        "pce_polarity": "affirmed",
        "pce_quote": "a hub repeats every frame to all ports",
    }
    seen = []

    def verifier(out, cand):
        seen.append(out.pce_relation)

    layer = run_stage(
        Fake(prop), PROMPT, REG, cp(), SECTIONS, lex(tmp_path), limit=1, verify=verifier
    )
    assert seen == ["acts_on"] and layer["needs_correct_edge"] and not layer["items"]

    def accept(out, cand):
        return edge("PX", "c_hub", "acts_on", "c_fr", out.pce_quote, found_by="misconception_stage")

    state = cp()
    # the proposed correct edge is E:PX; the wrong edge substitutes the endpoint relative to it
    ok = {**prop, "wrong_source": "c_sw", "perturbation_type": "substituted_concept"}
    layer = run_stage(Fake(ok), PROMPT, REG, state, SECTIONS, lex(tmp_path), limit=1, verify=accept)
    assert layer["items"] and layer["items"][0]["contradicts"] == ["E:PX"]
    assert state["relation_results_v3"][-1]["found_by"] == "misconception_stage"


def test_misconception_layer_is_invisible_to_expert_graph_code(tmp_path):
    from cumap.expert_kg.pipeline import Checkpoint
    from cumap.expert_kg.slice_rerun import build_pair_registry

    state = cp()
    run_stage(Fake(WARN), PROMPT, REG, state, SECTIONS, lex(tmp_path))
    ck = Checkpoint(
        run_id="r",
        stage="snapshots",
        relation_results_v3=state["relation_results_v3"],
        misconceptions=state["misconceptions"],
    )
    assert state["misconceptions"]["items"]
    pairs = {(p.concept_x_id, p.concept_y_id) for p in build_pair_registry(ck).all()}
    assert pairs == {
        ("c_sw", "c_fr"),
        ("c_lat", "c_bw"),
    }  # only expert pairs; no misconception edge


def test_conflation_may_contradict_a_lexicon_different_entry(tmp_path):
    """The book distinguishes the pair although no contrasts_with edge exists (CR-008 §5.4)."""
    state = {
        "concepts": [concept("c_rt", "routing table"), concept("c_ft", "forwarding table")],
        "relation_results_v3": [],
    }
    text = "A forwarding table is not a routing table. They are different data structures."
    d = {
        "id": "D1",
        "forms": ["routing table", "forwarding table"],
        "kind": "book_distinguishes",
        "why": "t",
        "scope": "book:pd6e",
        "status": "approved",
        "source": "t",
    }
    conf = {
        **WARN,
        "wrong_source": "c_ft",
        "wrong_relation": "conflated_with",
        "wrong_target": "c_rt",
        "perturbation_type": "conflation",
        "contradicts": ["L:D1"],
        "misconception_quote": "A forwarding table is not a routing table",
        "correction_quote": "They are different data structures",
    }
    layer = run_stage(Fake(conf), PROMPT, REG, state, [("s1", text)], lex(tmp_path, [d]))
    assert layer["items"] and layer["items"][0]["contradicts"] == ["L:D1"]
    assert len(layer["items"]) == 1  # the same wrong edge from several sentences is one item
    # a lexicon entry cannot support a non-conflation perturbation
    bad = {**conf, "perturbation_type": "polarity_flip", "wrong_relation": "uses"}
    assert not run_stage(Fake(bad), PROMPT, REG, state, [("s1", text)], lex(tmp_path, [d]))["items"]


def test_stage_is_idempotent_and_adds_an_edge_only_with_a_passing_item(tmp_path):
    prop = {
        **WARN,
        "contradicts": [],
        "proposed_correct": True,
        "wrong_source": "c_sw",
        "pce_source": "c_hub",
        "pce_relation": "acts_on",
        "pce_target": "c_fr",
        "pce_polarity": "affirmed",
        "pce_quote": "a hub repeats every frame to all ports",
    }

    def accept(out, cand):
        return edge("PX", "c_hub", "acts_on", "c_fr", out.pce_quote, found_by="misconception_stage")

    state = cp()
    for _ in range(2):  # a second run must not accumulate the stage's edges
        run_stage(Fake(prop), PROMPT, REG, state, SECTIONS, lex(tmp_path), limit=1, verify=accept)
    assert (
        sum(r.get("found_by") == "misconception_stage" for r in state["relation_results_v3"]) == 1
    )
    # an accepted edge whose item then fails the checks is NOT added to the expert layer
    bad = {**prop, "perturbation_type": "polarity_flip"}
    state2 = cp()
    run_stage(Fake(bad, bad), PROMPT, REG, state2, SECTIONS, lex(tmp_path), limit=1, verify=accept)
    assert not any(r.get("found_by") for r in state2["relation_results_v3"])
