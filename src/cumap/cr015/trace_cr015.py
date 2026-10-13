"""CR-015 trace for the frozen A2 run (CR §25): `boundary_family`, `concept_validity` and `mention_placement` events (additive stages; historical stages untouched), built from the
saved A2 outputs. Each placed mention links (input_refs) to the selector decision and the verifier verdict that justify it; each accepted-but-unplaced occurrence is an explicit
`blocked` placement event with a reason. No free-form reasoning is stored.

    uv run python -m cumap.cr015.trace_cr015                  # builds data/processed/cr015/stageA/trace_A2.jsonl and reports/cr015/trace_coverage.json"""

from __future__ import annotations

import json
from pathlib import Path

from cumap.cr014.union import SectionUnion, surface_regex
from cumap.cr015 import placement as PL
from cumap.cr015.dev_data import DevSection
from cumap.explain.trace import TraceEvent, TraceStore, make_event_id

ROOT = Path(".")
OUT = ROOT / "data/processed/cr015/stageA"
FREEZE = json.loads((ROOT / "reports/cr015/FREEZE_A2.json").read_text())
CONFIG_HASH = FREEZE["hashes"]["configs/cr014_concept_extraction.yaml"][:16]
LABEL_OUTCOME = {
    "KEEP_PRIMARY": "accepted",
    "KEEP_NESTED": "accepted",
    "EXPAND_TO": "corrected",
    "SHRINK_TO": "corrected",
}


def build_section(
    d: DevSection, u: SectionUnion, a2: dict, store: TraceStore, arm: str = "A2"
) -> dict:
    run_id = f"cr015_stageA_{arm}"
    art = f"data/processed/cr015/stageA/{arm}_{d.sid}.json"
    by_id = {c.cid: c for c in u.cands.values()}
    fam = {f.fid: f for f in u.families}
    sel_prompt, ver_prompt = a2["meta"]["selector_prompt"], a2["meta"]["verifier_prompt"]

    def add(stage, oid, action, outcome, locator, authority, **kw):
        eid = make_event_id(run_id, stage, oid, action, locator)
        store.add(TraceEvent(event_id=eid, run_id=run_id, dataset_mode="pd", document_id="pd6e", section_id=d.sid, stage=stage, object_type="span", object_id=oid,
                             action=action, outcome=outcome, authority=authority, source_artifact=art, source_locator=locator, config_hash=CONFIG_HASH, **kw))  # fmt: skip
        return eid

    bf_event: dict[
        tuple[str, str], str
    ] = {}  # (family id, surface) -> event id of the decision that kept it
    for fid, ds in a2["decisions"].items():
        f = fam[fid]
        for dd in ds:
            c = by_id.get(dd["candidate_id"])
            if c is None:
                continue
            outcome = LABEL_OUTCOME.get(dd["label"], "rejected")
            target = (dd["target_surface"] or "").lower() or None
            eid = add("boundary_family", f"{fid}:{c.cid}", "boundary_label", outcome, f"{d.sid}/{fid}/{c.cid}", "MODEL", model_id="gpt-6-luna", prompt_version=sel_prompt,
                      reason_code=dd["reason_code"], attrs={"family_id": fid, "label": dd["label"], "input_surface": c.surface, "target_surface": target, "family_members": len(f.members)})  # fmt: skip
            if outcome != "rejected":
                bf_event[(fid, target or c.surface)] = eid
    for fid, sels in a2["selected"].items():
        f = fam[fid]
        if len(f.members) == 1:
            s = next(iter(sels))
            bf_event[(fid, s)] = add("boundary_family", f"{fid}:{f.members[0]}", "pass_through", "accepted", f"{d.sid}/{fid}", "RULE", reason_code="single_member_family", attrs={"family_id": fid, "input_surface": s})  # fmt: skip
    cv_event: dict[str, str] = {}
    for surf, v in a2["verdicts"].items():
        ok = v.get("verdict") in ("ACCEPT_NEW", "LINK_EXISTING")
        cv_event[surf] = add("concept_validity", surf, "verdict", "accepted" if ok else "rejected", f"{d.sid}/verdict/{surf}", "MODEL", model_id="gpt-6-luna", prompt_version=ver_prompt,
                             reason_code=v.get("reason_code") or v.get("verdict"), attrs={"verdict": v.get("verdict"), "surface": surf})  # fmt: skip
    placed = {tuple(x) for x in a2["spans"]}
    accepted = set(a2["accepted"])
    n_placed = n_blocked = 0
    for fid, sels in a2["selected"].items():
        for s in sels:
            if s not in accepted:
                continue
            for occ in fam[fid].occurrences:
                for sp in PL.spans_inside_occurrence(u, s, occ):
                    if sp in placed:
                        add("mention_placement", f"{d.sid}:{sp[0]}-{sp[1]}", "placed", "accepted", f"{d.sid}/{sp[0]}-{sp[1]}/{fid}", "RULE", input_refs=[bf_event[(fid, s)], cv_event[s]] if (fid, s) in bf_event else [cv_event[s]],
                            attrs={"surface": s, "start": sp[0], "end": sp[1], "family_id": fid})  # fmt: skip
                        n_placed += 1
    done = {
        (e.attrs["start"], e.attrs["end"])
        for e in store.events.values()
        if e.stage == "mention_placement" and e.section_id == d.sid and e.action == "placed"
    }
    for s in sorted(accepted):
        for m in surface_regex(s).finditer(d.text):
            sp = (m.start(), m.end())
            if sp in done:
                continue
            add("mention_placement", f"{d.sid}:{sp[0]}-{sp[1]}:{s}", "suppressed", "blocked", f"{d.sid}/{sp[0]}-{sp[1]}/{s}", "RULE", input_refs=[cv_event[s]], reason_code="surface_not_kept_by_selector_in_this_family",
                attrs={"surface": s, "start": sp[0], "end": sp[1]})  # fmt: skip
            n_blocked += 1
    return {"placed": n_placed, "blocked": n_blocked}


