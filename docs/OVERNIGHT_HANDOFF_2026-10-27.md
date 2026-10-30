# Overnight handoff (2026-10-26 to 2026-10-27)

Written for: the project owner, and the execution session that picks this work up. It reports state and queued work; writing it changed no code, config or data, and nothing under `data/gold/` was touched. It replaces `docs/OVERNIGHT_HANDOFF.md` (2026-10-22/23) as the list of open work. That file stays as the record of T1-T14; its §0.2 (how to do one task) and §0.5 (what a task must not include) still apply and are not repeated here.

## 0. Instructions for the executing agent

- **Rules first.** `CLAUDE.md` overrides this file if they conflict.
- **Budget and merge permission are not set for tonight.** The 2026-10-23 grant ($20, merge after tests pass) was for T1-T14. Until the owner writes tonight's budget and merge permission in §0.1, do only the $0 tasks, do not merge, and leave each branch for review.
- **No `git add -A`, `.` or `-a`.** Stage by path; `data/gold/` and other untracked owner files stay out. Never push.
- **Cost rule (rule 7):** `--dry-run`, then `--limit 20` (or 2 papers first), then the full run. Stop and ask if an estimate passes `max_usd_per_command`.
- **New switches default to today's behaviour.** Older runs must replay byte-identically.
- **Pre-register before computing.** Write the rule into `DECISIONS.md` and commit it before the first call that could show the result.

### 0.1 Owner to fill in before the session starts

| Item | Value |
|---|---|
| Budget for tonight | _(owner)_ |
| Merge permission (`--no-ff` after pytest + ruff) | _(owner: yes / no)_ |
| Task order override | _(owner, optional)_ |

## 1. Repository state (checked 2026-10-26)

| Item | State |
|---|---|
| Branch | `cr-057-recall-view-hints-artefacts` (HEAD `a253ddb`); mainline is `master` |
| Uncommitted tracked changes | `src/cumap/concepts_v4/loop.py`, `src/cumap/cr043/run.py`, `tests/test_cr057.py` (11 lines added, 2 removed in total). Not reviewed in this session; look at `git diff` before touching them |
| Untracked, owner-owned | `data/gold/` has `cr015_pd_pilot_gold_draft.csv`, `cr021_rejected_links_review_marked.csv`, `cr050_identity_sheet_marked.csv`, `iir_fp_audit_blind.csv`, `lexicon_intake_slice3_c2.csv`, `pd_concept_pilot_blind.csv`, `pd_concept_test_blind.csv`, `scinlp_hier_identity_sheet_marked.csv`, and a stray `h420020-mapper.code-workspace`. Code must not add, move or delete them |
| Untracked, other | `data/interim/cr012/units/{4.1 … 9.2}/`, `data/interim/sleep/*.pkl`, `reports/OVERALL_FINDINGS_CR001-CR014.md`, `reports/cr043/cr057m7*.{json,md}`, root `h420020-mapper.code-workspace` |
| Tests / lint | not re-run for this handoff |
| Production, new P&D runs | registry v1.5, qualifier amendments v6 and qualifier checks v1 on, lexicon v0.5, adjudicator on `gpt-6-sol`, backfill off, luna profile |
| Production, new SciNLP runs | profile v5 (prompt `v5_scinlp`, arm B, all pairs), registry `relations_scinlp_v1.0.1` |
| Still off / not adopted | `identity_resolver` (default `legacy`), `identity_judge` (`off`), `misconception_source` (`legacy`), `assembly` (`legacy`), registry v1.6, SciNLP profile v6 (undecided, T2) |

## 2. Tasks for tonight

| # | Task | Cost | Needs |
|---|---|---|---|
| T1 | Finish CR-057: review the uncommitted diff, record the M7 result, then run the unseen check | $0, then about $2.5 (cap $4) | the §0.1 budget for the paid part |
| T2 | Decide profile v6 from the M7 numbers, by the rule already written in `DECISIONS.md` | $0 | T1 |
| T3 | **Tune the identity-search offer threshold (0.6)** as a new CR: design and pre-registration only unless the owner supplies labels | $0 | owner choice in §2.3 |
| T4 | Housekeeping on the open follow-ups that need no decision (§3.D) | $0 | none |

### 2.1 T1 · Finish CR-057

CR-057's pre-registration is in `DECISIONS.md` (2026-10-26). Four steps; step 1 is done.

