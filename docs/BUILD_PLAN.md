# Build Plan — H420020 Conceptual Understanding Mapper

Version 1 · 2026-09-28 · Owner: Zheng Tat Wong

This is the working plan the coding agent (Claude Code) follows. Work the milestones **in order**. Each one lists its goal, tasks, the files it produces, **acceptance checks**, and the steps only the human can do (marked 👤 **HUMAN**: stop and ask).
See `ARCHITECTURE.md` for the pipeline and the full node/edge schema, and `DECISIONS.md` for fixed choices.

---

## 0. Scope

**Research question:** Can comparing concepts and relations between a student's answer graph and an expert knowledge graph separate *correct*, *incomplete* and *contradictory* (misconception-bearing) answers better than text-similarity and classifier baselines? And can it say *which* relation is missing or wrong?

**MVP (definition of done):** M0–M7 complete for the **5 pilot questions** first, then extended to every SAF question the textbook covers well. Results are reported on held-out splits.

**Stretch:** M8 (misconception layer + feedback, Mohler second domain), M9 (demo polish).

**Domain & data**

| Item | Choice |
|---|---|
| Student answers | SAF – Communication Networks (English), Hugging Face `Short-Answer-Feedback/saf_communication_networks_english` (CC BY 4.0). Splits (confirm the names on download): train ≈1.7K, validation 427, test unseen answers 375, test unseen questions 479. Fields: question, reference_answer, provided_answer, answer_feedback, verification_feedback (Correct / Partially correct / Incorrect), score (0–1). **No question IDs, no student IDs.** |
| Expert source | Peterson & Davie, *Computer Networks: A Systems Approach*, 6th ed., CC BY 4.0. Source: `github.com/SystemsApproach/book` (reStructuredText, one folder per chapter). Pin the commit hash. |
| Second domain (stretch) | Mohler data-structures dataset (Hugging Face `Viswa45/ASAG`) + Morin, *Open Data Structures*. |
| LLM | OpenAI Responses API with Structured Outputs. `OPENAI_MODEL_STRONG` (default `gpt-6-astra`) for KG building and judging; `OPENAI_MODEL_BULK` (default `gpt-6-luna`) for bulk extraction and labelling. |

**Split discipline:** prompts, thresholds and rules are tuned on **train + validation only**. `test_unseen_answers` (UA) and `test_unseen_questions` (UQ) are used only for final reporting.

---

## 1. Timeline at a glance (estimates)

| Milestone | Weeks | Depends on | Human effort |
|---|---|---|---|
| M0 Repo scaffold, LLM wrapper, CLI | 0.5 | — | low |
| M1 Data ingestion, textbook parsing, EDA, coverage map | 1 | M0 | 👤 confirm coverage + pick pilot questions |
| M2 Schemas & relation registry | 0.5 | M0 | 👤 approve relation list |
| M3 Manual pilot gold (expert + student graphs) | 1.5 | M1, M2 | 👤 **high**: the annotation itself |
| M4 Silver relation-level labels from SAF feedback | 1.5 | M2, M1 | 👤 verify ~150–200 answers |
| M5 Expert KG pipeline v1 | 2.5 | M1, M2, M3 | 👤 review 100-edge sample |
| M6 Expected subgraphs + student-answer extraction | 1.5 | M4, M5 | 👤 spot checks |
| M7 Alignment, diagnosis, evaluation, baselines, ablations | 2 | M3, M4, M6 | low |
| M8 (stretch) Misconception layer, feedback generation, Mohler | 1.5–2 | M7 | 👤 curate misconceptions |
| M9 Demo + results pack | 1 | M7 | low |
| **Total** | **~14–16** | | |

Critical path: **M3 and M4**, because both depend on your annotation time. Start M4's labelling runs while you annotate M3.

---

## M0 — Repo scaffold, tooling, LLM wrapper (0.5 wk)

**Goal:** a runnable, tested skeleton. Nothing calls the network in tests.

