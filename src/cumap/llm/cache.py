"""Disk cache for LLM calls, keyed by (model, prompt_version, canonical input, schema)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import diskcache


def canonical_input_hash(model: str, prompt_version: str, messages: Any, schema_name: str) -> str:
    """sha256 of model + prompt_version + canonical JSON of messages + schema name.

    Canonical = json.dumps with sorted keys, so key order in caller-built message dicts
    never causes spurious cache misses.

    CR-001 §8.3: this signature has no "how the call was made" parameter (batch vs
    live) by design — a future Batch API submission path (deferred until M4/M6 have a
    real bulk workload to run it against; see docs/DECISIONS.md) MUST compute its cache
    key through this same function, which structurally guarantees identical results are
    cached under the same key regardless of which path produced them.
    """
    payload = json.dumps(
        {"model": model, "prompt_version": prompt_version, "messages": messages, "schema": schema_name},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LLMCache:
    """Thin wrapper around diskcache.Cache; a hit means the backend is never called."""

    def __init__(self, cache_dir: Path):
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(cache_dir))

    def get(self, key: str) -> dict | None:
        return self._cache.get(key)

    def set(self, key: str, value: dict) -> None:
        self._cache.set(key, value)

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def close(self) -> None:
        self._cache.close()
