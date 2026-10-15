"""CR-012 E0 for ONE evaluation unit (a P&D-E2E section): the frozen production workflow, run as its own one-section slice with a fresh run
id. Recipe = the CR-009 final production run (`slice3_c2`): concept stage with the pruner off (tau 0) and strict G-links, online canonicalisation
(prompt canonicalize v2, type-aware, 0.70 review band as in S0), anchor-first pair selection, relation stage (family v3 / choice v4 / qualifiers v4,
registry v1.3). The ONLY evaluation-specific input is the pair budget, set by the approved D3 rule B(u) = min(pool, max(1, ceil(14.2 * words / 1000))).
Nothing here reads gold.

    uv run python -m cumap.cr012.unit_run prepare --section 2.6
    uv run python -m cumap.cr012.unit_run run --section 2.6 --tag pilot --dry-run
    uv run python -m cumap.cr012.unit_run run --section 2.6 --tag pilot --max-usd 2
"""

from __future__ import annotations

import argparse
import json
import math
import os

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012.budget import pair_budget
from cumap.cr012.pd_e2e import SECTIONS, load_sections

UNITS = REPO_ROOT / "data/interim/cr012/units"
RECIPE = {"tau": 0.0, "strict_g_links": True, "anchors": True, "reference_run": "slice3_c2"}


def prepare(section_id: str) -> dict:
    rows = [r for r in load_sections() if r["section_id"] == section_id]
    assert len(rows) == 1, f"unknown section {section_id}"
    row = rows[0]
    d = UNITS / section_id
    d.mkdir(parents=True, exist_ok=True)
    src = d / "sections.jsonl"
    src.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    base = yaml.safe_load((REPO_ROOT / "configs/demo_slice.yaml").read_text())
    base["pd"]["source_jsonl"] = str(src.relative_to(REPO_ROOT))
    base["pd"]["chapters"] = [row["chapter_num"]]
    cfg = d / "slice.yaml"
    cfg.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")
    words = len(row["text"].split())
    return {
        "section": section_id,
        "slice_config": str(cfg),
        "words": words,
        "source_corpus": str(SECTIONS.relative_to(REPO_ROOT)),
    }


def select_without_sample(run_id: str, budget: int) -> dict:
    """The production selection step with the 50-pair unselected measurement sample switched off. The sample is classified but never
    enters the graph (group `sample`), so it only costs money; the SELECTED pairs are identical (checked by a test)."""
    from cumap.concepts_v4 import experiments as X
    from cumap.config import get_settings, load_demo_slice
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.pipeline import load_checkpoint, save_checkpoint
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    from cumap.expert_kg.mentions import use_production_matching

    use_production_matching()  # CR-020
    cfg = load_demo_slice()
    sections = sr.load_sections(REPO_ROOT / cfg.pd.source_jsonl, list(cfg.pd.chapters))
    run_dir = REPO_ROOT / "data/processed/kg" / run_id
    cp = load_checkpoint(run_dir)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    embed = X.Embedder(settings.embeddings.model)
    stats = sr.select_stage(
        cp, sections, registry, embed, budget=budget, sample=0, use_anchors=True
    )
    cp.stage = "relations"
    save_checkpoint(cp, run_dir)
    return {**stats, **sr.preflight_relations(cp)}


def run(section_id: str, tag: str, *, dry_run: bool, max_usd: float) -> dict:
    from cumap.concepts_v4 import cr009_run as R

    info = prepare(section_id)
    os.environ["CUMAP_DEMO_SLICE"] = info["slice_config"]
    run_id = f"cr012_{tag}_{section_id.replace('.', '_')}_E0"
    out: dict = {"run_id": run_id, "recipe": RECIPE, **info}
    c = R.stage_concepts(
        run_id,
        dry_run=dry_run,
        limit_units=None,
        max_usd=max_usd,
        tau=RECIPE["tau"],
        strict_g_links=RECIPE["strict_g_links"],
    )
    out["concepts"] = c
    if dry_run:
        out["pair_budget_if_pool_unbounded"] = math.ceil(14.2 * info["words"] / 1000)
        return out
    budget = math.ceil(
        14.2 * info["words"] / 1000
    )  # the pool cap is applied by the selector (it cannot select more than exist)
    sel = select_without_sample(run_id, budget)
    pool = sel.get("unique_candidate_pairs", 0)
    b = pair_budget(info["words"], pool)
    if b != budget:  # re-select with the capped budget so the logged number is the D3 number
        sel = select_without_sample(run_id, b)
    out["select"] = sel
    out["budget_record"] = {
        "word_count": info["words"],
        "eligible_candidate_pairs": pool,
        "budget": b,
        "selected_pairs": sel.get("selected"),
        "budget_saturated": (sel.get("selected") or 0) >= b,
    }
    out["relations"] = R.stage_relations(run_id, dry_run=False, max_usd=max_usd)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["prepare", "run"])
    ap.add_argument("--section", required=True)
    ap.add_argument("--tag", default="pilot")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=2.0)
    a = ap.parse_args()
    res = (
        prepare(a.section)
        if a.phase == "prepare"
        else run(a.section, a.tag, dry_run=a.dry_run, max_usd=a.max_usd)
    )
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
