# CR-015 STOP 2 — boundary + placement result (Stage A, development only)

Written for: Research. **No arm is eligible under the CR §22 development gates** (all four fail precision, distinct-surface precision and over-long reduction), but Stage A shows large, separable effects. Nothing is frozen. Development data = the 10 exposed CR-014 P&D sections (pilot 4.1, 9.2 + former held-out 4.2, 5.3, 6.1, 6.4, 7.2, 8.3, 8.4, 8.5; 50,523 words; 9,050 gold mentions). **Gold = model-generated annotation (CR-014; not human-validated); every number is agreement with it.** The fresh CR-015 pilot (4.3, 6.2) and held-out were not used. Scoring = the frozen scorer (`FREEZE_SCORER.json`, tag `cr015-scorer-frozen`); candidate universe = frozen CR-014 U2 (8,327 families, 10,761 candidates, 3,699 multi-member families); the verifier is the frozen CR-014 V3 verifier (prompt v2) in every arm.

## Arms
- **U0** production concept stage. **A0** exact frozen V3 (saved CR-014 outputs) with longest-match placement: the reference.
- **A1** A0's accepted surfaces + nested-aware placement from V3's own boundary decisions (a family with ≥2 kept accepted surfaces places the inner spans too); no model call, $0.
- **A2** new family-level boundary selector (`prompts/cr015_boundary_family/v1`; labels KEEP_PRIMARY / KEEP_NESTED / EXPAND_TO / SHRINK_TO / REJECT_*; one decision per candidate, zero/one/several spans per family) → frozen V3 verifier on the selected spans → family-grounded placement (a surface is placed only inside family occurrences where the selector kept it). Bulk tier gpt-6-luna.
- **A3** = A2 + retrieved hard-negative contrastive demonstrations (`v2` prompt). Bank built from development gold only (7,507 contrast groups, 14,859 negatives, sha256 `42e71b04…`), retrieved leave-one-section-out (a query section never sees its own gold); retrieved ids are saved with each batch.

## Mention-level and boundary results
| arm | predicted | P | R | F1 | ΔF1 vs U0 [95% CI] | ΔF1 vs A0 [95% CI] | macro-section F1 |
|---|---|---|---|---|---|---|---|
| U0 | 6,082 | 0.764 | 0.513 | **0.614** | – | – | 0.606 |
| A0 | 8,069 | 0.699 | 0.624 | **0.659** | +0.045 [+0.018, +0.081] | – | 0.670 |
| A1 | 8,612 | 0.697 | 0.664 | **0.680** | +0.066 [+0.040, +0.102] | +0.021 [+0.013, +0.029] | 0.693 |
| A2 | 10,675 | 0.665 | 0.785 | **0.720** | +0.106 [+0.062, +0.155] | +0.061 [+0.024, +0.100] | 0.736 |
| A3 | 9,434 | 0.680 | 0.709 | **0.694** | +0.080 [+0.041, +0.129] | +0.035 [+0.007, +0.066] | 0.711 |

| arm | one-token R / P | nested-gold recall | non-nested recall | predicted nested n / precision | over-long FP | under-long FP | F4 invalid nested | distinct-surface P / R / F1 | distinct accepted surfaces | candidate→final compression |
|---|---|---|---|---|---|---|---|---|---|---|
| U0 | 0.496 / 0.739 | 0.224 | 0.595 | 0 / NA | 207 | 259 | NA | 0.747 / 0.476 / 0.581 | 1,429 | 7.5:1 |
| A0 | 0.568 / 0.685 | 0.077 | 0.777 | 0 / NA | 553 | 216 | NA | 0.604 / 0.726 / 0.659 | 2,699 | 4.0:1 |
| A1 | 0.606 / 0.683 | 0.201 | 0.794 | 1,039 / 0.688 | 588 | 337 | 122 | 0.600 / 0.737 / 0.661 | 2,761 | 3.9:1 |
| A2 | 0.766 / 0.652 | 0.703 | 0.808 | 5,090 / 0.632 | 695 | 1129 | 913 | 0.560 / 0.789 / 0.655 | 3,160 | 3.4:1 |
| A3 | 0.668 / 0.675 | 0.472 | 0.775 | 3,551 / 0.624 | 688 | 796 | 607 | 0.571 / 0.779 / 0.659 | 3,063 | 3.5:1 |

