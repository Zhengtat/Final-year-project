# Progress

Update at the end of every milestone: what was done, which acceptance checks passed (with numbers), open issues, next step.

| Milestone | Status | Verified (numbers) | Notes |
|---|---|---|---|
| M0 Repo scaffold, LLM wrapper, CLI | done | 7/7 tests pass, 0 network calls; `ruff check` clean; `cumap --help` lists all 9 groups; cache-hit test shows 1 backend call across 2 identical `parse()` calls | |
| M1 Data ingestion, textbook, EDA, coverage | in progress — paused at 👤 HUMAN step | SAF: 2981 rows across 4 splits, counts match plan exactly (train 1700, validation 427, UA 375, UQ 479); 31 distinct questions (26 seen + 5 unseen, no overlap). Textbook: 64 sections, 9 chapters + 3 front-matter, 0 empty sections, order_index strictly increasing, 0 real residual-markup issues in a full-book scan. EDA report done. Coverage map done: embedding top-5 + LLM full/partial/none guess for all 31 questions (5 full, 16 partial, 10 none by the automated pass; see DECISIONS.md for a truncation bug found and fixed mid-run, and a residual embedding-retrieval limitation on 2 questions). | Score scale finding, near-dup question finding, coverage-guess retrieval limitation — see DECISIONS.md. Awaiting human pilot-question pick. |
| M2 Schemas & relation registry | done (registry logic + `gold validate`); relation list itself still 👤 draft | 51/51 tests pass (15 registry, 9 round-trip, 9 gold-validate, rest from M0/M1). Registry: reversing a symmetric relation is not a reversal ✓, increases/decreases conflict ✓, triggers/causes partially compatible ✓, is_a cycle detected ✓. `cumap gold validate` passes on good fixtures, reports readable messages on broken ones (unverified evidence quote, unknown relation, unverified evidence_span), and passes cleanly on the real (currently empty) `data/gold/`. | `configs/relations_v0.yaml` is still a draft awaiting 👤 approval — registry code works against it as-is but the relation list itself isn't signed off. |
| M3 Manual pilot gold | not started | | 👤 human annotation |
| M4 Silver labels from feedback | not started | | 👤 verify 150–200 |
| M5 Expert KG pipeline v1 | not started | | |
| M6 Expected subgraphs + student extraction | not started | | |
| M7 Alignment, diagnosis, evaluation | not started | | |
| M8 (stretch) Misconceptions, feedback, Mohler | not started | | |
| M9 Demo & results pack | not started | | |

## Log
<!-- newest first: YYYY-MM-DD · milestone · summary -->
- 2026-09-28 · M0 · Repo scaffolded (`git init`, `uv init`-equivalent `pyproject.toml`, `src/cumap/` package). LLM wrapper built: `llm/cache.py` (diskcache, sha256 key), `llm/mock.py` (fixture-backed), `llm/client.py` (`LLMClient.parse` — cache → mock/OpenAI → cache-write → JSONL log, hashes/metadata only, tenacity retry on 429/5xx), `llm/prompts.py` (versioned prompt loader). `config.py` loads `configs/default.yaml` + `.env`, env vars override model names. `cli.py` (Typer) has all 9 command groups (`data`, `textbook`, `gold`, `labels`, `kg`, `student`, `diagnose`, `eval`, `app`) with `not-implemented` stubs. Verified installed `openai==3.19.2` SDK against CLAUDE.md's Responses API description — matches exactly (see DECISIONS.md). Acceptance checks: `uv run pytest` → 7/7 pass, no network/key; `uv run cumap --help` lists all groups; mock-parse round-trip + cache-hit tests pass (`backend_call_count == 1` after 2 identical calls); `uv run ruff check .` clean. Noted: `data/*.parquet` (SAF splits) already present in repo root `data/`, apparently downloaded by the user ahead of M1 — left untouched, will relocate to `data/raw/saf/` in M1 rather than re-downloading. Committed.
