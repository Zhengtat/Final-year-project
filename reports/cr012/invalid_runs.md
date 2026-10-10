# CR-012 audit trail: invalid / superseded results

| date | item | what was wrong | status |
|---|---|---|---|
| 2026-10-10 | in-session pilot figure for section 2.6: strict E2E F1 0.21 (12 of 34 predicted edges correct) | the graph converter (`production_graph.graph_for_sections`) counted the 50-pair unselected measurement sample (group `sample`) as graph edges; the run itself (`cr012_pilot_2_6_E0`) was valid. My first fix had not taken effect because the file had been reformatted, and a unit test caught it. | **INVALID, superseded** by the corrected 2.6 result F1 0.104 (5 of 79 gold edges); guarded by `test_measurement_sample_results_never_enter_the_scored_graph` |
| 2026-10-10 | rehearsal scoring of the existing `slice3_c2` graph on sections 1.5 / 2.6 (first computation) | same converter defect (negligible there: strict F1 0.096 became 0.097) | superseded by the corrected values |

Nothing was tuned on any of these numbers.
