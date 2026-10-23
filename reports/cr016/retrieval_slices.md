# CR-016 STOP 2 — retrieval slices (raw support beside every metric)

1,140 queries from 17 exposed query sections; slices are multi-label and defined in `src/cumap/cr016/benchmark.py` (exact surface in earlier text; alias = a known alias occurs earlier but the surface does not; acronym; one-token; different boundary = a sub/super phrase occurs earlier but the surface does not; short gap ≤ 2 and long gap ≥ 8 source units to the nearest relevant paragraph; low-lexical-overlap = the surface occurs in none of the relevant paragraphs; same-surface-different-sense = one surface annotated under more than one canonical name; evidence-size buckets). CIs are paired bootstraps over query sections (10,000 resamples); slices with fewer than 5 queries are not bootstrapped.

| slice | support (queries / query sections) | M1 R@5 | M2 R@5 | ΔR@5 [95% CI] | M1 MRR | M2 MRR | M1 P@5 | M2 P@5 |
|---|---|---|---|---|---|---|---|---|
| exact-surface recurrence | 1035 / 17 | 0.652 | 0.668 | +0.015 [-0.007, +0.043] | 0.507 | 0.539 | 0.306 | 0.332 |
| alias recurrence | 58 / 15 | 0.500 | 0.569 | +0.069 [-0.060, +0.188] | 0.397 | 0.466 | 0.176 | 0.210 |
| acronym recurrence | 34 / 15 | 0.588 | 0.794 | +0.206 [-0.028, +0.412] | 0.458 | 0.663 | 0.182 | 0.341 |
| one-token recurrence | 632 / 17 | 0.684 | 0.698 | +0.014 [-0.018, +0.053] | 0.541 | 0.561 | 0.350 | 0.367 |
| different-boundary recurrence | 20 / 9 | 0.450 | 0.500 | +0.050 [-0.167, +0.294] | 0.415 | 0.410 | 0.200 | 0.180 |
| short-gap (≤ 2 units) | 390 / 16 | 0.790 | 0.795 | +0.005 [-0.034, +0.040] | 0.615 | 0.655 | 0.407 | 0.433 |
| long-gap (≥ 8 units) | 381 / 17 | 0.459 | 0.517 | +0.058 [+0.008, +0.114] | 0.344 | 0.407 | 0.180 | 0.201 |
| low-lexical-overlap / associative | 109 / 17 | 0.440 | 0.569 | +0.128 [+0.058, +0.205] | 0.349 | 0.434 | 0.163 | 0.200 |
| same-surface-different-sense (proxy) | 116 / 16 | 0.560 | 0.578 | +0.017 [-0.081, +0.097] | 0.381 | 0.390 | 0.214 | 0.222 |
| ≤ 5 relevant paragraphs | 499 / 17 | 0.443 | 0.513 | +0.070 [+0.032, +0.112] | 0.324 | 0.414 | 0.123 | 0.158 |
| 6–30 relevant paragraphs | 349 / 17 | 0.748 | 0.734 | -0.014 [-0.054, +0.028] | 0.588 | 0.597 | 0.367 | 0.409 |
| > 30 relevant paragraphs | 292 / 17 | 0.818 | 0.818 | +0.000 [-0.026, +0.032] | 0.664 | 0.649 | 0.494 | 0.492 |

Reading guide: the pre-registered difficult slices were alias, acronym, different-boundary, associative and same-surface-different-sense. Only the associative slice clears +0.10 with a CI above 0. Alias (58), acronym (34) and different-boundary (20) supports are too small for a conclusion; the acronym gain (+0.206) is the largest point estimate but its CI includes 0. The overall Recall@5 and MRR gains are concentrated in rare-evidence and long-gap queries.
