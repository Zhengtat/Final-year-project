# CR-011 STOP 2 - offline candidates, scorer and SLEEP-240 ($0, no API call)

Baseline snapshot: `slice3_c2` (1,243 nodes). Research rulings of 2026-10-08 applied (type map in config, `Concept` not a wildcard, alias-provenance classes). No held-out label exists or was opened; no scorer output or label was used to pick SLEEP-240 items.

## 1. Candidate generation (each source counted separately)

| source | pairs | exclusive to this source |
|---|---|---|
| lexicon_same | 1 | 0 |
| r1_key | 1 | 0 |
| token_overlap | 208 | 0 |
| r2_acronym | 1 | 0 |
| r3_strong | 1 | 1 |
| r3_weak | 2 | 1 |
| name_embedding | 17889 | 13754 |
| definition_embedding | 4825 | 3390 |
| evidence_embedding | 8939 | 5034 |
| graph_neighbours | 2086 | 1516 |
| same_surface | 1 | 0 |
| same_concept_queue | 1 | 1 |

- **Union: 28487 candidate pairs, 45.8 candidates per node** (retrieval floor only; no threshold here is an identity threshold).
- Hard guards before any scoring: {'type_incompatible': 15077, 'lexicon_different': 16}; **13394** pairs remain scoreable.
- The deterministic sources (R0/R1/R2/R3) add almost nothing: the online canonicalisation already applied them. Most sleep candidates come from embeddings and graph overlap, which are retrieval-only signals.

## 2. Historical owner labels: replay and candidate recall

- 86 labelled pairs ({'NOT_SAME/distinct_nodes': 2, 'NOT_SAME/partial': 9, 'NOT_SAME/same_node': 1, 'NOT_SAME/strings': 1, 'SAME/distinct_nodes': 1, 'SAME/partial': 16, 'SAME/same_node': 51, 'SAME/strings': 5}).
- Of the 73 SAME pairs, **51 were already merged online** (baseline successes), only **1** exist as two distinct nodes in this snapshot (candidate recall 1/1), and the rest name nodes that are not in `slice3_c2`.
- Name-level replay (the alias string as if it were a separate provisional node, partner aliases excluded): 11 pairs replayable, retrieved by {'name_embedding_top5': 7, 'token_overlap': 4, 'name_embedding_top20': 7, 'any_of_r1_token_name20': 7, 'r1_key': 1}; union recall 63.6% (definition/evidence/graph signals are unavailable for a bare string, so this is a lower bound).
- Lexicon `different`: 17 pairs exist as distinct nodes, 16 are among the candidates (all are vetoed before scoring).
- **Consequence:** the historical labels cannot measure sleep's candidate recall on the residual graph; the SLEEP-240 development labels must.

## 3. Scorer (development = historical owner labels, grouped 5-fold CV, out-of-fold metrics only)

- Training set: 107 pairs (73 SAME, 34 NOT_SAME incl. lexicon `different`), 80 normalised-form families. R0 `same` lexicon entries are deterministic-path positives and are excluded.
- Logistic regression: AUC 0.877, average precision 0.920; Platt calibration Brier 0.112, ECE 0.027 (before calibration ECE 0.084).
- Gradient-boosted ablation: AUC 0.881, average precision 0.932 (development ablation only; not production).
- Absent feature: concept_score (not stored on checkpoint nodes).

| feature group | AUC without it | delta | AUC with only it |
|---|---|---|---|
| lexical | 0.880 | +0.003 | 0.528 |
| embedding | 0.885 | +0.008 | 0.860 |
| alias | 0.846 | -0.031 | 0.490 |
| type | 0.868 | -0.009 | 0.761 |
| graph | 0.877 | +0.000 | 0.602 |
| chapter_recurrence | 0.886 | +0.009 | 0.859 |
| one_token | 0.875 | -0.002 | 0.582 |
| erst_context | 0.877 | +0.000 | 0.632 |

Interpretation limit: 107 pairs, mostly name-level strings; differences of a few hundredths of AUC are noise.

## 4. Operating points (proposed only where supportable)

