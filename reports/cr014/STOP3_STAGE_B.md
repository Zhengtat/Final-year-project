# CR-014 STOP 3 — Stage B development result (IIR dev; no arm eligible)

Written for: Research (CR-014 decision-maker). Development only: IIR dev, 13 sections, 17,987 words, 485 gold. No sealed P&D data was opened. Metric = **normalised-name exact** match (IIR gold has no character offsets); it is never pooled with the P&D span-exact metric. Frozen proposal input = **U2 = U1 deterministic ∪ raw iteration-0 current-LLM proposals** (5,137 candidates after de-duplication and removal of strings absent from the text).

## Result: no V-arm passes the CR §22 development rule
| arm | predicted | exact P | R | F1 | ΔF1 vs U0 [95% CI] | ΔP | ΔR | one-token R (U0 0.541) | eligible |
|---|---|---|---|---|---|---|---|---|---|
| U0 production final | 582 | 0.433 | 0.520 | 0.472 | – | – | – | 0.541 | reference |
| V0 production rules + pruner on U2 | 4,258 | 0.073 | 0.637 | 0.130 | −0.342 [−0.384, −0.293] | −0.360 | +0.118 | 0.535 | no |
| V1 independent verifier | 1,496 | 0.273 | 0.841 | 0.412 | −0.060 [−0.110, −0.006] | −0.160 | +0.322 | 0.907 | no |
| V2 V1 + overlap-family repair | 1,249 | 0.320 | 0.825 | 0.461 | −0.011 [−0.063, +0.044] | −0.113 | +0.305 | 0.843 | no |
| V3 V2 + one-token evidence | 1,174 | 0.342 | 0.827 | 0.483 | **+0.011** [−0.040, +0.066] | −0.091 | +0.307 | 0.820 | no |
| V4 | not run (see below) | | | | | | | | |

Rule checks (CR §22): F1 gain ≥ +0.02 **or** CI lower bound > 0 — fails for every arm (best +0.011, lo95 −0.040). Precision drop ≤ 0.02 — fails for every arm (−0.09 to −0.36). Recall gain ≥ +0.05 — passes (+0.31 for V1–V3). One-token recall regression ≤ 0.02 — passes (one-token recall rises 0.541 → 0.82–0.91). Leakage/provenance — no failure found (gold is read only by scoring; trace complete, see below).

**Reading:** CR-014's recall hypothesis is supported on this corpus — recall rises by about 0.31 and one-token recall by 0.28–0.37 — but the precision cost is too large for the frozen adoption rule. F1 does not improve reliably. Single run per arm; verifier nondeterminism is not measured.

## Why precision is low, and what is not known
- Unreviewed false positives: V3 773 (of which 268 overlap a gold term, i.e. partial/overlong boundary; 505 no overlap). The IIR gold is annotator-consensus, not proven exhaustive, so some "false positives" may be valid concepts the gold omits. **This is unmeasured.** I prepared a blind 58-item audit sheet (`data/interim/checks/cr014/iir_fp_audit_blind.csv`, arms hidden, order shuffled) for a human to label valid/invalid. I have not labelled it and will not.
- Boundary repair (V2 vs V1): precision +0.047, F1 +0.049, partial/overlong false positives 405 → 291; cost: 32 gold concepts lost at the boundary stage (B0; recall −0.016). 2,877 family members were not named by any repair decision, so repair acts as a filter; its losses are logged per family.
- One-token evidence + priority order (V3 vs V2): precision +0.022, one-token precision 0.251 → 0.262, but one-token recall 0.843 → 0.820 (−0.023): the prompt became stricter on one-word terms. Evidence is not a classifier here, yet it reduced recall on that class.
- A hard one-token gate is **not justified**: any cut-off of the pre-registered ranker removes recall (proposal recall 0.971 → 0.738 at 0.25; the added 0.125 cut-off, added after seeing the table, removes 1.7% of load and no recall). V3 therefore uses no gate. Ranker weights were fixed before any dev outcome was read.

