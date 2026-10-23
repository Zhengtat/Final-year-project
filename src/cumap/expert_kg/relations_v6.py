"""CR-038 DRAFT ($0, mock-tested only, never run): the per-relation qualifier schema and the dimension-quote choice schema of prompts v6, behind
`qualifier_amendments: "off" | "v6"` (default off; handoff section 10 changes 1-4, 6).

* `build_qualifiers_v6(registry, relation)`: a flat LLM schema with only the qualifiers the registry's `applies_to` gives that relation (every edge:
  polarity, modality, conditions, surface_phrase; `part_type` only for part_of, `action_type` only for acts_on, ...). Every field required and not
  null, no defaults, no extra properties. No `dimension` field.
* `build_relation_choice_v6(...)`: the v3 choice schema with `dimension_quote` in place of the paraphrased `comparison_dimension`: for contrasts_with an
  exact substring of the sentence (rule 3), replacing the paraphrase lemma match that turned 18 comparisons into no_relation.
* `surface_phrase_errors`: the surface phrase must be an exact substring of the evidence quote and shorter than it (the linking words only)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model

from cumap.schemas.relations import RelationRegistry

AMENDMENT_MODES = ("off", "v6")
DIMENSION_RELATIONS_V6 = frozenset(
    {"contrasts_with"}
)  # trades_off_with is not in any adopted registry
REQUIRED_REGISTRY_NOTE = (
    "qualifier_amendments v6 needs a registry whose modality has no `never` (relations_v1.5)"
)


def resolve_amendments(mode: str | None = None) -> str:
    """Explicit argument, else `qualifier_amendments` in `configs/relation_policy.yaml` (default "off"; a bare YAML `off` is False)."""
    if mode is None:
        import yaml

        from cumap.config import REPO_ROOT

        p = REPO_ROOT / "configs/relation_policy.yaml"
        mode = (
            (yaml.safe_load(p.read_text()) or {}).get("qualifier_amendments", "off")
            if p.exists()
            else "off"
        )
    if mode is False:
        mode = "off"
    if mode not in AMENDMENT_MODES:
        raise ValueError(f"qualifier_amendments must be one of {AMENDMENT_MODES}, got {mode!r}")
    return mode


def check_registry_for_v6(registry: RelationRegistry) -> None:
    mod = registry.qualifiers.get("modality")
    if mod is not None and "never" in (mod.values or []):
        raise ValueError(REQUIRED_REGISTRY_NOTE)
    if "dimension" in registry.qualifiers:
        raise ValueError(
            "qualifier_amendments v6 needs a registry without the `dimension` qualifier (relations_v1.5)"
        )


def applicable_qualifiers(registry: RelationRegistry, relation: str) -> list[str]:
    forward = registry.get(relation).name
    return [
        n
        for n, q in registry.qualifiers.items()
        if q.applies_to == "all" or forward in q.applies_to
    ]


def _py_type(q):
    if q.values:
        return Literal[*q.values]
    if q.type and q.type.startswith("list"):
        return list[str]
    return str


def build_qualifiers_v6(registry: RelationRegistry, relation: str) -> type[BaseModel]:
    fields = {
        n: (_py_type(registry.qualifiers[n]), ...)
        for n in applicable_qualifiers(registry, relation)
    }
    return create_model("QualifiersV6LLM", __config__=ConfigDict(extra="forbid"), **fields)


def qualifier_fields_block(registry: RelationRegistry, relation: str) -> str:
    """The prompt block that lists exactly the fields asked for this relation (from the registry's values and notes)."""
    lines = []
    for n in applicable_qualifiers(registry, relation):
        q = registry.qualifiers[n]
        what = (
            " | ".join(f'"{v}"' for v in q.values)
            if q.values
            else (
                "a list of short phrases from the quote (empty list if none)"
                if (q.type or "").startswith("list")
                else "a string"
            )
        )
        note = (q.note or "").strip()
        note = (note[0].upper() + note[1:] + ("" if note.endswith(".") else ".")) if note else ""
        lines.append(f"- {n}: {what}." + (f" {note}" if note else ""))
    return "\n".join(lines)


def build_relation_choice_v6(
    registry: RelationRegistry, family: str, same_concept: bool = False
) -> type[BaseModel]:
    from cumap.expert_kg.relations_v3 import build_relation_choice_v3

    return build_relation_choice_v3(
        registry, family, same_concept, dimension_field="dimension_quote"
    )


def surface_phrase_errors(surface_phrase: str | None, evidence_quote: str | None) -> list[str]:
    sp, q = " ".join((surface_phrase or "").split()), " ".join((evidence_quote or "").split())
    errs = []
    if not sp or sp not in q:
        errs.append("surface_phrase_not_in_quote")
    elif len(sp) >= len(q):
        errs.append("surface_phrase_not_shorter")
    return errs


def render_fields_check(block: str) -> bool:
    return not re.search(r"[{}]", block)
