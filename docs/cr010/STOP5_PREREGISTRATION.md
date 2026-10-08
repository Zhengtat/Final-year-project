# CR-010 STOP 5 — pre-registered definitions (written 2026-10-08, before any STOP-5 metric or `erst_direct` call)

Authority: Research decision 2026-10-08 (STOP 5 authorized). The implementation does not select the architecture.
Single annotator (annotator 1) stands in as the adjudicated label; there is no second human, so the κ gate is `NOT_EVALUABLE`.
The annotator-1 marginal counts over all 180 rows were seen while planning (erst_applies yes 49/180, survives yes 37/180);
no metric was computed by split before this file was written.

## Populations
- **Valid-relation items**: items whose annotator-1 `current_semantic_relation_judgement` is a registry v1.3 relation name
  (not `none`, not `other`). Dev = the 60 development items, held-out = the 120 test items. Gates use held-out only.
- `other` judgements (a relation the registry lacks) are counted and reported separately, outside every gate denominator.

## Metrics (all on valid-relation items)
1. **eRST expressibility** = share with `erst_applies_yes_no = yes`.
2. **Semantic preservation** = share with `machine_useful_meaning_survives_yes_no = yes`.
3. **Mapping-loss rate** = 1 − semantic preservation.
4. **Critical-loss rate** = share with survives = `no` AND at least one `loss_*` column = `yes`; Wilson 95% upper bound reported.
   Items with survives = `no` and no loss category are **silent losses**, reported separately (ambiguity flagged for Research).
5. **Relation-collision rate** = among expressible items of one split, the share whose representation key
   (`erst_relation_1`, `erst_relation_2_optional`, `direction_judgement`, `nuclearity_judgement_if_relevant`) is shared with at least
   one item of a different current relation.
6. **Reverse recoverability.** Procedure frozen from the DEV items only: lookup from representation key to the dev-majority current relation,
   with the fallback chain (full key) → (erst_relation_1, nuclearity) → (erst_relation_1) → the dev-majority relation among
   non-expressible items (key `NO_ERST`) → the global dev majority; ties go to the alphabetically first relation. A non-expressible
   item has the key `NO_ERST`. The table is written to `data/interim/stop5/reverse_recovery_frozen.json` with its sha256 BEFORE it
   is applied to held-out items; applied once. **Macro F1 over the gold relations present in held-out valid-relation items.**
7. **Sufficiently represented relation**: held-out relation with n ≥ 5 valid instances (gold = annotator judgement). Recall = reverse
   recovery returns that relation; numerator/denominator always shown; observed gate value = the minimum recall over such relations;
   n < 5 = `INSUFFICIENT_SUPPORT`.
8. **Organisation/pedagogical information**: gate passes if no valid held-out item of a pedagogical/organisation relation
   (`prerequisite_of`) is a silent loss, and no `loss_pedagogical_prerequisite` / `loss_principle_instance_organisation` flag is hidden;
   counts shown. (The registry has no principle-instance relation.)

## Architecture arms (held-out 120 items, same concept pair and evidence sentence as `current`)
- **current**: the frozen CR-009 outcome already stored per item (`current_outcome = edge` is a predicted edge).
- **erst_direct**: prompt `prompts/erst_direct/v1.md` (frozen here), strong tier, effort low; closed choice among the 31 eRST discourse
  labels plus `NO_ERST_RELATION`; never sees the current relation, family, mapping or hints. An edge is predicted iff the label is not
  `NO_ERST_RELATION` and the quoted evidence is an exact substring of the passage; otherwise no edge.
- **dual**: concept layer = `current` unchanged (identical edge metrics by construction) plus the frozen discourse graph
  (sha256 41cc5e7b…); reported as discourse-graph size and the P3 candidate-routing figures, kept apart from edge quality.
- **Gold edge presence** = annotator judgement is not `none`. Edge precision/recall/F1 per arm on the 120 held-out items; gate
  differences are erst_direct − current. The sample is relation-balanced, so absolute values are not natural prevalence.
- Descriptive (not gated): erst_direct agreement with annotator 1 on applicability and on `erst_relation_1`.

## Separation
Reported as five separate blocks: (1) expressibility, (2) semantic preservation, (3) reverse recoverability, (4) direct edge quality,
(5) P3 candidate-routing utility. P3 classifier failures are not representation failures.
