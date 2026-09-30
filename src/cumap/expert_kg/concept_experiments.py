"""CR-007 §3.2: concept-extraction v3 experiments E1-E5 on the IIR benchmark.

Every LLM call goes through LLMClient (cache, budget, log). A `Variant` says which optional
blocks of the `v3x` prompt template are on and how runs are aggregated:

  E1 codebook    condensed FACE code-book in our own words (networking examples)
  E2 samples=3   three deliberately varied runs; scored as the union AND as the >= 2-of-3 vote
  E3 propagate   a concept accepted in any section is also tagged, role `mentioned`, source
                 `propagation`, in every other section where a longest-match mention occurs ($0)
  E4 fewshot=k   k worked examples from OTHER dev sections (leave-one-section-out)
  E5 granularity compound terms stay whole; device and process are separate concepts

The baseline `v2` renders the frozen v2 prompt unchanged, so its dev calls are cache hits.
Selection rule (pre-registered in DECISIONS.md before any run): highest lenient micro F1 on dev;
within 0.02 take the simpler variant (fewer calls per section, then fewer components).
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from cumap.expert_kg.concepts import extract_concepts_for_section
from cumap.expert_kg.face_eval import evaluate_mentions
from cumap.expert_kg.face_scorer import GoldConcept, normalize
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.stats import extract_candidate_terms
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

PASS_NOTES = [
    "",
    (
        "Pass 2 of 3: be inclusive of every technical term a student of this section would need "
        "to recognise, including short one-word terms."
    ),
    (
        "Pass 3 of 3: concentrate on the multi-word technical phrases and on named techniques, "
        "algorithms and systems; still include short terms where they are central to the section."
    ),
]
TIE_MARGIN = 0.02


@dataclass(frozen=True)
class Variant:
    name: str
    prompt: str = "v3x"
    codebook: bool = False
    granularity: bool = False
    fewshot: int = 0
    samples: int = 1
    aggregate: str = "single"  # single | union | vote2
    propagate: bool = False

    @property
    def calls_per_section(self) -> int:
        return self.samples

    @property
    def n_components(self) -> int:
        return sum(
            [self.codebook, self.granularity, self.fewshot > 0, self.samples > 1, self.propagate]
        )


BASELINE = Variant("v2", prompt="v2")
SINGLES = [
    Variant("E1", codebook=True),
    Variant("E2-union", samples=3, aggregate="union"),
    Variant("E2-vote2", samples=3, aggregate="vote2"),
    Variant("E3", prompt="v2", propagate=True),
    Variant("E4", fewshot=2),
    Variant("E5", granularity=True),
]


def combine_variants(name: str, parts: list[Variant]) -> Variant:
    """A combination of singles (E3 propagates on top of whatever the prompt is)."""
    kw = {}
    for p in parts:
        kw["codebook"] = kw.get("codebook", False) or p.codebook
        kw["granularity"] = kw.get("granularity", False) or p.granularity
        kw["fewshot"] = max(kw.get("fewshot", 0), p.fewshot)
        kw["propagate"] = kw.get("propagate", False) or p.propagate
        if p.samples > 1:
            kw["samples"], kw["aggregate"] = p.samples, p.aggregate
    return Variant(name, prompt="v3x", **kw)


def select_by_rule(scores: dict[str, float], variants: dict[str, Variant]) -> str:
    """Pre-registered rule: best dev lenient micro F1; candidates within 0.02 of the best are
    tie-broken toward fewer calls per section, then fewer components, then name."""
    best = max(scores.values())
    near = [n for n, v in scores.items() if best - v <= TIE_MARGIN]
    return min(
        near, key=lambda n: (variants[n].calls_per_section, variants[n].n_components, -scores[n], n)
    )


# ---------------------------------------------------------------- prompt pieces
def _read_block(prompts_dir: Path, name: str) -> str:
    return (prompts_dir / "concept_extraction" / "blocks_v3x" / f"{name}.md").read_text().strip()


@dataclass
class FewShot:
    section_id: str
    excerpt: str
    terms: list[str]


def build_fewshot_pool(
    sections: list[dict], gold: list[GoldConcept], *, max_words: int = 110, min_terms: int = 3
) -> list[FewShot]:
    by = {}
    for g in gold:
        by.setdefault(g.section_id, []).append(g)
    pool = []
    for s in sections:
        words = s["text"].split()
        excerpt = " ".join(words[:max_words])
        if "." in excerpt and len(words) > max_words:
            excerpt = excerpt[: excerpt.rfind(".") + 1]
        ex_norm = normalize(excerpt)
        terms = [g.concept for g in by.get(s["section_id"], []) if normalize(g.concept) in ex_norm]
        if len(terms) >= min_terms:
            pool.append(FewShot(s["section_id"], excerpt, terms[:12]))
    return sorted(pool, key=lambda f: (-len(f.terms), f.section_id))


def pick_fewshot(pool: list[FewShot], target_section_id: str, k: int) -> list[FewShot]:
    return [f for f in pool if f.section_id != target_section_id][:k]


def format_fewshot(prompts_dir: Path, examples: list[FewShot]) -> str:
    parts = [_read_block(prompts_dir, "fewshot_intro"), ""]
    for i, e in enumerate(examples, 1):
        parts += [f"Example {i} excerpt:", e.excerpt, f"Terms selected: {'; '.join(e.terms)}", ""]
    return "\n".join(parts) + "\n"


def render_vars(
    variant: Variant, run_index: int, prompts_dir: Path, examples: list[FewShot]
) -> dict:
    if variant.prompt == "v2":
        return {}
    note = PASS_NOTES[run_index] if variant.samples > 1 else ""
    return {
        "codebook_block": (_read_block(prompts_dir, "codebook") + "\n\n")
        if variant.codebook
        else "",
        "granularity_block": (_read_block(prompts_dir, "granularity") + "\n\n")
        if variant.granularity
        else "",
        "few_shot_block": format_fewshot(prompts_dir, examples) if variant.fewshot else "",
        "pass_note": f"\n{note}\n" if note else "",
    }


# ---------------------------------------------------------------- aggregation
def aggregate_runs(runs: list[list[dict]], mode: str) -> list[dict]:
    """Union of runs, or names found in >= 2 runs; first run's mention (then run order) is kept."""
    if mode == "single":
        return list(runs[0])
    seen: dict[str, dict] = {}
    votes: dict[str, int] = {}
    for run in runs:
        for name in {m["canonical_name"].lower() for m in run}:
            votes[name] = votes.get(name, 0) + 1
        for m in run:
            seen.setdefault(m["canonical_name"].lower(), m)
    need = 2 if mode == "vote2" else 1
    return [m for k, m in seen.items() if votes[k] >= need]


