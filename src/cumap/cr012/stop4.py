"""CR-012 STOP 4 execution under the frozen `stop3-frozen` configuration. Held-out units run ONCE; nothing is tuned and no run is repeated because
of its result. Every model run is a subprocess of the frozen runners (own settings, own env), recorded in `reports/cr012/stop4_log.jsonl`.

    uv run python -m cumap.cr012.stop4 plan                       # $0: units, budgets, cost forecast
    uv run python -m cumap.cr012.stop4 run --authorised           # main held-out runs (resumable: a finished run is never repeated)
    uv run python -m cumap.cr012.stop4 stability --authorised     # 3 independent repeats on the frozen subset, private caches
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import yaml

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import cost as C
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.budget import pair_budget
from cumap.llm.cost import spend_from_log

TAG = "heldout"
GOLD_SHEET = "data/gold/pd_e2e_test_blind.csv"
LOG = REPO_ROOT / "reports/cr012/stop4_log.jsonl"
SPENT_BEFORE_STOP4 = 2.8539  # reports/cr012/spend_to_date.json (accepted by Research)
SOFT, HARD = 40.0, 50.0
CFG = yaml.safe_load((REPO_ROOT / "configs/cr012_e2e_eval.yaml").read_text())
PD_LEVELS = ("E0", "E1", "E2", "E3", "E4")
SC_LEVELS = ("E0", "E1", "E3", "E4")  # E2 NOT_SUPPORTED (no identity gold)


def pd_sections() -> list[str]:
    import csv

    with (REPO_ROOT / GOLD_SHEET).open(encoding="utf-8") as f:
        return sorted({r["section_id"] for r in csv.DictReader(f) if r["row_type"] == "SECTION"})


def sc_docs() -> list[str]:
    return [d.doc_key for d in SciNLPAdapter().load_documents("test")]


def run_id(kind: str, unit: str, level: str, tag: str = TAG) -> str:
    u = unit.replace(".", "_").replace("-", "_")
    return f"cr012_{tag}_{u}_{level}" if kind == "pd" else f"cr012_scinlp_{tag}_{u}_{level}"


def finished(rid: str) -> bool:
    f = REPO_ROOT / "data/processed/kg" / rid / "checkpoint.json"
    return f.exists() and bool(json.loads(f.read_text()).get("relation_results_v3"))


def spent_total() -> float:
    s, tot = get_settings(), SPENT_BEFORE_STOP4
    root = REPO_ROOT / "data/processed/kg"
    for d in sorted(root.glob(f"cr012_*{TAG}*")) + sorted(root.glob("cr012_*stab*")):
        tot += spend_from_log(s, d.name)
    return tot


def commands(kind: str, unit: str, level: str, tag: str = TAG, max_usd: float = 3.0) -> list[str]:
    py = [sys.executable, "-m"]
    m = str(max_usd)
    if kind == "pd":
        if level == "E0":
            return [
                *py,
                "cumap.cr012.unit_run",
                "run",
                "--section",
                unit,
                "--tag",
                tag,
                "--max-usd",
                m,
            ]
        return [*py, "cumap.cr012.oracle_run", level, "--section", unit, "--pilot-sheet", GOLD_SHEET, "--tag", tag, "--max-usd", m]  # fmt: skip
    if level == "E0":
        return [*py, "cumap.cr012.scinlp_run", "run", "--split", "test", "--doc", unit, "--tag", tag, "--max-usd", m]  # fmt: skip
    return [*py, "cumap.cr012.scinlp_oracle", level, "--split", "test", "--doc", unit, "--tag", tag, "--max-usd", m]  # fmt: skip


def execute(kind: str, unit: str, level: str, tag: str = TAG, cache_dir: str | None = None) -> dict:
    rid = run_id(kind, unit, level, tag)
    if finished(rid):
        return {"run_id": rid, "status": "already_finished_not_repeated"}
    before = spent_total()
    if before >= HARD - 1.0:
        raise SystemExit(
            f"STOP: spend {before:.2f} is within $1 of the ${HARD} hard cap; return to Research"
        )
    if before >= SOFT:
        print(f"WARNING: spend {before:.2f} is over the ${SOFT} soft warning", flush=True)
    env = {**os.environ, "CUMAP_CR012_STOP4": "1"}
    if cache_dir:
        env["CUMAP_LLM_CACHE_DIR"] = cache_dir
    t0 = time.time()
    p = subprocess.run(commands(kind, unit, level, tag), env=env, cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # fmt: skip
    rec = {
        "run_id": rid, "kind": kind, "unit": unit, "level": level, "tag": tag, "returncode": p.returncode,
        "seconds": round(time.time() - t0), "spent_total_after": round(spent_total(), 4),
        "stderr_tail": p.stderr[-600:] if p.returncode else "",
    }  # fmt: skip
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)
    if p.returncode or not finished(rid):
        raise SystemExit(
            f"STOP: {rid} did not finish ({p.returncode}); inspect, preserve as invalid, do not rerun blindly"
        )
    return rec


def plan() -> dict:
    words = {s: len(r["text"].split()) for s in pd_sections() for r in __import__("cumap.cr012.pd_e2e", fromlist=["x"]).load_sections() if r["section_id"] == s}  # fmt: skip
    docs = {d.doc_key: d.word_count for d in SciNLPAdapter().load_documents("test")}
    cp = C.build()
    out = {
        "tag": TAG,
        "pd_sections": words, "scinlp_test_docs": docs,
        "max_budget_pairs_D3": {k: pair_budget(w, 10**6) for k, w in {**words, **docs}.items()},
        "pd_levels": PD_LEVELS, "scinlp_levels": SC_LEVELS,
        "stability_subset": CFG["stability"]["subset"], "stability_repeats": CFG["stability"]["repeats"],
        "forecast_usd": cp, "spent_before": SPENT_BEFORE_STOP4,
        "projected_mandatory_total_upper": round(SPENT_BEFORE_STOP4 + cp["upper_no_sharing"]["heldout_pd"] + cp["upper_no_sharing"]["heldout_scinlp"] + cp["upper_no_sharing"]["stability"], 2),
        "hard_cap": HARD, "soft_warning": SOFT,
    }  # fmt: skip
    out["status"] = (
        "WITHIN_CAP"
        if out["projected_mandatory_total_upper"] <= HARD
        else "STOP_RETURN_TO_RESEARCH"
    )
    (REPO_ROOT / "reports/cr012/stop4_plan.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8"
    )
    return out


def run_main() -> None:
    for sid in pd_sections():
        for lv in PD_LEVELS:
            execute("pd", sid, lv)
    for d in sc_docs():
        for lv in SC_LEVELS:
            execute("sc", d, lv)


def run_stability() -> None:
    sub = CFG["stability"]["subset"]
    for i in range(1, CFG["stability"]["repeats"] + 1):
        cache = str(REPO_ROOT / f"data/cache/cr012_stability/run_{i}")
        for sid in sub["pd_sections"]:
            execute("pd", str(sid), "E0", f"stab{i}", cache)
        for d in sub["scinlp_documents"]:
            execute("sc", d, "E0", f"stab{i}", cache)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["plan", "run", "stability"])
    ap.add_argument(
        "--authorised",
        action="store_true",
        help="STOP 4 is authorised by Research (2026-10-10, held-out gold frozen)",
    )
    a = ap.parse_args()  # fmt: skip
    if a.phase == "plan":
        print(json.dumps(plan(), indent=1, default=str))
        return
    if not a.authorised:
        raise SystemExit("refusing to run held-out units without --authorised")
    plan_ = plan()
    if plan_["status"] != "WITHIN_CAP":
        raise SystemExit("projected mandatory total exceeds the hard cap: return to Research")
    run_main() if a.phase == "run" else run_stability()


if __name__ == "__main__":
    main()
