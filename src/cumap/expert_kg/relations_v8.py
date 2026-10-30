"""CR-059 DRAFT: relation choice with an endpoint-fit judgement instead of the node-type domain/range check (type-free runs, owner choice b).

`endpoint_check: "types"` (default, every earlier run) keeps the registry domain/range check; `"choice"` uses prompt relation_choice v8, whose
schema adds `endpoint_fit` (closed choice) and `endpoint_fit_reason`; a chosen relation with endpoint_fit "does_not_fit" is rejected with
reason `endpoint_fit`, logged like domain_range. Set per run by the benchmark profile; the P&D production path is unchanged."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, create_model

from cumap.schemas.relations import RelationRegistry

ENDPOINT_CHECKS = ("types", "choice")
FIT = ("fits", "does_not_fit")


def resolve_endpoint_check(value: str | None = None) -> str:
    """Explicit value, else the active benchmark profile's `endpoint_check`, else "types"."""
    if value is None:
        from cumap.cr012.schema_profile import active_profile

        p = active_profile()
        value = (p.raw.get("endpoint_check") if p else None) or "types"
    if value not in ENDPOINT_CHECKS:
        raise ValueError(f"endpoint_check must be one of {ENDPOINT_CHECKS}, not {value!r}")
    return value


def build_relation_choice_v8(
    registry: RelationRegistry, family: str, same_concept: bool = False
) -> type[BaseModel]:
    from cumap.expert_kg import relations_v6 as R6

    base = R6.build_relation_choice_v6(registry, family, same_concept)
    return create_model(
        "RelationChoiceV8LLM",
        __base__=base,  # keeps extra='forbid' and the 'other needs text' validator
        endpoint_fit=(Literal[FIT], ...),  # type: ignore[valid-type]
        endpoint_fit_reason=(str, ...),
    )
