# CR-020 — R1-key matching in production (dev experiment)

Pre-registered in `docs/change-requests/CR-020-r1key-matching.md`. TOKEN = existing E0 runs; R1KEY = copies with pair generation, selection and the production relation stage re-run under `CUMAP_MATCHING=r1key` (concepts unchanged). Determinism check passed on all 8 runs. Spend **$0.11** of the $10 cap.

**Decision (pre-registered rule): ADOPT_R1KEY** — SciNLP dev IDXR1-P1 F1 Δ +0.023, P&D dev Strict E2E F1 Δ +0.000.

## SciNLP dev (6 papers)

| arm | predicted edges | IDXR1-P1 P / R / F1 | IDX-P1 F1 | IDXR1-P3 F1 | concept F1 | pair-recall analogue |
|---|---|---|---|---|---|---|
| TOKEN | 131 | 0.114 / 0.084 / **0.096** | 0.096 | 0.113 | 0.433 | 47 / 70 = 0.671 |
| R1KEY | 137 | 0.138 / 0.106 / **0.120** | 0.095 | 0.133 | 0.433 | 50 / 70 = 0.714 |

## P&D development sections 1.5, 2.6 (CR-017 five metrics)

| arm | Concept F1 | Pair Recall | Relation Macro F1 | Strict E2E Edge F1 (P / R) |
|---|---|---|---|---|
| TOKEN | 0.630 | 0.212 | 0.600 | 0.086 (0.159 / 0.059) |
| R1KEY | 0.630 | 0.212 | 0.600 | 0.086 (0.159 / 0.059) |

Relation outcomes on selected pairs:

- SciNLP TOKEN: {'edge': 132, 'no_relation': 162, 'other': 97, 'rejected:endpoint_not_grounded': 3, 'rejected:domain_range': 62}
- SciNLP R1KEY: {'edge': 138, 'no_relation': 162, 'other': 96, 'rejected:domain_range': 57, 'rejected:endpoint_not_grounded': 3}
- P&D TOKEN: {'no_relation': 22, 'other': 22, 'rejected:endpoint_not_grounded': 2, 'edge': 44, 'rejected:domain_range': 4}
- P&D R1KEY: {'no_relation': 21, 'other': 22, 'rejected:endpoint_not_grounded': 2, 'edge': 44, 'rejected:domain_range': 5}
