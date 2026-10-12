# CR-013 supervisor / examiner demonstration script

Duration about 10 minutes. Open `reports/kg_explorer/index.html` (`open reports/kg_explorer/index.html`), keep the **Review** view, and follow the numbered steps; each step was executed once through the real UI and asserted (`tests/js/demo_and_tasks.py`), with a screenshot in `reports/cr013/demo/`. Do not start from the global graph. CR-013 changes explainability/observability only; it makes no accuracy-improvement claim.

| # | do | say | screenshot |
|---|---|---|---|
| 1 | Explain a section -> choose 3.3 (Internet (IP)), step 1 Source text | This is the textbook section. The highlighted sentences are the evidence the generator cited for 389 mentions. | `demo/demo_01_source_text.png` |
| 2 | Step 2 Concepts proposed | The generator proposed 114 candidate concepts here. A proposal is not yet a graph node; where the model recorded a reason it is shown, otherwise NOT_RECORDED. | `demo/demo_02_generator.png` |
| 3 | Step 3 Verification | Deterministic rules reject candidates whose evidence is not verbatim; here is one that was rejected and the rule that rejected it. | `demo/demo_03_verification.png` |
| 4 | Step 4 Pruning | The pruner scored every candidate and dropped none in this run; its threshold was not stored in the artifact, so it says NOT_RECORDED. | `demo/demo_04_pruning.png` |
| 5 | Step 5 Canonicalisation | This decides which names are one concept. It is identity, not a semantic relation. Blocked merges were not recorded in this run. | `demo/demo_05_canonicalisation.png` |
| 6 | Step 6 Eligible pairs | 1256 concept pairs were eligible in this section. The pair list is a replayed layer: recomputed by the frozen selection code and checked to reproduce the retained selection exactly, so it is labelled REPLAYED. | `demo/demo_06_eligible_pairs.png` |
| 7 | Step 7 Budget boundary | The run had a global budget; selected and not-selected pairs are shown with their replayed rank. Rank alone is not a cut-off because selection also has coverage and anchor phases. | `demo/demo_07_budget_boundary.png` |
| 8 | Step 8 Relation decisions, then Step 10 and click a committed edge | The classifier decided 129 pairs in this section. One committed relation: its evidence with source and target highlighted, direction, qualifiers, the recorded model reason, model and prompt version, validation, and its rank and budget. | `demo/demo_09_edge_journey.png` |
| 9 | Step 10 Local graph | The resulting local graph: committed edges; relations proposed but rejected at validation are dashed red. | `demo/demo_10_local_graph.png` |
| 10 | Why not? -> pick a suggested pair | This pair was eligible but never sent to the classifier. The tool walks the stages and stops at the earliest observable loss. It never says a relation should exist. | `demo/demo_11_why_not.png` |
| 11 | Graph tab -> guided view 1 | Zoom out to the chapter-level graph; every node and edge has the journey you just saw. | `demo/demo_12_global_graph.png` |
| 12 | Optional: CR-012 evaluation overlay -> P&D held-out | This is evaluation output, not the production graph. Codes show the earliest observed failure location in the frozen CR-012 run for each gold relation; they are not explanations of model intent and not production rules. | `demo/demo_13_evaluation_overlay_optional.png` |

Questions to expect: *Why is the rank labelled replayed?* (it was never stored; section 3 of the final report). *Is this accurate?* (not claimed; frozen results: P&D held-out E0 strict F1 0.053, SciNLP E0 0.050). *Why NOT_RECORDED?* (the retained run did not store it; the tool shows the gap instead of guessing).
