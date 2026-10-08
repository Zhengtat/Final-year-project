# CR-010 — Residual Node Recall and eRST Relation Architecture Evaluation

**Status:** IMPLEMENTATION PACKAGE DRAFT. **STOP 1 is not passed in this chat** because the live repository/branch/tag and completed CR-009 outputs are not mounted here. No coding assumption below may be treated as a substitute for repository reconciliation.

**Research authority:** latest Research ↔ FYI Implementation Contract / CR-010 handover supplied by the owner.

**Implementation authority:** `fyi implementation` may encode the approved design, but may not change method, metric, thresholds, hypotheses, experiment arms, relation semantics, sampling, annotation protocol, architecture gates, evidence/provenance requirements, or interpretation of results.

## 1. Objective and open outcomes

CR-010 asks three questions:

1. **Node recall:** can genuinely new residual-recall mechanisms improve the final CR-009 concept pipeline without materially damaging precision?
2. **eRST replacement:** can the existing domain-semantic relation ontology be replaced by the paper-faithful eRST discourse-relation ontology while preserving the information required by the Expert KG?
3. **Architecture:** if complete replacement fails, where should eRST live?

Allowed research outcomes remain open:

- `FULL_ERST_REPLACEMENT`
- `ERST_CORE_PLUS_DOMAIN`
- `DUAL_LAYER`
- `KEEP_CURRENT` (implementation report option when no change is justified)

The implementation must not predetermine a dual-layer result.

## 2. Inherited invariants

### CR-008

- Equivalence is **not** an expert-KG relation edge. `equivalent_to` must remain removed.
- `same_concept` is a canonicalisation/merge candidate only.
- R0–R4 term-lexicon decisions remain authoritative and guard every merge point.
- Known confusables must not merge because of an eRST or model similarity signal.
- Misconceptions remain a separate layer and are excluded from normal expert-KG precision/pair-selection calculations.
- Canonicalisation/re-keying must preserve provenance and rollback.

### CR-009

The following are inherited, not novel CR-010 claims: KG-aware generator → verifier → corrective iteration → pruner; existing-node cards; complete-span rules; G1/G2 baseline; strict same/different handling; anchors as discovery/pair-priority hints only; forward existing-node sweep; chapter-end backfill; PiVe-style corrective verification; pruner.

**Anchors are never KG edges.** Owner gold labels remain measurement data and must never become runtime rules. No automatic write to `data/gold` is permitted.

## 3. STOP 1 — repository reconciliation / $0 preflight

Before creating the branch or changing code, inspect the actual repository and record:

- CR-009 completion state, merge state, and `cr-009-complete` tag if present;
- current branch and branch/tag convention;
- final selected CR-009 concept configuration (G1/G2, iteration depth, M4, pruner model/threshold, V2, any rule demotions);
- active relation registry after CR-007/008/009;
- actual status of `acts_on`, `connected_to`, gated `identifies`, `encapsulates`, `trades_off_with`, `instantiates`, and any later relation;
- confirmation that `equivalent_to` is absent;
- active CR-008 term lexicon / R0–R4 state;
- misconception layer implementation;
- pair-selection implementation and caps/priorities;
- ChainLink implementation status;
- dry-run call counts, token estimates, API estimate, owner-annotation estimate, and proposed hard caps.

**No paid experiment before owner approval.** If the repository contradicts this CR’s inherited assumptions, stop and report the contradiction rather than silently adapting the experiment.

## 4. Node experiment

### N0 — frozen baseline

`N0 = final selected CR-009 concept pipeline` as discovered at STOP 1. Do not reconstruct it from the CR-009 draft.

### N1 — candidate-hint rescue

Add a deterministic rescue stage based on candidate extraction mechanisms already available or naturally derivable from the text: noun phrases, technical noun heads, headings/formatting, acronym candidates, and definitional patterns. A candidate is a **hint only**.

For every omitted candidate, the rescue decision is exactly one of `add_new`, `link_existing`, or `reject`. Any accepted item still passes through normal CR-009 verification, canonicalisation, and pruning. Record one-token technical candidates separately.

### N2 — selective independent resampling

Only when a frozen recall-warning condition fires, request an independent second generation sample. The second sample must not see the first model output. Union candidates only after generation, then run normal canonicalisation, verification, and pruning. Freeze the trigger definition on development before held-out evaluation and store it in configuration/provenance.

