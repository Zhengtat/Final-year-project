# Progress

Update at the end of every milestone: what was done, which acceptance checks passed (with numbers), open issues, next step.

| Milestone | Status | Verified (numbers) | Notes |
|---|---|---|---|
| M0 Repo scaffold, LLM wrapper, CLI | done | 7/7 tests pass, 0 network calls; `ruff check` clean; `cumap --help` lists all 9 groups; cache-hit test shows 1 backend call across 2 identical `parse()` calls | |
| M1 Data ingestion, textbook, EDA, coverage | not started | | |
| M2 Schemas & relation registry | not started | | |
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
