# CR-011 final report - sleep-phase consolidation: CLOSED, NO PRODUCTION CHANGE (Research decision 2026-10-09)

**Outcome:** `NO_PRODUCTION_CHANGE`. The existing CR-008 / CR-009 canonicalisation path remains the production architecture. No STOP 4, no STOP 5, no paid call, no migration. Both held-out sets (SLEEP-240 held-out, SLEEP-POS-160 held-out) remain sealed and were never inspected or annotated: held-out evaluation was not executed because the frozen development continuation criterion was not met.

## Findings (frozen by Research)

1. **Natural residual duplicate rate was low.** SLEEP-240 dev: SAME 3/80 = 3.75% (Wilson 95% [1.3%, 10.4%]), NOT_SAME 75, UNSURE 2. All 14 deterministic-stratum items were NOT_SAME.
2. **Positive enrichment still produced few duplicates.** SLEEP-POS dev: SAME 8/80 = 10.0%, NOT_SAME 71, UNSURE 1. The pre-registered viability gate (SAME >= 20) failed; the threshold was not lowered and enrichment was not retried. The two sets are never pooled: SLEEP-POS is deliberately enriched, so 11/160 is not a natural prevalence.
3. **Most high-similarity residual candidates were related but distinct** (related_other, kind_of and confusable account for 59 of the 71 SLEEP-POS negatives), consistent with upstream canonicalisation already resolving most straightforward duplicates.
4. **Local review ranking did not separate the remaining duplicates from related-but-distinct concepts well enough for safe review reduction.** Nine local configurations (six single-feature rankers, logistic on similarity features, logistic on all features, boosted trees), out-of-fold AUC about 0.40-0.55. The apparent pool-level reductions (evidence similarity about 46.8%, character ratio about 40.1%) are confounded by the similarity-enriched development sampling and are not evidence of useful review reduction.
5. **One hard type-guard false negative (`TYPE_GUARD_FALSE_NEGATIVE`).** SL080, gold SAME: "spectrum" (typed Parameter) and "electromagnetic spectrum" (typed Concept). Parameter-Concept is incompatible under the frozen CR-011 type map, so the pair is vetoed before ranking. Node-type noise or coarseness can make a hard identity guard reject a genuine SAME pair. The map was not changed (the failure was found from development gold after the map was frozen; relaxing it now would be a post-hoc change). A future design `HARD_INCOMPATIBLE` / `SOFT_TYPE_CONFLICT -> mandatory review` / `COMPATIBLE` is recorded for future research only.

## Continuation gate

Required: ReviewRecall = 1.00 AND ReviewReduction >= 25%. Maximum ReviewRecall over all tested configurations: 13/14 = 0.929 (SL080 vetoed). **Gate NOT PASSED.** CR-011 stops under the frozen rule. S-AGG and every paid LLM arm were not run.

## Gate and status table (nothing unevaluated is marked PASS or FAIL)

| item | status |
|---|---|
| automatic merge precision | NOT_EVALUATED / NOT_APPLICABLE - no candidate architecture advanced |
| Wilson precision gate | NOT_EVALUATED / NOT_APPLICABLE |
| `t_auto` | DISABLED (no automatic ML/LLM merging is eligible) |
| STOP-4 held-out safety | NOT_RUN |
| STOP-5 rollback round trip | NOT_APPLICABLE_NO_MIGRATION |
| STOP-5 evidence retention | NOT_APPLICABLE_NO_MIGRATION |
| STOP-5 alias-provenance migration | NOT_APPLICABLE_NO_MIGRATION |
| production adoption | NO |

## What CR-011 produced and what it did not

- Produced (kept as research assets, not as production behaviour): multi-signal candidate generation over the post-canonicalisation graph (28,487 candidates, 13,394 guard-eligible), the type-compatibility map in config, the alias-provenance class rulings, SLEEP-240 and SLEEP-POS-160 (dev labels only used), the local ranking evaluation and its pre-registrations.
- Not produced: MergeTransaction / inverse / round-trip machinery (STOP 5), any migrated graph, any held-out result.
- Cost: $0 API throughout.

## CR-012 interpretation

CR-011 adopted no production graph transformation. The final production graph is the pre-CR-011 graph (`slice3_c2`); `reports/cr011_sleep/CR012_EVAL_HANDOFF.json` is a no-op closure handoff (`sleep_adopted = false`, `automatic_merge_enabled = false`, `post_sleep_state = no_op_same_as_pre_sleep`, `merge_transactions = []`, `edge_rewrites = []`, `id_map_status = identity_no_change`). CR-012 must not rerun the experimental CR-011 rankers and must not report a measured sleep delta of zero: no pre/post sleep accuracy experiment exists for the production pipeline. Canonicalisation error attribution remains available through CR-012's oracle experiments (E2).

## Deferred (not part of CR-011)

A full-book residual-duplicate study (CR-012 or later, when the 17-chapter graph exists naturally) and a pre-canonicalisation online-vs-deferred identity experiment (a different research question).

Detail: `docs/cr011/STOP1_RECONCILIATION.md`, `reports/cr011_sleep/stop2.md`, `sleep_pos160.md`, `stop2_dev_labels_return.md`, `sleep_pos_dev_viability_return.md`, `stop3_triage_result.md`.
