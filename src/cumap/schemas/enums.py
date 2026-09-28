"""Shared enums, exactly as listed in ARCHITECTURE.md."""

from __future__ import annotations

from enum import StrEnum


class NodeType(StrEnum):
    PROTOCOL = "Protocol"
    MECHANISM = "Mechanism"
    COMPONENT = "Component"
    DATA_UNIT = "DataUnit"
    PARAMETER = "Parameter"
    PROPERTY = "Property"
    EVENT = "Event"
    STATE = "State"
    LAYER = "Layer"
    CONCEPT = "Concept"
    ANY = "Any"  # registry domain/range wildcard only, never a real Concept.node_type


class ConceptStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MERGED = "merged"


class MentionRole(StrEnum):
    DEFINED = "defined"
    USED = "used"
    MENTIONED = "mentioned"


class EdgeLayer(StrEnum):
    STRUCTURE = "structure"
    TAXONOMY = "taxonomy"
    PREREQUISITE = "prerequisite"
    SEMANTIC = "semantic"
    MISCONCEPTION = "misconception"


class Polarity(StrEnum):
    AFFIRMED = "affirmed"
    NEGATED = "negated"


class Modality(StrEnum):
    NECESSARY = "necessary"
    ALWAYS = "always"
    TYPICALLY = "typically"
    POSSIBLE = "possible"
    NEVER = "never"


class Criticality(StrEnum):
    CORE = "core"
    SUPPORTING = "supporting"
    PERIPHERAL = "peripheral"


class QuestionLinkRole(StrEnum):
    REQUIRED = "required"
    BONUS = "bonus"


class QuestionLinkSource(StrEnum):
    REFERENCE_ANSWER = "reference_answer"
    FEEDBACK_RUBRIC = "feedback_rubric"
    TEXTBOOK = "textbook"


class ConfusableKind(StrEnum):
    EDGE = "edge"
    CONCEPT = "concept"


class ConfusableType(StrEnum):
    SUBSTITUTION = "substitution"
    REVERSAL = "reversal"
    TYPE_SWAP = "type_swap"
    CONDITION_SWAP = "condition_swap"


class ValidationStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class ItemStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MERGED = "merged"


class EdgeOrigin(StrEnum):
    TEXTBOOK = "textbook"
    REFERENCE_ANSWER = "reference_answer"
    MANUAL = "manual"


class Stance(StrEnum):
    ASSERTED = "asserted"
    HEDGED = "hedged"
    QUESTIONED = "questioned"
    QUOTED = "quoted"


class DecidedBy(StrEnum):
    RULE = "rule"
    LLM = "llm"


class MatchType(StrEnum):
    EXACT = "exact"
    PARAPHRASE = "paraphrase"
    PARTIAL_RELATION = "partial_relation"
    REVERSED = "reversed"
    POLARITY_FLIP = "polarity_flip"
    SUBSTITUTED_CONCEPT = "substituted_concept"
    MODALITY_ERROR = "modality_error"
    CONDITION_ERROR = "condition_error"
    WRONG_TYPE = "wrong_type"
    UNSUPPORTED_EXTRA = "unsupported_extra"
    VALID_EXTRA = "valid_extra"


class Verdict(StrEnum):
    CORRECT = "correct"
    INACCURATE = "inaccurate"
    CONTRADICTORY = "contradictory"
    IRRELEVANT = "irrelevant"


class PropositionLabelValue(StrEnum):
    EXPRESSED = "expressed"
    MISSING = "missing"
    CONTRADICTED = "contradicted"
    UNCLEAR = "unclear"


class AnswerLabel3Way(StrEnum):
    CORRECT = "correct"
    INCOMPLETE = "incomplete"
    CONTRADICTORY = "contradictory"


class MisconceptionSource(StrEnum):
    MINED_FROM_FEEDBACK = "mined_from_feedback"
    LITERATURE = "literature"
    MANUAL = "manual"
