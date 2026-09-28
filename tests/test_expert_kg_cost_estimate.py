"""CR-005 §2 step 3 test: the cost-estimate arithmetic itself, on a tiny known
scenario -- confirms tier prices, reasoning-as-output, and the pairs-per-section
assumption all actually flow through to the totals, not just that it runs.
"""

from __future__ import annotations

import json

from cumap.expert_kg.cost_estimate import (
    CallAssumptions,
    SectionGroupStats,
    estimate_slice_cost,
    spend_for_run,
)


def test_estimate_slice_cost_toy_scenario(tmp_settings):
    tmp_settings.llm.tiers["bulk"].usd_per_1m_input_tokens = 1.0
    tmp_settings.llm.tiers["bulk"].usd_per_1m_output_tokens = 2.0
    tmp_settings.llm.tiers["strong"].usd_per_1m_input_tokens = 10.0
    tmp_settings.llm.tiers["strong"].usd_per_1m_output_tokens = 20.0

    group = SectionGroupStats(name="toy", section_count=1, total_words=1000)  # 1300 tokens/section
    assumptions = CallAssumptions(
        concepts_per_section=10.0,
        gleaning_new_concept_fraction=0.0,  # isolate the main pass for this check
        concept_extraction_prompt_overhead_tokens=0,
        tokens_per_concept_output=10,
        concept_extraction_reasoning_tokens=0,
        canonicalize_llm_call_fraction=0.0,  # isolate concept-extraction cost first
        candidate_pairs_per_section=0.0,  # isolate concept-extraction cost first
    )

    estimate = estimate_slice_cost(tmp_settings, group, assumptions)
    concept_task = next(t for t in estimate.by_task if t.task == "concept_extraction")

    assert concept_task.calls == 1
    assert concept_task.input_tokens == 1300  # 0 overhead + 1000 words * 1.3
    assert concept_task.output_tokens == 100  # 10 concepts * 10 tokens, 0 reasoning
    # bulk: $1/1M in, $2/1M out -> 1300/1e6*1 + 100/1e6*2 = 0.0013 + 0.0002
    assert abs(concept_task.usd - 0.0015) < 1e-9
    assert concept_task.tier == "bulk"


def test_estimate_slice_cost_reasoning_tokens_count_as_output(tmp_settings):
    tmp_settings.llm.tiers["strong"].usd_per_1m_input_tokens = 10.0
    tmp_settings.llm.tiers["strong"].usd_per_1m_output_tokens = 20.0

    group = SectionGroupStats(name="toy", section_count=1, total_words=0)
    assumptions = CallAssumptions(
        concepts_per_section=0.0,
        gleaning_new_concept_fraction=0.0,
        canonicalize_llm_call_fraction=0.0,
        candidate_pairs_per_section=1.0,
        relation_family_input_tokens=100,
        relation_family_output_tokens=0,
        relation_family_reasoning_tokens=500,  # all of this call's output is reasoning
        fraction_reaching_relation_choice=0.0,
        fraction_reaching_qualifiers=0.0,
    )

    estimate = estimate_slice_cost(tmp_settings, group, assumptions)
    family_task = next(t for t in estimate.by_task if t.task == "relation_family")
    assert family_task.output_tokens == 500  # reasoning_tokens alone, output_tokens field is 0
    # 100/1e6*10 + 500/1e6*20 = 0.001 + 0.01
    assert abs(family_task.usd - 0.011) < 1e-9


def test_estimate_slice_cost_pairs_per_section_scales_relation_calls(tmp_settings):
    tmp_settings.llm.tiers["strong"].usd_per_1m_input_tokens = 1.0
    tmp_settings.llm.tiers["strong"].usd_per_1m_output_tokens = 1.0

    group = SectionGroupStats(name="toy", section_count=3, total_words=0)
    assumptions = CallAssumptions(
        concepts_per_section=0.0,
        gleaning_new_concept_fraction=0.0,
        canonicalize_llm_call_fraction=0.0,
        candidate_pairs_per_section=5.0,
        fraction_reaching_relation_choice=1.0,
        fraction_reaching_qualifiers=1.0,
    )

    estimate = estimate_slice_cost(tmp_settings, group, assumptions)
    family_task = next(t for t in estimate.by_task if t.task == "relation_family")
    choice_task = next(t for t in estimate.by_task if t.task == "relation_choice")
    qualifiers_task = next(t for t in estimate.by_task if t.task == "relation_qualifiers")

    assert family_task.calls == 15  # 3 sections * 5 pairs
    assert choice_task.calls == 15
    assert qualifiers_task.calls == 15


def test_estimate_slice_cost_raises_on_unpriced_tier(tmp_settings):
    tmp_settings.llm.tiers["bulk"].usd_per_1m_input_tokens = None
    group = SectionGroupStats(name="toy", section_count=1, total_words=100)
    try:
        estimate_slice_cost(tmp_settings, group, CallAssumptions())
        raised = False
    except ValueError:
        raised = True
    assert raised


def _write_log(path, rows):
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_spend_for_run_sums_only_this_runs_cache_misses(tmp_settings, tmp_path):
    tmp_settings.llm.tiers["bulk"].usd_per_1m_input_tokens = 1.0
    tmp_settings.llm.tiers["bulk"].usd_per_1m_output_tokens = 2.0
    log_path = tmp_path / "llm_calls.jsonl"
    _write_log(
        log_path,
        [
            {
                "run_id": "run_a",
                "cache_hit": False,
                "model_tier": "bulk",
                "usage": {"input_tokens": 1000, "output_tokens": 500},
            },
            {
                "run_id": "run_a",
                "cache_hit": True,
                "model_tier": "bulk",
                "usage": {"input_tokens": 999999, "output_tokens": 999999},
            },
            {
                "run_id": "run_b",
                "cache_hit": False,
                "model_tier": "bulk",
                "usage": {"input_tokens": 1000, "output_tokens": 500},
            },
        ],
    )

    spend = spend_for_run(tmp_settings, "run_a", log_path=log_path)
    # 1000/1e6*1 + 500/1e6*2 = 0.001 + 0.001
    assert abs(spend - 0.002) < 1e-9


def test_spend_for_run_zero_when_log_missing(tmp_settings, tmp_path):
    spend = spend_for_run(tmp_settings, "run_a", log_path=tmp_path / "nonexistent.jsonl")
    assert spend == 0.0


def test_spend_for_run_skips_unpriced_tiers(tmp_settings, tmp_path):
    tmp_settings.llm.tiers["ceiling"].usd_per_1m_input_tokens = None
    log_path = tmp_path / "llm_calls.jsonl"
    _write_log(
        log_path,
        [
            {
                "run_id": "run_a",
                "cache_hit": False,
                "model_tier": "ceiling",
                "usage": {"input_tokens": 1000, "output_tokens": 500},
            }
        ],
    )
    assert spend_for_run(tmp_settings, "run_a", log_path=log_path) == 0.0
