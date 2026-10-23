# CR-016 STOP 1 — repository and memory feasibility reconciliation

Written for: Research. Scope: reconciliation plus a tiny, **stubbed** smoke test; no real LLM call for HippoRAG, no large index, no E* run. Cost so far $0. Branch `cr-016-cross-section-memory`, created from `main` at the CR-015 merge (`c3f6b25`, tag `cr-015-complete`). CR-016 spec copied to `docs/change-requests/`.

## 1. Frozen extractor E*
CR-015 ended `NO_ELIGIBLE_DEVELOPMENT_ARM`, so **E\* = the unchanged CR-009 production concept stage (U0)**: generator `concept_generator` v4 (G1, bulk tier gpt-6-luna), rule verifier, pruner tau 0 and strict G-links on P&D (slice3_c2 recipe), `canonicalize` v2 type-aware, then the frozen downstream. Hash manifest: `reports/cr016/estar_manifest.json` (commit `c3f6b25c`, 12 config/prompt/code files and every `concepts_v4/*.py`, model tiers, sampling note). CR-014 V3 and CR-015 A2/B1/B2 are not adopted and are not part of E\*.

## 2. Existing-node, linking and canonicalisation mechanisms in the repository
- **Cross-section state exists only in a whole-run mode.** The generator (`concepts_v4/loop.py`, `cards.py`) shows "growing nodes of EARLIER sections of the SAME run" (`configs/concept_gvp.yaml`, `retriever.eligible: growing`), and links mentions to them (G-links; strict mode rejects links without a rule). Canonicalisation (`pd_run.canonicalise`, `expert_kg/canonicalize.py`, `alias_rules.py`) maps every v4 node to a concept by R0 lexicon / R1 key / R2 acronym / R3-strong rules, then an embedding-retrieved LLM same/different/narrower/broader/review decision, always under the CR-008 DIFFERENT veto.
- **Every recent evaluation, however, runs one-section slices with an EMPTY node store** (CR-012 E0, CR-014 pilot/held-out, CR-015). In those runs "existing-node linking" never triggers. A memory that "supports existing-node linking" can therefore only be tested if E\* is run **cumulatively in book order**, which has not been done since the ch1–3 production run (see §8, blocker B).

## 3. Memory integration point
Per CR §4: after current-section candidate/boundary formation and before final validity/linking. In the frozen E\* the verifier is rule-based code and the only LLM decisions are the generator and the canonicalise call, so a "memory evidence packet" has a real consumer only at the **canonicalisation same/different decision** (E\*) — and, if the CR-015 A2 selector/verifier were the extractor, at the verifier. The primary experiment would insert the packet into the canonicalise prompt (candidate vs retrieved prior passages). That changes a frozen prompt, so it needs Research's explicit approval (it is the only place memory can influence E\*'s decisions).

## 4. HippoRAG facts (verified from the repository and an installed copy)
| item | value |
|---|---|
| repository / licence | `OSU-NLP-Group/HippoRAG`, **MIT** (LICENSE read) |
| commit to pin | **`d5c8329422e0a0b834a15874545cb6a74b4f9b26`** (2026-10-06); package `hipporag` version `2.0.0a5` (alpha); the only tag is `v1.0.0` (HippoRAG 1), so the commit must be pinned, not a tag |
| Python | ≥ 3.10 (3.11 used) |
| pinned dependencies | `torch==2.5.1`, `transformers==4.45.2`, `litellm==1.73.1`, `networkx==3.4.2`, `python_igraph==0.11.8`, `tiktoken==0.7.0`, `tenacity==8.5.0`, `openai>=3.3.1,<4` |
| main-environment versions | torch 2.14.0, transformers 5.17.0, networkx 3.6.1, python-igraph 1.0.0, tenacity 9.1.4, openai 3.19.2 |
| conflict audit | **hard conflicts with the main environment** on torch, transformers, networkx, python-igraph and tenacity: an isolated environment is mandatory |
| isolated environment | `.venv-hipporag/` (Python 3.11.16, gitignored), installed at the pinned commit: torch 2.5.1, transformers 4.45.2, sentence-transformers 5.7.0, networkx 3.4.2, python-igraph 0.11.8, litellm 1.73.1, openai 3.29.0; main environment untouched |
| embeddings | `Transformers/<sentence-transformers model>`, OpenAI, NV-Embed-v2, GritLM, Contriever, Cohere, vLLM. The paper's NV-Embed-v2 (7B) is not realistic on this machine; the smoke test used local `all-MiniLM-L6-v2` (the project's own embedder) |
| index structure | `save_dir/<llm>_<embedding>/` with `graph.pickle`, `openie_state.json`, `index_manifest.json` (index identity), `chunk_metadata.json`, vector stores, plus `openie_results_*.json` and its own LLM cache; incremental `index(...)` and `delete(...)` supported; `Chunk(content, source_id, metadata)` carries provenance and `retrieve` returns `doc_metadata` |
| LLM use | indexing: **2 LLM calls per passage** (NER + triples); retrieval: **1 LLM call per query** (the "recognition memory" fact filter); `llm_base_url` accepts any OpenAI-compatible endpoint; default `temperature=0` must be unset (`None`) for reasoning models |

