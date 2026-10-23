"""CR-037 DRAFT: the U5 identity judge (strong tier; `identity_resolver: u1` and `identity_judge: "v1"`, both off by default).

One LLM call decides a pair the deterministic rules U0-U4 (`identity.py`) could not decide: `same` / `narrower` / `broader` / `new` /
`not_a_concept`, with a verbatim evidence quote. The schema is a closed choice built from `configs/identity_rules.yaml` (rule 12), all fields
required, no defaults (CLAUDE.md "OpenAI usage"). The call goes through `llm/client.py` only (rule 4). The prompt `prompts/identity_judge/v1.md`
is a draft awaiting the owner's review: nothing here has been run against a real model, and the pre-registered measurement waits for that review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model

from cumap.config import REPO_ROOT
from cumap.expert_kg.identity import load_rules
from cumap.gold.validate import verify_quote
from cumap.llm.prompts import PromptTemplate, load_prompt

JUDGE_MODES = ("off", "v1")


def judge_options() -> tuple[str, ...]:
    return tuple(load_rules()["judge"]["options"])


def build_identity_judge_schema(options: tuple[str, ...] | None = None) -> type[BaseModel]:
    """Flat LLM schema: every field required, no defaults, no extra properties; `decision` is a closed choice."""
    opts = options or judge_options()
    return create_model(
        "IdentityJudgeLLM",
        __config__=ConfigDict(extra="forbid"),
        decision=(Literal[*opts], ...),
        evidence_quote=(str, ...),
        reason=(str, ...),
        confidence=(float, ...),
    )


def resolve_judge_mode(mode: str | None = None) -> str:
    """Explicit argument, else `identity_judge` in `configs/concept_policy.yaml` (default "off"; a bare YAML `off` is False)."""
    if mode is None:
        import yaml

        p = REPO_ROOT / "configs/concept_policy.yaml"
        mode = (yaml.safe_load(p.read_text()) or {}).get("identity_judge", "off")
    if mode is False:
        mode = "off"
    if mode not in JUDGE_MODES:
        raise ValueError(f"identity_judge must be one of {JUDGE_MODES}, got {mode!r}")
    return mode


def load_judge_prompt() -> PromptTemplate:
    j = load_rules()["judge"]
    return load_prompt(REPO_ROOT / "prompts", j["prompt"], j["version"])


@dataclass(frozen=True)
class JudgeResult:
    decision: (
        str  # one of the options, or "no_decision" when the evidence quote is not in the sentence
    )
    raw_decision: str
    evidence_quote: str
    reason: str
    confidence: float
    input_hash: str | None


def judge_pair(
    client,
    prompt: PromptTemplate,
    *,
    domain: str,
    surface: str,
    target_name: str,
    target_aliases: list[str],
    target_type: str,
    target_gloss: str | None,
    sentence: str,
    fixture_name: str = "default",
) -> JudgeResult:
    """One strong-tier call. A decision whose evidence quote is not an exact substring of `sentence` becomes `no_decision` (logged by the caller)."""
    schema = build_identity_judge_schema()
    res = client.parse(
        task=prompt.task,
        prompt_version=prompt.version,
        messages=[
            {
                "role": "user",
                "content": prompt.render(
                    domain=domain,
                    surface=surface,
                    target_name=target_name,
                    target_aliases=", ".join(target_aliases) or "none",
                    target_type=target_type,
                    target_gloss=target_gloss or "none",
                    evidence=sentence,
                ),
            }
        ],
        schema=schema,
        model_tier=load_rules()["judge"]["tier"],
        fixture_name=fixture_name,
    )
    o = res.output
    ok = verify_quote(o.evidence_quote, sentence)
    return JudgeResult(
        o.decision if ok else "no_decision",
        o.decision,
        o.evidence_quote,
        o.reason,
        o.confidence,
        getattr(res, "input_hash", None),
    )
