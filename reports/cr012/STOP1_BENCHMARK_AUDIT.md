# CR-012 STOP 1 - repository + benchmark reconciliation ($0, no paid call)

Branch `cr-012-end-to-end-evaluation` from `main` (`5fda330`, CR-011 merged and pushed). Machine-readable facts: `reports/cr012/dataset_manifest.json`.

## 1. Repository reconciliation

| Check | Evidence | Result |
|---|---|---|
| Final CR-010 architecture | `docs/DECISIONS.md` 2026-10-08, tag `cr-010-complete` | `DUAL_LAYER`: the semantic Expert-KG layer is unchanged; the eRST-compatible graph is candidate-pair routing only |
| Final CR-011 state | tag `cr-011-complete` | `closed_no_production_change`; STOP 4 / STOP 5 not run; held-out sets sealed |
| CR-011 handoff | `reports/cr011_sleep/CR012_EVAL_HANDOFF.json` (sha256 `64a050ec...`) | present; `python -m cumap.sleep.closure validate`: 0 problems; `sleep_adopted = false`, `post_sleep_state = no_op_same_as_pre_sleep`, identity id map |
| Frozen production baseline | handoff `pre_sleep_snapshot` | run `slice3_c2`, checkpoint sha256 `54eb0f194ca0...`, 28 files hashed; this IS the final production graph (CR-011 changed nothing) |
| Production concept stage | `configs/concept_gvp.yaml` (frozen-1), `prompts/concept_generator/v4`, `concept_backfill/v1` | hashes in the handoff |
| Production canonicalisation | `prompts/canonicalize/v2`, `configs/term_lexicon.yaml` v0.3, `alias_rules.yaml` v0.1-draft, `canonical_overrides.yaml` | hashes in the handoff |
| Production relation stage | registry `relations_v1.3`, prompts `relation_family v3`, `relation_choice v4`, `relation_qualifiers v4` | hashes in the handoff |
| Sleep configs | `configs/sleep_consolidation_v1.yaml` | not part of the evaluated workflow (not adopted) |
| Models / tiers / prices | `configs/default.yaml` | strong gpt-6-sol $2.00/$10.00 per 1M; bulk gpt-6-luna $0.10/$0.50 |
| Tests | full suite | 639 pass, ruff clean |

**Consequence for RQ4 (CR-011 contribution):** CR-011 adopted no transformation, so there is no pre/post pair to score. Per Research, CR-012 reports "no pre/post sleep accuracy experiment exists for the production pipeline" and does not claim a zero delta. The pre/post comparison (`sleep_before_after.md`, STOP 5 of CR-012) therefore has no experiment to run and is recorded as not applicable; canonicalisation error attribution comes from the oracle matrix (E2).

## 2. SciNLP audit (exact release)

| Item | Finding |
|---|---|
| Source / commit | `https://github.com/AKADDC/SciNLP`, `main` at `e78342be517e` ("readme"); previous commit `ed3e588` "data_refine" |
| Files | `Dataset/train.json` (sha256 `b40acb3b...`), `dev.json` (`3912609b...`), `test.json` (`4accdc6a...`), `KG_triples.txt` (model-generated, 1,089,239 lines, NOT gold), `README.md` |
| Format | JSON lines, one document per line: `doc_key`, `sentences` (pre-tokenised), `ner` ([start, end, type] per sentence, document-level token offsets), `relations` ([s1, e1, s2, e2, type]). **Raw text is not provided**; the adapter must detokenise |
| Documents | 60 (train 51 / dev 6 / test **3**); no document overlap between splits |
| Entities | 6,429 (train 4,993 / dev 671 / test 765) |
| Relations | 1,649 (train 1,175 / dev 179 / test 295) |
| Sentences / tokens | 13,214 / 338,773 (test 765 sentences, 20,468 tokens) |
| Entity types (repo) | `method`, `task`, `metric`, `dataset` (test: method 474, task 151, dataset 86, metric 54) |
| Relation types (repo, 11) | UsedFor, MeasuredBy, compareWith, enhancedBy, partOf, subtaskOf, similarWith, trainedWith, subclassOf, evaluatedBy, evaluatedOn. Symmetric per the paper: compareWith, similarWith. Observed domain/range matches the paper's definitions in >= 97% of instances (for example MeasuredBy method->metric 213/213, UsedFor method->task 317/319) |
| Licence | CC BY-NC 4.0, non-commercial academic research only (follows the ACL OCL Corpus policy). Raw files stay in gitignored `data/raw/` and are not redistributed |
| Official scorer | **None in the repository.** README reports PURE / PL-Marker / HGERE numbers (NER, Rel, Rel+, RE); the paper defines them in prose (strict span + type; Rel = subject span + object span + relation type; Rel+ also needs entity types; RE = relation classification with gold entities) |
| Paper vs repository | Paper v3: 60 papers, **7,072 entities, 1,826 relations**, split 8:1:1 (about 48/6/6), entity type "Model". Repository: 60 papers, **6,429 entities, 1,649 relations**, split 51/6/3, entity type `method`. The repository (after a `data_refine` commit) is what is frozen and evaluated; both are reported |
| Coreference / identity | **Not annotated.** Gold relations link mention spans; there are no canonical-concept clusters (the paper applies abbreviation / full-form normalisation as post-processing only) |
| Document text | clean tokenised ACL long papers, first pages only (doc keys `...-1-9.grobid`); about half of the sentences carry a gold entity |
| Published baselines | supervised PURE / PL-Marker / HGERE trained on SciNLP train; a different setting from the frozen few-shot workflow, and the scoring definition cannot be verified identical, so no leaderboard claim (CR section 17) |

Optional benchmarks (SciERC, SciER, OSKGC / Text2KGBench): not enabled, not downloaded.

