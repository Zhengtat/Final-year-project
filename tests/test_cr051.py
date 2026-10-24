"""CR-051: the rejected-link adjudicator runs on the policy tier (sol under the luna profile) (no network, no key)."""

import yaml

from cumap.concepts_v4.rejected_links import adjudicator_tier
from cumap.config import REPO_ROOT


def test_policy_names_escalate_and_a_profile_without_it_falls_back_to_strong():
    assert (
        yaml.safe_load((REPO_ROOT / "configs/concept_policy.yaml").read_text())[
            "rejected_link_tier"
        ]
        == "escalate"
    )
    assert adjudicator_tier({"strong": 1, "bulk": 1, "escalate": 1}) == "escalate"
    assert adjudicator_tier({"strong": 1, "bulk": 1}) == "strong"
