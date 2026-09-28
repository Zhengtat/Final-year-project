# H420020 — Conceptual Understanding Mapper

Final-year project: builds an expert knowledge graph from a networking textbook, converts
student free-text answers into comparable graphs, and diagnoses each answer as *correct*,
*incomplete* (missing edges) or *contradictory* (misconception candidate) by aligning the
two graphs edge by edge.

See `docs/BUILD_PLAN.md` (milestones), `docs/ARCHITECTURE.md` (pipeline and schemas),
`docs/DECISIONS.md` (fixed design choices) and `docs/PROGRESS.md` (status) before working
on this repo. `CLAUDE.md` has the non-negotiable rules (gold-data ownership, evidence
verification, LLM call discipline, cost controls).

## Setup

```bash
uv sync                                   # install dependencies into .venv
uv run python -m spacy download en_core_web_sm
cp .env.example .env                      # then fill in OPENAI_API_KEY
uv run pytest                             # tests: no network, no API key needed
uv run ruff check . && uv run ruff format .
uv run cumap --help
```

## CLI command groups

| Group | Purpose |
|---|---|
| `cumap data` | Download and prepare raw datasets (SAF). |
| `cumap textbook` | Fetch and parse the Peterson & Davie textbook source into sections. |
| `cumap gold` | Suggestion tooling for human annotation; validates `data/gold/`. Never writes to it. |
| `cumap labels` | Silver relation-level labels derived from SAF feedback (M4). |
| `cumap kg` | Expert knowledge graph construction (M5) and expected subgraphs (M6). |
| `cumap student` | Student answer → graph extraction (M6). |
| `cumap diagnose` | Aligns student graphs to expected subgraphs, produces diagnoses (M7). |
| `cumap eval` | Evaluation, baselines and ablations (M7). |
| `cumap app` | Streamlit review and demo apps. |

Every LLM-calling command supports `--dry-run` (prints planned call count and a rough
token/cost estimate, then exits) and `--limit N`.
