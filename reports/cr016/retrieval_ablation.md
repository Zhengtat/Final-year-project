# CR-016 STOP 2 — retrieval-only benchmark: dense (M1) vs HippoRAG 2 (M2)

Written for: Research. Retrieval only: no change to concept extraction or canonicalisation, no cumulative pipeline run, no fresh section touched. Pre-registered before any index or query (`configs/cr016_stage2.yaml`, tag `cr016-stage2-prereg`); the only post-registration changes were adapter fixes in the LLM shim (below) made before any result was seen.

## Set-up (as approved)
- **Memories:** M1 = HippoRAG's own `StandardRAG` (dense, same package, same chunk store) + a provenance sidecar; M2 = HippoRAG 2 (OpenIE, fact retrieval, recognition-memory filter, personalised PageRank). **Same embedder for both: local `all-MiniLM-L6-v2`**; same chunks (textbook paragraphs `section#p<i>`), same frozen query text (`"<surface>: <source sentence>"`, byte-identical), same top-k (10; metrics at 1/3/5). This is **not a reproduction of HippoRAG's best paper configuration** (NV-Embed-v2/GritLM, GPT-4o-mini OpenIE); it is the project's controlled MiniLM backbone.
- **Strict causal order:** the runner loops over the exposed units in book order; for each unit it answers that unit's queries against the index of EARLIER units only, then indexes the unit. Every retrieved item is checked and the run fails closed on any item with `source_order ≥ query order`.
- **Data (exposed only):** corpus = 2,071 paragraphs of 56 units (all units except the fresh allocation 4.3, 6.2, 5.2, 6.5, 9.1, 9.4 and untouched 5.1, 8.1, which were never indexed or queried). Queries = **1,140** cases (every case with valid earlier evidence; nothing had to be subsampled) from 17 gold-annotated exposed sections (CR-012, CR-014 gold; model-generated or owner-reviewed, provenance as in their manifests). Relevant evidence = an earlier paragraph containing a gold mention of the same concept or a word-bounded occurrence of one of its surfaces (name, aliases, mention surfaces); the answer key is read only by scoring.
- **HippoRAG LLM calls** go through a local OpenAI-compatible shim into `LLMClient` (rule 4: cache, call log with model, tokens, run id, cost; bulk tier gpt-6-luna). Adapter fixes: the shim wraps a bare list or a differently named list as `{"triples": …}` (42 answers), retries once when an answer is not valid JSON (4 retries, all recovered), and would fall back to an empty extraction (0 fallbacks); 0 request errors; HippoRAG's own fact-filter output failed to parse for 11 of 1,140 queries (≈ 1%, handled by HippoRAG's built-in fallback).

## Overall results (1140 queries, both backends)
| metric | M1 dense | M2 HippoRAG | Δ (M2−M1) | 95% CI (bootstrap by query section) |
|---|---|---|---|---|
| Recall@1 | 0.387 | 0.421 | +0.034 | [+0.007, +0.061] |
| Recall@3 | 0.553 | 0.605 | +0.053 | [+0.029, +0.075] |
| Recall@5 | 0.632 | 0.659 | +0.026 | [+0.007, +0.052] |
| MRR@10 | 0.492 | 0.530 | +0.038 | [+0.019, +0.057] |
| evidence precision@5 | 0.292 | 0.320 | +0.028 | – |
| mean retrieval latency (s/query) | 0.0089 | 2.28 | ×255 | – |

## Pre-registered Stage-A gate
| condition | result |
|---|---|
| (a) Recall@5 ≥ M1 + 0.05 | **not met** (Δ +0.026) |
| (b) 95% bootstrap lower bound > 0 for ΔRecall@5 or ΔMRR | **met**: ΔRecall@5 lower bound +0.007, ΔMRR lower bound +0.019 (narrow for Recall@5) |
| (c) a pre-registered difficult slice ≥ +0.10 with overall Recall@5 regression ≤ 0.03 | **met**: low-lexical-overlap / associative slice ΔR@5 = +0.128 (n = 109, 17 sections, CI [+0.058, +0.205]); acronym +0.206 (n = 34; CI includes 0); overall change +0.026 |
| future-section retrieval violations = 0 | **0** |
| retrieval provenance completeness = 1.00 | **1.00** |
**Mechanical gate outcome: the rule permits proceeding to pipeline integration (conditions (b) and (c) met).** The size of the effect is small: +0.026 absolute Recall@5, +0.038 MRR, +0.028 evidence precision@5, at 250× the query latency and a model call per query.

