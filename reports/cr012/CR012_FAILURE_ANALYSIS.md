# CR-012 failure analysis and future research hypotheses

This document proposes follow-up research. It does **not** modify CR-012; none of it was implemented or tested here.

## Failure taxonomy (measured, held-out)

| stage | P&D E0 share of misses | SciNLP E0 share of misses |
|---|---|---|
| N0 concept not extracted | 67 (16.1%) | 255 (89.8%) |
| N1 wrong / partial span | 34 (8.2%) | 7 (2.5%) |
| C0 concept split | 79 (19.0%) | 0 (0.0%) |
| C1 false merge | 1 (0.2%) | 0 (0.0%) |
| P0 pair not delivered | 206 (49.5%) | 15 (5.3%) |
| R0 classifier said no relation | 16 (3.8%) | 2 (0.7%) |
| R1 wrong relation | 6 (1.4%) | 5 (1.8%) |
| R2 wrong direction | 1 (0.2%) | 0 (0.0%) |
| R3 type / qualifier | 6 (1.4%) | 0 (0.0%) |
| E0 evidence invalid | 0 (0.0%) | 0 (0.0%) |

## Hypotheses (for later change requests)

1. **High-recall pair delivery / candidate generation.** In P&D, 49.5% of E0 misses are P0 and pair recall is 16.3%; the oracle uplift E2 -> E3 is the largest (+0.269). Hypothesis: a higher-recall, budget-aware candidate stage would recover more gold edges. To test: recall-vs-cost curves on development data, then a single held-out confirmation.
2. **Concept extraction recall, especially out of domain.** In SciNLP, N0 dominates (89.8%) and E0 -> E1 is the largest uplift. Hypothesis: domain-adaptive extraction (without over-narrowing precision) is the lever for external transfer.
3. **Relation acceptance / classification after endpoint recovery.** At E3, about 30% of pairs with an edge have the wrong relation or direction, and many gold pairs receive no relation (R0). Hypothesis: calibrated acceptance and relation choice could raise the ceiling above E4 = 0.470.
4. **Redesign the canonicalisation stability diagnostic.** The frozen disagreement rate is non-informative under its denominator. Proposal (future work / CR-013, not applied post-test): restrict the denominator to candidate identity decisions (pairs of mentions that either run linked, or that share a surface form), and report counts alongside the rate.
5. **Independently double-annotated P&D gold.** Obtain a second human annotator on at least 25-30% of the held-out sections (4.4 and 9.3 were designated) and report agreement before drawing stronger conclusions about the exact gold graph.

## Not recommended from these results

- Changing the pair budget, ranking, coverage policy or thresholds inside CR-012 based on these numbers.
- Narrowing concept extraction because SciNLP precision is low (over-extraction relative to selective annotation is an architecture-transfer outcome).
- Reading E4 as achievable accuracy, or summing oracle uplifts as if they were additive.
