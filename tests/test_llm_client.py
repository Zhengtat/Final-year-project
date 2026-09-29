from __future__ import annotations

import pytest
from pydantic import BaseModel

from cumap.llm.client import BudgetExceededError, LLMClient


class ConceptList(BaseModel):
    concepts: list[dict]


def test_mock_parse_returns_validated_object(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)

    result = client.parse(
        task="concept_extraction",
        prompt_version="v1",
        messages=[{"role": "user", "content": "extract concepts from section 6.3"}],
        schema=ConceptList,
        model_tier="strong",
    )

    assert isinstance(result.output, ConceptList)
    assert result.output.concepts[0]["canonical_name"] == "slow start"
    assert result.cache_hit is False
    assert client.backend_call_count == 1


def test_second_identical_call_is_a_cache_hit(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    messages = [{"role": "user", "content": "extract concepts from section 6.3"}]

    first = client.parse(
        task="concept_extraction",
        prompt_version="v1",
        messages=messages,
        schema=ConceptList,
        model_tier="strong",
    )
    second = client.parse(
        task="concept_extraction",
        prompt_version="v1",
        messages=messages,
        schema=ConceptList,
        model_tier="strong",
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert client.backend_call_count == 1  # the cache hit made zero backend calls
    assert second.output == first.output


def test_call_is_logged(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    client.parse(
        task="concept_extraction",
        prompt_version="v1",
        messages=[{"role": "user", "content": "log me"}],
        schema=ConceptList,
        model_tier="bulk",
    )

    log_path = tmp_settings.resolve(tmp_settings.paths.data_logs) / "llm_calls.jsonl"
    assert log_path.exists()
    line = log_path.read_text().strip().splitlines()[-1]
    assert '"model": "gpt-6-luna"' in line
    assert "log me" not in line  # never log prompt text


def test_parse_raises_before_call_when_overall_cap_would_be_exceeded(tmp_settings, fixtures_dir):
    tmp_settings.llm.max_usd_per_command = 0.0000001
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)

    with pytest.raises(BudgetExceededError):
        client.parse(
            task="concept_extraction",
            prompt_version="v1",
            messages=[{"role": "user", "content": "extract concepts from section 6.3"}],
            schema=ConceptList,
            model_tier="strong",
        )

    assert client.backend_call_count == 0  # never actually called
    assert client.spent_usd == 0.0  # nothing spent


def test_parse_raises_when_stage_cap_would_be_exceeded_even_if_overall_cap_is_fine(
    tmp_settings, fixtures_dir
):
    tmp_settings.llm.max_usd_per_command = 100.0  # generous overall cap
    tmp_settings.llm.stage_budgets_usd = {"concepts": 0.0000001}  # near-zero stage cap
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)

    with pytest.raises(BudgetExceededError):
        client.parse(
            task="concept_extraction",  # maps to stage "concepts"
            prompt_version="v1",
            messages=[{"role": "user", "content": "extract concepts from section 6.3"}],
            schema=ConceptList,
            model_tier="strong",
        )

    assert client.backend_call_count == 0


def test_parse_proceeds_and_tracks_spend_when_within_budget(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    assert client.spent_usd == 0.0

    client.parse(
        task="concept_extraction",
        prompt_version="v1",
        messages=[{"role": "user", "content": "extract concepts from section 6.3"}],
        schema=ConceptList,
        model_tier="strong",
    )

    assert client.backend_call_count == 1
    assert client.spent_usd > 0.0  # demo.json's _usage: input=200, output=80


def test_spent_usd_seeded_from_prior_log_on_resume(tmp_settings, fixtures_dir):
    run_id = "resume-test-run"
    first_client = LLMClient(tmp_settings, run_id=run_id, fixtures_dir=fixtures_dir)
    first_client.parse(
        task="concept_extraction",
        prompt_version="v1",
        messages=[{"role": "user", "content": "extract concepts from section 6.3"}],
        schema=ConceptList,
        model_tier="strong",
    )
    spent_after_first_call = first_client.spent_usd
    assert spent_after_first_call > 0.0

    resumed_client = LLMClient(tmp_settings, run_id=run_id, fixtures_dir=fixtures_dir)
    assert resumed_client.spent_usd == spent_after_first_call  # picked up from the log, not zero


def test_cache_hit_does_not_trigger_budget_check(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    messages = [{"role": "user", "content": "extract concepts from section 6.3"}]
    client.parse(
        task="concept_extraction",
        prompt_version="v1",
        messages=messages,
        schema=ConceptList,
        model_tier="strong",
    )
    spent_after_first_call = client.spent_usd

    # Now drop the cap to (near) zero -- a cache hit must still succeed since it costs nothing.
    tmp_settings.llm.max_usd_per_command = 0.0000001
    result = client.parse(
        task="concept_extraction",
        prompt_version="v1",
        messages=messages,
        schema=ConceptList,
        model_tier="strong",
    )
    assert result.cache_hit is True
    assert client.spent_usd == spent_after_first_call  # unchanged
