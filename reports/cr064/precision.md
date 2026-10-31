# CR-064: relation precision and recall by relation (20 first-set papers; overlap `IDXR1OV-P1`, strict beside)

## v5

### Predicted relations (overlap): where precision is lost

| relation | predicted | TP | P | wrong direction | wrong label | unannotated pair | non-gold endpoint | unplaced | strict P |
|---|---|---|---|---|---|---|---|---|---|
| UsedFor | 125 | 16 | 0.13 | 0 | 2 | 7 | 98 | 2 | 0.06 |
| partOf | 64 | 2 | 0.03 | 1 | 5 | 3 | 50 | 3 | 0.02 |
| compareWith | 89 | 29 | 0.33 | 0 | 5 | 14 | 40 | 1 | 0.28 |
| MeasuredBy | 70 | 32 | 0.46 | 0 | 0 | 7 | 30 | 1 | 0.34 |
| subclassOf | 32 | 3 | 0.09 | 0 | 3 | 3 | 23 | 0 | 0.09 |
| trainedWith | 26 | 5 | 0.19 | 0 | 0 | 0 | 19 | 2 | 0.15 |
| enhancedBy | 19 | 0 | 0.00 | 0 | 0 | 3 | 16 | 0 | 0.00 |
| evaluatedBy | 22 | 7 | 0.32 | 0 | 2 | 1 | 11 | 1 | 0.18 |
| subtaskOf | 10 | 4 | 0.40 | 0 | 0 | 1 | 5 | 0 | 0.40 |
| evaluatedOn | 7 | 2 | 0.29 | 0 | 0 | 0 | 5 | 0 | 0.14 |
| similarWith | 6 | 2 | 0.33 | 0 | 1 | 0 | 2 | 1 | 0.00 |
| (edge without node or quote) | 2 | 0 | 0.00 | 0 | 0 | 0 | 0 | 2 | 0.00 |
| **all** | 472 | 102 | 0.216 | 1 | 18 | 39 | 299 | 13 | |

Most frequent wrong labels (predicted on gold): compareWith on gold partOf x3; subclassOf on gold subtaskOf x2; UsedFor on gold enhancedBy x2; evaluatedBy on gold MeasuredBy x2; partOf on gold similarWith x2; subclassOf on gold evaluatedOn x1; compareWith on gold subclassOf x1; partOf on gold evaluatedBy x1; similarWith on gold partOf x1; partOf on gold subtaskOf x1; compareWith on gold MeasuredBy x1; partOf on gold enhancedBy x1

### Gold relations (overlap): recall and the classification-conditional rate

| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |
|---|---|---|---|---|---|---|---|
| MeasuredBy | 92 | 72 | 66 | 38 | 32 | 0.35 | 0.48 |
| UsedFor | 89 | 66 | 59 | 38 | 16 | 0.18 | 0.27 |
| compareWith | 76 | 66 | 61 | 42 | 29 | 0.38 | 0.48 |
| subtaskOf | 47 | 25 | 18 | 7 | 4 | 0.09 | 0.22 |
| trainedWith | 46 | 37 | 30 | 6 | 5 | 0.11 | 0.17 |
| enhancedBy | 41 | 30 | 28 | 2 | 0 | 0.00 | 0.00 |
| partOf | 34 | 21 | 18 | 2 | 2 | 0.06 | 0.11 |
| similarWith | 22 | 10 | 10 | 2 | 2 | 0.09 | 0.20 |
| evaluatedBy | 17 | 14 | 14 | 8 | 7 | 0.41 | 0.50 |
| subclassOf | 17 | 13 | 9 | 3 | 3 | 0.18 | 0.33 |
| evaluatedOn | 17 | 14 | 8 | 2 | 2 | 0.12 | 0.25 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 13 {'domain_range': 8, 'endpoint_not_grounded': 3, 'surface_phrase_not_in_quote': 2}
- wrong choice rejected (noise removed): 368 {'domain_range': 322, 'endpoint_not_grounded': 27, 'evidence_quote_not_in_sentence': 8, 'surface_phrase_not_in_quote': 11}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 738, 'family_fp': 837, 'choice_on_negative': 649, 'checks_dropped_wrong': 368, 'selected_positive': 265, 'family_tp': 213, 'choice_right': 125, 'checks_passed_correct': 112, 'in_graph_correct': 111, 'choice_wrong_label': 66, 'checks_passed_wrong': 347, 'in_graph_wrong': 338, 'choice_declined_positive': 22, 'assembly_dropped_wrong': 7, 'choice_declined_negative': 188, 'checks_dropped_correct': 13, 'family_fn': 52, 'assembly_dropped_correct': 1, 'unplaced_wrong': 2}

