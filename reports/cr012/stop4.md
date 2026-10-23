# CR-012 STOP 4 report: held-out execution under `stop3-frozen`

Written for: Research (decision before final interpretation / STOP 5). Nothing was tuned; no architecture change; each held-out unit was run once.

## Execution
- P&D held-out: 7 sections (4.4, 4.5, 5.4, 6.3, 7.1, 8.2, 9.3; 30,053 words), levels E0-E4. Gold: `data/gold/pd_e2e_test_blind.csv`, sha256 in `heldout_gold_provenance.json` (426 headline edges, single human annotator + LLM prefill reviewed by the owner; **no second annotator: single-annotator limitation, so no IAA is reported**).
- SciNLP test: 3 documents (2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid), levels E0, E1, E3-M, E4-M (E2 NOT_SUPPORTED, identity metrics NOT_SUPPORTED). Test gold relations: 164 / 130 / **1** (P17-1058 has one gold relation, so its document F1 is near-uninformative).
- 47 main runs + 12 stability runs (3 independent repeats, private cache per repeat, on the frozen subset: P&D 4.5, 4.4; SciNLP P17-1058, 2021.acl-long.353). No best-run selection.
- One execution defect, `invalid_runs.md`: the oracle leakage assertion false-positived on book-sentence words (section 4.4 E3), stopped at 13 s with $0 spent; fixed (structured fields only), test added, run resumed. No result was rerun or discarded.
- Execution plumbing added after the STOP-3 freeze (oracle tag, SciNLP surface-level oracle runner, orchestrator, scorer, test-split gate, private-cache env) is hashed in `frozen_hashes.json` (`stop4_execution_addendum`). No scorer semantics, oracle definition, prompt, model, threshold, pair budget or registry changed.
- Cost: STOP-4 model spend $23.07; cumulative CR-012 spend $25.93 (forecast $28-34; soft warning $40 never reached; hard cap $50 untouched).
- SciNLP E3-M/E4-M are defined on SURFACE-level pseudo-nodes (one node per distinct normalised surface, canonicalisation replaced); E1 keeps normal canonicalisation. E4-M cost is $0 because it reuses the E3-M classifications of the same gold pairs from the cache (identical calls), as in P&D.
- Interval note: the P&D section bootstrap (7 sections, seed 20261011, 10,000 resamples) is reported as requested; the frozen bootstrap code labels any unit count below 10 `NOT_EVALUABLE_SMALL_N`, so that label appears beside it. Read it as descriptive, not inferential.
- Canonicalisation disagreement in the stability table is computed over all span pairs common to two runs (about 6,000 per section, of which only tens are same-node), so it is strongly diluted and prints 0.000; it is reported as frozen, not as evidence that canonicalisation is deterministic.

## Headline observations (hypotheses only; no redesign proposed)
- P&D E0 strict end-to-end F1 0.053 (P 0.092 / R 0.038); oracle ladder E1 0.113, E2 0.129, E3 0.398, E4 0.470. Pair recall within reachable gold: E0 53/326; the biggest recoverable gaps are pair delivery (E2 to E3, +0.27) and, at E0, P0 (206 of 416 misses) and N0/N1 extraction (101).
- Relation accuracy given correct endpoints (P&D E3): 152 of 216 gold pairs with a predicted edge have the right relation (150 right direction).
- SciNLP relation strict F1: E0 0.050, E1 0.255, E3-M 0.463, E4-M 0.473; E0 misses are dominated by endpoint extraction (N0 255 of 284), the expected over/under-extraction transfer outcome.
- Provenance (E0, P&D): unsupported node rate 0.029, unsupported edge rate 0.000.
- Not applicable: S0/S1 and any pre/post sleep delta (CR-011 adopted no transformation).

## Results (`heldout`)

P&D-E2E and SciNLP are reported separately; there is no pooled number.

## P&D-E2E (canonical graph, section bootstrap)

| level | sections | strict E2E P / R / F1 (pooled) | 95% section-bootstrap F1 | pair recall | canon node F1 | typed mention F1 | pairwise id F1 | B-cubed F1 | $ |
|---|---|---|---|---|---|---|---|---|---|
| E0 | 7 | 0.092 / 0.038 / 0.053 | [0.030, 0.076] (NOT_EVALUABLE_SMALL_N) | 53/326 | 0.643 | 0.226 | 0.015 | 0.322 | 3.7736 |
| E1 | 7 | 0.212 / 0.077 / 0.113 | [0.080, 0.152] (NOT_EVALUABLE_SMALL_N) | 92/419 | 0.855 | 0.985 | 0.878 | 0.897 | 3.7082 |
| E2 | 7 | 0.220 / 0.092 / 0.129 | [0.105, 0.153] (NOT_EVALUABLE_SMALL_N) | 109/425 | 0.996 | 0.979 | 0.975 | 0.978 | 2.2822 |
| E3 | 7 | 0.457 / 0.352 / 0.398 | [0.324, 0.452] (NOT_EVALUABLE_SMALL_N) | 425/425 | 0.996 | 0.979 | 0.975 | 0.978 | 2.2166 |
| E4 | 7 | 0.708 / 0.352 / 0.470 | [0.396, 0.522] (NOT_EVALUABLE_SMALL_N) | 425/425 | 0.996 | 0.979 | 0.975 | 0.978 | 0.0 |

