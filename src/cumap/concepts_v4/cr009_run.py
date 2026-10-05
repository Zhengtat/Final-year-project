"""CR-009 §8: the P&D ch. 1-3 re-run, stage by stage, each with a preflight. A new `run_id`; the CR-007 and CR-008 runs
are kept. `uv run python -m cumap.concepts_v4.cr009_run concepts --run slice3_c1 [--dry-run] [--limit-units N]`, then
`select`, `relations`, `snapshots`. Relations use prompts relation_family v3 / relation_choice v4 / relation_qualifiers
v4 (registry v1.3); anchors only set pair priority."""

from __future__ import annotations

import argparse
import json

import spacy

from cumap.concepts_v4 import experiments as X
from cumap.concepts_v4 import pd_run as P
from cumap.concepts_v4 import runner as R
from cumap.concepts_v4.bank import load as load_bank
from cumap.config import REPO_ROOT, get_settings, load_demo_slice
from cumap.expert_kg import slice_rerun as sr
from cumap.expert_kg.canonicalize import CanonicalOverrides
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.pipeline import load_checkpoint, save_checkpoint
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

KG = REPO_ROOT / "data" / "processed" / "kg"


def stage_concepts(
    run: str,
    *,
    dry_run: bool,
    limit_units: int | None,
    max_usd: float,
    tau: float = 0.1,
    strict_g_links: bool = False,
) -> dict:
    settings = get_settings()
    slice_cfg = load_demo_slice()
    sections = sr.load_sections(REPO_ROOT / slice_cfg.pd.source_jsonl, list(slice_cfg.pd.chapters))
    raw = [
        {
            "section_id": s.section_id,
            "chapter_num": s.chapter_num,
            "order_index": i,
            "text": s.text,
            "heading_path": s.heading_path,
        }
        for i, s in enumerate(sections)
    ]
    units = P.make_units(raw)
    if limit_units:
        units = units[:limit_units]
    words = sum(len(u["text"].split()) for u in units)
    est = X.preflight(units, "G1", 1)
    est["usd_expected"] = round(
        est["usd_expected"] * 1.6, 3
    )  # P&D sections are longer than IIR dev's; chunks <= 2,500 words
    est["usd_worst"] = round(est["usd_worst"] * 2.0, 3)
    info = {"units": len(units), "sections": len(sections), "words": words, "preflight": est}
    if dry_run:
        return {"dry_run": True, **info}
    if est["usd_worst"] > max_usd:
        raise SystemExit(f"preflight worst case ${est['usd_worst']} exceeds --max-usd {max_usd}")
    nlp = spacy.load("en_core_web_sm")
    embed = X.Embedder(settings.embeddings.model)
    lexicon = Lexicon.load(REPO_ROOT / "configs" / "term_lexicon.yaml")
    dev_secs, _ = X.load_dev()
    pruners = X.loco_pruners(
        dev_secs, nlp, embed
    )  # IIR dev rows only; P&D is out of domain, so tau is recall-safe
    client = LLMClient(settings, run_id=run)
    run_obj = R.ConceptRun(
        client,
        load_prompt(REPO_ROOT / "prompts", "concept_generator", "v4"),
        load_bank(),
        X.loop_config("G1", 1),
        nlp=nlp,
        embed_fn=embed,
        lexicon=lexicon,
        domain="computer networking",
        backfill_prompt=load_prompt(REPO_ROOT / "prompts", "concept_backfill", "v1"),
        pruner_for=lambda ch: pruners["all"].p_growing,
        tau=tau,
        rho=1.5,
        strict_g_links=strict_g_links,
        progress=print,
    )
    out = run_obj.run(units)
    run_dir = KG / run
    X.save_run(
        out,
        run_dir / "v4_concepts.json",
        {"units": len(units), "spend_usd": round(client.spent_usd, 4)},
    )
    overrides = CanonicalOverrides.load(REPO_ROOT / "configs" / "canonical_overrides.yaml")
    res = P.canonicalise(
        out,
        units,
        lexicon,
        client,
        load_prompt(REPO_ROOT / "prompts", "canonicalize", "v2"),
        embed,
        overrides,
    )
    texts = {}
    for u in units:
        texts[u["orig_section"]] = (texts.get(u["orig_section"], "") + "\n\n" + u["text"]).strip()
    cp = P.build_checkpoint(run, out, res, units, texts)
    sr.finish_concepts(cp, sections, embed)  # first occurrence (longest match) and role rules
    cp.stage = "pairs_enumerated"
    save_checkpoint(cp, run_dir)
    return {
        **info,
        "v4_nodes": len(out.store.nodes),
        "concepts": len(cp.concepts),
        "anchors": len(cp.anchors),
        "canonicalise_llm_calls": res.llm_calls,
        "pruned": len(out.pruned),
        "spend_usd": round(client.spent_usd, 4),
    }


