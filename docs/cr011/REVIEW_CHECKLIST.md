# CR-011 Pre-Handoff Review Checklist

## Review A — Research faithfulness

- [ ] Strict identity means CR-008 SAME, not semantic relatedness.
- [ ] Graph communities/coarsening never imply merge.
- [ ] `concept_score` cannot decide identity alone.
- [ ] Fixed 0.70 threshold is not silently retained as the CR-011 decision boundary.
- [ ] `t_auto` / `t_review` are development-selected.
- [ ] SLEEP-240 is 240 items: six strata × 40.
- [ ] Split is 80 dev / 160 held-out by candidate cluster / normalized-form family.
- [ ] Held-out remains sealed for threshold/arm selection.
- [ ] Human labels remain ground truth.
- [ ] Experiment arms match S0–S5, S5-OT, S5-TIME, S-AGG.
- [ ] Adoption gates match the Research handover.
- [ ] No change remains an allowed outcome.

## Review B — Implementation consistency

- [ ] Actual CR-010 state discovered.
- [ ] CR-008 lexicon/version preserved.
- [ ] CR-009 generator→verifier→pruner ordering preserved.
- [ ] Existing aliases remain readable.
- [ ] Source snapshots remain immutable.
- [ ] New sleep namespace/version is isolated.
- [ ] Merge transactions record inverse operations.
- [ ] Exact rollback hash test exists.
- [ ] `data/gold` remains protected.
- [ ] Paid stages have dry-run preflight.
- [ ] CR-006 replay is downstream and cannot feed back as identity evidence.
