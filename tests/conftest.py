"""Shared test fixtures. Forces the mock LLM backend so no test needs network or a key."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["CUMAP_LLM_BACKEND"] = "mock"

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures" / "llm"


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    """A Settings object whose data dirs point at a tmp_path, so tests never touch data/."""
    from cumap.config import load_settings

    monkeypatch.setenv("CUMAP_LLM_BACKEND", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = load_settings(env_file=tmp_path / "does-not-exist.env")
    settings = settings.model_copy(
        update={
            "paths": settings.paths.model_copy(
                update={
                    "data_cache": tmp_path / "cache",
                    "data_logs": tmp_path / "logs",
                }
            )
        }
    )
    return settings
