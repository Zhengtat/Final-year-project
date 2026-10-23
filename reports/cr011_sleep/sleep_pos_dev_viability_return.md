# CR-011 - SLEEP-POS-160 development labels: viability check FAILED (2026-10-09)

**Rule (Research 2026-10-09):** gold SAME >= 20 in the 80 development items, else stop and return before any paid STOP-3 call. No adaptive replacement.

## Result

| decision | n |
|---|---:|
| SAME | **8** |
| NOT_SAME | 71 (related_other 28, kind_of 16, confusable 15, unrelated 3, process_vs_entity 3, broader_narrower 2, part_of 2, predecessor_or_version 1, same_surface_different_sense 1) |
| UNSURE | 1 (SP095 (Broadband Base Unit / baseband unit)) |

**8 < 20: STOP 3 stays paused. No paid call has been made.** Sheet format valid (80 rows, display columns unchanged, every NOT_SAME has a kind).

SAME items:

| item | source | pair | preferred form |
|---|---|---|---|
| SP013 | cross_chapter_same_surface | internetworking layer / network layer | network layer |
| SP030 | bridge_high_support | data link level / link layer | link layer |
| SP037 | name_similarity | link layer / data link layer | link layer |
| SP041 | same_type_same_sense | flow / flow of data | flow |
| SP045 | name_similarity | application programmer / application developer | application developer |
| SP069 | evidence_similarity | synchronization character / SYN character | SYN character |
| SP098 | alias_acronym_queue | message / datagram | datagram |
| SP105 | name_similarity | virtual circuit identifier / virtual circuit number | virtual circuit identifier (VCI) |

SAME by source (of 80): name similarity 3 of 11, alias/acronym/queue 1 of 3, bridge 1 of 11, cross-chapter 1 of 11, evidence 1 of 11, same-type 1 of 11, lexical 0 of 11, definition 0 of 11.

## What it shows

- Positive-enriched sampling raised the SAME rate from 3.75% (SLEEP-240 dev, 3/80) to 10.0% (8/80, Wilson [5.1%, 18.5%]), still well below the 25% the viability rule needs. Across both development sets 11 of 160 items (6.9%) are duplicates.
- The enrichment sources were all similarity-based. Most highly similar residual pairs are related-but-distinct (related_other, kind_of, confusable: 59 of 71 negatives), which is the CR-008 identity rule working as intended. High lexical similarity alone found no duplicate at all (0/11).
- The finding is consistent with the STOP-2 result: after online canonicalisation, the CR-008 rules and CR-009 links, the residual 3-chapter graph holds few true duplicates (about 7 per 100 of the most similar pairs).

## Consequences for the approved plan

- Track B (SAME recall on SLEEP-POS dev) would rest on 8 positives; recall resolution is 12.5 points per item. The arm-selection rule ("highest SAME recall, ties within 0.02") remains not discriminating. The held-out half would hold about 8 positives.
- Track A (natural safety) remains well powered (75 SLEEP-240 dev negatives plus 71 SLEEP-POS dev negatives). The precision/Wilson production gate stays NOT_EVALUABLE.

## Options for Research (no choice made here)

A. **Close the CR-011 evaluation as a safety / review-burden study.** Run STOP 3/4 offline with the 11 positives reported descriptively (no recall ranking claim), natural-negative safety as the gate set, and the outcome "no automatic merger; review-ranking only".
B. **Lower the viability bar** (for example to the minimum that gives a stable recall comparison, set by Research) and continue with Track B as designed, accepting wide intervals.
C. **Enlarge the evidence base** instead: re-evaluate on the full book (chapters 1-17 give far more provisional duplicates) or defer the recall question to CR-012's end-to-end evaluation.
D. **Study pre-canonicalisation nodes** as a separate ablation (Research already placed this outside the primary CR-011 question).
E. **Stop CR-011 here with a documented negative result**: sleep consolidation adds little after the existing pipeline on this graph; keep the safety, rollback and provenance machinery (MergeTransaction, inverse, round-trip) only if Research still wants it for CR-012.

Nothing about identity semantics, the CR-008 DIFFERENT veto or the safety gates changes under any option.
