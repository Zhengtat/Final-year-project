# CR-060 Part A: head-variant identity (replay on `cr057rest`, 37 papers, set `rest`, `IDXR1-P1`)

| arm | concepts | concept P / R / F1 | relation P / R / F1 | aliases | merges | edges dropped | rule |
|---|---|---|---|---|---|---|---|
| control | 2277 | 0.335 / 0.720 / 0.457 | 0.132 / 0.124 / 0.128 | 0 | 0 | 0 | — |
| A-name | 2270 | 0.340 / 0.734 / 0.465 | 0.141 / 0.131 / 0.136 | 105 | 7 | 4 | PASS (R +0.014, F1 +0.008) |
| A-all | 2266 | 0.335 / 0.706 / 0.454 | 0.139 / 0.126 / 0.132 | 359 | 11 | 4 | fail (R -0.014, F1 +0.004) |

Beside it (rule 35):

| arm | view | concept F1 | relation F1 |
|---|---|---|---|
| control | IDXR1X-P1 | 0.469 | 0.130 |
| control | IDXR1N-P1 | 0.424 | 0.114 |
| A-name | IDXR1X-P1 | 0.469 | 0.131 |
| A-name | IDXR1N-P1 | 0.423 | 0.113 |
| A-all | IDXR1X-P1 | 0.456 | 0.131 |
| A-all | IDXR1N-P1 | 0.423 | 0.115 |
