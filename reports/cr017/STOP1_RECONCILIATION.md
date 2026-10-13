# CR-017 STOP 1 — evaluation reconciliation

Written for: Research. Audit only: no model or API call, no scorer change, no historical artefact touched. Branch `cr-017-simplified-evaluation`, created from `main` at the CR-016 merge (`abd1733`); the CR-017 implementation spec and Research handover are copied to `docs/change-requests/` and `docs/research/`. Audit script `src/cumap/cr017/stop1_audit.py` → `reports/cr017/stop1_audit.json`. Hierarchy findings are in `hierarchy_gold_audit.md`. All "frozen" numbers are read from `reports/cr012/stop4_heldout_results.json` (CR-012 held-out, 7 P&D sections, level E0).

## Headline of this STOP
- Concept F1, Pair Recall and Strict E2E Edge F1 **already exist** in the frozen CR-012 scorer (`src/cumap/cr012/scoring.py::score_graph_unit`) and CR-017 can reuse them unchanged. **Relation Macro F1 does not exist** (only conditional accuracy over a different population). **Ancestor Hierarchy F1 does not exist** but the P&D-E2E gold supports it (79 `is_a` edges, 8 of 9 sections; `HIERARCHY_GOLD_GAP` does not apply to P&D, applies to SciNLP).
- Four definition points need a Research ruling before STOP 2/3 (Concept F1 variant; the Relation-Macro population and its handling of `other` / `no_relation` / `rejected`; the "required qualifiers" wording of the strict metric vs the frozen scorer; the headline section population). They are listed at the end; nothing was changed.

## 1. Current exact Concept F1
Three concept scores coexist, for different benchmarks. For the CR-017 P&D-E2E scorecard the candidates are the CR-012 ones:
| score | where | rule | frozen E0 held-out (pooled tp / fp / fn → P / R / F1) |
|---|---|---|---|
| `canonical_node` (untyped) | `cr012/scoring.py::score_graph_unit` | a predicted node is correct iff its evidence-grounded mention spans hit exactly one gold concept; gold concept counted once; split nodes cost precision; false-merge nodes map to nothing | 427 / 363 / 112 → 0.541 / 0.792 / **0.643** |
| `canonical_node_typed` | same | additionally node type = gold concept type | 314 / 476 / 225 → 0.397 / 0.583 / **0.473** |
| `concept_mentions_typed` | same | mention level, exact span and type | 472 / 546 / 2,684 → 0.464 / 0.150 / 0.226 |
Other concept F1s, not for this scorecard: IIR/FACE exact micro F1 over normalised names (`expert_kg/face_scorer.py`, used CR-005…CR-010); CR-014/015 mention-level span-exact and distinct-surface scores (`cr014/pilot_score.py`, `cr015/scoring.py`, development benchmarks with model-generated gold); SciNLP strict entity scorer (`score_scinlp_unit`, mention level). The spec says reuse "the convention already selected by the active benchmark"; the active benchmark is P&D-E2E, whose strict edge score is typed, so which of `canonical_node` (0.643) and `canonical_node_typed` (0.473) is the headline is a **Research decision**.

## 2. Canonical identity mapping
`cr012/scoring.py::align_nodes`: surface/alias is never matched lexically. A predicted node maps to a gold concept only through exact mention-span matches; a node hitting two gold concepts is a false merge (maps to nothing); a gold concept reached by two nodes is a split. Identity diagnostics already exist (pairwise F1 and B-cubed, `identity_metrics`). Gold concept ids are **section-local**, with aliases in the CONCEPT rows. This matches CR-017 §6.3 ("wrong canonical concept is incorrect, no lexical partial credit").

## 3. Taxonomy / hierarchy relation inventory
Registry v1.3 (`configs/relations_v1.3.yaml`), family `classification_structure`: `is_a` ("kind/subtype of"), `part_of`, `has_property`, `connected_to`. The only subsumption relation is `is_a`. `instantiates` is not active (CR-004 patch reserved, never applied). Canonicalisation "narrower/broader" decisions (336 in the production run) are review candidates, not edges.

## 4. Does the gold support ancestor closure?
Yes for P&D-E2E: 79 human-owned `is_a` edges, 102 ancestor pairs after closure (23 added), 0 cycles, 8 of 9 sections; thin and precision-biased (unannotated true ancestors count as false positives; section-local ids; closure per section). SciNLP: `NOT_SUPPORTED_NO_IDENTITY_GOLD`. Details and proposed cycle policy: `hierarchy_gold_audit.md`. No hierarchy was inferred from predictions.

## 5. Pair Recall
`score_graph_unit(...)["pair_recall"]` with `production_graph.proposed_pairs`. Denominator = gold edges (deduplicated by edge key) whose two canonical endpoint concepts have predicted nodes; numerator = those for which any pair of the endpoint nodes is among the pairs the production run sent to relation classification (`group == selected`; the 50-pair measurement sample is excluded); unordered endpoint pair. **This is exactly CR-017 §7.** Frozen E0: **53 / 326 = 0.163** (100 gold edges excluded for missing endpoints). Notes: (a) `cr010/pair_recall.py` is a different construct (recall inside an enumerated candidate universe P0–P3 against human labels, rule 29) and must keep a distinct name; (b) trace fields: the checkpoint keeps `selection_stats`, `selected_pairs`, `sample_pairs` and every classified pair; the generated/eligible/ranked layer is reproducible through CR-013's REPLAYED pair layer, not stored per pair.

