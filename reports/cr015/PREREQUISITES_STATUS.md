# CR-015 — Stage B prerequisites (Research decision after STOP 2)

| prerequisite | status |
|---|---|
| 1. freeze A2 | **DONE** — tag `cr015-a2-frozen`, `reports/cr015/FREEZE_A2.json` (selector prompt, verifier prompt, configs, code, development output hashes) |
| 2. implement trace events | **DONE** — stages `boundary_family`, `concept_validity`, `mention_placement`, `adjudication` added additively; A2 development trace `data/processed/cr015/stageA/trace_A2.jsonl`: 36,614 events, every one of the 10,682 placement events links to its selector and verifier events (coverage 1.00), 1,614 suppressed occurrences recorded with a reason, tests pass (`reports/cr015/trace_coverage.json`) |
| 3. human-audit ~120 exposed overlap families | **WAITING ON HUMAN** — `data/interim/checks/cr015/boundary_audit_blind.csv` (120 families, 441 rows; 30 per gold-pattern stratum, seeded `cr015-boundary-audit-v1`; sheet sha256 `b8efdf1b…`); guide `docs/annotation/cr015_boundary_audit_guide.md` |
| 4. confirm/fix the annotation convention | after 3: I compare human labels with the gold and with A2, then Research/owner decide any change |
| 5. freeze the B-stage codebook / prompt design | after 4 (the convention outcome shapes the codebook); drafts will be written then |
| fresh pilot (4.3, 6.2) | **KEPT SEALED** (not opened by any of the above) |
