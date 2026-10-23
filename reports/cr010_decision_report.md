# CR-010 Architecture Decision Report - RESEARCH DECISION RECORDED (2026-10-08)

The architecture was chosen by Research, not by implementation code. Evidence: `reports/cr010_stop5.md`, `reports/cr010_p3.md`,
`reports/cr010_stop4a.md`.

## Decision

- [ ] `KEEP_CURRENT`
- [ ] `FULL_ERST_REPLACEMENT` - **REJECTED** (also ineligible: IAA gate NOT_EVALUABLE; 8 gates FAIL)
- [ ] `ERST_CORE_PLUS_DOMAIN` - **REJECTED** (among represented held-out relations only `has_property` meets the recall gate: part_of 0/17, uses 6/15, is_a 0/12, has_purpose 0/10, acts_on 0/6, has_property 6/6, connected_to 0/5; insufficient evidence for a coherent eRST semantic core)
- [x] **`DUAL_LAYER` - SELECTED**
- [ ] `AMBIGUOUS`

## Rationale

Dual semantic performance equals `current` by construction; **dual is not claimed to have higher semantic-edge F1 than current**.
It is selected because it preserves the current semantic architecture, avoids the semantic loss of `erst_direct`, and keeps the
independently demonstrated P3 candidate-routing utility (eRST-linked sentence pairs: 63/150 = 42.0% human-true, about 1,070 estimated
true edges in the pool). P3 shows routing utility, not semantic-ontology equivalence, and is kept apart from every replacement metric.

## Held-out measures (81 valid-relation items; not redefined post hoc)

| measure | value |
|---|---|
| eRST expressibility | 22/81 = 27.2% |
| semantic preservation | 7/81 = 8.6% |
| named critical loss | 67/81 = 82.7% |
| silent loss | 7/81 = 8.6% |
| mapping loss total | 74/81 = 91.4% |
| relation collision (supporting diagnostic, among expressible) | 3/22 = 13.6% |

Loss categories (of 81): mechanism 27 (33.3%), part/whole 17 (21.0%), taxonomy 12 (14.8%), network topology 5 (6.2%), causal sign/direction 5 (6.2%), trade-off 1 (1.2%).

## Limitations and claim wording

- Claim: "eRST was unsuitable as a replacement for the domain-semantic Expert-KG relation layer under the evaluated REL-MAP evidence
  regime." The 27.2% expressibility is NOT generalised to textbook discourse overall (REL-MAP evidence is mostly single-sentence).
- Pair recall is recall within the enumerated P0-P3 candidate universe (100% at P3 by construction); relations outside it remain unmeasured.
- IAA: NOT_EVALUABLE (no second human). A study limitation; it no longer blocks CR-010 closure.
- Candidate discovery and conditional relation classification are distinct residual bottlenecks (P3 classifier recall 23/63 = 37%, precision 23/32 = 72%); the classifier was not tuned in CR-010.

## Production migration authorized?

- [x] No (CR-010 is closed with no migration; the eRST graph is an experimental, separate discourse layer under its own run ids)
