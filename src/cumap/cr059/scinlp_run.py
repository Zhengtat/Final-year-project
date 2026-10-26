"""CR-059 DRAFT: the frozen CR-012 SciNLP runner with profile v7 (`configs/scinlp_profile_v7.yaml`: type-free generator v7, the approved
domain profile, endpoint_check choice, every candidate pair classified). The frozen runner is not edited; as for CR-056 the profile path and
the all-pairs budget are set at call time. Train / dev only (rule 9). Refuses to start until the domain profile is owner-approved.

    uv run python -m cumap.cr059.scinlp_run run --split dev --doc <doc> ..."""

from __future__ import annotations

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR
from cumap.cr056.scinlp_run import all_pairs

PROFILE_V7 = REPO_ROOT / "configs/scinlp_profile_v7.yaml"


def use_profile_v7() -> None:
    from cumap.cr059.domain_profile import load_domain_profile

    prof = yaml.safe_load(PROFILE_V7.read_text())
    load_domain_profile(REPO_ROOT / prof["domain_profile"])  # raises unless the owner approved it
    SR.PROFILE = PROFILE_V7
    if prof.get("pair_budget") == "all":
        SR.pair_budget = all_pairs


if __name__ == "__main__":
    use_profile_v7()
    SR.main()
