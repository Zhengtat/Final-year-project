"""CR-010 STOP 3: what an eRST label may and may not do to the Expert KG. An eRST relation is discourse evidence between
discourse units; it never creates a domain edge by itself (CR-008: equivalence is a node property, not an edge; the
lexicon outranks every automatic rule). Every decision names its reason so an audit can show it."""

from __future__ import annotations

from dataclasses import dataclass

from cumap.erst.registry import ErstRegistry, UnknownErstLabel

# the effect vocabulary a label may have outside the discourse graph
PAIR_PRIORITY = "pair_priority_hint"  # CR-010 P3: eRST is pair-selection evidence only
SAME_CONCEPT_CANDIDATE = (
    "same_concept_candidate"  # canonicalisation evidence, through the lexicon-guarded merge
)
DOCUMENT_STRUCTURE = "document_structure"
DOMAIN_EDGE = "domain_edge"

CONTRAST_RELATIONS = frozenset({"contrasts_with", "trades_off_with"})
RETIRED_EDGE_NAMES = frozenset({"equivalent_to", "same_as", "synonym_of"})


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def check_kg_effect(
    reg: ErstRegistry,
    label: str,
    effect: str,
    *,
    relation: str | None = None,
    independent_domain_evidence: bool = False,
    grounded_dimension: bool = False,
) -> Decision:
    """Is `effect` (optionally naming the domain relation) allowed for an eRST `label`? Unknown labels raise."""
    rel = reg.get(label)  # fail closed
    if not rel.is_true_discourse_relation:
        return Decision(False, "SAME-UNIT is a technical device: no semantic or KG effect")
    if relation in RETIRED_EDGE_NAMES:
        return Decision(
            False, f"{relation} is never an edge: equivalence is a node property (CR-008)"
        )
    if effect == PAIR_PRIORITY:
        return Decision(True, "eRST is pair-selection evidence only")
    if effect == SAME_CONCEPT_CANDIDATE:
        ok = label.startswith("RESTATEMENT-")
        return Decision(
            ok,
            "restatement may queue a same-concept candidate only"
            if ok
            else "only RESTATEMENT-* may",
        )
    if effect == DOCUMENT_STRUCTURE:
        ok = label.startswith("ORGANIZATION-")
        return Decision(
            ok,
            "organisation labels describe document structure"
            if ok
            else "not an organisation label",
        )
    if effect != DOMAIN_EDGE:
        return Decision(False, f"unknown effect {effect!r}")
    # a domain edge never comes from the label alone
    if label.startswith("ORGANIZATION-"):
        return Decision(False, "organisation labels are document structure only")
    if label == "JOINT-LIST" and relation in CONTRAST_RELATIONS:
        return Decision(
            False, "a list is not a contrast: no automatic contrasts_with / trades_off_with"
        )
    if label == "CONTINGENCY-CONDITION" and relation == "prerequisite_of":
        return Decision(False, "a condition is not a prerequisite: no automatic prerequisite_of")
    if label.startswith("RESTATEMENT-"):
        return Decision(False, "restatement is canonicalisation evidence, never a domain edge")
    if not independent_domain_evidence:
        return Decision(False, "a domain edge needs independent domain-semantic evidence")
    if (
        label == "ADVERSATIVE-CONTRAST"
        and relation in CONTRAST_RELATIONS
        and not grounded_dimension
    ):
        return Decision(False, "the grounded-dimension requirement for contrasts remains")
    return Decision(True, "independent domain-semantic evidence present")


def signal_licenses_domain_relation(kind: str, subtype: str | None, relation: str) -> bool:
    """A discourse signal (even a semantic one: synonymy, meronymy, antonymy, repetition) is evidence for a discourse
    analysis, never a licence for a domain relation or a merge."""
    return False


def merge_gate(lexicon, a: str, b: str) -> Decision:
    """eRST restatement / synonymy evidence may only QUEUE a same-concept candidate, and a pair the term lexicon marks
    `different` is rejected here too (CR-008: the lexicon outranks every automatic rule)."""
    if lexicon is not None and lexicon.is_different(a, b):
        return Decision(False, "approved lexicon `different` pair: never merged")
    return Decision(True, "queued as a candidate only; the CR-008 merge pipeline decides")


__all__ = [
    "Decision",
    "UnknownErstLabel",
    "check_kg_effect",
    "merge_gate",
    "signal_licenses_domain_relation",
]
