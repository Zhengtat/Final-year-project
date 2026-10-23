# CR-014 STOP 4 — fresh held-out result (frozen U0 vs frozen V3, run once)

Written for: Research. Eight sealed P&D sections (4.2, 5.3, 6.1, 6.4, 7.2, 8.3, 8.4, 8.5; 40,058 words), manifest `cr014-manifest-2` (sha `a61f559e…`), run once after the freeze (`FREEZE_V3.json`, tag `cr014-v3-frozen`, commit `5ad4e10`). **Gold = model-generated annotation (LLM, owner-accepted provisionally; not human-annotated; `gold_manifest_heldout.json`, sha256 `2050319b…`, 8,344 rows: 1,065 concepts, 7,279 mentions, 1,812 flagged nested-valid; last written 17:58:42, before any held-out prediction).** Every number is agreement with that annotation. No tuning, retry for quality, manual fix or best-run selection occurred: 8 sections, 0 errors, each section run once. The held-out prediction process had an audit hook blocking gold opens and passed the freeze-hash check.

## Primary metric (pre-specified): mention-level span-exact, rule-17 longest-match placement
| arm | predicted | P | R | F1 | one-token R (5,275 gold) | one-token P |
|---|---|---|---|---|---|---|
| U0 frozen production | 4,933 | 0.749 | 0.508 | 0.605 | 0.489 | 0.727 |
| V3 frozen | 6,630 | 0.675 | 0.615 | **0.643** | 0.558 | 0.663 |
| Δ | | **−0.074** | +0.107 | +0.038 | +0.068 | −0.064 |

Confidence intervals for ΔF1: section-clustered paired bootstrap (8 sections, 10,000 resamples) **+0.038 [+0.010, +0.079]**; sentence-clustered (1,773 sentences) +0.038 [+0.026, +0.050]. Per-section F1 (U0 → V3): 4.2 0.558 → 0.644; 5.3 0.604 → 0.654; 6.1 0.625 → 0.705; 6.4 0.620 → 0.624; 7.2 0.623 → 0.606; 8.3 0.571 → 0.682; 8.4 0.539 → 0.708; 8.5 0.622 → 0.624. V3 is higher in 7 of 8 sections (two by ≤0.003); lower in 7.2.

## Adoption gates (CR §23)
| gate | requirement | result | status |
|---|---|---|---|
| exact micro F1 | dev-selected rule: ΔF1 ≥ +0.02 or CI lower bound > 0 | +0.038; section CI lower bound +0.010 | **pass** |
| exact recall | ≥ baseline + 0.05 | +0.107 | **pass** |
| precision delta | ≥ −0.02 | **−0.074** | **FAIL** |
| one-token recall delta | ≥ −0.02 | +0.068 | pass |
| gold leakage | 0 | 0 (hook + isolation tests; pilot-gold never in prediction path) | pass |
| evidence/provenance completeness for accepted predictions | 1.00 | 1.00 (2,266 accepted surfaces: each has source candidate ids and occurs verbatim in the section text; trace events per candidate) | pass |
| identity-guard violations caused by the concept stage | 0 | **NOT_EVALUATED** (needs the STOP-5 downstream run) | open |
| test-time manual fixes | 0 | 0 | pass |

**Gate status: not met — the precision floor fails (−0.074 against −0.02), on the pre-specified metric, with gold measured as frozen.** Per the CR, the result is frozen and returned to Research; nothing is retuned and the held-out set is not re-run.

## Other views of the same outputs (reported as required; not the gate)
| view | U0 P / R / F1 | V3 P / R / F1 |
|---|---|---|
| distinct surfaces per section (concept level) | 0.715 / 0.472 / 0.569 | 0.570 / 0.727 / 0.639 |
| nested spans all counted (1,812 gold are nested-valid) | 0.750 / 0.615 / 0.676 | 0.668 / 0.880 / 0.760 |

At concept level V3's precision falls 0.145 (recall +0.255). Under the pilot, the distinct-surface precision drop was 0.124, so the held-out repeats the pattern with a larger mention-level precision loss (−0.074 vs −0.014).

## Errors (V3 vs U0)
- **False positives:** V3 2,155 vs U0 1,237. No overlap with any gold span: 1,524 vs 878. Over-specific (contains a gold span): **497 vs 189** (boundary over-extension is now a clear weakness). Over-general (inside a gold span): 132 vs 170.
- **Missed gold, V3 (2,804):** U2 had the exact surface for 97.9% of gold mentions; no overlapping candidate 29; overlap only 115; verifier rejected a proposed surface 471; lost at boundary repair 260 (up from 24 on the pilot); accepted surface whose mention was not placed 1,929 (rule-17 longest-match suppresses shorter nested mentions; nested view above).
- Gold is dense (≈18.2 mentions per 100 words; 24.9% nested-valid); the production concept definition is stricter, which lowers U0 recall.

## Cost and runtime
Total ≈ **$1.64** (U0 production concept stage with canonicalisation ≈ $1.19; V3 ≈ $0.34 bulk tier; 421 V3 calls), against the $10 held-out target and the $30 cap; V3 wall time ≈ 77 min sequential, U0 ≈ 1.5 h. Cumulative CR-014 spend ≈ $3.1.

## Caveats
Single run per arm (nondeterminism unmeasured); gold is model-generated, single annotation, same broad model family as part of the pipeline (shared biases possible, unmeasured); eight sections of one textbook; the placement rule (pre-specified, unchanged) undercounts nested concepts for both arms.

## RESEARCH DECISION REQUIRED
1. The adoption table has one failed gate (precision −0.074 vs −0.02) with the other measurable gates passing and F1/recall/one-token clearly better. The CR says an ambiguous result is frozen and returned: is the outcome `NOT_ADOPTED` (precision gate failed), or a recorded `CONDITIONAL / needs STOP 5` for downstream compatibility? I have not decided this.
2. Whether STOP 5 (downstream compatibility, false-edge growth, pair-budget pressure, identity-guard violations) should run on the baseline and V3 concepts despite the failed gate, to inform a future CR rather than adoption.
3. Whether any follow-up (verifier-rejection losses: 471; boundary losses: 260; over-specific false positives: 497) belongs in a new CR; nothing is changed in CR-014 after this freeze.
