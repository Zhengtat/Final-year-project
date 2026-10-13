# CR-016 — final decision evidence (cross-section associative memory with HippoRAG 2)

Written for: Research, the project owner and examiners.

## Final status
| item | value |
|---|---|
| **Final status** | **DEVELOPMENT_ONLY_FEASIBILITY** |
| **Production change** | **NONE** (production extractor E\* = the unchanged CR-009 concept stage, U0; frozen canonicalisation, similarity gate (0.6) and review band (0.70) unchanged) |
| STOP 1 | done and approved with amendments |
| STOP 2 (retrieval-only benchmark) | done: PASS as a retrieval hypothesis |
| STOP 2B ($0 consumer-impact audit) | done |
| STOP 3 (pipeline memory ablation) | **NOT_RUN** (on hold, integration not justified) |
| STOP 4 (hybrid concept-card memory) | **NOT_REQUIRED** (not authorised by default) |
| STOP 5 (fresh held-out) | **NOT_RUN** |
| STOP 6 (downstream KG impact) | **NOT_REQUIRED** |
| Fresh sections | **all preserved untouched** (see below) |
| CR-016 spend | **≈ $0.81** (call-log total $0.811 of the $25 hard cap; STOP 1 $0) |

## What was established
1. **Isolation and mechanics (STOP 1).** HippoRAG (MIT, commit `d5c8329422e0a0b834a15874545cb6a74b4f9b26`, package `2.0.0a5`) conflicts with the main environment's pins (torch, transformers, networkx, python-igraph, tenacity), so it runs only in `.venv-hipporag/`. A stubbed smoke test showed incremental indexing, persistent reload, provenance metadata, a retrieval filter that fails closed on any future section, and separate arm indexes. The dense baseline (HippoRAG's `StandardRAG`) keeps no per-chunk metadata, so it needs a provenance sidecar.
2. **Retrieval benchmark (STOP 2).** 1,140 cases from 17 exposed gold-annotated sections, 2,071 paragraphs of 56 exposed units, strictly causal order, both memories on the same local MiniLM embedder (not the paper's configuration), HippoRAG model calls routed through the project client (rule 4). M2 HippoRAG vs M1 dense: Recall@5 0.659 vs 0.632 (Δ +0.026, 95% CI [+0.007, +0.052]), MRR 0.530 vs 0.492 (Δ +0.038, CI [+0.019, +0.057]), evidence precision@5 0.320 vs 0.292. The pre-registered gate was met through conditions (b) and (c) (not (a)); the low-lexical-overlap slice gained +0.128 Recall@5 (n = 109, CI [+0.058, +0.205]). Alias (58), acronym (34) and different-boundary (20) slices are too small to conclude; same-surface-different-sense showed no gain. 0 future-section retrieval violations, provenance completeness 1.00. Cost: M2 query latency 2.28 s vs 9 ms, HippoRAG indexing 25 minutes and $0.43, query filter $0.38.
3. **Consumer-impact audit (STOP 2B, $0).** Under the frozen canonicalisation, memory-assisted candidate injection is mechanically possible but changes no decision: only ≈ 2.3% of the production run's canonicalisation LLM calls are same-type decisions; of 58 benchmark cases that need the embedding-plus-LLM path, the embedding top-5 already holds the target in 50, and memory adds it in 0; across all 621 registered-target cases memory adds the target in 2 (M1) / 4 (M2) cases, none actionable under the frozen gate and band; injection adds about 2.5–2.9 non-target nodes per case (27 / 38 above the merge band; 5 / 4 lexicon-DIFFERENT look-alikes).

## Conclusion
HippoRAG 2 retrieves prior evidence modestly better than dense retrieval on the same backbone, mainly where the evidence shares little wording with the query, at much higher latency and a model call per query. The only approved consumer (candidate injection into the frozen canonicalisation) cannot use that advantage, because the frozen similarity gate and review band decide on name similarity. No gate was changed and no alternative consumer was built; both are left to a future change request. **No claim is made that memory improves the Expert KG**: no pipeline ablation and no KG-accuracy comparison were run.

## Limits to carry forward
Development material only (exposed gold of mixed provenance; nothing here is held-out evidence); one embedding backbone; the registry/node mapping in the audit is a gold-derived proxy; the cumulative book-order run needed to test existing-node linking end to end was never done; HippoRAG is an alpha release evaluated with the project's bulk-tier OpenIE model and adapter normalisations (42 triple answers re-wrapped, 4 invalid-JSON retries, 0 empty fallbacks, 0 errors; 11 of 1,140 fact-filter outputs failed to parse and used HippoRAG's built-in fallback).

## Fresh sections
Never indexed, never queried, no predictions and no gold created in CR-016: **4.3 (later development/pilot), 6.2 (reserve), 5.2, 6.5, 9.1, 9.4 (fresh held-out)**, and the untouched 5.1 and 8.1. Verified from the stage-2 corpus and queries: none of the eight section ids appears in either file.

## Artefacts
`STOP1_RECONCILIATION.md`, `exposure_audit.md`, `source_order_manifest.json`, `estar_manifest.json`, `smoke_test.json`, `retrieval_ablation.md`, `retrieval_slices.md`, `cost.md`, `stage2_results.json`, `records/` (retrieval records, queries, answer key, run manifest), `injection_feasibility.json`, `consumer_impact_audit.md`/`.json`, pre-registration `configs/cr016_stage2.yaml` (tag `cr016-stage2-prereg`), code in `src/cumap/cr016/`, isolated environment recipe in `STOP1_RECONCILIATION.md` §4.
