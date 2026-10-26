"""CR-057: the frozen CR-012 SciNLP runner with profile v6 (`configs/scinlp_profile_v6.yaml`: profile v5 + the M7 component-phrase
hint; every candidate pair classified). Same mechanism as `cumap.cr056.scinlp_run`. Train / dev only (rule 9).

    uv run python -m cumap.cr057.scinlp_run run --split dev --doc <doc> ..."""

from __future__ import annotations

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR
from cumap.cr056.scinlp_run import all_pairs

PROFILE_V6 = REPO_ROOT / "configs/scinlp_profile_v6.yaml"


def use_profile_v6() -> None:
    SR.PROFILE = PROFILE_V6
    if yaml.safe_load(PROFILE_V6.read_text()).get("pair_budget") == "all":
        SR.pair_budget = all_pairs


if __name__ == "__main__":
    use_profile_v6()
    SR.main()
