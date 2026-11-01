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
| evaluatedOn | 17 | 14 | 8 | 2 | 2 | 0.12 | 0.25 |
| subclassOf | 17 | 13 | 9 | 3 | 3 | 0.18 | 0.33 |

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
| evaluatedOn | 17 | 14 | 8 | 4 | 4 | 0.24 | 0.50 |
| subclassOf | 17 | 13 | 9 | 4 | 4 | 0.24 | 0.44 |

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
| evaluatedOn | 17 | 14 | 8 | 5 | 5 | 0.29 | 0.62 |
| subclassOf | 17 | 13 | 9 | 3 | 3 | 0.18 | 0.33 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 7 {'endpoint_not_grounded': 3, 'surface_phrase_not_in_quote': 3, 'evidence_quote_not_in_sentence': 1}
- wrong choice rejected (noise removed): 29 {'endpoint_not_grounded': 14, 'evidence_quote_not_in_sentence': 5, 'surface_phrase_not_in_quote': 8, 'endpoint_fit': 1, 'negation_without_cue': 1}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 738, 'family_fp': 837, 'choice_declined_negative': 470, 'selected_positive': 265, 'family_tp': 213, 'choice_right': 134, 'checks_passed_correct': 127, 'in_graph_correct': 127, 'choice_declined_positive': 52, 'choice_on_negative': 367, 'checks_passed_wrong': 365, 'in_graph_wrong': 358, 'checks_dropped_wrong': 29, 'assembly_dropped_wrong': 6, 'choice_wrong_label': 27, 'family_fn': 52, 'checks_dropped_correct': 7, 'unplaced_wrong': 1}

## arm R5

### Predicted relations (overlap): where precision is lost

| relation | predicted | TP | P | wrong direction | wrong label | unannotated pair | non-gold endpoint | unplaced | strict P |
|---|---|---|---|---|---|---|---|---|---|
| UsedFor | 138 | 21 | 0.15 | 0 | 4 | 7 | 105 | 1 | 0.08 |
| compareWith | 91 | 31 | 0.34 | 0 | 4 | 15 | 40 | 1 | 0.30 |
| trainedWith | 54 | 16 | 0.30 | 0 | 0 | 5 | 31 | 2 | 0.20 |
| enhancedBy | 39 | 2 | 0.05 | 0 | 1 | 3 | 32 | 1 | 0.05 |
| MeasuredBy | 65 | 35 | 0.54 | 0 | 0 | 7 | 23 | 0 | 0.40 |
| evaluatedBy | 33 | 7 | 0.21 | 0 | 2 | 4 | 19 | 1 | 0.12 |
| subclassOf | 18 | 3 | 0.17 | 0 | 2 | 0 | 13 | 0 | 0.11 |
| subtaskOf | 11 | 4 | 0.36 | 0 | 1 | 1 | 4 | 1 | 0.27 |
| evaluatedOn | 12 | 5 | 0.42 | 0 | 0 | 1 | 6 | 0 | 0.25 |
| similarWith | 5 | 1 | 0.20 | 0 | 1 | 1 | 1 | 1 | 0.00 |
| (edge without node or quote) | 2 | 0 | 0.00 | 0 | 0 | 0 | 0 | 2 | 0.00 |
| **all** | 468 | 125 | 0.267 | 0 | 15 | 44 | 274 | 10 | |

Most frequent wrong labels (predicted on gold): compareWith on gold partOf x3; UsedFor on gold enhancedBy x2; evaluatedBy on gold MeasuredBy x2; UsedFor on gold trainedWith x2; compareWith on gold UsedFor x1; subtaskOf on gold evaluatedOn x1; enhancedBy on gold partOf x1; subclassOf on gold partOf x1; similarWith on gold trainedWith x1; subclassOf on gold similarWith x1

### Gold relations (overlap): recall and the classification-conditional rate

| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |
|---|---|---|---|---|---|---|---|
| MeasuredBy | 92 | 72 | 66 | 39 | 35 | 0.38 | 0.53 |
| UsedFor | 89 | 66 | 59 | 36 | 21 | 0.24 | 0.36 |
| compareWith | 76 | 66 | 61 | 48 | 31 | 0.41 | 0.51 |
| subtaskOf | 47 | 25 | 18 | 4 | 4 | 0.09 | 0.22 |
| trainedWith | 46 | 37 | 30 | 19 | 16 | 0.35 | 0.53 |
| enhancedBy | 41 | 30 | 28 | 3 | 2 | 0.05 | 0.07 |
| partOf | 34 | 21 | 18 | 0 | 0 | 0.00 | 0.00 |
| similarWith | 22 | 10 | 10 | 1 | 1 | 0.05 | 0.10 |
| evaluatedBy | 17 | 14 | 14 | 8 | 7 | 0.41 | 0.50 |
| evaluatedOn | 17 | 14 | 8 | 5 | 5 | 0.29 | 0.62 |
| subclassOf | 17 | 13 | 9 | 3 | 3 | 0.18 | 0.33 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 3 {'endpoint_not_grounded': 2, 'surface_phrase_not_in_quote': 1}
- wrong choice rejected (noise removed): 21 {'endpoint_not_grounded': 11, 'surface_phrase_not_in_quote': 6, 'evidence_quote_not_in_sentence': 4}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 799, 'family_fp': 776, 'choice_declined_negative': 462, 'selected_positive': 265, 'family_tp': 214, 'choice_right': 140, 'checks_passed_correct': 137, 'in_graph_correct': 137, 'choice_on_negative': 314, 'checks_passed_wrong': 312, 'in_graph_wrong': 305, 'checks_dropped_wrong': 21, 'choice_declined_positive': 55, 'assembly_dropped_wrong': 5, 'choice_wrong_label': 19, 'family_fn': 51, 'checks_dropped_correct': 3, 'unplaced_wrong': 2}

## arm R6

### Predicted relations (overlap): where precision is lost

| relation | predicted | TP | P | wrong direction | wrong label | unannotated pair | non-gold endpoint | unplaced | strict P |
|---|---|---|---|---|---|---|---|---|---|
| UsedFor | 140 | 21 | 0.15 | 0 | 5 | 6 | 107 | 1 | 0.08 |
| partOf | 70 | 2 | 0.03 | 1 | 3 | 2 | 59 | 3 | 0.01 |
| compareWith | 87 | 32 | 0.37 | 0 | 4 | 16 | 35 | 0 | 0.31 |
| trainedWith | 61 | 14 | 0.23 | 0 | 1 | 5 | 39 | 2 | 0.15 |
| MeasuredBy | 67 | 32 | 0.48 | 0 | 0 | 6 | 29 | 0 | 0.36 |
| enhancedBy | 31 | 1 | 0.03 | 1 | 0 | 3 | 25 | 1 | 0.03 |
| evaluatedBy | 27 | 8 | 0.30 | 0 | 2 | 2 | 14 | 1 | 0.15 |
| subclassOf | 20 | 3 | 0.15 | 0 | 1 | 0 | 16 | 0 | 0.10 |
| subtaskOf | 10 | 3 | 0.30 | 0 | 1 | 1 | 4 | 1 | 0.30 |
| similarWith | 7 | 1 | 0.14 | 0 | 3 | 0 | 2 | 1 | 0.00 |
| evaluatedOn | 8 | 3 | 0.38 | 0 | 0 | 1 | 4 | 0 | 0.25 |
| (edge without node or quote) | 4 | 0 | 0.00 | 0 | 0 | 0 | 0 | 4 | 0.00 |
| **all** | 532 | 120 | 0.226 | 2 | 20 | 42 | 334 | 14 | |

