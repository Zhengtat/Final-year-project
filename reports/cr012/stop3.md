# CR-012 STOP 3 - development rehearsal on the pilot, scorer validation and cost measurement ($1.05)

Scope: SciNLP train/dev and the P&D pilot only. No held-out unit and no SciNLP test document was run. STOP 3 is **partly complete**: the P&D track and the scorers are ready; the SciNLP model track waits for a Research decision (section 5).

## 1. Scorer validation ($0) - `scorer_validation.md`
Perfect prediction = 1.0 on both scorers; each corruption moves the score by its constructed value (SciNLP train 51 / dev 6 documents; pilot sections 1.5 and 2.6).

## 2. Per-section E0 runner (`cumap.cr012.unit_run`)
The frozen production stages run as a one-section slice with a fresh run id (`CUMAP_DEMO_SLICE` points the unchanged config loader at the unit's slice file; the default production slice is untouched). Recipe = the CR-009 final run: pruner off (tau 0), strict G-links, type-aware canonicalisation (v2, 0.70 band as in S0), anchor-first selection, relations family v3 / choice v4 / qualifiers v4, registry v1.3. The only evaluation-specific input is the D3 pair budget. The production select step also classifies a 50-pair unselected measurement sample that never enters the graph; the runner switches it off (selected pairs verified identical, test + run-time check). Gold is never read by the runner.

## 3. Pilot E0 rehearsal (not a result; never tuned on)
| section | words | gold headline edges | pool / budget / selected | predicted edges | strict E2E P / R / F1 | pair recall | canonical-node F1 | identity pairwise F1 | cost |
|---|---|---|---|---|---|---|---|---|---|
| 1.5 | 3,643 | 39 | 165 / 52 / 52 (saturated) | 27 | 0.074 / 0.051 / 0.061 (2 correct) | 4 of 18 reachable | 0.623 | 0.546 | $0.39 |
| 2.6 | 2,921 | 79 | 187 / 42 / 42 (saturated) | 17 | 0.294 / 0.063 / 0.104 (5 correct) | 10 of 51 reachable | 0.685 | 0.771 | $0.66* |
| pooled | 6,564 | 118 | | 44 | 0.159 / 0.059 / **0.086** (7 correct) | | | | $1.05 |

*includes $0.41 for the measurement sample (not needed). The existing `slice3_c2` graph scores F1 0.118 (1.5) and 0.097 (2.6) on the same gold.

**Correction.** An earlier in-session figure for section 2.6 (strict F1 0.21, 12 correct edges) was wrong: my graph converter did not exclude the measurement-sample results from the graph, and the fix I thought I had applied had not taken effect. A test now guards it (`test_measurement_sample_results_never_enter_the_scored_graph`); the numbers above are the corrected ones.

What the rehearsal shows (observations, no tuning): the exhaustive gold holds 10.7 (1.5) and 27.0 (2.6) headline edges per 1k words against a D3 budget of 14.2 pairs per 1k words, so the budget is saturated in both sections and pair recall is low (22% and 20% of the gold edges whose endpoints exist); E3 will quantify that loss. Node quality is moderate (canonical-node F1 0.62-0.69). When a gold pair was classified the relation and direction were right 7 times out of 11.

## 4. Measured cost and refreshed preflight
Measured E0 on section 1.5: concepts $0.0033 and canonicalisation $0.0165 per 1k words, relations $0.0062 per selected pair; about $0.11 per 1k words. Refreshed full-plan estimate (`cost_preflight.json`): **$29.7 (cache sharing) to $38.4 (none)** against the $50 cap and $40 soft warning. Spent so far in CR-012: **$1.05**.

## 5. What is not done, and why
- **SciNLP model runs (E0/E1/E3-M/E4-M, dev rehearsal): blocked** on a Research decision about the external schema (node types and extraction scope are hard-coded for networking in the generator prompt and schema; a SciNLP relation registry must be authored). Draft proposal in the previous report; no SciNLP data has entered any prompt.
- **Freeze of evaluation code/config** (`configs/cr012_e2e_eval.yaml`): the P&D side can be frozen now; the SciNLP side cannot until the schema decision. Nothing was tuned.
- Pilot E1-E4 rehearsals ($0.5-1) were not run; they can follow if wanted before the freeze.
