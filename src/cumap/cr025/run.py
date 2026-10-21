"""CR-025 runner: one model for BOTH tiers on the SciNLP dev split (6 papers), the CR-021 dev recipe (E0, production settings), new run ids.

    uv run python -m cumap.cr025.run run   --arm luna|o4mini|sol [--dry-run] [--docs a,b]    # sequential over the docs
Each paper is a subprocess of `cumap.cr012.scinlp_run run` with the arm's model environment, so the arms can run in parallel processes.
The SciNLP test split is never opened here (rule 9)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

from cumap.cr012 import scinlp_run as SR
from cumap.cr019.stage_b import SC_DEV

ARMS = {"sol": "gpt-6-sol", "o4mini": "o4-mini", "luna": "gpt-6-luna"}
PRICE = {
    "gpt-6-sol": (2.0, 10.0),
    "o4-mini": (1.10, 4.40),
    "gpt-6-luna": (0.10, 0.50),
}  # USD per 1M tokens in / out
MAX_USD_PER_DOC = 2.0


def tag(arm: str) -> str:
    return f"cr025_{arm}"


def run_id(arm: str, doc: str) -> str:
    return f"cr012_scinlp_{tag(arm)}_{doc.replace('.', '_').replace('-', '_')}_E0"


def arm_env(arm: str) -> dict:
    m = ARMS[arm]
    return {
        **os.environ,
        "OPENAI_MODEL_STRONG": m,
        "OPENAI_MODEL_BULK": m,
        "CUMAP_MODELS_CONFIG": f"configs/models_cr025_{arm}.yaml",
    }


def run_arm(arm: str, docs: list[str], dry_run: bool) -> None:
    for d in docs:
        assert SR.split_allowed("dev")
        t0 = time.time()
        cmd = [
            sys.executable,
            "-m",
            "cumap.cr012.scinlp_run",
            "run",
            "--split",
            "dev",
            "--doc",
            d,
            "--tag",
            tag(arm),
            "--max-usd",
            str(MAX_USD_PER_DOC),
        ]
        r = subprocess.run(
            cmd + (["--dry-run"] if dry_run else []),
            env=arm_env(arm),
            capture_output=True,
            text=True,
            check=False,
        )
        print(
            json.dumps(
                {
                    "arm": arm,
                    "doc": d,
                    "returncode": r.returncode,
                    "seconds": round(time.time() - t0),
                    "tail": (r.stdout + r.stderr)[-300:],
                }
            ),
            flush=True,
        )
        if r.returncode:
            raise SystemExit(f"{arm} {d} failed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["run"])
    ap.add_argument("--arm", required=True, choices=list(ARMS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--docs", default=",".join(SC_DEV))
    a = ap.parse_args()
    run_arm(a.arm, a.docs.split(","), a.dry_run)


if __name__ == "__main__":
    main()