## 3. Benchmark isolation

- Before this audit no SciNLP, SciERC, SciER, OSKGC or Text2KGBench file existed in the repository; searches of `src/`, `configs/`, `prompts/`, `tests/` and `data/` find no such data, label, schema or example. Only design documents mention SciERC as a possible diagnostic (CR-005 planning text).
- The CR-011 isolation clause (20A) holds: CR-011 never read any of them (its work used P&D only).
- SciNLP test doc keys frozen in the manifest: `2021.acl-long.353`, `2024.acl-long.108-1-9.grobid`, `P17-1058.grobid`. Test text must never enter prompts, few-shot banks, lexicon, cues or guards.
- P&D-E2E held-out candidates: chapters 4-9 (37 sections, 139,604 words), none run by any CR-005..011 experiment (all runs and tuning used chapters 1-3). The 2 pilot sections must come from the already-developed chapters 1-3 (spec). The 6-8 held-out sections are frozen at STOP 2 before any final CUM prediction is viewed.

## 4. Cost preflight (repository-specific, from the logged slice3_c2 spend)

Measured unit rates (non-cached, strong tier for canonicalisation and relations, bulk for concepts): concepts + backfill about $0.008 per 1k words; canonicalisation about $0.032 per 1k words; relation classification $0.0083 per pair; production pair budget 1,100 pairs for the 77.3k-word slice = 14.2 pairs per 1k words ($0.118 per 1k words). Full E0 workflow about **$0.16 per 1k words**.

| stage | volume | per-run estimate | planning limit | note |
|---|---|---:|---:|---|
| pilot (2 P&D sections about 6k words + 2 SciNLP dev docs about 9k words, E0 plus partial oracles) | about 15k words | $4-6 | <= $5 | |
| held-out P&D (6-8 sections, about 22-30k words), E0-E4 | | $12-19 | | E3/E4 add classification of every gold pair (about 400-600 pairs) |
| held-out SciNLP test (3 docs, 20.5k tokens, about 17k words), E0-E4 | | $8-13 | | E4 alone: 295 gold pairs = $2.4 |
| held-out total | | **$18-32** (shared-cache floor to no-sharing ceiling) | <= $15 | |
| stability (3 independent E0 runs x [2 SciNLP docs + 2 P&D sections about 18.5k words]) | 55k words | **about $9** (cache must not be shared across the independent repeats) | <= $8 | |
| **all stages** | | **about $31-47** | warning $20, hard cap $30 | |

The ceiling and even the floor reach or exceed the $30 hard cap. The estimates will be replaced by measured per-1k-word cost from the STOP 3 rehearsal before STOP 4, but STOP 4 is a single frozen run, so the cap must be settled first.

## 5. Facts that complicate the approved specification: RESEARCH DECISION REQUIRED

**D1 - the SciNLP test split has 3 documents.** The spec says to bootstrap SciNLP by document. With n = 3 the document bootstrap has only 10 distinct resamples; a 95% interval is degenerate. (The paper's own 8:1:1 split would have been about 6 test documents; the released split is 51/6/3.) Options: (a) report per-document results and a document-level bootstrap with an explicit "n = 3, not informative" label; (b) bootstrap by a finer natural cluster inside documents (for example fixed-size section blocks, as P&D uses sections) and say so; (c) evaluate on dev + test (9 documents) with dev excluded from any tuning (needs the dev tuning claim relaxed); (d) a Research-set alternative.

**D2 - strict E2E semantics for a benchmark without identity gold.** SciNLP relations link mention spans and has no canonical clusters. "Correct source canonical concept" and the E2 oracle ("where benchmark gold supports it") are undefined there. Options: (a) mention-level strict scoring: a final edge is correct if some mention of its source node matches a gold subject span, some mention of its target matches a gold object span, and relation, direction and types agree; E2 not supported on SciNLP; (b) document-level triple scoring over normalised surface forms; (c) Research-set rule. Also needed: the exact "official-compatible" definition since no scorer is released (proposal: PURE-style strict Rel+ at span level, symmetric relations orientation-free).

**D3 - pair-selection budget for evaluation units.** Production fixed a global budget of 1,100 pairs for one 77k-word slice. For new documents the budget rule is undefined. Proposal: the production ratio of 14.2 pairs per 1k words, fixed before STOP 3 and applied identically to P&D and SciNLP (no test-dependent budget). This is a configuration choice that changes recall.

**D4 - cost cap** (section 4): approve a cap above $30 for the full plan, or name what to cut (stability repeats, E3/E4 on one benchmark, fewer held-out sections), or accept a staged plan that stops at the cap with the remaining stages reported as not run.

## 6. Implementation-only points (no decision needed)

- The adapter detokenises SciNLP tokens into text with a token-offset map; scoring converts predicted spans back to token offsets.
- The pipeline receives a frozen SciNLP registry: 4 entity types, 11 relations with the paper's domain/range, symmetric set {compareWith, similarWith}, names exactly as in the data (`method`, `MeasuredBy`...); no translation into networking labels. Definitions come from the paper.
- Existing infrastructure to reuse: `LLMClient` cache and budgets, evidence-quote verification, `RelationRegistry`, the pair-recall denominator already implemented in `cumap.cr010.pair_pools.pair_recall`, bootstrap helpers in `cumap.eval.stats`.

## 7. STOP 1 decision

- [x] **PASS (2026-10-09, Research rulings D1-D4 recorded in `docs/DECISIONS.md` and `configs/cr012_e2e_eval.yaml`)**
- [ ] BLOCKED (path / implementation only)
- [ ] RESEARCH DECISION REQUIRED (resolved) on D1, D2, D3, D4. Nothing was run; no benchmark data entered any prompt; no paid call. STOP 2 starts after the answers.