## Conditional metrics (dev)
| | V1 | V2 | V3 |
|---|---|---|---|
| verifier recall given exact proposal hit (463 gold in U2) | 0.881 | 0.864 | 0.866 |
| boundary recovery of overlap-only gold (14) | 0.0 | 0.0 | 0.0 |
| earliest-failure misses P0 / P1 / B0 / V (verifier) / R0 | 8 / 14 / 0 / 55 / 0 | 8 / 14 / 32 / 31 / 0 | 8 / 14 / 32 / 30 / 0 |

(V arm labels differ from the CR taxonomy code V0 = "verifier rejected valid proposal"; R0 = pruner removal is not separately measurable for LLM arms because they use no pruner.) The 14 overlap-only gold concepts (a candidate overlaps but none is exact) are never recovered: no arm builds a span that is not already a U2 candidate. V0 is an adapted arm: the production rule verifier and pruner (tau 0.1, LOCO model) applied to candidates cast as generator items; it does not filter a 5k-candidate union (the pruner passes ~all noun-like terms) and is not a faithful re-run of the production loop.

## Cost, calls, runtime (bulk tier gpt-6-luna)
| arm | calls | cost | wall time |
|---|---|---|---|
| V1 | 213 | $0.155 | 28 min |
| V2 | 238 | $0.176 | 42 min |
| V3 | 238 | $0.092 | 16 min |
| smoke (2 sections) + truncated first attempt | – | ≈ $0.07 | – |
| Stage A samples (STOP 2) | – | $0.104 | – |
Total CR-014 spend ≈ **$0.60** of the $15 dev soft target and $30 cap. Calls are sequential, so runtime dominates: a full P&D held-out section run would take hours at this speed unless batched in parallel. Preflight estimated bulk ≈ $0.33 for the three arms; actual $0.42 (reasoning tokens). A strong-tier run of V3 is estimated at ≈ $2–7 (preflight $2.0 before the reasoning multiplier).

## Traceability
CR-013 vocabulary extended additively (`proposal`, `boundary_repair`; historical stages and the explorer payload unchanged, CR-013 tests pass). Per-arm traces: `data/processed/cr014/stageB/trace_V{1,2,3}.jsonl` (about 10k events each: 5,137 PROPOSAL events with sources, offsets, families; 1,566 BOUNDARY_REPAIR events with family members, decisions and reason codes; verifier events with verdict, reason code, prompt version, tier). In V2/V3 only 3,046 of 5,137 candidates reach a verifier event; the rest end at the boundary stage. No chain-of-thought is stored.

## Items not done / pending
1. **P&D pilot (4.1, 9.2):** blind annotation sheet and delta guide are ready; no gold exists, so no P&D transfer or span-exact boundary result. 👤 HUMAN: annotate and freeze into `data/gold/`.
2. **Manifest:** `configs/cr014_manifest.yaml` (seed `cr014-manifest-v1`, sha256 recorded) froze pilot 4.1, 9.2; sealed held-out 4.2, 4.3, 5.2, 5.3, 6.1, 7.2, 8.3, 9.1; reserve 5.1, 6.2, 6.4, 6.5, 8.1, 8.4, 8.5, 9.4. Heads-up: the draw put two long sections in the held-out set (5.2 12.8k words, 9.1 10.2k); the 8 sections total ≈ 54k words to annotate exhaustively. Re-draw is possible before any prediction; say so.
3. **V4 (few-shot):** not run — no leak-free labelled example bank exists (dev gold is the only labelled set, and retrieval from it would leak into dev scoring).
4. Eligible arm: none, so nothing is frozen.

## RESEARCH DECISION REQUIRED
1. **Accept that no arm is eligible** and choose how to proceed. Options, all dev-only: (a) human FP audit of the 58 items first (cheap; tells whether the gold, not the system, limits precision); (b) strong-tier V3 probe (≈ $2–7) to test whether verifier quality is the limit; (c) a stricter verdict policy (e.g. require agreement of two independent verifier samples) at ~2× verifier cost; (d) stop CR-014 as `NO_PRODUCTION_CHANGE` with the recall finding recorded.
2. Whether the adoption rule's precision floor (−0.02) should be judged against audited rather than gold precision — a change to the research gate, so Research only; I have not changed it.
3. Manifest: keep the draw or re-draw (annotation burden).
4. Who annotates the pilot, and when.
