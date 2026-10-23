"""CR-013 STOP 5 report generator: FINAL_EXPLAINABILITY.md, DEMO_SCRIPT.md and usability_face_check.md, written from the manifests, check results and frozen outputs. It does not import evaluation code
or read gold; overlay numbers come from the frozen CR-012 results file.

    uv run python -m cumap.explain.final_report"""

from __future__ import annotations

import json
import os
import subprocess
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.explain.viewer_adapter import build_trace_payload, latest

R = REPO_ROOT / "reports/cr013"
STATEMENT = (
    "CR-013 changes explainability/observability only; it makes no accuracy-improvement claim."
)


def j(p: str):
    return json.loads((REPO_ROOT / p).read_text())


def main() -> None:
    man = j("reports/cr013/final_trace_manifest.json")
    pd = man["derived_traces"]["slice3_c2"]
    sc = man["derived_traces"]["cr012_scinlp_heldout_P17_1058_grobid_E0"]
    cov = pd["coverage_summary"]
    ax = j("reports/cr013/checks/accessibility_performance.json")
    xb = j("reports/cr013/checks/cross_browser_smoke.json")
    demo = j("reports/cr013/checks/demo_and_task_feasibility.json")
    bp, be = (
        j("reports/cr013/checks/browser_checks_production.json"),
        j("reports/cr013/checks/browser_checks_evaluation.json"),
    )
    fz = j("reports/cr012/stop4_heldout_results.json")
    test_line = (
        subprocess.run(
            ["uv", "run", "pytest", "-q"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={**os.environ, "CUMAP_LLM_BACKEND": "mock"},
            check=False,
        )
        .stdout.strip()
        .splitlines()[-1]
    )
    d = latest("slice3_c2")
    layers = Counter(
        json.loads(x)["layer"]
        for x in (d / "trace_events.jsonl").read_text().splitlines()
        if x.strip()
    )
    joins = Counter(
        (json.loads(x).get("join") or {}).get("method")
        for x in (d / "trace_events.jsonl").read_text().splitlines()
        if x.strip() and '"join": {' in x
    )
    gaps = [json.loads(x) for x in (d / "trace_gaps.jsonl").read_text().splitlines() if x.strip()]
    P = build_trace_payload()
    s33 = P["sections"]["3.3"]
    rows = [r for r in s33.get("rowrecs", []) if r["g"] != "sample"]
    fo, fe = cov["final_objects"]["concept"], cov["final_objects"]["edge"]
    ev, ex = cov["evidence"], cov["explanations"]
    sf, pf = (
        fz["scinlp"]["levels"]["E0"]["aggregates"]["rel"]["micro"]["f1"],
        fz["pd"]["levels"]["E0"]["pooled_strict_e2e"]["f1"],
    )
    errs = sum(len(v["violations"]) for v in ax["axe"].values())
    L = ["# CR-013 FINAL: Glass-box process explainability for Expert-KG construction", "",
         f"**{STATEMENT}** It adds traceability, explanation and failure-localisation tooling around the frozen pipeline and frozen CR-012 evaluation; no prediction, prompt, model, threshold, budget, registry or score was changed.", "",
         "Written for: Research, the supervisor and the examiners. Evidence: `reports/cr013/` (STOP reports, manifests, checks, screenshots), `data/processed/explainability/` (derived traces, gitignored) and `reports/kg_explorer/index.html` (generated, gitignored because it embeds CC BY-NC SciNLP text).", "",
         "## 1. What was delivered (STOPs 1-4)", "",
         "| STOP | outcome | report |", "|---|---|---|",
         "| 1 Trace audit ($0) | audited `slice3_c2` and one SciNLP run stage by stage; found that pair rank, the eligible pool, alias provenance, blocked merges, generator-call links and confidence were not retained | `trace_coverage.md` |",
         "| 2 Trace model | `TraceEvent`, lineage DAG, deterministic renderer, `Why not?` localiser, coverage and gap reporting, REPLAYED pair-rank layer (exactly reproduces the retained selection) | `stop2.md` |",
         "| 3 P&D explorer | Pipeline, Explain a section, Why not?, Rejected / lost, Stage snapshots, Debug trace table, Node and Edge journeys inside the existing explorer; three housekeeping gaps resolved without altering history | `stop3.md` |",
         "| 4 Evaluation overlay | opt-in, separate-payload overlay over the frozen CR-012 outputs: failure map, gold comparison, earliest-failure explanations for SciNLP and P&D held-out | `stop4.md` |",
         "| 5 Final | this report, final manifest, accessibility / performance / cross-engine checks, executed demo flow, tests and tag | this file |", "",
         "## 2. Final trace coverage (production run `slice3_c2`, P&D chapters 1-3)", "",
         "| CR section 12 metric | target | result |", "|---|---|---|",
         f"| Final-object trace coverage: concepts | >= 95% | **{fo['lineage_reaches_resolvable_evidence']} / {fo['count']} = {fo['pct_lineage_to_evidence']:.1f}%** reach resolvable source evidence |",
         f"| Final-object trace coverage: edges | >= 95% | **{fe['lineage_reaches_resolvable_evidence']} / {fe['count']} = {fe['pct_lineage_to_evidence']:.1f}%** |",
         f"| Evidence resolvability | 100% | **{ev['refs_resolving']} / {ev['refs_total']} = {ev['pct_locators_resolve']:.1f}%** of evidence locators resolve; {ev['quote_in_source_text_found']} / {ev['quote_in_source_text_checked']} ({ev['pct_quote_in_source_text']:.1f}%) quotes are also found in the section text they are attributed to (the rest: {ev['quote_not_found_in_verifier_rejected_candidates']} verifier-rejected candidates and {ev['quote_not_found_but_verbatim_in_other_sections']} strings that are verbatim only in other section(s), recorded as section-attribution gaps) |",
         f"| Explanation support rate | 100% | **{ex['pct_supported']:.1f}%** of {ex['dynamic_segments']} dynamic values in {ex['sentences']} sentences equal the trace field they were rendered from (JavaScript renderer equals the Python renderer on all 36,730 events) |",
         f"| Unknown honesty | 100% | **{ex['pct_unknown_honesty']:.1f}%** ({ex['unrecorded_fields_rendered_as_NOT_RECORDED']} unrecorded fields shown as NOT_RECORDED) |",
         f"| Replay determinism | 100% | two builds give an identical trace hash: **{pd['two_builds_identical_trace_hash']}**; the replay layer is deterministic: **{pd['replay']['deterministic']}** |",
         "| Stage localisation accuracy (fixtures) | 100% | **11 / 11** fixtures (all ten codes plus a recovered edge) |",
         "| Gold isolation | 100% | enforced by tests (section 5) |",
         f"| Read-only integrity | 100% | **{man['read_only_integrity']['all_audited_source_artifacts_byte_identical']}**: every audited source artifact is byte-identical before / after each build, now, and against the STOP-1 audit (section 8) |", "",
         f"Stage presence in the lineage of the final objects (% of objects): generator, canonicalisation, pruner, graph commit, organisation 100% for concepts and edges; pair generation / selection {fe['stage_presence_pct']['pair_generation']} / {fe['stage_presence_pct']['pair_selection']}%, relation classification and validation 100% for edges; verifier events attach to a text unit, so they are counted unit-scoped ({fo['unit_scoped_stage_presence_events_in_a_unit_the_object_comes_from'].get('verifier', 0)} of {fo['count']} concepts come from a unit with verifier events).", "",
         "### Known gaps (kept explicit; nothing was invented)", "", "| status | stage | field | what is not retained |", "|---|---|---|---|"]  # fmt: skip
    seen = set()
    for g in gaps:
        if g["scope"] == "run" or g["status"] == "INCONSISTENT":
            key = (g["stage"], g["field"], g["object_id"])
            if key not in seen:
                seen.add(key)
                L.append(
                    f"| {g['status']} | {g['stage']} | {g['field']}{' ' + g['object_id'] if g['object_id'] else ''} | {g['detail']} |"
                )
    by = Counter(g["status"] for g in gaps)
    L += ["", f"Object-level section-attribution gaps: {by.get('SECTION_ATTRIBUTION_MISMATCH', 0)} `SECTION_ATTRIBUTION_MISMATCH` and {by.get('SECTION_ATTRIBUTION_AMBIGUOUS', 0)} `SECTION_ATTRIBUTION_AMBIGUOUS` (the retained section id of a pair differs from the section that contains its cited sentence; nothing was re-attributed). Anchor pairs (`AP-`) and misconception-verification pairs (`MP-`) carry no pool rank and say so. The per-pair selection phase, the model's rejected relation alternatives and any confidence were never retained.", "",
         "## 3. Provenance classes", "",
         f"Every event carries a `layer`: **RECORDED** ({layers.get('RECORDED', 0)} events) is read directly from a retained artifact with its source artifact and JSON locator; **REPLAYED** ({layers.get('REPLAYED', 0)} events) is recomputed by the frozen deterministic selection code (no model call) and is used only because it reproduces the retained selected pairs, their order, the retained 50-pair sample and the retained selection statistics exactly (an invalid replay would emit no ranks); replayed ranks are always described as *not originally recorded*; **JOINED** ({layers.get('JOINED', 0)} events) is an exact, run-scoped, deterministic join with its method and key stored. Join methods in use: " + ", ".join(f"`{k}` ({v})" for k, v in sorted(joins.items(), key=lambda kv: str(kv[0]))) + ". Ambiguous or unresolved joins are not made; they are `AMBIGUOUS_JOIN` / `UNRESOLVED` gaps.", "",
         "## 4. The explorer", "",
         "Review (story and evidence depth) and Debug (audit depth) views over one offline page. New in CR-013 for the production P&D graph: Pipeline (11-stage ribbon, funnel, what each stage does / what happened / why it matters), Explain a section (10 steps from source text to the local final graph), Node and Edge journeys, Why not? (ordered checks, earliest observable failure, never a claim that a relation *should* exist), Rejected / lost items, Stage snapshots, and a Debug trace table with the audit fields of CR section 8.8.", "",
         "## 5. Production / evaluation isolation", "",
         "The production views and payload contain no gold, scorer output or frozen-run data. The evaluation overlay is a separate, opt-in mode with its own payload (`eval-gz`), its own JavaScript and its own Python module; it is not decoded until the user opens it, is banner-labelled *EVALUATION OUTPUT, gold-derived, NOT the production Expert KG*, and is dataset scoped (SciNLP held-out and P&D held-out are never pooled). Tests enforce: only `eval_adapter`, `why_not_eval` and `eval_report` read gold or import `cumap.cr012`; the production payload and trace JavaScript contain no overlay or gold symbol; the two blobs are separate; the overlay is undecoded until opt-in and leaves no evaluation text in production views.", "",
         f"**How the overlay must be read.** The overlay contains gold-derived evaluation observations, not ground truth about why the system reasoned incorrectly. Each code is CR-012's frozen attribution of an earliest observed failure location. For example, **P0** means that CR-012's frozen attribution determined that both endpoints existed but the relevant pair did not reach the required downstream stage. It is an earliest observed failure location, not an explanation of internal model intent, and it is not a decision rule for the production pipeline. Frozen headlines shown there: SciNLP E0 strict relation F1 {sf:.3f} (CI status NOT_EVALUABLE_SMALL_N, 3 documents); P&D held-out E0 strict F1 {pf:.3f} (descriptive small n, single annotator). CR-011 pre/post: NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION.", "",
         "## 6. Verification", "",
         f"- **Tests:** full suite `{test_line}`; lint clean on all CR-013 files.",
         "- **Parity:** the JavaScript renderer equals the Python renderer on all 36,730 events; the JavaScript `Why not?` equals the Python localiser on 230 probed pairs.",
         f"- **Accessibility (automated):** axe-core WCAG 2.0 A/AA over 10 light-mode states (graph, all trace tabs, edge journey, Debug views, evaluation map) and 7 dark-mode states: **{errs} violations** after fixes made in this STOP (unlabelled filters, keyboard-unreachable scroll regions, three low-contrast colours). Also: header / main / aside landmarks, no unnamed buttons, no unlabelled inputs, no horizontal page scroll at a 200%-zoom viewport and at 390 px, reduced-motion respected, first Tab reaches an interactive element. Automated checks find only a subset of problems; no manual screen-reader audit was done, and the graph itself is a canvas (the detail panel, search and tables are its text alternatives).",
         f"- **Performance (headless Chromium, this machine):** page ready in {ax['perf']['load_to_interactive_ms']} ms ({ax['perf']['file_mb']} MB file); first trace tab incl. decoding {ax['perf']['trace_decoded_events']} events: {ax['perf']['first_trace_tab_incl_decode_ms']} ms; later tab renders {ax['perf']['tab_why_render_ms']}-{ax['perf']['tab_snap_render_ms']} ms; five canvas redraws {ax['perf']['five_redraws_ms']} ms; JS heap {ax['perf']['js_heap_mb_after_everything']} MB.",
         f"- **Browsers:** full testing (behaviour checks, screenshots, axe, performance) was done in **headless Chromium 153 only** ({sum(bp.values())} / {len(bp)} production and {sum(be.values())} / {len(be)} evaluation behaviour checks pass). A smoke test of the same main flows also passed in the Playwright **Firefox {xb['firefox']['engine_version']}** and **WebKit {xb['webkit']['engine_version']}** builds (page load, trace decoding, keyboard navigation, walkthrough, Why not?, journeys, canvas drawing, evaluation overlay, SciNLP mode). This is a smoke test of those builds; **we do not claim compatibility with released Safari or Firefox versions**. The page needs `DecompressionStream`, which these builds provide; browsers without it show a message and cannot open the trace tabs.", "",
         "## 7. Demonstration and usability", "",
         f"- **Demonstration flow, executed once end to end through the real UI** (`tests/js/demo_and_tasks.py`, 13 steps, all asserted, {demo['demo_seconds_scripted']} s scripted, screenshots `reports/cr013/demo/`): source section 3.3 -> generator -> verification -> pruning -> canonicalisation -> eligible pairs -> budget boundary -> relation decisions and one edge journey -> validation -> local graph -> Why not? -> global graph -> optional evaluation overlay. The talk track is `DEMO_SCRIPT.md`.",
         f"- **Descriptive usability face check: NOT_EVALUATED.** No 2-3 readers could be recruited within this work, so no responses exist and none were fabricated. `usability_face_check.csv` is the ready, blank sheet (10 tasks). Separately, a *scripted feasibility* run confirmed that the information each of the 10 tasks asks for is reachable in the UI ({sum(t['completable_in_ui'] for t in demo['task_feasibility'].values())} / 10); that is not evidence about how people experience the page, and no inferential statistics or accuracy metric is derived from it.", "",
         "## 8. Read-only integrity manifest", "",
         f"`reports/cr013/final_trace_manifest.json` records: source run ids ({', '.join(man['source_run_ids'])}); the SHA-256 of every source artifact (before and after each build, now, and as recorded by the STOP-1 audit: {pd['stop1_audit_artifacts_compared']} + {sc['stop1_audit_artifacts_compared']} artifacts compared); CR-013 code and configuration hashes ({len(man['cr013_code_and_config_hashes'])} files, combined `{man['cr013_code_combined_sha256'][:16]}…`); derived-trace hashes (`slice3_c2` trace `{pd['explain_id']}`, SciNLP trace `{sc['explain_id']}`); the explorer hash (`{man['explorer']['sha256'][:16]}…`, two builds identical: {man['explorer']['second_build_identical']}); and the hashes of the read-only inputs of the evaluation overlay (unchanged: {man['overlay_frozen_inputs']['unchanged']}). **All audited source artifacts remain byte-identical: {man['read_only_integrity']['all_audited_source_artifacts_byte_identical']}.**", "",
         "## 9. Known limitations", "",
         "1. **Crowded labels.** Dense regions of the main graph can still show overlapping labels. A purely visual mitigation was added (labels are placed greedily by importance and skipped when they would overlap), but selected, searched and hovered labels are always drawn, so overlaps remain around a selected hub. Graph semantics are unchanged; use search, filters or the tables when a region is dense.",
         "2. Legacy-run limits (section 2): pair rank and the eligible pool exist only as a labelled replay for enumerated pool pairs; alias provenance, blocked merges, generator-call links, confidence and rejected alternatives were never recorded.",
         "3. The SciNLP trace is partial (no snapshots, organisation or pair registry in the retained run) and contains CC BY-NC text, so derived SciNLP artifacts and the generated page stay local.",
         "4. The overlay covers E0 only; P&D held-out gold has a single human annotator; SciNLP C0 / C1 are not applicable.",
         "5. Descriptive usability face check not performed (section 7); cross-engine testing is smoke-level (section 6).", "",
         "## 10. Reproduce", "", "```", "uv run python -m cumap.explain.build --run slice3_c2            # derived trace + replay", "uv run python -m cumap.report.kg_explorer                       # offline explorer (reports/kg_explorer/index.html)", "uv run python -m cumap.explain.final_manifest                   # integrity manifest", "uv run pytest -q                                                 # tests (no network, no key)", "```", "",
         "## 11. What CR-013 does not claim", "", f"{STATEMENT} It does not claim that the Expert KG is accurate or validated, that any explanation reflects model intent, that the explorer is accessible beyond the automated checks reported, or that it works in browsers other than those tested.", ""]  # fmt: skip
    (R / "FINAL_EXPLAINABILITY.md").write_text("\n".join(L), encoding="utf-8")

    D = ["# CR-013 supervisor / examiner demonstration script", "", f"Duration about 10 minutes. Open `reports/kg_explorer/index.html` (`open reports/kg_explorer/index.html`), keep the **Review** view, and follow the numbered steps; each step was executed once through the real UI and asserted (`tests/js/demo_and_tasks.py`), with a screenshot in `reports/cr013/demo/`. Do not start from the global graph. {STATEMENT}", "",
         "| # | do | say | screenshot |", "|---|---|---|---|"]  # fmt: skip
    steps = [
        (
            "Explain a section -> choose 3.3 (Internet (IP)), step 1 Source text",
            f"This is the textbook section. The highlighted sentences are the evidence the generator cited for {len(s33.get('mentions', []))} mentions.",
            "demo_01_source_text",
        ),
        (
            "Step 2 Concepts proposed",
            f"The generator proposed {len(s33.get('proposed', []))} candidate concepts here. A proposal is not yet a graph node; where the model recorded a reason it is shown, otherwise NOT_RECORDED.",
            "demo_02_generator",
        ),
        (
            "Step 3 Verification",
            "Deterministic rules reject candidates whose evidence is not verbatim; here is one that was rejected and the rule that rejected it.",
            "demo_03_verification",
        ),
        (
            "Step 4 Pruning",
            "The pruner scored every candidate and dropped none in this run; its threshold was not stored in the artifact, so it says NOT_RECORDED.",
            "demo_04_pruning",
        ),
        (
            "Step 5 Canonicalisation",
            "This decides which names are one concept. It is identity, not a semantic relation. Blocked merges were not recorded in this run.",
            "demo_05_canonicalisation",
        ),
        (
            "Step 6 Eligible pairs",
            f"{len(s33['pairs'])} concept pairs were eligible in this section. The pair list is a replayed layer: recomputed by the frozen selection code and checked to reproduce the retained selection exactly, so it is labelled REPLAYED.",
            "demo_06_eligible_pairs",
        ),
        (
            "Step 7 Budget boundary",
            "The run had a global budget; selected and not-selected pairs are shown with their replayed rank. Rank alone is not a cut-off because selection also has coverage and anchor phases.",
            "demo_07_budget_boundary",
        ),
        (
            "Step 8 Relation decisions, then Step 10 and click a committed edge",
            f"The classifier decided {len(rows)} pairs in this section. One committed relation: its evidence with source and target highlighted, direction, qualifiers, the recorded model reason, model and prompt version, validation, and its rank and budget.",
            "demo_09_edge_journey",
        ),
        (
            "Step 10 Local graph",
            "The resulting local graph: committed edges; relations proposed but rejected at validation are dashed red.",
            "demo_10_local_graph",
        ),
        (
            "Why not? -> pick a suggested pair",
            "This pair was eligible but never sent to the classifier. The tool walks the stages and stops at the earliest observable loss. It never says a relation should exist.",
            "demo_11_why_not",
        ),
        (
            "Graph tab -> guided view 1",
            "Zoom out to the chapter-level graph; every node and edge has the journey you just saw.",
            "demo_12_global_graph",
        ),
        (
            "Optional: CR-012 evaluation overlay -> P&D held-out",
            "This is evaluation output, not the production graph. Codes show the earliest observed failure location in the frozen CR-012 run for each gold relation; they are not explanations of model intent and not production rules.",
            "demo_13_evaluation_overlay_optional",
        ),
    ]
    for i, (do, say, shot) in enumerate(steps, 1):
        D.append(f"| {i} | {do} | {say} | `demo/{shot}.png` |")
    D += [
        "",
        "Questions to expect: *Why is the rank labelled replayed?* (it was never stored; section 3 of the final report). *Is this accurate?* (not claimed; frozen results: P&D held-out E0 strict F1 "
        + f"{pf:.3f}, SciNLP E0 {sf:.3f}). *Why NOT_RECORDED?* (the retained run did not store it; the tool shows the gap instead of guessing).",
        "",
    ]
    (R / "DEMO_SCRIPT.md").write_text("\n".join(D), encoding="utf-8")

    U = ["# CR-013 descriptive usability face check", "", "**Status: NOT_EVALUATED.** The CR asks for a descriptive face check with 2-3 readers (task completion, confusion points, qualitative comments; no inferential statistics, never an accuracy metric). No readers could be recruited within this work, so there are no responses; none were fabricated or simulated. The blank sheet `usability_face_check.csv` is ready to be run by the owner with a supervisor and a peer.", "",
         "## Scripted feasibility run (not a usability study)", "", "A script confirmed that the information each task asks for can be reached in the UI. It says nothing about how long it takes people or where they hesitate.", "", "| task | feasible in the UI | evidence |", "|---|---|---|"]  # fmt: skip
    for tid in sorted(demo["task_feasibility"], key=lambda x: int(x[1:])):
        t = demo["task_feasibility"][tid]
        U.append(
            f"| {tid} | {'yes' if t['completable_in_ui'] else 'NO'} | {t['evidence'].replace(chr(10), ' ')[:110]} |"
        )
    U += [
        "",
        "## How to run the human check",
        "",
        "Give each reader the ten tasks in `usability_face_check.csv` with the page open in the stated view; record success, seconds, confusion points and 1-5 clarity / trust ratings; report counts and quotes only.",
        "",
    ]
    (R / "usability_face_check.md").write_text("\n".join(U), encoding="utf-8")
    print("wrote FINAL_EXPLAINABILITY.md, DEMO_SCRIPT.md, usability_face_check.md")


if __name__ == "__main__":
    main()
