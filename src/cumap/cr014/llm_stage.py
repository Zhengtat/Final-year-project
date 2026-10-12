"""CR-014 Stage B LLM steps: the independent concept verifier (V1+) and overlap-family boundary repair (V2+). All calls go through
`LLMClient` (rule 4): Structured Outputs, disk cache keyed by (model, prompt version, input hash), no escalation. Gold is never an input."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from cumap.concepts_v4.schema import _Strict
from cumap.cr014.union import Cand, Family, SectionUnion
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.llm.prompts import PromptTemplate

Verdict = Literal[
    "ACCEPT_NEW",
    "LINK_EXISTING",
    "REJECT_NOT_CONCEPT",
    "REJECT_GENERIC",
    "REJECT_PARTIAL_OR_WRONG_BOUNDARY",
    "INSUFFICIENT_EVIDENCE",
]
VerifyReason = Literal[
    "valid_term", "existing_node", "generic_word", "descriptive_phrase", "value_or_quantity",
    "fragment_or_clause", "part_of_longer_term", "overlong", "unclear_context",
]  # fmt: skip
BoundaryDecision = Literal["KEEP", "EXPAND", "SHRINK", "SPLIT", "REJECT"]
BoundaryReason = Literal[
    "correct_boundary", "partial_span", "overlong_phrase", "nested_both_valid", "several_concepts",
    "no_concept", "new_longer_term",
]  # fmt: skip


class VerdictLLM(_Strict):
    candidate_id: str
    verdict: Verdict
    node_id: str | None
    reason_code: VerifyReason


class VerifyBatchLLM(_Strict):
    verdicts: list[VerdictLLM]


class SpanDecisionLLM(_Strict):
    surface: str | None
    decision: BoundaryDecision
    source_candidate_ids: list[str]
    reason_code: BoundaryReason


class FamilyDecisionLLM(_Strict):
    family_id: str
    decisions: list[SpanDecisionLLM]


class BoundaryBatchLLM(_Strict):
    families: list[FamilyDecisionLLM]


def apply_output_caps(client: LLMClient, cfg: dict) -> None:
    """The default 1000-token cap truncates a 25-verdict batch mid-JSON; raise it for the two CR-014 tasks only (runtime, not default.yaml)."""
    caps = client._settings.llm.max_output_tokens
    for task, n in cfg["max_output_tokens"].items():
        caps[task] = n


@dataclass
class Usage:
    calls: int = 0
    errors: list[str] = field(default_factory=list)


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def mark(text: str, sent: tuple[int, int], span: tuple[int, int], max_chars: int) -> str:
    """The sentence with the span wrapped in << >> (clipped around the span when the sentence is very long)."""
    a, b = sent
    s = text[a:b]
    i, j = span[0] - a, span[1] - a
    s = s[:i] + "<<" + s[i:j] + ">>" + s[j:]
    s = _ws(s)
    if len(s) > max_chars:
        k = s.index("<<")
        lo = max(0, k - max_chars // 2)
        s = ("..." if lo else "") + s[lo : lo + max_chars] + "..."
    return s


def candidate_context(u: SectionUnion, c: Cand, n_sent: int, max_chars: int) -> str:
    seen, parts = set(), []
    for a, b, si in c.occurrences:
        if si in seen:
            continue
        seen.add(si)
        parts.append(mark(u.text, u.sents[si], (a, b), max_chars))
        if len(parts) >= n_sent:
            break
    return " || ".join(parts)


def render_candidates(
    u: SectionUnion,
    cs: list[Cand],
    cfg: dict,
    matches: dict[str, list[str]],
    extra: dict[str, str] | None = None,
) -> str:
    ctx = cfg["context"]
    lines = []
    for c in cs:
        m = "; ".join(matches.get(c.surface, [])) or "none"
        src = ",".join(sorted(c.sources))
        text = candidate_context(
            u, c, ctx["max_sentences_per_candidate"], ctx["max_chars_per_sentence"]
        )
        ev = f" | {extra[c.cid]}" if extra is not None else ""
        lines.append(f"{c.cid} | {c.surface} | {src} | {m}{ev} | {text}")
    return "\n".join(lines)


def run_verifier(
    client: LLMClient,
    prompt: PromptTemplate,
    u: SectionUnion,
    heading: str,
    cs: list[Cand],
    cfg: dict,
    matches: dict[str, list[str]],
    domain: str,
    usage: Usage,
    fixture: str = "default",
    extra: dict[str, str] | None = None,
) -> dict[str, dict]:
    """cid -> {verdict, node_id, reason_code}; a candidate the model did not answer is absent (the caller logs it)."""
    apply_output_caps(client, cfg)
    out: dict[str, dict] = {}
    n = cfg["batch_candidates"]
    for i in range(0, len(cs), n):
        batch = cs[i : i + n]
        text = prompt.render(
            domain=domain,
            heading_path=heading,
            candidates=render_candidates(u, batch, cfg, matches, extra),
        )
        try:
            r = client.parse(
                task=prompt.task,
                prompt_version=prompt.version,
                messages=[{"role": "user", "content": text}],
                schema=VerifyBatchLLM,
                model_tier=cfg["model_tier"],
                fixture_name=fixture,
                allow_escalation=False,
            )
        except BudgetExceededError:
            raise
        except Exception as e:  # noqa: BLE001  # a failed batch yields no verdicts; logged, never guessed
            usage.errors.append(f"{u.section_id}[{i}]: {type(e).__name__}: {str(e)[:160]}")
            continue
        usage.calls += 1
        known = {c.cid for c in batch}
        for v in r.output.verdicts:
            if v.candidate_id in known and v.candidate_id not in out:
                out[v.candidate_id] = v.model_dump()
    return out


def render_families(
    u: SectionUnion, fams: list[Family], cands_by_id: dict[str, Cand], cfg: dict
) -> str:
    ctx = cfg["context"]
    blocks = []
    for f in fams:
        a, b, si = f.occurrences[0]
        sentence = mark(u.text, u.sents[si], (a, b), ctx["max_chars_per_sentence"] * 2)
        members = "; ".join(f"{cid} = {cands_by_id[cid].surface}" for cid in f.members)
        blocks.append(f"FAMILY {f.fid}\nsentence: {sentence}\ncandidates: {members}")
    return "\n\n".join(blocks)


def run_boundary(
    client: LLMClient,
    prompt: PromptTemplate,
    u: SectionUnion,
    heading: str,
    fams: list[Family],
    cands_by_id: dict[str, Cand],
    cfg: dict,
    domain: str,
    usage: Usage,
    fixture: str = "default",
) -> dict[str, list[dict]]:
    apply_output_caps(client, cfg)
    out: dict[str, list[dict]] = {}
    n = cfg["batch_families"]
    for i in range(0, len(fams), n):
        batch = fams[i : i + n]
        text = prompt.render(
            domain=domain,
            heading_path=heading,
            families=render_families(u, batch, cands_by_id, cfg),
        )
        try:
            r = client.parse(
                task=prompt.task,
                prompt_version=prompt.version,
                messages=[{"role": "user", "content": text}],
                schema=BoundaryBatchLLM,
                model_tier=cfg["model_tier"],
                fixture_name=fixture,
                allow_escalation=False,
            )
        except BudgetExceededError:
            raise
        except Exception as e:  # noqa: BLE001
            usage.errors.append(f"{u.section_id}[fam {i}]: {type(e).__name__}: {str(e)[:160]}")
            continue
        usage.calls += 1
        known = {f.fid for f in batch}
        for fd in r.output.families:
            if fd.family_id in known and fd.family_id not in out:
                out[fd.family_id] = [d.model_dump() for d in fd.decisions]
    return out