**Tasks**
1. `git init`; `uv init` with Python 3.11; package `cumap` under `src/cumap/`.
2. Dependencies: `pydantic>=2`, `typer`, `pyyaml`, `python-dotenv`, `pandas`, `pyarrow`, `datasets`, `networkx`, `spacy` (+ `en_core_web_sm`), `scikit-learn`, `sentence-transformers`, `openai`, `tenacity`, `diskcache`, `streamlit`, `pyvis`, `rich`. Dev: `pytest`, `ruff`.
3. `configs/default.yaml`: paths, model names (read from env with defaults), reasoning effort per task, thresholds, pilot question IDs (empty until M1), random seed.
4. `src/cumap/config.py`: load YAML + `.env`; a single `Settings` object.
5. `src/cumap/llm/`:
   - `client.py`: `LLMClient.parse(task: str, prompt_version: str, messages, schema: type[BaseModel], model_tier: "strong"|"bulk") -> ParsedResult` using `client.responses.parse(model=..., input=..., text_format=schema)` → `response.output_parsed`. Retries with `tenacity` on rate-limit and 5xx errors. Returns the parsed object plus metadata (model, prompt_version, input_hash, usage tokens, latency, run_id).
   - `cache.py`: `diskcache` keyed by sha256(model + prompt_version + canonical JSON of messages + schema name). A cache hit must not call the API.
   - `mock.py`: backend selected by `CUMAP_LLM_BACKEND=mock` that returns fixture JSON from `tests/fixtures/llm/<task>/*.json`.
   - `prompts.py`: load `prompts/<task>/<version>.md` (front-matter: task, version, schema, notes), with simple `{placeholders}`.
   - Log every call as a line in `data/logs/llm_calls.jsonl` (no prompt text, only hashes and metadata).
6. `src/cumap/cli.py` (Typer) with command groups: `data`, `textbook`, `gold`, `labels`, `kg`, `student`, `diagnose`, `eval`, `app`. Stubs are fine for now.
7. Every LLM-calling command supports `--limit N` and `--dry-run` (prints the planned call count and a rough token estimate, then exits).
8. `.gitignore`: `.env`, `data/raw/`, `data/cache/`, `data/logs/`, `data/processed/`, `.venv/`. **Do not ignore `data/gold/`**: it is committed.
9. `README.md`: setup (uv sync, `.env`, spaCy model download), one-line description of each CLI group.

**Outputs:** `pyproject.toml`, `src/cumap/{config.py,cli.py,llm/*}`, `configs/default.yaml`, `tests/test_llm_client.py`, `tests/test_config.py`.

**Acceptance checks**
- `uv run pytest` passes with no network and no API key.
- `uv run cumap --help` lists all command groups.
- A test shows: mock parse returns a validated Pydantic object; a second identical call is a cache hit (0 backend calls).
- `uv run ruff check .` is clean.

---

## M1 — Data ingestion, textbook parsing, EDA, coverage map (1 wk)

**Goal:** all raw data local and typed; the textbook split into sections; know which SAF questions the book covers.

**Tasks**
1. `cumap data download-saf` → `data/raw/saf/<split>.parquet`. Record the actual split names and row counts in `docs/PROGRESS.md`.
2. **Stable IDs:** `question_id = "q_" + sha1(normalised question text)[:8]`; `answer_id = "a_" + sha1(question_id + provided_answer)[:10]`. Save `data/interim/saf_questions.csv` (question_id, question, reference_answer, n answers per split) and `data/interim/saf_answers.parquet`. Report how many distinct questions exist and whether near-duplicate "variants" of a question exist (the paper says 22 questions; the dataset card says 26 variants).
3. `cumap textbook fetch` → shallow clone of `SystemsApproach/book` into `data/raw/textbook/pd6/` at a pinned commit (store the hash in `configs/default.yaml`).
4. `cumap textbook parse` → `data/interim/textbook_sections.jsonl` with one `Section` per lowest-level heading:
   `section_id` (e.g. `6.3` or a slug), `chapter_num`, `chapter_title`, `section_title`, `heading_path`, `order_index` (book order from the `index.rst` toctrees), `source_file`, `line_start`, `line_end`, `text` (plain text, code/figures removed), `emphasized_terms` (from `**bold**`, `*italic*`, `:term:` roles), `word_count`.
   Try `docutils` with unknown Sphinx directives registered as pass-through. If that proves brittle, fall back to a heading-regex parser. Keep whichever is robust and log the choice in `DECISIONS.md`.
