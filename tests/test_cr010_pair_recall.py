"""CR-010 STOP 4A: the strict P2 cue matcher, pool hygiene, the sampled pair-recall estimator, the annotation validator,
the IAA subset and the sealed-classifier gate (no network, no key, no real run data)."""

import random
from collections import Counter

import pytest

from cumap.cr010 import iaa
from cumap.cr010 import pair_recall as PR
from cumap.cr010 import strict_cues as SC


# ---------------------------------------------------------------- strict cue matcher
def test_config_accounts_for_every_repository_cue_exactly_once():
    from cumap.config import REPO_ROOT, get_settings
    from cumap.expert_kg.relations import _cue_words
    from cumap.schemas.relations import RelationRegistry

    reg = RelationRegistry.from_yaml(REPO_ROOT / get_settings().relation_registry)
    r = SC.reconcile_with_inventory(SC.load_config(), _cue_words(reg))
    assert r == {"unaccounted": [], "invented": [], "duplicates": []}


def test_matcher_uses_token_boundaries_not_substrings():
    m = SC.build_matcher()
    assert m.find("Information is also stored in the causeway.") == []
    assert m.find("A switch requires a table.") == ["requires"]
    assert "cause" in m.find("The cause of loss is congestion.")
    assert "because" in m.find("It fails because of loss.")


def test_standalone_function_words_are_not_cues_but_multiword_expressions_are():
    m = SC.build_matcher()
    for s in ("We wait for it, so it works, if then.", "After that, once it ends, since when?"):
        assert m.find(s) == []
    assert m.find("Do this so that packets arrive.") == ["so that"]
    assert m.find("Do this in order to win.") == ["in order to"]
    assert m.find("It is a switch.") == ["is a"]  # relation-bearing multiword: preserved by policy


def test_multiword_cues_are_contiguous_and_never_cross_a_sentence_boundary():
    m = SC.build_matcher()
    assert m.find("It is part and parcel of IP.") == []  # not contiguous
    assert m.find("It is part of IP.") == ["part of"]
    assert not m.matches(["It is part", "of the plan."])
    assert m.matches(["It is part of the plan.", "Then it ends."])


def test_inflection_forms_are_explicit_and_deterministic():
    m = SC.build_matcher()
    assert m.find("The router was required to forward.") == ["requires"]
    assert m.find("Packets were led to the edge.") == ["leads to"]
    assert m.find("It prevented loss.") == ["prevents"]
    assert SC.config_hashes() == SC.config_hashes()


# ---------------------------------------------------------------- blind sheet
def fake_items():
    out = []
    for pool in PR.POOLS:
        for i in range(PR.N_PER_POOL):
            out.append(
                {
                    "pool": pool,
                    "concept_x_id": f"{pool}x{i}",
                    "concept_y_id": f"{pool}y{i}",
                    "name_x": f"x{i}",
                    "name_y": f"y{i}",
                    "section_id": f"s{i % 7}",
                    "evidence_text": "text",
                    "origin": "o",
                }
            )
    return out


def test_blind_sheet_hides_pool_mixes_order_and_is_deterministic():
    sheet, key = PR.blind_rows(fake_items())
    assert list(sheet[0]) == PR.BLIND_COLUMNS
    assert all(not r[c] for r in sheet for c in PR.BLIND_COLUMNS[5:])
    assert all("pool" not in r for r in sheet) and len(sheet) == 450
    first_pool = [Counter(k["pool"] for k in key[i : i + 30]) for i in range(0, 450, 30)]
    assert all(len(c) > 1 for c in first_pool[:5])  # pools are interleaved
    flips = Counter(k["shown_a"] for k in key)
    assert flips["x"] > 100 and flips["y"] > 100  # A/B order randomised
    assert PR.blind_rows(fake_items())[0] == sheet


# ---------------------------------------------------------------- annotation validation
REL = {"is_a", "part_of", "other"}
IDS = ["PR001", "PR002", "PR003"]


def row(pid, t="", rel="", d="", ev=""):
    return {
        "pair_id": pid,
        "true_relation_exists": t,
        "relation_if_yes": rel,
        "direction_if_yes": d,
        "evidence_supported": ev,
    }


def test_validate_requires_the_conditional_fields_and_rejects_stray_ones():
    ok = [row("PR001", "yes", "is_a", "a_to_b", "yes"), row("PR002", "no"), row("PR003", "unclear")]
    assert PR.validate_sheet(ok, IDS, REL) == []
    bad = [
        row("PR001", "yes", "invented", "a_to_b", "yes"),
        row("PR002", "no", "is_a"),
        row("PR003", ""),
    ]
    assert len(PR.validate_sheet(bad, IDS, REL)) == 3
    assert PR.validate_sheet(ok[:2], IDS, REL)  # a missing id is reported


def test_truth_definition_primary_and_sensitivities():
    yes_supported = row("a", "yes", "is_a", "a_to_b", "yes")
    yes_unsupported = row("b", "yes", "is_a", "a_to_b", "no")
    unclear = row("c", "unclear")
    assert PR.is_true(yes_supported) and not PR.is_true(yes_unsupported)
    assert PR.is_true(yes_unsupported, ignore_evidence=True)
    assert not PR.is_true(unclear) and PR.is_true(unclear, unclear_as_yes=True)


