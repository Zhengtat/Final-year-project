# CR-012 cost

- Spent before STOP 4 (pilot, rehearsal, oracle development): $2.8539
- STOP-4 model spend: **$23.07** (main held-out $16.38; stability repeats $6.7)
- **Cumulative CR-012 spend: $25.9265**. Forecast $28.09-$33.92 (approved); soft warning $40 and hard cap $50 were never reached. No optional paid benchmark was run, and STOP 5 made no model call.

| level | P&D USD | SciNLP USD |
|---|---|---|
| E0 | 3.7736 | 1.9315 |
| E1 | 3.7082 | 1.1904 |
| E2 | 2.2822 | NOT_SUPPORTED |
| E3 | 2.2166 | 1.2727 |
| E4 | 0.0 | 0.0 |

E4 costs $0 on both benchmarks because it reuses the E3 classifications of the identical gold pairs from the cache (byte-identical calls).

E0 spend per correctly recovered edge: P&D $0.24 (16 correct edges); SciNLP $0.24 (8 correct relations). With so few correct edges this ratio is descriptive only and is not a cost-effectiveness claim.

Figure: `figures/cost_per_correct_edge_e0.svg`.
