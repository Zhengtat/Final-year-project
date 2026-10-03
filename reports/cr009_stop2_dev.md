# CR-009 STOP 2 — IIR dev results (13 sections; exact micro F1 selects)

Pre-registration: DECISIONS 2026-10-03. Scored with the existing FACE scorer; a mention is scored like a new concept.

## Live arms and the selection steps

| arm | predicted | exact P / R / F1 (micro) | lenient micro F1 | exact macro F1 | recall 1/2/3/4-gram (lenient) | calls | note |
|---|---|---|---|---|---|---|---|
| B0 = v3 (CR-007, E3) | 585 | 0.470 / 0.567 / **0.514** | 0.656 | 0.513 | 0.74 / 0.72 / 0.70 / 0.62 | 1 / section | reported, not selected |
| G1 | 582 | 0.438 / 0.526 / **0.478** | 0.602 | 0.478 | 0.72 / 0.65 / 0.63 / 0.25 | 57 | form G1, iterations <= 3, M4 False, M5 False, $0.1158 |
| G2 | 715 | 0.401 / 0.592 / **0.478** | 0.597 | 0.479 | 0.70 / 0.76 / 0.75 / 0.75 | 74 | form G2, iterations <= 3, M4 False, M5 False, $0.167 |
| G1_i1 | 548 | 0.478 / 0.540 / **0.507** | 0.633 | 0.511 | 0.72 / 0.67 / 0.58 / 0.50 | 44 | form G1, iterations <= 1, M4 False, M5 False, $0.065 |
| G1_i1_M4 | 567 | 0.471 / 0.551 / **0.508** | 0.622 | 0.510 | 0.71 / 0.68 / 0.60 / 0.38 | 43 | form G1, iterations <= 1, M4 True, M5 False, $0.0727 |
| G1_i1_M5 | 619 | 0.449 / 0.573 / **0.504** | 0.627 | 0.510 | 0.72 / 0.71 / 0.72 / 0.50 | 46 | form G1, iterations <= 1, M4 False, M5 True, $0.0833 |
| FINAL | 552 | 0.475 / 0.540 / **0.505** | 0.631 | 0.509 | 0.72 / 0.67 / 0.58 / 0.50 | 44 | form G1, iterations <= 1, M4 False, M5 False, $0.0081 |

## Verifier statistics per arm

| arm | sections Correct | stop reasons | flags per rule | hints added / rejected | restored | iterations histogram |
|---|---|---|---|---|---|---|
| G1 | 1 / 13 | {'dropped_few': 5, 'max_iterations': 6, 'correct': 1, 'no_change': 1} | {'F3': 80, 'F2': 21} | 76 / 7 | 95 | {0: 3, 1: 2, 2: 1, 3: 7} |
| G2 | 1 / 13 | {'correct': 1, 'max_iterations': 8, 'dropped_few': 3, 'error': 1} | {'F2': 37, 'F3': 143} | 99 / 24 | 72 | {0: 1, 1: 3, 2: 1, 3: 8} |
| G1_i1 | 0 / 13 | {'dropped_few': 7, 'max_iterations': 6} | {'F3': 39, 'F2': 13} | 17 / 5 | 23 | {0: 4, 1: 9} |
| G1_i1_M4 | 0 / 13 | {'dropped_few': 2, 'max_iterations': 11} | {'F3': 49, 'F2': 42} | 30 / 14 | 31 | {0: 2, 1: 11} |
| G1_i1_M5 | 0 / 13 | {'dropped_few': 2, 'max_iterations': 11} | {'F3': 61, 'F2': 20} | 52 / 37 | 47 | {1: 13} |
| FINAL | 0 / 13 | {'dropped_few': 7, 'max_iterations': 6} | {'F3': 39, 'F2': 13} | 17 / 5 | 23 | {0: 4, 1: 9} |

## Loop depth (replay of stored iterations; flagged items dropped, unresolved M1 not counted)