# ---------------------------------------------------------------- estimator
def mk_rows(true_by_pool, n=150, clusters=10, seed=1):
    rng = random.Random(seed)
    rows = []
    for pool in PR.POOLS:
        k = true_by_pool[pool]
        flags = [True] * k + [False] * (n - k)
        rng.shuffle(flags)
        rows += [
            {"pool": pool, "cluster": f"s{i % clusters}", "true": f} for i, f in enumerate(flags)
        ]
    return rows


SIZES = {"P0": 1000, "P1_extra": 8000, "P2_extra_strict": 5000}


def test_point_estimates_follow_the_definition():
    res = PR.cluster_bootstrap(
        mk_rows({"P0": 90, "P1_extra": 30, "P2_extra_strict": 15}), SIZES, b=500
    )
    T = res["estimated_true_edges"]
    assert T["P0"]["point"] == pytest.approx(1000 * 0.6)
    assert T["P1_extra"]["point"] == pytest.approx(8000 * 0.2)
    assert T["P2_extra_strict"]["point"] == pytest.approx(5000 * 0.1)
    total = 600 + 1600 + 500
    r = res["pair_recall_within_universe"]
    assert r["P0"]["point"] == pytest.approx(600 / total)
    assert r["P1"]["point"] == pytest.approx(2200 / total)
    assert r["P2"]["point"] == pytest.approx(1.0)
    lo, hi = r["P0"]["ci95_cluster"]
    assert lo <= r["P0"]["point"] <= hi


def test_cluster_interval_is_wider_than_the_naive_one_when_sections_differ():
    rows = []
    for pool in PR.POOLS:  # sections are all-true or all-false: extreme clustering
        for c in range(10):
            rows += [{"pool": pool, "cluster": f"{pool}{c}", "true": c < 3} for _ in range(15)]
    res = PR.cluster_bootstrap(rows, SIZES, b=2000)["prevalence"]["P0"]
    naive = res["wilson95_naive"][1] - res["wilson95_naive"][0]
    clustered = res["ci95_cluster"][1] - res["ci95_cluster"][0]
    assert clustered > naive * 1.3


def test_bootstrap_is_deterministic():
    r = mk_rows({"P0": 50, "P1_extra": 40, "P2_extra_strict": 10})
    a, b = PR.cluster_bootstrap(r, SIZES, b=300), PR.cluster_bootstrap(r, SIZES, b=300)
    assert a == b


# ---------------------------------------------------------------- the classifier stays sealed
def test_reveal_refuses_until_the_annotation_is_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(PR, "OUT", tmp_path)
    sheet = tmp_path / "marked.csv"
    sheet.write_text("pair_id\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        PR.reveal(sheet, [], [])
    PR.freeze_annotation(sheet)
    sheet.write_text("pair_id\nPR001\n", encoding="utf-8")  # edited after freezing
    with pytest.raises(SystemExit):
        PR.reveal(sheet, [], [])


def test_nothing_in_pair_recall_writes_under_data_gold():
    assert "gold" not in PR.OUT.parts and "gold" not in iaa.CHECKS.parts


# ---------------------------------------------------------------- IAA subset
def key_rows():
    rels = ["is_a", "part_of", "uses", "causes", "requires", "precedes"]
    rows = []
    for i in range(120):
        rows.append(
            {
                "item_id": f"E{i:03d}",
                "stratum": "ACCEPTED_EDGE",
                "current_relation": rels[i % 6],
                "current_reason": "",
                "current_outcome": "edge",
                "current_family": "f",
                "split": "dev" if i < 40 else "test",
            }
        )
    for i in range(30):
        rows.append(
            {
                "item_id": f"N{i:03d}",
                "stratum": "NO_RELATION",
                "current_relation": "none",
                "current_reason": "family_no_relation",
                "current_outcome": "no_relation",
                "current_family": "f",
                "split": "test",
            }
        )
        rows.append(
            {
                "item_id": f"O{i:03d}",
                "stratum": "OTHER_NEAR_MISS",
                "current_relation": "other",
                "current_reason": "relation_other" if i % 2 else "domain_range",
                "current_outcome": "other",
                "current_family": "f",
                "split": "test",
            }
        )
    return rows


def test_iaa_subset_has_the_exact_composition_and_covers_relations():
    kr = key_rows()
    ids = iaa.select(kr)
    by = Counter(r["stratum"] for r in kr if r["item_id"] in set(ids))
    assert by == {"ACCEPTED_EDGE": 40, "NO_RELATION": 10, "OTHER_NEAR_MISS": 10}
    rels = Counter(
        r["current_relation"]
        for r in kr
        if r["item_id"] in set(ids) and r["stratum"] == "ACCEPTED_EDGE"
    )
    assert set(rels) == {"is_a", "part_of", "uses", "causes", "requires", "precedes"}
    assert max(rels.values()) - min(rels.values()) <= 1  # broad, even coverage
    assert iaa.select(kr) == ids  # deterministic


def test_iaa_selection_cannot_see_annotator_labels():
    kr = key_rows()
    with_labels = [{**r, "current_semantic_relation_judgement": "x"} for r in kr]
    assert iaa.select(with_labels) == iaa.select(kr)


def test_kappa_and_the_gate_without_a_second_human_annotator():
    assert iaa.cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert iaa.cohen_kappa(["a", "b", "a", "b"], ["b", "a", "b", "a"]) == -1.0
    assert iaa.cohen_kappa([], []) is None
    s = iaa.status(None, None)
    assert s["iaa_gate"] == "NOT_EVALUABLE" and s["full_erst_replacement"] == "INELIGIBLE"
