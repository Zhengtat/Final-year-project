"""CR-043 runner: E0 (the real pipeline) on SciNLP train / dev papers with the CURRENT production settings (the local model
profile, R1-key matching, rejected-link adjudicator, backfill off). One subprocess of `cumap.cr012.scinlp_run run` per paper.

    uv run python -m cumap.cr043.run --dry-run            # estimates only
    uv run python -m cumap.cr043.run --limit 2            # the first 2 papers
    uv run python -m cumap.cr043.run                      # all 20 papers of the first set
The test split is refused (rule 9). Spending stops at --cap-usd (logged spend of the finished papers, all stages and models)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

from cumap.cr012 import production_graph as PG
from cumap.cr043.papers import first_set

TAG = "cr043base"
MAX_USD_PER_DOC = 1.0


def run_id(doc: str, tag: str = TAG) -> str:
    return f"cr012_scinlp_{tag}_{doc.replace('.', '_').replace('-', '_')}_E0"


def recorded_spend(rid: str) -> float:
    """USD of the run's non-cached calls, from the LLM call log (all stages, every model including escalations)."""
    from cumap.cr025.report import usage

    return float(usage([rid])["usd"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cap-usd", type=float, default=3.0)
    ap.add_argument("--tag", default=TAG)
    a = ap.parse_args()
    papers = first_set()[: a.limit] if a.limit else first_set()
    spent = 0.0
    for split, d in papers:
        assert split in ("train", "dev")
        rid = run_id(d, a.tag)
        ck = PG.run_path(rid) / "checkpoint.json"
        done = ck.exists() and json.loads(ck.read_text()).get("stage") == "snapshots"
        if done and not a.dry_run:
            spent += recorded_spend(rid)
            print(
                json.dumps(
                    {
                        "split": split,
                        "doc": d,
                        "skipped": "already finished",
                        "spent_so_far": round(spent, 4),
                    }
                ),
                flush=True,
            )
            continue
        cmd = [sys.executable, "-m", "cumap.cr012.scinlp_run", "run", "--split", split, "--doc", d, "--tag", a.tag,
               "--max-usd", str(MAX_USD_PER_DOC)] + (["--dry-run"] if a.dry_run else [])  # fmt: skip
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        spent += 0.0 if a.dry_run else recorded_spend(rid)
        print(json.dumps({"split": split, "doc": d, "rc": r.returncode, "s": round(time.time() - t0), "resumed": ck.exists(),
                          "spent_so_far": round(spent, 4), "tail": (r.stdout + r.stderr)[-240:]}), flush=True)  # fmt: skip
        if r.returncode:
            raise SystemExit(f"{d} failed")
        if spent > a.cap_usd:
            raise SystemExit(f"cap reached: ${spent:.3f} > ${a.cap_usd}")


if __name__ == "__main__":
    main()
