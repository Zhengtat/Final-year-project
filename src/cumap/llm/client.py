"""Single entry point for every LLM call in cumap. Never call the OpenAI SDK elsewhere.

Structured Outputs via `client.responses.parse(..., text_format=schema)`, a disk cache
keyed by (model, prompt_version, canonical input, schema), a mock backend for tests,
and a JSONL call log (hashes and metadata only — never prompt text or the key).

CR-001 §8: three tiers (strong/bulk/ceiling — "ceiling" is opt-in only, never a
default `model_tier` anywhere in the codebase) and escalation: a bulk-tier call
retries once on the strong tier if the schema fails to validate, the output's own
`confidence` field is below threshold, or the caller's `escalate_check` predicate
says so (for post-hoc checks like evidence verification, which happen outside this
class). Batch API submission is deferred to whichever milestone (M4/M6) first has a
real bulk workload to run it against — see docs/DECISIONS.md.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from cumap.config import Settings
from cumap.llm.cache import LLMCache, canonical_input_hash
from cumap.llm.mock import load_fixture

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass
class ParsedResult(Generic[SchemaT]):
    output: SchemaT
    model: str
    model_tier: str
    prompt_version: str
    task: str
    input_hash: str
    run_id: str
    usage: dict
    cache_hit: bool
    latency_ms: float
    escalated: bool = False
    escalation_reason: str | None = None  # "schema_error" | "low_confidence" | "evidence_check_failed"


def _is_retryable(exc: BaseException) -> bool:
    """Rate limits and 5xx are retryable; auth/validation errors are not."""
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status is not None:
        return status == 429 or status >= 500
    return exc.__class__.__name__ in {"RateLimitError", "APIConnectionError", "APITimeoutError"}


class LLMClient:
    """Structured Outputs client with caching, mock backend, tier escalation, and call
    logging. All LLM calls in cumap MUST go through this class (CLAUDE.md rule 4).
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
        # Test/manifest hooks (CR-001 §8.2: "the run manifest reports the escalation
        # rate and the cost split by tier"). backend_call_count counts calls that were
        # NOT cache hits, across all tiers combined.
        self._backend_call_count = 0
        self._escalation_count = 0
        self._calls_by_tier: dict[str, int] = defaultdict(int)

    @property
    def backend_call_count(self) -> int:
        return self._backend_call_count

    @property
    def escalation_count(self) -> int:
        return self._escalation_count

    @property
    def calls_by_tier(self) -> dict[str, int]:
        return dict(self._calls_by_tier)

    def _model_for_tier(self, model_tier: str) -> str:
        tiers = self._settings.llm.tiers
        if model_tier not in tiers:
            raise ValueError(f"model_tier must be one of {sorted(tiers)}, got {model_tier!r}")
        return tiers[model_tier].model

    def _reasoning_effort(self, task: str, model: str, model_tier: str) -> str:
        effort = self._settings.llm.reasoning_effort_overrides.get(
            task, self._settings.llm.tiers[model_tier].reasoning_effort
        )
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
        escalate_check: Callable[[SchemaT], bool] | None = None,
    ) -> ParsedResult[SchemaT]:
        """`escalate_check`: optional predicate for the "evidence_check_failed" escalation
        trigger — the caller's own post-hoc check (e.g. evidence-quote verification)
        happens outside this class, so it reports back via this callback rather than
        this class trying to know about every task's validation rules.
        """
        escalation = self._settings.llm.escalation
        can_escalate = escalation.enabled and model_tier == escalation.from_tier

        try:
            result = self._parse_single_tier(
                task=task, prompt_version=prompt_version, messages=messages, schema=schema,
                model_tier=model_tier, fixture_name=fixture_name,
            )
        except ValidationError:
            if can_escalate and "schema_error" in escalation.when:
                return self._escalate(task, prompt_version, messages, schema, fixture_name, "schema_error")
            raise

        if can_escalate:
            reason = self._escalation_reason(result, schema, escalation, escalate_check)
            if reason:
                return self._escalate(task, prompt_version, messages, schema, fixture_name, reason)

        return result

    def _escalation_reason(
        self,
        result: ParsedResult[SchemaT],
        schema: type[SchemaT],
        escalation,
        escalate_check: Callable[[SchemaT], bool] | None,
    ) -> str | None:
        if "low_confidence" in escalation.when and "confidence" in schema.model_fields:
            confidence = getattr(result.output, "confidence", None)
            if confidence is not None and confidence < escalation.confidence_threshold:
                return "low_confidence"
        if "evidence_check_failed" in escalation.when and escalate_check is not None and escalate_check(result.output):
            return "evidence_check_failed"
        return None

    def _escalate(self, task, prompt_version, messages, schema, fixture_name, reason: str) -> ParsedResult[SchemaT]:
        self._escalation_count += 1
        to_tier = self._settings.llm.escalation.to_tier

        # Mock backend only: if a "<fixture_name>_escalated.json" fixture exists, use it
        # for the retry, so a test can simulate "the strong tier gets a different/better
        # answer" instead of literally replaying the same fixture that just failed/scored
        # low. Falls back to the same fixture_name when no such variant exists (real
        # backend calls ignore fixture_name entirely, so this never affects production).
        if self._settings.llm_backend == "mock":
            from cumap.llm.mock import fixture_exists

            escalated_variant = f"{fixture_name}_escalated"
            if fixture_exists(self._fixtures_dir, task, escalated_variant):
                fixture_name = escalated_variant

        return self._parse_single_tier(
            task=task, prompt_version=prompt_version, messages=messages, schema=schema,
            model_tier=to_tier, fixture_name=fixture_name, escalated_reason=reason,
        )

    def _parse_single_tier(
        self,
        *,
        task: str,
        prompt_version: str,
        messages: list[dict],
        schema: type[SchemaT],
        model_tier: str,
        fixture_name: str,
        escalated_reason: str | None = None,
    ) -> ParsedResult[SchemaT]:
        model = self._model_for_tier(model_tier)
        input_hash = canonical_input_hash(model, prompt_version, messages, schema.__name__)
        start = time.monotonic()

        cached = self._cache.get(input_hash)
        if cached is not None:
            result = ParsedResult(
                output=schema.model_validate(cached["output"]),
                model=model,
                model_tier=model_tier,
                prompt_version=prompt_version,
                task=task,
                input_hash=input_hash,
                run_id=self.run_id,
                usage=cached.get("usage", {}),
                cache_hit=True,
                latency_ms=(time.monotonic() - start) * 1000,
                escalated=escalated_reason is not None,
                escalation_reason=escalated_reason,
            )
            self._log(result)
            return result

        if self._settings.llm_backend == "mock":
            raw = dict(load_fixture(self._fixtures_dir, task, fixture_name))
            usage = raw.pop("_usage", {"input_tokens": 0, "output_tokens": 0})
            output = schema.model_validate(raw)  # raises pydantic.ValidationError on schema mismatch
        else:
            output, usage = self._call_openai(model, messages, schema, task, model_tier)
        self._backend_call_count += 1
        self._calls_by_tier[model_tier] += 1

        self._cache.set(input_hash, {"output": output.model_dump(mode="json"), "usage": usage})
        result = ParsedResult(
            output=output,
            model=model,
            model_tier=model_tier,
            prompt_version=prompt_version,
            task=task,
            input_hash=input_hash,
            run_id=self.run_id,
            usage=usage,
            cache_hit=False,
            latency_ms=(time.monotonic() - start) * 1000,
            escalated=escalated_reason is not None,
            escalation_reason=escalated_reason,
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
        self, model: str, messages: list[dict], schema: type[SchemaT], task: str, model_tier: str
    ) -> tuple[SchemaT, dict]:
        from openai import OpenAI  # lazy: mock backend / tests never need this installed-and-keyed

        if self._client is None:
            self._client = OpenAI(api_key=self._settings.openai_api_key)

        effort = self._reasoning_effort(task, model, model_tier)
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
            "model_tier": result.model_tier,
            "prompt_version": result.prompt_version,
            "input_hash": result.input_hash,
            "cache_hit": result.cache_hit,
            "usage": result.usage,
            "latency_ms": result.latency_ms,
            "escalated": result.escalated,
            "escalation_reason": result.escalation_reason,
        }
        with self._log_path.open("a") as f:
            f.write(json.dumps(line) + "\n")
