# CR-012 STOP 3 return packet

Written for: Research (decision before STOP 4). Development rehearsal only; nothing here is a result, nothing was tuned.

## 1. P&D pilot E0-E4 (section 1.5, corrected evidence-grounded converter)
| level | strict E2E P / R / F1 | pair recall | canonical-node F1 | typed mention F1 | $ |
|---|---|---|---|---|---|
| E0 | 0.074 / 0.051 / 0.061 | 4/18 | 0.597 | 0.181 | 0.3932 |
| E1 | 0.091 / 0.051 / 0.066 | 3/35 | 0.766 | 0.957 | 0.4575 |
| E2 | 0.400 / 0.205 / 0.271 | 12/39 | 1.000 | 0.957 | 0.3232 |
| E3 | 0.583 / 0.538 / 0.560 | 39/39 | 1.000 | 0.957 | 0.2172 |
| E4 | 0.840 / 0.538 / 0.656 | 39/39 | 1.000 | 0.957 | 0.045 |

Section 2.6: E0 only (strict 0.294 / 0.063 / 0.104, 5 of 79 gold edges, pair recall 10/48, canonical F1 0.652). E1-E4 for 2.6 were dry-run only (plumbing verified) to stay inside the $1.50 pilot cap; the E3/E4 checkpoints in `data/processed` are empty dry-run artefacts and are excluded from the report.
Waterfall (1.5): resolution of mentions (E1) adds little; identity oracle (E2) +0.21; pair delivery (E3) +0.29; relation oracle (E4) +0.10. Gold density (10.7 headline edges / 1k words) is below the budget (14.2 pairs / 1k words), but the budget is saturated (pool 165 > budget 52), so pair selection under the fixed budget caps E0 pair recall. These are observations; no pair-budget, ranking, coverage or threshold change is proposed.

## 2. SciNLP train/dev rehearsal (E0, 2 dev documents, test split unopened)
| doc | entity strict P / R / F1 | relation strict P / R / F1 | gold entities / relations | $ |
|---|---|---|---|---|
| P02-1004.grobid | 0.163 / 0.457 / 0.241 | 0.200 / 0.167 / 0.182 | 35 / 6 | 0.559 |
| P05-1008.grobid | 0.070 / 0.333 / 0.116 | 0.000 / 0.000 / 0.000 | 12 / 0 | 0.331 |

Zero mentions fell off a token boundary; one negated relation was dropped (never a positive edge). Precision is low because the pipeline extracts far more concepts than the benchmark annotates; this is an architecture-transfer finding, not a tuning target. P05-1008 has 0 gold relations, so its relation precision is undefined/zero by construction.

## 3. Scorer / oracle validation
See `scorer_validation.md` (perfect = 1.0, corruptions move scores by constructed amounts, SciNLP train/dev and P&D pilot) and the new homograph / evidence-window tests; 708 tests pass, ruff clean on changed files.

## 4. Invalid / superseded runs
See `invalid_runs.md`: (a) 2.6 in-session F1 0.21 (sample counted as edges); (b) global string-match converter (1.5 oracle numbers E0 0.061 / E1 0.066 / E2 0.169 / E3 0.453 / E4 0.531). Both were converter defects, runs valid. (c) First SciNLP relation stage crashed on the CUM-only `action_type` qualifier lookup in `build_qualifiers_v3` (no spend lost; fixed with a default-path-identical `.get`, a plumbing defect, not tuning). Note: `stop3.md` section 3 canonical/pair-recall columns predate the grounded converter; this packet supersedes them.

## 5. Frozen hashes
git head at freeze: `787313bcc2882ed04907bc2a031d12c70c5aa656`; full list in `frozen_hashes.json` (schema freeze + final freeze: all `src/cumap/cr012/*.py`, concepts_v4 schema/loop/runner/cr009_run, config.py, relations_v3.py, prompts, registries, eval config `stop3-frozen`).
SciNLP schema: scinlp_profile `58b07157333e`, scinlp_relation_registry `2446acb2febd`, scinlp_generator_prompt `714113c983df`

## 6. Pair budget
`B(u) = min(candidate_pool_size, max(1, ceil(14.2 * word_count / 1000)))`; SciNLP dev: 62 of pool 100, 45 of pool 45 (both saturated).

## 7. Models / prompts
Tiers from `configs/default.yaml`: strong `gpt-6-sol` (medium), bulk `gpt-6-luna` (low); prompts: concept_generator v4 (CUM) / v4_scinlp (SciNLP), canonicalize v2, relation_family v3, relation_choice v4, relation_qualifiers v4; registry v1.3 (P&D), relations_scinlp (SciNLP).

## 8. Cost
Spent so far on CR-012 model runs: **$2.8539** (`spend_to_date.json`; pilot oracles 1.04, pilot E0 1.05, SciNLP dev 0.76).
Refreshed mandatory STOP-4 plan from measured rates: upper (no cache sharing) $33.92 total incl. stability (held-out P&D $13.28, SciNLP $9.07, stability $6.03); lower $28.09. Below the $40 soft warning; hard cap $50 not threatened. (Estimate's 'pilot' line is superseded by actual spend above.)

## 9. Isolation
SciNLP test split and P&D held-out sections: not opened by any model (`run_doc` refuses the test split; isolation scan CLEAN).

## Open owner items
Copy reviewed pilot sheet into `data/gold/` and restore the blank interim sheet; held-out annotation and second annotator still pending. STOP 4 not started.
