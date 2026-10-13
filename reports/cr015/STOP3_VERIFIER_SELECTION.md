# CR-015 STOP 3 — Stage B verifier result (development): precision recovery did not occur

Written for: Research. Development only (10 exposed CR-014 sections, 9,050 gold mentions, **model-generated gold**; every number is agreement with that annotation). Design, prompts and bank rule frozen before any call (`docs/cr015/STAGE_B_DESIGN.md`, tag `cr015-stageb-design-frozen`); the A2 selector was reused unchanged (tag `cr015-a2-frozen`), so B arms differ only in the verifier. The owner accepted the **model-filled** boundary audit as diagnostic and waived the human-audit prerequisite. The fresh pilot (4.3, 6.2) and held-out were not opened. B3 was not run (see below).

## Result: both concepthood verifiers lose precision against the A2 base
| arm | predicted | P | R | F1 | ΔF1 vs U0 [95% CI] | ΔF1 vs A2 [95% CI] | one-token R / P | nested-gold R | over-long FP | under-long FP | distinct P / R |
|---|---|---|---|---|---|---|---|---|---|---|---|
| U0 | 6,082 | 0.764 | 0.513 | **0.614** | – | – | 0.496 / 0.739 | 0.224 | 207 | 259 | 0.747 / 0.476 |
| A0 | 8,069 | 0.699 | 0.624 | **0.659** | +0.045 [+0.018, +0.081] | – | 0.568 / 0.685 | 0.077 | 553 | 216 | 0.604 / 0.726 |
| A2 | 10,675 | 0.665 | 0.785 | **0.720** | +0.106 [+0.062, +0.155] | – | 0.766 / 0.652 | 0.703 | 695 | 1129 | 0.560 / 0.789 |
| B1 | 12,818 | 0.587 | 0.831 | **0.688** | +0.074 [+0.027, +0.129] | – | 0.810 / 0.573 | 0.749 | 1023 | 1648 | 0.457 / 0.869 |
| B2 | 12,689 | 0.597 | 0.837 | **0.697** | +0.083 [+0.035, +0.136] | – | 0.817 / 0.591 | 0.757 | 1070 | 1614 | 0.463 / 0.877 |
(B0 = A2 as frozen: selector + the CR-014 V3 verifier.)

- **B1** (separate concepthood verifier): precision 0.665 → 0.587, recall 0.785 → 0.831, F1 0.720 → 0.688 (vs B0 not significantly better; both worse than A2 on F1).
- **B2** (+ retrieved contrastive demonstrations): precision 0.597, recall 0.837, F1 0.697 — +0.010 precision over B1, still −0.068 below B0.
- **Distinct-surface precision falls to 0.46** (B0 0.56, U0 0.75) while distinct-surface recall rises to 0.87–0.88: the verifiers admit many more distinct surfaces.
- **Over-long and invalid-nested false positives increase** (over-long 695 → 1,023 / 1,070; invalid nested 913 → 1,430 / 1,408), so the retained over-long gate is further from being met (target ≤ 415).

## Gates (CR §22)
| gate (CR §22) | B1 | B2 |
|---|---|---|
| 1_f1_gain_ge_0.02_or_ci_gt_0_vs_U0 | pass | pass |
| 2_precision_ge_U0_minus_0.02 | FAIL | FAIL |
| 3_recall_ge_U0_plus_0.05 | pass | pass |
| 4_one_token_recall_ge_U0_minus_0.02 | pass | pass |
| 5_distinct_precision_ge_U0_minus_0.05 | FAIL | FAIL |
| 6_distinct_recall_ge_U0_plus_0.05_or_within_0.03_of_V3 | pass | pass |
| 7_overlong_fp_reduced_25pct_vs_V3 | FAIL | FAIL |
| 8_9_no_identity_provenance_violation_or_leakage | pass | pass |
Both arms fail precision, distinct-surface precision and over-long reduction. **No arm is eligible. Nothing is frozen.**

