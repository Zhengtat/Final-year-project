# CR-012 oracle results and earliest-failure attribution

Each missed gold edge gets exactly one earliest failure code (S0/S1: NOT_APPLICABLE, CR-011 adopted no transformation). Oracle differences are **conditional / oracle uplifts**, not an additive causal decomposition.

## P&D

| level | misses | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | recovered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 416 | 67 | 34 | 79 | 1 | 206 | 16 | 6 | 1 | 6 | 0 | 16 |
| E1 | 397 | 5 | 1 | 206 | 23 | 143 | 12 | 7 | 0 | 0 | 0 | 35 |
| E2 | 391 | 0 | 1 | 0 | 0 | 319 | 47 | 23 | 1 | 0 | 0 | 41 |
| E3 | 279 | 0 | 1 | 0 | 0 | 0 | 211 | 65 | 2 | 0 | 0 | 153 |
| E4 | 279 | 0 | 1 | 0 | 0 | 0 | 211 | 65 | 2 | 0 | 0 | 153 |

- E0 earliest failures: pair delivery (P0) 206 / 416 = 49.5%; extraction (N0+N1) 101 / 416 = 24.3%; together 307 / 416 = 73.8%.
- E0 pair recall: 53 / 326 = 16.3% of gold edges whose endpoints existed reached relation classification (100 gold edges excluded for a missing endpoint node).
- Largest oracle uplift: E2 -> E3, F1 0.129 -> 0.398 (delta +0.269). The frozen candidate / pair-delivery stage is the largest demonstrated in-domain end-to-end bottleneck. This is not permission to change the pair budget in CR-012.
- Relation stage: when E3 produces an edge, relation correct 152 / 216 = 70.4%, direction correct 150 / 216 = 69.4%.

### Canonicalisation: held-out versus development pilot

Held-out: E1 0.113 -> E2 0.129, delta +0.016. The held-out experiment does **not** support canonicalisation as the dominant current bottleneck. The development pilot (section 1.5 only, development-only) showed E1 0.066 -> E2 0.271 (delta +0.206) and suggested otherwise. The held-out result has priority for final conclusions; the pilot discrepancy is reported, not hidden.

## SciNLP (mention level; C0/C1 not applicable)

| level | misses | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | recovered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 284 | 255 | 7 | 0 | 0 | 15 | 2 | 5 | 0 | 0 | 0 | 11 |
| E1 | 173 | 2 | 4 | 0 | 0 | 114 | 38 | 15 | 0 | 0 | 0 | 122 |
| E3-M | 126 | 2 | 4 | 0 | 0 | 1 | 99 | 20 | 0 | 0 | 0 | 169 |
| E4-M | 126 | 2 | 4 | 0 | 0 | 1 | 99 | 20 | 0 | 0 | 0 | 169 |

- E0 earliest failures are extraction: N0 255 / 284 = 89.8%. Cross-domain entity / concept extraction is the dominant observed SciNLP bottleneck; E0 -> E1 (0.050 -> 0.255) is consistent with this.
- E3-M -> E4-M (0.463 -> 0.473): comparatively limited remaining improvement at the classifier-ceiling step once endpoints are provided.

Figures (generated from the frozen results): `figures/pd_oracle_waterfall.svg`, `figures/earliest_failure_distribution.svg`, `figures/headline_e0_pd_vs_scinlp.svg`.
