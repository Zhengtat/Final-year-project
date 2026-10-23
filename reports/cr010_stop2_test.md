# CR-010 STOP 2 — node residual recall, IIR test (70 sections) — HELD-OUT, run once

N0 = the frozen CR-009 pipeline (G1, depth 1, M4/M5 off, pruner tau 0.1, no strict G-links). Arms are post-passes over the N0 run. Criteria (`configs/cr010_node.yaml`): exact micro F1 +0.02 or paired section-bootstrap 95% lower bound > 0, precision drop <= 0.02. No selection happens on this split.

## Metrics

| arm | predicted | exact P / R / **F1** | Δ F1 vs N0 | bootstrap 95% [lo, hi] | precision drop | lenient F1 | macro F1 | recall 1/2/3/4-gram (lenient) | one-token recall exact / lenient | rescue precision (exact) | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N0 | 3730 | 0.447 / 0.569 / **0.501** | – | – | – | 0.592 | 0.506 | 0.758 / 0.680 / 0.568 / 0.421 | 0.696 / 0.758 |  | $0 (reused) |
| N1 | 3961 | 0.444 / 0.599 / **0.510** | +0.009 | [+0.005, +0.014] | +0.003 | 0.598 | 0.514 | 0.800 / 0.708 / 0.595 / 0.421 | 0.741 / 0.800 | 126/270 | $0.1057 |
| N3 | 3846 | 0.451 / 0.591 / **0.512** | +0.011 | [+0.007, +0.014] | -0.004 | 0.601 | 0.515 | 0.759 / 0.711 / 0.599 / 0.421 | 0.697 / 0.759 | 83/134 | $0.0407 |
| N2 | 3871 | 0.442 / 0.583 / **0.503** | +0.002 | [-0.000, +0.005] | +0.005 | 0.594 | 0.507 | 0.771 / 0.698 / 0.589 / 0.421 | 0.706 / 0.771 | 69/178 | $0.0807 |
| N0rep | 3750 | 0.433 / 0.553 / **0.486** | -0.015 | [-0.028, -0.002] | +0.014 | 0.581 | 0.492 | 0.767 / 0.664 / 0.540 / 0.411 | 0.712 / 0.767 | – | $0.6316 (fresh run) |

## Confirmatory outcome (N1 only) and descriptive arms

Frozen before this run: **N1 is the sole confirmatory arm; N2 and N3 are descriptive.** The criteria are the same as on dev (exact micro F1 +0.02, or paired section-bootstrap 95% lower bound > 0, with a precision drop <= 0.02), against the **frozen CR-009 N0** (historical comparator). Nothing is adopted here; the N1/N0 decision belongs to Research.

| arm | role | gain ok | precision ok | meets the criteria |
|---|---|---|---|---|
| N1 | confirmatory | True | True | True |
| N3 | descriptive | True | True | True |
| N2 | descriptive | False | True | False |

**N1 meets the pre-registered criteria on the held-out split: True.**

Dev vs test for N1: dev Δ F1 +0.016 (95% [+0.005, +0.027]); test Δ F1 +0.009 (95% [+0.005, +0.014]).

### Baseline stability (fresh N0 replication, sensitivity check only)

Frozen CR-009 N0 F1 0.501; fresh N0 replication F1 0.486 (Δ -0.015, paired 95% [-0.028, -0.002]). For reference, the arms relative to the fresh replication:

- N1 vs N0rep: Δ F1 +0.024 (95% [+0.012, +0.037]), precision change +0.011
- N2 vs N0rep: Δ F1 +0.017 (95% [+0.004, +0.030]), precision change +0.009
- N3 vs N0rep: Δ F1 +0.026 (95% [+0.013, +0.039]), precision change +0.018

(The arms are post-passes over the frozen N0 run, so they are paired with it; the comparison with the fresh replication is on the same sections but not the same generated items.)

## N2 trigger (items per 100 words in N0's final output below theta)

| theta | sections resampled | exact P / R / F1 | cost of samples |
|---|---|---|---|
| 3.0 | 14 / 70 | 0.442 / 0.583 / 0.503 | (samples for all sections: $0.0807) |

Frozen trigger rule: highest exact micro F1 on dev, ties to the smaller theta; 'all' is a reference only. Value on this split: **3.0**.

## Rescue funnel (N1 / N3)

| arm | candidates | one-token candidates | add_new | link_existing | reject | proposed items | verified | deduplicated | pruned | kept | incomplete decisions | schema errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N1 | 1734 | 1324 | 172 | 154 | 1408 | 322 | 273 | 33 | 9 | 231 | 4 | 0 |
| N3 | 410 | 0 | 96 | 52 | 262 | 148 | 128 | 6 | 6 | 116 | 0 | 0 |

## Candidate coverage of N0's residual gold (1262 exact-unmatched gold terms)

- N1: residual gold in the candidate list 193/1262; recovered by the rescue (kept, exact name) 77; candidate rejected by the model 74.
- N3: residual gold in the candidate list 120/1262; recovered by the rescue (kept, exact name) 59; candidate rejected by the model 44.

Partial-span errors (false positives containing / inside a gold term), N0: {'over-general (inside a gold term)': 279, 'over-specific (contains a gold term)': 151}

- N1: {'over-general (inside a gold term)': 336, 'over-specific (contains a gold term)': 163}
- N3: {'over-general (inside a gold term)': 288, 'over-specific (contains a gold term)': 161}
- N2: {'over-general (inside a gold term)': 290, 'over-specific (contains a gold term)': 168}
- N0rep: {'over-general (inside a gold term)': 321, 'over-specific (contains a gold term)': 141}
