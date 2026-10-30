"""CR-059: domain profiles for the type-free generator prompt (`concept_generator/v7`).

A profile (`configs/domain_profiles/<name>_vN.yaml`) holds everything domain-specific the generator sees: the document kind, a domain
description, the specificity policy, which kinds of concept (the fixed checklist below) the domain extracts, an "always a concept" list, a
"never on its own" list and span conventions. No node types. Only a profile with `status: approved` is loaded (the owner approves a draft
from `cumap.cr059.draft`; code never approves). Every term in a profile carries the quote it was drafted from (rule 3)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

# The domain-independent checklist: kinds of thing a concept can be, in any technical domain. A profile switches each on or off.
CATEGORIES: dict[str, str] = {
    "named_artifact": "named systems, models, tools, software, standards or products",
    "technique": "algorithms, methods, procedures, and mathematical or statistical techniques",
    "component": "parts or mechanisms inside a larger system, model or device",
    "task": "tasks, problems, processes or operations the text performs, solves or studies",
    "resource": "datasets, corpora, benchmarks, collections and data structures",
    "measure": "measures, metrics, scores and quantities used to evaluate or describe something",
    "property": "properties, states and conditions of things",
    "phenomenon": "phenomena, effects and events",
    "field": "research areas, subfields and disciplines",
    "setting": "settings, configurations and scenarios in which something is done or tested",
}
Category = Literal[*CATEGORIES]  # type: ignore[valid-type]
SCOPE_TEXT = {
    "named_instances": (
        "Extract a concept only when the text names a specific one: a named system, technique, resource, task or measure. A "
        "generic word for a whole area or a kind of thing is not extracted on its own; extract it only as part of a specific name."
    ),
    "field_terms": (
        "Extract every term that has a specific technical meaning in the field, including general terms for kinds of things "
        "(for example the name of a class of devices or processes), not only named instances."
    ),
}
ACRONYM_TEXT = {
    "long_form_with_acronym_alias": '- When the text writes "long form ( ACRONYM )", the name is the long form and the acronym is an alias.',
    "keep_parenthesised_acronym_in_span": (
        '- When the text writes "long form ( ACRONYM )", the span includes the parenthesised acronym as written.'
    ),
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuotedTerm(_Strict):
    """A profile term with its evidence. A committed profile keeps only `quote_sha256` (SciNLP text is CC BY-NC); the quote itself sits in a
    gitignored evidence file, checked by `verify_evidence`."""

    term: str
    quote: str | None = None
    quote_sha256: str | None = None


class CategoryEntry(_Strict):
    include: bool
    scope: Literal["named_only", "any"]
    examples: list[QuotedTerm]
    reason: str | None = (
        None  # the drafter's one-sentence reason (internal model, not an LLM schema)
    )


class DomainProfile(_Strict):
    name: str
    version: int
    status: Literal["draft", "approved"]
    document_kind: str
    domain: str
    domain_description: str
    specificity: Literal["named_instances", "field_terms"]
    specificity_reason: str | None = None
    categories: dict[Category, CategoryEntry]  # type: ignore[valid-type]
    always_concepts: list[QuotedTerm]
    not_alone: list[QuotedTerm]
    acronym_convention: Literal[
        "long_form_with_acronym_alias", "keep_parenthesised_acronym_in_span"
    ]
    keep_variant_modifier: bool
    provenance: dict


def load_domain_profile(path: Path, *, require_approved: bool = True) -> DomainProfile:
    prof = DomainProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if require_approved and prof.status != "approved":
        raise ValueError(
            f"{path} is a {prof.status} profile: only an owner-approved profile can drive a run"
        )
    missing = set(CATEGORIES) - set(prof.categories)
    if missing:
        raise ValueError(f"{path} does not decide the categories {sorted(missing)}")
    return prof


def quote_hash(quote: str) -> str:
    import hashlib

    return hashlib.sha256(" ".join(quote.split()).encode("utf-8")).hexdigest()


def split_evidence(profile: dict) -> tuple[dict, dict]:
    """(profile with quote hashes only, evidence {sha256: quote}) from a drafted profile dict."""
    import copy

    prof, ev = copy.deepcopy(profile), {}

    def strip(items: list[dict]) -> None:
        for t in items:
            q = t.pop("quote", None)
            if q:
                h = quote_hash(q)
                t["quote_sha256"], ev[h] = h, " ".join(q.split())

    for c in prof["categories"].values():
        strip(c["examples"])
    strip(prof["always_concepts"])
    strip(prof["not_alone"])
    return prof, ev


def verify_evidence(prof: DomainProfile, evidence: dict[str, str]) -> list[str]:
    """Terms whose quote is missing from the evidence file, whose hash does not match, or that are not inside their quote."""
    bad = []
    items = [
        *prof.always_concepts,
        *prof.not_alone,
        *(e for c in prof.categories.values() for e in c.examples),
    ]
    for t in items:
        q = evidence.get(t.quote_sha256 or "") if t.quote is None else t.quote
        if (
            q is None
            or quote_hash(q) != (t.quote_sha256 or quote_hash(q))
            or t.term.lower() not in q.lower()
        ):
            bad.append(t.term)
    return bad


def _examples(entry: CategoryEntry, k: int = 4) -> str:
    ex = [e.term for e in entry.examples[:k]]
    return f" (for example {', '.join(ex)})" if ex else ""


def prompt_fields(prof: DomainProfile) -> dict[str, str]:
    """The v7 slots, rendered deterministically from the profile (no model call)."""
    inc, exc = [], []
    for name, gloss in CATEGORIES.items():
        e = prof.categories[name]
        if e.include:
            scope = "named ones only" if e.scope == "named_only" else "named or general"
            inc.append(f"- {gloss}: {scope}{_examples(e)}")
        else:
            exc.append(gloss)
    checklist = "\n".join(inc) or "- (none)"
    if exc:
        checklist += "\nNot concepts in this domain on their own: " + "; ".join(exc) + "."
    spans = [ACRONYM_TEXT[prof.acronym_convention]]
    if prof.keep_variant_modifier:
        spans.append("- A modifier that names the variant the text uses stays in the span.")
    return {
        "document_kind": prof.document_kind,
        "domain_description": prof.domain_description,
        "concept_scope": SCOPE_TEXT[prof.specificity],
        "category_checklist": checklist,
        "always_concepts": ", ".join(t.term for t in prof.always_concepts) or "(none)",
        "not_alone": ", ".join(f'"{t.term}"' for t in prof.not_alone) or "(none)",
        "span_conventions": "\n".join(spans),
    }