1. **Recall views:** done ($0). `IDXR1X-P1` and `IDXR1N-P1` are in every CR-043 scorecard.
2. **M7 hint (profile v6):** the arm ran as `cr057m7` and `cr057m7b`. `reports/cr043/cr057m7b.md` shows concept recall (`IDXR1-P1`) 0.767 and strict relation F1 0.146, against the adopted `cr055ballp` at 0.751 and 0.153. The recall gain (+0.016) clears the +0.01 bar, and the relation F1 fall (−0.007) is larger than the 0.005 the rule allows. I have not found a PROGRESS or DECISIONS entry that records this, and I do not know what differs between `cr057m7` and `cr057m7b`: check that before recording anything. If `cr057m7b` is the intended arm, the rule says v5 stays.
3. **PDF artefacts:** no matching-key change; handled by the head-stripped nested view (already in the decision).
4. **Unseen check (not run):** the 37 train papers in `cumap.cr043.papers.rest_set`, never used to develop CR-053 to CR-057. Run the adopted profile as `cr057rest` and the earlier v3 (prompt `v5_scinlp`, D3 budget) as `cr057rest_v3`; 2 papers first. Report every objective and recall view for both. **Check:** if the adopted profile's strict relation F1 or concept recall is below v3's, flag the adoption and restore v3 as the default pending the owner.

Docs: a `PROGRESS.md` CR-057 section with the verified numbers, and a `DECISIONS.md` result entry. Then commit by path, merge and tag `cr-057-complete` only if §0.1 allows it.

### 2.2 T2 · Profile v6 decision

Follows from T1 step 2. Do not edit `configs/scinlp_profile_v5.yaml` or v6 to make the rule pass; the rule was fixed before the run.

### 2.3 T3 · Tune the identity-search offer threshold (0.6)

**Background.** `search.offer_threshold: 0.6` in `configs/identity_rules.yaml` (and `DEFAULT_SIMILARITY_THRESHOLD = 0.6` in `src/cumap/expert_kg/canonicalize.py:36`, from CR-005) decides which registry candidates reach the LLM identity judge. It is a retrieval gate: below it no LLM call is made. It has no tuning record; the config comment says "reported as is, never tuned on measurement data", and CR-035 lists "tune the 0.6 threshold" under rejected alternatives for that reason. The 0.70 review band is separate and is not an identity threshold (CR-011 ruling); 0.6 is retrieval only.

**Why it is worth tuning.** The CR-035 replay on `slice3_c2` measured candidate recall (true match in the top 5 and ≥ 0.6) on the 45 evaluable owner-marked `same` pairs: legacy 24, `u1` 37 (8 of the 45 have no concept in the run). A pair missed here never reaches the judge. A lower threshold sends more candidates to the strong-tier judge, which costs calls.

