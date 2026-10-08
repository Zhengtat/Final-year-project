# CR-010 STOP 4A — return to Research (P3 and full P1/P2 classification NOT started)

## 1. P2 strict-pool regeneration (dry run, $0)

| pool | size | note |
|---|---|---|
| P0 (frozen) | 1100 | unchanged; 226 anchor-derived pairs sit outside the same-sentence universe |
| P1 extra | 7730 | was 7,680 in the prep: the 50 CR-007 random-sample pairs were left out of P0 too, so they belong to P1-extra by definition (+50) |
| P2 extra, **frozen strict matcher** | **4917** | new |
| P2 extra, prep rule (superseded) | 2474 | was 2,324 in the prep; recomputed 2,474 after excluding the anchor-derived P0 pairs the prep forgot to exclude |
| P2 extra, substring cue (rejected) | 7430 | |
| nested P0 / P1 / P2 | 1100 / 8830 / 13747 | P0 ⊂ P1 ⊂ P2 and both extras disjoint from earlier pools: asserted |

- Strict cue config `configs/cr010_p2_strict_cue_config.yaml`: file sha256 `48480f30b5f34d02…`, content sha256 `10a8e85d176f4bf7…`; frozen before any label. It accounts for all 52 repository cues exactly once (14 standalone function words removed, 38 kept).
- **Sensitivity (not used for selection, for Research):** without inflection forms the pool is 3165; without the cue `is a` it is 4323. The cue `uses` (use/used/using/uses) is the only strict cue for 1258 pairs, `is a` for 594.
- Full classification would cost about $64.2 (P1-extra) + $40.8 (P2-extra): **not approved, not run**.

## 2. REL-MAP-180 annotation status

- Annotator 1 (`annotator1`): **180/180 rows judged**, validator: 0 problems (`relmap validate`).
- Descriptive only (not a gate): on the 120 accepted-edge items annotator 1 chose the same relation as the current pipeline for 81 (68%).
- Single annotation; **kappa not measured** (see IAA below). Mapping/loss analysis is STOP 5 work and has not been done.

## 3. Sampled pair-recall study

- Frozen: seed 20261008, 150 random pairs from each of P0 (of 1100), P1-extra (7730) and P2-extra-strict (4917); no suitable random human-labelled P0 sample exists, so 150 P0 pairs were drawn (origin: {'anchor_derived': 36, 'same_sentence': 114}). Sample sha256 `e06f0d41bbe97201…`.
- 450 pairs in one shuffled blind sheet (`data/interim/pair_recall/pair_recall_blind_sheet.csv`, guide `docs/cr010/PAIR_RECALL_ANNOTATION_GUIDE.md`); columns exactly `true_relation_exists, relation_if_yes, direction_if_yes, evidence_supported, notes`.
- Classifier run on the 300 P1/P2 samples and **sealed** (300/300 done; P0 reuses the stored run results); revealed only after `freeze-annotation`.
- Truth (fixed now): `true_relation_exists = yes` AND `evidence_supported != no`. Estimator: pool proportion x pool size; 95% percentile bootstrap resampling evidence sections within each pool.

### Results (human labels)

| pool | true / n | prevalence | 95% CI (clustered) | naive Wilson | estimated true edges |
|---|---|---|---|---|---|
| P0 | 112/150 | 74.7% | [66.7%, 80.6%] | [67.2%, 81.0%] | 821 [733, 886] |
| P1_extra | 67/150 | 44.7% | [35.8%, 52.9%] | [36.9%, 52.7%] | 3453 [2764, 4092] |
| P2_extra_strict | 38/150 | 25.3% | [17.1%, 34.8%] | [19.0%, 32.8%] | 1246 [843, 1710] |

| pair recall within the P2 universe | point | 95% CI (clustered) |
|---|---|---|
| P0 | 14.9% | [12.6%, 17.6%] |
| P1 | 77.4% | [70.4%, 83.9%] |
| P2 | 100.0% | [100.0%, 100.0%] |

Label counts: {'P0': {'no': 38, 'yes': 112}, 'P1_extra': {'no': 83, 'yes': 67}, 'P2_extra_strict': {'no': 112, 'yes': 38}}. Both sensitivities (evidence ignored; unclear as yes) give identical numbers: no `unclear` label and no `evidence_supported = no` among the 450.

Pair recall is measured against true edges inside the enumerated universe (same sentence, or adjacent sentences with a strict cue); edges outside it are not counted. It is NOT conditional classifier accuracy.

### Conditional classifier accuracy (revealed after the annotation was frozen; separate from pair recall)

| pool | recall on human-true | precision vs human | same relation among TP |
|---|---|---|---|
| P0 | 71/112 (63%) | 71/75 (95%) | 66/71 |
| P1_extra | 35/67 (52%) | 35/49 (71%) | 27/35 |
| P2_extra_strict | 18/38 (47%) | 18/29 (62%) | 16/18 |

## 4. Actual spend

- Run `cr010_pair_recall`: **$1.8088** over 534 logged calls (4 cache hits). Approved ~$2.50, hard cap $4 before P3. The estimate was $2.49 for 300 pairs.

## 5. Human IAA availability

- 60-item subset frozen (hash `c03e9a798cdc1b2f…`): {'ACCEPTED_EDGE': 40, 'NO_RELATION': 10, 'OTHER_NEAR_MISS': 10}, split {'dev': 24, 'test': 36}, 15 relations covered (1-3 items each); hidden manifest `cr010_relmap180_iaa_hidden_manifest_DO_NOT_SHARE.csv`; blank sheet for annotator 2 `cr010_relmap180_iaa_annotator2_blind_sheet.csv`.
- **Second human annotator: none recorded. IAA gate = NOT_EVALUABLE; FULL_ERST_REPLACEMENT is ineligible until one annotates the 60 items.** An LLM does not satisfy the gate.
- **Protocol deviation:** annotator 1 had ALREADY completed and saved all 180 rows (the owner's marked sheet, saved 2026-10-06) when this subset was frozen. The selection cannot depend on those labels (it never reads them) but the CR's 'freeze before annotator-1 outcomes are known' was not met. Disclosed to Research.
