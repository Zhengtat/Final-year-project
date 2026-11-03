# Overnight handoff (2026-11-03 to 2026-11-04)

Scope: CR-064 pair-delivery arms only. Five arms, run in one night: A1, A2 and A3 (already pre-registered in `DECISIONS.md`, 2026-11-01, not yet judged) and two new arms, **A4 (neighbouring sentences)** and **A5 (nested mentions)**.

**A4 is the owner's intended pair-selection direction** (for the textbook too): for each concept, look for other concepts in its own sentence **and in the neighbouring sentences (one before, one after)** and pair them. It is not implemented anywhere today. The old `window` argument of `enumerate_candidates` (`relations.py`) is the only related code: with `window` > 0 it pairs concepts in different sentences but stores only the earliest sentence as the pair's text, so the classifier never sees the other concept. Production, the CR-064 arms and every frozen run use window 0. A4 must therefore build the passage properly (§5.1) and must not reuse that path. On SciNLP, where every pair is classified, A4 runs beside the same-sentence base so the two can be compared; the textbook version (ranked and budgeted) is a later CR (§8). Everything else open is unchanged and stays in `docs/OVERNIGHT_HANDOFF_2026-10-27.md` §3. `CLAUDE.md` overrides this file if they conflict.

## 0. Rules for every agent tonight

- Branch `cr-064-choice-step` (mainline `master`). No `git add -A`, `.` or `-a`: stage by path; untracked owner files under `data/gold/` stay untouched. Never push, never merge to `master`.
- Cost rule (rule 7): `--dry-run`, then `--limit 2`, then the full 20 papers. Per-arm cap **$1.5** (the pre-registered cap). Stop an arm and write why if its dry-run estimate passes the cap.
- Pre-register before computing: the rules below are written into `DECISIONS.md` and committed (Phase 0) before any call that could show a result. Do not edit a profile, prompt or rule after its arm has produced results; create the next version.
- New switches default to today's behaviour; every earlier run must replay byte-identically (run the existing `tests/test_cr064.py` before and after any code change).
- Same 20 first-set papers (`first_set()`), headline overlap `IDXR1OV-P1` relation F1, strict `IDXR1-P1` beside it. Train/dev only; the 37-paper confirmation is **not** run tonight (owner, 2026-11-01).
- Reproducibility note for the report: R8 is the reference arm (overlap relation F1 0.264, strict 0.197, spend $0.727). Registry `relations_scinlp_v1.0.4`, profile v18.

### 0.1 Owner fills in before starting

| Item | Value |
|---|---|
| Budget for tonight (suggested $8.00 = five arms at the $1.5 cap, plus margin) | _(owner)_ |
| Without a value | do only the $0 steps (Phases 0, 1 and the dry-runs) and stop |

### 0.2 Context from the pair-recall investigation (2026-11-03, $0, commit `ed26654`)

Read this before judging A2 and A4. Report: `reports/cr064/pair_loss.md`, generator `uv run python -m cumap.cr064.pair_loss` (set `CUMAP_MATCHING=r1key`, the mode the runs recorded). On the 57 development papers of v5 every built pair was classified (4,977 of 4,977; no paper hit the budget), yet 147 of the 737 gold relations whose two mentions were extracted never reached the classifier:

| cause | n | what it means for tonight |
|---|---|---|
| splitter cut at an abbreviation ("et al.", "e.g.", "i.e.", "vs.") | 72 | **A2's target.** The plain splitter cuts after every `. ! ?`, so the two concepts land in different pipeline sentences although the SciNLP gold relation is within one sentence. `split_sentences_abbrev` joins all 72 in a $0 check. |
| other cut inside the sentence | 4 | not fixed by A2; look at them if time allows |
| both gold mentions are one concept in the built graph | 64 | no pair of two concepts exists; **no arm can recover these** |
| two distinct concepts in one sentence, no candidate built | 7 | unexplained (the final concept list differs from the one the pairs were built from in 119 of 4,977 pairs) |

