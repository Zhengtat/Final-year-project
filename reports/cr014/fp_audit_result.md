# CR-014 STOP 3B step 1 — blind false-positive audit (IIR dev)

Source: `data/gold/iir_fp_audit_blind.csv` (owner-supplied labels; 58 unique items = up to 30 sampled unmatched predictions each from V1 and V3, **only from the no-overlap category**, arms hidden, shuffled). Labels: 44 yes, 14 no, 0 unsure.

| arm | sampled | judged valid concept | rate [Wilson 95%] |
|---|---|---|---|
| V1 | 30 | 19 | 0.63 [0.46, 0.78] |
| V3 | 30 | 27 | 0.90 [0.74, 0.97] |

Scope limits: the sample covers only false positives with no overlap with any gold term (V1 683, V3 505); the partial/overlong category (V1 405, V3 268) was not audited and is counted invalid here. Sample sizes are small, and the V1/V3 difference is partly a different mix of items.

Illustrative adjusted precision (exact tp + audited-valid share of the audited category; the other FP category counted invalid): V3 (401 + 0.90×505)/1174 ≈ 0.73; V1 (408 + 0.63×683)/1496 ≈ 0.56. **These must not be compared with U0's unadjusted 0.433:** U0's own unmatched predictions (330) have not been audited, so the same gold incompleteness applies to it. A like-for-like comparison needs a U0 audit sample (≈30 items) judged blind alongside.

Reading: the IIR gold is incomplete (about three quarters of sampled "false positives" for V1 and 9 in 10 for V3 were judged valid concepts), so the §22 precision floor measured against that gold is not a reliable verdict on V3. No gate was changed.
