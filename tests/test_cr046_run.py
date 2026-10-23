"""CR-046 measurement runner: arm ids and arm settings (no network, no key)."""

from cumap.cr046 import run as R
from cumap.cr046 import score as S


def test_arm_ids_are_new_and_bases_are_the_r1key_dev_runs():
    assert R.arm_id("1.5", "AMEND") == "cr046_amend_cr012_pilot_1_5_E0"
    assert R.base_id("2.6") == "cr020_r1key_cr012_pilot_2_6_E0"
    assert R.ARMS["BASE"]["qualifier_amendments"] == "off"
    assert R.ARMS["AMEND"] == {
        "registry": "configs/relations_v1.5.yaml",
        "qualifier_amendments": "v6",
    }


def test_agreement_counts_same_edges_only():
    p = {"section_id": "1.5", "concept_x_id": "a", "concept_y_id": "b", "sentence": "s"}
    e = {"pair": p, "outcome": "edge", "relation": "uses", "direction": "forward",
         "qualifiers": {"polarity": "affirmed", "modality": "never", "part_type": None}}  # fmt: skip
    f = {**e, "qualifiers": {"polarity": "affirmed", "modality": "always", "part_type": None}}
    out = S.agreement([e], [f])
    assert (
        out["same_edge_both_arms"] == 1
        and out["polarity_agree"] == 1
        and out["modality_agree"] == 0
    )
    assert out["modality_never_to"] == {"always": 1}
