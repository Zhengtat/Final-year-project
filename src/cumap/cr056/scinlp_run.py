"""CR-056: the frozen CR-012 SciNLP runner with profile v5 (`configs/scinlp_profile_v5.yaml`: the CR-055 arm B concept settings and
`pair_budget: all`). The frozen runner and `cr012/budget.py` are not edited: the profile path and, when the profile says `all`, the
runner's pair-budget function are set at call time, so every candidate pair is classified. Train / dev only (rule 9).

    uv run python -m cumap.cr056.scinlp_run run --split dev --doc <doc> ..."""

from __future__ import annotations

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR

PROFILE_V5 = REPO_ROOT / "configs/scinlp_profile_v5.yaml"


def all_pairs(_words: int, pool: int) -> int:
    return max(pool, 1)


def use_profile_v5() -> None:
    SR.PROFILE = PROFILE_V5
    if yaml.safe_load(PROFILE_V5.read_text()).get("pair_budget") == "all":
        SR.pair_budget = all_pairs


if __name__ == "__main__":
    use_profile_v5()
    SR.main()
