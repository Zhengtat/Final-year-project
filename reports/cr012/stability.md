# CR-012 stability (3 independent E0 repeats, private LLM cache per repeat, all repeats reported, no best-run selection)

Frozen subset (length rule, outcome-blind): P&D 4.5, 4.4; SciNLP P17-1058, 2021.acl-long.353.

| benchmark | unit | F1 repeat 1 / 2 / 3 | mean | sd | node-set Jaccard | edge-set Jaccard | canonicalisation disagreement | relation disagreement |
|---|---|---|---|---|---|---|---|---|
| P&D | 4.5 | 0.060 / 0.062 / 0.057 | 0.059 | 0.002 | 0.614 | 0.252 | 0.000 (NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR) | 0.000 |
| P&D | 4.4 | 0.024 / 0.022 / 0.072 | 0.039 | 0.023 | 0.620 | 0.257 | 0.000 (NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR) | 0.051 |
| SciNLP | P17-1058.grobid | 0.000 / 0.000 / 0.000 | 0.000 | 0.000 | 0.482 | 0.193 | 0.000 (NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR) | 0.000 |
| SciNLP | 2021.acl-long.353 | 0.035 / 0.047 / 0.023 | 0.035 | 0.010 | 0.683 | 0.411 | 0.000 (NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR) | 0.000 |

- Stability is generally modest, with P&D 4.4 the widest spread (F1 0.022-0.072). Node sets agree only about 0.5-0.7 and edge sets about 0.2-0.4 between repeats, so individual runs differ substantially in what they extract even where F1 is similar.
- The frozen canonicalisation disagreement value is kept for reproducibility but is **NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR**: its denominator is essentially all span pairs common to two runs, so it is insensitive to the small subset of pairs where an identity decision could differ. 0.000 must not be read as evidence that canonicalisation is deterministic. The primary stability metric was not redefined after the test; a corrected metric is proposed for future work (CR-013) only.
- Figure: `figures/stability.svg`.
