# CR-011 Decision Report

**Status:** UNSIGNED — Research/owner decision required.

## Evidence summary

- selected dev arm:
- held-out comparison:
- merge precision:
- merge recall:
- distinct-pair violation:
- exact micro F1 delta:
- evidence retention:
- alias provenance:
- rollback round trip:
- review-load change:
- actual spend:

## Required gate table

Copy the final gate table from the frozen evaluation report.

## Allowed conclusions

- `ADOPT_CR011_CONSOLIDATION`
- `KEEP_CURRENT_CR010_CR008_PATH`
- `REVIEW_RANKING_ONLY`
- `RESEARCH_DECISION_REQUIRED`

Implementation code and the coding agent must not sign or choose the research conclusion autonomously.

## Migration approval

- [ ] Research approves production migration.
- [ ] Owner approves production migration.
- [ ] STOP 5 rollback rehearsal passed.
- [ ] Production namespace/version identified.

Without all required approvals, the new sleep version remains experimental.
