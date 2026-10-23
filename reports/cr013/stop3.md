# CR-013 STOP 3: P&D explorer

Base commit (Research D3) `2e50b6538ab5a8c97c9df3a218ab70646af90695`. Trace `slice3_c2/77c22e3d915a`. Offline page `reports/kg_explorer/index.html` (generated; gitignored because the SciNLP mode embeds CC BY-NC text), built by `uv run python -m cumap.report.kg_explorer`. $0, no model call, no prediction change, no gold data in the production payload.

## 1. The three housekeeping items from STOP 2 (resolved without altering history or inventing data)

1. **117 quote strings not found in their section text.** Cause measured: of the 171 evidence strings not found in the section the trace attributes them to, 54 belong to verifier-rejected candidates (not verbatim, by design) and 117 are verbatim in other section(s) only: the retained section id of those pairs differs from the section that contains the cited sentence (76 objects with exactly one other section, 2 ambiguous object(s) whose text occurs in several other sections). They are explicit gaps `SECTION_ATTRIBUTION_MISMATCH` / `SECTION_ATTRIBUTION_AMBIGUOUS` with all section ids; nothing was re-attributed.
2. **529 edge rows vs 528 snapshot edges, and 1,103 selected relation rows vs 1,100 selected pairs.** Both explained: the 3 extra rows are `MP-` misconception-verification pairs created outside pair selection (code: `cr008_run`); two are committed, `MP-3` is not (reason not recorded). One `INCONSISTENT` gap with its id remains.
3. **4 ambiguous anchor joins.** `AP-n` pair ids are built from the anchor list index (`pair_selection`: `f"AP-{i}"`); the join `anchor_index_from_pair_id` is exact and was verified on all 226 anchor pairs (concept pair and section both match), so all are now `JOINED` and no anchor gap remains.

## 2. What was built (CR section 8)

