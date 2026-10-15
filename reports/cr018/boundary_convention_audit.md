# CR-018 STOP 2 — boundary convention audit: materials prepared, AWAITING HUMAN ANNOTATOR

Written for: Research and the project owner. **Status: `AWAITING_HUMAN_ANNOTATOR`.** No human annotator has been designated, so the audit cannot be completed. Per the instruction, I prepared the materials and stopped: **no label was filled by anyone or anything, no model-generated labels were substituted, the sample was not reduced to 30, no model call was made ($0), no fresh section was used, and no boundary prompt was written or tuned.** The annotation evidence, disagreement analysis and final gate recommendation below are therefore **not yet available**; what exists is the frozen sample, the frozen instructions, the frozen decision rule and a tested scorer that will produce them the moment a human sheet is returned.

## 1. What is frozen (hashes in `configs/cr018_audit_manifest.yaml`, enforced by a test)
| item | file | sha256 (first 16) |
|---|---|---|
| blind sheet (what the annotator gets) | `data/interim/checks/cr018/boundary_audit_blind.csv` | `fdf3ea64…` |
| hidden key (gold relation, stratum, A2-kept flag; gitignored, deterministically regenerated and hash-checked) | `data/processed/cr018/boundary_audit_key.csv` | `1dc0c1f4…` |
| annotator instructions (copy beside the sheet) | `docs/cr018/BOUNDARY_AUDIT_INSTRUCTIONS.md` | `0b683c23…` |
| decision rule | `configs/cr018_audit.yaml` | `4c89e0f0…` |
| sampler / scorer | `src/cumap/cr018/audit_sample.py`, `audit_score.py` | see manifest |

## 2. The frozen sample: 120 families, 480 span rows
Drawn with seed `cr018-boundary-audit-v1` from the **exposed** CR-014 development sections only (4.1, 4.2, 5.3, 6.1, 6.4, 7.2, 8.3, 8.4, 8.5, 9.2; none of the eight fresh candidates), families of 3–7 candidates in sentences of ≤ 60 words, at most 6 families per stratum per section. Strata follow the handover's 30/30/30/30; they are defined from candidate-span geometry against the development gold and are used **only for sampling, never shown**: no gold, system arm, verdict, FP/FN category or score appears in the sheet (tested).
| stratum (hidden) | families | spans | composition of its spans against the dev gold |
|---|---|---|---|
| OVERLONG (a non-gold candidate contains a gold span) | 30 | 127 | 28 gold-exact, 51 contain gold, 41 no overlap, 7 other |
| UNDERLONG_PARTIAL (non-gold prefix/suffix truncation of a gold span, or partial overlap) | 30 | 92 | 30 gold-exact, 62 truncations |
| INVALID_NESTED (non-gold candidate strictly interior to a gold span) | 30 | 146 | 25 gold-exact, 121 interior substrings |
| NESTED_PAIR (≥ 2 candidates are gold: the nested convention itself) | 15 | 61 | 32 gold-exact, 29 other |
| GOLD_SILENT (gold marks nothing and nothing overlaps it) | 15 | 54 | 54 gold-unmarked |
Overall 115 of 480 spans are gold-exact, 365 are gold-unmarked (the sample deliberately over-represents contested boundaries; rates are therefore reported per stratum and per boundary type, not as a population estimate). Per-family rows follow text order, so row position gives no hint. The annotator sees the section heading, previous/marked/next sentence, all spans of the family and one target span per row, and fills `q1` (exact complete boundary yes/no/unsure), `q2` (independently meaningful if inside a longer term) and one of the seven handover labels (`VALID_EXACT … UNCERTAIN`). Expected effort: ≈ 480 rows ≈ 2.5–3.5 hours.

A note on the earlier CR-015 model-filled sheet: it is **not used** here (invalid for this audit); this is a new draw with a new sheet design (context sentences, family spans visible, seven labels).

## 3. Frozen decision rule (PROPOSED by implementation; Research may amend before the sheet is returned, never after)
Human "valid" = `VALID_EXACT` or `VALID_NESTED`; development convention "valid" = span is a gold mention. `UNCERTAIN` is excluded from agreement and reported separately (> 15% uncertain marks the sheet unreliable). The convention differs **materially** if any of: R1 span agreement < 0.80; R2 > 20% of gold-unmarked spans judged valid (gold under-annotates); R3 > 15% of gold-marked spans judged invalid (gold over-annotates); R4 agreement < 0.70 within any stratum. It is **systematic** if ≥ 70% of at least 20 disagreements go one way. Outcomes: material and systematic → `STOPPED_BOUNDARY_GOLD_AMBIGUOUS` (return to Research, no boundary tuning against this gold); material but not systematic → `MIXED_RESEARCH_REVIEW`; otherwise `CONVENTION_COMPATIBLE`. 95% intervals are family-bootstrap (10,000 resamples). These thresholds were set before any human label exists; they are my proposal (the spec says only "material/systematic") and need Research confirmation.

## 4. What the scorer will report (`python -m cumap.cr018.audit_score --sheet <filled.csv>`)
Agreement, κ and confusion overall; **disagreement by boundary type** (by stratum, and the human label distribution by development-gold relation: exact / contains-gold / inside-gold / partial / no-overlap); gold-unmarked-judged-valid and gold-marked-judged-invalid rates with family-bootstrap CIs; the direction of disagreement; family-level view (families with ≥ 2 human-valid spans, none, or the human valid set equal to the gold set); and, as a secondary diagnostic only, agreement of the frozen A2 selector's kept spans with the human labels. The scorer **refuses** a sheet unless: a sidecar declares `role: human`, `model_assistance: none` and an annotator id; the file name does not suggest a model; the blind columns are unedited; every row has a valid, internally consistent label (checked by synthetic fixtures in `tests/test_cr018_audit.py`; these fixtures are test data, not findings).

## 5. Annotation evidence, disagreement analysis, gate recommendation
**Not available — `AWAITING_HUMAN_ANNOTATOR`.** Until a human sheet is scored: the gate recommendation is **hold**. STOP 3 (Track A) must not start, no boundary verifier prompt may be written, and BA2/BA3 results would otherwise only measure agreement with a gold that has never been checked by a human.

## RESEARCH / OWNER ACTION REQUIRED
1. **Designate a human annotator** (the owner or another person) and have them complete `data/interim/checks/cr018/boundary_audit_blind.csv` following the instructions beside it, then add `boundary_audit_annotator.json` (format in the instructions). Do not use a model for any cell. I will then run the scorer and return the evidence, disagreement analysis and recommendation.
2. Confirm or amend the §3 thresholds **before** the sheet comes back.
3. If no human is available: the audit stays open and Track A development stays blocked; any alternative (a smaller sample, a model-assisted audit) needs a new Research decision, which I have not assumed.
