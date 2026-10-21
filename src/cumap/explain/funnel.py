"""Concept-count funnel for the KG explorer's right-hand panel (derived, read-only, gold-free).

The browser computes the same numbers from the trace payload (`conceptFunnel` in `kg_explorer_trace.js`); this module is the
reference used by the parity test. Every step is a count of distinct things recorded in the retained trace:

1. candidates the generator offered = proposed nodes + candidates the checks rejected as *new concepts*
   (rejected *existing-concept mentions* are mentions of a concept that already exists, so they are not counted here);
2. after the checks = proposed nodes;
3. after the filter = proposed nodes minus those the pruner recorded as pruned (none are recorded in the retained runs);
4. after merging duplicate names = distinct final concepts the nodes map to (+ any node with no recorded mapping);
5. in the final graph;
6. with at least one relation in the final graph.

A step that does not follow from the previous one by its recorded removals gets an explicit "unaccounted" amount (never hidden).
"""

from __future__ import annotations

STEP_KEYS = ["candidates", "after_checks", "after_filter", "after_merge", "final", "linked"]


def _sec(e: dict) -> str:
    return (e.get("section_id") or "").split("#")[0]


def _edge_ends(payload: dict) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for e in payload["events"]:
        if e["stage"] == "graph_commit" and str(e["action"]) == "commit_edge":
            a = e.get("attrs") or {}
            out[e["object_id"].split(":", 1)[1]] = (
                a.get("source_concept_id"),
                a.get("target_concept_id"),
            )
    return out


def concept_funnel(payload: dict, scope: str | None = None) -> dict:
    """Funnel for the whole book (`scope=None`) or one section id."""
    secs = payload["sections"]
    chosen = [scope] if scope else list(secs)
    final_set = set(payload["final_concepts"])
    proposed = [p for s in chosen for p in secs[s].get("proposed", [])]
    ev = payload["events"]
    in_scope = (lambda e: _sec(e) == scope) if scope else (lambda e: True)
    rejected_new = sum(
        1
        for e in ev
        if e["stage"] == "verifier"
        and str(e["action"]).split(":")[0] == "candidate_rejected"
        and (e.get("attrs") or {}).get("kind") == "new_concepts"
        and in_scope(e)
    )
    pruned = sum(
        1 for e in ev if e["stage"] == "pruner" and e["outcome"] == "rejected" and in_scope(e)
    )
    pruned_unrecorded = sum(
        1 for e in ev if e["stage"] == "pruner" and e["outcome"] == "not_recorded" and in_scope(e)
    )
    mapped = {p[4] for p in proposed if p[4]}
    unmapped = sum(1 for p in proposed if not p[4])
    after_merge = len(mapped) + unmapped
    final = len(final_set) if not scope else len({c for c in mapped if c in final_set})
    ends = _edge_ends(payload)
    edge_ids = payload["final_edges"] if not scope else secs[scope].get("edges", [])
    linked_set = {c for i in edge_ids for c in ends.get(i, ()) if c in final_set}
    if scope:  # a section's linked concepts: its own final concepts that carry an edge anywhere in the final graph
        all_linked = {c for a, b in ends.values() for c in (a, b)}
        linked_set = {c for c in mapped if c in final_set and c in all_linked}
    n_prop = len(proposed)
    steps = [
        {"key": "candidates", "n": n_prop + rejected_new, "removed": None, "unaccounted": 0},
        {"key": "after_checks", "n": n_prop, "removed": rejected_new, "unaccounted": 0},
        {"key": "after_filter", "n": n_prop - pruned, "removed": pruned, "unaccounted": 0},
        {
            "key": "after_merge",
            "n": after_merge,
            "removed": n_prop - pruned - after_merge,
            "unaccounted": 0,
        },
        {"key": "final", "n": final, "removed": after_merge - final, "unaccounted": 0},
        {
            "key": "linked",
            "n": len(linked_set),
            "removed": final - len(linked_set),
            "unaccounted": 0,
        },
    ]
    # the merge step is derived from the mapping, so its removal is by construction; the final step must be explained by a
    # recorded cause. Nothing records a removal between "merged" and "final", so any difference is shown as unaccounted.
    steps[4]["unaccounted"] = steps[4]["removed"]
    return {
        "scope": scope or "all",
        "steps": steps,
        "pruned_unrecorded": pruned_unrecorded,
        "unmapped_nodes": unmapped,
    }
