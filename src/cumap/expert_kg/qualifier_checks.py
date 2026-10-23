"""CR-034 qualifier code checks ($0, no model call; switch `qualifier_checks: off | v1`, default off).

Three checks on a classified edge (handoff §10 change 5):
* `qualifier_misfit`      a qualifier is set although the registry's `applies_to` excludes the relation (for example `part_type` on `is_a`);
* `negation_without_cue`  polarity `negated` but the evidence quote contains no negation cue. Under `v1` the edge is REJECTED with this reason
                          (owner default D-4) and the rejection is logged in the pair's result;
* `surface_phrase_long`   the surface phrase is not shorter than the evidence quote (it should be the linking words only).

`qualifier_misfit` and `surface_phrase_long` are recorded as flags on the result (`qualifier_flags`) and do not reject: with the old prompt versions
22% of edges copy the whole quote, so rejecting would cut the graph. A later prompt version (CR-038) is what removes them. Older runs keep their
stored values; the checks only run for NEW classifications when the switch is `v1`."""

from __future__ import annotations

import re

MODES = ("off", "v1")
REJECT_REASON = "negation_without_cue"
NEGATION_CUE = re.compile(
    r"\b(?:not|no|never|without|cannot|neither|nor)\b|n['’]t\b|\bindependent of\b",
    re.IGNORECASE,
)


def _norm(s: str | None) -> str:
    return " ".join((s or "").split())


def _is_set(v) -> bool:
    return v not in (None, "", [], False)


def has_negation_cue(quote: str | None) -> bool:
    return bool(NEGATION_CUE.search(quote or ""))


def misfit_qualifiers(registry, relation: str, qualifiers: dict) -> list[str]:
    """Names of qualifiers that are set although the registry limits them to other relations."""
    out = []
    for name, qdef in registry.qualifiers.items():
        if name not in qualifiers or not _is_set(qualifiers[name]):
            continue
        if qdef.applies_to != "all" and relation not in qdef.applies_to:
            out.append(name)
    return sorted(out)


def check_edge(registry, relation: str, qualifiers: dict, evidence_quote: str | None) -> list[str]:
    """Flag codes for one edge, in a fixed order: `qualifier_misfit:<name>`, `negation_without_cue`, `surface_phrase_long`."""
    flags = [f"qualifier_misfit:{n}" for n in misfit_qualifiers(registry, relation, qualifiers)]
    if qualifiers.get("polarity") == "negated" and not has_negation_cue(evidence_quote):
        flags.append(REJECT_REASON)
    sp, q = _norm(qualifiers.get("surface_phrase")), _norm(evidence_quote)
    if sp and q and len(sp) >= len(q):
        flags.append("surface_phrase_long")
    return flags


def resolve_mode(mode: str | None = None) -> str:
    """The explicit argument wins; else `configs/relation_policy.yaml` (`qualifier_checks`, default off)."""
    if mode is None:
        import yaml

        from cumap.config import REPO_ROOT

        p = REPO_ROOT / "configs/relation_policy.yaml"
        mode = (
            (yaml.safe_load(p.read_text()) or {}).get("qualifier_checks", "off")
            if p.exists()
            else "off"
        )
    if mode is False:  # an unquoted `off` in YAML parses as False
        mode = "off"
    if mode not in MODES:
        raise ValueError(f"qualifier_checks must be one of {MODES}, got {mode!r}")
    return mode