- **`t_auto`: DISABLED: no threshold meets precision >= 0.98 with Wilson lower >= 0.95.** Best Wilson lower bound over thresholds on the labelled distribution: {'best_wilson_lower_over_thresholds': [0.827464, [0.9272727272727272, 0.8274005992784395, 55]]}. Under the CR rule ML auto-merge is disabled and the scorer is review-ranking only (a valid outcome).
- `t_review` (recover 90% of SAME in the labelled distribution): 0.649.
- **Predicted review volume: not forecastable from these labels.** Scoring the 13394 guard-surviving candidates gives calibrated scores with median 0.05 and 99.9th percentile 0.32, all below `t_review`: the band is empty. The historical positives (online-merged name variants) do not look like the residual pool, and the training prior is 68% SAME against an unknown, far lower pool base rate. This is a covariate and prior shift, not a finding about sleep.
- Planning figures that do not depend on the scorer: deterministic-source candidates 212, same-type pairs with name similarity >= 0.80 (not deterministic) 111, bridge-risk pairs 96, `same_concept` queue 1. The CR's call targets bound the LLM review band at <= 250 (development) and <= 150 (held-out).
- **Thresholds are therefore frozen only after the 80 SLEEP-240 development labels exist** (development per the CR = historical labels + SLEEP-240 development). No threshold is set now.

## 5. One-token diagnostics

- 374 one-token nodes; 13822 candidates involve one; 13812 of those carry only embedding/graph signals (embedding-only one-token auto-merge is forbidden, so they can only reach review).
- Scorer slice (out-of-fold): one-token pairs {'n': 56, 'pos': 34, 'auc': 0.9244652406417112, 'average_precision': 0.9428930164840569}; multi-token {'n': 51, 'pos': 39, 'auc': 0.8012820512820512, 'average_precision': 0.9135905487386652}.

## 6. SLEEP-240

- Status: **ok**. Strata availability before allocation: {'deterministic_r1_r3': 212, 'high_similarity_r4': 111, 'confusables_difficult_negatives': 950, 'one_token_polysemy': 507, 'cross_chapter_long_distance': 180, 'cluster_bridge_transitive_risk': 96}; every stratum filled to 40, shortfall none.
- Split by candidate family (shared node or normalised-form key): 136 families, largest 6; development 80 / held-out 160; leakage check: {'shared_families': 0, 'shared_nodes': 0, 'shared_normalised_keys': 0, 'ok': True}.
- Development by stratum {'cluster_bridge_transitive_risk': 14, 'confusables_difficult_negatives': 13, 'cross_chapter_long_distance': 13, 'deterministic_r1_r3': 14, 'high_similarity_r4': 13, 'one_token_polysemy': 13}; held-out {'cluster_bridge_transitive_risk': 26, 'confusables_difficult_negatives': 27, 'cross_chapter_long_distance': 27, 'deterministic_r1_r3': 26, 'high_similarity_r4': 27, 'one_token_polysemy': 27}.
- Sheets (contract columns only, A/B and item order randomised, no score/source/band/arm): `data/interim/checks/cr011/sleep240_dev_blind_sheet.csv` (80, sha256 `baab60d10008b5d4...`), `sleep240_heldout_blind_sheet.csv` (160, `a45503573b9c06d4...`); hidden manifest `sleep240_manifest_DO_NOT_SHARE.csv` (`fc4db83192a1d0c9...`) with 80 held-out items flagged for double annotation if a second annotator exists. Annotation codebook: `docs/annotation/sleep_merge_codebook.md`.
- Held-out labels stay sealed until STOP 4; held-out items may not enter prompts, rules or the lexicon.

## 7. Findings and items for Research (none requires a return under the STOP 1 rulings)

- Historical labels are structurally unlike the residual candidate pool (51 of 73 SAME pairs are already merged online, 1 is two distinct nodes). The scorer can be developed on them only as a name-level model; its calibration on the pool is unknown until the 80 development labels exist. No gate or threshold was changed.
- `concept_score` is not stored on checkpoint nodes; it is not a feature. If Research wants it as a feature, CR-009's pruner output would need to be persisted (a separate decision).
- Type map: 15,077 of 28,487 candidates (53%) are type-incompatible under the frozen map, which is the main driver of the small scoreable pool.

## 8. Cost

$0 (local embeddings, scikit-learn, no API call).

## Next

Owner: annotate `sleep240_dev_blind_sheet.csv` (80 items) per the codebook and save the marked copy under the gold folder. STOP 3 development ablations need those labels. The 160 held-out items can be annotated later, but must not be opened by any pipeline code before STOP 4.