## Where the benefit is, and is not (slices in `retrieval_slices.md`)
- Largest gains: low-lexical-overlap / associative evidence (+0.128 R@5), acronym recurrence (+0.206, only 34 queries, CI includes 0), and cases with ≤ 5 relevant paragraphs (+0.070, CI [+0.032, +0.112]); long-gap +0.058 (CI [+0.008, +0.114]).
- No gain: exact-surface (+0.015, CI includes 0), short-gap (+0.005), medium and common evidence (−0.014 / 0.000), same-surface-different-sense (+0.017: no sense-disambiguation benefit) and different-boundary (+0.050, n = 20, CI wide).
- Alias and boundary slices are tiny (58 and 20 queries), as flagged by Research; their CIs include 0.

## Is the proposed canonicalisation injection point feasible without changing frozen semantics?
**Mechanically yes, practically inert.** `canonicalize._canonicalize` builds its candidate list from an embedding top-k of the registry and (i) skips the LLM entirely unless the best candidate's similarity is ≥ 0.6, (ii) never merges an LLM "same" whose matched similarity is < 0.70 (it creates a new concept and routes the pair to review). An optional `extra_candidates` argument could add memory-mapped prior nodes to the list without touching the decision rules, but the gate and band still decide on name-embedding similarity. Measured on the exposed benchmark cases (registry proxy = canonical names of concepts first seen earlier):
| subset of benchmark cases (concept already registered, surface differs from its canonical name) | cases | prior concept already in the embedding top-5 | name similarity ≥ 0.6 (LLM gate) | name similarity ≥ 0.7 (merge band) | **outside top-5 but ≥ 0.7 (injection could change a merge)** |
|---|---|---|---|---|---|
| all | 200 | 173 | 157 | 144 | **0** |
| one_token | 131 | 106 | 90 | 78 | **0** |
| acronym | 25 | 6 | 3 | 0 | **0** |
| alias | 9 | 8 | 8 | 8 | **0** |
| associative_low_lexical_overlap | 19 | 18 | 18 | 18 | **0** |
| different_boundary | 4 | 4 | 4 | 4 | **0** |
So in these cases **no** memory-suggested node falls outside the embedding top-5 while clearing the merge band: injection would change no merge decision under the frozen semantics. For acronym cases (25) the name similarity is low (mean 0.47; 0 clear the merge band), and they are handled by the deterministic acronym rule (R2), not by embeddings. For memory to alter canonicalisation outcomes, the similarity gate or review band would have to be bypassed — a semantics change that needs Research approval, as instructed.

## Caveats
- The approved MiniLM backbone is weak; HippoRAG's graph components may benefit more or less from a stronger embedder. Not tested (not allowed after seeing results).
- Relevance is lexical or gold-linked, so exact-surface queries are easy for both systems; the common-evidence bucket (292 queries) is saturated at 0.818.
- Slices overlap (multi-label); the same-surface-different-sense slice is a proxy (one surface annotated under different canonical names).
- Gold is exposed development material with mixed provenance; nothing here is held-out evidence. One run per backend; HippoRAG's LLM steps are cached but not repeated.

## RESEARCH DECISION REQUIRED
1. The pre-registered gate permits pipeline integration, but the absolute gain is small and the only approved consumer (canonicalisation candidate injection) is inert under the frozen decision semantics (0 of 200 candidate cases). Proceed to STOP 3 anyway, choose a different consumer, relax the frozen gate/band (a semantics change), or stop here?
2. If proceeding, is a cumulative book-order E* run (≈ $5.4 per arm, many hours) justified for an inert consumer?
