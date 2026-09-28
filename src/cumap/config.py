"""Loads configs/default.yaml + .env into a single Settings object."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "default.yaml"


class PathsConfig(BaseModel):
    data_raw: Path
    data_interim: Path
    data_gold: Path
    data_processed: Path
    data_cache: Path
    data_logs: Path
    reports: Path
    prompts: Path


class TextbookConfig(BaseModel):
    repo_url: str
    clone_dir: Path
    pinned_commit: str | None = None


class LLMConfig(BaseModel):
    model_strong: str
    model_bulk: str
    reasoning_effort: dict[str, str]
    max_usd_per_command: float


class EmbeddingsConfig(BaseModel):
    model: str


class Settings(BaseModel):
    version: int
    seed: int
    paths: PathsConfig
    textbook: TextbookConfig
    llm: LLMConfig
    embeddings: EmbeddingsConfig
    pilot_questions: list[str]

    openai_api_key: str | None = None
    llm_backend: str = "openai"

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT

    def resolve(self, path: Path) -> Path:
        """Resolve a config-relative path against the repo root."""
        return path if path.is_absolute() else self.repo_root / path


def load_settings(config_path: Path | None = None, *, env_file: Path | None = None) -> Settings:
    """Load YAML config, apply env var overrides, and return a validated Settings object.

    `env_file` defaults to `<repo_root>/.env`; missing is fine (envs may already be set).
    """
    load_dotenv(dotenv_path=env_file or (REPO_ROOT / ".env"))

    raw = yaml.safe_load((config_path or DEFAULT_CONFIG_PATH).read_text())

    llm_raw = dict(raw["llm"])
    llm_raw["model_strong"] = os.environ.get("OPENAI_MODEL_STRONG", llm_raw["model_strong"])
    llm_raw["model_bulk"] = os.environ.get("OPENAI_MODEL_BULK", llm_raw["model_bulk"])
    raw = {**raw, "llm": llm_raw}

    return Settings(
        **raw,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        llm_backend=os.environ.get("CUMAP_LLM_BACKEND", "openai"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