## arm R2

### Predicted relations (overlap): where precision is lost

| relation | predicted | TP | P | wrong direction | wrong label | unannotated pair | non-gold endpoint | unplaced | strict P |
|---|---|---|---|---|---|---|---|---|---|
| UsedFor | 172 | 20 | 0.12 | 0 | 7 | 9 | 134 | 2 | 0.06 |
| partOf | 62 | 0 | 0.00 | 1 | 4 | 2 | 54 | 1 | 0.00 |
| compareWith | 87 | 29 | 0.33 | 0 | 4 | 15 | 38 | 1 | 0.29 |
| trainedWith | 63 | 15 | 0.24 | 0 | 1 | 4 | 41 | 2 | 0.14 |
| MeasuredBy | 80 | 34 | 0.42 | 0 | 1 | 8 | 37 | 0 | 0.33 |
| enhancedBy | 37 | 3 | 0.08 | 0 | 1 | 4 | 29 | 0 | 0.08 |
| evaluatedBy | 30 | 6 | 0.20 | 0 | 2 | 3 | 18 | 1 | 0.13 |
| subclassOf | 26 | 4 | 0.15 | 0 | 1 | 2 | 19 | 0 | 0.12 |
| evaluatedOn | 15 | 4 | 0.27 | 0 | 1 | 1 | 9 | 0 | 0.20 |
| subtaskOf | 14 | 5 | 0.36 | 0 | 1 | 1 | 6 | 1 | 0.21 |
| similarWith | 5 | 1 | 0.20 | 0 | 2 | 0 | 1 | 1 | 0.00 |
| (edge without node or quote) | 3 | 0 | 0.00 | 0 | 0 | 0 | 0 | 3 | 0.00 |
| **all** | 594 | 121 | 0.204 | 1 | 25 | 49 | 386 | 12 | |

Most frequent wrong labels (predicted on gold): UsedFor on gold trainedWith x3; UsedFor on gold enhancedBy x2; UsedFor on gold subtaskOf x2; evaluatedBy on gold MeasuredBy x2; partOf on gold similarWith x2; compareWith on gold UsedFor x1; subtaskOf on gold evaluatedOn x1; trainedWith on gold UsedFor x1; compareWith on gold subclassOf x1; compareWith on gold partOf x1; compareWith on gold MeasuredBy x1; evaluatedOn on gold trainedWith x1

### Gold relations (overlap): recall and the classification-conditional rate

| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |
|---|---|---|---|---|---|---|---|
| MeasuredBy | 92 | 72 | 66 | 38 | 34 | 0.37 | 0.52 |
| UsedFor | 89 | 66 | 59 | 38 | 20 | 0.22 | 0.34 |
| compareWith | 76 | 66 | 61 | 46 | 29 | 0.38 | 0.48 |
| subtaskOf | 47 | 25 | 18 | 8 | 5 | 0.11 | 0.28 |
| trainedWith | 46 | 37 | 30 | 19 | 15 | 0.33 | 0.50 |
| enhancedBy | 41 | 30 | 28 | 4 | 3 | 0.07 | 0.11 |
| partOf | 34 | 21 | 18 | 0 | 0 | 0.00 | 0.00 |
| similarWith | 22 | 10 | 10 | 1 | 1 | 0.05 | 0.10 |
| evaluatedBy | 17 | 14 | 14 | 7 | 6 | 0.35 | 0.43 |
| subclassOf | 17 | 13 | 9 | 4 | 4 | 0.24 | 0.44 |
| evaluatedOn | 17 | 14 | 8 | 4 | 4 | 0.24 | 0.50 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 10 {'surface_phrase_not_in_quote': 6, 'endpoint_not_grounded': 2, 'endpoint_fit': 2}
- wrong choice rejected (noise removed): 33 {'endpoint_not_grounded': 16, 'endpoint_fit': 4, 'surface_phrase_not_in_quote': 9, 'evidence_quote_not_in_sentence': 3, 'negation_without_cue': 1}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 738, 'family_fp': 837, 'choice_declined_negative': 398, 'selected_positive': 265, 'family_tp': 213, 'choice_right': 143, 'checks_passed_correct': 133, 'in_graph_correct': 132, 'choice_on_negative': 439, 'checks_passed_wrong': 437, 'in_graph_wrong': 429, 'checks_dropped_wrong': 33, 'choice_declined_positive': 39, 'assembly_dropped_wrong': 5, 'choice_wrong_label': 31, 'checks_dropped_correct': 10, 'family_fn': 52, 'unplaced_wrong': 3, 'assembly_dropped_correct': 1}