Most frequent wrong labels (predicted on gold): UsedFor on gold trainedWith x3; compareWith on gold partOf x3; UsedFor on gold enhancedBy x2; evaluatedBy on gold MeasuredBy x2; similarWith on gold subclassOf x2; partOf on gold enhancedBy x2; compareWith on gold UsedFor x1; subtaskOf on gold evaluatedOn x1; trainedWith on gold UsedFor x1; partOf on gold similarWith x1; similarWith on gold partOf x1; subclassOf on gold similarWith x1

### Gold relations (overlap): recall and the classification-conditional rate

| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |
|---|---|---|---|---|---|---|---|
| MeasuredBy | 92 | 72 | 66 | 37 | 32 | 0.35 | 0.48 |
| UsedFor | 89 | 66 | 59 | 36 | 21 | 0.24 | 0.36 |
| compareWith | 76 | 66 | 61 | 46 | 32 | 0.42 | 0.52 |
| subtaskOf | 47 | 25 | 18 | 3 | 3 | 0.06 | 0.17 |
| trainedWith | 46 | 37 | 30 | 19 | 14 | 0.30 | 0.47 |
| enhancedBy | 41 | 30 | 28 | 2 | 1 | 0.02 | 0.04 |
| partOf | 34 | 21 | 18 | 2 | 2 | 0.06 | 0.11 |
| similarWith | 22 | 10 | 10 | 1 | 1 | 0.05 | 0.10 |
| evaluatedBy | 17 | 14 | 14 | 9 | 8 | 0.47 | 0.57 |
| evaluatedOn | 17 | 14 | 8 | 3 | 3 | 0.18 | 0.38 |
| subclassOf | 17 | 13 | 9 | 3 | 3 | 0.18 | 0.33 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 4 {'endpoint_not_grounded': 1, 'surface_phrase_not_in_quote': 2, 'evidence_quote_not_in_sentence': 1}
- wrong choice rejected (noise removed): 23 {'endpoint_not_grounded': 12, 'evidence_quote_not_in_sentence': 3, 'surface_phrase_not_in_quote': 8}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 738, 'family_fp': 837, 'choice_declined_negative': 467, 'selected_positive': 265, 'family_tp': 213, 'choice_right': 134, 'checks_passed_correct': 130, 'in_graph_correct': 130, 'choice_on_negative': 370, 'checks_passed_wrong': 373, 'in_graph_wrong': 366, 'checks_dropped_wrong': 23, 'choice_declined_positive': 53, 'choice_wrong_label': 26, 'checks_dropped_correct': 4, 'family_fn': 52, 'unplaced_wrong': 4, 'assembly_dropped_wrong': 3}

## arm R7

### Predicted relations (overlap): where precision is lost

| relation | predicted | TP | P | wrong direction | wrong label | unannotated pair | non-gold endpoint | unplaced | strict P |
|---|---|---|---|---|---|---|---|---|---|
| UsedFor | 136 | 20 | 0.15 | 0 | 4 | 6 | 104 | 2 | 0.07 |
| partOf | 66 | 1 | 0.02 | 1 | 4 | 2 | 56 | 2 | 0.02 |
| compareWith | 93 | 31 | 0.33 | 0 | 3 | 22 | 37 | 0 | 0.29 |
| trainedWith | 49 | 13 | 0.27 | 0 | 1 | 2 | 30 | 3 | 0.18 |
| MeasuredBy | 67 | 34 | 0.51 | 0 | 0 | 7 | 26 | 0 | 0.37 |
| enhancedBy | 30 | 2 | 0.07 | 0 | 0 | 4 | 23 | 1 | 0.07 |
| subclassOf | 23 | 5 | 0.22 | 0 | 2 | 0 | 16 | 0 | 0.13 |
| evaluatedBy | 25 | 7 | 0.28 | 0 | 2 | 2 | 14 | 0 | 0.16 |
| subtaskOf | 12 | 4 | 0.33 | 0 | 1 | 1 | 5 | 1 | 0.33 |
| similarWith | 7 | 1 | 0.14 | 0 | 2 | 0 | 3 | 1 | 0.00 |
| evaluatedOn | 11 | 5 | 0.45 | 0 | 0 | 1 | 5 | 0 | 0.27 |
| (edge without node or quote) | 4 | 0 | 0.00 | 0 | 0 | 0 | 0 | 4 | 0.00 |
| **all** | 523 | 123 | 0.235 | 1 | 19 | 47 | 319 | 14 | |

