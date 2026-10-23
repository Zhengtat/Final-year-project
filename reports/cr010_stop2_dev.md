# CR-010 STOP 2 — node residual recall, IIR dev (13 sections)

N0 = the frozen CR-009 pipeline (G1, depth 1, M4/M5 off, pruner tau 0.1, no strict G-links). Arms are post-passes over the N0 run; selection by the pre-registered rule (`configs/cr010_node.yaml`): exact micro F1 +0.02 or paired section-bootstrap 95% lower bound > 0, precision drop <= 0.02, tie band 0.02 (simpler wins), no change allowed.

## Metrics

| arm | predicted | exact P / R / **F1** | Δ F1 vs N0 | bootstrap 95% [lo, hi] | precision drop | lenient F1 | macro F1 | recall 1/2/3/4-gram (lenient) | one-token recall exact / lenient | rescue precision (exact) | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N0 | 582 | 0.435 / 0.522 / **0.474** | – | – | – | 0.605 | 0.467 | 0.651 / 0.681 / 0.684 / 0.375 | 0.547 / 0.651 |  | $0 (reused) |
| N1 | 617 | 0.438 / 0.557 / **0.490** | +0.016 | [+0.005, +0.027] | -0.003 | 0.612 | 0.482 | 0.703 / 0.698 / 0.702 / 0.375 | 0.605 / 0.703 | 19/35 | $0.0192 |
| N3 | 596 | 0.433 / 0.532 / **0.477** | +0.003 | [-0.005, +0.012] | +0.002 | 0.605 | 0.470 | 0.651 / 0.698 / 0.684 / 0.375 | 0.547 / 0.651 | 7/15 | $0.0021 |
| N2 | 612 | 0.435 / 0.548 / **0.485** | +0.011 | [+0.002, +0.022] | +0.000 | 0.613 | 0.477 | 0.669 / 0.714 / 0.702 / 0.500 | 0.581 / 0.669 | 16/35 | $0.0661 |

## Selection by the pre-registered rule

| arm | gain ok | precision ok | qualifies |
|---|---|---|---|
| N1 | True | True | True |
| N3 | False | True | False |
| N2 | True | True | True |

**Rule outcome: N1**

## N2 trigger (items per 100 words in N0's final output below theta)

| theta | sections resampled | exact P / R / F1 | cost of samples |
|---|---|---|---|
| 1.0 | 0 / 13 | 0.435 / 0.522 / 0.474 | (samples for all sections: $0.0661) |
| 1.5 | 0 / 13 | 0.435 / 0.522 / 0.474 | (samples for all sections: $0.0661) |
| 2.0 | 1 / 13 | 0.433 / 0.526 / 0.475 | (samples for all sections: $0.0661) |
| 2.5 | 2 / 13 | 0.432 / 0.528 / 0.475 | (samples for all sections: $0.0661) |
| 3.0 | 5 / 13 | 0.435 / 0.548 / 0.485 | (samples for all sections: $0.0661) |
| all | 13 / 13 | 0.410 / 0.579 / 0.480 | (samples for all sections: $0.0661) |

Frozen trigger rule: highest exact micro F1 on dev, ties to the smaller theta; 'all' is a reference only. Value on this split: **3.0** (to be written to `n2.trigger_frozen` BEFORE the test run).

## Rescue funnel (N1 / N3)

| arm | candidates | one-token candidates | add_new | link_existing | reject | proposed items | verified | deduplicated | pruned | kept | incomplete decisions | schema errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N1 | 331 | 260 | 28 | 21 | 282 | 49 | 40 | 4 | 1 | 35 | 0 | 0 |
| N3 | 71 | 0 | 7 | 11 | 53 | 18 | 16 | 2 | 0 | 14 | 0 | 0 |

## Candidate coverage of N0's residual gold (232 exact-unmatched gold terms)

- N1: residual gold in the candidate list 44/232; recovered by the rescue (kept, exact name) 15; candidate rejected by the model 26.
- N3: residual gold in the candidate list 17/232; recovered by the rescue (kept, exact name) 5; candidate rejected by the model 11.

Partial-span errors (false positives containing / inside a gold term), N0: {'over-specific (contains a gold term)': 31, 'over-general (inside a gold term)': 31}

- N1: {'over-general (inside a gold term)': 37, 'over-specific (contains a gold term)': 36}
- N3: {'over-specific (contains a gold term)': 35, 'over-general (inside a gold term)': 32}
- N2: {'over-specific (contains a gold term)': 34, 'over-general (inside a gold term)': 34}
