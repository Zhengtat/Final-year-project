from __future__ import annotations

from pydantic import BaseModel

from cumap.llm.client import LLMClient


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
