"""CR-046 measurement of the CR-038 qualifier amendments (handoff section 10), pre-registered in docs/DECISIONS.md before any call.

Two arms on the SAME concepts and the SAME selected pairs: the P&D development runs `cr020_r1key_cr012_pilot_{1_5,2_6}_E0`
(current production settings, R1-key matching) are copied to new run ids, their relation results are cleared (the selected pairs
are kept), and only the relation stage is re-run under the luna profile:

- `BASE`:  production relation stage (family v3, choice v4, qualifiers v4, registry v1.3), `qualifier_checks: v1`;
- `AMEND`: `qualifier_amendments: v6` (choice v6, qualifiers v6, registry v1.5), `qualifier_checks: v1`.

    uv run python -m cumap.cr046.run relations --arm BASE --dry-run
    uv run python -m cumap.cr046.run relations --arm AMEND --limit 20
    uv run python -m cumap.cr046.run relations --arm AMEND
    uv run python -m cumap.cr046.run spend
P&D development sections only (rule 9); no gold is read here."""

from __future__ import annotations

import argparse
import json
import os
import shutil

from cumap.config import REPO_ROOT, get_settings
from cumap.cr019 import stage_b as SB

CAP_USD = 1.0
KG = REPO_ROOT / "data/processed/kg"
ARMS = {
    "BASE": {"registry": "configs/relations_v1.3.yaml", "qualifier_amendments": "off"},
    "AMEND": {"registry": "configs/relations_v1.5.yaml", "qualifier_amendments": "v6"},
}


def base_id(sid: str) -> str:
    return f"cr020_r1key_{SB.pd_base(sid)}"


def arm_id(sid: str, arm: str) -> str:
    return f"cr046_{arm.lower()}_{SB.pd_base(sid)}"


def _copy(src: str, rid: str) -> None:
    """Concepts and selected pairs from the base run; relation results cleared."""
    from cumap.expert_kg.pipeline import load_checkpoint, save_checkpoint

    if (KG / rid).exists():
        return
    (KG / rid).mkdir(parents=True)
    for f in ("checkpoint.json", "v4_concepts.json"):
        if (KG / src / f).exists():
            shutil.copy2(KG / src / f, KG / rid / f)
    cp = load_checkpoint(KG / rid)
    cp.relation_results_v3 = []
    cp.stage = "relations"
    save_checkpoint(cp, KG / rid)


def spend() -> dict:
    from cumap.llm.cost import spend_from_log

    st = get_settings()
    per = {
        arm_id(s, a): round(spend_from_log(st, arm_id(s, a)), 4) for s in SB.PD_DEV for a in ARMS
    }
    return {"per_run": per, "total_usd": round(sum(per.values()), 4), "cap_usd": CAP_USD}


def relations(sid: str, arm: str, *, limit: int | None, dry_run: bool, max_usd: float) -> dict:
    from cumap.concepts_v4 import experiments as X
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.pipeline import load_checkpoint
    from cumap.llm.client import LLMClient
    from cumap.schemas.relations import RelationRegistry

    SB.use_unit(SB.pd_base(sid))
    os.environ["CUMAP_MATCHING"] = (
        "r1key"  # the base runs' matching mode (recorded in their selection_stats)
    )
    rid = arm_id(sid, arm)
    _copy(base_id(sid), rid)
    cp = load_checkpoint(KG / rid)
    pre = sr.preflight_relations(cp)
    if dry_run:
        return {"dry_run": True, "run_id": rid, **pre}
    left = CAP_USD - spend()["total_usd"]
    if left <= 0:
        raise SystemExit(f"CR-046 cap reached: ${CAP_USD}")
    settings = get_settings()
    settings.llm.stage_budgets_usd["relations"] = max_usd
    client = LLMClient(settings, run_id=rid)
    cfg = ARMS[arm]
    registry = RelationRegistry.from_yaml(REPO_ROOT / cfg["registry"])
    cp = sr.relations_stage(client, cp, KG / rid, registry, REPO_ROOT / "prompts", X.Embedder(settings.embeddings.model), progress=print, limit=limit, qualifier_checks="v1", qualifier_amendments=cfg["qualifier_amendments"])  # fmt: skip
    return {"run_id": rid, "results": len(cp.relation_results_v3), "pairs": pre["pairs"], "spend_usd": round(client.spent_usd, 4)}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["relations", "spend", "score"])
    ap.add_argument("--arm", choices=sorted(ARMS))
    ap.add_argument("--section", choices=SB.PD_DEV)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=1.0)
    a = ap.parse_args()
    if a.cmd == "spend":
        out = spend()
    elif a.cmd == "score":
        from cumap.cr046.score import main as score

        out = score()
    else:
        out = [
            relations(s, a.arm, limit=a.limit, dry_run=a.dry_run, max_usd=a.max_usd)
            for s in ([a.section] if a.section else SB.PD_DEV)
        ]
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
