"""Single entry point for every LLM call in cumap. Never call the OpenAI SDK elsewhere.

Structured Outputs via `client.responses.parse(..., text_format=schema)`, a disk cache
keyed by (model, prompt_version, canonical input, schema), a mock backend for tests,
and a JSONL call log (hashes and metadata only — never prompt text or the key).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from cumap.config import Settings
from cumap.llm.cache import LLMCache, canonical_input_hash
from cumap.llm.mock import load_fixture

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass
class ParsedResult(Generic[SchemaT]):
    output: SchemaT
    model: str
    prompt_version: str
    task: str
    input_hash: str
    run_id: str
    usage: dict
    cache_hit: bool
    latency_ms: float


def _is_retryable(exc: BaseException) -> bool:
    """Rate limits and 5xx are retryable; auth/validation errors are not."""
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status is not None:
        return status == 429 or status >= 500
    return exc.__class__.__name__ in {"RateLimitError", "APIConnectionError", "APITimeoutError"}


class LLMClient:
    """Structured Outputs client with caching, mock backend, and call logging.

    All LLM calls in cumap MUST go through this class (CLAUDE.md rule 4).
    """

    def __init__(
        self,
        settings: Settings,
        *,
        run_id: str | None = None,
        fixtures_dir: Path | None = None,
    ):
        self._settings = settings
        self._cache = LLMCache(settings.resolve(settings.paths.data_cache) / "llm")
        self._log_path = settings.resolve(settings.paths.data_logs) / "llm_calls.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or uuid.uuid4().hex
        self._fixtures_dir = fixtures_dir or (settings.repo_root / "tests" / "fixtures" / "llm")
        self._client = None  # lazy OpenAI client; never constructed by mock-backend tests
        # Test hook: counts real/mock backend invocations, i.e. calls that were NOT cache hits.
        self._backend_call_count = 0

    @property
    def backend_call_count(self) -> int:
        return self._backend_call_count

    def _model_for_tier(self, model_tier: str) -> str:
        if model_tier == "strong":
            return self._settings.llm.model_strong
        if model_tier == "bulk":
            return self._settings.llm.model_bulk
        raise ValueError(f"model_tier must be 'strong' or 'bulk', got {model_tier!r}")

    def _reasoning_effort(self, task: str, model: str) -> str:
        effort = self._settings.llm.reasoning_effort.get(task, "low")
        # gpt-6-astra does not support effort "none" (CLAUDE.md OpenAI usage notes).
        if model == "gpt-6-astra" and effort == "none":
            return "low"
        return effort

    def parse(
        self,
        *,
        task: str,
        prompt_version: str,
        messages: list[dict],
        schema: type[SchemaT],
        model_tier: str,
        fixture_name: str = "default",
    ) -> ParsedResult[SchemaT]:
        model = self._model_for_tier(model_tier)
        input_hash = canonical_input_hash(model, prompt_version, messages, schema.__name__)
        start = time.monotonic()

        cached = self._cache.get(input_hash)
        if cached is not None:
            result = ParsedResult(
                output=schema.model_validate(cached["output"]),
                model=model,
                prompt_version=prompt_version,
                task=task,
                input_hash=input_hash,
                run_id=self.run_id,
                usage=cached.get("usage", {}),
                cache_hit=True,
                latency_ms=(time.monotonic() - start) * 1000,
            )
            self._log(result)
            return result

        if self._settings.llm_backend == "mock":
            raw = dict(load_fixture(self._fixtures_dir, task, fixture_name))
            usage = raw.pop("_usage", {"input_tokens": 0, "output_tokens": 0})
            output = schema.model_validate(raw)
        else:
            output, usage = self._call_openai(model, messages, schema, task)
        self._backend_call_count += 1

        self._cache.set(input_hash, {"output": output.model_dump(mode="json"), "usage": usage})
        result = ParsedResult(
            output=output,
            model=model,
            prompt_version=prompt_version,
            task=task,
            input_hash=input_hash,
            run_id=self.run_id,
            usage=usage,
            cache_hit=False,
            latency_ms=(time.monotonic() - start) * 1000,
        )
        self._log(result)
        return result

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    def _call_openai(
        self, model: str, messages: list[dict], schema: type[SchemaT], task: str
    ) -> tuple[SchemaT, dict]:
        from openai import OpenAI  # lazy: mock backend / tests never need this installed-and-keyed

        if self._client is None:
            self._client = OpenAI(api_key=self._settings.openai_api_key)

        effort = self._reasoning_effort(task, model)
        response = self._client.responses.parse(
            model=model,
            input=messages,
            text_format=schema,
            reasoning={"effort": effort},
        )
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return response.output_parsed, usage

    def _log(self, result: ParsedResult) -> None:
        line = {
            "ts": time.time(),
            "run_id": result.run_id,
            "task": result.task,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "input_hash": result.input_hash,
            "cache_hit": result.cache_hit,
            "usage": result.usage,
            "latency_ms": result.latency_ms,
        }
        with self._log_path.open("a") as f:
            f.write(json.dumps(line) + "\n")
