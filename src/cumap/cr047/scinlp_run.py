"""CR-047: the frozen CR-012 SciNLP runner (`cr012/scinlp_run.py`, hash-pinned, not edited) with profile v2
(`configs/scinlp_profile_v2.yaml`: registry `relations_scinlp_v1.0.1.yaml`, no modality `never`), so new SciNLP runs can use
`qualifier_amendments: v6`. Same commands and arguments as the frozen runner:

    uv run python -m cumap.cr047.scinlp_run run --split dev --doc <doc> ...
Train / dev only, as the frozen runner enforces (rule 9)."""

from __future__ import annotations

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR

PROFILE_V2 = REPO_ROOT / "configs/scinlp_profile_v2.yaml"


def use_profile_v2() -> None:
    SR.PROFILE = (
        PROFILE_V2  # read at call time by SR.prepare / SR.run; the frozen file is unchanged
    )


if __name__ == "__main__":
    use_profile_v2()
    SR.main()
