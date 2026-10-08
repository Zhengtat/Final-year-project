# CR-011 - return to Research after the SLEEP-240 development labels (2026-10-09)

**Trigger:** a new methodological ambiguity / the frozen evaluation design may not be able to answer the CR's question. No paid call has been made; STOP 3 is paused.

## Problem

The owner labelled the 80 development items (valid: 0 format problems, display columns unchanged). Result:

| decision | n | note |
|---|---:|---|
| NOT_SAME | 75 | related_other 27, kind_of 20, process_vs_entity 9, broader_narrower 5, confusable 5, unrelated 4, same_surface_different_sense 3, part_of 2 |
| SAME | 3 | "underlying Ethernet" / Ethernet; "spectrum" / "electromagnetic spectrum"; "virtualization" / "virtualize" |
| UNSURE | 2 | "checksum algorithm" / "checksum scheme"; "single-use networks" / "voice telephone network" |

Positive prevalence in development is 3/80 = 3.75% (Wilson 95% [1.3%, 10.4%]). All 14 deterministic-stratum items (R1/token-overlap candidates) are NOT_SAME, and in the other strata the only positives are 2 of 13 high-similarity items and 1 of 13 one-token items.

## Why the approved design cannot answer the question as written

- **The residual graph has almost nothing left to merge.** The online canonicalisation, the CR-008 rules and the CR-009 generator links already merged the true duplicates (172 events). What sleep sees is overwhelmingly related-but-distinct concepts. This is itself a finding about the baseline.
- **Merge recall is not estimable.** With 3 gold SAME pairs in development, recall can only be 0, 1/3, 2/3 or 1 (one item moves it by 0.33). The development selection rule ("highest merge recall; within 0.02 prefer fewer calls") cannot rank arms S1-S5, S-AGG, S5-OT or S5-TIME. The held-out set (160 items) would hold roughly 6 gold SAME pairs (expected 6.0, plausible range 2-11).
- **The precision gate cannot be shown.** The CR asks for merge precision >= 0.98 and a Wilson lower bound >= 0.95 "when N permits". With n accepted merges all correct the lower bound is 0.44 (n=3), 0.61 (n=6), 0.72 (n=10), 0.84 (n=20): it cannot reach 0.95 until about 70 correct accepted merges, which this graph does not contain. So ML auto-merge stays disabled (as already found) and the gate is not evaluable, not failed.
- **The benefit gate (+0.05 merge recall or -25% review load at comparable precision) is not evaluable** with 3-6 positives.
- **What IS well powered:** the safety side. 75 development and about 150 held-out gold NOT_SAME pairs give a usable distinct-pair violation estimate (0 violations of 75: upper bound about 4.8%), which is the gate that protects the graph.
- The scorer cannot be re-fitted usefully: 3 new positives added to the 73 historical ones (which are structurally unlike the pool).

## Alternatives (decision is Research's; none is chosen here)

A. **Run STOP 3/4 as specified and report honestly.** Safety metrics (violations, one-token errors, rollback, provenance) are measurable; recall and benefit are reported as unevaluable; the expected outcome is NO CHANGE for production plus CR-011 kept as a review-ranking/research tool (the CR allows this). Cost about $6.5 as approved, with little discriminating information on recall.
B. **Add a positive-enriched supplement** (new stratum or a separate SLEEP-POS set) built from candidate classes with higher SAME rates (for example grammatical/short-form variants, abbreviation-like pairs, definition-bearing near-duplicates), annotated blind, development and held-out kept separate. This changes the evaluation set (Research-owned) and needs new annotation (the owner's time); it would let recall and precision be estimated.
C. **Narrow the claim of CR-011** to a safety and review-burden study on this graph (violation rate, review volume, provenance and rollback correctness) and defer recall/benefit to CR-012's end-to-end evaluation or to a larger book (the full 17-chapter text produces many more provisional duplicates than the 3-chapter slice).
D. **Re-run the extraction without the online merge** for the evaluation only (provisional nodes before canonicalisation), so sleep sees the duplicates the online pass would have caught; changes the baseline S0 and is a larger method decision.

## Consequences

- A is cheapest and honest but cannot support adoption; B/D cost owner time or a new baseline; C changes what CR-011 claims.
- Nothing about identity semantics, the CR-008 DIFFERENT veto or the safety gates changes under any option.

## Decision needed from Research

Which of A-D (or another) governs STOP 3/4, and whether the benefit and Wilson-bound gates are to be recorded as NOT_EVALUABLE where N does not permit. Until then I will not spend on STOP 3.

## Other items for the record

- Two UNSURE items are mandatory review items, not negatives (codebook rule); they are excluded from precision and recall.
- Marked development sheet committed unchanged: `data/gold/sleep240_dev_blind_sheet.csv`.
