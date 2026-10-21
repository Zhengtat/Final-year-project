# CR-022 — SciNLP hierarchy and relation scoring, and registry transfer

**Status:** Part A approved 2026-10-21 (owner, overnight instruction); Part B not approved. Branch `cr-022-scinlp-hierarchy-scoring` (from `cr-018-boundary-identity`; re-base later at the owner's choice).
**Branch:** to be decided at approval: `cr-018-boundary-identity` (precedent of CR-019 to CR-021, CR-018 paused at STOP 2) or `cr-022-scinlp-hierarchy-scoring` from `main` once CR-018 is merged. Tag `cr-022-complete` when merged.
**Scope:** evaluation and reporting. Part A changes no model behaviour, extraction, pair selection, relation semantics, canonicalisation or frozen artefact ($0). Part B is an optional, paid, experimental run under new run ids; it changes no production default.

---

## 1. Problem

The SciNLP headline reports three of the five CR-017 metrics. Two are missing:

| Metric | SciNLP status today | Reason |
|---|---|---|
| Ancestor Hierarchy F1 | `NOT_SUPPORTED_NO_IDENTITY_GOLD` | SciNLP gold is mention-level with no identity clusters; ancestor closure needs concept nodes (CR-017 hierarchy audit). CR-012 ruling D2 forbids inferring identity from strings for the headline. |
| Relation Macro F1 | `NOT_COMPUTED` | Not wired for the SciNLP schema in `cr017/replay.py`. |

The SciNLP gold does contain hierarchy and typed relations (frozen release `SciNLP-repo-e78342be`, counted 2026-10-19):

| Split | Docs | Relations | subclassOf | subtaskOf | Labels (support) |
|---|---|---|---|---|---|
| dev | 6 | 179 | 8 | 12 | 11 labels, 7 to 36 each |
| test | 3 | 295 | 31 | 15 | 11 labels, 8 to 75 each |

A second gap: every SciNLP run uses the benchmark-local registry (`configs/relations_scinlp.yaml`). The networking registry (`relations_v1.3.yaml`) that the student phase will use has never been scored against independent relation gold.

## 2. Part A — rescoring ($0, no model call)

Inputs, read-only and hashed before and after (rule 31 practice): the frozen SciNLP dev and test runs at E0, E1, E3-M and E4-M (CR-012 STOP 4 and the CR-019 dev runs), and the 2026-10-16 rebuild runs (CR-021). Every number is reported beside the frozen CR-012 / CR-017 number and names its variant (rule 35). Each metric is computed under the frozen grounding and under `IDX-P1`.

**A1 `HIER-DIRECT` — direct hierarchy edge F1.** Strict edge P/R/F1 restricted to the hierarchy label set, at mention level, using the frozen strict scorer unchanged. No identity is inferred, so D2 is respected. Default hierarchy set: `{subclassOf, subtaskOf}`; owner decision at STOP 1 (see §5). `partOf` stays out, consistent with CR-017's `{is_a}`-only hierarchy.

**A2 `HIER-ANC-SURF` — ancestor hierarchy F1 on surface nodes.** One pseudo-node per distinct normalised surface per document (the same construction the E3-M / E4-M oracles use), closure per document, the CR-017 cycle policy (detect and report cycles, closure with a visited set, cycle pairs kept in the prediction). This infers identity from strings, so it is a labelled variant and is never shown as the headline. The report states how many gold surfaces collapse into one node and how many ancestor pairs closure adds.

**A3 `REL-MACRO-SCINLP` — relation macro F1 over the 11 SciNLP labels.** `cr017` `macro_from_rows` on pairs whose two endpoints are both placed, classes with support ≤ 3 flagged, with the per-class support table. Direction accuracy given a correct label is reported as a diagnostic.

**Determinism gate.** Before any variant is reported, the scorer must reproduce the frozen SciNLP figures exactly (test E0: concept F1 0.352, pair recall 0.545, strict edge F1 0.050; IDX-P1 0.195).

## 3. Part B — registry transfer (optional, paid)

**Question.** Does the networking relation registry classify independent relation gold as well as the benchmark's own registry, on the relations both can express?

**B0 — mapping table (human-owned).** Claude drafts a SciNLP → v1.3 mapping into `data/interim/suggestions/cr022_scinlp_to_v13_map.yaml`; the owner approves it into `configs/scinlp_to_v13_map.yaml` with `status: approved` per entry. Only approved entries take effect. The mapping is frozen before any Part B output is seen and is never changed after. Each entry records direction (whether source and target swap) and a fit grade.

Draft proposal (for the owner to accept, change or reject):

| SciNLP label | Test support | v1.3 relation | Fit |
|---|---|---|---|
| subclassOf | 31 | is_a | clean |
| partOf | 8 | part_of | clean |
| UsedFor | 75 | has_purpose | clean |
| compareWith | 52 | contrasts_with | close (symmetric vs directional) |
| trainedWith | 11 | uses | close |
| subtaskOf | 15 | part_of or is_a | owner decides |
| enhancedBy | 43 | uses or increases | owner decides |
| MeasuredBy, evaluatedOn, evaluatedBy | 42 | — | unmapped (no evaluation relation) |
| similarWith | 18 | — | unmapped (equivalence retired in v1.3) |

With the clean and close rows only, 177 of 295 test relations (60%) are mappable. Unmapped gold relations are excluded from Part B scoring and counted in the report; they are a measured limit of the registry, not an error of the run.

**B1 — re-run the relation stage only.** On copies of the SciNLP dev E0 runs (new run ids `cr022_v13_<base>`), re-run relation family, relation choice, qualifiers and evidence checks on the **same selected pairs** with registry v1.3 and the existing networking prompt versions. Concepts, canonicalisation and pair selection are not re-run. A $0 check first confirms that the copies reproduce the base selected pairs exactly.

**Scoring.** Gold is restricted to approved mapped labels. Both arms are scored on that same restricted gold: the v1.3 arm through the mapping, the SciNLP-registry arm (existing E0 output) on the same subset. Reported: strict edge F1 on the subset, relation macro F1 over the mapped classes, direction accuracy, and the share of v1.3 predictions that are `other` or `no_relation`. The E4-M condition (correct pair given) is reported for both arms where the oracle runs allow it, to separate classification from delivery.

**Cost and data.** Rule 7 order (dry run, `--limit 20`, full). Cap **$10** for dev. Test papers are run only with explicit owner approval at STOP 3, under a separate cap.

**Reading rule (fixed before any Part B run).** Part B is descriptive; there is no adoption decision and no production change. The report states the difference between arms on the shared subset with its sign, the mappable share, and which classes drive the difference.

## 4. Rules that apply

- Frozen artefacts are read-only; new outputs use new run ids (rules 13, 31, 35).
- Every rescored number names its variant and sits beside the frozen number, never instead of it (rule 35).
- Code never writes `data/gold/` (rule 2). The mapping table is an owner decision; drafts go to `data/interim/suggestions/`.
- Relations change only through a registry version (rule 11). This CR adds no relation and edits no prompt; if a prompt change proves necessary it becomes a new prompt version and a DECISIONS entry.
- SciNLP test: Part A rescores existing outputs only. Part B on test needs owner approval.

## 5. Stop points

- **STOP 1 ($0).** Determinism gate passes; counts per document (hierarchy edges, surface collisions, gold cycles); draft mapping table written. Owner decides: (a) hierarchy set `{subclassOf, subtaskOf}` or `{subclassOf}` only; (b) whether to run Part B; (c) the mapping table.
- **STOP 2 ($0).** Part A report `reports/cr022/part_a.md` with A1–A3 on dev and test, beside the frozen numbers.
- **STOP 3 ($, optional).** Part B dev run and report `reports/cr022/part_b.md`; owner decides whether to run test.
- **STOP 4.** PROGRESS, DECISIONS and ARCHITECTURE (evaluation section) updated; tests pass; merge per the git workflow.

## 6. Acceptance

- Frozen SciNLP figures reproduced exactly by the scorer used for the variants.
- Source run hashes identical before and after.
- New tests cover: hierarchy-set filtering, surface pseudo-node closure with a cycle, macro F1 with a low-support class, mapping application with direction swap and unmapped labels.
- `uv run pytest` passes with no network and no key; Part A spends $0; Part B stays within its cap.
- Each report names the dataset release, splits, run ids, grounding variant and scorer.

## 7. Out of scope

- Changing the SciNLP headline definition or any frozen number.
- P&D hierarchy scoring (already evaluable on P&D-E2E gold, CR-017).
- Any change to production defaults, the registry, or concept and pair stages.
