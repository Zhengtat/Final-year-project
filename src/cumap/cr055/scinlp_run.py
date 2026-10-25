"""CR-055: the frozen CR-012 SciNLP runner with profile v4 (`configs/scinlp_profile_v4.yaml`: generator prompt v6_scinlp and the
concept_recall switches), or the profile named by `CUMAP_SCINLP_PROFILE` (e.g. `configs/scinlp_profile_v4_g2.yaml`). Train / dev only.

    uv run python -m cumap.cr055.scinlp_run run --split dev --doc <doc> ..."""

from __future__ import annotations

import os

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR

PROFILE_V4 = REPO_ROOT / "configs/scinlp_profile_v4.yaml"


def use_profile() -> None:
    SR.PROFILE = (
        REPO_ROOT / os.environ["CUMAP_SCINLP_PROFILE"]
        if os.environ.get("CUMAP_SCINLP_PROFILE")
        else PROFILE_V4
    )


if __name__ == "__main__":
    use_profile()
    SR.main()
