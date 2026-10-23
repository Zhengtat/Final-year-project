# CR-015 boundary audit — result (NOT human: diagnostic only)

Written for: Research. **Provenance: the filled sheet is `data/interim/checks/cr015/boundary_audit_blind_model_filled.csv`; by its file name and the owner's earlier statements it was filled by a model, not by a human (sha256 `ad07b116…`; the blind sheet itself is unchanged).** Research asked for a *human* audit; this is not one. It is reported as `MODEL_GENERATED_DIAGNOSTIC` and must not be used as human evidence or to change a gate. Structure is complete: 441 of 441 rows labelled (216 yes, 225 no, 0 unsure), 110 rows marked as independent nested terms, 18 notes.

## Comparison (family sample: 120 exposed families, 30 per gold-pattern stratum; labels from the model-filled sheet)
| reference | spans the reference marks valid / labelled valid by the audit | spans the reference does not mark / labelled valid by the audit | agreement with the audit |
|---|---|---|---|
| model-generated gold (CR-014) | 127 / **119 (94%)** | 314 / **97 (31%)** | 0.762 |
| frozen A2 selector (kept spans) | 245 / **186 (76%)** | 196 / **30 (15%)** | 0.798 |

By stratum (gold-marked spans labelled valid | gold-unmarked spans labelled valid): nested pair in gold 61/67 | 23/51; only the longest span in gold 29/30 | 23/72; only a shorter span in gold 29/30 | 25/83; no candidate in gold — | 26/108.

Family-level: 71 of 120 families (59%) contain two or more valid spans; the longest candidate is itself valid in 68 of 120.

## What this suggests (diagnostic, not conclusive)
- **The gold is narrower than the audit's convention.** About a third of the candidate spans the gold leaves unmarked were judged valid, including 26 of 108 in families where the gold marks nothing at all. If this held under a human audit, part of the "false positives" measured against the dev gold (and the over-long and invalid-nested counts) would be gold omissions, not model errors, and development precision would be understated.
- **A2's kept spans line up with the audit better than the gold does** (0.798 vs 0.762), but A2 also keeps spans the audit rejects (59 of 245 = 24%), and its non-selected spans include 30 the audit accepts.
- **Nested spans are common:** 110 of the 216 valid spans are marked independent terms inside a longer valid term, which is the convention A2's explicit nested labels follow and the longest-match placement erases.
- The model-filled labels come from a model, possibly of the same family as the system under test, so agreement with A2 may be partly shared bias.

## Status of the Stage B prerequisites
| prerequisite | status |
|---|---|
| freeze A2; trace events | done |
| human audit of ~120 families | **NOT SATISFIED as specified** (the filled sheet is model-generated) |
| confirm/fix the annotation convention | **not done**: no human evidence; no convention was changed |
| freeze the B-stage codebook / prompt design | **not done** (waits on the convention decision) |

## RESEARCH DECISION REQUIRED
1. Accept this model-filled audit as diagnostic-only and waive the human requirement, or require a human audit (the full 441 rows, or a smaller blind subset, e.g. 30 families, that would let a human check whether the model labels are trustworthy)?
2. Whether the apparent gold under-annotation justifies changing the convention for Stage B development (for example: both a nested outer and inner span count when each is independently meaningful), and whether the dev gold should be re-audited by a human before Stage B tunes against it.
3. If Research waives the human audit, Stage B can proceed on the A2 base; I will then draft the B1–B3 codebook and prompts and freeze them before any Stage B call. I will not start before that decision.