| CR item | Where in the explorer |
|---|---|
| 8.1 Pipeline | **Pipeline** tab: 11-stage ribbon (keyboard arrows), funnel, per-stage *what it does / what happened / why it matters*, section or whole-graph scope |
| 8.2 Section Walkthrough | **Explain a section**: 10 steps from source text to local graph, stepper with keyboard arrows |
| 8.3 Node Journey | detail panel of any concept (P&D): chronological stages, mentions grouped, source evidence, run-level gaps |
| 8.4 Edge Journey | detail panel of any edge: endpoint lineage, pair rank (REPLAYED) / budget, relation decision with model + prompt version, validation, commit, evidence |
| 8.5 Why not? | **Why not?** tab (also from a concept's panel and from the Lost list): ordered checks, earliest observable failure, never claims a relation *should* exist |
| 8.6 Rejected / Lost | **Rejected / lost**: rejected concepts, corrections, rejected hints, pruned (none), kept-separate taxonomy decisions, eligible pairs outside the selection, `no_relation` pairs, validation rejections, missing-trace gaps |
| 8.7 Stage Snapshots | **Stage snapshots**: slider over extraction, canonicalisation, selection, classification, validation for one section; the normal graph stays final-only |
| 8.8 Debug / Audit | Debug view: **Trace table** (event id, stage, outcome, authority, reason, rule, artifact, locator, evidence refs, score, threshold, rank, eligible count, budget, model, prompt version, config hash, registry version, layer), raw JSON per event, copy ids |

Review = Story + Evidence depth; Debug = Audit depth (CR section 10). Authority badges (RULE / MODEL / SCORE / STRUCTURAL) and layer badges (REPLAYED / JOINED) are on every event; replayed ranks are always labelled *not originally recorded*.

## 3. Three worked walkthroughs (from the built trace)

### W1. Supervisor walkthrough: section 3.3 (Internet (IP))

Open **Explain a section**, choose 3.3. Step 1 shows the source text with the 389 cited evidence sentences highlighted. Step 2: the generator proposed 114 concepts (e.g. “IP address space” — recorded model reason: “anchor removed by verifier”). Step 3: the verifier rejected 28 candidates (e.g. “slash notation” by rule F3). Step 4: pruner scores recorded for every candidate, none pruned (threshold NOT_RECORDED). Step 5: canonicalisation records. Step 6: 1256 eligible pairs are attributed to this section (REPLAYED layer). Step 7: 99 were selected; the first pair outside the run's budget is “network ⟷ subnetwork” at replayed rank 1359 of 8604 (budget 1100). Step 8: the classifier decided 129 pairs (75 with a relation proposed). Step 9: validation accepted 62 and rejected 13. Step 10: the local final graph has 62 committed edges. (Screenshots 03-05.)

### W2. Node journey

Concept `concept:c_802_11_wi_fi_standard` (“802.11 Wi-Fi standard”): 33 events across 6 stages ({'source': 8, 'generator': 13, 'pruner': 2, 'canonicalisation': 4, 'graph_commit': 3, 'organisation': 3}), 26 lineage objects. Open it in the graph and read the **Node journey** block: generator proposals and the mentions that support them (grouped), pruner scores, canonicalisation links (JOINED by exact name, key shown), graph commit, organisation history (ring changes), and the source quotes. Stages with no retained record are labelled (verifier events attach to a text unit; blocked merges are NOT_RECORDED). (Screenshot 10.)

### W3. Edge journey and Why not?

Edge `RP-1-problem-building-a-network-0`: journey of 78 events; replayed pair rank 420 of 8604, budget 1100, relation decision with model and prompt version, validation, commit, and its source evidence with source and target highlighted (screenshots 09, 11). Then **Why not?** for “network” and “subnetwork”: both concepts are in the final graph, the pair is eligible, but it was not selected, so the earliest observable failure is **P0**: *The pair was never sent to relation classification, so the classifier had no opportunity to decide whether a semantic relation exists.* (screenshot 06). The tab answers the same way for any pair of final concepts; pairs outside the replayed pool get P0 'not an eligible pair', and a missing concept gets N0.

### W4 (user story 4). Why is a concept unlinked?

Unlinked concept “1G”: of its 4 indexed pairs the earliest-failure breakdown is {'P0': 4} (P0 = not delivered to the classifier, R0 = classifier said no relation, R3/E0 = rejected at validation). Pairs that are not even eligible produce no indexed record and the tab says so. This separates *no eligible pair*, *pair not selected*, *classifier no relation*, *validation rejection* and *trace unavailable*.

## 4. Verification

- pytest (trace model + explorer): **41 passed in 9.59s**.
- Text parity: the JavaScript renderer produced text identical to the Python renderer for all 36,730 events (19,522 stored + 17,208 synthesised replayed-pool events).
- `Why not?` parity: 230 probed pairs (indexed, N0 and not-eligible) give identical codes, status, sentences and check answers in JavaScript and Python.
- Real-browser behaviour checks (headless Chromium 153, `tests/js/browser_checks.py`): see section 5.
- Gold isolation: the production payload and the trace-layer JavaScript contain no gold, scorer, `cr012` or SciNLP data (tested).
- Existing features: dataset switch, Review / Debug, search, filters, graph, SciNLP document view remain (tested in Node and in Chromium).

## 5. Real-browser checks

```
{
 "ribbon_arrowright_moves_the_selected_stage": true,
 "ribbon_keeps_focus_on_the_selected_stage": true,
 "ribbon_arrowleft_returns": true,
 "ribbon_has_tab_roles": true,
 "stepper_arrowright_advances": true,
 "stepper_next_button_works": true,
 "reduced_motion_removes_detail_transition_movement": true,
 "journey_is_populated": true,
 "narrow_has_no_horizontal_page_scroll": true,
 "narrow_pipeline_has_no_horizontal_page_scroll": true,
 "scinlp_mode_still_works_and_hides_pd_trace_tabs": true,
 "debug_view_adds_trace_table_tab": true,
 "review_view_hides_trace_table_tab": true,
 "no_page_errors": true
}
```

## 6. Screenshots (`reports/cr013/screenshots/`, headless Chromium, light and dark, 1500 px and 390 px)

| file | what it shows |
|---|---|
| `01_graph_review.png` | Graph view with the new tab strip |
| `02_pipeline_pair_selection.png` | Pipeline: ribbon, funnel, replayed rank labelled |
| `03_section_budget_boundary.png` | Explain a section, step 7 budget boundary |
| `04_section_relation_decision.png` | Step 8 relation decisions |
| `05_section_local_graph.png` | Step 10 local final graph (committed edges, rejected dashed red) |
| `06_why_not_pair_not_delivered.png` | Why not? P0 with replayed rank |
| `07_rejected_lost_items.png` | Rejected / lost items |
| `08_stage_snapshot_classification.png` | Stage snapshot after classification |
| `09_edge_journey_review.png` | Edge journey in Review |
| `10_node_journey_review.png` | Node journey in Review |
| `11_edge_journey_debug.png` | Edge journey in Debug (raw fields, ids, hashes) |
| `12_debug_trace_table.png` | Debug trace table |
| `13_narrow_pipeline.png` | Narrow (390 px) layout |
| `14_dark_pipeline.png` | Dark mode |

## 7. Usability face-check sheet

`reports/cr013/usability_face_check.csv` is a BLANK task sheet for 2-3 readers (supervisor, a peer): task, view, success, seconds, confusion notes, clarity and trust 1-5. It is descriptive only and is never reported as model accuracy. No ratings were invented; it is for the owner to run.

## 8. Limits and notes

- The explorer needs a browser with `DecompressionStream` (current Chrome, Edge, Safari 16.4+, Firefox 113+); the trace (about 2.5 MB gzip, 15 MB raw) is decoded on first use of a trace tab. Only Chromium was tested here; Safari and Firefox were not.
- The page is 5.9 MB because it embeds the P&D graph, the SciNLP evaluation graphs and the trace; it opens offline.
- The SciNLP evaluation overlay (gold comparison, earliest-failure labels) is STOP 4 and is not in this build; SciNLP mode is unchanged.
- Replayed ranks exist only for the enumerated pool pairs; anchor (`AP-`) and verification (`MP-`) pairs carry no rank and say so.
- The generated page is gitignored (SciNLP text, CC BY-NC); the screenshots committed here are P&D only (CC BY).
