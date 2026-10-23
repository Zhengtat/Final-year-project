# CR-012 FINAL EVALUATION: end-to-end Expert-KG evaluation

Written for: the examiners and Research. All numbers come from the single frozen held-out execution (`cr012-stop4-complete`, 4697acb) under the `stop3-frozen` configuration; nothing was tuned, rerun or rescored after it.

## 1. What this evaluation is

**Software / operational result.** The complete pipeline runs from raw text to a canonical typed graph under a frozen, reproducible workflow (hashes, run log, cache-keyed model calls, evidence-checked output).
**Accuracy result.** The current frozen system has **low strict end-to-end graph accuracy**. The Expert KG must not be described as validated or high-accuracy on the basis of these results. CR-012 is not a failure: it identifies where the architecture loses accuracy, which is its research purpose.

## 2. Headline results (two benchmarks, never pooled)

| benchmark | headline | value |
|---|---|---|
| P&D-E2E (in-domain, 7 held-out sections) | STRICT_E2E_EDGE P / R / F1, E0 | **0.092 / 0.038 / 0.053**; section-bootstrap interval [0.030, 0.076], DESCRIPTIVE_SMALL_N |
| SciNLP (external, 3 test documents) | strict relation P / R / F1, E0 | **0.364 / 0.027 / 0.050**; CI_status NOT_EVALUABLE_SMALL_N; per-document / macro / min-max in `external_e2e.md` |

The annotation schemas differ (P&D: exhaustive canonical-graph gold with 17 relations; SciNLP: selective mention-level gold with 11 relations), so the two E0 numbers are not comparable accuracy scores (`figures/headline_e0_pd_vs_scinlp.svg`).

## 3. Where accuracy is lost (hypotheses supported by the oracle runs; conditional / oracle uplifts, not an additive decomposition)

- **P&D main bottleneck: candidate pair / endpoint delivery.** 307 / 416 = 73.8% of earliest E0 misses are extraction or pair delivery (P0 49.5%, N0+N1 24.3%). Pair recall at E0 is 53 / 326 = 16.3%. Largest oracle uplift E2 -> E3: 0.129 -> 0.398.
- **Relation classification** is not solved but is much stronger than E0 suggests: 70.4% relation / 69.4% direction correct on E3 pairs. E4 (0.470) is a gold-endpoint ceiling, not production accuracy.
- **Canonicalisation** is not the dominant held-out bottleneck (E1 0.113 -> E2 0.129); the development pilot suggested otherwise and the held-out result takes priority.
- **SciNLP main bottleneck: entity / concept extraction** (255 / 284 = 89.8% of E0 misses; E0 0.050 -> E1 0.255). E3-M - E1 is the post-mention / endpoint-delivery loss (no E2 identity oracle); E3-M -> E4-M 0.463 -> 0.473.

## 4. Stability, support and provenance

- Three independent repeats on the frozen subset: generally modest stability, P&D 4.4 the widest (F1 0.022-0.072). The canonicalisation-disagreement statistic is NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR (`stability.md`).
- Unsupported nodes / edges and provenance completeness (E0 P&D): see `unsupported_facts.md` and `provenance.md` (provenance completeness 0.976).

## 5. CR-011

CR011_PRE_POST = NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION. CR-011 adopted no production graph transformation, so no pre/post comparison and no delta_F1_sleep exist or are reported.

## 6. Cost

STOP-4 spend $23.07; cumulative CR-012 spend **$25.9265**, within the approved budget (`cost.md`).

## 7. Limitations

1. **Single annotator** for the P&D held-out gold: inter-annotator agreement NOT_EVALUABLE_SINGLE_ANNOTATOR. The LLM prefill was reviewed by the owner and is not a second annotator. This weakens certainty in the exact gold graph.
2. **Small n**: 7 P&D sections and 3 SciNLP documents; one SciNLP test document has only one gold relation. Intervals are descriptive.
3. Annotation schemas and densities differ between the benchmarks; SciNLP is selectively annotated while the pipeline extracts exhaustively, which depresses strict precision by construction.
4. SciNLP E3-M / E4-M use surface-level pseudo-nodes; SciNLP identity metrics, E2 and canonical-node scores are NOT_SUPPORTED.
5. Strict scoring (exact spans, types, relations, direction) is deliberately harsh; the scores are not a measure of human-judged usefulness of the graph.
6. One system recipe (CR-009 `slice3_c2` with the frozen D3 pair budget) and one execution; no ablation of the budget or ranking was run, by design.
7. The development pilot and held-out results disagree on the canonicalisation share; the held-out result is used.
8. The stability disagreement metric is non-informative under its frozen denominator.
9. The pair budget (14.2 pairs / 1k words) was saturated in all 10 held-out E0 units (pool larger than budget, selected = budget), so pair-delivery results are specific to that budget.

## 8. Process record

One execution defect (an over-eager leakage assertion that false-positived on words of the book sentence in the section 4.4 E3 oracle; stopped before any spend, fixed, logged in `invalid_runs.md`). Earlier development-time converter defects are likewise logged. No result was discarded or selected.

## 9. Reports and figures

`pd_e2e.md`, `external_e2e.md`, `oracle_error_attribution.md`, `stability.md`, `unsupported_facts.md`, `provenance.md`, `cost.md`, `CR012_FAILURE_ANALYSIS.md`; `figures/*.svg`. CR-011 consolidation: NOT APPLICABLE, no production transformation adopted (no fake pre/post chart is produced).