## 5. Tiny smoke test (stubbed LLM, mechanics only) — `reports/cr016/smoke_test.json`
`src/cumap/cr016/smoke_hipporag.py` (runs only in `.venv-hipporag`, imports nothing from cumap): a local stub answers the NER / triple / filter calls; 5 sections × ≤6 paragraphs indexed incrementally into two separate arms (HippoRAG; dense `StandardRAG` on the same package and embedder). Results:
| requirement | result |
|---|---|
| incremental indexing | **pass**; the index hash changes with each section in both arms |
| persistent reload | **pass**; a reloaded index returns the identical top-4 in both arms |
| source_id / metadata provenance | **pass** for HippoRAG (`chunk_metadata.json` with section, paragraph, source order, hash); **StandardRAG indexes plain strings and keeps no metadata**, so the dense arm needs an adapter-held provenance sidecar (the smoke test used one, persisted and reloaded) |
| causal retrieval filter | **pass**: the adapter raises `FutureLeak` when any returned chunk has `source_order ≥ query order` (tested on an index that did contain later sections: failed closed in both arms), and an index built only from earlier sections passed the filter in both arms |
| separate arm indexes | **pass**: independent directories and manifests |
Not tested: OpenIE quality, the fact-filter step with real facts, PPR behaviour, real cost. 60 stub calls, 5 s.

## 6. Chunking, dense baseline, index size and cost
- **Chunking:** the parsed text has 64 units, **2,654 textbook paragraphs**, mean 82 words, only 2 over 300 words: paragraph units with `section_id#p<i>` ids are directly usable (CR's preferred first implementation).
- **Dense baseline (M1):** same embedder and the same chunk store via HippoRAG's `StandardRAG` (identical chunking/ids/embedding code path) plus the provenance sidecar; embedding family default `all-MiniLM-L6-v2` for both M1 and M2 (a weaker embedder than the paper's; it must be declared).
- **Index size (estimates):** M1 ≈ 2,654 × 384-d vectors ≈ 4 MB. M2: ≈ 2,654 passage nodes plus ~10–20k phrase nodes and ~15–25k fact triples (paper-like ratios; unmeasured), tens of MB on disk.
- **OpenIE (M2, whole book, bulk tier gpt-6-luna at $0.10 / $0.50 per 1M tokens):** 5,308 calls, ≈ 5.1M input and 0.9M output tokens ≈ **$1.0–1.5** (hidden reasoning tokens could double the output), ≈ 1 h with 8 workers; on the strong tier it would be ≈ $19. Indexing is incremental in book order, so the cost is paid once per arm pass and OpenIE results can be cached across snapshots.
- **Retrieval calls:** M1 free. M2 one filter LLM call per query (≈ 3k tokens in); a Stage-A benchmark of ~4,000 queries ≈ $1–2; a Stage-B ablation querying every distinct selected span (≈ 7,300 across the 10 development sections) ≈ $2–3 and hours of sequential latency.
- **Verifier token increase** (3 paragraphs per packet): ≈ +330 input tokens per queried candidate, ≈ $0.2 per arm per 7,300 candidates.
- **Planning-limit check:** STOP 2 ≈ $2–4 (cap $8), STOP 3 ≈ $4–6 (cap $15), STOP 5 ≈ $3–5 (cap $12); the CR lists no budget for STOP 6, and a downstream two-arm run measured $11.7 on 40k words in CR-014, which on its own would use a quarter of the $45 hard cap.

