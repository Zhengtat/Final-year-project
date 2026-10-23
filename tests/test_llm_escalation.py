"""CR-001 §8 acceptance tests: LLM client tiers and escalation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from cumap.llm.client import LLMClient


class AnswerWithConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    confidence: float


class AnswerNoConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str


def test_tiers_resolve_to_configured_models(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    assert client._model_for_tier("strong") == "gpt-6-sol"
    assert client._model_for_tier("bulk") == "gpt-6-luna"
    assert client._model_for_tier("ceiling") == "gpt-6-astra"


def test_unknown_tier_raises(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    with pytest.raises(ValueError, match="model_tier must be one of"):
        client._model_for_tier("nonexistent")


def test_bulk_call_with_high_confidence_does_not_escalate(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    result = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=[{"role": "user", "content": "x"}],
        schema=AnswerWithConfidence,
        model_tier="bulk",
        fixture_name="high_confidence",
    )
    assert result.escalated is False
    assert result.model_tier == "bulk"
    assert client.escalation_count == 0


def test_bulk_call_with_low_confidence_escalates_exactly_once(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    result = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=[{"role": "user", "content": "x"}],
        schema=AnswerWithConfidence,
        model_tier="bulk",
        fixture_name="low_confidence",
    )
    assert result.escalated is True
    assert result.escalation_reason == "low_confidence"
    assert result.model_tier == "strong"
    assert result.model == "gpt-6-sol"
    assert client.escalation_count == 1
    assert client.calls_by_tier == {"bulk": 1, "strong": 1}


def test_strong_tier_call_never_escalates_even_with_low_confidence(tmp_settings, fixtures_dir):
    """Escalation only fires when model_tier == escalation.from_tier ("bulk")."""
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    result = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=[{"role": "user", "content": "x"}],
        schema=AnswerWithConfidence,
        model_tier="strong",
        fixture_name="low_confidence",
    )
    assert result.escalated is False
    assert client.escalation_count == 0


def test_schema_without_confidence_field_never_triggers_low_confidence_escalation(
    tmp_settings, fixtures_dir
):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    result = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=[{"role": "user", "content": "x"}],
        schema=AnswerNoConfidence,  # no `confidence` field at all -> nothing to check
        model_tier="bulk",
        fixture_name="answer_only",
    )
    assert result.escalated is False
    assert client.escalation_count == 0


def test_schema_error_on_bulk_tier_escalates(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    result = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=[{"role": "user", "content": "x"}],
        schema=AnswerWithConfidence,
        model_tier="bulk",
        fixture_name="schema_error",  # invalid against AnswerWithConfidence (missing confidence)
    )
    assert result.escalated is True
    assert result.escalation_reason == "schema_error"
    assert result.model_tier == "strong"
    assert result.output.answer == "the strong tier got it right"  # loaded the _escalated variant
    assert client.escalation_count == 1


def test_schema_error_on_strong_tier_propagates_when_not_escalatable(tmp_settings, fixtures_dir):
    from pydantic import ValidationError

    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    with pytest.raises(ValidationError):
        client.parse(
            task="escalation_test",
            prompt_version="v1",
            messages=[{"role": "user", "content": "x"}],
            schema=AnswerWithConfidence,
            model_tier="strong",  # not the escalation.from_tier -> no escalation, error propagates
            fixture_name="schema_error",
        )


def test_evidence_check_failed_escalates_via_callback(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    result = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=[{"role": "user", "content": "x"}],
        schema=AnswerWithConfidence,
        model_tier="bulk",
        fixture_name="high_confidence",  # confidence alone wouldn't escalate
        escalate_check=lambda output: (
            output.answer == "a confident answer"
        ),  # simulate a failed evidence check
    )
    assert result.escalated is True
    assert result.escalation_reason == "evidence_check_failed"


def test_evidence_check_passing_does_not_escalate(tmp_settings, fixtures_dir):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    result = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=[{"role": "user", "content": "x"}],
        schema=AnswerWithConfidence,
        model_tier="bulk",
        fixture_name="high_confidence",
        escalate_check=lambda output: False,
    )
    assert result.escalated is False


def test_escalated_result_cache_hit_on_second_call(tmp_settings, fixtures_dir):
    """A second identical call hits the cache for BOTH the bulk sub-check and the
    escalated strong-tier result — same cache mechanism regardless of escalation, keyed
    by (model, prompt_version, messages, schema), so no real backend call repeats.
    """
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    messages = [{"role": "user", "content": "x"}]
    first = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=messages,
        schema=AnswerWithConfidence,
        model_tier="bulk",
        fixture_name="low_confidence",
    )
    second = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=messages,
        schema=AnswerWithConfidence,
        model_tier="bulk",
        fixture_name="low_confidence",
    )
    assert first.escalated is True
    assert first.cache_hit is False  # first time: real backend calls for both bulk and strong
    assert second.escalated is True
    assert second.cache_hit is True  # second time: the escalated (strong) result is a cache hit
    # Only 1 real backend call per tier total, across both parse() calls.
    assert client.calls_by_tier == {"bulk": 1, "strong": 1}


@pytest.fixture
def luna_settings(tmp_path, monkeypatch):
    """CR-026: the luna-default profile (every tier luna, sol only on escalation), data dirs in tmp_path."""
    from cumap.config import load_settings

    monkeypatch.setenv("CUMAP_LLM_BACKEND", "mock")
    monkeypatch.setenv("CUMAP_MODELS_CONFIG", "configs/models_luna_default.yaml")
    monkeypatch.setenv("OPENAI_MODEL_STRONG", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_MODEL_BULK", "gpt-6-luna")
    s = load_settings(env_file=tmp_path / "none.env")
    return s.model_copy(
        update={
            "paths": s.paths.model_copy(
                update={"data_cache": tmp_path / "cache", "data_logs": tmp_path / "logs"}
            )
        }
    )


def test_luna_default_profile_uses_luna_everywhere_and_sol_only_as_the_escalation_tier(
    luna_settings, fixtures_dir
):
    client = LLMClient(luna_settings, fixtures_dir=fixtures_dir)
    assert client._model_for_tier("strong") == client._model_for_tier("bulk") == "gpt-6-luna"
    assert (
        client._model_for_tier("escalate") == "gpt-6-sol"
        and client._model_for_tier("ceiling") == "gpt-6-astra"
    )


@pytest.mark.parametrize("tier", ["strong", "bulk"])
def test_luna_default_escalates_once_to_sol_from_either_tier(luna_settings, fixtures_dir, tier):
    client = LLMClient(luna_settings, fixtures_dir=fixtures_dir)
    kw = {
        "task": "escalation_test",
        "prompt_version": "v1",
        "messages": [{"role": "user", "content": "x"}],
        "schema": AnswerWithConfidence,
    }
    ok = client.parse(**kw, model_tier=tier, fixture_name="high_confidence")
    assert ok.model == "gpt-6-luna" and ok.escalated is False
    low = client.parse(
        **{**kw, "messages": [{"role": "user", "content": "y"}]},
        model_tier=tier,
        fixture_name="low_confidence",
    )
    assert low.escalated is True and low.model == "gpt-6-sol" and low.model_tier == "escalate"
    assert client.escalation_count == 1


def test_a_call_that_opts_out_of_escalation_stays_on_luna(luna_settings, fixtures_dir):
    client = LLMClient(luna_settings, fixtures_dir=fixtures_dir)
    r = client.parse(
        task="escalation_test",
        prompt_version="v1",
        messages=[{"role": "user", "content": "x"}],
        schema=AnswerWithConfidence,
        model_tier="strong",
        fixture_name="low_confidence",
        allow_escalation=False,
    )
    assert r.model == "gpt-6-luna" and r.escalated is False