| arm | predicted | exact P / R / F1 (micro) | lenient micro F1 | exact macro F1 | recall 1/2/3/4-gram (lenient) | calls | note |
|---|---|---|---|---|---|---|---|
| G1 depth 0 | 492 | 0.490 / 0.497 / **0.493** | 0.602 | 0.496 | 0.66 / 0.59 / 0.60 / 0.12 | 57 |  |
| G1 depth 1 | 554 | 0.457 / 0.522 / **0.487** | 0.606 | 0.487 | 0.71 / 0.62 / 0.65 / 0.38 | 57 | selected by the rule: depth 1 (G1) |
| G1 depth 2 | 571 | 0.448 / 0.528 / **0.485** | 0.610 | 0.483 | 0.70 / 0.65 / 0.67 / 0.25 | 57 |  |
| G1 depth 3 | 582 | 0.438 / 0.526 / **0.478** | 0.602 | 0.478 | 0.72 / 0.65 / 0.63 / 0.25 | 57 |  |
| G2 depth 0 | 687 | 0.410 / 0.581 / **0.481** | 0.597 | 0.481 | 0.68 / 0.75 / 0.75 / 0.50 | 74 |  |
| G2 depth 1 | 734 | 0.388 / 0.588 / **0.468** | 0.589 | 0.472 | 0.72 / 0.76 / 0.74 / 0.75 | 74 |  |
| G2 depth 2 | 708 | 0.403 / 0.588 / **0.478** | 0.604 | 0.478 | 0.70 / 0.77 / 0.75 / 0.75 | 74 |  |
| G2 depth 3 | 715 | 0.401 / 0.592 / **0.478** | 0.597 | 0.479 | 0.70 / 0.76 / 0.75 / 0.75 | 74 |  |

## Reported, not selected (final run FINAL = G1, depth 1, tau 0.1)

| arm | predicted | exact P / R / F1 (micro) | lenient micro F1 | exact macro F1 | recall 1/2/3/4-gram (lenient) | calls | note |
|---|---|---|---|---|---|---|---|
| B0 = v3 (E3) | 585 | 0.470 / 0.567 / **0.514** | 0.656 | 0.513 | 0.74 / 0.72 / 0.70 / 0.62 | 1 / section | the baseline |
| iteration 0, raw generator output | 530 | 0.492 / 0.538 / **0.514** | 0.621 | 0.514 | 0.67 / 0.65 / 0.61 / 0.50 | 1 / section |  |
| L0 (iteration 0 + rules offline) | 494 | 0.494 / 0.503 / **0.498** | 0.613 | 0.503 | 0.65 / 0.60 / 0.61 / 0.50 | 1 / section | PiVe's offline correction |
| **v4 FINAL (live)** | 552 | 0.475 / 0.540 / **0.505** | 0.631 | 0.509 | 0.72 / 0.67 / 0.58 / 0.50 | 44 | the reported dev number |

## Pruner tau (replay; rule: highest exact micro F1 with recall drop <= 0.01)

| tau | F1 | recall | precision | predicted | eligible |
|---|---|---|---|---|---|
| none | 0.507 | 0.540 | 0.478 | 548 | – |
| 0.1 | 0.510 | 0.540 | 0.483 | 543 | True |
| 0.2 | 0.508 | 0.532 | 0.487 | 530 | True |
| 0.3 | 0.507 | 0.522 | 0.493 | 513 | False |
| 0.4 | 0.514 | 0.513 | 0.514 | 484 | False |
| 0.5 | 0.508 | 0.493 | 0.524 | 456 | False |
| 0.6 | 0.497 | 0.468 | 0.529 | 429 | False |
| 0.7 | 0.470 | 0.421 | 0.533 | 383 | False |
| 0.8 | 0.461 | 0.396 | 0.552 | 348 | False |
| 0.9 | 0.435 | 0.353 | 0.566 | 302 | False |

**Chosen tau = 0.1.**

## Comparison arms on dev (reported, never selected; `selection_eligible: false`)

| arm | predicted | exact P / R / F1 (micro) | lenient micro F1 | exact macro F1 | recall 1/2/3/4-gram (lenient) | calls | note |
|---|---|---|---|---|---|---|---|
| C-SAC | 283 | 0.618 / 0.361 / **0.456** | 0.565 | 0.462 | 0.34 / 0.53 / 0.44 / 0.12 | 17 | pruner P1 at tau 0.5 (P2 not built) |
| C-PiVe | 430 | 0.498 / 0.441 / **0.468** | 0.597 | 0.472 | 0.45 / 0.60 / 0.74 / 0.50 | 24 |  |
| C-PiVe-off | 381 | 0.528 / 0.414 / **0.464** | 0.589 | 0.470 | 0.42 / 0.58 / 0.63 / 0.25 | 13 |  |
| C-ConExion | 330 | 0.627 / 0.427 / **0.508** | 0.574 | 0.502 | 0.32 / 0.58 / 0.56 / 0.25 | 13 | one random dev example, their filter, our bulk model |

Caveats: C-SAC and C-PiVe are SAC-KG-style and PiVe-style re-implementations on our benchmark, not reproductions; C-ConExion uses our model, not Llama-3-70B. FACE's published supervised micro F1 is 0.76 (a different protocol).

