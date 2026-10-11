"""CR-013 `Why not?` localiser, PRODUCTION mode: inspects the retained trace stage by stage for two concepts and stops at the earliest OBSERVABLE loss.

It uses only trace data (no gold, no scorer output) and never claims that a missing edge should exist. Production codes: N0 (endpoint concept not in the final
graph), P0 (pair not delivered: not an eligible pair, or eligible but not selected), R0 (classifier chose no relation / other), R3 (validation rejected the relation on
type or qualifier grounds), E0 (validation rejected it because an endpoint or evidence was not grounded). Identity (C0 / C1) and wrong relation or direction (R1 / R2)
need a reference and exist only in evaluation mode (`why_not_eval`)."""

from __future__ import annotations

from collections import defaultdict

from cumap.explain.render import fmt, render_template
from cumap.explain.trace import NOT_RECORDED, TraceStore

CODE_TEXT = {
    "N0": "At least one of the two concepts is not a node of the final graph, so no relation between them can exist.",
    "P0": "The pair was never sent to relation classification, so the classifier had no opportunity to decide whether a semantic relation exists.",
    "R0": "The pair was sent to relation classification and the classifier recorded that no accepted relation was stated for it.",
    "R3": "A relation was proposed for the pair but validation rejected it on a type or qualifier check.",
    "E0": "A relation was proposed for the pair but validation rejected it because an endpoint or the evidence could not be grounded.",
}
E0_REASONS = {"endpoint_not_grounded"}
RANK_SENTENCE = "The pair ranked {rank} out of {eligible_count} eligible pairs ({rank_layer} rank); the run's budget was {budget}. Selection also uses a per-section minimum, anchor and coverage phases, so rank alone is not a cut-off."
REASON_SENTENCE = "Recorded reason code: {reason_code}."


CHECK_LABELS = {
    "final": "{c} is a node of the final graph?", "identity": "identity of the two concepts valid?", "eligible": "eligible pair generated?", "selected": "selected for relation classification?",
    "classified": "relation classification outcome", "validated": "passed validation?", "committed": "edge committed to the graph?",
}  # fmt: skip


def check_id(check: str) -> str:
    for cid, label in CHECK_LABELS.items():
        if check == label or (cid == "final" and check.endswith("is a node of the final graph?")):
            return cid
    raise KeyError(check)


def pair_index(store: TraceStore) -> dict[frozenset, list[str]]:
    idx: dict[frozenset, list[str]] = defaultdict(list)
    for eid in store.by_stage.get("pair_selection", []):
        e = store.events[eid]
        refs = [r for r in e.input_refs if r.startswith("concept:")]
        if len(refs) == 2:
            idx[frozenset(refs)].append(e.object_id)
    return {k: sorted(set(v)) for k, v in idx.items()}


def _indexes(store: TraceStore) -> dict:
    cached = getattr(store, "_why_not_idx", None)
    if cached is not None:
        return cached
    rel_by_pair: dict[str, list] = defaultdict(list)
    for i in store.by_stage.get("relation_classification", []):
        e = store.events[i]
        for r in e.input_refs:
            rel_by_pair[r].append(e)
    edge_by_row: dict[str, list] = defaultdict(list)
    for i in store.by_stage.get("graph_commit", []):
        e = store.events[i]
        if e.object_type == "edge" and e.action == "edge_to_relation_row":
            for r in e.input_refs:
                edge_by_row[r].append(e)
    replayed = any(
        store.events[i].layer == "REPLAYED" for i in store.by_stage.get("pair_selection", [])[:200]
    )
    store._why_not_idx = {"rel": rel_by_pair, "edge": edge_by_row, "replayed": replayed}  # type: ignore[attr-defined]
    return store._why_not_idx  # type: ignore[attr-defined]


