# CR-013 STOP 4: evaluation overlay

Scope (Research STOP-4 authorisation): strictly separated CR-012 / SciNLP evaluation overlays for gold comparison, earliest-failure explanation and an aggregate failure map linked to concrete examples. **$0, no model call, no prediction rerun, no gold reinterpretation:** the overlay reads only the frozen CR-012 outputs (tag `cr012-stop4-complete`, commit `4697acb`: `reports/cr012/stop4_heldout_results.json`, the retained E0 checkpoints, the benchmark gold and the frozen `cumap.cr012.attribution` functions). The codes are explained as observations of the frozen run; nothing here is a production decision rule.

## 1. Design and separation

- **A separate, opt-in mode.** A third top-level button, `CR-012 evaluation overlay`, styled as a warning, opens the overlay; the production P&D views never show it. A permanent banner reads *EVALUATION OVERLAY — EVALUATION OUTPUT, gold-derived. NOT the production Expert KG*, and the same page states that the codes are observations, not decision rules.
- **A separate payload.** The overlay is its own gzip blob (`eval-gz`), decoded only when the user opens the mode (verified in a real browser: it stays undecoded through every production view). The production trace blob (`trace-gz`) contains no gold, scorer, `cr012` or SciNLP data, and the trace-layer JavaScript contains no reference to the overlay.
- **A separate module.** `src/cumap/explain/eval_adapter.py` (and `why_not_eval.py`, `eval_report.py`) are the only explain modules that import `cumap.cr012` or read the gold; a test enforces this.
- **Dataset scoped, never pooled.** SciNLP held-out (3 documents) and P&D held-out (7 sections, *not* the Chapters 1-3 graph) are separate datasets with separate headline numbers and separate failure maps; unit ids are disjoint and each list shows one dataset.

## 2. What the overlay shows

- **Failure map.** Per dataset: the frozen headline (F1, precision, recall, CI status), a stacked bar of the earliest failure of every missed gold relation, a document / section x code matrix (click a count to list those gold relations), a glossary of the ten codes with the frozen wording and one concrete example each, and the frozen oracle ladder as context.
- **Gold relations.** A filterable list (code, strict-match status, unit, text search); selecting a relation opens its explanation in the detail panel.
- **Explanation of one gold relation.** The source sentence with the gold endpoints highlighted, the frozen earliest-failure code with its plain meaning, the ordered stage checks with the decisive check marked and later stages shown as *not evaluated*, what the run retained for the endpoints (predicted nodes and relations), the selection context (budget, selected, eligible-pool size), and, for SciNLP, a link that opens the missed relation in the SciNLP evaluation graph.

## 3. Frozen outputs, reproduced exactly

Every per-relation code is the frozen `attribute()` applied to that relation's facts; the builder asserts that the pooled and per-unit counts equal `stop4_heldout_results.json`, and a test repeats the check. SciNLP codes are also checked relation by relation against the frozen `sc_attribution`.

### SciNLP held-out (3 test documents), E0

Headline (frozen): strict relation F1 (mention level) F1 **0.050** (P 0.364 / R 0.027); CI status NOT_EVALUABLE_SMALL_N. SciNLP has no identity gold, so C0 / C1 are not applicable.

| document | gold | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | none | F1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021.acl-long.353 | 164 | 147 | 2 | 0 | 0 | 6 | 2 | 2 | 0 | 0 | 0 | 5 | 0.046 |
| 2024.acl-long.108-1-9 | 130 | 107 | 5 | 0 | 0 | 9 | 0 | 3 | 0 | 0 | 0 | 6 | 0.057 |
| P17-1058 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000 |
| **pooled** | 295 | 255 | 7 | 0 | 0 | 15 | 2 | 5 | 0 | 0 | 0 | 11 | |

### P&D held-out (7 sections, not the Chapters 1-3 graph), E0

Headline (frozen): STRICT_E2E_EDGE (canonical graph) F1 **0.053** (P 0.092 / R 0.038); CI status DESCRIPTIVE_SMALL_N (NOT_EVALUABLE_SMALL_N). 

| section | gold | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | none | F1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4.4 | 64 | 13 | 1 | 12 | 0 | 32 | 3 | 0 | 0 | 0 | 0 | 3 | 0.070 |
| 4.5 | 49 | 4 | 4 | 12 | 0 | 25 | 1 | 0 | 0 | 1 | 0 | 2 | 0.062 |
| 5.4 | 58 | 13 | 6 | 9 | 0 | 22 | 1 | 2 | 0 | 1 | 0 | 4 | 0.096 |
| 6.3 | 49 | 6 | 8 | 13 | 0 | 20 | 2 | 0 | 0 | 0 | 0 | 0 | 0.000 |
| 7.1 | 69 | 10 | 3 | 9 | 1 | 36 | 5 | 2 | 1 | 1 | 0 | 1 | 0.021 |
| 8.2 | 64 | 6 | 7 | 19 | 0 | 25 | 0 | 1 | 0 | 2 | 0 | 4 | 0.085 |
| 9.3 | 79 | 15 | 5 | 5 | 0 | 46 | 4 | 1 | 0 | 1 | 0 | 2 | 0.039 |
| **pooled** | 432 | 67 | 34 | 79 | 1 | 206 | 16 | 6 | 1 | 6 | 0 | 16 | |

## 4. Failure-localisation fixture results (frozen attribution order)

