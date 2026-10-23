"""Runner for the CR-007 §3.2 IIR ablation: dry-run estimate, --limit, budget-capped real runs,
results and scores under data/processed/ablation/<run_id>/. Dev split (chapters 1-3, FACE text) for
the ablation; the test split is run ONCE per prompt version afterwards (CLAUDE.md rule 9)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from cumap.expert_kg.concept_experiments import (
    BASELINE,
    SINGLES,
    Variant,
    build_fewshot_pool,
    run_variant,
    save_result,
    score,
    with_name,
)
from cumap.expert_kg.face_scorer import GoldConcept, load_gold_concepts
from cumap.llm.client import LLMClient

BULK_IN, BULK_OUT = 0.10, 0.50  # USD per 1M tokens, bulk tier (configs/default.yaml)
BASE_PROMPT_TOKENS = 700
BLOCK_TOKENS = {"codebook": 380, "granularity": 90}
FEWSHOT_TOKENS_PER_EXAMPLE = 210
OUT_TOKENS = 1000


@dataclass
class Plan:
    variant: str
    sections: int
    calls: int
    est_input_tokens: int
    est_usd: float


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def plan_variant(variant: Variant, sections: list[dict]) -> Plan:
    calls = len(sections) * variant.samples
    per_call_extra = (
        BLOCK_TOKENS["codebook"] * variant.codebook
        + BLOCK_TOKENS["granularity"] * variant.granularity
        + FEWSHOT_TOKENS_PER_EXAMPLE * variant.fewshot
    )
    tokens = (
        sum(
            BASE_PROMPT_TOKENS + per_call_extra + round(len(s["text"].split()) * 1.35)
            for s in sections
        )
        * variant.samples
    )
    usd = tokens * BULK_IN / 1e6 + calls * OUT_TOKENS * BULK_OUT / 1e6
    return Plan(variant.name, len(sections), calls, tokens, usd)


def load_split(root: Path, split: str) -> tuple[list[dict], list[GoldConcept]]:
    ext = root / "data" / "interim" / "external"
    if split == "dev":
        return _read_jsonl(ext / "iir_sections.jsonl"), load_gold_concepts(
            ext / "iir_gold_concepts.csv"
        )
    sections = _read_jsonl(ext / "iir_test_sections_v3.jsonl")
    return sections, load_gold_concepts(ext / "iir_test_gold_concepts_v3.csv")


def default_variants() -> list[Variant]:
    return [BASELINE, *SINGLES]


def run_ablation(
    client: LLMClient,
    variants: list[Variant],
    sections: list[dict],
    gold: list[GoldConcept],
    *,
    root: Path,
    registry,
    nlp,
    embed_fn,
    prompts_dir: Path,
    fewshot_source: tuple[list[dict], list[GoldConcept]] | None = None,
    out_name: str | None = None,
    progress=None,
) -> dict[str, dict]:
    out_dir = root / "data" / "processed" / "ablation" / (out_name or client.run_id)
    texts = {s["section_id"]: s["text"] for s in sections}
    pool_secs, pool_gold = fewshot_source or (sections, gold)
    pool = build_fewshot_pool(pool_secs, pool_gold)
    scores: dict[str, dict] = {}
    for v in variants:
        res = run_variant(
            client,
            v,
            sections,
            nlp=nlp,
            registry=registry,
            prompts_dir=prompts_dir,
            fewshot_pool=pool,
            progress=progress,
        )
        scores[v.name] = score(res, gold, texts, nlp=nlp, embed_fn=embed_fn)
        save_result(out_dir, res, scores[v.name])
        if progress:
            s = scores[v.name]
            progress(
                f"{v.name}: lenient micro F1 {s['lenient_micro']['f1']:.3f}, exact {s['exact_micro']['f1']:.3f}, "
                f"spend ${client.spent_usd:.4f}"
            )
    (out_dir / "scores.json").write_text(json.dumps(scores, indent=1), encoding="utf-8")
    return scores


def new_run_id(prefix: str = "abl") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


__all__ = [
    "Plan",
    "default_variants",
    "load_split",
    "new_run_id",
    "plan_variant",
    "run_ablation",
    "with_name",
]
