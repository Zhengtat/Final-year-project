# CR-019 Stage B — multi-sentence evidence for relation classification

Pre-registered 2026-10-15 (DECISIONS.md). SINGLE = production relation stage (family v3 / choice v4 / qualifiers v4, first co-occurring sentence); MULTI = family v4 / choice v5 / qualifiers v5 on up to 3 co-occurring sentences of the same section, on a copy of the SINGLE run (same concepts, same selected pairs). Data: SciNLP dev (6 papers, runs `cr012_scinlp_cr019dev_*_E0`) and P&D development sections 1.5, 2.6 (`cr012_pilot_*_E0`). Spend: **$6.49** of the $25 cap.

**Recommendation (pre-registered rule): KEEP_SINGLE** — SciNLP dev IDX-P1 F1 Δ -0.010, P&D dev Strict E2E F1 Δ +0.025.

## SciNLP dev (strict relation, mention level)

| arm | variant | edges placed / predicted | P | R | F1 |
|---|---|---|---|---|---|
| SINGLE | `FROZEN` | 52 / 131 | 0.154 | 0.045 | **0.069** |
| SINGLE | `FROZEN-UNPLACED-FP` | 52 / 131 | 0.061 | 0.045 | **0.052** |
| SINGLE | `IDX-P1` (primary) | 125 / 131 | 0.114 | 0.084 | **0.096** |
| SINGLE | `IDX-P3` | 126 / 131 | 0.116 | 0.112 | **0.114** |
| MULTI | `FROZEN` | 56 / 143 | 0.140 | 0.045 | **0.068** |
| MULTI | `FROZEN-UNPLACED-FP` | 56 / 143 | 0.056 | 0.045 | **0.050** |
| MULTI | `IDX-P1` (primary) | 135 / 143 | 0.096 | 0.078 | **0.086** |
| MULTI | `IDX-P3` | 138 / 143 | 0.082 | 0.089 | **0.085** |

Relation-stage outcomes on selected pairs:

- SINGLE: {'edge': 132, 'no_relation': 162, 'other': 97, 'rejected:endpoint_not_grounded': 3, 'rejected:domain_range': 62}
- MULTI: {'edge': 145, 'rejected:domain_range': 64, 'rejected:endpoint_not_grounded': 4, 'no_relation': 135, 'other': 108}

## P&D development sections (CR-017 five metrics)

| arm | node positions | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 | Strict E2E Edge F1 (P / R) |
|---|---|---|---|---|---|---|
| SINGLE | `FROZEN` | 0.630 | 0.133 | 0.212 | 0.600 | 0.086 (0.159 / 0.059) |
| SINGLE | `IDX` | 0.643 | 0.133 | 0.203 | 0.600 | 0.086 (0.159 / 0.059) |
| MULTI | `FROZEN` | 0.630 | 0.133 | 0.212 | 0.686 | 0.112 (0.209 / 0.076) |
| MULTI | `IDX` | 0.643 | 0.133 | 0.203 | 0.686 | 0.112 (0.209 / 0.076) |

Relation-stage outcomes on selected pairs:

- SINGLE: {'no_relation': 22, 'other': 22, 'rejected:endpoint_not_grounded': 2, 'edge': 44, 'rejected:domain_range': 4}
- MULTI: {'no_relation': 17, 'other': 27, 'edge': 43, 'rejected:domain_range': 4, 'rejected:endpoint_not_grounded': 3}

Spend per run: {'cr012_scinlp_cr019dev_2021_acl_long_295_E0': 0.5975, 'cr012_scinlp_cr019dev_2024_acl_long_144_1_9_grobid_E0': 0.701, 'cr012_scinlp_cr019dev_P16_1007_grobid_E0': 0.5856, 'cr012_scinlp_cr019dev_P02_1004_grobid_E0': 0.0032, 'cr012_scinlp_cr019dev_P03_1014_grobid_E0': 0.5507, 'cr019b_multi_cr012_scinlp_cr019dev_2021_acl_long_295_E0': 0.6173, 'cr019b_multi_cr012_scinlp_cr019dev_2024_acl_long_144_1_9_grobid_E0': 0.5699, 'cr019b_multi_cr012_scinlp_cr019dev_P05_1008_grobid_E0': 0.2844, 'cr019b_multi_cr012_scinlp_cr019dev_P16_1007_grobid_E0': 0.5055, 'cr019b_multi_cr012_scinlp_cr019dev_P02_1004_grobid_E0': 0.4585, 'cr019b_multi_cr012_scinlp_cr019dev_P03_1014_grobid_E0': 0.4995, 'cr019b_multi_cr012_pilot_1_5_E0': 0.4308, 'cr019b_multi_cr012_pilot_2_6_E0': 0.6893}
