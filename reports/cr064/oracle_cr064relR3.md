# CR-064: relation-step oracle ladder, R3 (20 first-set papers, overlap `IDXR1OV-P1`, $0)

Recomputed arm score: TP 118, predicted 519, gold 498 -> P 0.227 / R 0.237 / F1 0.232.

## 1. Where the gold relations are lost (each stage keeps only what survived the one before)

| stage | gold relations still alive | % of gold | lost here |
|---|---|---|---|
| gold | 498 | 100.0% |  |
| endpoints_placed | 368 | 73.9% | 130 |
| pair_selected | 321 | 64.5% | 47 |
| family_right | 256 | 51.4% | 65 |
| choice_right | 160 | 32.1% | 96 |
| checks_passed | 153 | 30.7% | 7 |
| assembled | 153 | 30.7% | 0 |
| credited | 118 | 23.7% | 35 |

Gold relations whose pair was never selected: same sentence vs other sentence = {'same_sentence': 47}.

## 2. Pair-level accounting (selected pairs)

```
{
 "selected": 1840,
 "selected_negative": 1575,
 "family_tn": 738,
 "family_fp": 837,
 "choice_declined_negative": 470,
 "selected_positive": 265,
 "family_tp": 213,
 "choice_right": 134,
 "checks_passed_correct": 127,
 "in_graph_correct": 127,
 "choice_declined_positive": 52,
 "choice_on_negative": 367,
 "checks_passed_wrong": 365,
 "in_graph_wrong": 358,
 "checks_dropped_wrong": 29,
 "assembly_dropped_wrong": 6,
 "choice_wrong_label": 27,
 "family_fn": 52,
 "checks_dropped_correct": 7,
 "unplaced_wrong": 1
}
```

## 3. Oracle ladder (recall side): ceiling if that stage and all later ones were perfect

| oracle | credited gold | recall | precision (FPs kept) | F1 (FPs kept) | F1 (FPs removed) |
|---|---|---|---|---|---|
| as run | 118 | 0.237 | 0.227 | **0.232** | 0.383 |
| perfect mention-level credit (edge on the right gold mention pair) | 153 | 0.307 | 0.276 | **0.291** | 0.470 |
| perfect checks and assembly | 160 | 0.321 | 0.285 | **0.302** | 0.486 |
| perfect choice (label + direction) | 256 | 0.514 | 0.390 | **0.443** | 0.679 |
| perfect pair selection and classification | 368 | 0.739 | 0.479 | **0.581** | 0.850 |
| perfect concepts (every gold endpoint is a node) | 498 | 1.000 | 0.554 | **0.713** | 1.000 |

## 4. Precision-side oracles (recall fixed), cumulative

| oracle | predicted left | precision | F1 |
|---|---|---|---|
| remove wrong direction + wrong label (choice errors on gold pairs) | 496 | 0.238 | **0.237** |
| also remove unplaced edges | 485 | 0.243 | **0.240** |
| also remove non-gold endpoints (concept precision) | 159 | 0.742 | **0.359** |
| also remove unannotated pairs (gold incompleteness) | 118 | 1.000 | **0.383** |

False positives by kind: {'wrong direction': 1, 'wrong label': 22, 'unannotated pair': 41, 'non-gold endpoint': 326, 'unplaced': 11}