## 6. Relation macro / micro scoring
There is **no macro or micro relation F1**. `relation_conditional` counts gold edges whose pair has a *predicted edge* and checks relation and direction: frozen E0 32 → 23 relation-correct (71.9%), 22 direction-correct; `relation_confusion` (gold → picked relation) is stored per section for the same population. Population gap: the classifier outcomes `other`, `no_relation` and `rejected` never become a `PredEdge`, so gold pairs that **reached** the classifier but ended in one of them are outside the current conditional score. From the checkpoints (audit): of the 53 held-out gold edges that reached the classifier, **32 ended as edges, 8 `other`, 6 `no_relation`, 7 `rejected`**. Direction is already separate (not double counted). Support is small: over the 9 annotated sections, 67 reached gold edges fall in 11 classes (acts_on 14, uses 13, is_a 11, contrasts_with 7, part_of 6, has_purpose 6, connected_to 3, has_property 3, increases 2, performs 1, decreases 1); on held-out alone 53. A macro F1 over these classes will be driven by classes with 1–3 items. CR-017 §8.6 requires recording the current NO_RELATION/OTHER semantics: today they are non-edges, not predicted classes.

## 7. STRICT_E2E_EDGE_F1
`score_graph_unit(...)["strict_e2e_edge"]`, pooled by `pool_graph_units`: correct iff canonical source, canonical target, endpoint types, relation and direction (orientation ignored for symmetric relations) match; counting rules (de-duplication by match key, a gold item recalled once, split nodes cost precision) are fixed and tested. Frozen E0: tp 16, fp 158, fn 410 → P 0.092 / R 0.038 / F1 **0.053** (macro mean 0.0533). **Discrepancy:** CR-017 §9.1 lists "required qualifiers" among the matching fields; the frozen scorer does **not** include qualifiers in the strict key and reports them as a secondary (`qualifier_accuracy`, 0 of 5 matched edges needing a qualifier correct at held-out E0). §9.2 also requires that CR-017 reproduce the existing result, so the frozen definition must win unless Research says otherwise.

## 8. Confidence intervals
`cr012/bootstrap.py::cluster_bootstrap` (+ paired variant): resampling unit = section, 10,000 resamples, seed 20261011, percentile interval; `MIN_UNITS_FOR_CI = 10`, so the 7 held-out sections give `CI_status = NOT_EVALUABLE_SMALL_N` and the label `DESCRIPTIVE_SMALL_N_ONLY` (E0 strict F1 0.053, descriptive interval [0.030, 0.076]). `eval/stats.paired_bootstrap_delta` is the section-clustered paired bootstrap used in CR-009/010/014/015. Both satisfy CR-017 §17.

## 9. CR-012 oracle implementation
`cr012/oracle.py` (E1…E4 injections, label-leak scans `FORBIDDEN_VISIBLE_KEYS`), `oracle_run.py` (runs), `attribution.py` (earliest-failure codes N0, N1, C0, C1, P0, R0…R3, E0), frozen results for E0–E4 in `stop4_heldout_results.json`. P&D pooled strict F1 / canonical-node F1 / pair recall by level: E0 0.053 / 0.643 / 0.163; E1 0.113 / 0.855 / 0.220; E2 0.129 / 0.996 / 0.256; E3 0.398 / 0.996 / 1.000; E4 0.470 / 0.996 / 1.000. These are the stage-loss reference for CR-017 §12–13.

## 10. Reports and UI consuming the old metric names
- Scorers and report builders: `src/cumap/cr012/{scoring,stop4_score,stop5,stability,stop4_stability,pilot_oracle_report,scorer_validation,budget}.py`; config `configs/cr012_e2e_eval.yaml` (`headline_metric: STRICT_E2E_EDGE_F1`); test `tests/test_cr012_stop2.py`.
- Frozen outputs: `reports/cr012/{stop4_heldout_results,stop4_check_pd_results,stop4_check_sc_results,pilot_oracles,pilot_e0_rehearsal,scorer_validation}.json` and the CR-012 markdown reports (`FINAL_EVALUATION.md`, `pd_e2e.md`, `stop2.md`).
- UI: `src/cumap/explain/eval_adapter.py` (CR-013 evaluation overlay: strict_e2e_edge and the failure codes), `src/cumap/report/kg_explorer.py` and `kg_explorer.html` plus the generated `reports/kg_explorer/index.html` (`canonical_node`), `reports/cr013/stop4.md`.
- Name collision: CR-010 modules `cr010/{pair_recall,pair_pools,stop4_report,stop4a_report,p3}.py` and their tests use "pair recall" for a different quantity.
- Documents quoting the old names: `docs/PROGRESS.md`, `reports/OVERALL_FINDINGS_CR001-CR014.md`, `reports/cr016/STOP1_RECONCILIATION.md`.
Implication: CR-017 must add the five-metric scorecard beside the old keys (no rename of frozen keys) and migrate the UI/report layers in STOP 5.

## Findings that need a Research decision
1. **Concept F1 variant** for the headline: `canonical_node` (0.643) or `canonical_node_typed` (0.473); both can be reported, but one is the headline.
2. **Hierarchy:** approve `{is_a}`, per-section closure, the cycle policy, descriptive-only status, and the precision caveat (or order optional human hierarchy annotation); decide 7 held-out vs 9 annotated sections; SciNLP hierarchy = NOT_SUPPORTED.
3. **Relation Macro F1 population:** gold pairs that reached the classifier (53 held-out), with classifier outputs `other` / `no_relation` / `rejected` treated how? Proposal: they are misses for the gold class (false negatives) and create no false positive for any ontology class; report per-class support beside the macro (classes with ≤ 3 items flagged), plus a micro F1 and a direction accuracy as diagnostics. Confirm.
4. **Qualifiers in the strict metric:** keep the frozen scorer (no qualifiers in the key) as required by §9.2, or define a separate qualified-strict diagnostic.
5. **Statistical status:** with 7 held-out sections every interval is `NOT_EVALUABLE_SMALL_N`/descriptive; confirm that is acceptable for the headline table.
