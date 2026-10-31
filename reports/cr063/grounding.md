# CR-063: symbol-aware grounding (57 SciNLP train / dev papers; v5 runs + span identity in memory)

Reference: v11 (A-name) under `IDXR1-P1`. `IDXR1S-P1` is reported beside it (rule 35).

## Set `first`

| arm @ grounding | concept P / R / F2 (F1) | recall Δ | relation P / R / F1 | relation F1 Δ |
|---|---|---|---|---|
| A-name @ IDXR1-P1 | 0.365 / 0.771 / **0.631** (0.496) | +0.0000 | 0.169 / 0.161 / 0.165 | +0.0000 |
| A-name @ IDXR1S-P1 | 0.366 / 0.773 / **0.632** (0.497) | +0.0015 | 0.169 / 0.161 / 0.165 | +0.0000 |
| A-name-acr @ IDXR1-P1 | 0.370 / 0.766 / **0.631** (0.499) | -0.0054 | 0.171 / 0.159 / 0.164 | -0.0005 |
| A-name-acr @ IDXR1S-P1 | 0.381 / 0.788 / **0.649** (0.514) | +0.0172 | 0.177 / 0.165 / 0.171 | +0.0057 |

Spans extended over symbols: {'A-name': 5, 'A-name-acr': 96}.

## Set `rest`

| arm @ grounding | concept P / R / F2 (F1) | recall Δ | relation P / R / F1 | relation F1 Δ |
|---|---|---|---|---|
| A-name @ IDXR1-P1 | 0.340 / 0.734 / **0.596** (0.465) | +0.0000 | 0.141 / 0.131 / 0.136 | +0.0000 |
| A-name @ IDXR1S-P1 | 0.344 / 0.742 / **0.602** (0.470) | +0.0077 | 0.141 / 0.131 / 0.136 | +0.0000 |
| A-name-acr @ IDXR1-P1 | 0.334 / 0.704 / **0.576** (0.453) | -0.0297 | 0.142 / 0.129 / 0.135 | -0.0010 |
| A-name-acr @ IDXR1S-P1 | 0.345 / 0.728 / **0.596** (0.469) | -0.0058 | 0.143 / 0.130 / 0.136 | +0.0003 |

Spans extended over symbols: {'A-name': 41, 'A-name-acr': 218}.