Earliest-failure attribution (pooled over sections; S0/S1 not applicable):

| level | misses | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | recovered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 416 | 67 | 34 | 79 | 1 | 206 | 16 | 6 | 1 | 6 | 0 | 16 |
| E1 | 397 | 5 | 1 | 206 | 23 | 143 | 12 | 7 | 0 | 0 | 0 | 35 |
| E2 | 391 | 0 | 1 | 0 | 0 | 319 | 47 | 23 | 1 | 0 | 0 | 41 |
| E3 | 279 | 0 | 1 | 0 | 0 | 0 | 211 | 65 | 2 | 0 | 0 | 153 |
| E4 | 279 | 0 | 1 | 0 | 0 | 0 | 211 | 65 | 2 | 0 | 0 | 153 |

Relation accuracy given correct endpoints (pooled; gold pairs with a predicted edge):

- E0: 32 pairs, relation correct 23, direction correct 22
- E1: 52 pairs, relation correct 33, direction correct 33
- E2: 62 pairs, relation correct 40, direction correct 39
- E3: 216 pairs, relation correct 152, direction correct 150
- E4: 216 pairs, relation correct 152, direction correct 150

Provenance and unsupported rates (E0, pooled over sections):

- unsupported node rate 0.029; unsupported edge rate 0.000; provenance completeness 0.976

## SciNLP (mention level, 3 test documents, CI_status NOT_EVALUABLE_SMALL_N)

| level | relation strict micro P / R / F1 | per-document F1 | macro F1 | min / max doc F1 | entity strict micro F1 | entity typed micro F1 | $ |
|---|---|---|---|---|---|---|---|
| E0 | 0.364 / 0.027 / 0.050 | 2021=0.046, 2024=0.057, P17-1058=0.000 | 0.034 | 0.000 / 0.057 | 0.352 | 0.342 | 1.9315 |
| E1 | 0.635 / 0.159 / 0.255 | 2021=0.232, 2024=0.284, P17-1058=0.000 | 0.172 | 0.000 / 0.284 | 0.979 | 0.975 | 1.1904 |
| E3 | 0.730 / 0.339 / 0.463 | 2021=0.494, 2024=0.429, P17-1058=0.000 | 0.308 | 0.000 / 0.494 | 0.983 | 0.979 | 1.2727 |
| E4 | 0.781 / 0.339 / 0.473 | 2021=0.498, 2024=0.446, P17-1058=0.000 | 0.315 | 0.000 / 0.498 | 0.983 | 0.979 | 0.0 |

Mention-level earliest-failure attribution over gold relations (C0 / C1 not applicable: no identity gold):

| level | misses | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | recovered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 284 | 255 | 7 | 0 | 0 | 15 | 2 | 5 | 0 | 0 | 0 | 11 |
| E1 | 173 | 2 | 4 | 0 | 0 | 114 | 38 | 15 | 0 | 0 | 0 | 122 |
| E3 | 126 | 2 | 4 | 0 | 0 | 1 | 99 | 20 | 0 | 0 | 0 | 169 |
| E4 | 126 | 2 | 4 | 0 | 0 | 1 | 99 | 20 | 0 | 0 | 0 | 169 |

Identity metrics (canonical-node F1, pairwise, B-cubed, E2): NOT_SUPPORTED. No bootstrap over entities or edges; the diagnostic document bootstrap is DESCRIPTIVE_SMALL_N_ONLY and is not reported as a CI.


## Stability (3 independent E0 repeats, private caches, no best-run selection)

| benchmark | unit | F1 per run | mean | sd | node Jaccard | edge Jaccard | canonicalisation disagreement | relation disagreement |
|---|---|---|---|---|---|---|---|---|
| pd | 4.5 | 0.060, 0.062, 0.057 | 0.059 | 0.002 | 0.614 | 0.252 | 0.000 | 0.000 |
| pd | 4.4 | 0.024, 0.022, 0.072 | 0.039 | 0.023 | 0.620 | 0.257 | 0.000 | 0.051 |
| scinlp | P17-1058.grobid | 0.000, 0.000, 0.000 | 0.000 | 0.000 | 0.482 | 0.193 | 0.000 | 0.000 |
| scinlp | 2021.acl-long.353 | 0.035, 0.047, 0.023 | 0.035 | 0.010 | 0.683 | 0.411 | 0.000 | 0.000 |
