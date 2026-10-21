from __future__ import annotations

from pathlib import Path

from cumap.config import Settings, load_settings


def test_load_settings_from_default_yaml(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CUMAP_LLM_BACKEND", "mock")

    settings = load_settings(env_file=tmp_path / "does-not-exist.env")

    assert isinstance(settings, Settings)
    assert settings.llm.tiers["strong"].model == "gpt-6-sol"
    assert settings.llm.tiers["bulk"].model == "gpt-6-luna"
    assert settings.llm.tiers["ceiling"].model == "gpt-6-astra"
    assert settings.llm.escalation.enabled is True
    assert settings.llm.escalation.from_tier == "bulk"
    assert settings.llm.escalation.to_tier == "strong"
    assert settings.llm_backend == "mock"
    assert len(settings.pilot_questions) == 5
    assert all(qid.startswith("q_") for qid in settings.pilot_questions)


def test_env_overrides_model_names(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL_STRONG", "gpt-override-strong")
    monkeypatch.setenv("OPENAI_MODEL_BULK", "gpt-override-bulk")
    monkeypatch.setenv("OPENAI_MODEL_CEILING", "gpt-override-ceiling")

    settings = load_settings(env_file=tmp_path / "does-not-exist.env")

    assert settings.llm.tiers["strong"].model == "gpt-override-strong"
    assert settings.llm.tiers["bulk"].model == "gpt-override-bulk"
    assert settings.llm.tiers["ceiling"].model == "gpt-override-ceiling"


def test_resolve_relative_path_against_repo_root():
    settings = load_settings()
    resolved = settings.resolve(Path("data/gold"))
    assert resolved == settings.repo_root / "data" / "gold"


def test_model_profile_overlays_only_the_tiers_it_names(tmp_path, monkeypatch):
    """CR-023: CUMAP_MODELS_CONFIG swaps the strong tier to o4-mini with its price; bulk is untouched; unset restores the baseline."""
    monkeypatch.delenv("OPENAI_MODEL_STRONG", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_BULK", raising=False)
    monkeypatch.setenv("CUMAP_LLM_BACKEND", "mock")
    monkeypatch.setenv("CUMAP_MODELS_CONFIG", "configs/models_cr023.yaml")
    s = load_settings(env_file=tmp_path / "none.env")
    assert s.llm.tiers["strong"].model == "o4-mini" and s.llm.tiers["strong"].usd_per_1m_input_tokens == 1.10
    assert s.llm.tiers["bulk"].model == "gpt-6-luna" and s.llm.tiers["ceiling"].model == "gpt-6-astra"
    monkeypatch.setenv("CUMAP_MODELS_CONFIG", "")
    assert load_settings(env_file=tmp_path / "none.env").llm.tiers["strong"].model == "gpt-6-sol"
