# CR-060 Part A: head-variant identity (replay on `cr055ballp`, 20 first-set papers, `IDXR1-P1`)

| arm | concepts | concept P / R / F1 | relation P / R / F1 | aliases | merges | edges dropped | rule |
|---|---|---|---|---|---|---|---|
| control | 1269 | 0.356 / 0.751 / 0.483 | 0.157 / 0.149 / 0.153 | 0 | 0 | 0 | — |
| A-name | 1269 | 0.365 / 0.771 / 0.496 | 0.169 / 0.161 / 0.165 | 41 | 0 | 0 | PASS (R +0.020, F1 +0.012) |
| A-all | 1258 | 0.371 / 0.768 / 0.500 | 0.174 / 0.161 / 0.167 | 188 | 11 | 3 | PASS (R +0.016, F1 +0.014) |

Beside it (rule 35):

| arm | view | concept F1 | relation F1 |
|---|---|---|---|
| control | IDXR1X-P1 | 0.509 | 0.173 |
| control | IDXR1N-P1 | 0.452 | 0.147 |
| A-name | IDXR1X-P1 | 0.509 | 0.173 |
| A-name | IDXR1N-P1 | 0.452 | 0.147 |
| A-all | IDXR1X-P1 | 0.501 | 0.167 |
| A-all | IDXR1N-P1 | 0.449 | 0.143 |
