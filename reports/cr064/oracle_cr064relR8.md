# CR-064: relation-step oracle ladder, R8 (origin sentence, no partOf) (20 first-set papers, overlap `IDXR1OV-P1`, $0)

Recomputed arm score: TP 130, predicted 486, gold 498 -> P 0.267 / R 0.261 / F1 0.264.

## 1. Where the gold relations are lost (each stage keeps only what survived the one before)

| stage | gold relations still alive | % of gold | lost here |
|---|---|---|---|
| gold | 498 | 100.0% |  |
| endpoints_placed | 368 | 73.9% | 130 |
| pair_selected | 321 | 64.5% | 47 |
| family_right | 267 | 53.6% | 54 |
| choice_right | 174 | 34.9% | 93 |
| checks_passed | 173 | 34.7% | 1 |
| assembled | 173 | 34.7% | 0 |
| credited | 130 | 26.1% | 43 |

Gold relations whose pair was never selected: same sentence vs other sentence = {'same_sentence': 47}.

## 2. Pair-level accounting (selected pairs)

```
{
 "selected": 1840,
 "selected_negative": 1575,
 "family_tn": 802,
 "selected_positive": 265,
 "family_tp": 216,
 "choice_right": 143,
 "checks_passed_correct": 142,
 "in_graph_correct": 142,
 "family_fp": 773,
 "choice_on_negative": 327,
 "checks_passed_wrong": 334,
 "in_graph_wrong": 327,
 "checks_dropped_wrong": 15,
 "choice_declined_negative": 446,
 "assembly_dropped_wrong": 6,
 "choice_wrong_label": 22,
 "choice_declined_positive": 51,
 "family_fn": 49,
 "unplaced_wrong": 1,
 "checks_dropped_correct": 1
}
```

## 3. Oracle ladder (recall side): ceiling if that stage and all later ones were perfect

| oracle | credited gold | recall | precision (FPs kept) | F1 (FPs kept) | F1 (FPs removed) |
|---|---|---|---|---|---|
| as run | 130 | 0.261 | 0.267 | **0.264** | 0.414 |
| perfect mention-level credit (edge on the right gold mention pair) | 173 | 0.347 | 0.327 | **0.337** | 0.516 |
| perfect checks and assembly | 174 | 0.349 | 0.328 | **0.339** | 0.518 |
| perfect choice (label + direction) | 267 | 0.536 | 0.429 | **0.476** | 0.698 |
| perfect pair selection and classification | 368 | 0.739 | 0.508 | **0.602** | 0.850 |
| perfect concepts (every gold endpoint is a node) | 498 | 1.000 | 0.583 | **0.737** | 1.000 |

## 4. Precision-side oracles (recall fixed), cumulative

| oracle | predicted left | precision | F1 |
|---|---|---|---|
| remove wrong direction + wrong label (choice errors on gold pairs) | 468 | 0.278 | **0.269** |
| also remove unplaced edges | 459 | 0.283 | **0.272** |
| also remove non-gold endpoints (concept precision) | 174 | 0.747 | **0.387** |
| also remove unannotated pairs (gold incompleteness) | 130 | 1.000 | **0.414** |

False positives by kind: {'wrong direction': 0, 'wrong label': 18, 'unannotated pair': 44, 'non-gold endpoint': 285, 'unplaced': 9}