**Rules for the study (so it does not break the repo's own constraints):**
1. New CR on its own branch from the mainline. Log a `DECISIONS.md` entry that supersedes the "rejected: no tuning" line for this threshold only, and says which labelled data may be used for tuning.
2. **Separate the tune set from the report set.** The 45 pairs behind the CR-035 number are measurement data: do not tune on them and then report on them. The sealed sets (SLEEP-240, SLEEP-POS) stay sealed. Two ways to get a tune set; **the owner chooses** (§2.3 decision below):
   - **(a) a new blind sample** from `slice3_c2` for the owner to mark (👤, never invent gold). Code writes it to `data/interim/suggestions/`. Also useful as a fresh held-out set for the identity-judge measurement (§3.A item 9);
   - **(b) a split of the existing marked pairs by chapter**, tuning on one part and reporting on the other. Cheaper, but about 45 positives is small: report confidence intervals and say so.
3. **Objective (pre-register it):** the smallest threshold whose candidate recall of true `same` pairs reaches a target (suggest 95%), subject to the extra judge calls it adds, which are reported per threshold. Precision is the judge's job; the review band and the lexicon `different` veto still sit behind it. Sweep 0.40 to 0.80 in steps of 0.05, and sweep `top_k` (now 5) with it, or fix it and say so, because the two interact.
4. **Negatives.** The historical labelled set has few negatives (CR-011 notes: 86 pairs, 15 negatives, plus 21 lexicon `different`; I did not re-count them). With few negatives you can tune only for recall, and the report must say so.
5. **Run it as a $0 replay.** Embeddings are cached (as in the CR-035 replay); no model call. If a paid judge run is wanted afterwards, it needs the §0.1 budget and rule 7.
6. **Adopt as config, not code.** A new value in `configs/identity_rules.yaml` for new runs only; older runs and frozen replays keep 0.6. Record the threshold in each run's metadata, and never compare results across thresholds without naming them (same logic as rule 35). The threshold only takes effect where the search runs: `identity_resolver: u1` (default `legacy`) or the legacy `canonicalize` call. State which path the study covers.
7. **Report:** candidate recall and extra judge calls per threshold, with intervals, as a generated report under `reports/` (reports are produced by scripts).

**Owner decision needed:** tune set (a) or (b); and whether the goal is recall or judge-call cost. Without an answer, the executing session writes only the pre-registration and the replay script, runs nothing, and stops.

### 2.4 T4 · Housekeeping with no decision needed

All $0 and independent of T1-T3:
- the `surface_phrase_long` flag fires 128 times on `slice3_c2`; review its threshold before using it for anything but review (CR-045 open item);
- the explorer scorecard and the presentation metric definition for `HIER-T1` / `FACT-C1` still show the older definitions (CR-042 open item);
- re-run `uv run pytest` and `uv run ruff check .` on the mainline and record the numbers in `PROGRESS.md`.

## 3. Leftover items from the previous handoff

Source: `docs/OVERNIGHT_HANDOFF.md`. Status is as of 2026-10-26, taken from `PROGRESS.md` and `DECISIONS.md` (CR-041 to CR-057). "No record found" means I did not find a later entry; confirm with the owner before treating it as still open.

### 3.A Owner decisions still open

| # | Item (previous handoff §) | Status |
|---|---|---|
| 1 | **CR-018 boundary audit** (§3.1). Paused at STOP 2 (`AWAITING_HUMAN_ANNOTATOR`). Needs the human to fill `data/interim/checks/cr018/boundary_audit_blind.csv` (120 families / 480 spans, about 2.5 to 3.5 h, no model help), plus Research decisions D1 to D6 in `reports/cr018/STOP1_RECONCILIATION.md` §8 on branch `cr-018-boundary-identity` (not merged). Previous recommendation: D1 (iii) with B1 primary, D5 approve $8, D4 (i). STOP 3 must not start without them | no record found of any decision |
| 2 | **Same-settings re-run of `slice3_c2`** (§3.2), about $8, to separate the CR-020/021 change from run-to-run variation. Would now also use the luna profile, a third change | no record found; `slice3_c2` stays production |
| 3 | **Model comparison on the locked test split** (§3.2b). CR-025 used SciNLP dev only. Needs the owner to lift the test lock; final reporting only (rule 9) | no record found |
| 4 | **CR-022 Part B** (§3.3): paid registry transfer, dev cap $10. The mapping now comes from registry v1.4, so the only question is whether to run it | no record found |
| 5 | **Adopt registry v1.4 / v1.6 as default** (§3.4). v1.4.1 (owner-approved wording) exists; v1.5 is the P&D default since CR-047; v1.6 failed its rule in CR-048 and stays off. Whether v1.4.1 should become the base for SciNLP beyond `relations_scinlp_v1.0.1` | partly resolved by CR-046/047; confirm the rest |
| 6 | **CR-026 caveat** (§3.6): calls with `allow_escalation=False` (for example the concept generator) never reach sol, so some stages that ran on sol before now stay on luna. Accept, or list the stages that keep sol | no record found |
| 7 | **Report wording** (§3.7). Objective O2 says "constituent concepts" but the hierarchy scorer uses only `is_a`; the O5 strict-edge text does not say endpoint concept types must also match; the supervisor deck's timeline dates are estimates | no record found |
| 8 | **Switch on/off** (CR-044 open): `identity_resolver` (recommended `u1` after the judge measurement), `assembly` (recommended `legacy` for now), `identity_judge`. `qualifier_checks` is on (CR-045) | `identity_resolver`, `assembly`, `identity_judge` still awaiting the owner |
| 9 | **Identity judge** (CR-049/050/051). The production adjudicator on luna fails its bar (same precision 0.667, LB 0.467); sol fixes it partly (0.783, LB 0.581, adopted for new runs in CR-051). Judge v1 is better but its lower bound 0.535 is below the 0.70 rule. Open: adopt v1 by a rule change, or keep sol; and a held-out set that has not been used before | the CR-021 held-out split has been looked at twice; a fresh sheet was used once (CR-050). Tonight's T3 option (a) would also give a new set |
| 10 | **Misconception family** (CR-048): failed its rule (items 0/4, P&D macro F1 0.781 → 0.505) and stays `legacy`. Refinement ideas are in `DECISIONS.md`; whether to pursue them is the owner's call. The §14 coverage concern (relation classifier sees ~15% of pairs) is still unaddressed | open |
| 11 | **Domain-matched pruner** (§4): train P1 on the 10 exposed P&D sections with model-generated gold, bank/CSO features wired in, leave-one-chapter-out, CR-009 τ rule. Development replay is $0; sealed sections 5.2, 6.5, 9.1, 9.4 stay sealed. Not started, draft offered | no record found |
| 12 | **Lexicon intake, next round** (§9). `cumap lexicon intake` exists (CR-029); v0.5 is production. Next sheet is built after the next production rebuild or when the owner asks | on request |

### 3.B Deferred builds (decided in principle, not built)

| # | Item | Notes |
|---|---|---|
| 1 | **CR-028 online identity extension** (§7 "Extension") | Input B per section; incremental occurrence index (reuse `cr019/occurrences.py`, positions only, rules 24 and 35); bookkeeping kept current from the index; deterministic name refresh with `name_history`; remove `slice_rerun.finish_concepts` from new runs only after a measurement run shows the online result equals it (first chapter and roles for every concept). Keep it for `legacy` replays. Plan steps 1-9 are in the previous handoff §7 |
| 2 | **Input C of the resolver** (§7, §8 step 2) | The `same_concept` queue reader exists (CR-029) but has no production consumer; wiring it into the resolver was not done |
| 3 | **Judge measurement before `identity_resolver: u1`** (§7 step 8) | Partly done as CR-049/050; the pre-registered held-out step is open (item A9) |
| 4 | **Assembly v2 adoption** (§12) | `assembly: v2` is built (CR-036) and defaults to `legacy`. Open: readers that assume one edge per pair (`report/data.py`, `kg_explorer.py`, organisation view, scorers); per-occurrence classification so several relations per pair can appear |
| 5 | **Option C: stage-wise relation classification** (§11) | An idea, not a plan. Cheap family step on every candidate pair (8,604 for chapters 1-3, about $1 on luna), budget applied to choice and qualifiers. Ten open questions (triage recall on the 600 CR-010 pairs, precision, selection, budget, batch API, `triaged_out` records, pool order, measurement, several relations per pair, the 50-pair measurement sample). CR-056 adopted all pairs for SciNLP, which is related but separate |
| 6 | **Batch API** (`CLAUDE.md`) | Not built; wait for a real bulk workload, ideally Option C |
| 7 | **Domain/range rejections** (§10 "Related") | 58 in `slice3_c2`, many apparently true statements. Needs an owner sheet and a registry change |
| 8 | **`trades_off_with` cleanup** (§10 change 6) | Remove it from `DIMENSION_RELATIONS` in `relations_v3.py` once no saved run needs it |
| 9 | **Downstream readers of the narrower modality set** (§10 change 7) | `report/data.py`, `kg_explorer.py`, `misconception.py`, `gold_editor.py` must accept the narrower modality set and a missing `dimension` qualifier; confirm they were checked in CR-047 |
| 10 | **Docs/code mismatch 3** (§4) | `loco_pruners` builds `P1Model` without a bank or CSO, so two features are always 0. Fixing it changes behaviour, so it needs a CR (ties to item A11) |
| 11 | **Presentation deck edits** | Remove the "Discourse links" box from stage 5 (CR-030); update stage 4 to "save graph" (CR-036); update metric definitions (CR-032/033) |

### 3.C Reminders (no plan yet)

- **Review the whole evaluation pipeline, starting with how concepts are scored** (§17): score concepts as concepts, not spans; name or boundary-tolerant matching instead of exact span; partial credit as a diagnostic; splits and merges counted separately; knock-on effects on Hierarchy F1, Pair Recall, Relation Macro F1 and Strict E2E; decide the rule once for the whole pipeline. Any change is a new, named scorer variant beside the frozen numbers, pre-registered, validated on train/dev first, with a determinism gate. CR-052 and CR-056 added span-extension and nested-placement views (`IDXR1X-P1`, `IDXR1N-P1`); these are recall views, not the review.
- **Stage-wise relation classification (Option C)**: see B5.
- **Several relations per concept pair** (§11 item 9, §12): P&D gold has 3 of 118 pilot pairs and 15 of 417 test pairs with more than one true relation; selection currently keeps one sentence per pair.

### 3.D Follow-ups with no decision needed

Listed in §2.4 (they are also the leftovers from CR-042 and CR-045).

### 3.E Closed since the previous handoff (for reference; do not redo)

| Previous item | Closed by |
|---|---|
| T1-T14 execution tasks | merged 2026-10-23, tags `cr-027-complete` to `cr-040-complete` |
| §3.5 CR-023 paid comparison | closed without the run (D-6) |
| Owner review of the CR-037/038/039/040 drafts | owner approved the drafts (recorded in CR-044); v1.4.1 built (CR-046) |
| Lexicon intake sheet marks | v0.4 (CR-041), v0.5 (CR-044) |
| SciNLP identity sheet marks | CR-042: `HIER-T1` with real identity |
| Qualifier code checks on | CR-045 |
| Qualifier amendments and registry v1.5 | CR-046, CR-047 |
| Misconception family measurement | CR-048: not adopted |
| Identity judge v1/v2 measurement | CR-049, CR-050: not adopted; adjudicator on sol adopted in CR-051 |
| SciNLP concept-span and recall work | CR-052 to CR-056 |

## 4. Execution log (append one row per task)

| Task | Branch | Merge commit / tag | Tests passed | Spend | Status / notes |
|---|---|---|---|---|---|
| T1 | | | | | |
| T2 | | | | | |
| T3 | | | | | |
| T4 | | | | | |
