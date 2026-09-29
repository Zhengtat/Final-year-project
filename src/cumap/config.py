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


class TierConfig(BaseModel):
    model: str
    reasoning_effort: str
    # CR-005 §2 step 3: per-tier pricing, replacing the flat placeholder rate for any
    # cost estimate that knows which tier a call will run on. None on a tier that has
    # no confirmed price yet (e.g. ceiling, opt-in only) — estimators must raise, not
    # silently treat a missing price as free.
    usd_per_1m_input_tokens: float | None = None
    usd_per_1m_output_tokens: float | None = None


class EscalationConfig(BaseModel):
    enabled: bool
    from_tier: str
    to_tier: str
    when: list[str]  # "schema_error" | "evidence_check_failed" | "low_confidence"
    confidence_threshold: float


class LLMConfig(BaseModel):
    # CR-001 §8: strong/bulk/ceiling. "ceiling" is never a default model_tier anywhere
    # in the codebase — opt-in only, e.g. for a model bake-off.
    tiers: dict[str, TierConfig]
    # Per-task effort wins over its tier's default (e.g. expert_subgraph needs more
    # care than the average strong-tier call); unlisted tasks use the tier default.
    reasoning_effort_overrides: dict[str, str]
    escalation: EscalationConfig
    max_usd_per_command: float
    assumed_usd_per_1k_input_tokens: float
    assumed_usd_per_1k_output_tokens: float
    assumed_batch_discount: float  # CR-003 §13: "--batch roughly halves the cost"
    # CR-005 §9: per-stage budgets, enforced inside LLMClient.parse itself (not just
    # a pre-run estimate) -- a stage with no entry here, or an entry of null, falls
    # back to max_usd_per_command only. Stage names match TASK_TO_STAGE in llm/client.py.
    stage_budgets_usd: dict[str, float | None] = {}
    # Worst-case output-token bound used for the pre-call budget check, and passed to
    # the real API as max_output_tokens (bounds actual generation, not just the
    # estimate) -- per task, falling back to "default" when a task has no entry.
    max_output_tokens: dict[str, int] = {}


class EmbeddingsConfig(BaseModel):
    model: str


class Settings(BaseModel):
    version: int
    seed: int
    paths: PathsConfig
    textbook: TextbookConfig
    relation_registry: Path
    registry_version_supported: list[int]
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
    tiers_raw = dict(llm_raw["tiers"])
    env_override = {
        "strong": "OPENAI_MODEL_STRONG",
        "bulk": "OPENAI_MODEL_BULK",
        "ceiling": "OPENAI_MODEL_CEILING",
    }
    for tier_name, env_var in env_override.items():
        if tier_name in tiers_raw and os.environ.get(env_var):
            tiers_raw[tier_name] = {**tiers_raw[tier_name], "model": os.environ[env_var]}
    llm_raw["tiers"] = tiers_raw
    raw = {**raw, "llm": llm_raw}

    return Settings(
        **raw,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        llm_backend=os.environ.get("CUMAP_LLM_BACKEND", "openai"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


class CorpusSliceConfig(BaseModel):
    """One corpus's slice definition within configs/demo_slice.yaml (CR-005 §1,
    §9 relations_enabled).
    """

    source_jsonl: Path
    chapters: list[int]
    domain: str
    relations_enabled: bool


class DemoSliceConfig(BaseModel):
    pd: CorpusSliceConfig
    iir_face: CorpusSliceConfig
    max_usd_per_command: float


def load_demo_slice(path: Path | None = None) -> DemoSliceConfig:
    raw = yaml.safe_load((path or (REPO_ROOT / "configs" / "demo_slice.yaml")).read_text())
    return DemoSliceConfig(**raw)