## Why: what changed relative to B0
- The CR-014 verifier carried a boundary verdict (`REJECT_PARTIAL_OR_WRONG_BOUNDARY`), which rejected **835** selected spans in B0. The frozen design removes boundary from the verifier (the boundary is assumed to be settled upstream). B1/B2 newly accept 445 / 450 of those surfaces, plus 355 / 384 that B0 called not-a-concept and 370 / 325 it called generic.
- The mentions B1 adds over B0 number 2,264 and only **19.4%** are correct (B2: 2,179 added, **22.3%**), while the mentions it removes number 121 and 13% of them were correct. So B1/B2 add recall (+0.046 / +0.052) at a very low marginal precision.
- The retrieved demonstrations (bank: 7,967 positives, 2,472 negatives; sha256 `5b6fc94a…`) helped only slightly (+0.010 precision, +0.009 F1).
- Interpretation: the A2 selector's boundaries are not reliable enough to hand to a verifier that is told not to look at boundaries. The old verifier's boundary verdict was acting as a second boundary check. Separating boundary from concepthood, as the CR specifies, removes that check without replacing it.

## Valid-concept rejection and invalid acceptance (against the model-generated gold)
- Correctly bounded valid concepts the verifier rejected (earliest cause V0): B0 **584**, B1 **160**, B2 **109**.
- Invalid acceptances (unmatched placed mentions, all categories): B0 3,574, B1 5,293, B2 5,113.
- Verdict mix (distinct selected spans): B0 accepted 3,160 of 7,320; B1 4,273; B2 4,256.

## Remaining gold misses and false positives
| earliest cause of a missed gold mention | A2 (=B0) | B1 | B2 |
|---|---|---|---|
| B0 only a wrong-boundary candidate | 320 | 320 | 320 |
| B1 selector chose an over-long boundary | 213 | 213 | 213 |
| B2 selector chose an under-long boundary | 46 | 46 | 46 |
| B3 valid nested concept suppressed (an enclosing span was kept) | 437 | 437 | 437 |
| BS selector kept no overlapping span (rejected/unanswered) | 57 | 57 | 57 |
| P0 not proposed | 292 | 292 | 292 |
| V0 valid bounded concept rejected by verifier | 584 | 160 | 109 |

| false-positive mention category | A2 (=B0) | B1 | B2 |
|---|---|---|---|
| F0/F1/F7 no overlap with gold (generic, descriptive or unsupported; unreviewed) | 1750 | 2622 | 2429 |
| F2 over-long technical span | 695 | 1023 | 1070 |
| F3 under-long / partial span | 216 | 218 | 206 |
| F4 invalid nested substring | 913 | 1430 | 1408 |

## Cost, calls, runtime (bulk tier)
B1: 299 calls, $0.244, 56 min. B2: 299 calls, $0.258, 55 min. Stage B ≈ $0.50 against the $15 soft target. Cumulative CR-015 spend ≈ $2.5 (pilot gold draft $0.80, Stage A $1.16, Stage B $0.50) against the $25 warning and $35 cap.

## B3 (not run)
CR §16 permits B3 only if B0–B2 miss the gates **and** a precision-recovery hypothesis remains. Both verifiers accept the same large share of the selected spans (B1 and B2 agree on most verdicts), so adjudicating their disagreements would not recover the 2,000+ low-precision added mentions; I judge the hypothesis not supported by this evidence and did not spend on it. Research may still order it.

## Caveats
- Model-generated gold (not human); the audit suggests the dev gold omits a third of valid unmarked spans, so absolute precision values are lower bounds. Relative comparisons between arms share that bias.
- Single run per arm; verifier nondeterminism not measured. B2's bank excludes gold spans the A2 verifier rejected and negatives that overlap gold, so it encodes the benchmark's and A2's agreement.
- CR-015 trace events were implemented for A2 (full lineage); they were not built for B1/B2 outputs.

## RESEARCH DECISION REQUIRED
1. Stage B as frozen did not recover precision (best precision 0.665 at A2; U0 0.764). Which direction? (a) a separate, explicit **boundary-validation** step on the selected spans (a new design: boundary and concepthood answered by two fields or two calls, final acceptance = both) — this follows the evidence that the old verdict was doing real work; (b) accept the A2-level trade-off (F1 +0.106 over U0, precision −0.10) and move to downstream compatibility on A2 with its precision cost stated; (c) stop CR-015 as NOT_ADOPTED with the findings; (d) run B3.
2. The over-long gate remains unmet by every arm (target ≤ 415; best 553 at A0, B arms 1,023–1,070). Keep it, or re-baseline it against a human-reviewed convention?
3. Whether the held-out/downstream stages should be attempted before any arm passes the development gates (I recommend not).
