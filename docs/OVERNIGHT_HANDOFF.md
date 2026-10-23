# Overnight handoff (2026-10-22 to 2026-10-23)

Written for: the project owner, and the execution sessions that pick the work up (§0). This file reports state and queued work; writing it changed no code, config or data. Nothing under `data/gold/` was touched.

## 0. Instructions for the executing agent (read this first)

Written for: a Claude Sonnet session that executes this handoff without the owner present. Owner decisions for these sessions, 2026-10-23:
- merges are allowed after tests pass;
- the total budget is **$20**;
- the recommended defaults in §0.4 are adopted;
- the executing Sonnet session may **draft** new prompt and registry versions as new files, but stops for owner review before any run that uses them (§0.5).

### 0.1 Before every task

0. **First, before any task (once):** commit this file as it is now, on `main`, so the starting instructions are versioned. Stage it by path and nothing else:
   ```
   git switch main
   git add docs/OVERNIGHT_HANDOFF.md
   git commit -m "Overnight handoff: execution instructions for the Sonnet session (owner-approved)"
   ```
   Check `git show --stat HEAD` lists only `docs/OVERNIGHT_HANDOFF.md`.

1. **Read the project rules:** `CLAUDE.md` (the non-negotiable rules override this file if they ever conflict) and the task's own section below. Read only the code files the task names, plus their tests.
2. **Check the working tree:** `git branch --show-current` must be `main`, and `git status --short` must show no modified tracked files. Untracked files are expected (§1) and must never be committed.
3. **Record the owner's execution rules in `docs/DECISIONS.md`** once, as part of task T1 (on its branch, not directly on `main`):

   > 2026-10-23 · owner: execution sessions may merge a CR into `main` with `--no-ff` after `uv run pytest` and `uv run ruff check .` pass; total API budget for these sessions $20; the defaults in docs/OVERNIGHT_HANDOFF.md §0.4 are owner-approved; the session may draft new prompt and registry versions as new files, and no run uses a draft before the owner reviews it.

### 0.2 How to do one task

1. **Branch:** `git switch -c <branch> main`, using the branch name in §0.3.
2. **Build exactly what the section says**, nothing more. Every behaviour change goes behind a switch whose default keeps today's behaviour (`legacy` / `false` / off) unless the section says otherwise. Older runs must replay byte-identically.
3. **Tests:** add the tests the section lists. Tests never touch the network: `CUMAP_LLM_BACKEND=mock`, fixtures in `tests/fixtures/`.
4. **Check:** `uv run pytest -q` and `uv run ruff check .`, then `uv run ruff format` on the files you changed. All must pass.
5. **Docs:**
   - a `DECISIONS.md` entry (date · decision · reason · alternatives);
   - a `PROGRESS.md` section with the numbers you verified;
   - any `ARCHITECTURE.md` / `CLAUDE.md` lines the section names.
6. **Commit:** stage files **by path** (`git add path/one path/two`). **Never** use `git add -A`, `git add .` or `git commit -a`: `data/gold/` and other untracked owner files must stay out. End the message with the attribution line the session's system instructions give.
7. **Merge:**
   ```
   git switch main
   git merge --no-ff <branch> -m "Merge CR-NNN: <one line>"
   git tag cr-NNN-complete
   ```
   Never push.
8. **Log:** add a row to the execution log (§0.6) with task, branch, merge commit, test count and spend. Commit the log change on the task's branch before merging, staging `docs/OVERNIGHT_HANDOFF.md` by path; fill in the merge commit in the next task's commit.

### 0.3 Task order

Do these in order. Tasks marked "after" need the earlier one merged first.