5. EDA report `reports/m1_eda_saf.md`: per question, the count by split, label distribution and score histogram; answer and feedback length stats; 3 example (answer, feedback) pairs per label. Generate it from a script, not a notebook.
6. Coverage suggestions: embed each question + reference answer and each section (`sentence-transformers`, model name in config). For each question, write the top-5 sections with scores to `data/interim/suggestions/question_section_map.csv`, plus an LLM-generated one-line coverage guess (full / partial / none) and a reason.
7. 👤 **HUMAN:** confirm coverage per question and pick **5 pilot questions** with *full* coverage and a spread of labels. Suggested candidates if covered: TCP congestion-control phases; piggybacking in sliding window; CSMA/CD collision-domain diameter; transparent bridges / spanning tree; IPv6 extension headers; binary vs Manchester encoding; reverse-path forwarding. The human saves `data/gold/question_section_map.csv` and puts the pilot IDs in `configs/default.yaml`.

**Acceptance checks**
- Row counts match the dataset card (±0) and splits are stored separately.
- Every chapter parses; no section has empty text except intro stubs; `order_index` is strictly increasing in book order.
- Unit tests for the ID functions (stable across runs) and the parser (on a small `.rst` fixture).
- `reports/m1_eda_saf.md` exists; coverage suggestions exist for every question.

---

## M2 — Schemas & relation registry (0.5 wk)

**Goal:** Pydantic models that follow `ARCHITECTURE.md` §4 exactly, plus a validated relation registry.

**Tasks**
1. `src/cumap/schemas/`:
   - `textbook.py`: `Section`
   - `saf.py`: `Question`, `Answer`
   - `nodes.py`: `Concept`, `ConceptMention`
   - `relations.py`: `RelationType`, `RelationRegistry` (loads `configs/relations_v0.yaml`)
   - `edges.py`: `Evidence`, `QuestionLink`, `ConfusableRef`, `Validation`, `ExpertEdge`
   - `student.py`: `StudentEdge`, `Alignment`
   - `labels.py`: `Proposition`, `PropositionLabel`, `ExtraError`, `SilverAnswerLabel`
   - `diagnosis.py`: `DiagnosisRecord`
   - `misconceptions.py`: `Misconception`
2. Enums exactly as in `ARCHITECTURE.md` (polarity, modality, layer, match_type, verdict, stance, status, role, node_type).
3. **LLM-facing schemas** are separate, flat versions (all fields required, optional fields as `X | None`, no defaults). Structured Outputs requires this. Converters map them to the full internal models.
4. Registry logic in `relations.py`:
   - `normalise(edge)`: puts symmetric relations in canonical order and rewrites an inverse relation to its forward form.
   - `is_reversal(a, b)`, `conflicts(a, b)`, `compatible(a, b) -> "full" | "partial" | None`
   - `check_types(edge, concept_types) -> list[str]`: domain/range violations.
5. `cumap gold validate`: validates every YAML/JSON file under `data/gold/` against the schemas and the registry. It also checks that every `Evidence.quote` is an exact substring (after whitespace normalisation) of the referenced section text or answer text.
6. 👤 **HUMAN:** review `configs/relations_v0.yaml` (the draft is provided) and approve or edit it.

**Acceptance checks**
- Round-trip tests (model → JSON → model) for every schema.
- Registry tests:
  - reversing a symmetric relation is *not* a reversal;
  - `increases`/`decreases` conflict;
  - `triggers`/`causes` are partially compatible;
  - an `is_a` cycle is detected.
- `cumap gold validate` passes on the fixtures and fails with readable messages on broken fixtures.

---

## M2.1 — CR-001: registry v1 migration (applied 2026-09-28, mid-M3)

**Goal:** apply change request CR-001 (`docs/change-requests/CR-001-relations-v1.md`; rationale in `docs/research/relation-mapping-research.md`) — relation registry v1 (16 relations, 6 families + pedagogical, each with a template/examples/near-misses), core-edge qualifiers (`part_type`, `dimension`, `surface_phrase`, `relation_family`, `registry_version`), the `ChainLink` reasoning layer, a version-aware validator, a gold migration tool, and LLM tiers/escalation. `relations_v0.yaml` stays loadable; nothing already in `data/gold/` is touched without the human's say-so.

