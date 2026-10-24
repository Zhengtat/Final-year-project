"""CR-048: the cue pair set and the misconception switch stays legacy (no network, no key)."""

import yaml

from cumap.config import REPO_ROOT
from cumap.cr048 import run as R


def test_cue_pairs_are_unordered_unique_pairs_from_cue_sentences():
    cp = {
        "concepts": [
            {"concept_id": "c_a", "canonical_name": "routing table", "node_type": "Component", "aliases": []},
            {"concept_id": "c_b", "canonical_name": "forwarding table", "node_type": "Component", "aliases": []},
            {"concept_id": "c_c", "canonical_name": "router", "node_type": "Component", "aliases": []},
        ],
        "misconceptions": {"candidate_log": [
            {"section_id": "3.4", "sentence": "A routing table is not a forwarding table in a router.", "outcome": "items"},
            {"section_id": "3.4", "sentence": "Nothing here.", "outcome": "not_warning"},
        ]},
    }  # fmt: skip
    pairs = R.cue_pairs(cp)
    assert sorted((p["concept_x_id"], p["concept_y_id"]) for p in pairs) == [
        ("c_a", "c_b"),
        ("c_a", "c_c"),
        ("c_b", "c_c"),
    ]
    assert all(p["concept_x_id"] < p["concept_y_id"] for p in pairs)


def test_misconception_source_stays_legacy_after_cr048():
    pol = yaml.safe_load((REPO_ROOT / "configs/relation_policy.yaml").read_text())
    assert pol["misconception_source"] == "legacy"
