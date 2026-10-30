# CR-062 $0 sizing: domain-free verifier rules (57 SciNLP train / dev papers, profile v11, `IDXR1-P1`)

Gold only evaluates; no rule is trained (owner constraint). Part (b) is an approximate replay (corrective round not replayed).

## (b) Rescuing items the verifier dropped on F2 / F3

| arm | rescued gold | rescued non-gold | concept P / R / F2 (F1) | recall Δ | F2 Δ |
|---|---|---|---|---|---|
| control | 0 | 0 | 0.349 / 0.747 / **0.609** (0.476) | +0.0000 | +0.0000 |
| V2 | 5 | 24 | 0.349 / 0.749 / **0.609** (0.476) | +0.0012 | +0.0003 |
| V1-para + V2 | 10 | 34 | 0.348 / 0.750 / **0.610** (0.476) | +0.0026 | +0.0009 |
| V1-paper + V2 | 17 | 63 | 0.348 / 0.753 / **0.611** (0.476) | +0.0060 | +0.0024 |

## (c) Flag rules on the final concepts

Nodes: {'gold': 1387, 'non_gold': 2152}.

| rule | non-gold flagged | gold flagged | non-gold per gold | gold mentions at risk |
|---|---|---|---|---|
| V6 | 171 | 208 | 0.82 | 292 |
| V7 | 226 | 124 | 1.82 | 262 |
| V6 or V7 | 376 | 307 | 1.22 | 522 |

**Paid arm (pre-registered trigger: (b) recall >= +0.005 or (c) >= 3 non-gold per gold): True**
