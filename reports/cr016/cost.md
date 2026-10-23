# CR-016 STOP 2 — cost, runtime and index size

All model spend is read from the project's call log (`data/logs/llm_calls.jsonl`, run id `cr016_s2_hipporag`, bulk tier gpt-6-luna at $0.10 / $0.50 per 1M input / output tokens, cache hits free).

| item | calls | cache hits | input tokens | output tokens | USD |
|---|---|---|---|---|---|
| M2 offline indexing: NER | 4,031 | 1,961 | 642,458 | 149,210 | 0.1389 |
| M2 offline indexing: triples | 4,031 | 1,961 | 1,277,412 | 335,735 | 0.2956 |
| M2 online queries: fact filter (1,140 queries) | 1,140 | 0 | 3,337,555 | 85,422 | 0.3765 |
| M1 dense (local embeddings) | 0 | – | – | – | 0 |
| **STOP 2 total** | | | | | **0.8110** |

Offline indexing ≈ $0.43 for 2,071 paragraphs (the cache hits are the repeated runs after the adapter fixes, so the table counts each call once as spent; indexing only the first time was billed). Online query cost ≈ $0.00033 per query (≈ 2,900 input tokens per fact-filter call). Planning allocation was ≤ $3 for STOP 2 (actual $0.81); cumulative CR-016 spend $0.81 against the $25 hard cap ($20 warning).

| time | M1 dense | M2 HippoRAG |
|---|---|---|
| indexing 2,071 paragraphs (incremental, per unit) | 38 s | 1493 s (≈ 25 min, 8 workers) |
| 1,140 queries | 10.2 s (9 ms / query) | 2597 s (2.28 s / query) |
| whole run | 4138 s wall clock |

Index snapshot ids (after the last unit): M1 `M1_dense:9-perspective-the-cloud-is-the-new-internet@c4153e3a876bb1e7`, M2 `M2_hipporag:9-perspective-the-cloud-is-the-new-internet@2f1e9ec4817f7551`. Environment: {"hipporag": "2.0.0a5", "torch": "2.5.1", "transformers": "4.45.2", "sentence-transformers": "5.7.0", "networkx": "3.4.2", "python-igraph": "0.11.8", "litellm": "1.73.1", "openai": "3.29.0"}; embedding `Transformers/sentence-transformers/all-MiniLM-L6-v2`; config hash `cf9787ed740b78c4`; HippoRAG commit `d5c8329422e0a0b834a15874545cb6a74b4f9b26`.

Machine-readable records (`reports/cr016/records/`): `retrieval_records.jsonl.gz` (query_id, query_section, backend, index_snapshot_id, retrieved item ids, source sections, rank, score, source locator, future-section check, embedding identity, config hash, latency), `queries.jsonl.gz` (runtime-visible query inputs), `answer_key.jsonl.gz` (relevance and slice flags, read only by scoring), `run_manifest.json` (per-unit index snapshots and timings).