## 7. Privacy, trace schema, scorer
- **API/privacy:** all indexed text is the public CC BY 4.0 textbook; no gold, labels, predictions or SciNLP text enter any index; the HuggingFace model is fetched unauthenticated; the OpenAI key stays in `.env`. **Rule 4 conflict:** HippoRAG calls the OpenAI SDK itself, which CLAUDE.md rule 4 forbids outside `llm/client.py`. Options: (A) a local OpenAI-compatible shim that forwards every HippoRAG call through `LLMClient` (cache, cost log, run id) — feasible but needs a raw-text path through a Pydantic schema; (B) a documented, logged exception for the isolated service. Either needs approval.
- **Trace schema:** stages `proposal`, `boundary_repair`, `boundary_family`, `concept_validity`, `mention_placement`, `adjudication` exist; CR-016's `memory_query`, `memory_retrieval`, `memory_consume`, `memory_update`, `memory_card_create` do not — an additive extension is needed (same method as CR-014/015).
- **CR-012 end-to-end scorer:** present and frozen (`cr012/scoring.py::score_graph_unit`, `stop4_score.py`, outputs `STRICT_E2E_EDGE`, node, identity metrics). It **can only be applied where relation gold exists: the nine CR-012 sections (1.5, 2.6, 4.4, 4.5, 5.4, 6.3, 7.1, 8.2, 9.3), all exposed**. Fresh sections have no relation gold, so the KG-accuracy comparison would be `NOT_EVALUABLE` on fresh data (CR §18.6). The reference level is low (E0 strict edge F1 0.053, section CI [0.030, 0.076]), so a memory-induced difference of a few hundredths would be inside the noise.

## 8. Findings that need a Research decision (none silently substituted)
- **A. Where memory can act in the frozen E\*.** E\*'s concept stage has no evidence-consuming verifier; memory would only matter at canonicalisation (changing a frozen prompt) or in a verifier that is not part of E\*. Which consumer defines the primary experiment?
- **B. Evaluation protocol.** One-section slices cannot test existing-node linking. A cumulative book-order E\* run with a growing node store is needed (≈ 200k words up to 9.4; U0 cost ≈ $0.027 per 1k words ≈ **$5.4 per arm**, three arms ≈ $16, each many hours sequentially) and has not been budgeted. Alternative: restrict the primary experiment to retrieval quality (Stage A) and evidence-only effects, with existing-node linking declared `NOT_EVALUABLE`.
- **C. LLM routing for HippoRAG** (rule 4): shim through `LLMClient` or a logged exception.
- **D. Embedding family:** local MiniLM (feasible, weak) vs a stronger local model vs an API embedding; M1 and M2 must share it.
- **E. Fresh data and gold:** four untouched sections (41.8k words) have no gold; two label-exposed, never-predicted sections (4.3, 6.2) have model-generated gold. Gold provenance for fresh data (model-generated again, or human-annotated) is undecided. Alias/acronym recurrence slices are small (a few hundred mentions in all exposed gold).
- **F. Budget:** STOP 6 downstream has no line in the cost contract.
- **G. HippoRAG maturity:** `2.0.0a5` alpha, single pinned commit; behaviour depends on the OpenIE model (bulk tier here, not GPT-4o-mini as in the paper).

Not a blocker as defined by the spec: future-section isolation is guaranteed by construction plus the fail-closed filter (smoke test), provenance is recoverable (HippoRAG metadata; dense via sidecar), HippoRAG can be isolated reproducibly (pinned commit, separate venv), and a valid evaluation strategy exists in principle (A/B above). Items B and E decide whether it exists *cheaply*.

## RESEARCH DECISION REQUIRED
1. Choose the primary consumer of memory (A) and the evaluation protocol (B): cumulative cost ≈ $16 and many hours, or a retrieval-quality-first study with existing-node linking `NOT_EVALUABLE`.
2. Approve the rule-4 approach for HippoRAG's LLM calls (C) and the embedding family (D).
3. Decide fresh-gold provenance for 5.2 / 6.5 / 9.1 / 9.4 (E) and whether 4.3 / 6.2 may serve as the CR-016 pilot.
4. Add a budget line for STOP 6 (F) or restrict the KG-accuracy diagnostic to the nine exposed CR-012 sections.
