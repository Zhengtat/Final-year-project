"""CR-048 measurement of the CR-039 misconception family (handoff section 14), pre-registered in docs/DECISIONS.md before any call.

Arm `CUE` (recall and false positives): a copy of `slice3_c2` whose selected pairs are every concept pair co-mentioned in one of
the 89 cue sentences of its legacy misconception stage (`checkpoint.misconceptions.candidate_log`: 4 items, 10 needs-correct-edge,
75 not-a-warning). Arm `PDMISC` (ordinary relations unchanged): the CR-046 P&D development pairs (sections 1.5 / 2.6) with the
misconception family on, compared with `cr046_amend_*` (same pairs, v6, no misconception family).
Both arms: registry v1.6, `qualifier_amendments: v6`, `misconception_source: classification`, `qualifier_checks: v1`, luna profile.

    uv run python -m cumap.cr048.run pairs                          # $0: build the CUE pair set
    uv run python -m cumap.cr048.run relations --arm CUE --dry-run | --limit 20 | (all)
    uv run python -m cumap.cr048.run relations --arm PDMISC
    uv run python -m cumap.cr048.run score
Development data only (P&D chapters 1-3 and dev sections 1.5 / 2.6; rule 9). No gold is read except by the P&D scorer."""

from __future__ import annotations

import argparse
import json
import os
import shutil

from cumap.config import REPO_ROOT, get_settings
from cumap.cr019 import stage_b as SB
from cumap.cr046 import run as R46

CAP_USD = 1.0
KG = REPO_ROOT / "data/processed/kg"
SRC = "slice3_c2"
CUE_RUN = "cr048_cue_slice3_c2"
REGISTRY = "configs/relations_v1.6.yaml"


def pd_id(sid: str) -> str:
    return f"cr048_pdmisc_{SB.pd_base(sid)}"


def run_ids() -> list[str]:
    return [CUE_RUN] + [pd_id(s) for s in SB.PD_DEV]


def _matcher(cp: dict):
    from cumap.expert_kg.canonicalize import RegisteredConcept
    from cumap.expert_kg.mentions import MentionMatcher
    from cumap.expert_kg.relations import concept_vocab

    cs = [
        RegisteredConcept(c["concept_id"], c["canonical_name"], c["node_type"], None, "", list(c.get("aliases", [])))
        for c in cp["concepts"]
    ]  # fmt: skip
    return MentionMatcher(concept_vocab(cs))


def cue_pairs(cp: dict) -> list[dict]:
    """Every unordered concept pair co-mentioned (longest match) in a cue sentence, in candidate-log order."""
    mm = _matcher(cp)
    out, seen = [], set()
    for i, c in enumerate(cp["misconceptions"]["candidate_log"]):
        ids = sorted({m.concept_id for m in mm.find(c["sentence"])})
        for a_i, a in enumerate(ids):
            for b in ids[a_i + 1 :]:
                k = (c["section_id"], a, b, c["sentence"])
                if k in seen:
                    continue
                seen.add(k)
                out.append({"pair_id": f"CUE-{c['section_id']}-{i}-{len(out)}", "section_id": c["section_id"], "concept_x_id": a, "concept_y_id": b,
                            "sentence": c["sentence"], "cooccurrence_count": 1, "cue_score": 1})  # fmt: skip
    return out


def build_cue_run() -> dict:
    from cumap.expert_kg.pipeline import load_checkpoint, save_checkpoint

    if not (KG / CUE_RUN).exists():
        (KG / CUE_RUN).mkdir(parents=True)
        for f in ("checkpoint.json", "v4_concepts.json"):
            shutil.copy2(KG / SRC / f, KG / CUE_RUN / f)
        raw = json.loads((KG / SRC / "checkpoint.json").read_text())
        cp = load_checkpoint(KG / CUE_RUN)
        cp.selected_pairs = cue_pairs(raw)
        cp.sample_pairs, cp.relation_results_v3 = [], []
        cp.stage = "relations"
        save_checkpoint(cp, KG / CUE_RUN)
    cp = json.loads((KG / CUE_RUN / "checkpoint.json").read_text())
    return {
        "run_id": CUE_RUN,
        "pairs": len(cp["selected_pairs"]),
        "sentences": len({p["sentence"] for p in cp["selected_pairs"]}),
    }


def spend() -> dict:
    from cumap.llm.cost import spend_from_log

    st = get_settings()
    per = {r: round(spend_from_log(st, r), 4) for r in run_ids()}
    return {"per_run": per, "total_usd": round(sum(per.values()), 4), "cap_usd": CAP_USD}


def relations(rid: str, *, limit: int | None, dry_run: bool) -> dict:
    from cumap.concepts_v4 import experiments as X
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.pipeline import load_checkpoint
    from cumap.llm.client import LLMClient
    from cumap.schemas.relations import RelationRegistry

    if rid == CUE_RUN:
        os.environ.pop("CUMAP_DEMO_SLICE", None)  # slice3_c2's own slice (the default demo slice)
        os.environ["CUMAP_MATCHING"] = "token"  # slice3_c2 was built with token matching
        build_cue_run()
    else:
        sid = next(s for s in SB.PD_DEV if pd_id(s) == rid)
        SB.use_unit(SB.pd_base(sid))
        os.environ["CUMAP_MATCHING"] = "r1key"
        R46._copy(R46.base_id(sid), rid)
    get_settings.cache_clear()
    cp = load_checkpoint(KG / rid)
    pre = sr.preflight_relations(cp)
    if dry_run:
        return {
            "dry_run": True,
            "run_id": rid,
            **pre,
            "est_usd_luna": round((pre["pairs"] - pre["already_classified"]) * 0.0003, 3),
        }
    if spend()["total_usd"] >= CAP_USD:
        raise SystemExit(f"CR-048 cap reached: ${CAP_USD}")
    settings = get_settings()
    settings.llm.stage_budgets_usd["relations"] = (
        3.0  # sol-era preflight bound; real spend is capped by CAP_USD
    )
    client = LLMClient(settings, run_id=rid)
    registry = RelationRegistry.from_yaml(REPO_ROOT / REGISTRY)
    cp = sr.relations_stage(client, cp, KG / rid, registry, REPO_ROOT / "prompts", X.Embedder(settings.embeddings.model), progress=None, limit=limit,
                            qualifier_checks="v1", qualifier_amendments="v6", misconception_source="classification")  # fmt: skip
    return {
        "run_id": rid,
        "results": len(cp.relation_results_v3),
        "pairs": pre["pairs"],
        "spend_usd": round(client.spent_usd, 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pairs", "relations", "spend", "score"])
    ap.add_argument("--arm", choices=["CUE", "PDMISC"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "pairs":
        out = build_cue_run()
    elif a.cmd == "spend":
        out = spend()
    elif a.cmd == "score":
        from cumap.cr048.score import main as score

        out = score()
    else:
        rids = [CUE_RUN] if a.arm == "CUE" else [pd_id(s) for s in SB.PD_DEV]
        out = [relations(r, limit=a.limit, dry_run=a.dry_run) for r in rids]
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
