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

JUDGE_MODES = ("off", "v1")  # CR-049: v2 (context packs) is measured by cumap.cr049 only; the production call sites pass no packs yet


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


def load_judge_prompt(version: str | None = None) -> PromptTemplate:
    """`version` None = the version in configs/identity_rules.yaml (v1); CR-049 passes "v2" explicitly."""
    j = load_rules()["judge"]
    return load_prompt(REPO_ROOT / "prompts", j["prompt"], version or j["version"])


def _norm(s: str) -> str:
    return " ".join(s.split())


def _mentions(sentence: str, names: list[str]) -> bool:
    import re

    low = _norm(sentence).lower()
    return any(re.search(rf"(?<![\w-]){re.escape(n.lower())}(?![\w-])", low) for n in names if n)


def context_pack(
    sentences: list[str],
    names: list[str],
    *,
    first: str | None = None,
    exclude: str | None = None,
    k: int = 3,
) -> list[str]:
    """CR-049 (GraphJudge, entity-centric context): up to `k` sentences, in text order, that mention one of `names` (whole-word,
    case-insensitive), `first` (the term's own sentence) leading the pack and `exclude` left out. Only context for the judge: it never writes
    a mention (rule 24)."""
    out = [_norm(first)] if first else []
    skip = {_norm(x) for x in (first, exclude) if x}
    for s in sentences:
        n = _norm(s)
        if len(out) >= k:
            break
        if n not in skip and n not in out and _mentions(n, names):
            out.append(n)
    return out


def render_pack(pack: list[str]) -> str:
    return "\n".join(f"- {s}" for s in pack) if pack else "- (no other sentence uses it)"


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
    term_context: list[str] | None = None,
    concept_context: list[str] | None = None,
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
                    **(
                        {}
                        if prompt.version == "v1"
                        else {
                            "term_context": render_pack(term_context or [sentence]),
                            "concept_context": render_pack(concept_context or []),
                        }
                    ),
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
