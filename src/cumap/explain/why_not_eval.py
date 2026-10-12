"""CR-013 `Why not?` EVALUATION mode: attaches the frozen CR-012 earliest-failure code to a gold relation. This module is the only explain module that touches
evaluation machinery, and it is imported only by the evaluation overlay; production code never imports it."""

from __future__ import annotations

from cumap.explain.why_not import CODE_TEXT

EVAL_TEXT = {
    **CODE_TEXT,
    "N1": "A gold endpoint was extracted, but with a span that does not match the gold span exactly.",
    "C0": "A gold concept was split across several nodes and the split lost the pair.",
    "C1": "A node merged two different gold concepts (a false merge), so the endpoint is not a faithful node.",
    "R1": "The pair was classified but the relation chosen is not the gold relation.",
    "R2": "The right relation was chosen in the wrong direction.",
}


def localise(facts: dict) -> dict:
    """facts: the per-gold-edge trace facts (the same fields as `cumap.cr012.attribution.EdgeTrace`). -> {"code": str|None, "text": str}."""
    from cumap.cr012.attribution import EdgeTrace, attribute

    t = EdgeTrace(
        endpoints=tuple(facts["endpoints"]), span_status=tuple(facts["span_status"]), false_merge=tuple(facts["false_merge"]), split=tuple(facts["split"]), pairs_proposed=tuple(facts["pairs_proposed"]),
        no_relation=tuple(facts["no_relation"]), predicted_relations=tuple(facts["predicted_relations"]), gold_relation=facts["gold_relation"], symmetric=facts["symmetric"],
        reversed_only=facts["reversed_only"], types_ok=facts["types_ok"], qualifiers_ok=facts["qualifiers_ok"], evidence_valid=facts["evidence_valid"],
    )  # fmt: skip
    code = attribute(t)
    return {
        "code": code,
        "text": EVAL_TEXT[code] if code else "The gold edge is present in the final graph.",
        "scope": "EVALUATION (frozen CR-012 attribution order)",
    }