def stage_select(run: str, budget: int) -> dict:
    settings = get_settings()
    slice_cfg = load_demo_slice()
    sections = sr.load_sections(REPO_ROOT / slice_cfg.pd.source_jsonl, list(slice_cfg.pd.chapters))
    run_dir = KG / run
    cp = load_checkpoint(run_dir)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    embed = X.Embedder(settings.embeddings.model)
    stats = sr.select_stage(cp, sections, registry, embed, budget=budget, use_anchors=True)
    cp.stage = "relations"
    save_checkpoint(cp, run_dir)
    return {**stats, **sr.preflight_relations(cp)}


def stage_relations(run: str, *, dry_run: bool, max_usd: float) -> dict:
    settings = get_settings()
    run_dir = KG / run
    cp = load_checkpoint(run_dir)
    pre = sr.preflight_relations(cp)
    if dry_run:
        return {"dry_run": True, **pre}
    if pre["est_usd_upper"] > max_usd:
        raise SystemExit(
            f"preflight upper bound ${pre['est_usd_upper']:.2f} exceeds --max-usd {max_usd}"
        )
    settings.llm.stage_budgets_usd["relations"] = max_usd
    client = LLMClient(settings, run_id=run)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    embed = X.Embedder(settings.embeddings.model)
    cp = sr.relations_stage(
        client, cp, run_dir, registry, REPO_ROOT / "prompts", embed, progress=print
    )
    return {"results": len(cp.relation_results_v3), "spend_usd": round(client.spent_usd, 4)}


def stage_snapshots(run: str) -> dict:
    import numpy as np

    settings = get_settings()
    slice_cfg = load_demo_slice()
    sections = sr.load_sections(REPO_ROOT / slice_cfg.pd.source_jsonl, list(slice_cfg.pd.chapters))
    run_dir = KG / run
    cp = load_checkpoint(run_dir)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    dropped = sr.mark_gated_dropped(cp, registry)
    out = sr.snapshots_stage(cp, run_dir, sections, registry, lambda t: np.zeros(1))
    save_checkpoint(cp, run_dir)
    return {
        "gated_dropped": dropped,
        "chapters": [(r.chapter_num, len(r.snapshot.nodes), len(r.snapshot.edges)) for r in out],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["concepts", "select", "relations", "snapshots"])
    ap.add_argument("--run", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit-units", type=int)
    ap.add_argument("--max-usd", type=float, default=15.0)
    ap.add_argument("--budget", type=int, default=700)
    ap.add_argument("--tau", type=float, default=0.1)
    ap.add_argument("--strict-g-links", action="store_true")
    a = ap.parse_args()
    if a.stage == "concepts":
        r = stage_concepts(
            a.run,
            dry_run=a.dry_run,
            limit_units=a.limit_units,
            max_usd=a.max_usd,
            tau=a.tau,
            strict_g_links=a.strict_g_links,
        )
    elif a.stage == "select":
        r = stage_select(a.run, a.budget)
    elif a.stage == "relations":
        r = stage_relations(a.run, dry_run=a.dry_run, max_usd=a.max_usd)
    else:
        r = stage_snapshots(a.run)
    print(json.dumps(r, indent=1, default=str))


if __name__ == "__main__":
    main()
