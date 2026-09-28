"""CR-005 §2 step 3: cost estimate for the M5 demo slice (concept extraction +
canonicalisation + relation extraction), built from per-task token/call assumptions
and the configured per-tier prices (configs/default.yaml `llm.tiers.*`).

Every assumed quantity below Step 4's calibration run is a named, documented
`CallAssumptions` field -- nothing is a hidden constant. Once the calibration run
(1 IIR section + 1 P&D section, real API) gives measured tokens-per-call, replace the
relevant defaults and re-run `estimate_slice_cost` rather than trusting these numbers
as final. Reasoning tokens are counted as output tokens throughout (CR-005 step 3:
"count reasoning tokens as output"), matching how OpenAI actually bills them
(`response.usage.output_tokens` already includes reasoning; see llm/client.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cumap.config import Settings

WORDS_TO_TOKENS = 1.3  # rough ratio for English technical prose


@dataclass
class SectionGroupStats:
    name: str
    section_count: int
    total_words: int

    @property
    def avg_tokens_per_section(self) -> float:
        return (self.total_words / self.section_count) * WORDS_TO_TOKENS


@dataclass
class CallAssumptions:
    """Defaults are order-of-magnitude judgement calls (registry option-list sizes,
    typical structured-output verbosity), not measurements. Step 4 replaces them.
    """

    # concept extraction (bulk tier)
    concepts_per_section: float = 30.0
    gleaning_new_concept_fraction: float = 0.2
    concept_extraction_prompt_overhead_tokens: int = 550
    tokens_per_concept_output: int = 55
    concept_extraction_reasoning_tokens: int = 300

    # canonicalisation (strong tier -- corrected from bulk, see DECISIONS.md)
    canonicalize_llm_call_fraction: float = 0.4  # share of concepts above the similarity threshold
    canonicalize_input_tokens: int = 450
    canonicalize_output_tokens: int = 60
    canonicalize_reasoning_tokens: int = 400

    # relations (strong tier). candidate_pairs_per_section is the number CR-005 step 3
    # explicitly asks to show -- Step 5's stop condition is "> ~60 candidate pairs per
    # section", so this default is deliberately picked well under that line.
    candidate_pairs_per_section: float = 20.0
    relation_family_input_tokens: int = 350
    relation_family_output_tokens: int = 30
    relation_family_reasoning_tokens: int = 350
    relation_choice_input_tokens: int = 550  # includes the relation_options block (near-misses)
    relation_choice_output_tokens: int = 60
    relation_choice_reasoning_tokens: int = 400
    relation_qualifiers_input_tokens: int = 400
    relation_qualifiers_output_tokens: int = 50
    relation_qualifiers_reasoning_tokens: int = 300
    # Every pair gets a family call; only pairs that clear family + relation reach the
    # qualifier pass (family != no_relation/other, relation != other).
    fraction_reaching_relation_choice: float = 0.7
    fraction_reaching_qualifiers: float = 0.55


@dataclass
class TaskCost:
    task: str
    tier: str
    calls: float
    input_tokens: float
    output_tokens: float  # includes reasoning tokens
    usd: float


@dataclass
class SliceCostEstimate:
    group_name: str
    by_task: list[TaskCost] = field(default_factory=list)

    @property
    def total_usd(self) -> float:
        return sum(t.usd for t in self.by_task)


def _tier_price(settings: Settings, tier: str) -> tuple[float, float]:
    cfg = settings.llm.tiers[tier]
    if cfg.usd_per_1m_input_tokens is None or cfg.usd_per_1m_output_tokens is None:
        raise ValueError(
            f"tier {tier!r} ({cfg.model}) has no configured price yet -- can't estimate its cost"
        )
    return cfg.usd_per_1m_input_tokens, cfg.usd_per_1m_output_tokens


def _task_cost(
    task: str,
    tier: str,
    calls: float,
    input_tokens_per_call: float,
    output_tokens_per_call: float,
    price_in: float,
    price_out: float,
) -> TaskCost:
    input_tokens = calls * input_tokens_per_call
    output_tokens = calls * output_tokens_per_call
    usd = input_tokens / 1_000_000 * price_in + output_tokens / 1_000_000 * price_out
    return TaskCost(
        task=task,
        tier=tier,
        calls=calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usd=usd,
    )


def estimate_slice_cost(
    settings: Settings, group: SectionGroupStats, a: CallAssumptions
) -> SliceCostEstimate:
    bulk_in, bulk_out = _tier_price(settings, "bulk")
    strong_in, strong_out = _tier_price(settings, "strong")

    n = group.section_count
    section_tokens = group.avg_tokens_per_section
    concepts = a.concepts_per_section
    pairs = a.candidate_pairs_per_section

    tasks = [
        _task_cost(
            "concept_extraction",
            "bulk",
            n,
            a.concept_extraction_prompt_overhead_tokens + section_tokens,
            concepts * a.tokens_per_concept_output + a.concept_extraction_reasoning_tokens,
            bulk_in,
            bulk_out,
        ),
        _task_cost(
            "concept_extraction_gleaning",
            "bulk",
            n,
            a.concept_extraction_prompt_overhead_tokens
            + section_tokens
            + concepts * 5,  # already_found list
            concepts * a.gleaning_new_concept_fraction * a.tokens_per_concept_output
            + a.concept_extraction_reasoning_tokens,
            bulk_in,
            bulk_out,
        ),
        _task_cost(
            "canonicalize",
            "strong",
            n * concepts * (1 + a.gleaning_new_concept_fraction) * a.canonicalize_llm_call_fraction,
            a.canonicalize_input_tokens,
            a.canonicalize_output_tokens + a.canonicalize_reasoning_tokens,
            strong_in,
            strong_out,
        ),
        _task_cost(
            "relation_family",
            "strong",
            n * pairs,
            a.relation_family_input_tokens,
            a.relation_family_output_tokens + a.relation_family_reasoning_tokens,
            strong_in,
            strong_out,
        ),
        _task_cost(
            "relation_choice",
            "strong",
            n * pairs * a.fraction_reaching_relation_choice,
            a.relation_choice_input_tokens,
            a.relation_choice_output_tokens + a.relation_choice_reasoning_tokens,
            strong_in,
            strong_out,
        ),
        _task_cost(
            "relation_qualifiers",
            "strong",
            n * pairs * a.fraction_reaching_qualifiers,
            a.relation_qualifiers_input_tokens,
            a.relation_qualifiers_output_tokens + a.relation_qualifiers_reasoning_tokens,
            strong_in,
            strong_out,
        ),
    ]
    return SliceCostEstimate(group_name=group.name, by_task=tasks)