Most frequent wrong labels (predicted on gold): compareWith on gold partOf x3; evaluatedBy on gold MeasuredBy x2; partOf on gold enhancedBy x2; UsedFor on gold trainedWith x2; subtaskOf on gold evaluatedOn x1; trainedWith on gold UsedFor x1; UsedFor on gold enhancedBy x1; subclassOf on gold subtaskOf x1; UsedFor on gold subtaskOf x1; partOf on gold similarWith x1; similarWith on gold partOf x1; similarWith on gold trainedWith x1

### Gold relations (overlap): recall and the classification-conditional rate

| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |
|---|---|---|---|---|---|---|---|
| MeasuredBy | 92 | 72 | 66 | 40 | 34 | 0.37 | 0.52 |
| UsedFor | 89 | 66 | 59 | 36 | 20 | 0.22 | 0.34 |
| compareWith | 76 | 66 | 61 | 47 | 31 | 0.41 | 0.51 |
| subtaskOf | 47 | 25 | 18 | 4 | 4 | 0.09 | 0.22 |
| trainedWith | 46 | 37 | 30 | 17 | 13 | 0.28 | 0.43 |
| enhancedBy | 41 | 30 | 28 | 3 | 2 | 0.05 | 0.07 |
| partOf | 34 | 21 | 18 | 1 | 1 | 0.03 | 0.06 |
| similarWith | 22 | 10 | 10 | 1 | 1 | 0.05 | 0.10 |
| evaluatedBy | 17 | 14 | 14 | 8 | 7 | 0.41 | 0.50 |
| evaluatedOn | 17 | 14 | 8 | 5 | 5 | 0.29 | 0.62 |
| subclassOf | 17 | 13 | 9 | 5 | 5 | 0.29 | 0.56 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 2 {'endpoint_not_grounded': 1, 'surface_phrase_not_in_quote': 1}
- wrong choice rejected (noise removed): 27 {'endpoint_not_grounded': 12, 'evidence_quote_not_in_sentence': 6, 'surface_phrase_not_in_quote': 8, 'endpoint_fit': 1}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 738, 'family_fp': 837, 'choice_declined_negative': 470, 'selected_positive': 265, 'family_tp': 213, 'choice_right': 139, 'checks_passed_correct': 137, 'in_graph_correct': 136, 'choice_declined_positive': 50, 'choice_on_negative': 367, 'checks_passed_wrong': 364, 'in_graph_wrong': 353, 'checks_dropped_wrong': 27, 'assembly_dropped_wrong': 7, 'choice_wrong_label': 24, 'family_fn': 52, 'checks_dropped_correct': 2, 'unplaced_wrong': 4, 'assembly_dropped_correct': 1}

## arm R8

### Predicted relations (overlap): where precision is lost