**Steps and stop points** (one commit per step, prefix `CR-001:`):
1. Registry v1 (`schemas/relations.py`, `configs/relations_v1.yaml`; v1-only fields optional so v0 files still load).
2. Schema changes (core-edge qualifiers, `ChainLink`/`ChainLinkAlignment`, extended match types, `DiagnosisRecord` additions).
3. Version-aware validator (`cumap gold validate --registry v1`; missing `registry_version` = v0).
4. Gold migration tool (`cumap gold migrate-v1`, proposes v1 upgrades under `data/interim/suggestions/migrations/v1/`, never writes to `data/gold/`). **⛔ STOP 1:** human reviews `reports/migration_v1.md`.
5. M3 tooling: gold editor v1 fields + chain-links panel; `suggest-expert`/`suggest-student` switched to v2 prompts; relation-agreement sampler (`cumap gold sample-relation-items`) + scorer (`cumap eval relation-agreement`, Cohen's κ); mismatch report extended. **⛔ STOP 2:** human confirms the agreement sheets.
6. LLM client tiers (`strong`=`gpt-6-sol`, `bulk`=`gpt-6-luna`, `ceiling`=`gpt-6-astra`, opt-in only) and escalation (bulk → strong on schema error / low confidence / failed evidence check).
7. Docs (this update).
8. Acceptance checks.

**Acceptance checks**
- All tests pass with no network/key; `ruff check` clean.
- `cumap gold validate` passes on fixtures for both v0 and v1 rules.
- `reports/migration_v1.md` exists; a test proves the migration tool never writes to `data/gold/`.
- Relation-agreement sheets exist (real run: 30 items on the pilot sections — short of the ≥48-item, 6-families-×-8 target; open decision for the human, see `docs/PROGRESS.md`).
- `docs/ARCHITECTURE.md`, `docs/BUILD_PLAN.md` (this file), `CLAUDE.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md` updated.

---

## M3 — Manual pilot gold (1.5 wk; mostly 👤 HUMAN, agent builds the tooling)

**Goal:** a small, trustworthy gold set that every later component is scored against. The agent must **never** write into `data/gold/`; it only writes suggestions to `data/interim/suggestions/`.

**🚫 Student-annotation half DEFERRED (2026-09-28, scope decision: expert KG only; see DECISIONS.md)** — tasks 2, 3 below, the `student_pilot` human task, and the relation-agreement test (superseded by CR-003 §6, also deferred). Expert-side annotation (task 1, and `expert_pilot`) stays in scope.

**Tasks (agent)**
1. `cumap gold suggest-expert --qid <id>`: from the covered sections, LLM-drafts an expert subgraph for the question (concepts + edges with evidence quotes, polarity, modality, conditions, criticality, chain IDs). Output is YAML in `data/interim/suggestions/expert/<qid>.yaml`, with every item marked `source: model_suggestion`.
2. 🚫 *(deferred)* `cumap gold sample-answers`: picks 10 answers per pilot question from **train only**, stratified by label (≈3 Correct / 4 Partially correct / 3 Incorrect), with a fixed seed. Writes `data/interim/pilot_answers.csv`.
3. 🚫 *(deferred)* `cumap gold suggest-student --answer-id <id>`: drafts a student graph (edges with `evidence_span` offsets) linked to the question's expert concepts. Output goes to `data/interim/suggestions/student/<answer_id>.yaml`.
4. Streamlit `app/gold_editor.py` (or clearly templated YAML plus the validator, whichever is faster): shows the source text or answer side by side with the draft; supports accept / edit / delete / add; the human saves to `data/gold/...`. (CR-001: also has `part_type`/`dimension`/`surface_phrase` fields, a family-grouped relation dropdown, and a chain-links panel. Expert-graph mode stays in scope; student-graph mode is built but unused while student annotation is deferred.)
5. `cumap gold mismatch-report`: from the gold student graphs and the gold expert edges, tabulates `match_type` frequencies → `reports/m3_mismatch_types.md`. (CR-001: also tabulates `family_match`/`part_type_error` and chain-link types; reports agreement at both family and relation level. 🚫 *deferred* — needs student graphs.)
6. 🚫 *(deferred — superseded by CR-003 §6, not just student-scope)* **(CR-001) Relation-set agreement test:** `cumap gold sample-relation-items --n 100 --seed <seed>` picks textbook text mentioning ≥2 pilot-gold concepts, stratified across the 6 semantic families, and writes blank `annotator_A.csv`/`annotator_B.csv` sheets (never pre-filled). `cumap eval relation-agreement` scores the two completed sheets: Cohen's κ at relation and family level, direction agreement, per-relation κ, and >20%-confusion pairs, with a merge/split recommendation for the human to decide. Real run produced 30/100 items (short of the ≥48 target) before being deferred — see `DECISIONS.md`.
7. **(CR-001) Chain-link annotation:** the gold editor's chain-links panel lets the human link two edges with a type (cause/purpose/condition/sequence/contrast) and a connective. Expert-graph chain links stay in scope; student-graph chain links are deferred with the rest of student annotation.

**Tasks (👤 HUMAN)**
- Finalise `data/gold/expert_pilot/<qid>.yaml` for the 5 pilot questions (target ≥ 8 edges each, all with textbook evidence).
- 🚫 *(deferred)* Finalise `data/gold/student_pilot/<answer_id>.yaml` for the 50 sampled answers, including a `match_type` per student edge and the list of missing expected edges.
- Note any schema problems → the agent updates the schema and `DECISIONS.md`.
- 🚫 *(deferred)* **(CR-001)** Two annotators independently fill in the relation-agreement sheets and save them to `data/gold/relation_agreement/`.

**Acceptance checks**
- `cumap gold validate` passes on all gold files.
- 5 expert subgraphs exist. 🚫 *(deferred)* 50 student graphs exist; the mismatch-type report exists.
- Schema changes are logged in `DECISIONS.md`.
- 🚫 *(deferred)* **(CR-001)** The relation-agreement report exists (`reports/m3_relation_agreement.md`) and any merge/split decisions are logged in `DECISIONS.md`.

---

## M4 — Silver relation-level labels from SAF feedback (1.5 wk) — 🚫 DEFERRED (2026-09-28, scope decision: expert KG only; see DECISIONS.md)

**Goal:** turn SAF's human feedback into per-proposition labels (expressed / missing / contradicted), which separate *incomplete* from *contradictory* answers.

**Tasks**
1. `cumap labels propositions` (strong model): split each question's reference answer into atomic `Proposition`s. Each has `prop_id`, `text`, an optional triple (source, relation, target, polarity, conditions), `criticality` (core / supporting) and `weight`. The weights must sum to 1 per question; use SAF score steps as a hint. Output: `data/interim/suggestions/propositions.jsonl`.
   👤 **HUMAN:** review all questions' propositions (~22–26 questions, quick) and save `data/gold/propositions.jsonl`.
2. `cumap labels from-feedback` (bulk model): for every answer in every split, label each proposition `expressed | missing | contradicted | unclear`. Include `answer_quote` and `feedback_quote` (both must be verified substrings; failures become `unclear` and are logged). Also list `extra_errors` (wrong claims not covered by any proposition). Output: `data/processed/silver/labels_<run_id>.jsonl`.
   **Note:** the feedback is privileged information. The *diagnosis system never sees it*; only the labeller does.
3. Derived answer label: `contradictory` if any proposition is contradicted or there is any extra error; else `incomplete` if any core proposition is missing; else `correct`. Store it as `SilverAnswerLabel`.
4. Streamlit `app/label_verifier.py`: shows question, answer, feedback, and each proposition's predicted label; the human marks agree / change. Sample **150–200 answers** stratified by question × SAF label, **including items from both test splits** (these become the primary evaluation set). Save to `data/gold/verified_labels.jsonl`.
5. `cumap eval silver-agreement` → `reports/m4_silver_labels.md`:
   - Cohen's κ (proposition level) and macro-F1 (answer level) between the model labels and your labels;
   - confusion matrices;
   - consistency with SAF: share of `Correct` answers with no missing core proposition, and correlation of `1 − weighted missing/contradicted` with the SAF score.

**Acceptance checks**
- Target κ ≥ 0.6 on proposition labels (report the value either way). If it's below 0.6, revise the prompt (new version) on train/validation and rerun.
- The verified set covers every pilot question and both test splits.
- Results in `reports/m4_silver_labels.md`.

---

## M5 — Expert KG pipeline v1 (2.5 wk)

**Goal:** textbook → validated expert KG, chapter by chapter, with cross-chapter linking.

Run first on the chapters covering the pilot questions, then on the whole book.

**Tasks**
1. `textbook/stats.py` (FACE-style signals, no LLM):
   - spaCy noun-chunk candidates of 1–4 tokens with stop-modifiers removed (e.g. "such", "many", "certain");
   - frequency per section and across the book; tf-idf;
   - flags for `in_heading` and `emphasized`.
   Saved per section as `data/processed/candidates/<section_id>.json`.
2. `expert_kg/concepts.py` (strong model, prompt `concept_extraction/v1`), run per section. Inputs: section text, heading path, candidate list with stats, and the **top-k existing concepts retrieved from the global registry** (by embedding). Outputs `ConceptMention`s: canonical name, aliases, node_type, short definition in the book's words, `role` (defined / used / mentioned), evidence quote. Then run a **gleaning pass** ("list concepts you missed") once.
3. `expert_kg/canonicalize.py`: for each new mention, retrieve the top-5 similar existing concepts (name + definition embedding). If the similarity is above a threshold, the LLM decides `same | broader | narrower | different`. `same` → merge (add alias and mention); `broader`/`narrower` → propose an `is_a` edge; `different` → create a new concept.
4. **(CR-001) `expert_kg/relations.py` relation extraction, four passes** (`ARCHITECTURE.md` §6), not one prompt:
   - (a) Stage A: candidate concept pairs + supporting evidence quote (per section, from the concepts + earlier concepts mentioned in this section);
   - (b) Stage B: **family-first multiple-choice verification** via `registry.choice_set(x, y, families=...)` — filled templates, the reversed template for directional relations, `NO_RELATION`, `OTHER`;
   - (c) a separate **qualifier pass**: polarity, modality, conditions, `part_type`/`dimension`/`surface_phrase` (tested on a small negation/hedge fixture set — this pass exists because a single extraction pass tends to miss negated cases);
   - (d) a **chain-link pass**: given two accepted edges, ask whether the text connects them with a reason and what type;
   - (e) an **`other`-relation review report** each run — logged for schema review, clustered periodically to decide whether a new registry relation is warranted.
5. Cross-chapter prerequisite links: concept *defined* in section A and *used* in a later section B → `prerequisite_of` candidate (A's concept → the concept B introduces), with confidence. **Do not** derive prerequisites from book order alone.
6. `expert_kg/hierarchy.py`: for new concepts without an `is_a`/`part_of` parent, retrieve the top-5 candidate parents and let the LLM pick one or `none`.
7. `expert_kg/checks.py`:
   - evidence quote is a substring of the section text (reject if not);
   - domain/range types;
   - no cycles in `is_a`, `part_of`, `prerequisite_of`;
   - symmetric normalisation;
   - transitive reduction for `is_a`/`prerequisite_of`;
   - orphan report.
   Rejected items go to `data/processed/kg/<run_id>/rejected.jsonl` with a reason.
8. `graph/store.py`: save and load a KG as `nodes.jsonl` + `edges.jsonl` + `chain_links.jsonl` + `manifest.json` (run_id, commit, prompt versions, models, counts, cost, **escalation rate and cost split by tier** — CR-001 §8.2). Load into NetworkX.
9. Streamlit `app/review_app.py`: review a random sample of edges (accept / edit / reject → `validation.status`). Also add a `cumap kg export-neo4j` stub (CSV for `neo4j-admin import`), deferred.
10. **(CR-001)** Before the full run: `cumap eval model-bakeoff --tiers bulk,strong,ceiling --task <task> --items <gold subset>` — runs the same prompt on each tier over a gold subset, reports F1/κ/cost/latency; cheapest tier within 0.05 of the best score is the recommendation, human decides, logged in `DECISIONS.md`.

**Evaluation** (`reports/m5_expert_kg.md`)
- Concept recall/precision vs the concepts in `data/gold/expert_pilot/*` (lenient match: canonical or alias, or embedding ≥ threshold, then manual check).
- Edge precision on a **100-edge 👤 HUMAN-reviewed** stratified sample.
- Evidence-substring pass rate; counts by relation type, layer and node type; cost and tokens.
- **(CR-001)** Ontology conformance rate (domain/range respected), unsupported-by-text rate, direction accuracy, polarity accuracy — reported separately, not folded into one aggregate score.

**Acceptance checks (targets)**
- Evidence-substring pass rate ≥ 95% before rejection.
- Concept recall ≥ 0.8 on pilot gold.
- Edge precision ≥ 0.8 on the reviewed sample.
- Zero cycles in the taxonomy and prerequisite layers.
- The run is reproducible from cache: a re-run makes 0 API calls.

---

## M6 — Expected subgraphs + student-answer → graph (1.5 wk) — 🚫 DEFERRED (2026-09-28, scope decision: expert KG only; see DECISIONS.md)

**Tasks**
1. `cumap kg expected-subgraphs`: map each gold proposition (M4) to KG edges (the LLM proposes matches; exact rules first).
   - Matched edges get a `QuestionLink(role=required, weight=…, source=reference_answer)`.
   - A proposition with **no** KG edge becomes a question-specific expert edge (`source: reference_answer`, `layer: semantic`) and is logged as a **textbook coverage gap**.
   - Add `role=bonus` links for 1-hop KG edges relevant to the question.
   - Output: `data/processed/expected/<qid>.json`.
2. `student/extract.py` (bulk model, prompt `student_extraction/v1`). Inputs: question, answer, and the question's concept neighbourhood (expected subgraph + 1 hop) with aliases. Output: `StudentEdge`s linked to concept IDs (or `unlinked:<surface>`), with polarity, modality, conditions, `stance`, `evidence_span` (char offsets; verified), `extraction_confidence`, `link_confidence`, and **(CR-001)** `surface_phrase` plus proposed `ChainLink`s from connectives ("because", "so that", "if...then", ...).
3. `cumap student extract --split <name>`: runs over a split with caching.

**Acceptance checks** (`reports/m6_student_extraction.md`)
- Against the 50 gold student graphs: edge P/R/F1 (a triple matches after linking), polarity accuracy, link accuracy.
- Evidence-span verification pass rate ≥ 95%.
- Coverage-gap log produced; the number of reference propositions missing from the KG is reported.
- **(CR-001)** Chain-link P/R against the M3 gold chain links.

---

## M7 — Alignment, diagnosis, evaluation (2 wk) — 🚫 DEFERRED (2026-09-28, scope decision: expert KG only; see DECISIONS.md)

**Tasks**
1. `align/rules.py`: a deterministic `match_type` classifier (see `ARCHITECTURE.md` §4c), applied in this order:
   1. exact (same normalised triple, polarity, modality, conditions)
   2. paraphrase (compatible relation = full)
   3. `polarity_flip`
   4. `reversed` (directional relation, swapped endpoints)
   5. `substituted_concept` (one endpoint replaced by a concept in `confusable_with`, a sibling under the same parent, or a `contrasts_with` partner)
   6. `condition_error`
   7. `modality_error`
   8. `wrong_type` (conflicting relation, or a domain/range violation)
   9. `partial_relation` (right endpoints, compatible = partial)
   10. **(CR-001)** `family_match` (same endpoints/family, incompatible relation) and `part_type_error` (`part_of`, right endpoints, wrong `part_type`)
   11. `unsupported_extra` or `valid_extra` (the edge exists in the KG but isn't expected)
2. `align/judge.py`: an LLM fallback only for ambiguous cases (several candidates, or low link confidence). It returns match_type + rationale. Log whether the rule path or the LLM path decided.
3. **(CR-001)** Chain-link alignment: for each student `ChainLink`, compare against the matching expert `ChainLink` (if any) → `ChainLinkAlignment` with `match_type` (exact/wrong_link_type/reversed_link/missing_link/unsupported_link — `ARCHITECTURE.md` §4f).
4. `align/diagnose.py` → `DiagnosisRecord`: matched / missing / contradicted / extra, each weighted by criticality and weight; required coverage; broken chains; upstream gaps (a missing edge whose `depends_on_edges` are also missing); misconception candidates; derived labels (correct / incomplete / contradictory; SAF 3-way; predicted score = weighted required coverage minus a penalty for contradictions); **(CR-001)** `chain_link_results`, `reasoning_errors` (link_ids with `wrong_link_type`/`reversed_link`), `family_coverage` (weighted required-edge coverage per relation family).
   **Rules:** missing never produces "contradictory"; a misconception candidate needs an explicit contradiction of a core edge or a confusable substitution.
5. Baselines (`eval/baselines/`):
   - `sbert.py`: cosine(reference, answer) with thresholds tuned on train+validation;
   - `classifier.py`: fine-tuned DeBERTa-v3-base (or small) on the SAF 3-way label and on the silver 3-way label; train on train, early-stop on validation. MPS on an Apple-silicon Mac is fine; document a Colab option if it's too slow;
   - `llm_zero_shot.py`: same strong model, grading the answer from question + reference only (no feedback);
   - `embedding_only.py`: our pipeline but with edge matching by embedding similarity instead of rules.
6. Ablations (flags on the diagnoser): `--no-relation-types` (concept overlap only), `--no-polarity`, `--no-conditions`, `--no-criticality`, `--no-confusables`. **(CR-001)** Progressive relation-detail ablation to isolate which level drives diagnosis: concept overlap only → **+ family** → **+ fine relation** → **+ qualifiers** → **+ chain links**.
7. `cumap eval run` → `reports/m7_results.md`:
   - **Primary:** macro-F1 on correct / incomplete / contradictory against **human-verified labels** (M4 sample), reported separately for UA and UQ.
   - **Secondary:** against silver labels (all items); SAF 3-way macro-F1; score Spearman ρ and RMSE.
   - Edge-level (M3 gold): match_type accuracy.
   - McNemar tests vs the best baseline; confusion matrices; 20 annotated error cases.
   - **(CR-001)** `family_coverage` per relation family; reasoning-error counts; the progressive ablation table; single- vs two-threshold results if CR-002 has landed by then.

**Acceptance checks**
- The full pipeline runs end to end on UA and UQ from cache.
- The results tables and error analysis exist.
- Every number in the report can be traced to a run_id.

---

## M8 — Stretch: misconception layer, feedback generation, second domain (1.5–2 wk) — 🚫 DEFERRED (2026-09-28, scope decision: expert KG only; see DECISIONS.md)

1. `cumap misconceptions mine`: cluster contradicted propositions and extra errors across train + validation (embeddings + HDBSCAN or agglomerative clustering); the LLM names each cluster and proposes the expert edges it conflicts with. Output: `data/interim/suggestions/misconceptions.yaml`.
   👤 **HUMAN** curates → `data/gold/misconceptions_networking.yaml`. Wire into `confusable_with` / `contradicted_by_misconceptions`, then re-run M7 with and without the layer.
2. Feedback generation from `DiagnosisRecord` (the LLM gets only the diagnosis, not the reference feedback). Compare with SAF feedback using an LLM judge (coverage of the same issues) plus a 30-item 👤 human rating.
3. Second domain: *Open Data Structures* + Mohler. Re-run M1 (ingestion), M5 and M6/M7 in score mode, and compare RMSE with MitiGaTe's reported 0.762 on Mohler (note the protocol differences). Seed misconceptions from Karpierz & Wolfman 2014 and BDSI.

## M9 — Demo & results pack (1 wk)

1. `app/demo_app.py` (Streamlit + pyvis): pick a question and answer, then:
   - show the expected subgraph with the student graph overlaid (green = matched, grey = missing, red = contradicted, orange = extra);
   - highlight the evidence spans in the answer;
   - show a diagnosis panel with misconception candidates and generated feedback.
2. `reports/` → final tables and figures for the report; `docs/RESULTS.md` summarises them with run_ids.
3. Optional: Neo4j export + Browser screenshots.

---

## Cost & safety rails (all milestones)

- Always run `--dry-run`, then `--limit 20`, then the full split.
- Use the bulk tier (`gpt-6-luna`) for per-answer tasks (M4 labelling, M6 extraction) and the strong tier (`gpt-6-sol`, CR-001) for KG building, propositions and judging. The `ceiling` tier (`gpt-6-astra`) is opt-in only — a model bake-off, never a default.
- **(CR-001)** Run a model bake-off (`cumap eval model-bakeoff`) before the M4 and M5 full runs; log the tier decision in `DECISIONS.md`. Bulk-tier calls escalate to strong once on a schema error, low confidence, or a failed evidence check — the run manifest reports the escalation rate and the cost split by tier.
- Record tokens and estimated cost per run in the manifest; stop and ask if a single command would exceed the budget in `configs/default.yaml` (`max_usd_per_command`, default 5). Cost estimates use Sol/Luna list prices (placeholder — unconfirmed, see `DECISIONS.md`); `--batch` estimates apply `assumed_batch_discount`.
- Cached results are the source of truth for reproducibility; never delete `data/cache/` without asking.
