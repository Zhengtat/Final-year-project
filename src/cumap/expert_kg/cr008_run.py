"""CR-008 step 3: re-key a finished run ($0) and write snapshots. Usage:
`uv run python -m cumap.expert_kg.cr008_run --run slice3_a1 --new-run slice3_b1`."""

from __future__ import annotations

import argparse
import json

import numpy as np

from cumap.config import REPO_ROOT, get_settings, load_demo_slice
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.pipeline import Checkpoint, save_checkpoint
from cumap.expert_kg.rekey import RekeyResult, rekey_run
from cumap.expert_kg.roles import SectionText
from cumap.expert_kg.slice_rerun import load_sections, snapshots_stage
from cumap.schemas.relations import RelationRegistry

KG_DIR = REPO_ROOT / "data" / "processed" / "kg"


def build_context(cp: dict, sections, lexicon: Lexicon) -> AliasContext:
    forms = [f for c in cp["concepts"] for f in (c["canonical_name"], *c.get("aliases", []))]
    return AliasContext.build(
        lexicon,
        {s.section_id: s.text for s in sections},
        {s.section_id: s.chapter_num for s in sections},
        forms,
    )


def rekey_stage(src_run: str, new_run: str, *, snapshots: bool = True) -> tuple[RekeyResult, dict]:
    settings = get_settings()
    slice_cfg = load_demo_slice()
    sections = load_sections(REPO_ROOT / slice_cfg.pd.source_jsonl, list(slice_cfg.pd.chapters))
    cp_in = json.loads((KG_DIR / src_run / "checkpoint.json").read_text())
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    ctx = build_context(cp_in, sections, Lexicon.load(REPO_ROOT / "configs" / "term_lexicon.yaml"))
    texts = [SectionText(s.section_id, s.chapter_num, i, s.text) for i, s in enumerate(sections)]
    result = rekey_run(cp_in, ctx, registry, texts, new_run)
    run_dir = KG_DIR / new_run
    cp = Checkpoint(**result.checkpoint)
    cp.stage = "snapshots"
    save_checkpoint(cp, run_dir)
    snap = {}
    if snapshots:
        out = snapshots_stage(cp, run_dir, sections, registry, lambda t: np.zeros(1))
        save_checkpoint(cp, run_dir)
        snap = {"chapters": len(out)}
    return result, snap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--new-run", required=True)
    a = ap.parse_args()
    result, _ = rekey_stage(a.run, a.new_run)
    print(json.dumps(result.report, indent=2, default=str))


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- misconception stage (CR-008 §5)
def misconception_stage(run: str, *, dry_run: bool, limit: int | None, max_usd: float) -> dict:
    from cumap.expert_kg import misconception as mc
    from cumap.expert_kg.canonicalize import RegisteredConcept
    from cumap.expert_kg.cr008_sheets import write_misconception_sheet
    from cumap.expert_kg.mentions import MentionMatcher
    from cumap.expert_kg.pipeline import load_checkpoint
    from cumap.expert_kg.relations import CandidatePair, concept_vocab
    from cumap.expert_kg.relations_v3 import classify_pair_v3
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    settings = get_settings()
    slice_cfg = load_demo_slice()
    sections = load_sections(REPO_ROOT / slice_cfg.pd.source_jsonl, list(slice_cfg.pd.chapters))
    pairs = [(s.section_id, s.text) for s in sections]
    run_dir = KG_DIR / run
    cp = load_checkpoint(run_dir)
    assert cp is not None, f"no checkpoint for {run}"
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    lexicon = Lexicon.load(REPO_ROOT / "configs" / "term_lexicon.yaml")
    cands = mc.scan_cues(pairs, lexicon)
    pre = mc.preflight(cands)
    if dry_run:
        return {"dry_run": True, **pre}
    if pre["est_usd"] > max_usd:
        raise SystemExit(f"preflight ${pre['est_usd']} exceeds --max-usd {max_usd}")
    settings.llm.stage_budgets_usd["misconceptions"] = max_usd
    client = LLMClient(settings, run_id=run)
    prompts = REPO_ROOT / "prompts"
    p_fam, p_rel, p_q = (
        load_prompt(prompts, t, v)
        for t, v in (
            ("relation_family", "v3"),
            ("relation_choice", "v4"),
            ("relation_qualifiers", "v3"),
        )
    )
    prompt = load_prompt(prompts, "misconception_structuring", "v2")
    cp_d = {"concepts": cp.concepts, "relation_results_v3": cp.relation_results_v3}
    regs = {
        c["concept_id"]: RegisteredConcept(
            c["concept_id"],
            c["canonical_name"],
            c["node_type"],
            c.get("definition"),
            "",
            list(c.get("aliases", [])),
        )
        for c in cp.concepts
    }
    matcher = MentionMatcher(concept_vocab(list(regs.values())))
    counter = {"n": 0}

    def verify(out, cand):
        """Relation verifier: a fresh classification of the proposed edge on the OTHER tier (bulk)."""
        counter["n"] += 1
        sent = next(
            (
                s
                for s in mc._sentences(cand.paragraph)
                if out.pce_quote and " ".join(out.pce_quote.split()) in " ".join(s.split())
            ),
            cand.sentence,
        )
        pair = CandidatePair(
            f"MP-{counter['n']}", cand.section_id, out.pce_source, out.pce_target, sent
        )
        res = classify_pair_v3(
            client,
            p_fam,
            p_rel,
            p_q,
            registry,
            pair,
            regs[out.pce_source],
            regs[out.pce_target],
            matcher,
            same_concept=True,
            model_tier="bulk",
        )
        if res.outcome != "edge" or res.relation != out.pce_relation:
            return None
        d = res.to_dict()
        d["group"], d["found_by"] = "selected", "misconception_stage"
        return d

    layer = mc.run_stage(client, prompt, registry, cp_d, pairs, lexicon, limit=limit, verify=verify)
    cp.relation_results_v3 = cp_d["relation_results_v3"]
    cp.misconceptions = layer
    # accepted proposed correct edges changed the expert layer: rebuild snapshots (organise is re-run next)
    snapshots_stage(cp, run_dir, sections, registry, lambda t: np.zeros(1))
    save_checkpoint(cp, run_dir)
    edges = mc.expert_edges(cp.relation_results_v3)
    sheet = write_misconception_sheet(
        {"misconceptions": layer}, registry, edges, REPO_ROOT / "data" / "interim" / "checks"
    )
    (run_dir / "misconceptions.jsonl").write_text(
        "\n".join(json.dumps(i) for i in layer["items"]) + "\n", encoding="utf-8"
    )
    return {
        "spend_usd": round(client.spent_usd, 4),
        "backend_calls": client.backend_call_count,
        **layer["stats"],
        "sheet": sheet,
    }
