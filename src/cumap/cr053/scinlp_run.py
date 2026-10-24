"""CR-053: the frozen CR-012 SciNLP runner with profile v3 (`configs/scinlp_profile_v3.yaml`: profile v2 + generator prompt
`concept_generator/v5_scinlp`). Same commands as the frozen runner; train / dev only (rule 9).

    uv run python -m cumap.cr053.scinlp_run run --split dev --doc <doc> ..."""

from __future__ import annotations

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR

PROFILE_V3 = REPO_ROOT / "configs/scinlp_profile_v3.yaml"


def use_profile_v3() -> None:
    SR.PROFILE = PROFILE_V3  # read at call time; the frozen runner file is unchanged


if __name__ == "__main__":
    use_profile_v3()
    SR.main()