Consequences for the arms:
- Pair Recall has two denominators. Mention level (CR-043 scorecard, `pair_recall_analogue`): 590 / 737 = 0.801 (first 20: 220 / 258 = 0.853; other 37: 370 / 479 = 0.772). Concept-node level (CR-058 funnel, `pair_selected` / `endpoints_placed`): 590 / 673 = 0.877 (first 20: 220 / 252 = 0.873; other 37: 370 / 421 = 0.879). The report's Table 4 and Appendix C use the **concept-node** definition (owner, 2026-11-03). Report both for every arm; never mix them in one table.
- A2 can raise Pair Recall by at most 72 of 737 (about 0.10 at mention level). Expect its extra classifier cost to come from those pairs plus longer evidence sentences across citations.
- A4 (neighbouring sentences) would also recover the splitter-cut pairs, so a gain in A4 over R8 is partly the same 72 pairs; compare A4 with A2 as the base, not with R8, before crediting the neighbour rule.
- Hierarchy F1 is now `A1-DIR` (owner, 2026-11-03; `DECISIONS.md`): subclassOf and subtaskOf scored as one class, direction only. Use it in every arm table, with the label-strict figure beside it. Development baseline: 0.146 (19 / 95 / 127; paper-bootstrap 95% 0.08 to 0.22; first 20 papers 0.132, other 37 papers 0.156); report `reports/cr064/hierarchy.md`. With 7 hits on the first 20 papers, differences between arms there are within noise.

## 1. Order of work

```
Phase 0  (sequential, $0)   preflight + pre-register A4/A5, commit
   |
   +--> Phase 1A (agent A, main tree)        Phase 1B (agent B, git worktree)
        run A1, A2, A3 in parallel ($)       build A4/A5 code, tests, profile builder ($0)
   |                                                |
   +------------------------+-----------------------+
                            v
Phase 2  (sequential, $0)   verdicts A1->A2->A3, merge 1B branch, choose base arm
                            v
Phase 3  (parallel, $)      A4 and A5 on the chosen base (two processes)
                            v
Phase 4  (sequential, $0)   report, oracle ladder, PROGRESS/DECISIONS, tests, commit
```

Why this shape: A1, A2 and A3 are separate profiles and separate run ids, so their runs are independent and go in parallel; only their **verdicts** are chained. A4 and A5 need the winning base, so they wait for Phase 2, then go in parallel with each other. Agent B works in its own worktree because it edits `cooccurrence.py` / `relations.py` / `mentions.py` while agent A runs the same code.

## 2. Phase 0 · Preflight and pre-registration (sequential, $0)

1. `git status`, `uv run pytest -q`, `uv run ruff check .`. Record the numbers. Check what already exists: `data/processed/kg/cr012_scinlp_cr064relA1_*` and `..A2_*` directories are present (20 each). Open one `checkpoint.json` and state whether they are only the `--build-only` rebuilds ($0) or have `relation_results_v3` filled. If filled, do not rerun that arm; score it.
2. Confirm A1–A3 approval gate: `approved("a1")` passes (registry patch `CR-064-relations-scinlp-v1.0.4-drop-partOf.yaml` approved by the owner on 2026-11-01).
3. Append to `DECISIONS.md` (entry dated 2026-11-03, written BEFORE any run) the A4/A5 definitions and rules in §5 and §6, plus the base-choice rule in §4. Commit by path. Create the sub-branch for agent B: `git branch cr-064-a4a5 && git worktree add ../h420020-mapper-a4a5 cr-064-a4a5`.

## 3. Phase 1A · A1, A2, A3 (agent A, main tree)

Definitions are in the 2026-11-01 entry (A1 `cooccurrence: all`; A2 = A1 + `sentence_split: abbrev`; A3 = A2 + `declined_pass: v13`). Do not change them.

1. `$0` dry-run each: `uv run python -m cumap.cr064.arm_relations --arm a1 --dry-run` (then `a2`, `a3`). Record candidate-pair counts against R8's `selected_pairs` per paper; this tells the extra cost. For A2 also record how many of R8's P0 relations (gold relations with both mentions extracted whose pair was never built; `sc_attribution` code `P0`) now have a candidate pair; §0.2 expects up to 72 of 147 across the 57 development papers, so a smaller number on the 20 first-set papers is normal, but zero means the splitter switch did not take effect. If any arm's estimate is above $1.5, stop that arm and report.
2. `--limit 2` for each arm (`--arm a1 --limit 2 --cap-usd 1.5`, same for a2, a3). Look at 2 outputs per arm: `~s` ids present, no crashes, `second_pass` rows present for A3.
3. Full runs, three processes at once (separate terminals or background jobs): `--arm a1`, `--arm a2`, `--arm a3`, each with `--cap-usd 1.5`. Wait for all three. Do not start Phase 2 until all three finish or hit their cap (a capped arm is reported as capped, not as a result).

