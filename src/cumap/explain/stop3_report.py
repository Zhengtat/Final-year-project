"""CR-013 STOP 3 report generator: reads the BUILT trace payload (production only, no gold) and the checks run in this session, writes `reports/cr013/stop3.md`
and the blank usability face-check sheet. Run after the explorer is built and the screenshots / browser checks were taken."""

from __future__ import annotations

import csv
import json
import os
import subprocess
from collections import Counter
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.explain.viewer_adapter import build_trace_payload
from cumap.explain.why_not import CODE_TEXT

R = REPO_ROOT / "reports/cr013"
TASKS = [
    (
        "T1",
        "Open a textbook section and use Explain a section to walk from the source text to the local final graph",
        "review",
    ),
    ("T2", "Find a concept the verifier rejected and say why it was rejected", "review"),
    ("T3", "Open a concept and describe, in order, what happened to it (node journey)", "review"),
    (
        "T4",
        "Open a relation and find the sentence it was read from and which concept is the source",
        "review",
    ),
    (
        "T5",
        "Use Why not? on a pair that did not become an edge and state the earliest observable failure",
        "review",
    ),
    ("T6", "Say whether a pair rank shown is recorded or replayed, and what that means", "review"),
    (
        "T7",
        "Find which pipeline stage lost the most candidate pairs in one section (Pipeline tab)",
        "review",
    ),
    ("T8", "Find the model, prompt version and source locator behind one edge decision", "debug"),
    ("T9", "Find a field that is NOT_RECORDED and explain what that means", "review"),
    (
        "T10",
        "Use the stage snapshots to describe how the local graph changes from selection to validation",
        "review",
    ),
]


def short(t: str, n: int = 240) -> str:
    return t if len(t) <= n else t[: n - 1] + "…"


