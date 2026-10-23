"""CR-014 trace for Stage B runs: PROPOSAL, BOUNDARY_REPAIR and verifier events (CR-013 TraceEvent vocabulary, additive stages only).
Built from a saved arm output; lineage proposed -> deduplicated -> family-grouped -> boundary decision -> verified/rejected. No chain-of-thought."""

from __future__ import annotations

import json
from pathlib import Path

from cumap.cr014.stage_b import CFG, OUT, load_dev, unions
from cumap.explain.trace import TraceEvent, TraceStore, make_event_id


def build(arm: str, tag: str = "") -> dict:
    d = json.loads((OUT / f"{arm}{tag}.json").read_text())
    meta = d["meta"]
    nlp, sections, emph, _g, out0 = load_dev()
    us = unions(nlp, sections, emph, out0)
    run_id = f"cr014_stageB_{arm}{tag}"
    store = TraceStore()
    art = f"data/processed/cr014/stageB/{arm}{tag}.json"
    model = CFG["stage_b"]["model_tier"] if arm != "V0" else None

    def add(stage, sid, oid, action, outcome, locator, authority, **kw):
        store.add(TraceEvent(event_id=make_event_id(run_id, stage, oid, action, locator), run_id=run_id, dataset_mode="other",
                             document_id="iir_dev", section_id=sid, stage=stage, object_type="span", object_id=oid, action=action,
                             outcome=outcome, authority=authority, source_artifact=art, source_locator=locator, **kw))  # fmt: skip

    for sid, u in us.items():
        sec = d["sections"][sid]
        fam_of: dict[str, list[str]] = {}
        for f in u.families:
            for m in f.members:
                fam_of.setdefault(m, []).append(f.fid)
        for c in u.cands.values():
            add("proposal", sid, c.cid, "proposed", "emitted", f"{sid}/{c.cid}", "RULE" if c.sources - {"llm_iter0"} else "MODEL",
                attrs={"surface": c.surface, "sources": sorted(c.sources), "start": c.start_offset, "end": c.end_offset,
                       "token_length": c.token_length, "occurrences": c.count, "families": fam_of.get(c.cid, [])})  # fmt: skip
        for fid, decs in sec["boundary"].items():
            f = next(x for x in u.families if x.fid == fid)
            by = {c.cid: c.surface for c in u.cands.values()}
            add("boundary_repair", sid, fid, "boundary_decision", "corrected" if any(x["decision"] != "KEEP" for x in decs) else "accepted",
                f"{sid}/{fid}", "MODEL", model_id=model, prompt_version=meta["prompt_b"], reason_code=decs[0]["reason_code"] if decs else None,
                attrs={"overlap_family": fid, "members": {m: by[m] for m in f.members}, "decisions": decs})  # fmt: skip
        for cid, v in sec["verdicts"].items():
            if cid.startswith("_"):
                continue
            ok = v.get("verdict") in {"ACCEPT_NEW", "LINK_EXISTING", "RULES_AND_PRUNER"}
            add("verifier", sid, cid, "verdict", "accepted" if ok else "rejected", f"{sid}/{cid}", "MODEL" if arm != "V0" else "RULE",
                model_id=model, prompt_version=meta["prompt_v"], reason_code=v.get("reason_code") or v.get("verdict"),
                attrs={"surface": v.get("surface"), "verdict": v.get("verdict")})  # fmt: skip
    path = OUT / f"trace_{arm}{tag}.jsonl"
    store.to_jsonl(path)
    n_prop = len(store.by_stage.get("proposal", []))
    cands = {e.object_id for e in store.events.values() if e.stage == "proposal"}
    verified = {e.object_id for e in store.events.values() if e.stage == "verifier"}
    return {"arm": arm, "events": len(store.events), "proposal_events": n_prop, "boundary_events": len(store.by_stage.get("boundary_repair", [])),
            "verifier_events": len(verified), "candidates_with_verifier_event": len(cands & verified), "path": str(path)}  # fmt: skip


if __name__ == "__main__":
    out = [build(a) for a in ("V1", "V2", "V3")]
    Path(OUT / "trace_manifest.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