| fixture | expected | localised | frozen wording shown |
|---|---|---|---|
| source endpoint never extracted | N0 | N0 OK | At least one of the two concepts is not a node of the final graph, so no relation between … |
| target endpoint extracted with a wrong span | N1 | N1 OK | A gold endpoint was extracted, but with a span that does not match the gold span exactly.… |
| source endpoint is a false merge | C1 | C1 OK | A node merged two different gold concepts (a false merge), so the endpoint is not a faithf… |
| source concept split, pair lost | C0 | C0 OK | A gold concept was split across several nodes and the split lost the pair.… |
| endpoint pair never sent to the classifier | P0 | P0 OK | The pair was never sent to relation classification, so the classifier had no opportunity t… |
| classifier answered no relation | R0 | R0 OK | The pair was sent to relation classification and the classifier recorded that no accepted … |
| classifier chose another relation | R1 | R1 OK | The pair was classified but the relation chosen is not the gold relation.… |
| right relation, wrong direction | R2 | R2 OK | The right relation was chosen in the wrong direction.… |
| endpoint types fail the check | R3 | R3 OK | A relation was proposed for the pair but validation rejected it on a type or qualifier che… |
| evidence invalid | E0 | E0 OK | A relation was proposed for the pair but validation rejected it because an endpoint or the… |
| nothing lost (recovered) | none | none OK | The gold edge is present in the final graph.… |

**11 / 11** fixtures attributed to the intended stage (stage localisation accuracy 100%). On the real data, each relation's stage checks are also verified against its code (`test_each_relations_stage_checks_are_consistent_with_its_frozen_code`).

## 5. Gold-isolation tests

pytest (trace model, explorer, overlay): **53 passed in 13.88s**.

| test | what it proves |
|---|---|
| `test_only_the_evaluation_modules_read_gold_or_import_cr012` | only `eval_adapter`, `why_not_eval`, `eval_report` touch gold or `cumap.cr012` |
| `test_production_payload_is_free_of_the_overlay_and_any_gold` | the production trace payload contains no gold, frozen-run or SciNLP data |
| `test_the_overlay_has_its_own_payload_and_production_javascript_never_references_it` | the trace-layer JavaScript has no overlay symbol; page hooks to the overlay are guarded |
| `test_the_two_payload_blobs_are_separate_and_the_overlay_blob_matches_python` | `trace-gz` and `eval-gz` are separate, and the embedded overlay equals the Python build |
| `test_overlay_is_opt_in_not_decoded_before_and_never_leaks_into_production_views` | the overlay is undecoded until opened; production views and the page after leaving the mode contain no evaluation text |
| `test_overlay_is_dataset_scoped_and_pooled_counts_equal_the_frozen_results` | 295 SciNLP and 432 P&D gold rows, disjoint units, counts equal to the frozen results |
| `test_overlay_counts_equal_the_frozen_cr012_results_exactly`, `test_per_relation_codes_equal_the_frozen_scinlp_attribution` | no reinterpretation of the frozen attribution |

Real-browser checks (headless Chromium, `tests/js/take_eval_screenshots.py`):

```
{
 "overlay_payload_not_decoded_at_start": true,
 "production_views_show_no_gold_or_evaluation_text": true,
 "overlay_still_not_decoded_after_all_production_views": true,
 "opt_in_loads_the_overlay": true,
 "banner_marks_evaluation_output": true,
 "no_graph_tab_in_evaluation_mode": true,
 "scinlp_failure_map_shows_the_frozen_headline": true,
 "pd_overlay_is_a_separate_dataset": true,
 "matrix_cell_filters_the_gold_list": true,
 "detail_names_the_earliest_failure_and_marks_later_stages": true,
 "scinlp_detail_offers_the_graph_link_for_a_missed_relation": true,
 "open_in_graph_switches_to_the_scinlp_graph_and_selects_the_missed_edge": true,
 "leaving_the_overlay_returns_to_the_production_graph": true,
 "debug_view_keeps_the_overlay_open": true,
 "narrow_overlay_has_no_horizontal_page_scroll": true,
 "no_page_errors": true
}
```

## 6. Evaluation-mode screenshots (`reports/cr013/screenshots/`)

| file | shows |
|---|---|
| `15_eval_pd_failure_map.png` | P&D held-out failure map: headline, stacked bar, section x code matrix, glossary |
| `16_eval_pd_gold_relations_p0.png` | Gold relations filtered to P0 from a matrix cell |
| `17_eval_pd_detail_p0.png` | Explanation of one gold relation lost at P0 |
| `18_eval_pd_detail_r1_example.png` | Explanation of a wrong-relation (R1) example opened from the glossary |
| `19_eval_pd_narrow.png` | Narrow (390 px) layout |
| `20_eval_pd_dark.png` | Dark mode |
| `_eval_scinlp_failure_map / _eval_scinlp_detail.png` | SciNLP overlay (local only, gitignored: contains CC BY-NC text) |

## 7. What the overlay deliberately does not do

- It does not turn failure codes into decision rules, thresholds or recommendations for the production pipeline; the page says so wherever codes appear.
- It does not rerun any model, re-score, re-attribute or edit gold. The retained E0 predictions are only read.
- It does not pool SciNLP and P&D, and it does not show any CR-011 pre/post panel (CR011 = NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION; S0 / S1 not applicable).
- Oracle levels (E1-E4) appear only as the frozen F1 values with the caveat that they are conditional diagnostics, not an additive decomposition; no per-relation oracle traces are shown.
- Limits: E0 only; P&D held-out gold has a single human annotator; SciNLP C0 / C1 are not applicable (no identity gold) and one SciNLP document has a single gold relation; the pair pool is retained as a count only for these runs, so P0 explanations state the budget and pool size, not a rank.
