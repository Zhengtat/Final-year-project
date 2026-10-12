# CR-014 STOP 2 — Stage A proposal-universe result (development only)

Scope: proposal recall only; no verifier, boundary or one-token logic was built or tuned. No held-out data was read. Dev set = **IIR dev, 13 sections, 17,987 words, 485 gold concepts** (`iir_gold_concepts.csv`; exposed dev data, different domain from P&D). Baseline U0 = the retained frozen N0 dev run (`data/processed/cr010/dev/N0.json`, the production recipe `frozen-1`, tau 0.1). Code: `src/cumap/cr014/{proposal,stage_a,gliner_proposer}.py`; results `data/processed/cr014/stageA/stage_a_results.json` (gitignored).

**Scorer reproduction check:** U0 exact proposal recall 0.520 = CR-010 STOP-2 dev N0 exact recall 0.522 (252/485 TP). The scorer is the repo's (`normalize(candidate)` equals a gold name or alias).

## Proposal gate
| arm | exact proposal recall | overlap recall | candidates | /1k words | candidates per gold | gate (≥0.80 exact, or ≥ U0+0.15) |
|---|---|---|---|---|---|---|
| U0 production final | 0.520 | 0.740 | 563 | 31 | 1.2 | reference |
| U1 deterministic | **0.942** | 0.981 | 5,132 | 285 | 10.6 | **PASS** (+0.422) |
| U2 U1 + current LLM (raw, pre-veto) | 0.963 | 0.988 | 5,289 | 294 | 10.9 | PASS |
| U3 U2 + 1 / 2 / 3 samples | 0.965 / 0.965 / 0.967 | 0.988 | 5,331 / 5,367 / 5,380 | 296–299 | 11.1 | PASS |
| U4 U2 + GLiNER | 0.965 | 0.988 | 5,397 | 300 | 11.1 | PASS |
| U5 U2 + 3 samples + GLiNER | 0.969 | 0.988 | 5,480 | 305 | 11.3 | PASS |
| (ref) U2f U1 + production-final LLM | 0.957 | 0.986 | 5,263 | 293 | 10.9 | PASS |
| (ref) LLM only: raw / raw + 3 samples | 0.586 / 0.658 | 0.800 / 0.864 | 638 / 850 | 35 / 47 | 1.3 / 1.8 | FAIL alone |
| (ref) GLiNER only (thr 0.1) | 0.676 | 0.893 | 1,113 | 62 | 2.3 | FAIL alone |

**Proposal-gate decision: PASSED on development** (U1 alone 0.942 ≥ 0.80 and ≥ 0.85 preferred target). Ceiling: 96.5% of gold strings occur verbatim in the section text, so no span proposer can exceed 0.965 under string matching; U5 reaches 0.969 only because aliases/other surface forms count.

## How to read this (caveats)
- U1 enumerates every contiguous 1–4-word subspan of noun/modifier runs, so its recall is close to the text ceiling **by construction**. Its candidate precision is ≈ 485×0.942/5,132 ≈ **9%**; the work moves entirely to the verifier (Stage B). A high proposal recall is not evidence of a good concept extractor.
- Gold in this dev set has **no character offsets**, so "exact" means exact normalised string, not exact span. Span-exactness and boundary behaviour can only be measured on the fresh P&D gold (not yet created).
- Dev is IIR, not P&D. The P&D result is untested; the gate here licenses Stage B on dev, not any claim about P&D.
- Overlap recall = a candidate contains / is contained in a gold name (stopword-only singletons excluded). With 5k candidates it is near-saturated and weakly informative.
- 3.5% of gold (17 of 485) never occurs verbatim in the text; those are outside every string proposer.

## Incremental recall by proposer (dev, exact)
| source | alone | gold covered only by it, i.e. drop when removed from the full union (U5) |
|---|---|---|
| U1 deterministic | 0.942 | **−0.148** (72 gold) |
| current LLM raw (pre-veto) | 0.586 | −0.002 |
| current LLM final (production) | 0.526 | 0.000 |
| GLiNER | 0.676 | −0.002 |
| samples 1 / 2 / 3 | 0.522 / 0.532 / 0.518 | −0.002 / 0.000 / −0.002 |

Cumulative gain over U2 (0.963): 1 sample +0.002, 2 samples +0.002, 3 samples +0.004; GLiNER +0.002. Independent LLM samples raise LLM-only recall 0.586 → 0.658 (+0.072) but add almost nothing once U1 is present. **Independence finding:** the production pipeline loses 6.6 points of its own generator's recall to its rules/pruner/G-link vetoes (raw 0.586 vs final 0.520; 32 gold concepts proposed and then dropped).

U1 sub-source standalone exact recall (candidates): np 0.763 (2,674), compound 0.437 (1,224), noun_span 0.338 (2,505), head 0.287 (1,793), recurrent 0.196 (299), adj_noun 0.181 (982), definitional 0.039 (54), acronym 0.006 (4), heading 0.000 (1), of_phrase 0.000 (248). Heading, of-phrase and acronym sources contribute nothing on this domain/data.

