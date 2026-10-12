"""CR-013 deterministic explanation renderer. Text is produced ONLY from structured trace fields through fixed templates; no model is called and no rationale is
generated. A stored rationale is shown as "Recorded model reason". A missing value renders the literal `NOT_RECORDED`. Every dynamic piece of a sentence is a segment
bound to a trace field, so `verify_support` can prove that each factual value shown equals the field it came from."""

from __future__ import annotations

import re

from cumap.explain.trace import NOT_RECORDED, TraceEvent

RENDERER_VERSION = "r1"
PLACEHOLDER = re.compile(r"\{([A-Za-z_.0-9]+)\}")

STAGE_INFO = {
    "source": "The source text is the retained textbook section the system read.",
    "generator": "The concept generator proposes candidate concepts and mentions from the text; a proposal is not yet a final graph node.",
    "verifier": "The verifier checks proposals with deterministic rules (evidence must be verbatim, spans must be consistent) and records flags, corrections and rejections.",
    "correction": "A correction step re-asks for or repairs proposals flagged by the verifier.",
    "pruner": "The pruner scores each candidate and drops low-scoring ones; in this run it was configured not to drop anything.",
    "canonicalisation": "Canonicalisation decides which names are the same concept (one node with aliases); it is about identity, not about semantic relations.",
    "pair_generation": "Pair generation lists the concept pairs that co-occur in a sentence and are eligible for a relation check.",
    "pair_selection": "Pair selection chooses which eligible pairs are sent to relation classification, under a budget with coverage rules.",
    "relation_classification": "Relation classification asks, for a selected pair, whether the sentence states a relation from the registry, and in which direction.",
    "validation": "Validation checks the classified relation: evidence grounding, endpoint grounding, and type constraints.",
    "graph_commit": "Graph commit writes the accepted concepts and edges to the final knowledge graph.",
    "organisation": "Organisation reorganises the already-built graph for structural importance and communities; it does not decide whether a fact is true.",
}

# (stage, action prefix) -> sentences. Placeholders are dotted trace-field paths.
T: dict[tuple[str, str], list[str]] = {
    ("source", "unit_text"): [
        "This unit of source text ({attrs.unit}) belongs to a textbook section; its text hash is {attrs.section_text_sha256}."
    ],
    ("generator", "proposed"): [
        "The generator proposed “{attrs.name}” as a candidate {attrs.node_type}; it was not yet a final KG node.",
        "Recorded model reason: {attrs.recorded_reason}.",
    ],
    ("generator", "mention_recorded"): [
        "The phrase “{attrs.surface}” was recorded as a mention (role: {attrs.role}) in section {section_id}."
    ],
    ("generator", "g_link_accepted"): [
        "The generator linked “{attrs.surface}” to an existing node (rule {rule_id}; outcome: {outcome})."
    ],
    ("generator", "g_link_rejected"): [
        "The generator link of “{attrs.surface}” to an existing node was rejected (rule {rule_id}; outcome: {outcome})."
    ],
    ("generator", "alias_link"): [
        "“{attrs.alias}” was recorded as a name for this concept (outcome: {outcome}; rule: {rule_id}). Recorded reason: {attrs.recorded_reason}."
    ],
    ("verifier", "autofix"): ["Verifier rule {rule_id} automatically corrected: {attrs.what}."],
    ("verifier", "flag_raised"): ["Verifier rule {rule_id} flagged: {attrs.detail}."],
    ("verifier", "hint_raised"): [
        "Verifier rule {rule_id} raised a hint ({attrs.type}) about “{attrs.text}”: {attrs.detail}."
    ],
    ("verifier", "candidate_rejected"): [
        "The candidate “{attrs.surface}” was rejected by verifier rule(s) {reason_code}."
    ],
    ("verifier", "hint_rejected"): [
        "The hint about “{attrs.text}” was rejected (rule {rule_id}). Recorded model reason: {attrs.recorded_reason}."
    ],
    ("pruner", "prune_score"): [
        "The pruner recorded a score of {score} for “{attrs.name}” (threshold: {threshold}); outcome: {outcome}."
    ],
    ("canonicalisation", "alias_link"): [
        "“{attrs.alias}” was linked to this concept (outcome: {outcome}; rule: {rule_id}; similarity: {score}). Recorded reason: {attrs.recorded_reason}."
    ],
    ("canonicalisation", "taxonomy_candidate"): [
        "A taxonomy decision “{reason_code}” was recorded relative to {output_refs}; outcome: {outcome} (the names were not merged into one concept). Recorded reason: {attrs.recorded_reason}."
    ],
    ("canonicalisation", "merge_review"): [
        "A merge review of “{attrs.alias}” against {attrs.candidate} was recorded (similarity {score}); outcome: {outcome}. Recorded reason: {attrs.recorded_reason}."
    ],
    ("canonicalisation", "v4_node_to_concept"): [
        "Generator node {attrs.v4_node} resolves to this concept by an exact name join (key: {join.key}). This is a deterministic join, not a recorded decision."
    ],
    ("pair_generation", "pool_pair_replayed"): [
        "REPLAYED layer (recomputed by the frozen selection code; not originally recorded): this pair was an eligible candidate with cue score {score} and co-occurrence count {attrs.cooccurrence_count}."
    ],
    ("pair_generation", "related_candidate"): [
        "Canonicalisation listed these two concepts as related candidates."
    ],
    ("pair_generation", "anchor_pair_join"): [
        "This pair came from an anchor record (anchor type: {attrs.anchor_type}; join key {join.key}); cue: {attrs.cue}."
    ],
    ("pair_generation", "misconception_verification_pair"): [
        "This pair was created by the misconception-verification step, not by pair selection. Origin: {attrs.origin}."
    ],
    ("pair_generation", "anchor_candidate"): [
        "These two concepts were paired because one was anchored to the other (anchor type: {attrs.anchor_type})."
    ],
    ("pair_selection", "selected_recorded"): [
        "This pair was selected for relation classification (recorded). The run selected {budget} pairs from {eligible_count} eligible pairs; cue score {score}.",
        "Pair origin (from the retained pair id): {attrs.origin}.",
        "Rank and selection phase for this pair: NOT_RECORDED in the original run.",
    ],
    ("pair_selection", "unselected_sample_recorded"): [
        "This pair was NOT selected; it is one of the retained unselected sample pairs used to measure what selection leaves out (cue score {score})."
    ],
    ("pair_selection", "rank_replayed"): [
        "REPLAYED layer (recomputed by the frozen selection code and verified to reproduce the retained selected set exactly; not originally recorded): this pair ranked {rank} out of {eligible_count} eligible pairs by cue score; the run's budget was {budget}; outcome: {outcome}."
    ],
    ("relation_classification", "classify_pair"): [
        "The relation classifier outcome for this pair was {outcome} (reason code: {reason_code}); model {model_id}, prompt version {prompt_version}.",
        "Recorded decision: relation {attrs.relation}, direction {attrs.direction}, family {attrs.family}. Recorded model reason: {attrs.family_reason}.",
        "Recorded evidence quote: “{attrs.evidence_quote}”.",
    ],
    ("validation", "validate_relation"): [
        "Validation outcome: {outcome} (reason code: {reason_code}); evidence grounding: {attrs.grounding}; type errors: {attrs.type_errors}."
    ],
    ("graph_commit", "commit_node"): [
        "This concept was committed to the graph; first introduced in chapter {attrs.first_introduced_chapter}."
    ],
    ("graph_commit", "commit_edge"): [
        "This edge was committed to the graph: relation {attrs.relation}, from section {section_id}."
    ],
    ("graph_commit", "edge_to_relation_row"): [
        "The committed edge resolves to its relation-classification row by an exact pair-id join (key: {join.key}). This is a deterministic join."
    ],
    ("organisation", "org_event"): [
        "The organisation layer recorded “{reason_code}” in chapter {attrs.chapter} (from {attrs.from_state} to {attrs.to_state}). This reorganises the existing graph; it does not decide whether a fact is true."
    ],
}
FALLBACK = ["{stage}: {action} (outcome: {outcome})."]