## 4. Phase 2 · Verdicts and base choice (sequential, $0)

1. Score the three arms with the existing scoring path used for R-arms (`reports/cr064/arms_all.{json,md}` generator; extend its arm list, do not change the scoring).
2. Verdicts, pre-registered in the 2026-11-01 entry: A1 vs R8, A2 vs A1, A3 vs A2; "helps" = overlap relation F1 ≥ previous + 0.005; also report each vs R8. Chain rule: a step that does not help is still carried into the next arm; the next verdict is also stated against the last arm that helped.
3. **Base-choice rule for A4/A5 (pre-registered):** the base is the arm with the highest overlap relation F1 among R8, A1, A2 and A3. If two are within 0.005, take the one with fewer switches (R8 < A1 < A2 < A3). Write the choice and the numbers in `DECISIONS.md` before Phase 3 starts.
4. Merge agent B's branch into `cr-064-choice-step` (`git merge --no-ff cr-064-a4a5`), run `uv run pytest -q`; if it fails, stop and report, do not start Phase 3.

## 5. Phase 1B · Build A4 and A5 (agent B, worktree `../h420020-mapper-a4a5`, $0, runs alongside Phase 1A)

All changes default to today's behaviour. Do not run any paid call here. Also do not touch `data/gold/`.

### 5.1 A4 · neighbouring sentence (`cooccurrence_window: 1`)

**Question:** does letting a pair span two consecutive sentences recover relations the same-sentence rule cannot see? Today a pair needs both concepts in one sentence (`DEFAULT_SENTENCE_WINDOW = 0`); the sentences around it reach the classifier only as background.

**Definition.**
- New profile key `cooccurrence_window` (default `0`; allowed `0`, `1`). `1` requires `cooccurrence: all` (raise a clear error otherwise).
- Keep every same-sentence candidate exactly as the base builds it. Add **window candidates**: for each section, each i, each concept pair (x, y) with x mentioned in sentence i and y in sentence i+1 (or the reverse). Skip the pair at (i, i+1) if x and y both occur in sentence i, or both occur in sentence i+1 (already candidates). Use the base's `sentence_split`.
- Candidate: `sentence` = `sentences[i] + " " + sentences[i+1]` (whitespace as in the source); `pair_id` = `RP-<section>-<n>~w<i>`; one candidate per (pair, i). No window candidate crosses a section boundary. A concept in sentence i is therefore paired with concepts in i-1, i and i+1 (the i-1 pairs are the window (i-1, i)). Owner rule (2026-11-03): neighbouring sentences are paired only with the target sentence. Two concepts that appear only in i-1 and i+1 are never paired with each other, and two concepts that both sit in the same neighbouring sentence are not paired by that window (they are paired when that sentence is itself the target).
- **Do not use the legacy `window` argument** of `enumerate_candidates` (it keeps only the earliest sentence as the pair text). Leave it unchanged so older runs replay; add a test that its output for `window=1` is untouched.
- **Fields for later ranking (textbook).** Fill `cue_score` (a relational cue word appears in the passage, same rule as `enumerate_candidates`) and `cooccurrence_count` (number of (i, i+1) windows in the section where the pair occurs) on every window candidate, so the existing ranking `(-cue_score, -cooccurrence_count)` and the textbook selector in `pair_selection.py` can rank them without change. Tonight nothing is ranked or cut (`pair_budget: all`).
- Implement as `window_pairs(...)` in `src/cumap/expert_kg/cooccurrence.py`, called from `build_pairs` when the key is 1. Extend the places that read `"~s"` in a pair id (grep `"~s"`, for example the primary-pair filter in `build_pairs`) so `~w` ids are handled, and `reselect_stage` records `window_pairs` in `selection_stats`.
- **Prompt.** Open `prompts/relation_family/` (version used by the profile) and `prompts/relation_choice/v11.md` and check where they say "the sentence". Create `relation_choice` v14 (v11 untouched) and, if the family prompt has the same wording, the next `relation_family` version: only the wording changes, "Sentence" becomes "Passage (one sentence, or two consecutive sentences)", and the relation must be stated by the passage, the evidence quote copied from the passage. Add `choice_prompt: v14` (and the family key) to the A4 profile.
- **Evidence check.** Confirm by a test that the existing quote check accepts a quote that crosses the sentence boundary and rejects one not in the passage. Do not loosen any check; if it fails, stop and report.
- **Profile builder.** A script `python -m cumap.cr064.make_profile --base <arm> --add cooccurrence_window=1 --out configs/scinlp_profile_v23.yaml` that copies the chosen base profile's YAML and adds only the listed keys plus `status`. (Same script is used for A5, so only the chosen base differs at run time.) Register `"a4": ("cr064relA4", configs/scinlp_profile_v23.yaml)` in `ARMS`, `PATCHES` (same patch as R8) and `BUILD_ARMS` in `arm_relations.py`.

