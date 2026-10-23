# PROMPT-CR-011 — Coding-agent handoff

Implement **CR-011 — Sleep-Phase Node Consolidation and Reversible Knowledge Restructuring** exactly as specified in:

`docs/change-requests/CR-011-sleep-consolidation.md`

Read these supporting files before coding:

- `STOP1_RECONCILIATION.md`
- `configs/sleep_consolidation_v1.yaml`
- `configs/fewshot/sleep_merge_v1.yaml`
- `prompts/sleep_merge_adjudicator_v1.md`
- `docs/annotation/sleep_merge_codebook.md`
- `docs/cr011_migration_rollback.md`
- `tests/fixtures/sleep/fixtures.yaml`

## Hard authority rule

Research owns identity semantics, metrics, thresholds/gates, experiment arms, SLEEP-240 sampling/split construction, human-label protocol, gold policy and production-adoption rules.

Do not silently change them.

If repository reality makes the approved method impractical, stop and report:

**Problem → why approved design cannot be implemented → alternatives → expected methodological consequences → decision required from Research.**

## First action: STOP 1 only

Do **not** make paid calls or mutate production data.

1. Inspect git state, CR-010 completion evidence, merge/tag and branch convention.
2. Locate the actual canonicalisation/merge modules and every current trigger.
3. Audit R0–R4, current thresholds, type guards, one-token behaviour and `concept_score` interaction.
4. Audit cluster formation: determine whether pairwise SAME can become transitive closure without cross-cluster validation.
5. Audit alias provenance, `merged_from`/lineage, description history, edge re-keying, duplicate-edge evidence, self-loops and evidence retention.
6. Prove or disprove exact rollback from current state; do not assume `merged_from` is enough.
7. Map CR-010/eRST node-identity hooks and `same_concept` queue.
8. Count nodes, aliases, merge events, one-token merges and cross-chapter merges.
9. Locate historical owner merge labels and current price configuration.
10. Fill `STOP1_RECONCILIATION.md` and the cost preflight.
11. Wait for owner approval before STOP 2 or any paid call.

## After STOP 1 approval

Execute only in CR order.

### STOP 2 — offline candidates + scorer

- Build multi-signal candidate retrieval and feature extraction.
- Replay historical owner labels for candidate recall and scorer development.
- Run logistic scorer + calibration and the specified gradient-boosted ablation.
- Propose `t_auto` and `t_review` from development only.
- Freeze SLEEP-240 by cluster/normalised-form family: 80 dev / 160 held-out.
- Generate blind annotation sheets with no model/rule/score leakage.
- Report predicted LLM review count.
- Do not open held-out labels for tuning.

### STOP 3 — development ablations

Run S0, S1, S2, S3, S4, S5, S5-OT, S5-TIME and the approved development scope for S-AGG.

Reject any arm that violates CR-008 `different`, loses evidence/provenance/rollback, has merge precision < 0.98, or regresses exact micro F1 by > 0.01.

Select by highest merge recall; within 0.02 recall choose fewer LLM calls / less human review.

Generate real-data trade-off charts only from frozen outputs.

### STOP 4 — held-out

Run **S0 and the frozen selected candidate exactly once**. S-AGG is held-out-eligible only if competitive on development and separately approved for spend.

Report all adoption gates, Wilson intervals, per-stratum results, agreement, one-token errors and actual spend.

Do not perform production migration until Research/owner approves the held-out result.

### STOP 5 — migration / rollback rehearsal

Use a new `sleep_id` and immutable source snapshot.

- generate merge plan;
- validate guards;
- apply event-sourced transactions;
- re-key/deduplicate edges with evidence union;
- log self-loop rejections;
- write inverse operations;
- run structural integrity;
- perform exact rollback round trip;
- compare canonical content hashes;
- report before/after counts and CR-006 organisation replay diff.

Only after approval may a new sleep version become the production canonical view.

## Non-negotiable guards

- `term_lexicon.different` outranks embeddings, ML and LLM.
- Graph similarity/community membership never proves identity.
- `concept_score` cannot decide identity alone.
- One-token embedding-only auto-merge is forbidden.
- Naïve transitive closure is forbidden.
- `SAME` from ML/LLM is still subject to hard guards and cluster consistency.
- `suspected_split` is review-only; do not automatically split production nodes.
- Raw source node records are never physically destroyed.
- Duplicate edge collapse unions all evidence.
- `data/gold` is read-only to pipeline code.
- Aggressive mode cannot overwrite production namespace.
- Test examples cannot enter prompts/rules/lexicon until after held-out reporting.
- No paid call before approved preflight.

## Git

Derive the exact branch, commit and merge/tag convention from the repository at STOP 1. Do not assume a branch name merely from this package.