## arm R3

### Predicted relations (overlap): where precision is lost

| relation | predicted | TP | P | wrong direction | wrong label | unannotated pair | non-gold endpoint | unplaced | strict P |
|---|---|---|---|---|---|---|---|---|---|
| UsedFor | 133 | 20 | 0.15 | 0 | 4 | 6 | 101 | 2 | 0.08 |
| partOf | 71 | 2 | 0.03 | 1 | 4 | 5 | 57 | 2 | 0.03 |
| compareWith | 77 | 30 | 0.39 | 0 | 5 | 10 | 31 | 1 | 0.32 |
| trainedWith | 58 | 14 | 0.24 | 0 | 1 | 5 | 36 | 2 | 0.17 |
| MeasuredBy | 68 | 32 | 0.47 | 0 | 0 | 8 | 28 | 0 | 0.35 |
| enhancedBy | 31 | 2 | 0.06 | 0 | 0 | 3 | 26 | 0 | 0.06 |
| evaluatedBy | 31 | 6 | 0.19 | 0 | 2 | 2 | 20 | 1 | 0.10 |
| subclassOf | 19 | 3 | 0.16 | 0 | 1 | 0 | 15 | 0 | 0.11 |
| evaluatedOn | 13 | 5 | 0.38 | 0 | 1 | 1 | 6 | 0 | 0.23 |
| similarWith | 8 | 1 | 0.12 | 0 | 4 | 0 | 2 | 1 | 0.00 |
| subtaskOf | 9 | 3 | 0.33 | 0 | 0 | 1 | 4 | 1 | 0.33 |
| (edge without node or quote) | 1 | 0 | 0.00 | 0 | 0 | 0 | 0 | 1 | 0.00 |
| **all** | 519 | 118 | 0.227 | 1 | 22 | 41 | 326 | 11 | |

Most frequent wrong labels (predicted on gold): compareWith on gold partOf x3; UsedFor on gold enhancedBy x2; evaluatedBy on gold MeasuredBy x2; partOf on gold enhancedBy x2; compareWith on gold UsedFor x1; trainedWith on gold UsedFor x1; UsedFor on gold subtaskOf x1; compareWith on gold MeasuredBy x1; evaluatedOn on gold trainedWith x1; partOf on gold similarWith x1; similarWith on gold subclassOf x1; similarWith on gold partOf x1

### Gold relations (overlap): recall and the classification-conditional rate

| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |
|---|---|---|---|---|---|---|---|
| MeasuredBy | 92 | 72 | 66 | 41 | 32 | 0.35 | 0.48 |
| UsedFor | 89 | 66 | 59 | 34 | 20 | 0.22 | 0.34 |
| compareWith | 76 | 66 | 61 | 45 | 30 | 0.39 | 0.49 |
| subtaskOf | 47 | 25 | 18 | 3 | 3 | 0.06 | 0.17 |
| trainedWith | 46 | 37 | 30 | 16 | 14 | 0.30 | 0.47 |
| enhancedBy | 41 | 30 | 28 | 3 | 2 | 0.05 | 0.07 |
| partOf | 34 | 21 | 18 | 2 | 2 | 0.06 | 0.11 |
| similarWith | 22 | 10 | 10 | 1 | 1 | 0.05 | 0.10 |
| evaluatedBy | 17 | 14 | 14 | 7 | 6 | 0.35 | 0.43 |
| subclassOf | 17 | 13 | 9 | 3 | 3 | 0.18 | 0.33 |
| evaluatedOn | 17 | 14 | 8 | 5 | 5 | 0.29 | 0.62 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 7 {'endpoint_not_grounded': 3, 'surface_phrase_not_in_quote': 3, 'evidence_quote_not_in_sentence': 1}
- wrong choice rejected (noise removed): 29 {'endpoint_not_grounded': 14, 'evidence_quote_not_in_sentence': 5, 'surface_phrase_not_in_quote': 8, 'endpoint_fit': 1, 'negation_without_cue': 1}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 738, 'family_fp': 837, 'choice_declined_negative': 470, 'selected_positive': 265, 'family_tp': 213, 'choice_right': 134, 'checks_passed_correct': 127, 'in_graph_correct': 127, 'choice_declined_positive': 52, 'choice_on_negative': 367, 'checks_passed_wrong': 365, 'in_graph_wrong': 358, 'checks_dropped_wrong': 29, 'assembly_dropped_wrong': 6, 'choice_wrong_label': 27, 'family_fn': 52, 'checks_dropped_correct': 7, 'unplaced_wrong': 1}