def main() -> dict:
    from cumap.cr015.dev_data import load_dev
    from cumap.cr015.stage_a import unions

    dev = load_dev()
    us = unions(dev)
    store = TraceStore()
    counts = {}
    for d in dev:
        a2 = json.loads((OUT / f"A2_{d.sid}.json").read_text())
        counts[d.sid] = build_section(d, us[d.sid], a2, store)
    path = OUT / "trace_A2.jsonl"
    store.to_jsonl(path)
    cov = coverage(store)
    cov["per_section"] = counts
    cov["path"] = str(path)
    Path("reports/cr015/trace_coverage.json").write_text(json.dumps(cov, indent=1))
    return cov


def coverage(store: TraceStore) -> dict:
    ev = list(store.events.values())
    placed = [e for e in ev if e.stage == "mention_placement" and e.action == "placed"]
    blocked = [e for e in ev if e.stage == "mention_placement" and e.action == "suppressed"]
    ids = set(store.events)
    linked_both = sum(
        1 for e in placed if len(e.input_refs) == 2 and all(r in ids for r in e.input_refs)
    )
    linked_any = sum(1 for e in placed if e.input_refs and all(r in ids for r in e.input_refs))
    bf = [e for e in ev if e.stage == "boundary_family"]
    return {
        "events": len(ev), "boundary_family_events": len(bf), "concept_validity_events": sum(e.stage == "concept_validity" for e in ev), "placed_mentions": len(placed), "suppressed_occurrences": len(blocked),
        "placed_with_selector_and_verifier_links": linked_both, "placed_with_resolvable_links": linked_any,
        "placed_link_coverage": linked_any / len(placed) if placed else None,
        "suppressed_with_verifier_link": sum(1 for e in blocked if e.input_refs and e.input_refs[0] in ids),
        "all_events_have_model_prompt_config": all((e.authority == "RULE" or (e.model_id and e.prompt_version)) and e.config_hash for e in ev),
    }  # fmt: skip


def why_placed(store: TraceStore, section: str, start: int, end: int) -> list[str]:
    """Answers 'why was this span placed / chosen here?' from the trace (selector label, verifier verdict)."""
    out = []
    for e in store.events.values():
        if (
            e.stage == "mention_placement"
            and e.section_id == section
            and e.attrs.get("start") == start
            and e.attrs.get("end") == end
        ):
            out.append(f"{e.action}: {e.attrs['surface']!r} ({e.reason_code or 'ok'})")
            for r in e.input_refs:
                x = store.events[r]
                out.append(
                    f"  <- {x.stage}: {x.attrs.get('label') or x.attrs.get('verdict')} / {x.reason_code}"
                )
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