## Development gates (CR §22)
| gate (CR §22) | A0 | A1 | A2 | A3 |
|---|---|---|---|---|
| 1_f1_gain_ge_0.02_or_ci_gt_0_vs_U0 | pass | pass | pass | pass |
| 2_precision_ge_U0_minus_0.02 | FAIL | FAIL | FAIL | FAIL |
| 3_recall_ge_U0_plus_0.05 | pass | pass | pass | pass |
| 4_one_token_recall_ge_U0_minus_0.02 | pass | pass | pass | pass |
| 5_distinct_precision_ge_U0_minus_0.05 | FAIL | FAIL | FAIL | FAIL |
| 6_distinct_recall_ge_U0_plus_0.05_or_within_0.03_of_V3 | pass | pass | pass | pass |
| 7_overlong_fp_reduced_25pct_vs_V3 | FAIL | FAIL | FAIL | FAIL |
| 8_9_no_identity_provenance_violation_or_leakage | pass | pass | pass | pass |
| **eligible** | False | False | False | False |
(A0 is the V3 reference, so its over-long gate compares it with itself.)

## What happened
- **Placement alone (A1, $0):** ΔF1 +0.021 over A0 (95% [+0.013, +0.029]); recall +0.040; nested-gold recall 0.077 → 0.201; precision unchanged (−0.002).
- **Family selector with explicit nested validity (A2):** the largest gain — F1 0.720, recall 0.785, nested-gold recall 0.703, one-token recall 0.766 — but precision falls to 0.665 (U0 0.764) because the nested spans it places are often not gold nested mentions (913 invalid-nested and 1,129 under-long false positives).
- **Contrastive hard negatives (A3):** invalid-nested false positives fall 913 → 607 and under-long 1,129 → 796, precision 0.665 → 0.680, but recall falls 0.785 → 0.709, so F1 0.694 < A2's 0.720. It does not reduce over-long false positives (695 → 688).
- **Over-long false positives are not reduced by any arm** (A0 553, A1 588, A2 695, A3 688; U0 207), so gate 7 fails everywhere. Of the selector's KEEP_PRIMARY labels, 692 (A3) fall on spans that contain a gold span: either a real boundary error or the gold's inner-term convention (not separable without human review of the gold).
- **Distinct-surface precision is not recovered** (0.560–0.604 vs U0 0.747); distinct-surface recall is held (0.726–0.789). Candidate→final compression is 3.4–4.0:1 vs U0 7.5:1: Stage A is a boundary stage and adds no precision filter, so this is the target of Stage B.

## Stage-conditional metrics
- **Boundary-selector exact recovery** (gold mentions whose exact span is a candidate in a family, 8,429): A0 0.703, **A2 0.910**, A3 0.825. **Nested recovery** (1,958 nested-valid gold): A0 0.187, **A2 0.773**, A3 0.520.
- **Mention-placement loss after acceptance (M0):** A0 490, A1 128, A2 0, A3 1.

## Where the remaining gold misses come from (earliest cause)
| earliest cause of a missed gold mention | A0 | A1 | A2 | A3 |
|---|---|---|---|---|
| B0 only a wrong-boundary candidate | 184 | 184 | 320 | 317 |
| B1 selector chose an over-long boundary | 540 | 540 | 213 | 449 |
| B2 selector chose an under-long boundary | 45 | 45 | 46 | 25 |
| B3 valid nested concept suppressed (an enclosing span was kept) | 1506 | 1506 | 437 | 932 |
| BS selector kept no overlapping span (rejected/unanswered) | 32 | 32 | 57 | 66 |
| M0 accepted, not placed at this mention | 490 | 128 | 0 | 1 |
| P0 not proposed | 123 | 123 | 292 | 292 |
| V0 valid bounded concept rejected by verifier | 486 | 486 | 584 | 554 |
(B3 = nested concept dropped because an enclosing span was kept; B1/B2 = selector chose a longer/shorter boundary; V0 = verifier rejected a correctly bounded concept; P0/B0 = not proposed / only a wrong-boundary candidate.)