| relation | predicted | TP | P | wrong direction | wrong label | unannotated pair | non-gold endpoint | unplaced | strict P |
|---|---|---|---|---|---|---|---|---|---|
| UsedFor | 139 | 21 | 0.15 | 0 | 4 | 7 | 106 | 1 | 0.09 |
| compareWith | 91 | 33 | 0.36 | 0 | 3 | 19 | 36 | 0 | 0.31 |
| enhancedBy | 54 | 3 | 0.06 | 0 | 2 | 4 | 43 | 2 | 0.06 |
| trainedWith | 56 | 17 | 0.30 | 0 | 0 | 4 | 33 | 2 | 0.21 |
| MeasuredBy | 63 | 36 | 0.57 | 0 | 0 | 5 | 22 | 0 | 0.44 |
| evaluatedBy | 26 | 7 | 0.27 | 0 | 2 | 2 | 14 | 1 | 0.15 |
| subclassOf | 20 | 3 | 0.15 | 0 | 1 | 0 | 16 | 0 | 0.15 |
| subtaskOf | 16 | 5 | 0.31 | 0 | 2 | 1 | 7 | 1 | 0.25 |
| similarWith | 10 | 1 | 0.10 | 0 | 4 | 1 | 3 | 1 | 0.00 |
| evaluatedOn | 10 | 4 | 0.40 | 0 | 0 | 1 | 5 | 0 | 0.30 |
| (edge without node or quote) | 1 | 0 | 0.00 | 0 | 0 | 0 | 0 | 1 | 0.00 |
| **all** | 486 | 130 | 0.267 | 0 | 18 | 44 | 285 | 9 | |

Most frequent wrong labels (predicted on gold): UsedFor on gold trainedWith x2; UsedFor on gold enhancedBy x2; compareWith on gold partOf x2; evaluatedBy on gold MeasuredBy x2; enhancedBy on gold partOf x2; similarWith on gold subclassOf x2; compareWith on gold UsedFor x1; subtaskOf on gold evaluatedOn x1; similarWith on gold partOf x1; subtaskOf on gold partOf x1; similarWith on gold trainedWith x1; subclassOf on gold similarWith x1

### Gold relations (overlap): recall and the classification-conditional rate

| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |
|---|---|---|---|---|---|---|---|
| MeasuredBy | 92 | 72 | 66 | 43 | 36 | 0.39 | 0.55 |
| UsedFor | 89 | 66 | 59 | 36 | 21 | 0.24 | 0.36 |
| compareWith | 76 | 66 | 61 | 48 | 33 | 0.43 | 0.54 |
| subtaskOf | 47 | 25 | 18 | 5 | 5 | 0.11 | 0.28 |
| trainedWith | 46 | 37 | 30 | 22 | 17 | 0.37 | 0.57 |
| enhancedBy | 41 | 30 | 28 | 4 | 3 | 0.07 | 0.11 |
| partOf | 34 | 21 | 18 | 0 | 0 | 0.00 | 0.00 |
| similarWith | 22 | 10 | 10 | 1 | 1 | 0.05 | 0.10 |
| evaluatedBy | 17 | 14 | 14 | 8 | 7 | 0.41 | 0.50 |
| evaluatedOn | 17 | 14 | 8 | 4 | 4 | 0.24 | 0.50 |
| subclassOf | 17 | 13 | 9 | 3 | 3 | 0.18 | 0.33 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 1 {'endpoint_not_grounded': 1}
- wrong choice rejected (noise removed): 15 {'endpoint_not_grounded': 7, 'surface_phrase_not_in_quote': 5, 'evidence_quote_not_in_sentence': 1, 'endpoint_fit': 2}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 802, 'selected_positive': 265, 'family_tp': 216, 'choice_right': 143, 'checks_passed_correct': 142, 'in_graph_correct': 142, 'family_fp': 773, 'choice_on_negative': 327, 'checks_passed_wrong': 334, 'in_graph_wrong': 327, 'checks_dropped_wrong': 15, 'choice_declined_negative': 446, 'assembly_dropped_wrong': 6, 'choice_wrong_label': 22, 'choice_declined_positive': 51, 'family_fn': 49, 'unplaced_wrong': 1, 'checks_dropped_correct': 1}

## arm R9

### Predicted relations (overlap): where precision is lost

