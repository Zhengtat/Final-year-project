"""CR-015 A2/A3: family-level boundary selector (LLM) -> unchanged frozen-V3 verifier -> family-grounded nested-aware placement.

All calls go through `LLMClient`. The verifier prompt/logic is the frozen CR-014 V3 one (prompt v2, one-word evidence column); only the boundary stage and placement differ.
A3 additionally injects retrieved hard-negative contrastive demonstrations from the development bank (leave-one-section-out)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from cumap.concepts_v4.schema import _Strict
from cumap.cr014 import v3_core
from cumap.cr014.llm_stage import Usage, mark, run_verifier
from cumap.cr014.proposal import norm_surface
from cumap.cr014.union import Cand, Family, SectionUnion
from cumap.cr015 import hardneg
from cumap.llm.client import BudgetExceededError

Label = Literal[
    "KEEP_PRIMARY",
    "KEEP_NESTED",
    "EXPAND_TO",
    "SHRINK_TO",
    "REJECT_DESCRIPTIVE",
    "REJECT_GENERIC",
    "REJECT_UNSUPPORTED",
]
Reason = Literal[
    "correct_boundary",
    "nested_independent",
    "longer_term_in_text",
    "shorter_term",
    "wrapper_phrase",
    "discourse_word",
    "fragment",
]
KEEP = {"KEEP_PRIMARY", "KEEP_NESTED"}
BATCH_FAMILIES = 15
MAX_WORDS = 6
DOMAIN = "computer networking"


class CandDecisionLLM(_Strict):
    candidate_id: str
    label: Label
    target_surface: str | None
    reason_code: Reason


class FamilyDecisionLLM(_Strict):
    family_id: str
    decisions: list[CandDecisionLLM]


class BoundaryFamilyBatchLLM(_Strict):
    families: list[FamilyDecisionLLM]


@dataclass
class SelectorOutcome:
    selected: dict[str, set[str]] = field(default_factory=dict)  # fid -> surfaces the selector kept
    decisions: dict[str, list[dict]] = field(default_factory=dict)
    invalid_targets: list[dict] = field(default_factory=list)
    unanswered: list[str] = field(default_factory=list)  # candidate ids with no decision
    retrieval: dict[str, list[str]] = field(
        default_factory=dict
    )  # batch key -> retrieved group ids
    n_families_llm: int = 0


def render_families(u: SectionUnion, fams: list[Family], by_id: dict[str, Cand]) -> str:
    blocks = []
    for f in fams:
        a, b, si = f.occurrences[0]
        sentence = mark(u.text, u.sents[si], (a, b), 720)
        members = "; ".join(f"{cid} = {by_id[cid].surface}" for cid in f.members)
        blocks.append(f"FAMILY {f.fid}\nsentence: {sentence}\ncandidates: {members}")
    return "\n\n".join(blocks)


def demonstrations(
    bank: dict,
    section: str,
    fams: list[Family],
    by_id: dict[str, Cand],
    out: SelectorOutcome,
    key: str,
    per_family: int = 1,
    cap: int = 8,
) -> str:
    seen, groups = set(), []
    for f in fams:
        longest = max((by_id[c] for c in f.members), key=lambda c: c.token_length)
        head = longest.surface.split()[-1]
        for g in hardneg.retrieve(bank, section, longest.token_length, head, k=per_family):
            if g["group_id"] not in seen:
                seen.add(g["group_id"])
                groups.append(g)
    groups = groups[:cap]
    out.retrieval[key] = [g["group_id"] for g in groups]
    return "\n".join(hardneg.render_group(g) for g in groups) or "(none)"


def run_selector(
    client,
    prompt,
    u: SectionUnion,
    heading: str,
    fams: list[Family],
    by_id: dict[str, Cand],
    usage: Usage,
    *,
    bank: dict | None = None,
) -> SelectorOutcome:
    out = SelectorOutcome()
    client._settings.llm.max_output_tokens["cr015_boundary_family"] = 9000
    for i in range(0, len(fams), BATCH_FAMILIES):
        batch = fams[i : i + BATCH_FAMILIES]
        kw = {
            "domain": DOMAIN,
            "heading_path": heading,
            "families": render_families(u, batch, by_id),
        }
        if bank is not None:
            kw["demonstrations"] = demonstrations(
                bank, u.section_id, batch, by_id, out, f"{u.section_id}[{i}]"
            )
        try:
            r = client.parse(
                task=prompt.task, prompt_version=prompt.version, messages=[{"role": "user", "content": prompt.render(**kw)}],
                schema=BoundaryFamilyBatchLLM, model_tier="bulk", allow_escalation=False,
            )  # fmt: skip
        except BudgetExceededError:
            raise
        except Exception as e:  # noqa: BLE001
            usage.errors.append(f"{u.section_id}[{i}]: {type(e).__name__}: {str(e)[:140]}")
            continue
        usage.calls += 1
        fam_by_id = {f.fid: f for f in batch}
        for fd in r.output.families:
            f = fam_by_id.get(fd.family_id)
            if f is None or fd.family_id in out.decisions:
                continue
            out.decisions[f.fid] = [d.model_dump() for d in fd.decisions]
    out.n_families_llm = len(out.decisions)
    for f in fams:
        sent = " ".join(
            u.text[u.sents[si][0] : u.sents[si][1]].lower() for _a, _b, si in f.occurrences[:3]
        )
        sent = re.sub(r"\s+", " ", sent)
        answered = {d["candidate_id"] for d in out.decisions.get(f.fid, [])}
        out.unanswered += [c for c in f.members if c not in answered]
        sel = set()
        for d in out.decisions.get(f.fid, []):
            if d["candidate_id"] not in f.members:
                continue
            surf = by_id[d["candidate_id"]].surface
            if d["label"] in KEEP:
                sel.add(surf)
            elif d["label"] in {"EXPAND_TO", "SHRINK_TO"}:
                t = norm_surface(d["target_surface"] or "")
                if t and len(t.split()) <= MAX_WORDS and t in sent:
                    sel.add(t)
                else:
                    out.invalid_targets.append(
                        {"family": f.fid, "candidate": surf, "target": d["target_surface"]}
                    )
        out.selected[f.fid] = sel
    return out


def verify_selected(
    client, prompt_v, u: SectionUnion, heading: str, selected: dict[str, set[str]], usage: Usage
) -> tuple[set[str], dict[str, dict]]:
    """The frozen V3 verifier (prompt v2, one-word evidence, 25 per call) on the distinct selected surfaces."""
    n_new = 0
    spans: dict[str, Cand] = {}
    for surfaces in selected.values():
        for s in surfaces:
            if s in spans:
                continue
            c = v3_core.new_span_cand(u, s, n_new)
            if c is None:
                continue
            if c.cid.count("#s"):
                n_new += 1
            spans[s] = c
    cs = list(spans.values())
    fe = v3_core.onetoken_features(u, heading)
    sc = v3_core.onetoken_scores(u, heading)
    cs = sorted(cs, key=lambda c: (c.token_length != 1, -sc.get(c.cid, 0.0), c.cid))
    extra = {
        c.cid: (
            v3_core.evidence_text(c, fe[c.cid]) if c.cid in fe else "evidence: n/a (multi-word)"
        )
        for c in cs
    }
    vs = run_verifier(client, prompt_v, u, heading, cs, v3_core.SB, {}, DOMAIN, usage, extra=extra)
    accepted = {c.surface for c in cs if vs.get(c.cid, {}).get("verdict") in v3_core.ACCEPT}
    verdicts = {c.surface: vs.get(c.cid, {"verdict": "NO_ANSWER"}) for c in cs}
    return accepted, verdicts