**Report split (needed to read the result):** results are reported for same-sentence candidates and window candidates separately (the v14 wording applies to both, so a change in the same-sentence part is the prompt effect, and the window part is the window effect).

### 5.2 A5 · nested mentions (`mention_spans: nested`)

**Question:** with names and aliases kept on the node, does counting a concept mentioned inside a longer concept name ("bit" inside "bit rate") as a mention add real candidate pairs? Rule 17 (longest-match, non-overlapping) is reversed **for candidate-pair enumeration only** in this arm; concept mentions, propagation, spread, first occurrence and all scoring stay longest-match.

**Definition.**
- New profile key `mention_spans` (default `longest`; allowed `longest`, `nested`).
- `MentionMatcher.find_all(text)` in `src/cumap/expert_kg/mentions.py`: every vocabulary match at every start token and every length, overlapping and nested allowed. Both modes: `token` (walk the trie from each start and keep every node with `"\0"`) and `r1key` (for each start token and each window length up to `self._max`, keep every hit that passes the existing checks: article start, short key, acronym guard). `find` is unchanged.
- `sentence_mentions` (in `relations.py`) uses `find_all` when the profile says `nested`, and returns, per concept, the sentence indices **and** the character spans.
- A pair (x, y) is a candidate in a sentence only if some occurrence of x and some occurrence of y have **disjoint** character spans (so "bit" and "bit rate" from the same words do not pair with each other, but "bit" and "latency" do, even when "bit" appears only inside "bit rate"). Ranking, ids, the splitter and the `cooccurrence` rule are unchanged; the pair's earliest qualifying sentence stays the primary.
- Pair candidates come out of a new function `enumerate_candidates_nested` or an argument of `enumerate_candidates`, not by editing the default path.
- Profile: `configs/scinlp_profile_v24.yaml` from the same builder (`--add mention_spans=nested`). Register `"a5": ("cr064relA5", ...)`.

### 5.3 Tests and a $0 candidate-universe check (both arms)