| relation | predicted | TP | P | wrong direction | wrong label | unannotated pair | non-gold endpoint | unplaced | strict P |
|---|---|---|---|---|---|---|---|---|---|
| UsedFor | 138 | 18 | 0.13 | 0 | 6 | 6 | 107 | 1 | 0.07 |
| enhancedBy | 56 | 4 | 0.07 | 0 | 2 | 5 | 45 | 0 | 0.07 |
| compareWith | 83 | 32 | 0.39 | 0 | 4 | 12 | 35 | 0 | 0.33 |
| trainedWith | 51 | 13 | 0.25 | 0 | 1 | 4 | 31 | 2 | 0.18 |
| MeasuredBy | 62 | 32 | 0.52 | 0 | 0 | 8 | 22 | 0 | 0.39 |
| evaluatedBy | 34 | 7 | 0.21 | 0 | 2 | 3 | 21 | 1 | 0.12 |
| subclassOf | 17 | 4 | 0.24 | 0 | 1 | 0 | 12 | 0 | 0.18 |
| subtaskOf | 13 | 4 | 0.31 | 0 | 0 | 1 | 8 | 0 | 0.23 |
| evaluatedOn | 8 | 4 | 0.50 | 0 | 0 | 0 | 4 | 0 | 0.38 |
| similarWith | 4 | 1 | 0.25 | 0 | 1 | 1 | 0 | 1 | 0.00 |
| (edge without node or quote) | 2 | 0 | 0.00 | 0 | 0 | 0 | 0 | 2 | 0.00 |
| **all** | 468 | 119 | 0.254 | 0 | 17 | 40 | 285 | 7 | |

Most frequent wrong labels (predicted on gold): UsedFor on gold trainedWith x4; compareWith on gold partOf x3; UsedFor on gold enhancedBy x2; evaluatedBy on gold MeasuredBy x2; enhancedBy on gold partOf x2; compareWith on gold UsedFor x1; trainedWith on gold UsedFor x1; similarWith on gold partOf x1; subclassOf on gold similarWith x1

### Gold relations (overlap): recall and the classification-conditional rate

| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |
|---|---|---|---|---|---|---|---|
| MeasuredBy | 92 | 72 | 66 | 37 | 32 | 0.35 | 0.48 |
| UsedFor | 89 | 66 | 59 | 31 | 18 | 0.20 | 0.31 |
| compareWith | 76 | 66 | 61 | 47 | 32 | 0.42 | 0.52 |
| subtaskOf | 47 | 25 | 18 | 5 | 4 | 0.09 | 0.22 |
| trainedWith | 46 | 37 | 30 | 16 | 13 | 0.28 | 0.43 |
| enhancedBy | 41 | 30 | 28 | 5 | 4 | 0.10 | 0.14 |
| partOf | 34 | 21 | 18 | 0 | 0 | 0.00 | 0.00 |
| similarWith | 22 | 10 | 10 | 1 | 1 | 0.05 | 0.10 |
| evaluatedBy | 17 | 14 | 14 | 8 | 7 | 0.41 | 0.50 |
| evaluatedOn | 17 | 14 | 8 | 4 | 4 | 0.24 | 0.50 |
| subclassOf | 17 | 13 | 9 | 4 | 4 | 0.24 | 0.44 |

### Checks: rejected relation results

- right choice rejected (a gold relation wrongly dropped): 3 {'surface_phrase_not_in_quote': 2, 'evidence_quote_not_in_sentence': 1}
- wrong choice rejected (noise removed): 22 {'endpoint_not_grounded': 8, 'endpoint_fit': 3, 'evidence_quote_not_in_sentence': 4, 'surface_phrase_not_in_quote': 7}
- pair accounting: {'selected': 1840, 'selected_negative': 1575, 'family_tn': 794, 'selected_positive': 265, 'family_tp': 215, 'choice_right': 133, 'checks_passed_correct': 130, 'in_graph_correct': 129, 'choice_declined_positive': 61, 'family_fp': 781, 'choice_on_negative': 325, 'checks_passed_wrong': 324, 'in_graph_wrong': 317, 'checks_dropped_wrong': 22, 'assembly_dropped_wrong': 5, 'choice_declined_negative': 456, 'choice_wrong_label': 21, 'checks_dropped_correct': 3, 'family_fn': 50, 'unplaced_wrong': 2, 'assembly_dropped_correct': 1}

