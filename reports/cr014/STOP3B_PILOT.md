# CR-014 STOP 3B — P&D pilot, span-exact (frozen U0 vs current V3)

Written for: Research. Development material only (pilot sections 4.1 and 9.2, ≈10.5k words). Gold = owner-supplied `data/gold/pd_concept_pilot_blind.csv` (1,771 mentions, 374 concepts, 172 flagged `nested_valid`; ≈16.9 mentions per 100 words, so a very inclusive annotation). Metric = **mention-level span-exact** (character offsets); never pooled with the IIR normalised-name metric. No code, prompt or threshold was changed after seeing these results; V3 is exactly the STOP-3 configuration (`cr014-stageB-1`, verifier prompt v2, boundary prompt v1, bulk tier).

## Setup (how each arm produced spans)
- **U0** = production concept stage on a one-section slice (tau 0, strict G-links), as CR-012 ran it (`cr014_pilot_{4_1,9_2}_U0`). Spans = longest-match, non-overlapping placement of the kept concepts' names + aliases + mention surfaces in the section text (rule 17).
- **V3** = U2 (U1 ∪ the raw iteration-0 output of the U0 run) → exact de-duplication → overlap families → boundary repair → verifier with one-token evidence. Spans = the same placement of the accepted surfaces.
- The domain string in the prompts was "computer networking"; no existing nodes were shown (fresh slice, as U0).

## Main result (rule-17 placement, comparable to production)
| arm | predicted mentions | P | R | F1 | one-token R (1,163 gold) | one-token P |
|---|---|---|---|---|---|---|
| U0 | 1,149 | 0.826 | 0.536 | 0.650 | 0.525 | 0.793 |
| V3 | 1,439 | 0.812 | 0.660 | **0.728** | 0.615 | 0.794 |
| Δ | | −0.014 | +0.124 | **+0.078** | +0.090 | +0.001 |

By section: 4.1 U0 0.826/0.571/0.675 → V3 0.859/0.645/0.737; 9.2 U0 0.826/0.499/0.623 → V3 0.772/0.675/0.720. Direction is the same in both sections. Sentence-clustered paired bootstrap of ΔF1 (424 sentences): +0.079, 95% [+0.052, +0.105]. This resamples sentences from only two sections, so it understates section-level uncertainty; treat it as descriptive.

Checks mirroring CR §22 (descriptive, pilot is not the selection set): ΔF1 ≥ +0.02 yes; precision drop ≤ 0.02 yes (−0.014); recall gain ≥ +0.05 yes; one-token recall regression ≤ 0.02 yes (gain). Single run per arm; verifier nondeterminism not measured.

## Variants of the same outputs
| view | U0 P / R / F1 | V3 P / R / F1 |
|---|---|---|
| nested spans all counted (every occurrence of every accepted surface; 172 gold are nested-valid) | 0.758 / 0.593 / 0.666 | 0.684 / 0.772 / 0.725 |
| distinct surfaces (concept-level, per section) | 0.868 / 0.485 / 0.622 | 0.744 / 0.723 / 0.733 |

At concept level V3's precision falls 0.124 while recall rises 0.238; at mention level (frequency-weighted) precision is nearly unchanged. Both views should be quoted together.

## Boundary and error taxonomy
- **Span-level proposal recall of U2:** 0.970 of gold mentions have their exact surface among the candidates.
- **Unmatched V3 predictions (270):** no overlap with gold 130; over-specific (contains a gold span) 56; over-general (inside a gold span) 84. U0 (200): 93 / 18 / 89. V3 produces more over-specific spans than U0 (56 vs 18) and fewer over-general ones relative to its size.
- **Missed gold, V3 (602):** exact candidate absent and nothing overlaps (P0) 19; only an overlapping, inexact candidate (P1) 32; verifier rejected a proposed exact surface 328; lost at the boundary stage (never reached the verifier) 24; surface accepted but this mention not placed 199 (mostly nested or shorter-span mentions suppressed by longest-match placement; the nested view above recovers them). For U0: 562 missed gold have no overlapping prediction, 260 overlap inexactly.
- So the dominant remaining loss is the verifier (328), not proposal (51) or boundary repair (24).

## Cost and runtime
U0: $0.135 (4.1) + $0.190 (9.2) incl. canonicalisation. V3: $0.038 + $0.047 = $0.085 (46 + 59 calls, 7.6 + 9.0 min). Pilot total ≈ $0.41 (target ≤ $5). Cumulative CR-014 ≈ $1.0.

## Reading and limits
- On P&D, with a dense gold, V3 raises recall and F1 with essentially unchanged mention-level precision — in contrast to IIR dev, where the same system lost precision. That fits the FP-audit finding that IIR dev gold is incomplete, but it is two sections of one textbook and one annotator's inclusive definition; it does not by itself show adoption-level evidence.
- Gold provenance: owner-supplied, not independently double-annotated; agreement `NOT_EVALUABLE`. The annotator/provenance statement (human or LLM-assisted) has not been given to me and is not asserted here; file facts are in `reports/cr014/gold_manifest_pilot.json` (its last write, 14:14:54, precedes every pilot prediction, the first being 14:22; the LLM-generated FP-audit file was last written 6 s later, which the owner should explain when stating provenance). Dense gold favours recall-oriented systems (generic terms such as "network" and "component" are in gold); production's stricter concept definition is part of why U0 recall is low.
- Not done: held-out run, downstream compatibility, stability repeats, strong-tier or two-sample verifier variants. The sealed held-out sections (manifest v2) remain unopened.

## RESEARCH DECISION REQUIRED
1. Interpretation: given IIR dev (precision fail, gold incomplete per the FP audit) and P&D pilot (F1 +0.078, precision held), is V3 a candidate for freezing, or should the verifier-rejection loss (328 of 602 misses) be addressed first (strong-tier probe ≈ $2–7, two-sample agreement ≈ 2× verifier cost) on development data only?
2. Which adoption-rule precision basis applies (gold-measured vs audited) — a gate change, so Research only; unchanged here.
3. A like-for-like U0 false-positive audit on IIR dev (≈30 items, blind) if the IIR precision question is to be settled.
4. Commit of the owner's `data/gold/*` files (untracked) — owner decision.


## Update after Research decision (STOP 3B PASS)
V3 frozen for STOP 4; precision basis for the adoption gate remains gold-measured (mention-level span-exact); the IIR FP audit is diagnostic only and its labels were LLM-generated per Research. Distinct-surface result (U0 P 0.868 / R 0.485; V3 P 0.744 / R 0.723) is reported prominently and is not the gate.