- `tests/test_cr064.py` additions (mock backend, no network): window candidate built only across i/i+1; skipped when a same-sentence candidate exists; ids carry `~w`; section boundary respected; `find_all` returns "bit" and "bit rate" for "the bit rate" while `find` returns only "bit rate"; disjoint-span rule excludes the nested self-pair; defaults leave earlier selections byte-identical (compare with a stored R8 `selected_pairs` fixture).
- `$0` build for the 20 papers with the **R8 profile as a stand-in base** (the real base comes later): number of candidates vs R8, and the share of gold relations whose pair is newly a candidate (use the oracle module's "pair selected" stage, `cumap.cr064.oracle`). Write it to `reports/cr064/a4a5_universe.md`. Evaluation only; nothing from gold goes into code or prompts.
- **Budget versus pair-recall curve ($0, informs the textbook ranking).** For the base's candidates and for base + A4 window candidates, rank all pairs of each paper by the existing rule `(-cue_score, -cooccurrence_count, pair_id)` and report gold-pair recall (within the candidate universe, stated as such) when only the top 10%, 25%, 50%, 75% and 100% are kept, plus recall per candidate (precision of the pool). Write it to `reports/cr064/a4_budget_recall.md`. Gold is used for evaluation only; the ranking rule is not tuned on it. This is the first measurement of the budget/recall trade-off the textbook will face.
- `uv run pytest -q` and `uv run ruff check .` clean on the sub-branch; commit by path. Report back the commit id.

## 6. Phase 3 · A4 and A5 (parallel, after Phase 2)

Pre-registered (written in Phase 0): each arm is judged against the **base**; "helps" = overlap relation F1 ≥ base + 0.005; strict beside; also report versus R8. Reported for each arm: concept-pair candidates, pair-selected gold, family / choice losses (oracle ladder), precision cost (overlap relation P and R), spend, and (A4) the same-sentence versus window split. If both arms help, the combination (A4 + A5) is **not** run tonight; flag it for the owner.

1. Build both profiles on the chosen base: `make_profile --base <base> --add cooccurrence_window=1 --out configs/scinlp_profile_v23.yaml` and `--add mention_spans=nested --out configs/scinlp_profile_v24.yaml`.
2. `$0` dry-run each (`--arm a4 --dry-run`, `--arm a5 --dry-run`): candidate counts per paper. **Stop an arm and report if its candidates are more than 2.5 times the base's or its estimate is over $1.5.**
3. `--limit 2` each; read 2 outputs per arm (A4: a `~w` row with a two-sentence quote; A5: a pair that exists only through a nested mention).
4. Full 20-paper runs, two processes at once, `--cap-usd 1.5`.

## 7. Phase 4 · Report and close (sequential, $0)

1. Add, for every arm, Pair Recall in both denominators (§0.2) and Hierarchy F1 `A1-DIR` (label-strict beside it) to `arms_all`; extending `cumap.cr064.pair_loss` to take a run tag is the $0 way to show where each arm's remaining misses go. Regenerate `reports/cr064/arms_all.{json,md}` with A1–A5 (extend the arm list only), plus `oracle_cr064relA*.md` for each arm (`cumap.cr064.oracle`).
2. `DECISIONS.md`: one results entry per arm, each stating the verdict, the numbers, the base, the spend and the dataset (20 first-set papers, SciNLP commit `e78342be`). `PROGRESS.md`: a CR-064 section with the verified numbers. Failures and capped arms are written as such.
3. `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`. Record counts. Commit by path with the attribution trailer. **No merge to `master`, no tag, no push**; the CR stays open for the owner's review and the 37-paper confirmation decision.
4. Remove the worktree (`git worktree remove ../h420020-mapper-a4a5`); keep the `cr-064-a4a5` branch.

## 8. Not tonight

- 37-paper confirmation of the best arm (owner has not asked).
- Any adoption of a CR-064 arm as the SciNLP default.
- Adding the concept-node Pair Recall beside `pair_recall_analogue` in the CR-043 scorecard (asked, owner has not answered). The report text already uses the concept-node definition.
- **The textbook (P&D) version of A4.** Intended direction (owner, 2026-11-03): candidate pairs come from the same sentence and the neighbouring sentences, and a ranking is applied to trade budget against pair-recall because the pool is too large to classify (8,604 unique same-sentence candidate pairs for P&D chapters 1-3 in the production run `slice3_c2`, against a selected 1,100). Textbook work has barely started, so this needs its own CR with its own pre-registration after A4's SciNLP result and the budget/recall curve. Tonight's code is written so that `build_pairs` and the pair fields can be reused, but the textbook budget, coverage phase and ranking in `pair_selection.py` and `cr012/budget.py` stay untouched.
- The open items in `docs/OVERNIGHT_HANDOFF_2026-10-27.md` §2–§3.

## 9. Execution log (append one row per phase)

| Phase | Agent | Commit | Tests passed | Spend | Status / notes |
|---|---|---|---|---|---|
| 0 | | | | | |
| 1A (A1, A2, A3) | | | | | |
| 1B (A4/A5 build) | | | | | |
| 2 | | | | | |
| 3 (A4, A5) | | | | | |
| 4 | | | | | |
