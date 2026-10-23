"""CR-010 N1: the rescue call for one section. Input: the generator's final output, the section's cards and the
deterministic candidate hints. Output: add_new / link_existing / reject per candidate. Accepted items go through the
CR-009 verifier (rules only, no corrective round), canonicalisation (R1 key de-duplication, C3 to existing mentions)
and the pruner before they count. All LLM calls go through `LLMClient`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from cumap.concepts_v4.cards import Card
from cumap.concepts_v4.loop import render_cards, render_paragraphs
from cumap.concepts_v4.schema import NodeType, _Strict
from cumap.concepts_v4.verifier import VerifyCtx, drop_flagged, verify
from cumap.cr010.candidates import Candidate
from cumap.expert_kg.alias_rules import AliasConfig, r1_key
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.llm.prompts import PromptTemplate


class RescueDecisionLLM(_Strict):
    candidate_id: str
    decision: Literal["add_new", "link_existing", "reject"]
    name: str | None
    aliases: list[str]
    node_type: NodeType | None
    role: Literal["defined", "used", "mentioned", "refined"] | None
    evidence: str | None
    para: str | None
    node_id: str | None
    surface: str | None
    reason: str


class RescueLLM(_Strict):
    decisions: list[RescueDecisionLLM]


@dataclass
class RescueResult:
    section_id: str
    candidates: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    calls: int = 0
    error: str | None = None
    out: dict = field(
        default_factory=lambda: {
            "existing_mentions": [],
            "not_mentions": [],
            "new_concepts": [],
            "hint_responses": [],
        }
    )
    incomplete: int = 0  # decisions dropped for missing fields


def render_rescue(
    prompt: PromptTemplate,
    *,
    domain: str,
    heading: str,
    cards: list[Card],
    final: dict,
    paras: dict[str, str],
    cands: list[Candidate],
) -> str:
    recorded = sorted(
        {c["name"] for c in final["new_concepts"]}
        | {m["surface"] for m in final["existing_mentions"]},
        key=str.lower,
    )
    return prompt.render(
        domain=domain,
        heading_path=heading,
        existing_nodes=render_cards(cards),
        recorded="; ".join(recorded) or "(nothing)",
        section_paragraphs=render_paragraphs(paras),
        candidates="\n".join(f"{c.cid} | {c.term} | {', '.join(c.sources)}" for c in cands),
    )


def decisions_to_output(decisions: list[dict], cards: list[Card]) -> tuple[dict, int]:
    """Generator-format output from the accepted decisions; a decision missing a field its outcome needs is dropped."""
    out = {"existing_mentions": [], "not_mentions": [], "new_concepts": [], "hint_responses": []}
    by_id = {c.node.id for c in cards}
    bad = 0
    for d in decisions:
        if d["decision"] == "add_new":
            if not all(d.get(k) for k in ("name", "node_type", "role", "evidence", "para")):
                bad += 1
                continue
            out["new_concepts"].append(
                {
                    "name": d["name"],
                    "aliases": list(d["aliases"]),
                    "node_type": d["node_type"],
                    "role": "used" if d["role"] == "refined" else d["role"],
                    "evidence": d["evidence"],
                    "para": d["para"],
                    "extraction_origin": "independent",
                    "anchors": [],
                    "independence_check": "rescue candidate: no anchor sought",
                    "found_via_anchor": False,
                }
            )
        elif d["decision"] == "link_existing":
            if (
                not all(
                    d.get(k)
                    for k in ("node_id", "surface", "node_type", "role", "evidence", "para")
                )
                or d["node_id"] not in by_id
            ):
                bad += 1
                continue
            out["existing_mentions"].append(
                {k: d[k] for k in ("node_id", "surface", "node_type", "role", "evidence", "para")}
            )
    return out, bad


def run_rescue(
    client: LLMClient,
    prompt: PromptTemplate,
    sec: dict,
    paras: dict[str, str],
    cards: list[Card],
    final: dict,
    cands: list[Candidate],
    *,
    domain: str,
    model_tier: str = "bulk",
    fixture: str = "default",
) -> RescueResult:
    res = RescueResult(sec["section_id"], candidates=[c.__dict__ for c in cands])
    if not cands:
        return res
    rendered = render_rescue(
        prompt,
        domain=domain,
        heading=str(sec.get("heading") or sec["section_id"]),
        cards=cards,
        final=final,
        paras=paras,
        cands=cands,
    )
    try:
        r = client.parse(
            task="concept_rescue",
            prompt_version=prompt.version,
            messages=[{"role": "user", "content": rendered}],
            schema=RescueLLM,
            model_tier=model_tier,
            fixture_name=fixture,
            allow_escalation=False,
        )
    except BudgetExceededError:
        raise
    except Exception as e:  # noqa: BLE001  # a failed rescue call adds nothing
        res.error = f"{type(e).__name__}: {str(e)[:200]}"
        return res
    res.calls = 1
    known = {c.cid for c in cands}
    res.decisions = [d.model_dump() for d in r.output.decisions if d.candidate_id in known]
    res.out, res.incomplete = decisions_to_output(res.decisions, cards)
    return res


def merge_additions(
    final: dict,
    extra: dict,
    vctx: VerifyCtx,
    cfg: AliasConfig,
    pruner=None,
    tau: float = 0.0,
) -> tuple[dict, dict]:
    """Verify `extra` (rules only), de-duplicate against `final` by R1 key, prune new concepts. Returns the merged
    final and a funnel {proposed, verified, deduplicated, kept, pruned} plus the names kept."""
    funnel = {
        "proposed": len(extra["new_concepts"]) + len(extra["existing_mentions"]),
        "verified": 0,
        "deduplicated": 0,
        "pruned": 0,
        "kept": 0,
        "kept_names": [],
    }
    if not funnel["proposed"]:
        return final, funnel
    vr = verify(extra, vctx)
    kept, _dropped = drop_flagged(vr.out, vr.flags)
    funnel["verified"] = len(kept["new_concepts"]) + len(kept["existing_mentions"])
    have = {r1_key(c["name"], cfg) for c in final["new_concepts"]} | {
        r1_key(a, cfg) for c in final["new_concepts"] for a in c["aliases"]
    }
    have_m = {(m["node_id"], r1_key(m["surface"], cfg)) for m in final["existing_mentions"]}
    merged = {k: list(v) for k, v in final.items()}
    for c in kept["new_concepts"]:
        k = r1_key(c["name"], cfg)
        if k in have:
            funnel["deduplicated"] += 1
            continue
        if pruner is not None and pruner(c["name"]) < tau:
            funnel["pruned"] += 1
            continue
        have.add(k)
        merged["new_concepts"].append(c)
        funnel["kept"] += 1
        funnel["kept_names"].append(c["name"])
    for m in kept["existing_mentions"]:
        k = (m["node_id"], r1_key(m["surface"], cfg))
        if k in have_m:
            funnel["deduplicated"] += 1
            continue
        have_m.add(k)
        merged["existing_mentions"].append(m)
        funnel["kept"] += 1
        funnel["kept_names"].append(m["surface"])
    return merged, funnel
