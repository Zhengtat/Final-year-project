"""CR-039 DRAFT ($0, mock-tested only, never run): the misconception family in relation classification, behind
`misconception_source: "legacy" | "classification"` (default legacy; handoff section 14).

* `build_misconception_choice(registry)`: the closed-choice schema (rule 12) of the choice step for the `misconception` family: the WRONG statement (a
  registry relation or `conflated_with`, direction, polarity), the perturbation type, the CORRECT statement or `none`, two verbatim quotes. Every
  field required, no defaults, no extra properties.
* `build_relation_choice_v7(...)`: that schema for the misconception family, the v6 schema (CR-038) for every other family.
* `misconception_options_block`: the options shown to the choice step for the family.
Items built from these answers live only in the `misconception` layer (rule 22); see `misconception.layer_from_classification`."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model, model_validator

from cumap.expert_kg.misconception import CONFLATED, PERTURBATIONS, PREVALENCE
from cumap.schemas.relations import RelationRegistry

MISCONCEPTION_FAMILY = "misconception"
SOURCES = ("legacy", "classification")


def resolve_source(mode: str | None = None) -> str:
    """Explicit argument, else `misconception_source` in `configs/relation_policy.yaml` (default "legacy")."""
    if mode is None:
        import yaml

        from cumap.config import REPO_ROOT

        p = REPO_ROOT / "configs/relation_policy.yaml"
        mode = (
            (yaml.safe_load(p.read_text()) or {}).get("misconception_source", "legacy")
            if p.exists()
            else "legacy"
        )
    if mode not in SOURCES:
        raise ValueError(f"misconception_source must be one of {SOURCES}, got {mode!r}")
    return mode


def check_registry_for_misconceptions(registry: RelationRegistry) -> None:
    if MISCONCEPTION_FAMILY not in registry.families:
        raise ValueError(
            "misconception_source classification needs a registry with the misconception family (relations_v1.6)"
        )


def semantic_relation_names(registry: RelationRegistry) -> list[str]:
    return [r.name for r in registry.all_relations() if r.layer != "misconception"]


def build_misconception_choice(registry: RelationRegistry) -> type[BaseModel]:
    sem = tuple(semantic_relation_names(registry))
    wrong = (*sem, CONFLATED, "none")

    def _consistent(self):
        if self.is_misconception and (
            self.wrong_relation == "none"
            or self.perturbation_type == "none"
            or not self.misconception_quote
        ):
            raise ValueError(
                "a misconception needs wrong_relation, perturbation_type and misconception_quote"
            )
        return self

    return create_model(
        "MisconceptionChoiceLLM",
        __config__=ConfigDict(extra="forbid"),
        __validators__={"_consistent": model_validator(mode="after")(_consistent)},
        is_misconception=(bool, ...),
        wrong_relation=(Literal[*wrong], ...),
        wrong_direction=(Literal["forward", "reversed"], ...),
        wrong_polarity=(Literal["affirmed", "negated"], ...),
        perturbation_type=(Literal[*PERTURBATIONS, "none"], ...),
        correct_relation=(Literal[*sem, "none"], ...),
        correct_direction=(Literal["forward", "reversed"], ...),
        correct_polarity=(Literal["affirmed", "negated"], ...),
        misconception_quote=(str | None, ...),
        correction_quote=(str | None, ...),
        prevalence_cue=(Literal[*PREVALENCE], ...),
        reason=(str, ...),
    )


def build_relation_choice_v7(
    registry: RelationRegistry, family: str, same_concept: bool = False
) -> type[BaseModel]:
    if family == MISCONCEPTION_FAMILY:
        return build_misconception_choice(registry)
    from cumap.expert_kg.relations_v6 import build_relation_choice_v6

    return build_relation_choice_v6(registry, family, same_concept)


def misconception_options_block(registry: RelationRegistry, x: str, y: str) -> str:
    """Every registry relation as a possible WRONG (or correct) statement between X and Y, in both reading directions, plus conflated_with."""
    lines = []
    for rel in registry.all_relations():
        if rel.family == "pedagogical":
            continue
        lines.append(f"- {rel.name}: {rel.definition}")
        lines.append(f'    forward  (X first): "{registry.template_for(rel.name, x, y)}"')
        if rel.directional:
            lines.append(
                f'    reversed (Y first): "{registry.template_for(rel.name, x, y, reverse=True)}"'
            )
    lines.append(
        "- none: no statement of this kind (only for correct_relation, or wrong_relation when is_misconception is false)"
    )
    return "\n".join(lines)