### N3 — one-token diagnostic ablation

Run the selected rescue pipeline with one-token candidate hints disabled.

### Node selection

Primary metric: **exact micro F1**. Also report lenient F1, precision, recall, macro F1, n-gram recall, partial-span errors, one-token recall, rescue precision, candidate counts at rescue/verification/pruning, and incremental API cost.

Adopt a node arm only when either:

- exact micro F1 improves by **≥ +0.02 absolute**, or
- the paired section-level bootstrap ΔF1 lower bound is positive,

and precision drops by **≤ 0.02 absolute**. If qualifying systems are within **0.02 F1**, choose the simpler system. **No node change is allowed as the final outcome.**

## 5. eRST source-faithfulness contract

The primary ontology authority is Zeldes et al. (2024), *eRST: A Signaled Graph Theory of Discourse Relations and Organization*.

`configs/erst_relations.yaml` encodes Appendix A Table A.1 exactly at label level: **32 labels, 31 discourse relations plus technical `SAME-UNIT`**. It preserves coarse class and source-table nuclearity symbol. `SAME-UNIT` must never be treated as an ordinary semantic relation.

eRST relations operate primarily over **discourse units / propositions**. Existing Expert-KG relations operate primarily over **concepts**. Similar English names do not establish equivalence.

Keep these notions distinct in schemas and provenance:

1. eRST discourse relation;
2. eRST relation signal;
3. domain-semantic concept relation.

Signal handling must support discourse markers plus the paper’s seven non-DM signal families: graphical, lexical, morphological, numerical, reference, semantic, syntactic. A semantic signal such as synonymy/meronymy/repetition is evidence for a discourse analysis, not permission to create `synonym_of`, `part_of`, or `equivalent_to` as eRST relations.

## 6. Relation architecture arms

### `current`

The frozen CR-009 relation architecture from STOP 1.

### `erst_direct`

Use exactly the same candidate concept pair and supporting evidence presented to `current`, but classify only into the paper-faithful eRST inventory plus `NO_ERST_RELATION`.

The classifier must not see the current predicted relation, current relation family, current→eRST mapping table, or mapping-derived hints. Preserve supported direction, nuclearity, concurrent relations, and signals. This arm is intentionally a fair direct-replacement test rather than a translation layer.

### `dual`

Concept-semantic relations remain in a concept layer. eRST relations operate on EDUs/propositions/evidence spans in a separate graph. Unless the implementation genuinely satisfies eRST’s full structural requirements, call the result an **eRST-compatible discourse relation graph**, not a complete eRST parse. Do not remove ChainLink merely because eRST exists.

## 7. REL-MAP-180 mapping benchmark

Freeze exactly 180 items:

- 120 accepted current concept edges;
- 30 current `NO_RELATION` hard negatives;
- 30 `OTHER` / difficult rejected / near-miss pairs.

Group by evidence section before splitting. Freeze **60 development** and **120 held-out test** items. At least **60** items receive independent double annotation.

Blind annotators must not see model predictions, the research mapping table, model confidence, or architecture recommendation. They judge current semantic relation, eRST applicability/label(s), direction/nuclearity where relevant, semantic survival, and information loss.

Loss categories include taxonomy; part/whole composition; mechanism; network topology; identifier semantics; encapsulation/payload semantics; causal sign/direction; technical dependency; trade-off semantics; pedagogical prerequisite; principle-instance organisation.

The mapping table in this package is explicitly **NOT GOLD**. It is a hypothesis aid and must never be shown to blind annotators or used as hidden runtime truth.

## 8. Semantic preservation and reverse recoverability

Report eRST expressibility, semantic preservation, mapping-loss rate, critical-loss rate, relation-collision rate, and reverse recoverability.

Freeze an eRST-representation → current-semantic-relation recovery procedure using development data only. Evaluate it once on held-out test data and report macro F1.

## 9. Full-replacement gate

`FULL_ERST_REPLACEMENT` is eligible only if all gates pass:

| Gate | Threshold |
|---|---:|
| eRST expressibility | ≥ 0.90 |
| Semantic preservation | ≥ 0.90 |
| Mapping-loss rate | ≤ 0.10 |
| Critical-loss 95% Wilson upper bound | ≤ 0.15 |
| Reverse-mapping macro F1 | ≥ 0.90 |
| Recall for sufficiently represented current relation | ≥ 0.75 |
| eRST-direct edge-F1 difference | ≥ −0.05 |
| eRST-direct precision difference | ≥ −0.05 |
| Mapping agreement | κ ≥ 0.67 |
| Organisation/pedagogical information | no silent loss |

