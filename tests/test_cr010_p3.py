"""CR-010 P3: eRST-linked candidate pairs, exclusion of earlier pools, the four-pool estimator, sealed classifier gate."""

import random
from types import SimpleNamespace

import pytest

from cumap.cr010 import p3 as P3
from cumap.cr010 import pair_recall as PR
from cumap.expert_kg.canonicalize import RegisteredConcept


def concept(cid, name):
    return RegisteredConcept(
        concept_id=cid,
        canonical_name=name,
        node_type="Concept",
        definition=None,
        first_introduced="s",
    )


SECTION = SimpleNamespace(
    section_id="s1",
    text="A router forwards packets. A switch learns addresses. The cable is long. A hub repeats bits.",
)
CS = [concept("r", "router"), concept("s", "switch"), concept("c", "cable"), concept("h", "hub")]


def edge(label, nuclei, sat):
    return {
        "section_id": "s1",
        "edge": {"label": label, "nucleus_units": nuclei, "satellite_unit": sat},
    }


def test_a_direct_edge_links_the_concepts_of_its_two_units_only():
    g = {
        "edges": [
            edge("ELABORATION-ADDITIONAL", ["U0"], "U1"),
            edge("ELABORATION-ADDITIONAL", ["U0"], "U3"),
        ]
    }
    got = P3.linked_pairs(g, [SECTION], CS)
    assert set(got) == {frozenset("rs"), frozenset("rh")}
    assert "cable" not in str(got)  # unit 2 is linked to nothing
    far = got[frozenset("rh")]["links"][0]
    assert far["text"] == "A router forwards packets." + P3.GAP + "A hub repeats bits."
    assert (
        got[frozenset("rs")]["links"][0]["text"].count(P3.GAP) == 0
    )  # adjacent units are joined plainly


def test_multinuclear_edges_link_every_pair_of_nuclei_and_there_is_no_transitive_closure():
    g = {
        "edges": [
            edge("JOINT-LIST", ["U0", "U1", "U3"], None),
            edge("ELABORATION-ADDITIONAL", ["U1"], "U2"),
        ]
    }
    got = P3.linked_pairs(g, [SECTION], CS)
    assert frozenset("rs") in got and frozenset("rh") in got and frozenset("sh") in got
    assert frozenset("rc") not in got  # U0 and U2 are only linked through U1


def test_labels_are_kept_for_the_key_only():
    g = {"edges": [edge("CAUSAL-CAUSE", ["U1"], "U0")]}
    link = P3.linked_pairs(g, [SECTION], CS)[frozenset("rs")]["links"][0]
    assert link["labels"] == ["CAUSAL-CAUSE"]
    assert not any(lab in col for col in PR.BLIND_COLUMNS for lab in link["labels"])


def rows(true_by, n=150, clusters=10):
    rng = random.Random(3)
    out = []
    for pool, k in true_by.items():
        flags = [True] * k + [False] * (n - k)
        rng.shuffle(flags)
        out += [
            {"pool": pool, "cluster": f"s{i % clusters}", "true": f} for i, f in enumerate(flags)
        ]
    return out


def test_four_pool_recall_follows_the_definition_and_p3_is_the_universe():
    sizes = {"P0": 1000, "P1_extra": 8000, "P2_extra_strict": 5000, "P3_extra": 2000}
    res = P3.nested_bootstrap(
        rows({"P0": 90, "P1_extra": 30, "P2_extra_strict": 15, "P3_extra": 30}), sizes, b=300
    )
    t = [600, 1600, 500, 400]
    rec = res["pair_recall_within_universe"]
    assert rec["P0"]["point"] == pytest.approx(t[0] / sum(t))
    assert rec["P2"]["point"] == pytest.approx(sum(t[:3]) / sum(t))
    assert rec["P3"]["point"] == pytest.approx(1.0)


def test_p3_classifier_stays_sealed_until_its_annotation_is_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(PR, "OUT", tmp_path)
    sheet = tmp_path / "p3.csv"
    sheet.write_text("pair_id\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        P3.reveal_p3(sheet, [], [])
