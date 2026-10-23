"""CR-035 identity resolver, deterministic part U0-U4 ($0, no model call; `identity_resolver: legacy | u1`, default legacy).

One set of rules for every candidate source (A generator link, B new concept against the registry, C a `same_concept` queue pair). The rules are the
existing CR-008 machinery (`canonical_rules.AliasContext.pair_rule`) seen through one door, so the same pair gets the same decision whichever path found
it. The first rule that decides wins:

    U0 lexicon `different` -> keep apart   U1 lexicon `same` -> merge   U2 same name form (exact / R1 key) -> merge
    U3 acronym <-> long form in the text -> merge   U4-strong textbook alias statement -> merge   U4-weak cue -> review (never merges, rule 19)

A pair no rule decides is `undecided`: the caller falls back to today's LLM path (rejected-link adjudicator for A, `canonicalize` for B), which is the
U5 judge until `prompts/identity_judge` exists. Node types must be compatible for U2-U4 (U0 and U1 do not need them)."""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from cumap.config import REPO_ROOT
from cumap.expert_kg.canonical_rules import AliasContext, RuleHit

RULES_PATH = REPO_ROOT / "configs/identity_rules.yaml"
LEGACY_TO_U = {"R0": "U1", "exact": "U2", "R1": "U2", "R2": "U3", "R3-strong": "U4-strong"}
U_TO_LEGACY = {"U1": "R0", "U2": "R1", "U3": "R2", "U4-strong": "R3-strong"}


@dataclass(frozen=True)
class IdentityDecision:
    decision: str  # keep_apart | merge | review | undecided
    rule_id: str | None  # U0 | U1 | U2 | U3 | U4-strong | U4-weak | None (undecided)
    evidence_quote: str | None = None
    legacy_rule_id: str | None = (
        None  # the pre-CR-035 id of the same rule (R0 / R1 / R2 / R3-strong)
    )


UNDECIDED = IdentityDecision("undecided", None)


def load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))


def from_hit(hit: RuleHit) -> IdentityDecision:
    return IdentityDecision("merge", LEGACY_TO_U[hit.rule_id], hit.evidence_quote, hit.rule_id)


def resolve_deterministic(
    ctx: AliasContext,
    a: str,
    b: str,
    *,
    chapter: int | None = None,
    a_type: str = "Concept",
    b_type: str = "Concept",
    type_aware: bool = True,
) -> IdentityDecision:
    """U0-U4 for two surface forms. `ctx` carries the lexicon, the alias config and the textbook alias statements."""
    if ctx.lexicon.is_different(a, b, chapter):
        ctx.stats["blocked_by_lexicon"] += 1
        return IdentityDecision("keep_apart", "U0", legacy_rule_id=None)
    hit = ctx.pair_rule(a, b, chapter, a_type=a_type, b_type=b_type, type_aware=type_aware)
    if hit is not None:
        return from_hit(hit)
    if ctx.weak_hints(a, b):
        from cumap.expert_kg.canonical_rules import types_compatible

        if not type_aware or types_compatible(a_type, b_type):
            return IdentityDecision("review", "U4-weak", ctx.weak_hints(a, b)[0].quote)
    return UNDECIDED


def resolve_against_forms(
    ctx: AliasContext,
    surface: str,
    forms: list[str],
    *,
    chapter: int | None = None,
    surface_type: str = "Concept",
    node_type: str = "Concept",
    type_aware: bool = True,
) -> IdentityDecision:
    """Input A: the generator linked `surface` to a node. A U0 veto against any form of the node wins; otherwise the best merge rule over the node's forms
    (U1 before U2 before U3 before U4-strong); otherwise a weak cue (review); otherwise undecided."""
    ds = [
        resolve_deterministic(
            ctx,
            surface,
            f,
            chapter=chapter,
            a_type=surface_type,
            b_type=node_type,
            type_aware=type_aware,
        )
        for f in forms
    ]
    for d in ds:
        if d.decision == "keep_apart":
            return d
    order = ["U1", "U2", "U3", "U4-strong"]
    merges = [d for d in ds if d.decision == "merge"]
    if merges:
        return min(merges, key=lambda d: order.index(d.rule_id))
    return next((d for d in ds if d.decision == "review"), UNDECIDED)