These are project gates, not thresholds proposed by the eRST authors.

## 10. Pair recall is independent

Pair recall = validated true edges whose endpoint pair reached classification / validated true edges for which both endpoint nodes exist.

A missing endpoint is a node-recall failure. Existing endpoints whose pair is never proposed are a pair-recall failure. A proposed pair receiving the wrong relation is a classification failure.

### P0–P3

- **P0:** frozen CR-009/CR-007 selection strategy.
- **P1:** P0 + previously unhandled same-sentence / same-clause co-mentions.
- **P2:** P1 + high-confidence relation-cue expansion.
- **P3:** P2 + pairs prioritised because concepts occur across discourse units connected by the experimental eRST graph.

P3 uses eRST only as pair-selection evidence; it never converts a discourse edge directly into a concept edge. Report pair recall, pairs classified, relation yield, edge precision/recall/F1, and cost.

## 11. STOP sequence

### STOP 1 — repository reconciliation / $0 preflight
See §3.

### STOP 2 — node experiment
Run N0/N1/N2/N3 on development; report full metrics/failure slices/costs; select by the pre-registered rule; evaluate held-out once; do not tune on held-out.

### STOP 3 — eRST implementation audit
Verify inventory, hierarchy, direction/nuclearity, signals, `SAME-UNIT`, no invented relations, and no CR-008 equivalence violation against the primary paper.

### STOP 4 — mapping + pair recall
Freeze REL-MAP-180; run blind mapping study; run P0–P3; report pair recall separately from conditional classifier accuracy.

### STOP 5 — architecture evaluation
Run `current`, `erst_direct`, and `dual`; populate every gate; produce loss analysis and reverse-recoverability results. **Implementation code does not select the architecture.** Return evidence to Research.

## 12. Testing requirements

Tests must cover: schema validation; exact eRST inventory; direction/nuclearity; unknown labels fail closed; alias/equivalence regression; misconception-layer separation; anchor-not-edge regression; gold-data write protection; provenance; migration idempotency; rollback; no-network/no-key; dry-run cost; pair-recall denominator; blind-split leakage; deterministic evaluation where applicable.

Minimum regressions should include known confusables (`HDLC != SDLC`, `Internet != internetworking`, `CRC != error-detecting code`) if still present in the active CR-008 lexicon, plus a list/co-mention fixture proving that eRST/list evidence cannot itself create a contrast/trade-off concept edge.

## 13. Provenance and migration

Every accepted expert-KG edge must retain source/evidence, extraction run, prompt/config, relation-registry version, and verification/confidence path. Experimental CR-010 outputs receive new `run_id`/organization identifiers and must not overwrite CR-009.

Any migration requires versioned schema, before/after counts, information-loss report, provenance preservation, and rollback. See `docs/cr010_migration_rollback.md`.

## 14. Deliverables in this package

- `change-request-010-node-and-erst-relations.md`
- `PROMPT-CR-010.md`
- `configs/cr010_experiments.yaml`
- `configs/erst_relations.yaml`
- `data/interim/checks/cr010_current_to_erst_mapping_NOT_GOLD.csv`
- `data/interim/checks/cr010_relmap180_blind_annotation_template.csv`
- `reports/cr010_evaluation_report_template.md`
- `docs/cr010_migration_rollback.md`
- `tests/fixtures/cr010_erst_fixtures.yaml`
- `reports/cr010_cost_report_template.csv`
- `reports/cr010_decision_report_template.md`
- `docs/CR010_PROJECT_DOC_UPDATES_2026-10-04.md`
- `STOP1_RECONCILIATION.md`

Repository paths remain provisional until STOP 1 discovers the actual convention.

## 15. Review status

**Review A — source faithfulness:** specification registry checked against the primary paper’s Appendix A label inventory/nuclearity notation and signal-family description. Implementation audit remains STOP 3.

**Review B — implementation consistency:** CR-008/CR-009 draft lineage has been checked, but the live repository/completed CR-009 state is not available in this chat. Therefore Review B is **blocked at STOP 1**, and this package must not be represented as ready-to-merge until reconciliation is complete.
