# CR-021 rejected-link adjudicator (v2)

Gold `data/gold/cr021_rejected_links_review_marked.csv` (model-assisted, checked by the owner); stratified 70/70 split; strong tier; spend $0.59 of $3.

## dev (72 rows, accuracy 0.861)

| decision | correct / decided | precision | Wilson LB |
|---|---|---|---|
| new_concept | 40 / 44 | 0.909 | 0.788 |
| same_as_target | 21 / 24 | 0.875 | 0.69 |
| not_a_concept | 1 / 4 | 0.25 | 0.046 |

Gold same-as-target rows decided new_concept: 2 / 25.
Confusion (gold->decision): {'new_concept->new_concept': 40, 'new_concept->not_a_concept': 1, 'new_concept->same_as_target': 3, 'not_a_concept->new_concept': 2, 'not_a_concept->not_a_concept': 1, 'same_as_target->new_concept': 2, 'same_as_target->not_a_concept': 2, 'same_as_target->same_as_target': 21}
Adopt promotion: **True** · adopt aliasing: **False** (pre-registered rule; binding on heldout only).

## heldout (68 rows, accuracy 0.941)

| decision | correct / decided | precision | Wilson LB |
|---|---|---|---|
| new_concept | 42 / 43 | 0.977 | 0.879 |
| same_as_target | 20 / 21 | 0.952 | 0.773 |
| not_a_concept | 2 / 4 | 0.5 | 0.15 |

Gold same-as-target rows decided new_concept: 1 / 22.
Confusion (gold->decision): {'new_concept->new_concept': 42, 'new_concept->not_a_concept': 1, 'new_concept->same_as_target': 1, 'not_a_concept->not_a_concept': 2, 'same_as_target->new_concept': 1, 'same_as_target->not_a_concept': 1, 'same_as_target->same_as_target': 20}
Adopt promotion: **True** · adopt aliasing: **True** (pre-registered rule; binding on heldout only).