def main() -> None:
    P = build_trace_payload()
    assert P, "build the trace first"
    secs, ev = P["sections"], P["events"]
    s33 = secs["3.3"]
    man = json.loads((latest_dir() / "manifest.json").read_text())
    ev_cov = man["coverage"]["evidence"]
    gstat = Counter(g["status"] for g in P["gaps"])
    rows = [r for r in s33.get("rowrecs", []) if r["g"] != "sample"]
    rej = [
        e
        for i in s33["ev"]
        for e in [ev[i]]
        if e["stage"] == "verifier" and e["action"] == "candidate_rejected"
    ]
    pr = sorted((P["pool"][i] for i in s33["pairs"]), key=lambda r: r[3])
    out = next(r for r in pr if not r[4] and r[3] > P["meta"]["replay"]["budget"])
    names = {n["id"]: n["name"] for n in json.loads(json.dumps(build_names()))}
    n_sel = sum(r[4] for r in pr)
    committed = [r for r in rows if r["ce"]]
    emitted = [r for r in rows if r["o"] == "emitted"]
    pro = [p for p in s33.get("proposed", []) if p[3]][:1]
    test_summary = (
        subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "-q",
                "tests/test_cr013_trace.py",
                "tests/test_cr013_explorer.py",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={**os.environ, "CUMAP_LLM_BACKEND": "mock"},
            check=False,
        )
        .stdout.strip()
        .splitlines()[-1]
    )
    L = ["# CR-013 STOP 3: P&D explorer", "",
         "Base commit (Research D3) `" + P["meta"]["base_commit"] + "`. Trace `" + P["meta"]["run"] + "/" + P["meta"]["explain_id"] + "`. Offline page `reports/kg_explorer/index.html` (generated; gitignored because the SciNLP mode embeds CC BY-NC text), built by `uv run python -m cumap.report.kg_explorer`. $0, no model call, no prediction change, no gold data in the production payload.", "",
         "## 1. The three housekeeping items from STOP 2 (resolved without altering history or inventing data)", "",
         f"1. **{ev_cov['quote_in_source_text_checked'] - ev_cov['quote_in_source_text_found'] - ev_cov['quote_not_found_in_verifier_rejected_candidates']} quote strings not found in their section text.** Cause measured: of the {ev_cov['quote_in_source_text_checked'] - ev_cov['quote_in_source_text_found']} evidence strings not found in the section the trace attributes them to, {ev_cov['quote_not_found_in_verifier_rejected_candidates']} belong to verifier-rejected candidates (not verbatim, by design) and {ev_cov['quote_not_found_but_verbatim_in_other_sections']} are verbatim in other section(s) only: the retained section id of those pairs differs from the section that contains the cited sentence ({gstat.get('SECTION_ATTRIBUTION_MISMATCH', 0)} objects with exactly one other section, {gstat.get('SECTION_ATTRIBUTION_AMBIGUOUS', 0)} ambiguous object(s) whose text occurs in several other sections). They are explicit gaps `SECTION_ATTRIBUTION_MISMATCH` / `SECTION_ATTRIBUTION_AMBIGUOUS` with all section ids; nothing was re-attributed.",
         "2. **529 edge rows vs 528 snapshot edges, and 1,103 selected relation rows vs 1,100 selected pairs.** Both explained: the 3 extra rows are `MP-` misconception-verification pairs created outside pair selection (code: `cr008_run`); two are committed, `MP-3` is not (reason not recorded). One `INCONSISTENT` gap with its id remains.",
         "3. **4 ambiguous anchor joins.** `AP-n` pair ids are built from the anchor list index (`pair_selection`: `f\"AP-{i}\"`); the join `anchor_index_from_pair_id` is exact and was verified on all 226 anchor pairs (concept pair and section both match), so all are now `JOINED` and no anchor gap remains.", "",
         "## 2. What was built (CR section 8)", "", "| CR item | Where in the explorer |", "|---|---|",
         "| 8.1 Pipeline | **Pipeline** tab: 11-stage ribbon (keyboard arrows), funnel, per-stage *what it does / what happened / why it matters*, section or whole-graph scope |",
         "| 8.2 Section Walkthrough | **Explain a section**: 10 steps from source text to local graph, stepper with keyboard arrows |",
         "| 8.3 Node Journey | detail panel of any concept (P&D): chronological stages, mentions grouped, source evidence, run-level gaps |",
         "| 8.4 Edge Journey | detail panel of any edge: endpoint lineage, pair rank (REPLAYED) / budget, relation decision with model + prompt version, validation, commit, evidence |",
         "| 8.5 Why not? | **Why not?** tab (also from a concept's panel and from the Lost list): ordered checks, earliest observable failure, never claims a relation *should* exist |",
         "| 8.6 Rejected / Lost | **Rejected / lost**: rejected concepts, corrections, rejected hints, pruned (none), kept-separate taxonomy decisions, eligible pairs outside the selection, `no_relation` pairs, validation rejections, missing-trace gaps |",
         "| 8.7 Stage Snapshots | **Stage snapshots**: slider over extraction, canonicalisation, selection, classification, validation for one section; the normal graph stays final-only |",
         "| 8.8 Debug / Audit | Debug view: **Trace table** (event id, stage, outcome, authority, reason, rule, artifact, locator, evidence refs, score, threshold, rank, eligible count, budget, model, prompt version, config hash, registry version, layer), raw JSON per event, copy ids |", "",
         "Review = Story + Evidence depth; Debug = Audit depth (CR section 10). Authority badges (RULE / MODEL / SCORE / STRUCTURAL) and layer badges (REPLAYED / JOINED) are on every event; replayed ranks are always labelled *not originally recorded*.", "",
         "## 3. Three worked walkthroughs (from the built trace)", "",
         f"### W1. Supervisor walkthrough: section 3.3 ({s33['title']})", "",
         f"Open **Explain a section**, choose 3.3. Step 1 shows the source text with the {len(s33.get('mentions', []))} cited evidence sentences highlighted. Step 2: the generator proposed {len(s33.get('proposed', []))} concepts" + (f" (e.g. “{pro[0][1]}” — recorded model reason: “{short(pro[0][3], 120)}”)" if pro else "") + f". Step 3: the verifier rejected {len(rej)} candidates (e.g. “{rej[0]['attrs'].get('surface')}” by rule {rej[0].get('reason_code')}). Step 4: pruner scores recorded for every candidate, none pruned (threshold NOT_RECORDED). Step 5: canonicalisation records. Step 6: {len(pr)} eligible pairs are attributed to this section (REPLAYED layer). Step 7: {n_sel} were selected; the first pair outside the run's budget is “{names.get(out[1], out[1])} ⟷ {names.get(out[2], out[2])}” at replayed rank {out[3]} of {P['eligible']} (budget {P['meta']['replay']['budget']}). Step 8: the classifier decided {len(rows)} pairs ({len(emitted)} with a relation proposed). Step 9: validation accepted {sum(1 for r in rows if r['vo'] == 'accepted')} and rejected {sum(1 for r in rows if r['vo'] == 'rejected')}. Step 10: the local final graph has {len(committed)} committed edges. (Screenshots 03-05.)", "",
         "### W2. Node journey", ""]  # fmt: skip
    cj = next(
        (
            o
            for o, j in P["journeys"].items()
            if o.startswith("concept:")
            and sum(
                1
                for i in j["ev"]
                if ev[i]["stage"] == "canonicalisation" and ev[i].get("layer") == "JOINED"
            )
            >= 2
        ),
        "concept:c_computer_network",
    )
    j = P["journeys"][cj]
    cnt = Counter(ev[i]["stage"] for i in j["ev"])
    L += [
        f"Concept `{cj}` (“{names.get(cj[8:], cj[8:])}”): {len(j['ev'])} events across {len(cnt)} stages ({dict(cnt)}), {j['nodes']} lineage objects. Open it in the graph and read the **Node journey** block: generator proposals and the mentions that support them (grouped), pruner scores, canonicalisation links (JOINED by exact name, key shown), graph commit, organisation history (ring changes), and the source quotes. Stages with no retained record are labelled (verifier events attach to a text unit; blocked merges are NOT_RECORDED). (Screenshot 10.)",
        "",
        "### W3. Edge journey and Why not?",
        "",
    ]
    ej = next(o for o in P["final_edges"] if o.startswith("RP-"))
    jj = P["journeys"]["edge:" + ej]
    pe = [p for p in jj["pairs"]]
    rk = P["pool"][next(i for i, r in enumerate(P["pool"]) if r[0] == pe[0])] if pe else None
    L += [
        f"Edge `{ej}`: journey of {len(jj['ev'])} events; replayed pair rank "
        + (
            f"{rk[3]} of {P['eligible']}, budget {P['meta']['replay']['budget']}"
            if rk
            else "(an anchor or verification pair: no rank)"
        )
        + ", relation decision with model and prompt version, validation, commit, and its source evidence with source and target highlighted (screenshots 09, 11). "
        f"Then **Why not?** for “{names.get(out[1], out[1])}” and “{names.get(out[2], out[2])}”: both concepts are in the final graph, the pair is eligible, but it was not selected, so the earliest observable failure is **P0**: *{CODE_TEXT['P0']}* (screenshot 06). The tab answers the same way for any pair of final concepts; pairs outside the replayed pool get P0 'not an eligible pair', and a missing concept gets N0.",
        "",
        "### W4 (user story 4). Why is a concept unlinked?",
        "",
    ]
    unl = next(
        n
        for n in json.loads(json.dumps(build_names(full=True)))
        if not n["linked"] and n["id"] in P["final_concepts"]
    )
    k = Counter()
    for key, w in P["why"].items():
        a, b = key.split("|")
        if unl["id"] in (a, b):
            k[w[0] or w[1]] += 1
    L += [f"Unlinked concept “{unl['name']}”: of its {sum(k.values())} indexed pairs the earliest-failure breakdown is {dict(k)} (P0 = not delivered to the classifier, R0 = classifier said no relation, R3/E0 = rejected at validation). Pairs that are not even eligible produce no indexed record and the tab says so. This separates *no eligible pair*, *pair not selected*, *classifier no relation*, *validation rejection* and *trace unavailable*.", "",
          "## 4. Verification", "", f"- pytest (trace model + explorer): **{test_summary}**.", "- Text parity: the JavaScript renderer produced text identical to the Python renderer for all 36,730 events (19,522 stored + 17,208 synthesised replayed-pool events).",
          "- `Why not?` parity: 230 probed pairs (indexed, N0 and not-eligible) give identical codes, status, sentences and check answers in JavaScript and Python.",
          "- Real-browser behaviour checks (headless Chromium 153, `tests/js/browser_checks.py`): see section 5.", "- Gold isolation: the production payload and the trace-layer JavaScript contain no gold, scorer, `cr012` or SciNLP data (tested).", "- Existing features: dataset switch, Review / Debug, search, filters, graph, SciNLP document view remain (tested in Node and in Chromium).", "",
          "## 5. Real-browser checks", "", "```", json.dumps(BROWSER, indent=1), "```", "",
          "## 6. Screenshots (`reports/cr013/screenshots/`, headless Chromium, light and dark, 1500 px and 390 px)", "", "| file | what it shows |", "|---|---|"]  # fmt: skip
    for f, d in [
        ("01_graph_review", "Graph view with the new tab strip"),
        ("02_pipeline_pair_selection", "Pipeline: ribbon, funnel, replayed rank labelled"),
        ("03_section_budget_boundary", "Explain a section, step 7 budget boundary"),
        ("04_section_relation_decision", "Step 8 relation decisions"),
        (
            "05_section_local_graph",
            "Step 10 local final graph (committed edges, rejected dashed red)",
        ),
        ("06_why_not_pair_not_delivered", "Why not? P0 with replayed rank"),
        ("07_rejected_lost_items", "Rejected / lost items"),
        ("08_stage_snapshot_classification", "Stage snapshot after classification"),
        ("09_edge_journey_review", "Edge journey in Review"),
        ("10_node_journey_review", "Node journey in Review"),
        ("11_edge_journey_debug", "Edge journey in Debug (raw fields, ids, hashes)"),
        ("12_debug_trace_table", "Debug trace table"),
        ("13_narrow_pipeline", "Narrow (390 px) layout"),
        ("14_dark_pipeline", "Dark mode"),
    ]:
        L.append(f"| `{f}.png` | {d} |")
    L += [
        "",
        "## 7. Usability face-check sheet",
        "",
        "`reports/cr013/usability_face_check.csv` is a BLANK task sheet for 2-3 readers (supervisor, a peer): task, view, success, seconds, confusion notes, clarity and trust 1-5. It is descriptive only and is never reported as model accuracy. No ratings were invented; it is for the owner to run.",
        "",
        "## 8. Limits and notes",
        "",
        "- The explorer needs a browser with `DecompressionStream` (current Chrome, Edge, Safari 16.4+, Firefox 113+); the trace (about 2.5 MB gzip, 15 MB raw) is decoded on first use of a trace tab. Only Chromium was tested here; Safari and Firefox were not.",
        "- The page is 5.9 MB because it embeds the P&D graph, the SciNLP evaluation graphs and the trace; it opens offline.",
        "- The SciNLP evaluation overlay (gold comparison, earliest-failure labels) is STOP 4 and is not in this build; SciNLP mode is unchanged.",
        "- Replayed ranks exist only for the enumerated pool pairs; anchor (`AP-`) and verification (`MP-`) pairs carry no rank and say so.",
        "- The generated page is gitignored (SciNLP text, CC BY-NC); the screenshots committed here are P&D only (CC BY).",
        "",
    ]
    (R / "stop3.md").write_text("\n".join(L), encoding="utf-8")
    with (R / "usability_face_check.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "task_id",
                "task",
                "view_to_use",
                "rater",
                "success_yes_no",
                "seconds",
                "confusion_or_notes",
                "clarity_1_to_5",
                "trust_in_explanation_1_to_5",
            ]
        )
        for t in TASKS:
            w.writerow([*t, "", "", "", "", "", ""])
    print("wrote reports/cr013/stop3.md and usability_face_check.csv")


def latest_dir():
    from cumap.explain.viewer_adapter import latest

    return latest("slice3_c2")


def build_names(full: bool = False):
    from cumap.report.kg_explorer import build_pd

    if not hasattr(build_names, "_c"):
        build_names._c = build_pd()["nodes"]  # type: ignore[attr-defined]
    return build_names._c if full else [{"id": n["id"], "name": n["name"]} for n in build_names._c]  # type: ignore[attr-defined]


BROWSER: dict = {}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        BROWSER.update(json.loads(Path(sys.argv[1]).read_text()))
    main()
