"""CR-059 DRAFT: the SciNLP runner with profile v8 (= v7 with the narrower domain profile v2). Refuses to start until profile v2 is
owner-approved. Train / dev only (rule 9).

    uv run python -m cumap.cr059.scinlp_run_v8 run --split dev --doc <doc> ..."""

from __future__ import annotations

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR
from cumap.cr059 import scinlp_run as R7

PROFILE_V8 = REPO_ROOT / "configs/scinlp_profile_v8.yaml"

if __name__ == "__main__":
    R7.PROFILE_V7 = (
        PROFILE_V8  # same checks (approved domain profile, all pairs), the v8 profile file
    )
    R7.use_profile_v7()
    SR.main()
