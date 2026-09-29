"""Reads real spend from the LLM call log, given the configured per-tier prices.

Kept in `llm/` (not `expert_kg/`) since it's fundamentally about the call log
`llm/client.py` itself writes -- shared by `LLMClient`'s own live budget enforcement
(CR-005 §9) and `expert_kg/cost_estimate.py`'s reporting, which imports and re-exports
`spend_from_log` as `spend_for_run` rather than duplicating this logic.
"""

from __future__ import annotations

import json
from pathlib import Path

from cumap.config import Settings


def spend_from_log(settings: Settings, run_id: str, log_path: Path | None = None) -> float:
    """Real USD spent so far by `run_id`. Cache hits cost nothing and are skipped; a
    tier with no configured price is skipped too (can't cost what has no price).
    """
    path = log_path or (settings.resolve(settings.paths.data_logs) / "llm_calls.jsonl")
    if not path.exists():
        return 0.0

    total_usd = 0.0
    with path.open() as f:
        for line in f:
            row = json.loads(line)
            if row["run_id"] != run_id or row["cache_hit"]:
                continue
            tier_cfg = settings.llm.tiers.get(row["model_tier"])
            if tier_cfg is None or tier_cfg.usd_per_1m_input_tokens is None:
                continue
            usage = row["usage"]
            total_usd += usage.get("input_tokens", 0) / 1_000_000 * tier_cfg.usd_per_1m_input_tokens
            total_usd += (
                usage.get("output_tokens", 0) / 1_000_000 * tier_cfg.usd_per_1m_output_tokens
            )
    return total_usd