| # | Task | Section | Branch / CR | Cost | Notes |
|---|---|---|---|---|---|
| T1 | Docs/code mismatches 1, 2, 4 (comments and docstrings only); the §0.1 `DECISIONS.md` entry; D-6 | §4, §5 | `housekeeping-docs-sync` | $0 | no behaviour change; no CR number. This file is already committed by §0.1 step 0 |
| T2 | Remove backfill from new production runs (switch) | §6 | `cr-027-remove-backfill` (CR-027) | $0 | default per §0.4 D-1 |
| T3 | `same_concept` queue reader + standing lexicon intake sheet | §8 step 1, §9 | `cr-029-review-intake` (CR-029) | $0 | writes owner sheets to `data/interim/suggestions/`; the owner marks them later; does not block later tasks |
| T4 | Retire eRST in the docs | §13 | `cr-030-retire-erst` (CR-030) | $0 | docs only; CLAUDE.md rules 28 and 29 become historical notes (owner-approved) |
| T5 | Record the `IDX-P1` oracle ladder as a generated report | §16 "Related", Appendix A | `cr-031-oracle-ladder-idx` (CR-031) | $0 | acceptance numbers in Appendix A |
| T6 | Broader Hierarchy F1 (`HIER-T1`, `HIER-T1-SURF-R1`) + scoped SciNLP identity sheet | §15 | `cr-032-hierarchy-t1` (CR-032) | $0 | module `src/cumap/cr032/`, not `cr026_hier` (CR-026 is taken). Generate the sheet; the real-identity SciNLP figure waits for the owner's marks |
| T7 | SciNLP concept-level fact F1 (`FACT-C1-SURF-R1`) | §16 | `cr-033-fact-f1` (CR-033) | $0 | write the pre-registration into `DECISIONS.md` and commit it **before** computing anything on the test split; validate on train/dev first |
| T8 | Qualifier code checks only (part A of §10) | §10 changes 5 and 7 | `cr-034-qualifier-checks` (CR-034) | $0 | see §0.5: no new prompt versions. Switch `qualifier_checks: off/v1`, default off. Add a $0 replay report on `slice3_c2` counting which edges each check would change |
| T9 | Identity resolver, deterministic part (U0-U4) + registry-search changes + merge-log fix (part A of §7) | §7 | `cr-035-identity-resolver-a` (CR-035) | $0 | see §0.5: U5 and the extension are deferred. Switch `identity_resolver: legacy/u1`, default `legacy`. With `u1`, a pair that U0-U4 cannot decide falls back to today's LLM path (adjudicator / canonicalize), so no new prompt is needed |
| T10 | Fold "verify and assemble" into classification; "save graph" export (`assembly: legacy/v2`) | §12 | `cr-036-save-graph` (CR-036), after T9 | $0 | until the CR-028 online index exists, `v2` still calls `slice_rerun.finish_concepts` |
| T11 | **Draft** the identity judge (U5): `prompts/identity_judge/v1.md` + its closed-choice schema, wired behind `identity_resolver: u1` with a `judge: off/v1` switch (default off) | §7 steps 3-4 | `cr-037-identity-judge-draft` (CR-037), after T9 | $0 | build from `prompts/rejected_link_adjudicator/v2.md`, adding `narrower` / `broader`. Static content first, per-item last. Mock-fixture tests only. **Stop:** the §7 step 8 measurement (about $3) waits for owner review of the prompt |
| T12 | **Draft** the qualifier and choice prompts (part B of §10): `prompts/relation_qualifiers/v6.md` (per-relation fields, evidence quote passed in, no `dimension`, no modality `never`), `prompts/relation_choice/v6.md` with a verbatim dimension quote, the per-relation qualifier schema, and registry **v1.5** with the qualifier definitions | §10 changes 1-4, 6 | `cr-038-qualifiers-draft` (CR-038), after T8 | $0 | v1.5 is built from **v1.3** (production), not v1.4 (not adopted), through a patch file in `configs/registry-patches/` like CR-024; say so in its header. Behind a switch, default off. **Stop:** the §10 measurement waits for owner review |
| T13 | **Draft** the misconception family: registry **v1.6** (= v1.5 + `misconception` family, layer `misconception`), `prompts/relation_family/v5.md` and `prompts/relation_choice/v7.md` that offer it (built on T12's v6), its closed-choice schema, and the code checks reusing `misconception.py` | §14 | `cr-039-misconception-family-draft` (CR-039), after T12 | $0 | switch `misconception_source: legacy/classification`, default `legacy`. Keep the $0 cue scan as a selection-priority signal (§14 mitigation). **Stop:** the §14 measurement waits for owner review |
| T14 | **Draft** wording for the six unreviewed v1.4 relations (`subtask_of`, `enhanced_by`, `measured_by`, `evaluated_by`, `evaluated_on`, `similar_to`): definitions, examples, near-misses | §3 item 4 | `cr-040-v14-review-draft` (CR-040) | $0 | **do not edit `configs/relations_v1.4.yaml`.** Write the proposed wording as an owner review sheet `docs/cr040/v14_relation_review.md` (current text beside proposed text, with the reason for each change). Adoption is an owner decision |

**Stop and leave for the owner** (do not start; do not draft):
- every **paid measurement** of a drafted prompt (§7 step 8, §10, §14): it waits for owner review of the draft;
- CR-028's online extension (§7 "Extension");
- Option C (§11);
- the evaluation review (§17);
- adopting registry v1.4, v1.5 or v1.6 as the production default;
- the CR-018 annotation (§3 item 1);
- the domain-matched pruner (§4);
- any rebuild or test-split run (§3 items 2, 2b);
- CR-022 Part B (§3 item 3).

**Where a section below differs from §0:** §0 wins. In particular:
- "stop for owner sign-off" before merging is replaced by §0.2 step 7;
- "after CR-028" in §12 means after T9 (CR-035, the deterministic part); the online bookkeeping is deferred, so `v2` keeps calling `finish_concepts`;
- every "measurement before adoption" that needs a paid run (§7 step 8, §10, §14) waits for the owner's review of the drafted prompt (T11-T13), and §7's online extension is deferred. Keep each switch at its default;
- CR numbers come from §0.3 (sections below may mention placeholder numbers).

### 0.4 Owner-approved defaults for the open items (2026-10-23)

| Id | Item | Default |
|---|---|---|
| D-1 | §6 CR-027 | a config switch `backfill: false` for new production runs; keep the code (not delete) |
| D-2 | §8 interim step | do it, combined with §9 into CR-029 |
| D-3 | §9 intake sheet | cap 40 rows per sheet; samples 5 (U5 narrower/broader/new) and 10 (deterministic-merge audit), seed recorded in the key file; the first sheet is built from `slice3_c2` only |
| D-4 | §10 negated edge without a negation cue | reject with reason `negation_without_cue`, logged; only when `qualifier_checks: v1` |
| D-5 | §7 `not_a_concept` on inputs B and C | a review flag; the node is kept |
| D-6 | §3 item 5, CR-023 | close without the paid comparison run: one `PROGRESS.md` line and one `DECISIONS.md` line in T1's branch |
| D-7 | everything else in §3 still marked "to confirm" | not executed; it stays an owner item |

### 0.5 What a task must not include

- **Drafts only.** New prompt and registry versions are allowed only in T11-T13, always as **new files**:
  - never edit an existing version;
  - every draft sits behind a switch whose default keeps today's behaviour;
  - a draft is tested with mock fixtures only;
  - no run, paid or not, uses a draft before the owner has reviewed it. List each draft in `PROGRESS.md` under "awaiting owner review".
  - T8 and T9 must not need a new prompt; if one turns out to be needed, leave that part for T11 / T12.
  - **Version numbers:** always take the next free number. Check with `ls prompts/<task>/` and `ls configs/relations_v*.yaml` before creating a file. On 2026-10-23 the latest were: `relation_family` v4, `relation_choice` v5, `relation_qualifiers` v5, registry v1.4; `prompts/identity_judge/` does not exist yet.
- **Never edit an existing prompt version** (rule 8), any file under `data/gold/` (rule 2), a frozen report or result file, or the frozen scorers (`cr012`, `cr017-1`, CR-019 variants). New scorers are new, named variants (rule 35).
- **No change to production defaults** except T2's backfill switch. New switches default to today's behaviour.
- **Never push.** Never force anything (`git push`, `--force`, `reset --hard` on `main`).

### 0.6 Budget, stopping and the execution log

- **Budget:** $20 in total across all execution sessions; nothing in T1-T10 needs a paid call.
  - If a paid call ever seems necessary: run `--dry-run` first, check the estimate fits the remaining budget and `max_usd_per_command` ($15 in `configs/default.yaml`), then `--limit 20`, then the full run (rule 7).
  - Record the spend in the log below.
  - Stop if the running total would pass $20.
- **Stop the task** (leave the branch unmerged, write the reason in `PROGRESS.md` and in the log, go on to the next task that doesn't depend on it) if any of these happen:
  - tests or ruff still fail after two honest attempts to fix;
  - a determinism gate does not reproduce the frozen numbers;
  - the task would need a file under `data/gold/`, a new prompt or registry version, or a change to a non-negotiable rule other than the ones this file names;
  - the code differs from what the section describes in a way that changes the plan.
- **Stop the whole session** if `main` stops passing tests after a merge. Revert that merge with `git revert -m 1 <merge>` and log it.

**Execution log** (append one row per task):

| Task | Branch | Merge commit / tag | Tests passed | Spend | Status / notes |
|---|---|---|---|---|---|
| T1 | housekeeping-docs-sync | (merge commit see git log) / no tag | 876 | $0 | merged; docstring/comment fixes, DECISIONS rules entry, D-6 |
| T2 | cr-027-remove-backfill | see git log / cr-027-complete | 879 | $0 | merged |
| T3 | cr-029-review-intake | see git log / cr-029-complete | 886 | $0 | merged; sheet data/interim/suggestions/lexicon_intake_slice3_c2.csv awaits owner marks |
| T4 | cr-030-retire-erst | see git log / cr-030-complete | 886 (unchanged, docs only) | $0 | merged |
| T5 | cr-031-oracle-ladder-idx | see git log / cr-031-complete | 889 | $0 | merged; reports/cr031/ generated, acceptance table reproduced |
| T6 | cr-032-hierarchy-t1 | see git log / cr-032-complete | 901 | $0 | merged; real-identity SciNLP figure awaits owner marks on scinlp_hier_identity_sheet.csv |
| T7 | cr-033-fact-f1 | see git log / cr-033-complete | 906 | $0 | merged; pre-registration commit 6c1d7a1 precedes the test run |
| T8 | cr-034-qualifier-checks | see git log / cr-034-complete | 924 | $0 | merged; switch default off |


### 0.7 Where the data is (all read-only for these tasks)

| What | Where | Notes |
|---|---|---|
| Production P&D graph | `data/processed/kg/slice3_c2/checkpoint.json` | keys used here: `concepts`, `merges`, `merge_review`, `taxonomy_candidates`, `relation_results_v3` (each has `outcome`, `reason`, `relation`, `direction`, `qualifiers`, `evidence_quote`, `pair`, `group`), `misconceptions`, `anchors`, `selection_stats` |
| Concept-stage record | `data/processed/kg/slice3_c2/v4_concepts.json` | `sections` (per-section verifier iterations, flags, hints), `merges` (**the real generator-stage rule ids**: `G-link`, `G-link-rejected`, …; the checkpoint's `merges` relabels them all as `G-link`, see §7 step 6), `backfill` |
| Comparison rebuild | `data/processed/kg/slice3_c3/` | made with R1-key matching and the adjudicator |
| SciNLP runs | `data/processed/kg/cr012_scinlp_heldout_<doc>_<E0/E1/E3/E4>/checkpoint.json` (test, frozen); `..._cr021test_...`, `..._cr021dev_...` (rebuild) | load with `cumap.cr012.production_graph.load_run`; run ids via `cumap.cr019.run.sc_run_id(doc, level)` |
| SciNLP gold | `cumap.cr012.adapters.SciNLPAdapter().gold(split)` / `.load_documents(split, paragraph_every=cumap.cr012.scinlp_run.PARAGRAPH_EVERY)` | test split = 3 papers (`cumap.cr019.run.SC_DOCS`); final reporting only (rule 9) |
| P&D gold | `data/gold/pd_e2e_pilot_blind.csv` (sections 1.5, 2.6), `data/gold/pd_e2e_test_blind.csv` (held-out) | read through the CR-012 / CR-017 loaders, never written |
| Frozen scorers | `src/cumap/cr012/scoring.py`, `src/cumap/cr017/`, `src/cumap/cr019/variants.py` | reuse, never modify |
| Frozen results | `reports/cr012/*.json`, `reports/cr017/headline_metrics.json`, `reports/cr019/stage_a.json`, `reports/cr022/part_a.json` | determinism gates compare against these |

## 1. Repository state (checked 2026-10-22)

| Item | State |
|---|---|
| Mainline | `main` at `d51f7af` (Merge CR-026). CR-019, CR-020, CR-021, CR-022 Part A, housekeeping-lint, CR-023, CR-024, CR-025 and CR-026 are merged. Tags up to `cr-021-complete`, `cr-022-part-a-complete`. |
| Not merged | `cr-018-boundary-identity`: CR-018 STOP 1 (`b44c128`) and STOP 2 (`9fcea9d`) exist only there; the rest of that branch's commits were merged to `main` through the CR-019 to CR-021 branches. `cr-022-scinlp-hierarchy-scoring`: superseded by `cr-022-part-a` (merged); its only extra commit is the previous handoff (`49ba673`). |
| Tests / lint | 876 tests pass, ruff clean (as recorded for CR-026 in `PROGRESS.md`; not re-run for this handoff). |
| Active model profile | CR-026: the local `.env` selects `configs/models_luna_default.yaml` (every tier gpt-6-luna, gpt-6-sol only on escalation). Restore the baseline by unsetting `CUMAP_MODELS_CONFIG` and setting `OPENAI_MODEL_STRONG=gpt-6-sol`. |
| Production graph | P&D `slice3_c2` (explorer, CR-013 config). `slice3_c3` is the CR-021 comparison rebuild, not production. |
| Relation registry | Production default v1.3. v1.4 (CR-024) is built but not adopted. |
| Untracked files | `data/gold/` has six untracked files (`cr015_pd_pilot_gold_draft.csv`, `cr021_rejected_links_review_marked.csv`, `iir_fp_audit_blind.csv`, `pd_concept_pilot_blind.csv`, `pd_concept_test_blind.csv`, and a stray `h420020-mapper.code-workspace`). These are owner-owned: code must not add, move or delete them; committing them is the owner's call. Also untracked: `data/interim/cr012/units/{4.1 ... 9.2}/`, two `data/interim/sleep/*.pkl`, `reports/OVERALL_FINDINGS_CR001-CR014.md`, a root `h420020-mapper.code-workspace`. |

## 2. Ongoing work in the open chat sessions

| Session | Work | Branch / files | Done | Open |
|---|---|---|---|---|
| **h420020-mapper-23** (this one) | Presentation explanation of the concept stage (generator, verifier, hints, anchors, pruner, span boundaries) | none changed except this file | Explanations given in chat; facts checked against the code and `slice3_c2` | See §4: four places where the docs and the code disagree; a domain-matched pruner CR (not started, draft offered) |
| **h420020-mapper-8b** | Report text: the five evaluation metrics (from `cr012/scoring.py`, `cr017/hierarchy.py`, `cr017/headline.py`, `configs/cr017_eval.yaml`) | no commits, no code changes, $0 | Paragraphs written and shortened at the owner's request | Owner's wording call: (1) objective O2 says "constituent concepts" but the hierarchy scorer uses only `is_a`; (2) the O5 strict-edge text doesn't say the endpoint concept types must also match |
| **h420020-mapper-4e** | Supervisor presentation and report support | no commits, $0 | Canva deck `DAHYZcvCV74` (4 slides, black and white: overview, expert-KG architecture, simplified architecture, 13-week timeline); report §3.4 rewrite and new §3.5 (SciNLP evaluation) as text to paste (the Google Doc was not edited: Drive connector is read-only) | Timeline dates are estimates, not yet confirmed by the owner. Its CR-022 questions are partly out of date: see §3, item 3 |
| **h420020-mapper-88** | Overnight implementation work 2026-10-21/22 | merged locally on `main`, nothing pushed; 876 tests pass | Explorer concept-count funnel; CR-019/020/021 and CR-022 Part A merged (tags `cr-019/020/021-complete`, `cr-022-part-a-complete`); repo-wide ruff clean; CR-023 o4-mini profile (baseline archived, tag `cr023-models-pre-change`); CR-024 registry v1.4 (built, not adopted); CR-025 three-model comparison on SciNLP dev (relation F1 luna 0.114 / o4-mini 0.081 / sol 0.154); CR-026 luna default (active via local `.env`). **Spend about $5.8** (CR-025: luna $0.18, sol $3.63, o4-mini $1.98 including two failed attempts) plus a few cents of ping calls | CR-018 STOP 2 + D1 to D6; adopt v1.4; CR-022 Part B; whether to run the model comparison on the locked test split |

Note: sessions 8b and 4e reported branch `cr-018-boundary-identity`, but the shared working tree is now on `main`. A session that resumes should check `git branch --show-current` before writing anything.

## 3. Owner decisions needed

1. **CR-018 (paused at STOP 2, `AWAITING_HUMAN_ANNOTATOR`).** A human must fill the frozen 120-family / 480-span blind boundary sheet `data/interim/checks/cr018/boundary_audit_blind.csv` (≈ 2.5 to 3.5 h, no model help), and Research decisions D1 to D6 (`reports/cr018/STOP1_RECONCILIATION.md` §8 on the CR-018 branch) are open. STOP 3 must not start without them. Previous recommendation: D1 (iii) with B1 primary, D5 approve $8, D4 (i).
2. **Production graph: decided, keep `slice3_c2`** (owner, as reported by session 88). Still open: a same-settings re-run (about $8, needs approval) to separate the CR-020/021 change from run-to-run variation. A new run would now also use the CR-026 luna profile, which is a third change.
2b. **Model comparison on the locked test split?** CR-025 ran on SciNLP dev only. Running on test needs the owner to lift the test lock again; it would be final-reporting only (rule 9).
3. **CR-022 Part B** (paid registry transfer, dev cap $10): not approved, not run. CR-024 has since replaced the draft mapping table with registry v1.4 and fixed the hierarchy set from the registry (`{is_a, subtask_of}` = SciNLP `{subclassOf, subtaskOf}`). So the remaining CR-022 decision is only whether to run Part B, and it depends on item 4.
4. **CR-024: adopt registry v1.4?** The definitions, examples and near-misses of the six new relations (`subtask_of`, `enhanced_by`, `measured_by`, `evaluated_by`, `evaluated_on`, `similar_to`) are drafts that need owner review. Adoption needs new relation prompt versions and a re-run.
5. **CR-023 paid comparison (about $4.3).** It is probably no longer needed: CR-025 already compared o4-mini (lowest scores, and it truncated at the production caps). Recommendation: close CR-023 without the run.
6. **CR-026 caveat.** Calls made with `allow_escalation=False` (for example the concept generator) never escalate to sol, so some stages that ran on sol before now stay on luna even when the output is weak. Accept, or list the stages that should keep sol.
7. **Report wording** from sessions 8b and 4e (§2): the O2 and O5 objective texts, and the timeline dates.
8. **Backfill: decided, remove it** (owner, 2026-10-22). Queued as CR-027 for a later session (§6). Still to confirm: a config switch (recommended) or deleting the code.
9. **Identity rules: decided, merge into one resolver** (owner, 2026-10-22). Queued as CR-028 after CR-027 (§7). Still to confirm: the held-out data for the measurement, and the `not_a_concept` policy for new concepts. Extension decided the same day: run input B per section, keep bookkeeping current with an incremental occurrence index, refresh names by a fixed rule, and remove the end-of-pass bookkeeping from new runs once the online result is shown to match it (§7, "Extension").
10. **`same_concept` queue: decided, handle it** (owner, 2026-10-22). Queued (§8): an interim $0 review-sheet step, then input C of the CR-028 resolver. Still to confirm: whether the interim step is worth doing on its own, given one pair so far.
11. **Lexicon intake: decided, only reviewed decisions enter the lexicon; no new seed lists** (owner, 2026-10-22). Existing v0.3 entries stay. Queued (§9), built together with the §8 interim step. Still to confirm:
    - the 40-row cap per sheet, and the sample sizes (5 for narrower/broader/new, 10 for the deterministic-merge audit);
    - whether `slice3_c3`'s adjudicator decisions should feed the first sheet, even though `slice3_c2` stays production.
12. **Qualifiers: decided, amend them; keep the separate qualifier call** (owner, 2026-10-22). Queued (§10). Still to confirm: the adoption limit (≤ 0.01 drop), and what happens to a negated edge with no negation cue (rejected, or kept as affirmed and flagged).
13. **Reminder: develop stage-wise relation classification (Option C)** (§11). Not a plan yet; the owner wants to develop it further before deciding.
14. **Verify and assemble: decided, remove it as a stage** (owner, 2026-10-22). Queued after CR-028 (§12). Its remaining checks move into relation classification's edge store: directed edges, direction from types when only one orientation is valid, symmetric normalisation, identical-edge merging, conflict flags, and a separate measurement list. The registry version is recorded and checked when a run is loaded. What remains is a "save graph" export of the chapter snapshots.
15. **eRST: decided, remove it from the graph design** (owner, 2026-10-22). Queued (§13): docs, rules 28-29 become historical notes, the code stays for frozen CR-010 results.
16. **Misconceptions: decided, produce them from a misconception family in relation classification** (owner, 2026-10-22). Queued (§14). Still to confirm: the registry v1.5 family definition; and whether the $0 cue scan stays as a selection-priority signal, given the coverage risk.
17. **Hierarchy F1: decided, broaden it to transitive hierarchy relations, closure per relation** (owner, 2026-10-23). Queued (§15) as a new labelled variant beside the frozen number: P&D `is_a` + `part_of` (per part type), SciNLP subclassOf + subtaskOf + partOf. SciNLP concept matching uses a scoped owner identity sheet (hierarchy-relation endpoints only, about 96 mentions, 👤 about 20 to 30 minutes); R1-key pseudo-nodes stay as a cross-check. `part_of` without a part type is scored direct-only (none on P&D today).
18. **SciNLP concept-level fact F1: decided, add it beside the headline** (owner, 2026-10-23). Queued (§16), pre-registered before computing; `IDX-P1` stays the headline, `IDX-P3` the upper bound. No full identity sheet (owner decision): the score runs only on R1-key pseudo-nodes and is always labelled as string-based. The scoped §15 hierarchy sheet is unchanged. Also in §16: the IDX-P1 oracle ladder computed today, to be recorded as a generated report.
19. **Reminder: review the whole evaluation pipeline** (owner, 2026-10-23). Start with concept scoring: score concepts as concepts, not spans (§17). Not a plan yet.

## 4. Findings from this session (docs vs code; no change made)

| # | Where | Docs say | Code does |
|---|---|---|---|
| 1 | `expert_kg/pair_selection.py` docstring; `concept_gvp.yaml` `anchor_family_map` | The anchor **type** sets pair priority | Phase 0b puts every anchor pair first in **book order**; the type is never read there. `anchor_family_map` is read only by the CR-009 STOP 3 report |
| 2 | `concept_gvp.yaml` `hint_rejection_reasons` | Five fixed reasons for rejecting a hint | `HintResponseLLM.reason` is free text and nothing reads that list (the fixed set that is enforced belongs to not-mentions) |
| 3 | `concepts_v4/pruner.py` `term_features` | Six surface features, including general-knowledge bank and CSO membership | `loco_pruners` builds `P1Model(embed_fn, nlp)` without a bank or CSO, so those two features are always 0 |
| 4 | `concept_gvp.yaml` `pruner.tau: 0.1` | τ = 0.1 | Every P&D run since `slice3_c2`, the CR-012 unit runner and SciNLP use τ = 0, so the pruner is off; `slice3_c2` records 0 pruned concepts |

Suggested follow-up: correct the docstring and the config comments in one small commit (no behaviour change). Fixing item 3 changes behaviour, so it belongs in a CR.

**Possible CR (not opened): domain-matched pruner.** Train P1 on the 10 exposed P&D sections with model-generated gold (`pd_concept_pilot_blind.csv`, `pd_concept_test_blind.csv`: 4.1, 9.2, 4.2, 5.3, 6.1, 6.4, 7.2, 8.3, 8.4, 8.5), using the generator's own new concepts as rows instead of spaCy noun phrases, with the bank/CSO features wired in, leave-one-chapter-out, and the CR-009 τ rule. Development replay costs $0; sealed sections 5.2, 6.5, 9.1, 9.4 stay sealed. For a new domain with no gold, the pruner stays off and could become a review flag only.

## 5. Safe overnight work (no approval needed: $0, no model call, no gold)

- Fix the docs/code mismatches 1, 2 and 4 in §4 (comments and docstrings only), on a `housekeeping-*` branch from `main`.
- Re-run `uv run pytest` and `uv run ruff check .` on `main` and record the numbers.

Everything else above needs an owner decision or spend first. Never push. Merging and tagging follow §0.2 (owner, 2026-10-23).

## 6. Queued for a later session: CR-027 remove backfill from production runs

**Owner decision (2026-10-22): remove backfill.** Not started; do it at a later date, as its own CR. $0, no model call.

**Why** (measured from `slice3_c2`, no ablation run):
- **Cost and output:** backfill costs $0.089 of $10.29 (69 calls) and adds 234 mentions on 145 nodes (12% of recorded existing mentions); the model rejected 113 of 358 string matches.
- **Little downstream use:** candidate pairs (`enumerate_candidates`), first chapter and spread all come from longest-match string matching, not recorded mentions. Backfill changes the strongest role of 35 nodes, of which only 4 enter the pair-coverage phase. Evaluation runs per section or per paper and barely trigger it. It never reaches the retriever.
- **Side effect:** the checkpoint conversion (`concepts_v4/pd_run.py` lines 104-198) treats each node's earliest mention as its creation mention. For the 145 backfilled nodes, canonicalisation therefore saw the backfill quote, and that mention was relabelled `source: "llm"`: the checkpoint shows 89 `backfill` mentions, not 234. With backfill off, new runs no longer hit this; existing runs keep it.

**Plan** (proposed to the owner; confirm the "switch, not delete" choice before starting):
1. Branch `cr-027-remove-backfill` from `main`.
2. `configs/concept_policy.yaml`: add `backfill: false` with a comment (new production runs only).
3. `concepts_v4/cr009_run.py`: read the switch and call `run_obj.run(units, backfill=...)`. This one seam covers P&D, the CR-012 unit runner and SciNLP. Record `backfill` in the run's metadata. Leave `experiments.py` (IIR, frozen CR-009 / CR-010 arms) untouched, so old arms replay.
4. Keep the code and `prompts/concept_backfill/v1.md` (rule 8). The explorer funnel, CR-013 traces and STOP 3 reports read the stored backfill records of older runs.
5. Tests: a production run with the switch off makes no `concept_backfill` call; the existing backfill tests pass with it on.
6. Docs:
   - `DECISIONS.md`: decision, reason, alternatives (fix the conversion and keep backfill; a $0 pair-selection replay first).
   - `ARCHITECTURE.md`: concept-stage paragraph.
   - `CLAUDE.md`: rules 23 and 24 say "backfill (older runs only)".
   - `PROGRESS.md`: a CR-027 section.
7. Run `uv run pytest` and `uv run ruff check .`, commit on the branch, then merge and tag as in §0.2.

**Not in scope:** rebuilding `slice3_c2`, which stays production. If the owner later wants the effect measured, run the $0 replay of pair selection with backfill mentions removed.

## 7. Queued for a later session: CR-028 one identity resolver

**Owner decision (2026-10-22): merge the two identity rule sets into one.** Design below; nothing built. Do it after CR-027, because both change `concepts_v4/pd_run.py`. Diagram of the proposed design: https://claude.ai/artifact/WwvnBMkBVrgVUFMhcPexn9 (private to the owner).

**Problem.** Generator links (input A) go through the strict G-link check and then the rejected-link adjudicator. New concepts (input B) go through exact, R0 to R4. `same_concept` relation answers (input C) only queue a pair, and nothing in production reads that queue: it is consumed only by the CR-011 sleep candidate builder, which was not adopted. In `slice3_c2` the queue holds one pair (datagram / message, §1.3, "datagram may be thought of as a synonym for message"), and it was never merged or rejected. The deterministic rules mostly overlap, but:
- the G-link path lacks R3 (textbook alias statements);
- the two paths use two different LLM judges (`rejected_link_adjudicator` v2 and `canonicalize` v2) with different outcomes;
- so one pair can get different answers depending on which path found it.

**The common ruleset (u1).** Every input becomes candidate pairs, and the candidate sources differ:
- A: the card the generator named;
- B: a registry search (top 5, similarity ≥ 0.6, compatible node type, lexicon `different` partners removed);
- C: the pair itself.

Every pair then meets the same rules in this order. The first rule that decides wins.

| Rule | What | Decides | Comes from |
|---|---|---|---|
| U0 | lexicon `different` pair (approved, scoped) | keep apart (veto) | lexicon guard at R1-R3/R4 and verifier C1 |
| U1 | lexicon `same` set | merge | R0, G-link rule 1 |
| U2 | same name form: exact, R1 name key (with acronym guard), or the same words up to plural/inflection | merge | exact, R1, G-link rule 4 (and today's "trivial link") |
| U3 | acronym ↔ long form written in the text (Schwartz & Hearst pair, or an embedded "long form (SF)"); chapter-scoped when an acronym has two expansions | merge | R2, G-link rules 2-3 |
| U4 | textbook alias statement: strong cue ("also known as", "also called", "abbreviated", "or simply") merges, weak cue ("sometimes called", "often called") goes to review | merge / review | R3 (new for input A) |
| U5 | one LLM judge, strong tier, strict "same" rule, verbatim quote checked: `same` / `narrower` / `broader` / `new` / `not_a_concept` | see below | `rejected_link_adjudicator` v2 + `canonicalize` v2 |

- **Type check:** node types must be compatible for U2 to U5 (as CR-007 does for R1-R3 and R4 candidates).
- **U5 outcomes:**
  - `same` merges, except a candidate found only by registry search with similarity < 0.70, which goes to review (today's R4 band);
  - `narrower` / `broader` gives a new node plus a taxonomy candidate (this replaces the unadopted `more_specific` promotion rule);
  - `new` gives a new node;
  - `not_a_concept` drops the item **only for input A** (measured in CR-021). For B and C it is a review flag and the node is kept, until it is measured there.

**Unchanged:** when each input runs (A online, B after the pass, C in the relation stage); the lexicon outranks every rule (rule 20); deterministic rules before any LLM call and weak cues never auto-merge (rule 19); equivalence stays a node property (rule 21); re-key after merges that touch existing relations.

**Candidate source B: registry-search changes** (owner, 2026-10-22; $0, part of CR-028). Today `ConceptRegistry.top_k_similar` (`expert_kg/canonicalize.py`):
- embeds `"name. definition"`, or the name alone when there is no definition (only 343 of 1,243 `slice3_c2` concepts have one);
- uses local `all-MiniLM-L6-v2`, cosine similarity, top 5;
- never embeds aliases;
- embeds a concept once and never again.

Changes:
1. **Same text recipe on both sides:** `"name. gloss"`, where the gloss is the 25-word quote every node already has (`make_gloss`), so a defined concept and an undefined one are no longer compared on texts of different kinds.
2. **Embed every form:** canonical name and each alias, each as `"form. gloss"`. A concept's score is its best-matching form (max cosine), and the matched form is logged with the candidate.
3. **Re-embed after a merge:** an alias added by a merge invalidates the concept's cached vectors.
4. Thresholds stay 0.6 (offer) and 0.70 (review band), recorded in `configs/identity_rules.yaml`. The 0.6 value has no tuning record, so it is reported as is and is not tuned on the measurement data.

These must sit behind the same `identity_resolver` switch; `legacy` keeps today's search byte-identical for replays.

**Plan** (first step is to confirm the plan with the owner):
1. Branch `cr-028-identity-resolver` from `main` (after CR-027 is merged).
2. `configs/identity_rules.yaml` (ruleset `u1`: rule order, thresholds 0.6 / 0.70, `not_a_concept` policy per input). Add `identity_resolver: legacy | u1` to `configs/concept_policy.yaml`, default `legacy` until adopted; record the value in run metadata.
3. `expert_kg/identity.py`: pure functions for U0-U4 (reuse `lexicon.py`, `alias_rules.py`), `resolve(pair, ctx) -> IdentityDecision {rule_id, decision, target, evidence}`, and one U5 call through `llm/client.py`.
4. New prompt `prompts/identity_judge/v1.md`, built from `rejected_link_adjudicator` v2 with `narrower` / `broader` added. Static content first, per-item content last; closed choice set (rule 12). Old prompts stay (rule 8).
5. Wire the three candidate sources: `runner._apply` (A, replacing `g_link_ok` + `_adjudicate` when `u1`), `pd_run` canonicalisation (B), the `same_concept` queue (C). The `legacy` path must replay older runs byte-identically.
6. Fix the merge log on the way. Keep each entry's own rule id: today `pd_run.py` relabels every generator-stage entry, rejected links included, as `G-link`. Log U0-U5 ids with a legacy mapping (G-link, R0-R4, G-link-adjudicated).
7. Tests (no network, mock backend): each rule fires in order; U0 vetoes at every source; same pair gives the same decision from A and from B; legacy replay unchanged. For the search: a concept is found through an alias; a merge invalidates its cached vectors; both sides use the same text recipe (stub embedder).
8. Pre-registered measurement before adoption (write it into DECISIONS first):
   - **Development:** CR-021 dev split (72 rows) for input A; the owner-marked CR-005 / CR-007 / CR-008 merge-sheet pairs for input B, excluding pairs the lexicon already covers (they would pass U0/U1 trivially).
   - **Held-out:** the CR-021 held-out split was used once (v2 adoption), so either label its reuse as a second look, or ask the owner to mark a fresh sheet of about 100 B-path pairs from `slice3_c2`.
   - **Proposed rule:** adopt if U5 `same` precision is not lower than the adjudicator v2 held-out value by more than 0.03, and the U0-U4 decisions on a $0 replay of `slice3_c2` equal today's except the intended changes (U4 on links, plural rule on search).
   - **Search, $0:** on the owner-marked `same` pairs from the merge sheets, report candidate recall (the true match is in the top 5 and ≥ 0.6) for the legacy search and the new search side by side. Also report how many extra pairs reach U5, since each one is a strong-tier call.
   - **Cap:** about $3, following rule 7 (dry run, `--limit 20`, then the full run).
9. Docs:
   - `DECISIONS.md`;
   - `ARCHITECTURE.md` (CR-008 and CR-021 sections);
   - `CLAUDE.md` (rules 19 and 25 name the resolver and U5 instead of the adjudicator);
   - `PROGRESS.md`.

   Run pytest and ruff, commit on the branch, then merge and tag as in §0.2. A rebuild with a new run id (about $8) needs separate approval; `slice3_c2` stays production.

**Open for the owner:** a fresh held-out mark sheet, or a second use of the CR-021 held-out split; and whether `not_a_concept` should ever drop items on paths B and C.

**Extension (owner, 2026-10-22): online identity, incremental bookkeeping, name refresh; remove the end-of-pass bookkeeping.** Part of CR-028; needs measurement like the rest.

1. **Input B runs per section.** After each section (chunk), that section's new concepts go through U0-U5 against everything known so far, instead of once after the whole pass. Each concept is still compared with the same set (book order), but merged concepts and aliases now reach the next section's cards.
2. **Incremental occurrence index** (deterministic, $0; reuse the CR-019 `cr019/occurrences.py` matching, positions only, never mentions: rules 24 and 35):
   - when a concept or alias is added, index its forms over every section processed so far. This catches concepts named before they were created (17 in `slice3_c2`);
   - when a new longer term appears, re-scan only the sections that contain it, so shorter matches inside it stop counting (15 in `slice3_c2`);
   - use the run's recorded matching mode (`r1key` for new runs, CR-020).
3. **Bookkeeping kept current from the index:**
   - first occurrence and first chapter (rule 18: the first longest-match occurrence);
   - one `defined` per concept, re-applied whenever a merge combines two histories.
4. **Name refresh**, deterministic and logged in `name_history` (section, old name, new name, rule):
   - prefer the form in the concept's `defined` mention, then the long form over an acronym (R2);
   - never a shorter head of a longer term;
   - rename only when a `defined` mention or an R2 long form appears, never on frequency alone, so card names stay stable;
   - the concept id (`c_<slug>`) never changes (rule 31); only the display name does.
5. **Remove the end-of-pass bookkeeping** (`slice_rerun.finish_concepts`, rule-18 first occurrence and role rule) from new production runs, since the online index makes it redundant.
   - Before removing it, the measurement run must show that the online result equals `finish_concepts` on the same run (first chapter and roles for every concept), recorded once in the CR report.
   - Keep the function for `legacy` runs and replays: older runs, including `slice3_c2` and the CR-013 replay, were built with it and must still replay byte-identically.
   - Update `docs/ARCHITECTURE.md` and CLAUDE.md rule 18 to say where the rule is applied.
6. **Measurement:** compare against `legacy` on the P&D development sections (new run ids). Report:
   - duplicates left after the pass;
   - number of renames and examples;
   - changes in concepts, pairs and edges;
   - the five CR-017 metrics.

   Online merging changes the generator's inputs, so differences are expected and must be read beside run-to-run variation (see the CR-021 rebuild).
7. **Keep:** the lexicon veto, full alias provenance and the non-transitive type map (rule 30).

## 8. Queued for a later session: handle the `same_concept` queue (lane C)

**Owner decision (2026-10-22): the queue must not sit unread.** Not started; do it at a later date.

**Problem.** When `relation_choice` (v4 and later, comparison family only) answers `same_concept`, `relations_v3.py` stores `outcome: same_concept`, `reason: queued_for_merge` and draws no edge. Nothing in production reads that queue (only the unadopted CR-011 `sleep/candidates.py`). So a synonym the book states is never merged, never rejected and never sent to review. `slice3_c2` and `slice3_c3` each hold one such pair: datagram / message (§1.3, "datagram may be thought of as a synonym for message", pair `RP-1.3-310`).

**Two steps:**
1. **Interim, $0, can be done before CR-028** (branch `cr-029-same-concept-queue` from `main`):
   - add a reader that lists every `same_concept` result of a run (pair, sentence, evidence quote);
   - run the deterministic identity rules on it (lexicon `different` veto, lexicon `same`, R1, R2, R3);
   - write the pairs no rule decides to the merge review sheet in `data/interim/suggestions/` (blind: names, types and quotes only; never `data/gold/`), so the owner marks them;
   - an owner mark then becomes a lexicon entry through the CR-008 learning loop, and a merge, if any, happens by re-key at $0. Nothing merges automatically in this step.
   - Tests: one fixture run with a queued pair produces one sheet row; a lexicon `different` pair produces none.
   - Docs: DECISIONS, PROGRESS.
2. **In CR-028 (§7):** queued pairs become input C of the identity resolver and go through U0 to U5, with `not_a_concept` as a review flag only. The interim reader from step 1 is reused as C's candidate source.

**Expected effect:** small (one pair per P&D slice so far). The point is that a stated synonym gets a logged decision instead of disappearing.

## 9. Queued for a later session: standing lexicon intake

**Owner decision (2026-10-22): only reviewed decisions enter the lexicon.** The review sheet is the only way into `configs/term_lexicon.yaml`. No new seed lists are drafted, and the existing approved v0.3 entries stay (including seeds D101-D116), because the generator's LOOK-ALIKES block, verifier C1 and the misconception layer use them. A new domain starts with an empty lexicon (as SciNLP does). Not started; $0, no model call. Build it together with the §8 interim step (same branch `cr-029-same-concept-queue`, renamed `cr-029-review-intake` if both are done), because both produce one blind owner sheet.

**Problem.** The lexicon has been at v0.3 since CR-008 (2026-10-02). Its entries came only from the CR-005 / CR-007 / CR-008 merge sheets and the research-chat seeds. Later identity decisions never reach it.

**What goes on the sheet.** The resolver's uncertain or costly decisions only, where a mark changes something:

| From | Rows | Why |
|---|---|---|
| U4 weak cue ("sometimes called", "often called") | all | never auto-merged; waits on the owner |
| U5 `same`, merged | all (or a seeded random sample when more than the cap) | a wrong merge is the costly error; a `different` mark undoes it |
| U5 `same`, held back (search similarity < 0.70) | all | a likely true merge waiting on the owner |
| U5 `not_a_concept` on inputs B and C | all | only a flag until measured |
| U5 `narrower` / `broader` / `new` | small random sample (e.g. 5) | both nodes are kept, so an error is cheap |
| U2, U3, U4-strong deterministic merges | audit sample (e.g. 10) | only a mark can create the `different` entry that undoes a wrong rule merge (CR-008 sheet: 15 of 15 correct) |

U0 vetoes and U1 lexicon merges are never re-asked. Until CR-028 is built, the same rule applies to today's equivalents:
- weak R3 cues → the U4 weak row;
- R4 merges and the 0.70 review band (`merge_review`) → the U5 `same` rows;
- adjudicator decisions (`G-link-adjudicated`) → the U5 rows by decision type;
- the `same_concept` queue (§8) → the U5 rows;
- exact / R0 / R1 / R2 / strong R3 merges → the audit sample.

**What to build:**
1. **`cumap lexicon intake --run <run_id>`**, read-only on the run. It collects the rows in the table above from the run's merge log and decision records.
   - It removes pairs the lexicon already covers (by R1 key) and pairs already marked on an earlier intake sheet.
   - It writes one blind sheet to `data/interim/suggestions/lexicon_intake_<run_id>.csv` with columns: id, section, name A, name B, node types, evidence quote(s), mark (same / different / neither), note. The model's decision, reason and similarity are not shown. The source of each row goes in a separate key file.
   - Rows are capped at 40 per sheet, ordered by the table's row order, then book order. Samples use a fixed seed recorded in the key file. The rest are listed in the key file for the next sheet.
2. **Marking.** The owner marks the sheet and copies it to `data/gold/`; code never writes there (rule 2).
3. **Conversion.** `lexicon_proposals.propose_from_marks` (CR-008 learning loop, unchanged rules) turns the marks into entries:
   - same → `same`; different → `different`, with kind and why taken from the owner's note; neither → no entry, recorded so the pair is not asked again;
   - each entry cites "owner mark: lexicon intake <run_id> row N" and keeps the quote;
   - conflicting marks across sheets are left out and reported.
4. **New lexicon version** (v0.4, …): the changelog line and a `DECISIONS.md` entry. New entries affect **new runs only**. Record the lexicon version and hash in each run's metadata if it isn't recorded already, so replays use the version a run was built with.
5. **Tests:** fixture run → expected sheet rows; covered pairs and already-marked pairs are skipped; no model decision appears in the sheet; a marked fixture produces entries with sources; a `different` mark blocks the pair on the next run.
6. **When to run it:** after each production rebuild, or when the owner asks. It is a 👤 step: nothing enters the lexicon without a mark.

**Relation to CR-028:** the intake keeps the human layer (U0 / U1) growing only from the resolver's own U4-weak and U5 decisions plus the audit sample: a `same` mark lets U1 merge the pair next time with no LLM call, and a `different` mark lets U0 block it.

## 10. Queued for a later session: qualifier amendments

**Owner decision (2026-10-22): tidy the qualifiers; keep the separate qualifier call** (do not merge it into the relation-choice call). Not started. New versions are needed (rule 8): `relation_qualifiers` v6 (v5 already exists from CR-019), `relation_choice` v6, and the qualifier definitions in a new registry version (rule 11) with a `DECISIONS.md` entry.

**Findings** (`slice3_c2`, 549 edges):
- **`dimension` is asked twice.** The choice step's `comparison_dimension` is the one the code checks; the qualifier step asks again without seeing it. The qualifier version is set on 9 edges, 7 of them not comparisons.
- **Two encodings of a denial:** modality `never` and polarity `negated`.
- **1 of the 3 negated edges is wrong.** "fast parallel hardware switches can only be built using fixed-length cells" was marked negated.
- **`part_type` appears on 1 `is_a` and 1 `requires` edge.** The registry's `applies_to` limits are not enforced.
- **The surface phrase often copies the whole quote:** 122 of 549 (22%).
- **Stale text:** both the choice v4 and qualifier v4 prompts still mention the retired `trades_off_with`.

**Changes:**
1. **Per-relation qualifier schema** (built from the registry's `applies_to`, like the dynamic choice schema):
   - every edge: `polarity`, `modality`, `conditions`, `surface_phrase`;
   - `part_type` only for `part_of`;
   - `action_type` only for `acts_on`;
   - no `dimension` field.
2. **Remove `dimension` from the qualifiers.** The comparison dimension comes only from the choice step. In the new `relation_choice` version, it becomes a verbatim **dimension quote** (e.g. "faster", "8 bits … 16 bits") checked as a substring of the sentence, instead of the paraphrase lemma match that turned 18 comparisons into no_relation (about half of them real contrasts, e.g. SRAM vs DRAM "faster").
3. **Drop modality `never`.** Negation is recorded only by `polarity`. Modality becomes `necessary / always / typically / possible`.
4. **Pass the evidence quote to the qualifier step**, and require `surface_phrase` to be a substring of the quote and shorter than it (the linking words only).
5. **New code checks ($0):**
   - a qualifier must fit its relation (defence in depth even with the per-relation schema);
   - `negated` needs a negation cue in the quote (not, no, never, without, cannot, neither, nor, only … not, independent of); a negated edge without a cue becomes `rejected` with reason `negation_without_cue`, logged;
   - surface phrase shorter than the quote.
6. **Remove the `trades_off_with` text** from the new prompt versions, and remove it from `DIMENSION_RELATIONS` in `relations_v3.py` once no saved run needs it.
7. **Downstream readers:** `report/data.py`, `kg_explorer.py`, `misconception.py` (polarity / modality perturbations) and `gold_editor.py` must accept the narrower modality set and a missing `dimension` qualifier. Older runs keep their stored values (`never` stays readable).

**Measurement before adoption** (P&D development sections 1.5 / 2.6, new run ids, `--dry-run`, then `--limit 20`, then full; write the rule into DECISIONS first):
- relation choice and edge results must not get worse (pre-registered limit, e.g. Relation Macro F1 and Strict E2E drop ≤ 0.01);
- report polarity, modality and part_type agreement between v4 and v5 on the same edges;
- report how many comparison pairs become `contrasts_with` edges with the dimension quote.
- Cost: well under $1 on luna.

**Related, not included here:** the domain/range rejections (58 in `slice3_c2`, many apparently true statements, mostly `has_purpose` / `has_property` ranges). These need an owner sheet and a registry change, and were not part of this decision.

## 11. Reminder for the owner: develop "stage-wise relation classification" (Option C) further

**Status: an idea to develop, not a plan.** Nothing is approved or built. Raised 2026-10-22.

**The idea.** Per pair the pipeline already stops early: relation choice runs only on pairs with a family, and qualifiers only on pairs that pass the code checks. What changes is the order across pairs. Today 1,100 pairs are picked **before** any LLM call by a weak ranking, and 52% of those slots produced no edge in `slice3_c2`. Option C instead:
1. runs the cheap **family step on every candidate** (8,604 same-sentence pairs for chapters 1-3);
2. applies the budget only to relation choice + qualifiers;
3. spends that budget on family-positive pairs.

**Evidence that motivates it** (`slice3_c2`, classifier-judged, $0):
- selected pairs gave edges 48% of the time, against 40% for random unselected pairs;
- the cue score had no value (cue 1: 47%, cue 0: 50%);
- anchor pairs 53%; list-like sentences 37%; sentences over 40 words 35%.

CR-010 owner labels: selected pairs 74.7% true, skipped same-sentence pairs 44.7% true; classifier precision 95% vs 71% on those pools.

**Rough cost for the whole same-sentence pool, chapters 1-3** (estimated from logged token averages; not measured):

| Stage | Pairs | luna | sol |
|---|---|---|---|
| family | 8,604 | ~$1.0 | ~$20 |
| choice (~78% family-positive) | ~6,700 | ~$1.3 | ~$26 |
| qualifiers | ~3,500 | ~$0.5 | ~$11 |
| total | | ~$2.9 | ~$57 |

**Questions to work out:**
1. **Triage recall:** measure the luna family step on the 600 owner-labelled CR-010 pairs (P0 / P1 / P2 / P3) first. Use the family step as a hard filter, or only as a ranking signal?
2. **Precision:** classifying the wider pool adds edges at lower precision (71% vs 95% in CR-010). Options: a `confidence` field and threshold in a new choice-prompt version; a stricter rule for lower-ranked pools; owner marks on a sample.
3. **Selection:** the coverage and anchor phases could choose each core concept's best family-positive pair.
4. **Budget per stage**, possibly with adaptive stopping (stop when a batch's edge rate falls below a threshold); combine with the $0 pair-ranking fixes (word-boundary cues between the mentions, cue-bearing evidence sentence, lower rank for list-like and long sentences).
5. **Batch API:** this is the bulk workload CLAUDE.md says to wait for; results go through the same cache.
6. **Records:** a `triaged_out` outcome so CR-013 traces and the explorer funnel stay complete; report pair recall with its scope (rule 29).
7. **Order of pools:** same-sentence first, then the ±2-sentence window (+13,460 pairs counted at $0), with the family step as its triage.
8. **Measurement:** P&D development sections, new run ids, a pre-registered rule (e.g. triage recall on human-true pairs ≥ 0.9; edge precision against owner labels no more than 0.02 below today).
9. **Several relations per concept pair** (owner, 2026-10-22): a pair can have more than one true relation (P&D gold: 3 of 118 pilot pairs, 15 of 417 test pairs). Today selection keeps one sentence per pair for the whole book, so at most one relation is ever classified. Classifying per occurrence (each sentence, or each section, where the pair co-occurs) would let several relations appear; §12 `v2` assembly then keeps them. Decide how many occurrences per pair to classify (all, or the best few by rank), since it multiplies the number of calls.
10. **The measurement sample:** the 50 random unselected pairs per run estimate what the budget misses. If every candidate is classified, nothing is unselected and the sample can be dropped.

## 12. Queued for a later session: fold "verify and assemble" into classification; keep only the snapshot export

**Owner decision (2026-10-22): remove "verify and assemble" as a stage in the planned pipeline.** Every check it still does moves into relation classification, where each edge is written. What remains is a plain export step, **"save graph"**: write the chapter snapshots that the organisation view (rule 13) and the explorer read.

- **Scope:** new production runs only. Older runs, including `slice3_c2` and the CR-013 replay, keep today's assembly (`legacy`) so they replay byte-identically.
- **Order:** do it after CR-028, which brings the online bookkeeping and the lane-C re-keying.
- **Cost:** $0, no model call.
- **Diagram:** https://claude.ai/artifact/HBo98edjFg3AH54ECzTc69 (private to the owner).

**Why each of today's assembly steps goes** (`slice3_c2` counts):

| Step today | Fired | Decision |
|---|---|---|
| cycles in transitive relations | 0 | **remove**: report only, nothing reads it, a cycle does not corrupt the graph |
| domain/range re-check | 0 | **remove**: repeats the classification-time check |
| retired relations (`gated_dropped`) | 0 | **remove for new runs**: replaced by recording the registry version and checking it when a stored run is loaded; kept for legacy replays |
| merged-away results (self-pairs, consolidated, secondary) | 0 | **moves to settle identity**: re-keying after lane-C merges (CR-028) handles what it changes |
| one edge per concept pair | 1 | **replace**: a pair can have several true relations (P&D gold: 3 of 118 pilot pairs, 15 of 417 test pairs, e.g. X `uses` Y and X `acts_on` Y). Edge identity becomes (pair, relation, direction). The one duplicate (`MP-3`, `MP-4`, modulation scheme → bit) came from the misconception stage classifying the same proposed correct edge twice; fix that at the source |
| measurement sample out | 20 edges | **moves to classification**: sample results go to a separate measurement list and never mix with graph edges (dropped entirely if Option C classifies every candidate, §11) |
| fix direction | 174 reversed | **moves to classification**, which already decides it |
| concept bookkeeping | 32 concepts | **moves online** (CR-028 extension) |
| write chapter snapshots | always | **keep**, as the "save graph" export |

**What to build:**
1. **Record the registry version and file hash in the run** (checkpoint and manifest; not recorded today). Loading a stored run for rebuilding or replay refuses a different version unless `legacy` is set.
2. **Edge store written at classification**, keyed by (pair, relation, direction). When a relation result is accepted:
   - **store the directed edge** (`source_id` / `target_id`), keeping the original pair id for traceability (selection, de-duplication, CR-013 joins);
   - **set direction from node types** when only one orientation is type-valid (117 of 549 edges in `slice3_c2`; the model agreed on all 117). When the model chose the type-invalid orientation, set the valid one instead of rejecting, and log it (`direction_set_by_types`, with the model's answer). Both orientations valid (420 edges): the model's answer stands. Neither valid: rejected as today. Report how many of the 58 domain/range rejections this recovers, beside the domain/range owner review;
   - **normalise symmetric relations** (`connected_to`, `contrasts_with`, v1.4 `similar_to`) to sorted concept ids; readers treat them as undirected;
   - **merge an identical edge** into the stored one, adding its quote (`evidence_all`);
   - **flag a registry conflict** (`conflicts_with`, e.g. `causes` vs `prevents` in the same direction) against edges already stored on the pair, in the manifest and the explorer; do not drop either;
   - **write measurement-sample results to a separate list**, never to the edge store.
3. **Misconception stage:** do not classify a proposed correct edge for a concept pair that already has a result for that relation (`expert_kg/misconception.py`).
4. **"Save graph" export:** write the chapter snapshots from the edge store and the concepts (bookkeeping already current from CR-028). No checks in this step. A switch `assembly: legacy | v2` in the run config, recorded in the manifest; `legacy` is today's code, unchanged.
5. **Readers that assume one edge per pair:** check the snapshot schema, `report/data.py`, `kg_explorer.py`, the organisation view (importance), the CR-017 scorers (scored as recorded, never re-defined; rule 35), and `same_concept` / misconception handling.
6. **Tests:**
   - a reversed answer is stored as Y → X;
   - a one-orientation pair gets the type-valid direction and the log entry;
   - two different relations on one pair are both kept;
   - two identical edges merge with both quotes;
   - a symmetric edge found both ways is one edge;
   - a `conflicts_with` pair is flagged;
   - sample results never reach the snapshots;
   - a registry mismatch on load stops;
   - `v2` snapshots equal `legacy` snapshots on a fixture where none of the new rules fire;
   - `legacy` replay of `slice3_c2` is unchanged (CR-013 replay still valid).
7. **Note:** selection still classifies each pair on one sentence, so several relations per pair only appear with per-occurrence classification (§11).
8. **Docs:**
   - `ARCHITECTURE.md` (relation stage, re-keying and snapshot paragraphs; stage 4 renamed "save graph");
   - `DECISIONS.md`, `PROGRESS.md`;
   - the presentation's stage 4 box.

## 13. Queued for a later session: retire the eRST discourse layer

**Owner decision (2026-10-22): remove eRST from the graph design.** Not started; $0.

**Why it can go:**
- Production never used it. Pair selection is same-sentence (P0), and eRST only proposed the P3 pool measured in CR-010.
- It never wrote an edge, merge or alias (rule 28).
- CR-010 found it expressed 27.2% of valid relations and preserved the useful meaning of 8.6%. P3 pairs were 42% human-true, but production never adopted that pool.

**What to do:**
1. **Docs:**
   - `ARCHITECTURE.md`: mark the "Relation layers after CR-010: dual layer" section as historical and drop eRST from the current layer list;
   - CLAUDE.md: rules 28 and 29 become historical notes for CR-010 results only, which is an owner change to the non-negotiable rules; log it in `DECISIONS.md`.
2. **Code:** keep `src/cumap/erst/` and `data/processed/cr010/` so the frozen CR-010 results still reproduce; no new run uses them. If the Option C pool work (§11) later wants cross-sentence pairs, use the ±2-sentence window with a cue filter, not eRST.
3. **Presentation:** remove the "Discourse links" box from stage 5 of the deck.

## 14. Queued for a later session: misconceptions from relation classification (a misconception family)

**Owner decision (2026-10-22):** add a misconception family and choice to relation classification, so misconceptions come from the same calls as relations instead of a second scan of the text. Items then go through code checks and form the misconception layer. Not started; needs a new registry version (rule 11) and new prompt versions (rule 8), and measurement before it replaces today's stage.

**Today** (`expert_kg/misconception.py`, `slice3_c2`):
1. a $0 cue scan over every paragraph (`configs/misconception_cues.yaml`: explicit error, tempting belief, confusion, negated identity, contrast, plus approved lexicon `different` pairs) gave 89 candidates;
2. one strong-tier structuring call per candidate (90 calls, about $0.71 on sol);
3. the result: 4 items, 75 "not a warning", 10 waiting for a correct edge.

The items:

| Item | Perturbation | Contradicts |
|---|---|---|
| modulation scheme `prevents` bit | wrong relation | `E:MP-3` |
| modulation scheme `acts_on` bit | polarity flip | `E:MP-4` |
| hardware switch `requires` cell | polarity flip | `E:MP-12` |
| routing table `conflated_with` forwarding table | conflation | lexicon `L:D-CR-005-29` |

**Planned design:**
1. **Registry (v1.5):** a `misconception` family, layer `misconception` (never semantic; rule 22).
   - The family step offers it when the sentence presents a belief as wrong ("a common mistake is…", "it is tempting to think…", "contrary to…", "is not the same as…").
   - It must not be offered for a plain negation: "X does not require Y" stays a negated semantic edge.
2. **Choice step, misconception family** (closed choice, rule 12). Outputs:
   - **the wrong statement:** a relation from the registry (or `conflated_with`), with its direction;
   - **the perturbation type:** polarity flip, reversed, substituted concept, conflation, wrong category, wrong relation, condition error, modality error;
   - **the correct statement,** if the text gives it: relation and direction, or "none";
   - **a misconception quote and a correction quote,** both verbatim.
3. **Code checks** (reuse today's `misconception.py` checks):
   - both quotes are verbatim;
   - endpoints are grounded;
   - the wrong statement differs from the correct one;
   - the perturbation type matches the difference (e.g. a polarity flip changes only polarity);
   - the item links to the expert edge it contradicts (`E:`) or an approved lexicon `different` entry (`L:`).
   - If the correct edge is not in the graph, it is classified as an ordinary relation (`found_by: misconception_stage`). If that fails, the item waits as `needs_correct_edge`. This also fixes the duplicate source (§12): a correct edge already stored is linked, never classified twice.
   - A failure is logged and goes to the owner sheet; nothing is dropped silently.
4. **Output:** items are written to `checkpoint.misconceptions` exactly as today, so the layer, the explorer and every reader stay unchanged.

**Risks to measure:**
- **Coverage:**
  - the relation classifier only sees selected pairs (1,100 budget, about 15% of real relations) and one sentence per pair, while today's cue scan reads every paragraph;
  - two of the four items need two sentences (misconception quote and correction quote in different sentences, e.g. modulation scheme / bit in §2.2).
  - Mitigation: keep the $0 cue scan, but only to **raise the selection priority** of pairs in cue sentences, and give misconception-family pairs a two-sentence window. Under Option C (§11: family step on every candidate) the coverage gap mostly disappears.
- **False positives:** the family step may confuse an ordinary negation or contrast with a misconception. Today the structuring call rejects 75 of 89 cue candidates as "not a warning".
- **Cost:** fewer calls (no separate structuring pass). The saving is small (about $0.71 per run on sol, cents on luna); the main gain is one pipeline instead of two.

**Measurement before adoption** (P&D development sections and `slice3_c2`, new run ids, pre-registered):
- recall of today's 4 items and of the owner-confirmed warnings;
- the false-positive rate on the 75 "not a warning" cue sentences;
- relation results on non-misconception pairs unchanged within the usual limit.

Keep today's stage as `legacy` until it passes.

## 15. Queued for a later session: broader Hierarchy F1 (transitive relations) and a SciNLP variant

**Owner decision (2026-10-23): broaden Hierarchy F1 beyond `is_a`.**
- **The rule:** use the **transitive** hierarchy relations, with closure per relation. Not every directed edge: chaining non-transitive relations (`uses`, `acts_on`, `has_property`) invents pairs the text never states, and mixing relation types in one chain is meaningless.
- **Status:** not started; $0, scorer only, no model call.
- **Scope:** a new, named variant reported beside the frozen CR-017 number. The frozen `cr017-1` scorer and every frozen result stay unchanged (rule 35, CR-017 freeze).

**Definition (variant `HIER-T1`):**
- For each relation in the hierarchy set **separately**, take the gold edges and the predicted edges of that relation and expand each into (concept, ancestor) pairs by transitive closure.
- Pool the pairs of all relations in the set, keyed (relation, concept, ancestor), and compute P / R / F1 over the two pair sets.
- Chains never mix relations. `part_of` chains only within the same `part_type` (component / member / phase; Winston et al.), so `part_of` closure is computed per part type.
- Everything else is inherited from the frozen CR-017 scorer (`src/cumap/cr017/hierarchy.py`):
  - mention-span alignment of predicted nodes to gold concepts;
  - wrong concept = wrong pair;
  - unmapped or false-merged nodes get synthetic ids (false positives only);
  - missing concepts lose all their pairs;
  - set semantics;
  - cycles reported, closure with a visited set, self pairs dropped and counted;
  - per-section closure for P&D.
- Also report each relation's own F1 and the direct-edge F1 (no closure) as diagnostics.

**Hierarchy set**, read from the registry, never hard-coded (rule 11): relations the registry marks as hierarchy and transitive.
- **P&D (v1.3):** `is_a` and `part_of`. P&D test gold has `is_a` 64 and `part_of` 41 (pilot 15 and 18), so support rises by about 64%.
  - Checked 2026-10-23: every P&D `part_of` gold row has a `part_type` (test 41: component 36, member 5; pilot 18: component 16, member 2), and so do all 104 predicted `part_of` edges in `slice3_c2`.
  - Rule for any future `part_of` without a part type (owner, 2026-10-23): score it as a **direct edge only, never chained** (conservative, no invented pairs).
- **SciNLP:** subclassOf, subtaskOf and partOf (test gold 27 / 19 / 2), via registry v1.4 `external_labels` (`is_a`, `subtask_of`, `part_of`). SciNLP partOf has no part type, so it chains as one relation.
- **Note:** the registry also marks `precedes`, `causes` and `prerequisite_of` transitive; they are ordering or causal, not hierarchy, and stay out. Add an explicit `hierarchy: true` flag in the registry (or reuse v1.4's derived hierarchy set) so the choice is visible.

**SciNLP identity: why the frozen scorer can't run there, and the variant.**
- **The gap:** SciNLP gold relations link mention spans and have **no concept or coreference clusters** (CR-012 STOP 1 audit). Concept F1 still works there because it matches spans one at a time. Hierarchy closure needs to know that two gold mentions are the same concept, and the gold doesn't say.
- **Variant `HIER-T1-SURF-R1`:** build gold and predicted pseudo-nodes by grouping mentions whose CR-008 R1 name key matches, plus acronym ↔ long-form pairs found in the same paper (CR-008 R2). This improves today's CR-022 A2, which groups exact strings: 765 gold mentions → 238 nodes, 527 collisions.
  - Report the collision count and a few colliding names with every figure.
  - Label it as inferring identity from strings; never a headline.
- **Rejected:** using the system's own nodes to group gold mentions (circular; CR-022).
- **👤 step (owner, 2026-10-23): a scoped identity sheet, not a full annotation.** The gold closure only needs to know which gold mentions are the same concept **among the endpoints of SciNLP's hierarchy relations** (subclassOf, subtaskOf, partOf: 48 on test, so at most about 96 endpoint mentions, many repeated), not among all 765 gold mentions.
  - Code writes a blind sheet to `data/interim/suggestions/scinlp_hier_identity_sheet.csv` with: paper, mention text, sentence, a row id. No system output, no model call.
  - The owner groups rows that name the same concept (about 20 to 30 minutes) and copies the marked sheet to `data/gold/`. Code never writes there (rule 2).
  - With the sheet, `HIER-T1` runs on SciNLP with real concept matching and becomes the SciNLP hierarchy figure. The R1-key pseudo-node variant stays as a labelled cross-check.
  - The full 765-mention annotation is not planned (poor value: 46 hierarchy relations over 3 papers, 4 to 5 true positives today). Oracle E2 on SciNLP therefore stays unsupported.

**What to build:**
1. `src/cumap/cr032/` (CR-032, see §0.3 T6), reusing `ancestor_closure` and the CR-012 alignment.
2. Config `configs/hierarchy_eval.yaml`: variant names, hierarchy relation source (registry flag), `part_of` per-part-type rule, SciNLP pseudo-node rule.
3. Tests:
   - `is_a` and `part_of` chains are closed separately;
   - a mixed `is_a` → `part_of` chain gives no pair;
   - `part_of` component → phase gives no pair;
   - the frozen `is_a`-only result is reproduced exactly when the set is {is_a};
   - R1-key pseudo-nodes merge "prefix-tuning" / "prefixtuning";
   - acronym ↔ long form merges within one paper only.
4. Determinism gate: frozen CR-017 P&D and CR-022 SciNLP numbers reproduce exactly before any new figure is reported.
5. Report: P&D held-out and pilot, E0 to E4; SciNLP test, frozen run and rebuild, under `FROZEN` and `IDX-P1` grounding. The new figures sit beside the frozen ones in the explorer scorecard, labelled.
6. Docs:
   - `DECISIONS.md` (definition, why not all directed edges, why per relation);
   - `ARCHITECTURE.md` (evaluation section);
   - `PROGRESS.md`;
   - the presentation's metric definition.

**Owner decisions recorded (2026-10-23):** the scoped SciNLP identity sheet (above) instead of a full annotation; `part_of` without a part type is direct-only (none exist on P&D today). Nothing else is open.

## 16. Queued for a later session: concept-level fact F1 for SciNLP (pre-register before computing)

**Owner decision (2026-10-23):** add a concept-level fact score for SciNLP, because the knowledge graph stores a relation once between two concepts, while the gold marks it at every mention where it appears. Not started; $0, scorer only, no model call. Do it together with §15, which needs the same identity step.

**Why not just switch the headline to `IDX-P3`:**
- P3 credits an edge from sentences the classifier never read (right answer, wrong evidence).
- It can count one predicted edge as several true positives.
- Switching after the test rescoring (P3 is higher) would be post-hoc: CR-019 pre-registered `IDX-P1` as primary.

`IDX-P1` stays the headline and `IDX-P3` stays beside it as the upper bound.

**Definition (variant `FACT-C1`):**
- **Gold facts:** collapse SciNLP's mention-level gold relations into unique (source concept, relation, target concept) facts. A relation marked in several sentences is one fact. Symmetric relations are unordered.
- **Predicted facts:** the graph's edges, one per (source concept, relation, target concept), each mapped to gold concepts through the same identity step.
- **Score:** P / R / F1 over the two fact sets; each fact counts once on each side.
- **Evidence:** not used for matching. Report beside it the share of true-positive facts whose own quote also matches a gold mention-level relation (the `IDX-P1` view), so "right fact, different sentence" is visible as a number.
- A predicted concept that maps to no gold concept keeps a synthetic id, so its facts can only be false positives. A gold concept with no predicted node loses its facts.

**Identity (shared with §15):**
- **`FACT-C1-SURF-R1` ($0, runs first):** gold and predicted concepts from R1-key pseudo-nodes plus acronym ↔ long form within each paper. Labelled as inferring identity from strings; report the collision count.
- **No full identity sheet (owner, 2026-10-23).** The owner decided not to annotate the endpoints of all 295 test relations (about 590 mentions). So `FACT-C1-SURF-R1` is the only version of this score, always labelled as inferring identity from strings. The scoped hierarchy sheet in §15 is unchanged and stays the only 👤 identity step; it covers hierarchy endpoints only and is not used here.

**Pre-registration** (write into `DECISIONS.md` before computing anything on test; rule 9):
- the definition above, the identity rule (R1-key pseudo-nodes only), and that `IDX-P1` stays the headline;
- that `FACT-C1` is reported beside it;
- that `FACT-C1-SURF-R1` is a labelled companion score, not a headline candidate, because its identity is inferred from strings. Any later headline change is a logged owner decision, never chosen on which number is higher.
- Validate the scorer on SciNLP train/dev first: fixtures, then dev numbers.

**What to build:**
1. A scorer module next to the §15 one, reusing the CR-012 adapter and alignment and the CR-019 occurrence index for predicted node spans.
2. Tests:
   - a relation marked in three sentences is one gold fact;
   - one predicted edge matches it once;
   - a symmetric relation matches either direction;
   - an unmapped predicted node gives only false positives;
   - pseudo-nodes merge "prefix-tuning" / "prefixtuning";
   - the evidence-match share is computed.
3. Determinism gate: the frozen CR-012 and CR-019 SciNLP numbers reproduce before any new figure.
4. Report:
   - SciNLP test (frozen E0 run, CR-021 rebuild, and the E1 / E3-M / E4-M oracle runs) and dev;
   - `FACT-C1-SURF-R1` only;
   - beside `IDX-P1` / `IDX-P3`, also in the explorer scorecard, labelled.
5. Docs: `DECISIONS.md`, `ARCHITECTURE.md` evaluation section, `PROGRESS.md`, and the presentation's metric definitions.

**Related, already computed (2026-10-23, not yet recorded in the repo):** the oracle ladder under `IDX-P1`:

| Level | `FROZEN` | `IDX-P1` | `IDX-P3` |
|---|---|---|---|
| E0 | 0.050 | 0.195 | 0.332 |
| E1 | 0.255 | 0.236 | 0.427 |
| E3-M | 0.463 | 0.433 | 0.574 |
| E4-M | 0.473 | 0.462 | 0.617 |

The `FROZEN` column reproduced exactly; the source runs were hash-identical before and after.

- Reading: under `IDX-P1` the concept-extraction step is +0.041, not +0.205; pair delivery (+0.197) is the largest loss.
- Record it as a generated report with a `DECISIONS.md` entry (task T5, CR-031). The script is in Appendix A; it goes into `src/` first, because reports are generated by scripts.

## 17. Reminder for the owner: review the whole evaluation pipeline, starting with how concepts are scored

**Status: a reminder, not a plan** (owner, 2026-10-23). Nothing is decided or built.

The owner wants to go through the evaluation end to end. The first point: **a concept should be scored as a concept, not as a span.**

**How concepts are scored today** (checked 2026-10-23):

| Benchmark | Score | What is matched | Span-dependence |
|---|---|---|---|
| **P&D** (CR-017 Concept F1, untyped `canonical_node`) | concept level | predicted nodes vs gold concepts, one per concept | **alignment is span-based:** `cr012/scoring.align_nodes` maps a predicted node to a gold concept only through an **exact** mention-span match. A node with the right concept but a slightly different span ("TCP connection" vs "connection") maps to nothing, so it counts as a miss *and* a false positive. A node that hits two gold concepts is a false merge, and two nodes on one concept are a split |
| **SciNLP** (entity strict) | **span level** | each predicted mention vs each gold mention, exact span | fully span-based. A concept mentioned five times counts five times, and one off-by-a-word span is wrong, even if the concept is right. There is no identity gold, so there is no concept-level version yet |

**Questions to look at:**
1. **Unit:** score unique concepts (per section / per paper), not mentions. On SciNLP that needs identity: R1-key pseudo-nodes (as in §15 / §16), labelled, since the full identity sheet is not being done.
2. **Matching a predicted concept to a gold concept:**
   - by **name and aliases** (R1 key, acronym ↔ long form) rather than by exact mention span;
   - or by span with a **boundary tolerance** (head-word match, or overlap). This ties in with CR-018's boundary audit and the nested-gold convention from CR-014 / CR-015.
3. **Partial credit:** a too-long or too-short span ("the TCP connection setup" vs "connection setup"), or a more general concept than gold, as a separate diagnostic.
4. **Splits and merges:** keep counting them, but separately from Concept F1, so one concept split into two nodes isn't hidden inside the score.
5. **Knock-on effects:** Hierarchy F1, Pair Recall, Relation Macro F1 and Strict E2E all reuse the same node alignment. A concept-level match changes every downstream metric, so decide the rule once for the whole pipeline.
6. **Rest of the pipeline to review in the same pass:**
   - grounding variants (`FROZEN` / `IDX-P1` / `IDX-P3`, CR-019);
   - the Pair Recall analogue on SciNLP;
   - Relation Macro F1 support;
   - the oracle definitions on SciNLP (pseudo-nodes for E3-M / E4-M; E2 unsupported);
   - small-n intervals;
   - P&D gold provenance (model-generated, owner-accepted);
   - which numbers are frozen.
7. **Process:** any change is a new, named scorer variant reported beside the frozen numbers (rule 35; CR-017 freeze). It needs a pre-registered definition, validation on SciNLP train/dev and the P&D pilot first, and a determinism gate. The frozen results are never rewritten.

## 18. Production `slice3_c2` concept-stage numbers (for reference)

43 sections, 85 generator calls, 0 errors. Stop reasons: 42 `max_iterations` (one corrective round), 1 `correct`. Verifier drops: 273 items (155 existing mentions, 118 new concepts; rules F3 215, F2 99, C1 26, C2 4; an item can carry several rules). Hints: 266 added, 77 rejected (M2 31, M1 26, M3 20), 195 unresolved (M3 146, M2 49), 42 unconfirmed mentions (M1). Carry-forward restored 198 items. Auto-fixes over all iterations: F6→independent 588, F5 anchor dropped 580, F2 whitespace 130, C3 new→mention 61, F2 anchor dropped 41, C4 refined→defined 16. Canonicalisation: 16 G-links accepted, 124 rejected (the CR-021 adjudicator was not active in this run). Pruner: 0 pruned (τ = 0).

## Appendix A. Oracle ladder under `IDX-P1` (task T5): script and acceptance numbers

Computed 2026-10-23 in the orchestrating session with this read-only script (no model call; the 12 source checkpoints were hash-identical before and after). Move it into `src/cumap/cr031/oracle_ladder.py`. Add a `main()` that writes `reports/cr031/oracle_ladder.json` and a generated `reports/cr031/oracle_ladder.md` table (levels × variants, P / R / F1, entity strict F1, predicted / unplaced edges, earliest-failure codes, the "right fact, not credited" count = codes `recovered` minus strict TP). Then add a test that runs on a small fixture.

```python
"""Read-only rescoring of the frozen CR-012 SciNLP held-out oracle runs under the CR-019 groundings. No model call."""
import collections as C
import hashlib

from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import sc_attribution
from cumap.cr019 import variants as V
from cumap.cr019.run import SC_DOCS, sc_run_id

LEVELS = ("E0", "E1", "E3", "E4")  # E3 / E4 are the SciNLP E3-M / E4-M runs (surface pseudo-nodes)
VARIANTS = ("FROZEN", "IDX-P1", "IDXR1-P1", "IDX-P3")


def ladder() -> dict:
    ad = SciNLPAdapter()
    gold_all, sym = ad.gold("test"), ad.symmetric_relations()
    dmap = {d.doc_key: d for d in ad.load_documents("test", paragraph_every=SR.PARAGRAPH_EVERY)}
    paths = [PG.run_path(sc_run_id(dk, lv)) / "checkpoint.json" for dk in SC_DOCS for lv in LEVELS]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    out = {}
    for lv in LEVELS:
        for v in VARIANTS:
            per, codes, predicted, unplaced = {}, C.Counter(), 0, 0
            for dk in SC_DOCS:
                cp = PG.load_run(sc_run_id(dk, lv))
                r = V.sc_score(dmap[dk], gold_all[dk], cp, sym, v)
                per[dk] = r["scores"]
                predicted += r["edges"]["predicted"]
                unplaced += r["edges"]["unplaced"]
                codes.update(c or "recovered" for c in sc_attribution(dmap[dk], gold_all[dk], r["pred"], cp, sym))
            out[f"{lv}/{v}"] = {
                "rel": S.aggregate_documents(per, "rel")["micro"],
                "entity_strict": S.aggregate_documents(per, "entity_strict")["micro"],
                "predicted_edges": predicted,
                "unplaced_edges": unplaced,
                "earliest_failure": dict(codes),
            }
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    out["sources_unchanged"] = before == after
    return out
```

**Acceptance (the generated report must reproduce these exactly; if `FROZEN` does not, stop):**

| Level | `FROZEN` strict F1 (P / R) | `IDX-P1` strict F1 (P / R) | `IDXR1-P1` | `IDX-P3` | entity strict F1, FROZEN / IDX-P1 |
|---|---|---|---|---|---|
| E0 | 0.050 (0.364 / 0.027) | 0.195 (0.348 / 0.136) | 0.195 | 0.332 | 0.352 / 0.611 |
| E1 | 0.255 (0.635 / 0.159) | 0.236 (0.456 / 0.159) | 0.236 | 0.427 | 0.979 / 0.877 |
| E3-M | 0.463 (0.730 / 0.339) | 0.433 (0.599 / 0.339) | 0.432 | 0.574 | 0.983 / 0.887 |
| E4-M | 0.473 (0.781 / 0.339) | 0.462 (0.725 / 0.339) | 0.462 | 0.617 | 0.983 / 0.887 |

Earliest-failure codes under `IDX-P1` (295 gold relations):

| Level | N0 | N1 | P0 | R0 | R1 | recovered | strict TP |
|---|---|---|---|---|---|---|---|
| E0 | 76 | 35 | 67 | 12 | 8 | 97 | 40 |
| E1 | 2 | 4 | 114 | 38 | 15 | 122 | 47 |
| E3-M | 2 | 4 | 1 | 99 | 20 | 169 | 100 |
| E4-M | 2 | 4 | 1 | 99 | 20 | 169 | 100 |

The `FROZEN` E0 row must also equal `reports/cr012/external_e2e.md`, and the `IDX-P1` E0 row must equal `reports/cr019/stage_a.json`.

**What the report must say** (generated text, no new claims):
- These are new figures on the test split, computed for reporting only (rule 9).
- Under `IDX-P1` the concept step E0 → E1 is +0.041 (it was +0.205 under `FROZEN`), because the rescued relations hit the pair budget (P0 67 → 114).
- Pair delivery (E1 → E3-M, +0.197) is the largest loss.
- At the ceiling, 99 of 295 gold relations get "no relation".
- About 57-75 per level are "right fact, not credited": attribution `recovered` but not a strict true positive. This is inferred; `IDX-P3` credits 66 more relations at E3-M.
- The steps are conditional uplifts, not additive.
- E3-M / E4-M use surface pseudo-nodes.
- 3 papers.
