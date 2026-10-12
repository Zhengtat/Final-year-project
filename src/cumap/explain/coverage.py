"""CR-013 trace coverage, evidence resolvability, explanation support and honesty checks over a built trace. Read-only."""

from __future__ import annotations

import re
from collections import Counter

from cumap.explain.lineage import Lineage, norm, resolve
from cumap.explain.render import NOT_RECORDED, fmt, render_event, verify_support
from cumap.explain.trace import STAGES, TraceStore


def resolves(ref: str) -> bool:
    v = resolve(ref)
    return isinstance(v, str) and bool(v.strip())


def coverage(
    store: TraceStore,
    lin: Lineage,
    finals: dict[str, str],
    sec_text: dict[str, str],
    gaps: list[dict],
) -> dict:
    gap_objects = {g["object_id"] for g in gaps if g["scope"] == "object" and g["object_id"]}
    out: dict = {"final_objects": {}, "evidence": {}, "explanations": {}}
    unit_stages: dict[str, set[str]] = {}
    for e in store.events.values():
        if e.object_id.startswith("cand:"):
            unit_stages.setdefault(e.object_id.split(":")[1], set()).add(e.stage)
    for kind in ("concept", "edge"):
        ids = sorted(o for o, t in finals.items() if t == kind)
        reached, with_gap, stage_presence, no_evidence, unit_scoped = 0, 0, Counter(), [], Counter()
        for oid in ids:
            tb = lin.trace_back(oid)
            ok = bool(tb["evidence"]) and all(resolves(r) for r in tb["evidence"])
            reached += ok
            if not ok:
                no_evidence.append(oid)
            if (
                ok
                or oid in gap_objects
                or any(
                    g["object_id"] in tb["nodes"]
                    for g in gaps
                    if g["scope"] == "object" and g["object_id"]
                )
            ):
                with_gap += 1
            present = {
                store.events[i].stage for n in tb["nodes"] for i in store.by_object.get(n, [])
            }
            stage_presence.update(present)
            scoped: set[str] = set()
            for n_id in tb[
                "nodes"
            ]:  # verifier events attach to a unit, not to a concept: UNIT-SCOPED presence
                if n_id.startswith("unit:"):
                    scoped |= unit_stages.get(n_id[5:], set())
            unit_scoped.update(scoped)
        n = len(ids) or 1
        out["final_objects"][kind] = {
            "count": len(ids), "lineage_reaches_resolvable_evidence": reached, "pct_lineage_to_evidence": 100 * reached / n,
            "covered_incl_documented_gaps": with_gap, "pct_covered_incl_documented_gaps": 100 * with_gap / n,
            "stage_presence_pct": {s: round(100 * stage_presence.get(s, 0) / n, 1) for s in STAGES},
            "unit_scoped_stage_presence_events_in_a_unit_the_object_comes_from": {s: n_ for s, n_ in sorted(unit_scoped.items())}, "without_evidence_examples": no_evidence[:10],
        }  # fmt: skip
    refs = {r for e in store.events.values() for r in e.evidence_refs} | {
        r for rs in lin.evidence.values() for r in rs
    }
    unresolved = sorted(r for r in refs if not resolves(r))
    q_checked = q_found = q_missing_rejected = q_elsewhere = 0
    mism: dict[str, dict] = {}
    all_norm = {k: norm(v) for k, v in sec_text.items()}
    by_kind: Counter = Counter()
    q_missing: list[str] = []
    for e in store.events.values():
        base = (e.section_id or "").split("#")[0]
        if base not in sec_text:
            continue
        text = norm(sec_text[base])
        for r in e.evidence_refs:
            v = resolve(r)
            if isinstance(v, str) and v.strip():
                q_checked += 1
                if norm(v) in text:
                    q_found += 1
                elif ".rejected[" not in r and sum(norm(v) in t for t in all_norm.values()) >= 1:
                    q_elsewhere += 1  # verbatim in other section(s) only: a section-attribution mismatch (ambiguous when several), reported, never corrected
                    mism.setdefault(
                        e.object_id,
                        {
                            "object_id": e.object_id,
                            "section_id": e.section_id,
                            "found_in": [k for k, t in all_norm.items() if norm(v) in t],
                            "evidence_ref": r,
                        },
                    )
                else:
                    q_missing_rejected += ".rejected[" in r
                    if ".rejected[" not in r:
                        by_kind[re.sub(r"\[\d+\]", "[]", r.split("::")[1])] += 1
                    if len(q_missing) < 10:
                        q_missing.append(r)
    out["evidence"] = {
        "refs_total": len(refs), "refs_resolving": len(refs) - len(unresolved), "pct_locators_resolve": 100 * (len(refs) - len(unresolved)) / max(len(refs), 1), "unresolved_examples": unresolved[:10],
        "quote_in_source_text_checked": q_checked, "quote_in_source_text_found": q_found, "pct_quote_in_source_text": 100 * q_found / max(q_checked, 1), "quote_not_found_examples": q_missing, "quote_not_found_in_verifier_rejected_candidates": q_missing_rejected, "quote_not_found_but_verbatim_in_other_sections": q_elsewhere, "section_attribution_mismatches": list(mism.values()), "quote_not_found_other_by_locator_kind": dict(by_kind),
    }  # fmt: skip
    segs = bad = unrec_ok = unrec_total = 0
    sentences = 0
    for e in store.events.values():
        r = render_event(e)
        bad += len(verify_support(e, r))
        for sent in r["sentences"]:
            sentences += 1
            for s in sent["segments"]:
                if s["field"]:
                    segs += 1
                    if fmt(e.get(s["field"])) == NOT_RECORDED:
                        unrec_total += 1
                        unrec_ok += s["text"] == NOT_RECORDED
    out["explanations"] = {
        "events_rendered": len(store.events), "sentences": sentences, "dynamic_segments": segs, "support_violations": bad, "pct_supported": 100 * (segs - bad) / max(segs, 1),
        "unrecorded_fields_rendered_as_NOT_RECORDED": f"{unrec_ok}/{unrec_total}", "pct_unknown_honesty": 100 * unrec_ok / max(unrec_total, 1),
    }  # fmt: skip
    out["gaps"] = {
        "total": len(gaps),
        "by_status": dict(Counter(g["status"] for g in gaps)),
        "by_stage": dict(Counter(g["stage"] for g in gaps)),
    }
    return out