def why_not(store: TraceStore, concept_a: str, concept_b: str, idx: dict | None = None) -> dict:
    """concept ids with the `concept:` prefix. -> {"checks": [...], "earliest_failure": code|None, "status": ..., "sentences": [...]}."""
    idx = idx if idx is not None else pair_index(store)
    ix = _indexes(store)
    checks: list[dict] = []
    final: str | None = None

    def add(check, answer, events=(), fields=None, note=None):
        checks.append(
            {
                "id": check_id(check),
                "check": check,
                "answer": answer,
                "event_ids": [e.event_id for e in events],
                "fields": fields or {},
                "note": note,
            }
        )

    ends_ok = True
    for c in (concept_a, concept_b):
        committed = [e for e in store.for_object(c, "graph_commit") if e.action == "commit_node"]
        add(f"{c} is a node of the final graph?", "yes" if committed else "no", committed)
        ends_ok &= bool(committed)
    if not ends_ok:
        final = "N0"
    add(
        "identity of the two concepts valid?",
        "not_assessed_in_production",
        note="needs a reference; see evaluation mode",
    )
    key = frozenset((concept_a, concept_b))
    pairs = idx.get(key, [])
    rows = []
    if final is None:
        replay = [e for p in pairs for e in store.for_object(p, "pair_selection", "REPLAYED")]
        recorded_sel = [e for p in pairs for e in store.for_object(p, "pair_selection", "RECORDED")]
        if pairs:
            add("eligible pair generated?", "yes", replay or recorded_sel)
        elif ix["replayed"]:
            add(
                "eligible pair generated?",
                "no",
                note="not in the replayed eligible pool (REPLAYED layer)",
            )
            final = "P0"
        else:
            add(
                "eligible pair generated?",
                "unknown",
                note=f"{NOT_RECORDED}: the eligible pool is not retained and no valid replay layer is present",
            )
        if final is None and pairs:
            sel = [e for e in recorded_sel if e.outcome == "selected"]
            rk = replay[0] if replay else None
            fields = {
                "rank": rk.rank if rk else None,
                "eligible_count": (rk or recorded_sel[0]).eligible_count,
                "budget": (rk or recorded_sel[0]).budget,
            }
            fields["rank_layer"] = "REPLAYED" if rk else "NOT_RECORDED"
            if sel or (rk and rk.outcome == "selected"):
                add("selected for relation classification?", "yes", sel or [rk], fields)
            else:
                add(
                    "selected for relation classification?",
                    "no",
                    [x for x in (rk, *recorded_sel) if x],
                    fields,
                )
                final = "P0"
        if final is None and pairs:
            rows = sorted(
                {e.event_id: e for p in pairs for e in ix["rel"].get(p, [])}.values(),
                key=lambda e: e.event_id,
            )
            if not rows:
                add(
                    "relation classification outcome",
                    "unknown",
                    note=f"{NOT_RECORDED}: no retained classification row for the selected pair",
                )
            else:
                emitted = [e for e in rows if e.outcome == "emitted"]
                add(
                    "relation classification outcome",
                    "relation_proposed" if emitted else "no_relation",
                    rows,
                    {"reason_code": rows[0].reason_code},
                )
                if not emitted:
                    final = "R0"
        if final is None and rows:
            val = [e for r in rows for e in store.for_object(r.object_id, "validation")]
            rej = [e for e in val if e.outcome == "rejected"]
            if rej:
                add("passed validation?", "no", rej, {"reason_code": rej[0].reason_code})
                final = "E0" if rej[0].reason_code in E0_REASONS else "R3"
            else:
                add("passed validation?", "yes", val)
                edge = [e for r in rows for e in ix["edge"].get(r.object_id, [])]
                add(
                    "edge committed to the graph?",
                    "yes" if edge else "no",
                    edge,
                    note=None if edge else "validated but no committed edge was found: trace gap",
                )
    status = (
        "edge_exists"
        if final is None
        and checks
        and checks[-1]["answer"] == "yes"
        and checks[-1]["check"].startswith("edge committed")
        else ("lost" if final else "unknown")
    )
    sentences = []
    if final:
        sentences.append(render_template(CODE_TEXT[final], lambda p: None))
        last = checks[-1]
        if last["fields"].get("rank") is not None:
            f = last["fields"]
            sentences.append(
                render_template(
                    RANK_SENTENCE,
                    lambda p, f=f: f.get(p),
                )
            )
        if last["fields"].get("reason_code"):
            sentences.append(render_template(REASON_SENTENCE, lambda p, f=last["fields"]: f.get(p)))
    return {"concept_a": concept_a, "concept_b": concept_b, "checks": checks, "earliest_failure": final, "status": status,
            "sentences": ["".join(s["text"] for s in segs) for segs in sentences], "note": "production mode: a missing edge is never claimed to be a missing true relation"}  # fmt: skip


__all__ = ["CODE_TEXT", "fmt", "pair_index", "why_not"]
