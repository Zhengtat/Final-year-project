# CLAUDE.md — H420020 Conceptual Understanding Mapper

## What this project is
Final-year project (FYP H420020) by Zheng Tat Wong. The system:
1. builds an **expert knowledge graph** from a university CS textbook;
2. converts **student free-text answers** into graphs;
3. compares the two edge by edge to diagnose what a student understands, what is **missing** (incomplete) and what is **contradicted** (misconception candidate).

- Domain: computer networking.
- Student data: SAF – Communication Networks (English).
- Expert source: Peterson & Davie, *Computer Networks: A Systems Approach* 6e (CC BY 4.0, `github.com/SystemsApproach/book`).

**Read before any work:** `docs/BUILD_PLAN.md` (milestones, tasks, acceptance checks), `docs/ARCHITECTURE.md` (pipeline, node/edge schema, diagnosis rules), `docs/DECISIONS.md`, `docs/PROGRESS.md`.

## How to work
- Do one milestone at a time, in order. Re-read its section in `BUILD_PLAN.md` before starting. Propose a short plan and wait for approval before large changes.
- **Stop and ask** at every step marked 👤 HUMAN (gold annotation, choosing pilot questions, reviewing samples, approving the relation registry). Never invent gold data.
- At the end of each milestone: run its acceptance checks, write what was verified (with numbers) and any open issues in `docs/PROGRESS.md`, then commit.
- Log every design or schema change in `docs/DECISIONS.md` (date · decision · reason · alternatives).
- Keep commits small, with clear messages. Don't push unless asked.

## Commands
```bash
uv sync                                   # install
uv run python -m spacy download en_core_web_sm
uv run pytest                             # tests (no network, no API key)
uv run ruff check . && uv run ruff format .
uv run cumap --help                       # CLI
uv run streamlit run src/cumap/app/review_app.py
```

## Non-negotiable rules
1. **Research rules** (see `ARCHITECTURE.md` §1):
   - missing ≠ contradicted;
   - a wrong answer ≠ a misconception;
   - semantic similarity ≠ conceptual correctness (embeddings only propose candidates);
   - one answer's graph ≠ a learner model;
   - book order ≠ prerequisite.
2. **`data/gold/` is human-owned.** Code must never create, modify or delete files there. Model drafts go to `data/interim/suggestions/`.
3. **Evidence or it doesn't enter the graph.** Every LLM-produced concept, edge or label carries a quote. The quote must be verified as an exact substring (after whitespace normalisation) of its source text. Failures are rejected and logged with a reason.
4. **All LLM calls go through `src/cumap/llm/client.py`**: Structured Outputs with Pydantic, a disk cache keyed by (model, prompt_version, input hash), and a log line with model, prompt version, tokens and run_id. Never call the OpenAI SDK anywhere else.
5. **Tests never touch the network or need a key.** Use `CUMAP_LLM_BACKEND=mock` and fixtures in `tests/fixtures/`.
6. **Secrets:** `OPENAI_API_KEY` comes from `.env`. Never commit `.env`, never print or log keys.
7. **Cost control:** every LLM command supports `--dry-run` and `--limit`. Run dry-run, then `--limit 20`, then the full run. Stop and ask if the estimate exceeds `max_usd_per_command` in `configs/default.yaml`.
8. **Prompts are versioned files** in `prompts/<task>/vN.md`. Never edit a version that has produced saved results; create `vN+1`.
9. **Split discipline:** tune only on train and validation. `test_unseen_answers` and `test_unseen_questions` are for final reporting only.
10. **The SAF feedback is privileged.** Only the silver-label builder (M4) may read `answer_feedback`. The diagnosis pipeline and the baselines must never see it.
11. **(CR-001) Relations change only through a new registry version** (`configs/relations_vX.Y.yaml`) plus a `DECISIONS.md` entry. Never add or rename a relation inside code or prompts.
12. **(CR-001) Relation classification is always a choice among registry options** (including reversed, none and other), never free-text labels — use `RelationRegistry.choice_set`/the dynamic v2 LLM schemas (`build_edge_suggestion_v2` and friends), not a plain `relation: str` field, for any new extraction prompt.

## OpenAI usage
- Use the Responses API with Structured Outputs:
  `client.responses.parse(model=..., input=[...], text_format=PydanticModel)` → `response.output_parsed`.
- Schema constraints for LLM-facing models:
  - every field required;
  - optional fields typed `X | None`;
  - no default values;
  - no extra properties.
  Keep these flat "LLM schemas" separate from the richer internal models, and convert between them.
- **(CR-001) Three tiers, from `configs/default.yaml` → `llm.tiers` (env override: `OPENAI_MODEL_STRONG`/`_BULK`/`_CEILING`):**
  - `strong` (default `gpt-6-sol`): KG construction, propositions, judging, gold-drafting (`suggest-expert`/`suggest-student`).
  - `bulk` (default `gpt-6-luna`): per-answer labelling and extraction (M4, M6).
  - `ceiling` (default `gpt-6-astra`): **opt-in only** — a model bake-off (`cumap eval model-bakeoff`) or similar. Never a default `model_tier` anywhere in the code.
- **(CR-001) Escalation:** a `bulk`-tier call retries once on `strong` when the schema fails to validate, the output's own `confidence` field is below `llm.escalation.confidence_threshold`, or the caller's `escalate_check` predicate says so (e.g. a failed evidence check). Never more than one retry. Logged with `escalated`/`escalation_reason`; the run manifest reports the escalation rate and cost split by tier.
- **(CR-001) Batch API:** for full-split bulk runs, submit via `--batch` and read results back through the *same* cache (`canonical_input_hash` has no batch-vs-live parameter by construction, so this is safe) — not yet implemented; build it when M4/M6 have a real bulk workload, not speculatively.
- **(CR-001) Prompt layout for caching:** in any new prompt, put static content (instructions, the registry guideline block, few-shot examples) **first** and per-item content **last**, so provider-side prefix caching helps at bulk-run scale.
- GPT-6 models don't accept `temperature`/`top_p` when reasoning is active. Set the reasoning effort per task in config instead; `gpt-6-astra` doesn't support effort `none` (use `low`). Reproducibility comes from the cache plus pinned prompt versions.
- At setup, check model IDs and the `parse` signature against the installed `openai` package and OpenAI's docs. If anything differs, update `configs/default.yaml` and log it in `DECISIONS.md`.

## Repo map (target)
```
configs/            default.yaml, relations_v0.yaml (history), relations_v1.yaml (CR-001, current)
data/raw/           downloaded datasets + textbook clone        (gitignored)
data/interim/       parsed sections, ID tables, suggestions/     (suggestions are drafts)
data/gold/          HUMAN-OWNED annotations                      (committed)
data/processed/     KG runs, silver labels, diagnoses by run_id  (gitignored)
data/cache/ data/logs/                                           (gitignored)
prompts/<task>/vN.md
src/cumap/          config, cli, llm/, schemas/, data/, textbook/, expert_kg/, labels/,
                    student/, align/, graph/, eval/, app/
tests/              unit tests + fixtures (incl. tests/fixtures/llm/<task>/*.json)
reports/            generated markdown reports per milestone
docs/               BUILD_PLAN, ARCHITECTURE, DECISIONS, PROGRESS
```

## Code style
Python 3.11, full type hints, Pydantic v2, ruff (line length 100), pytest. Small pure functions. Logic lives in `src/`; notebooks (if any) only call `src/`. Reports are generated by scripts, not written by hand.
