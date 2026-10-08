# CR-011 revised STOP 3 - local review-ranking evaluation (pre-registered 2026-10-09, before any score on the dev labels)

Authority: Research decision 2026-10-09 (Option A). No paid call. Automatic ML/LLM merging is not eligible (`t_auto` disabled; the production merge-precision / Wilson gate is NOT_EVALUABLE, neither PASS nor FAIL). Merge recall is not an arm-selection metric.

## Data
- Development labels: SLEEP-240 dev (3 SAME / 75 NOT_SAME / 2 UNSURE) and SLEEP-POS dev (8 / 71 / 1). Prevalences stay separate. MUST_REVIEW = SAME or UNSURE = 14 items.
- Eligible universe ("eligible pairs") = all candidate pairs of the post-canonicalisation graph that survive the hard guards: not CR-008 `different`, type-compatible under the frozen map (28,487 candidates, 13,394 survive). A labelled dev pair that is vetoed by a hard guard can never reach review; it is reported as a guard finding, and a MUST_REVIEW item that is vetoed or is not a candidate counts as NOT sent to review.

## Metrics
- ReviewRecall = MUST_REVIEW dev items sent to review / all 14. Hard requirement 1.00.
- ReviewReduction (primary) = 1 - reviewed_pairs / eligible_pairs over the eligible universe above. Secondary (reported, not the gate): the same ratio inside the labelled dev items that pass the guards.
- CR-008 DIFFERENT violations: pairs proposed for review that the lexicon forbids. Zero by construction (vetoed before ranking); counted.

## Configurations (fixed list; all local)
1. Single-feature rankers: name_cos, char_ratio, token_jaccard, def_cos (missing = 0), ev_cos, max(name_cos, def_cos, ev_cos).
2. `lr_similarity`: logistic regression on similarity features only (name_cos, def_cos, ev_cos, char_ratio, token_jaccard, containment, head_equal).
3. `lr_all`: logistic regression on all 29 features.
4. `gb_all`: gradient-boosted trees on all features.
Models are fitted on the guard-eligible dev items with target MUST_REVIEW (SAME or UNSURE = 1), grouped 5-fold CV by candidate family. Historical owner labels are NOT used here (structurally unlike the pool; STOP 2 finding).

## Threshold and evaluation procedure
- Out-of-fold scores on the dev items; review threshold t = the lowest out-of-fold score among the 14 MUST_REVIEW items that are eligible (so dev ReviewRecall = 1.00 by construction, honestly out-of-fold).
- The final model is refitted on all eligible dev items and applied to the whole eligible universe; reviewed_pairs = pairs with score >= t; ReviewReduction = 1 - reviewed / eligible.
- Selection: among configurations with ReviewRecall = 1.00 and zero DIFFERENT violations, the maximum ReviewReduction; ties (within 0.005): simpler model, fewer features, lower runtime. The configuration, its t and the model are frozen before any held-out label is opened.

## Continuation gate (Research)
- Best local configuration with ReviewReduction >= 25% AND ReviewRecall = 1.00: STOP 4 may proceed (both held-out sets, separately).
- Otherwise: STOP CR-011 after STOP 3, no paid call, record NO PRODUCTION CHANGE; S-AGG is not run in CR-011.

## Caveats stated in advance
- ReviewRecall is measured on 14 labelled must-review items; unlabelled duplicates in the universe may sit below t. This is a development estimate, tested only by the held-out sets.
- The 160 dev items are a stratified/enriched sample, not the natural pair distribution; that is why the primary reduction is computed on the whole eligible universe.
