# CR-064: partOf fold scoring variant (20 first-set papers; overlap `IDXR1OV-P1`)

A predicted subclassOf, enhancedBy, UsedFor on a pair whose gold label is partOf (same ordered pair) counts as correct; reported BESIDE the overlap and strict numbers, never instead of them; not comparable with published SciNLP numbers.

| arm | overlap P / R / F1 (as scored) | check vs measure | **folded** P / R / F1 | credits by predicted label |
|---|---|---|---|---|
| v5 | 0.216 / 0.205 / 0.210 | ok | 0.216 / 0.205 / **0.210** | – |
| arm R2 | 0.204 / 0.243 / 0.222 | ok | 0.204 / 0.243 / **0.222** | – |
| arm R3 | 0.227 / 0.237 / 0.232 | ok | 0.227 / 0.237 / **0.232** | – |
| arm R5 | 0.267 / 0.251 / 0.259 | ok | 0.267 / 0.251 / **0.259** | – |
| arm R6 | 0.226 / 0.241 / 0.233 | ok | 0.226 / 0.241 / **0.233** | – |
| arm R7 | 0.235 / 0.247 / 0.241 | ok | 0.235 / 0.247 / **0.241** | – |
| arm R8 | 0.267 / 0.261 / 0.264 | ok | 0.270 / 0.263 / **0.266** | {'enhancedBy': 1} |
| arm R9 | 0.254 / 0.239 / 0.246 | ok | 0.256 / 0.241 / **0.248** | {'enhancedBy': 1} |
