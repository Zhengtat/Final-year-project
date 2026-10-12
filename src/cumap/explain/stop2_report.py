"""CR-013 STOP 2 report generator: reads the BUILT derived trace (never the gold) and writes `reports/cr013/stop2.md` with the schema, sample lineages,
coverage, replay verification, integrity proof and gaps. Read-only on the trace."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.explain.lineage import Lineage
from cumap.explain.render import render_event
from cumap.explain.trace import TraceEvent, TraceStore
from cumap.explain.why_not import pair_index, why_not

ROOT = REPO_ROOT / "data/processed/explainability"


def latest(run: str) -> Path:
    return max((ROOT / run).glob("*/manifest.json"), key=lambda p: p.stat().st_mtime).parent


def load(d: Path):
    store = TraceStore.from_jsonl(d / "trace_events.jsonl")
    lin = [
        json.loads(x) for x in (d / "object_lineage.jsonl").read_text().splitlines() if x.strip()
    ]
    return store, {r["object_id"]: r for r in lin}, json.loads((d / "manifest.json").read_text())


def chain(store: TraceStore, recs: dict, root: str, depth: int = 3) -> list[str]:
    """A compact walk toward the evidence, one line per object with its events (rendered text, authority, layer)."""
    lines, seen, frontier = [], {root}, [root]
    for level in range(depth + 1):
        nxt = []
        for oid in frontier:
            r = recs.get(oid)
            lines.append(
                f"{'  ' * level}- `{oid}`"
                + (
                    f" ({'; '.join(sorted({p['link'] + ('/' + p['layer'] if p['layer'] != 'RECORDED' else '') for p in r['parents']}))})"
                    if r and r["parents"]
                    else ""
                )
            )
            for eid in (r["event_ids"] if r else [])[:3]:
                e = store.events[eid]
                lines.append(
                    f"{'  ' * level}  - [{e.stage} · {e.authority} · {e.layer}] {render_event(e)['text'][:260]}"
                )
            for p in (r["parents"] if r else [])[:5]:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    nxt.append(p["id"])
            if r and r["evidence_refs"]:
                lines.append(
                    f"{'  ' * level}  - evidence: `{r['evidence_refs'][0]}` -> “{str(__import__('cumap.explain.lineage', fromlist=['resolve']).resolve(r['evidence_refs'][0]))[:140]}”"
                )
        frontier = nxt
    return lines


def main() -> None:
    d = latest("slice3_c2")
    store, recs, m = load(d)
    sd = latest("cr012_scinlp_heldout_P17_1058_grobid_E0")
    sm = json.loads((sd / "manifest.json").read_text())
    cov = m["coverage"]
    n_pass = (
        subprocess.run(
            ["uv", "run", "pytest", "-q", "tests/test_cr013_trace.py"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={**__import__("os").environ, "CUMAP_LLM_BACKEND": "mock"},
            check=False,
        )
        .stdout.strip()
        .splitlines()[-1]
    )
    finals_c = sorted(o for o, r in recs.items() if r["final"] and r["object_type"] == "concept")
    node = next(
        o
        for o in finals_c
        if sum(1 for p in recs[o]["parents"] if p["link"] == "canonical_of_v4_node") >= 2
        and any(e.startswith("te_") for e in recs[o]["event_ids"])
    )
    edge = next(
        o
        for o, r in sorted(recs.items())
        if r["final"] and r["object_type"] == "edge" and o.startswith("edge:RP-")
    )
    pool = [
        e
        for e in store.events.values()
        if e.action == "rank_replayed"
        and e.outcome == "not_selected"
        and e.rank
        and e.rank > (e.budget or 0)
        and not e.attrs.get("in_unselected_sample")
    ]
    pool.sort(key=lambda e: e.rank)
    pe = pool[0]
    a, b = [r for r in pe.input_refs if r.startswith("concept:")]
    wn = why_not(store, a, b, pair_index(store))
    lin = Lineage([], {}, {})
    del lin
    fields = [
        (
            n,
            str(f.annotation).replace("typing.", "").replace("<class '", "").replace("'>", ""),
            "required" if f.is_required() else f"default {f.default!r}"[:40],
        )
        for n, f in TraceEvent.model_fields.items()
    ]
    L = ["# CR-013 STOP 2: trace model", "",
         f"Base commit (Research D3): `{m['base_commit']}` (the exact audited `viz-kg-explorer` commit). Branch `cr-013-process-explainability`. Derived trace `{m['source_run_id']}/{m['explain_id']}` under `data/processed/explainability/` (gitignored). $0, no model call, no prediction change.", "",
         "## 1. Trace schema (`src/cumap/explain/trace.py`, version " + m["trace_schema_version"] + ")", "",
         "`TraceEvent` (pydantic, `extra=forbid`) has the CR 5.1 fields plus three provenance additions: `layer` (RECORDED / REPLAYED / JOINED), `join` (`{method, key}` for deterministic joins, Research D2) and `attrs` (stage-specific recorded values, never inferred).", "",
         "| field | type | |", "|---|---|---|"]  # fmt: skip
    L += [f"| `{n}` | `{t}` | {r} |" for n, t, r in fields]
    L += ["", "Stages: source, generator, verifier, correction, pruner, canonicalisation, pair_generation, pair_selection, relation_classification, validation, graph_commit, organisation. Outcomes and authorities as in the CR. Object ids keep the production ids behind a namespace prefix (`concept:`, `v4node:`, `mention:`, `unit:`, `pair:`, `relrow:`, `edge:`).", "",
          "## 2. Replay layer (Research D1)", "",
          f"The retained run kept only the selected pairs and aggregate stats. The frozen deterministic selection code was re-run (no model call) on the run's own retained concepts, anchors and the section texts. **Reproduction check: {'VALID' if m['replay']['valid'] else 'INVALID'}** (mismatches: {m['replay']['mismatches'] or 'none'}): the replay reproduces the retained selected pair ids in order, the retained 50-pair unselected sample and the retained selection stats exactly, and a second replay run is byte-identical (`deterministic = {m['replay'].get('deterministic')}`). Eligible pool {m['replay']['eligible_count']} pairs; budget 1,100. Replayed ranks are labelled `REPLAYED` everywhere and rendered as 'not originally recorded'. Rank is the position of the concept pair's best-ranked occurrence by cue score; selection also uses a per-section minimum, an anchor phase and a coverage phase, so rank alone is not a cut-off. The 226 anchor pairs (`AP-` ids) enter selection directly from the anchors, outside the enumerated pool, and carry no rank; 3 `MP-` verification pairs come from the misconception stage, not from pair selection.", "",
          "Code hashes used by the replay: " + ", ".join(f"`{k.split('/')[-1]}` `{v[:12]}`" for k, v in m["replay"]["code_hashes"].items()) + ".", "",
          "## 3. Sample lineages (read from the built trace; text is rendered by the deterministic renderer)", "", "### 3.1 A final node: `" + node + "`", ""]  # fmt: skip
    L += chain(store, recs, node, 2)
    L += ["", "### 3.2 A final edge: `" + edge + "`", ""] + chain(store, recs, edge, 3)
    L += [
        "",
        "### 3.3 A pair that was NOT delivered, with its `Why not?` answer",
        "",
        f"Pair `{pe.object_id}` between `{a}` and `{b}`:",
        "",
    ]
    L += [
        f"- [{e.stage} · {e.authority} · {e.layer}] {render_event(e)['text']}"
        for e in store.for_object(pe.object_id)
    ]
    L += ["", "`Why not?` (production mode):", ""] + [
        f"- {c['check']} -> **{c['answer']}**"
        + (f" ({c['fields']})" if c["fields"] else "")
        + (f" - {c['note']}" if c["note"] else "")
        for c in wn["checks"]
    ]
    L += ["", f"Earliest observable failure: **{wn['earliest_failure']}**. " + " ".join(wn["sentences"]), "",
          "## 4. Trace coverage (real `slice3_c2` build)", "", "| measure | value |", "|---|---|"]  # fmt: skip
    for kind in ("concept", "edge"):
        c = cov["final_objects"][kind]
        L.append(
            f"| final {kind}s whose lineage reaches resolvable evidence | {c['lineage_reaches_resolvable_evidence']} / {c['count']} = {c['pct_lineage_to_evidence']:.1f}% |"
        )
    ev, ex = cov["evidence"], cov["explanations"]
    L += [f"| evidence locators that resolve | {ev['refs_resolving']} / {ev['refs_total']} = {ev['pct_locators_resolve']:.1f}% |", f"| evidence quotes found in the source section text (informative; whitespace-normalised) | {ev['quote_in_source_text_found']} / {ev['quote_in_source_text_checked']} = {ev['pct_quote_in_source_text']:.1f}% (of the {ev['quote_in_source_text_checked'] - ev['quote_in_source_text_found']} not found, {ev['quote_not_found_in_verifier_rejected_candidates']} are evidence strings of verifier-rejected candidates (rule F2/F3: not verbatim); {ev['quote_not_found_but_verbatim_in_other_sections']} are verbatim only in OTHER section(s): the retained section id of that pair differs from the section(s) that contain its cited sentence (recorded as `SECTION_ATTRIBUTION_MISMATCH`, or `_AMBIGUOUS` when several sections contain it, with all section ids; nothing was corrected); {ev['quote_in_source_text_checked'] - ev['quote_in_source_text_found'] - ev['quote_not_found_in_verifier_rejected_candidates'] - ev['quote_not_found_but_verbatim_in_other_sections']} remain unexplained) |",
          f"| explanation sentences whose every value equals its trace field | {ex['dynamic_segments'] - ex['support_violations']} / {ex['dynamic_segments']} values = {ex['pct_supported']:.1f}% ({ex['sentences']} sentences over {ex['events_rendered']} events) |", f"| unrecorded fields rendered as NOT_RECORDED | {ex['unrecorded_fields_rendered_as_NOT_RECORDED']} = {ex['pct_unknown_honesty']:.1f}% |",
          f"| replay determinism (two builds, identical trace hash) | {m['replay_determinism_trace_hash_equal']} (`{m['trace_events_sha256'][:16]}…`) |", f"| events / lineage links / gaps | {m['counts']['events']} / {m['counts']['links']} / {m['counts']['gaps']} |", "",
          "Stage presence in the lineage of final objects (% of objects; verifier events attach to a generator unit, not to a concept, so they are counted unit-scoped):", "", "| stage | concepts | edges |", "|---|---|---|"]  # fmt: skip
    for s in cov["final_objects"]["concept"]["stage_presence_pct"]:
        L.append(
            f"| {s} | {cov['final_objects']['concept']['stage_presence_pct'][s]} | {cov['final_objects']['edge']['stage_presence_pct'][s]} |"
        )
    L += ["", f"Unit-scoped verifier presence for concepts (events in a unit the concept's mentions come from): {cov['final_objects']['concept']['unit_scoped_stage_presence_events_in_a_unit_the_object_comes_from']} of {cov['final_objects']['concept']['count']}.", "",
          "## 5. Trace gaps (kept explicit; nothing invented)", "", "| scope | stage | field | status | detail |", "|---|---|---|---|---|"]  # fmt: skip
    for g in (
        json.loads(x) for x in (d / "trace_gaps.jsonl").read_text().splitlines() if x.strip()
    ):
        L.append(
            f"| {g['scope']} {g['object_id'] or ''} | {g['stage']} | {g['field']} | {g['status']} | {g['detail']} |"
        )
    L += ["", "## 6. Tests", "", f"`tests/test_cr013_trace.py`: **{n_pass}**. Covered: hash identity before/after a build; TraceEvent round trip; deterministic ids and `extra=forbid`; lineage reaches evidence for a node and an edge; many-mentions-to-one-concept and many-evidence-to-one-edge DAG fan-in; joins carry method and key; renderer determinism and support verification (and a tampered sentence is detected); `NOT_RECORDED` rendering; rank above/below the boundary; recorded taxonomy guard stays separate; relation explanation from stored fields only; `Why not?` localises N0 / P0 (not eligible and not selected) / R0 / R3 / E0 and an existing edge; no `should exist` claim; unknown replay -> `unknown`; the frozen evaluation attribution localises N0, N1, C0, C1, P0, R0, R1, R2, R3, E0 and a recovered edge; production modules import no gold or evaluation code; coverage and gap honesty; build-twice identity; and the real `slice3_c2` build meets the integrity criteria.", "",
          "## 7. Source hash-integrity proof", "", f"`source_hashes_unchanged = {m['source_hashes_unchanged']}`: the SHA-256 of every source artifact was taken before the build and again after writing all outputs, and the two maps are identical.", "", "| source artifact | sha256 (before = after) |", "|---|---|"]  # fmt: skip
    for p, h in sorted(m["source_artifacts"].items()):
        L.append(
            f"| `{p}` | `{h}` |"
            + ("" if m["source_hashes_after_build"][p] == h else " **CHANGED**")
        )
    L += ["", "## 8. Secondary trace: retained SciNLP held-out E0 run (`cr012_scinlp_heldout_P17_1058_grobid_E0`)", "",
          f"Built with the same adapter and no replay (the sections differ; replay not enabled). Events {sm['counts']['events']}, links {sm['counts']['links']}, gaps {sm['counts']['gaps']}. Final objects are taken from the checkpoint (no snapshots exist): concepts {sm['coverage']['final_objects']['concept']['count']} with {sm['coverage']['final_objects']['concept']['pct_lineage_to_evidence']:.1f}% lineage to evidence, edges {sm['coverage']['final_objects']['edge']['count']} with {sm['coverage']['final_objects']['edge']['pct_lineage_to_evidence']:.1f}%; locators resolve {sm['coverage']['evidence']['pct_locators_resolve']:.1f}%. Source hashes unchanged: {sm['source_hashes_unchanged']}. The derived SciNLP trace contains SciNLP text (CC BY-NC) and stays local and gitignored.", "",
          "## 9. Applied Research decisions", "", "- D1: replay is a labelled REPLAYED layer that reproduces the retained selected set exactly (valid here); an invalid replay would emit no ranks.", "- D2: only exact, run-scoped, deterministic joins (exact name or alias, unique; `#` suffix strip; equal pair id, unique; anchor key, unique); ambiguous or unresolved joins become `AMBIGUOUS_JOIN` / `UNRESOLVED` gaps (see section 5).", f"- D3: branch base `{m['base_commit']}`; `viz-kg-explorer` was not merged into `main`.", "",
          "## 10. Findings this build surfaced", "", "- Anchor (`AP-`) pairs and misconception verification (`MP-`) pairs are not ranked pool pairs; their origin is shown from the retained pair id and the retained anchor / relation records.", "- One `MP-` edge row has outcome `edge` but no committed snapshot edge (trace gap with its id); 2 other `MP-` edges are committed.", "- No data from the evaluation side (gold, scorer, attribution) is read by any production module; the frozen CR-012 attribution is reachable only from `why_not_eval.py`.", ""]  # fmt: skip
    (REPO_ROOT / "reports/cr013/stop2.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote reports/cr013/stop2.md", len(L), "lines")


if __name__ == "__main__":
    main()