def fmt(v) -> str:
    if v is None or v == "":
        return NOT_RECORDED
    if isinstance(v, float):
        return f"{v:.3f}"
    if isinstance(v, (list, tuple)):
        return ", ".join(fmt(x) for x in v) if v else NOT_RECORDED
    if isinstance(v, dict):
        return "; ".join(f"{k}={fmt(x)}" for k, x in v.items()) if v else NOT_RECORDED
    return str(v)


def render_template(template: str, get) -> list[dict]:
    segs, pos = [], 0
    for m in PLACEHOLDER.finditer(template):
        if m.start() > pos:
            segs.append({"text": template[pos : m.start()], "field": None})
        segs.append({"text": fmt(get(m.group(1))), "field": m.group(1)})
        pos = m.end()
    if pos < len(template):
        segs.append({"text": template[pos:], "field": None})
    return segs


def render_event(e: TraceEvent) -> dict:
    key = (e.stage, e.action.split(":")[0].split("#")[0])
    templates = T.get(key)
    if templates is None and e.stage == "organisation":
        templates = T[("organisation", "org_event")]
    templates = templates or FALLBACK
    get = lambda path: e.get(path)
    sentences = []
    for t in templates:
        segs = render_template(
            t.replace("{stage}", e.stage).replace("{action}", e.action) if t is FALLBACK[0] else t,
            get,
        )
        sentences.append({"text": "".join(s["text"] for s in segs), "segments": segs})
    return {
        "event_id": e.event_id, "renderer_version": RENDERER_VERSION, "stage": e.stage, "authority": e.authority, "layer": e.layer, "object_id": e.object_id,
        "stage_info": STAGE_INFO[e.stage], "sentences": sentences, "text": " ".join(s["text"] for s in sentences),
        "support": sorted({s["field"] for sent in sentences for s in sent["segments"] if s["field"] and fmt(get(s["field"])) != NOT_RECORDED}),
        "unrecorded": sorted({s["field"] for sent in sentences for s in sent["segments"] if s["field"] and fmt(get(s["field"])) == NOT_RECORDED}),
    }  # fmt: skip


def verify_support(e: TraceEvent, rendered: dict) -> list[str]:
    """Every dynamic segment must equal the formatted trace field it is bound to (a missing field must show NOT_RECORDED). Returns the violations."""
    bad = []
    for sent in rendered["sentences"]:
        for s in sent["segments"]:
            if s["field"] and s["text"] != fmt(e.get(s["field"])):
                bad.append(f"{e.event_id}:{s['field']}")
    return bad


def render_pair_rank_example(rank: int, eligible: int, budget: int, selected: bool) -> str:
    """CR-style stand-alone sentence for fixtures: states only the recorded numbers and the recorded outcome (selection also uses coverage phases, so rank alone is not a cut-off)."""
    return f"The pair ranked {rank} out of {eligible} eligible candidates; the run's budget was {budget}; outcome: {'selected' if selected else 'not selected'}."