def propagate(final: dict[str, list[dict]], texts: dict[str, str]) -> dict[str, list[dict]]:
    """E3: tag every accepted concept in each other section where a longest-match mention occurs."""
    names = {m["canonical_name"].lower(): m["canonical_name"] for ms in final.values() for m in ms}
    matcher = MentionMatcher({k: k for k in names})
    out: dict[str, list[dict]] = {}
    for sid, ms in final.items():
        have = {m["canonical_name"].lower() for m in ms}
        extra, seen = [], set(have)
        for hit in matcher.find(texts[sid]):
            key = hit.concept_id
            if key in seen:
                continue
            seen.add(key)
            extra.append(
                {
                    "canonical_name": names[key],
                    "node_type": "Concept",
                    "role": "mentioned",
                    "definition": None,
                    "evidence_quote": hit.surface,
                    "section_id": sid,
                    "run_index": 0,
                    "source": "propagation",
                }
            )
        out[sid] = ms + extra
    return out


# ---------------------------------------------------------------- run + score
@dataclass
class VariantResult:
    variant: Variant
    runs: dict[str, list[list[dict]]] = field(default_factory=dict)  # sid -> per-run mentions
    final: dict[str, list[dict]] = field(default_factory=dict)
    rejected: list[dict] = field(default_factory=list)


def run_variant(
    client: LLMClient,
    variant: Variant,
    sections: list[dict],
    *,
    nlp,
    registry: RelationRegistry,
    prompts_dir: Path,
    domain: str = "information retrieval",
    fewshot_pool: list[FewShot] | None = None,
    fixture_name: str = "default",
    progress=None,
) -> VariantResult:
    prompt = load_prompt(prompts_dir, "concept_extraction", variant.prompt)
    res = VariantResult(variant)
    for i, s in enumerate(sections):
        cands = extract_candidate_terms(s["text"], nlp)
        examples = pick_fewshot(fewshot_pool or [], s["section_id"], variant.fewshot)
        runs = []
        for r in range(variant.samples):
            terms = list(cands)
            if r > 0:
                random.Random(f"{s['section_id']}:{r}").shuffle(terms)
            out = extract_concepts_for_section(
                client,
                prompt,
                None,
                registry,
                section_id=s["section_id"],
                section_text=s["text"],
                heading_path=s["heading_path"],
                candidate_terms=terms,
                domain=domain,
                fixture_name=fixture_name,
                include_gleaning=False,
                extra_vars=render_vars(variant, r, prompts_dir, examples) or None,
            )
            runs.append([{**asdict(m), "source": "llm"} for m in out.mentions])
            res.rejected += out.rejected
        res.runs[s["section_id"]] = runs
        res.final[s["section_id"]] = aggregate_runs(runs, variant.aggregate)
        if progress:
            progress(f"{variant.name}: section {i + 1}/{len(sections)}")
    if variant.propagate:
        res.final = propagate(res.final, {s["section_id"]: s["text"] for s in sections})
    return res


def score(
    result: VariantResult, gold: list[GoldConcept], texts: dict[str, str], *, nlp, embed_fn
) -> dict:
    ev = evaluate_mentions(result.final, gold, texts, nlp=nlp, embed_fn=embed_fn)
    m = ev["metrics"]
    return {
        "variant": result.variant.name,
        "n_predicted": m["n_predicted"],
        "n_gold": m["n_gold"],
        "exact_micro": m["exact"]["micro"],
        "lenient_micro": m["lenient"]["micro"],
        "exact_macro": m["exact"]["macro"],
        "lenient_macro": m["lenient"]["macro"],
        "recall_by_ngram": m["recall_by_ngram"]["lenient"],
        "precision_by_role": m["precision_by_role"],
        "calls_per_section": result.variant.calls_per_section,
    }


def save_result(out_dir: Path, result: VariantResult, scores: dict | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.variant.name}.json"
    path.write_text(
        json.dumps(
            {
                "variant": asdict(result.variant),
                "runs": result.runs,
                "final": result.final,
                "rejected": result.rejected,
                "scores": scores,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return path


def with_name(v: Variant, name: str) -> Variant:
    return replace(v, name=name)