## Slices (exact proposal recall; n = gold count)
| arm | 1-token (172) | 2-token (248) | 3-token (57) | 4+ (8) | known (178) | new (307) | definitional cue (11) | no cue (474) |
|---|---|---|---|---|---|---|---|---|
| U0 | 0.541 | 0.540 | 0.404 | 0.250 | 0.685 | 0.423 | 0.818 | 0.513 |
| U1 | 0.959 | 0.940 | 0.895 | 1.000 | 0.944 | 0.941 | 1.000 | 0.941 |
| U2 | 0.971 | 0.964 | 0.930 | 1.000 | 0.955 | 0.967 | 1.000 | 0.962 |
| U3 (3 samples) | 0.971 | 0.972 | 0.930 | 1.000 | 0.955 | 0.974 | 1.000 | 0.966 |
| U4 | 0.971 | 0.964 | 0.947 | 1.000 | 0.955 | 0.971 | 1.000 | 0.964 |
| U5 | 0.971 | 0.972 | 0.947 | 1.000 | 0.955 | 0.977 | 1.000 | 0.968 |
| GLiNER only | 0.686 | 0.698 | 0.561 | 0.625 | 0.736 | 0.642 | 1.000 | 0.669 |

One-token proposal recall: U0 0.541 → U1 0.959 (no one-token class is lost at the proposal stage). "Known" = a name already gold in an earlier dev section (gold-derived, evaluation only). Emphasis-cue slice has n = 0: no dev emphasised term equals a gold name. Definition cues: only 11 gold.

## Source-overlap matrix (Jaccard of covered gold; candidate-set Jaccard in the JSON)
| | u1 | llm_raw | llm_final | GLiNER | s1 | s2 | s3 |
|---|---|---|---|---|---|---|---|
| u1 | 1 | 0.59 | 0.53 | 0.70 | 0.52 | 0.54 | 0.52 |
| llm_raw | 0.59 | 1 | 0.90 | 0.59 | 0.81 | 0.77 | 0.82 |
| GLiNER | 0.70 | 0.59 | 0.55 | 1 | 0.55 | 0.55 | 0.54 |
| s1 / s2 / s3 | 0.52–0.54 | 0.77–0.82 | 0.74–0.79 | 0.54–0.55 | 1 | 0.84 / 0.79 | 1 |

Gold covered: u1 457, GLiNER 328, llm_raw 284, llm_final 255, samples 251–258. Samples overlap each other at 0.79–0.85 of covered gold, so they are largely redundant. Candidate-set Jaccard between u1 and any LLM source is only 0.07–0.09 (LLM proposals are a small, mostly-contained subset).

## Runtime and cost
| item | amount |
|---|---|
| U1 deterministic (spaCy, CPU) | 23.4 s for 13 sections / 18k words ($0) |
| GLiNER `urchade/gliner_medium-v2.1` threshold 0.1 | load 6.7 s (first model download ≈ 50 s), predict 15.1 s CPU ($0) |
| U3 samples (gpt-6-luna, bulk, raw 1 call/section, no verifier) | 3 × ≈$0.035 = **$0.1044 total**; ≈ 252 s per sample wall time (sequential) |
| Preflight estimate | $0.178 (upper); actual lower because there is no verifier reprompt |
| Cap check | $0.10 spent of the $15 dev soft target and $30 hard cap; no pilot/held-out spend |

U4 dependency: `gliner==0.2.29` with torch 2.14, run **ephemerally** (`uv run --no-project --with gliner …`); `pyproject.toml` / lockfile unchanged. Licences (library and model card) have **not been independently confirmed** from sources in this environment; the model was fetched unauthenticated from the Hugging Face Hub. Treat GLiNER as adoptable only after Research/owner confirms the licence. Because it adds +0.002 recall over U2, nothing here argues for adopting it.

## Candidate-universe implications for Stage B (no work done yet)
- Verifier load at U1/U5 volume: ≈ 285–305 candidates per 1,000 words (≈ 11 per gold concept); on the 18-section fresh P&D pool (101,931 words) this means ≈ 29–31k candidates, so candidate-level LLM verification needs ranking/batching and nested-span grouping (overlap families) before any paid call.
- The proposal stage no longer limits recall on this dev set; precision-recovery is the open question.

## RESEARCH DECISION REQUIRED
1. Confirm that the proposal gate is **passed** (U1 0.942; +0.422 over U0) and that Stage B may start on the U5-family union, or prefer a smaller union. Evidence favours **U2 (U1 + current LLM raw)**: U3/U4/U5 add ≤ +0.006 for 91–191 more candidates and extra paid/dependency cost. Recommended Stage-B union: U2 (or U1 alone if the pre-veto LLM output must be excluded).
2. The independence finding (6.6 points lost to vetoes) shows the raw pre-rule LLM output must be kept as a proposal source; confirm that Stage B uses the **raw iteration-0 output**, not the post-verifier `final`.
3. Approve a fresh P&D benchmark selection (still pending from STOP 1) because span-level exactness, boundary quality and P&D transfer cannot be measured on IIR dev.
4. GLiNER licence confirmation (only matters if U4/U5 is chosen).
5. Whether to extend the CR-013 trace stages (proposal/boundary) now (still pending from STOP 1).
