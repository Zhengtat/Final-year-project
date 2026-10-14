# CR-017 STOP 3 — unified five-metric evaluator

Written for: Research. Scorer/reporting only: no model call, no frozen artefact written to. Code `src/cumap/cr017/{headline,hierarchy,run}.py`, config `configs/cr017_eval.yaml`, tests `tests/test_cr017_headline.py` (14) and `tests/test_cr017_hierarchy.py` (16). Research rulings applied: untyped canonical-node F1 is the Concept headline; relation-scorer semantics as proposed at STOP 1.

## Entry point and contract
`evaluate(units, symmetric)` (`headline.py`) returns `{"headline": {concept_f1, ancestor_hierarchy_f1, pair_recall, relation_macro_f1, strict_e2e_edge_f1}, "diagnostics": {...}}`; `run.evaluate_run(tag, level)` wraps it with the CR-017 §19 envelope (schema version, prediction/gold artefacts, scorer version, provenance with prediction, gold and config hashes, code revision, scorer-file hashes). Not-evaluable metrics return `status = NOT_EVALUABLE` with a reason and `null` values (never 0): tested for hierarchy without gold (`HIERARCHY_GOLD_GAP`) and for an empty relation population. The five metrics are never combined (`composite_score: false`).

## Reuse versus new
| metric | implementation |
|---|---|
| Concept F1 | frozen CR-012 `canonical_node` (untyped), via `score_graph_unit` |
| Ancestor Hierarchy F1 | CR-017 STOP-2 scorer (approved) |
| Pair Recall | frozen CR-012 `pair_recall` via `score_graph_unit`; unordered pair |
| Relation Macro F1 | **new**: gold edges with both endpoint nodes whose pair reached classification; classifier edge relation is the prediction (gold relation preferred if the classifier produced it); `other` / `no_relation` / `rejected` / gated-away = false negative for the gold class, no false positive for any class; macro over classes with gold support; direction accuracy and micro F1 are diagnostics; classes with support ≤ 3 flagged |
| Strict E2E Edge F1 | frozen CR-012 `strict_e2e_edge` via `score_graph_unit`; qualifiers stay outside the strict key (secondary `qualifier_accuracy`) |
| Intervals | section bootstrap, same RNG recipe as `cr012/bootstrap.py` (tested to give the identical interval); `NOT_EVALUABLE_SMALL_N` below 10 sections |
Legacy outputs are all kept in `diagnostics.legacy` (typed canonical node, typed mentions, identity pairwise/B-cubed, relation_conditional, relation_confusion, qualifier accuracy, alignment) and the old `reports/cr012` artefacts are untouched.

## Reproduction of the frozen scorer (the compatibility gate)
On the 7 frozen held-out E0 runs the new evaluator returns **exactly** the CR-012 numbers: Strict E2E tp/fp/fn 16 / 158 / 410 (F1 0.0533, interval [0.0302, 0.0763], same as `stop4_heldout_results.json`); Concept (untyped canonical node) 427 / 363 / 112 (F1 0.6426); Pair Recall 53 / 326 with 100 excluded; the legacy conditional population 32 gold edges. This is a regression test (`test_reproduces_the_frozen_cr012_headline_numbers_exactly`).

## Evaluator output on the frozen held-out E0 runs (validation run; the official replay with oracle levels E1–E4 is STOP 4)
| metric | score | 95% CI (section bootstrap, descriptive) | counts |
|---|---|---|---|
| Concept F1 (untyped canonical node) | 0.643 | [0.589, 0.698] | 427/363/112 (tp/fp/fn) |
| Ancestor Hierarchy F1 | 0.114 | [0.077, 0.156] | 7/41/68 (tp/fp/fn) |
| Pair Recall | 0.163 | [0.139, 0.186] | 53/326 reached |
| Relation Macro F1 | 0.484 | [0.302, 0.632] | 53 gold edges that reached the classifier, 11 classes |
| Strict E2E Edge F1 | 0.053 | [0.030, 0.076] | 16/158/410 (tp/fp/fn) |

Relation classes (pooled over the 7 held-out sections; support = gold edges that reached the classifier):
| relation | gold support (reached) | tp | fp | fn | F1 | low support (≤ 3) |
|---|---|---|---|---|---|---|
| acts_on | 12 | 4 | 0 | 8 | 0.500 |  |
| connected_to | 1 | 0 | 0 | 1 | 0.000 | yes |
| contrasts_with | 7 | 1 | 0 | 6 | 0.250 |  |
| decreases | 1 | 1 | 0 | 0 | 1.000 | yes |
| has_property | 1 | 1 | 0 | 0 | 1.000 | yes |
| has_purpose | 6 | 1 | 0 | 5 | 0.286 |  |
| increases | 1 | 0 | 0 | 1 | 0.000 | yes |
| is_a | 8 | 7 | 2 | 1 | 0.824 |  |
| part_of | 3 | 1 | 2 | 2 | 0.333 | yes |
| performs | 1 | 1 | 2 | 0 | 0.500 | yes |
| requires | 0 | 0 | 2 | 0 | n/a |  |
| uses | 12 | 6 | 1 | 6 | 0.632 |  |

Relation diagnostics: micro P/R/F1 = 0.719 / 0.434 / 0.541; direction accuracy given a correct label 0.957; classifier outputs that left no relation prediction: {'other': 8, 'no_relation': 6, 'rejected': 7}. Six of the eleven classes have support ≤ 3, so the macro F1 is unstable (its interval is wide); per-class supports are always published beside it.

## Fixtures
Relation macro: perfect/wrong/no-prediction cases; `other`, `no_relation`, `rejected` create false negatives only; predicted-only classes are outside the macro mean; low-support flag; empty population is not-evaluable; reached-classifier filter; missing-endpoint exclusion; wrong direction is a diagnostic, symmetric relations ignore orientation. Evaluator: reuse of the frozen scorers on a synthetic unit; unordered Pair Recall; hierarchy NOT_EVALUABLE without gold and scored with gold; bootstrap equality with the CR-012 recipe; config checks.

## Status
STOP 3 complete; nothing was rerun and nothing historical changed. Next: STOP 4 historical replay over the frozen artefacts (E0–E4, pilot and held-out), producing `historical_replay.md`, `headline_metrics.json`, `diagnostics.json`, with hierarchy `NOT_EVALUABLE` where gold is absent (SciNLP).