## False positives by category (earliest cause; F0/F1/F7 are not separable without human review)
| false-positive mention category | A0 | A1 | A2 | A3 |
|---|---|---|---|---|
| F0/F1/F7 no overlap with gold (generic, descriptive or unsupported; unreviewed) | 1656 | 1681 | 1750 | 1536 |
| F2 over-long technical span | 553 | 588 | 695 | 688 |
| F3 under-long / partial span | 216 | 215 | 216 | 189 |
| F4 invalid nested substring | 0 | 122 | 913 | 607 |

## Boundary-family confusion (A2 and A3: selector label × relation of the candidate span to gold at its family occurrence)
A2
| selector label | exact_gold | over_long | under_long | no_gold_overlap |
|---|---|---|---|---|
| KEEP_PRIMARY | 1421 | 617 | 39 | 528 |
| KEEP_NESTED | 1820 | 231 | 1155 | 695 |
| EXPAND_TO | 67 | 141 | 242 | 166 |
| SHRINK_TO | 41 | 425 | 21 | 226 |
| REJECT_DESCRIPTIVE | 91 | 512 | 273 | 1319 |
| REJECT_GENERIC | 118 | 0 | 554 | 1210 |
| REJECT_UNSUPPORTED | 14 | 83 | 117 | 221 |

A3
| selector label | exact_gold | over_long | under_long | no_gold_overlap |
|---|---|---|---|---|
| KEEP_PRIMARY | 1382 | 692 | 35 | 631 |
| KEEP_NESTED | 1356 | 219 | 671 | 488 |
| EXPAND_TO | 522 | 215 | 857 | 592 |
| SHRINK_TO | 83 | 404 | 95 | 258 |
| REJECT_DESCRIPTIVE | 88 | 428 | 220 | 1199 |
| REJECT_GENERIC | 110 | 0 | 386 | 996 |
| REJECT_UNSUPPORTED | 31 | 52 | 137 | 201 |

## Cost, volume, runtime
| arm | calls | cost | wall time |
|---|---|---|---|
| A0 (CR-014 V3 on these sections) | 526 | $0.43 | – |
| A1 | 0 | $0 | seconds |
| A2 | 550 | $0.58 | 2.0 h (sequential) |
| A3 | 550 | $0.58 | 2.4 h |
Stage A total ≈ $1.16 (+ $0.80 for the pilot gold draft), against the $5 soft target. Cumulative CR-015 spend ≈ $2.0. The selector answered every candidate (A2: 1 unanswered, 1 invalid target; A3: 0, 2; no call errors). Cost per correct mention: A2 ≈ $0.00009 (tp from the table). Runtime, not cost, is the constraint.

## Caveats
- Development and selection use the same 10 sections that CR-014 used; gold is model-generated; the inner/outer span convention of that gold affects over-long and nested counts and cannot be separated from model error here.
- Gates 8–9 (identity/provenance, leakage) hold by construction (no canonicalisation or gold access in these arms); trace events for CR-015 stages (`boundary_family`, `mention_placement`) are not emitted yet — NOT DONE; the trace stage extension is pending.
- The fresh pilot (4.3, 6.2; reviewed gold hash in `gold_manifest_pilot.json`, label MODEL_GENERATED_DIAGNOSTIC until the owner states the review was human) is untouched and available for validation at STOP 3.
- Single run per arm; selector nondeterminism not measured.

## RESEARCH DECISION REQUIRED
1. No arm is eligible, as expected before precision recovery. Which boundary/placement base should Stage B build on? My reading of the evidence: **A2** (best F1, recall and nested recovery; its extra false positives are the kind a concepthood verifier is meant to remove) — **A3** if you prefer fewer invalid nested spans at the cost of 0.076 recall; **A1** if you want a model-free, lower-risk base. I have not chosen.
2. Gate 7 (over-long reduction of 25%) is not met by any arm. Is that gate still to apply to the Stage-B candidate, or should over-long be judged against a human-reviewed sample of the gold's span convention first?
3. Whether the unresolved inner-vs-outer convention in the model-generated gold needs a human-reviewed sample before Stage B tunes against it.
