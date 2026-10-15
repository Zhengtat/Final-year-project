"""CR-020 experiment runner: re-run pair generation, selection and the production relation stage on a copy of each dev E0 run, under a
chosen matching mode. Concepts are copied, never re-run. Pre-registered in docs/change-requests/CR-020-r1key-matching.md; cap $10.

    uv run python -m cumap.cr020.run check  --base <run_id>                     # TOKEN re-selection must equal the base selection ($0)
    uv run python -m cumap.cr020.run select --base <run_id>                     # R1KEY pair generation + selection ($0)
    uv run python -m cumap.cr020.run relations --base <run_id> [--limit 20] [--dry-run]
    uv run python -m cumap.cr020.run spend
    uv run python -m cumap.cr020.run score
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import unit_run as UR
from cumap.cr012.budget import pair_budget
from cumap.cr019 import stage_b as SB

CAP_USD = 10.0
KG = REPO_ROOT / "data/processed/kg"
OUT = REPO_ROOT / "reports/cr020"
BASES = [SB.sc_base(d) for d in SB.SC_DEV] + [SB.pd_base(s) for s in SB.PD_DEV]


def arm_id(base: str, mode: str) -> str:
    return f"cr020_{mode}_{base}"


def _words(sections_path) -> int:
    return sum(
        len(json.loads(x)["text"].split())
        for x in sections_path.read_text().splitlines()
        if x.strip()
    )


def _copy(base: str, rid: str) -> None:
    from cumap.expert_kg.pipeline import load_checkpoint, save_checkpoint

    if (KG / rid).exists():
        return
    (KG / rid).mkdir(parents=True)
    for f in ("checkpoint.json", "v4_concepts.json"):
        if (KG / base / f).exists():
            shutil.copy2(KG / base / f, KG / rid / f)
    cp = load_checkpoint(KG / rid)
    cp.selected_pairs, cp.sample_pairs, cp.relation_results_v3 = [], [], []
    cp.stage = "select"
    save_checkpoint(cp, KG / rid)


def select(base: str, mode: str) -> dict:
    """Pair generation + selection under `mode`, with the CR-012 D3 budget rule (same as the base runs)."""
    src = SB.use_unit(base)
    os.environ["CUMAP_MATCHING"] = mode
    rid = arm_id(base, mode)
    _copy(base, rid)
    words = _words(src)
    budget = math.ceil(14.2 * words / 1000)
    sel = UR.select_without_sample(rid, budget)
    b = pair_budget(words, sel.get("unique_candidate_pairs", 0))
    if b != budget:
        sel = UR.select_without_sample(rid, b)
    cp = json.loads((KG / rid / "checkpoint.json").read_text())
    return {
        "run_id": rid,
        "words": words,
        "budget": b,
        "pool": sel.get("unique_candidate_pairs"),
        "selected": len(cp["selected_pairs"]),
    }


def _pair_keys(rid: str) -> list[tuple]:
    cp = json.loads((KG / rid / "checkpoint.json").read_text())
    return sorted(
        (p["section_id"], *sorted((p["concept_x_id"], p["concept_y_id"])), p["sentence"])
        for p in cp["selected_pairs"]
    )


def check(base: str) -> dict:
    """Determinism: a TOKEN re-selection on a copy must reproduce the base run's selected pairs exactly."""
    r = select(base, "token")
    same = _pair_keys(r["run_id"]) == _pair_keys(base)
    return {**r, "reproduces_base_selection": same}


def spend() -> dict:
    from cumap.llm.cost import spend_from_log

    st = get_settings()
    per = {
        arm_id(b, m): round(spend_from_log(st, arm_id(b, m)), 4)
        for b in BASES
        for m in ("r1key", "token")
    }
    return {
        "per_run": {k: v for k, v in per.items() if v},
        "total_usd": round(sum(per.values()), 4),
        "cap_usd": CAP_USD,
    }


def relations(base: str, *, limit: int | None, dry_run: bool, max_usd: float) -> dict:
    from cumap.concepts_v4 import experiments as X
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.pipeline import load_checkpoint
    from cumap.llm.client import LLMClient
    from cumap.schemas.relations import RelationRegistry

    SB.use_unit(base)
    os.environ["CUMAP_MATCHING"] = (
        "r1key"  # endpoint grounding uses the same matching as pair generation
    )
    rid = arm_id(base, "r1key")
    cp = load_checkpoint(KG / rid)
    if cp is None or not cp.selected_pairs:
        raise SystemExit(f"run `select --base {base}` first")
    pre = sr.preflight_relations(cp)
    if dry_run:
        return {"dry_run": True, "run_id": rid, **pre}
    left = CAP_USD - spend()["total_usd"]
    if left < max_usd:
        raise SystemExit(
            f"CR-020 cap: ${left:.2f} left of ${CAP_USD}, run asks for up to ${max_usd}"
        )
    settings = get_settings()
    settings.llm.stage_budgets_usd["relations"] = max_usd
    client = LLMClient(settings, run_id=rid)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    cp = sr.relations_stage(client, cp, KG / rid, registry, REPO_ROOT / "prompts", X.Embedder(settings.embeddings.model), progress=print, limit=limit)  # fmt: skip
    return {
        "run_id": rid,
        "results": len(cp.relation_results_v3),
        "pairs": pre["pairs"],
        "spend_usd": round(client.spent_usd, 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "select", "relations", "spend", "score"])
    ap.add_argument("--base")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=2.0)
    a = ap.parse_args()
    if a.cmd == "check":
        out = check(a.base)
    elif a.cmd == "select":
        out = select(a.base, "r1key")
    elif a.cmd == "relations":
        out = relations(a.base, limit=a.limit, dry_run=a.dry_run, max_usd=a.max_usd)
    elif a.cmd == "spend":
        out = spend()
    else:
        from cumap.cr020.score import main as score

        out = score()
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
