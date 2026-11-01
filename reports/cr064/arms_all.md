# CR-064: relation arms on 20 first-set papers (registry v1.0.2 / v1.0.4, no node types)

Adoption rule (pre-registered): overlap relation F1 >= v5 -0.005. Delta +0.0113: **passes**. trainedWith wording is gold-informed (owner option B).

Arm R3 rule (pre-registered): overlap relation F1 >= R2 + 0.005 and >= v5 -0.005. Delta vs R2 +0.0104, vs v5 +0.0217: **passes**.

Context arm arm R6 (pre-registered): delta vs R3 +0.0010, vs v5 +0.0227: **fails**.

Context arm arm R7 (pre-registered): delta vs R3 +0.0089, vs v5 +0.0306: **passes**.

| arm | overlap concept P / R / F2 | overlap relation P / R / F1 | strict relation P / R / F1 | spend |
|---|---|---|---|---|
| v5 | 0.426 / 0.899 / 0.736 | 0.216 / 0.205 / **0.210** | 0.157 / 0.149 / 0.153 |  |
| arm R (CR-059) | 0.426 / 0.899 / 0.736 | 0.176 / 0.221 / **0.196** | 0.125 / 0.157 / 0.139 | $0.4633 |
| arm R2 | 0.426 / 0.899 / 0.736 | 0.204 / 0.243 / **0.222** | 0.145 / 0.173 / 0.158 | $0.5756 |
| arm R3 | 0.426 / 0.899 / 0.736 | 0.227 / 0.237 / **0.232** | 0.164 / 0.171 / 0.167 | $0.5935 |
| arm R5 (R3, no partOf) | 0.426 / 0.899 / 0.736 | 0.267 / 0.251 / **0.259** | 0.190 / 0.179 / 0.184 | $0.7105 |
| arm R6 (origin) | 0.426 / 0.899 / 0.736 | 0.226 / 0.241 / **0.233** | 0.158 / 0.169 / 0.163 | $0.6047 |
| arm R7 (neighbours) | 0.426 / 0.899 / 0.736 | 0.235 / 0.247 / **0.241** | 0.168 / 0.177 / 0.172 | $0.6024 |
| arm R8 (R6, no partOf) | 0.426 / 0.899 / 0.736 | 0.267 / 0.261 / **0.264** | 0.200 / 0.195 / 0.197 | $0.727 |
| arm R9 (R7, no partOf) | 0.426 / 0.899 / 0.736 | 0.254 / 0.239 / **0.246** | 0.186 / 0.175 / 0.180 | $0.5308 |

## v5

- choice-step losses (overlap): wrong relation: gold trainedWith -> evaluatedOn x12; wrong relation: gold enhancedBy -> UsedFor x7; wrong relation: gold MeasuredBy -> other x6; wrong relation: gold similarWith -> partOf x6; wrong relation: gold MeasuredBy -> evaluatedBy x5; wrong relation: gold evaluatedOn -> UsedFor x4; wrong relation: gold trainedWith -> UsedFor x4; wrong relation: gold compareWith -> no_relation x4; wrong relation: gold partOf -> compareWith x3; wrong relation: gold MeasuredBy -> enhancedBy x3
- endpoint drops: {'domain_range / gold-linked': 49, 'domain_range / not gold-linked': 281}
- outcomes (selected pairs): {'no_relation': 674, 'rejected': 381, 'edge': 459, 'other': 326}

## arm R (CR-059)

- choice-step losses (overlap): wrong relation: gold trainedWith -> evaluatedOn x14; wrong relation: gold trainedWith -> UsedFor x7; wrong relation: gold MeasuredBy -> other x6; wrong relation: gold similarWith -> other x6; wrong relation: gold MeasuredBy -> evaluatedBy x5; wrong relation: gold enhancedBy -> UsedFor x4; wrong relation: gold subtaskOf -> subclassOf x4; wrong relation: gold partOf -> other x4; wrong relation: gold partOf -> compareWith x3; wrong relation: gold MeasuredBy -> enhancedBy x3
- endpoint drops: {'endpoint_fit / gold-linked': 17, 'endpoint_fit / not gold-linked': 78}
- outcomes (selected pairs): {'no_relation': 694, 'edge': 599, 'other': 417, 'rejected': 130}

## arm R2

- choice-step losses (overlap): wrong relation: gold enhancedBy -> other x9; wrong relation: gold MeasuredBy -> other x8; wrong relation: gold similarWith -> partOf x6; wrong relation: gold partOf -> other x5; wrong relation: gold MeasuredBy -> evaluatedBy x4; wrong relation: gold trainedWith -> UsedFor x4; wrong relation: gold UsedFor -> other x3; wrong relation: gold partOf -> compareWith x3; wrong relation: gold MeasuredBy -> compareWith x3; wrong relation: gold subtaskOf -> other x3
- endpoint drops: {'endpoint_fit / gold-linked': 2, 'endpoint_fit / not gold-linked': 4}
- outcomes (selected pairs): {'no_relation': 724, 'other': 503, 'edge': 570, 'rejected': 43}

## arm R3

- choice-step losses (overlap): wrong relation: gold subtaskOf -> no_relation x7; wrong relation: gold enhancedBy -> no_relation x6; wrong relation: gold MeasuredBy -> no_relation x5; wrong relation: gold UsedFor -> other x4; wrong relation: gold MeasuredBy -> other x4; wrong relation: gold UsedFor -> no_relation x4; wrong relation: gold MeasuredBy -> evaluatedBy x4; wrong relation: gold trainedWith -> no_relation x4; wrong relation: gold evaluatedBy -> no_relation x3; wrong relation: gold subclassOf -> no_relation x3
- endpoint drops: {'endpoint_fit / not gold-linked': 1}
- outcomes (selected pairs): {'no_relation': 890, 'other': 422, 'edge': 492, 'rejected': 36}

## arm R5 (R3, no partOf)

- choice-step losses (overlap): wrong relation: gold MeasuredBy -> other x9; wrong relation: gold subtaskOf -> no_relation x7; wrong relation: gold MeasuredBy -> no_relation x7; wrong relation: gold enhancedBy -> no_relation x7; wrong relation: gold UsedFor -> other x6; wrong relation: gold UsedFor -> no_relation x5; wrong relation: gold trainedWith -> UsedFor x5; wrong relation: gold MeasuredBy -> evaluatedBy x4; wrong relation: gold partOf -> no_relation x4; wrong relation: gold subclassOf -> no_relation x3
- endpoint drops: {}
- outcomes (selected pairs): {'no_relation': 885, 'other': 482, 'edge': 449, 'rejected': 24}

## arm R6 (origin)

- choice-step losses (overlap): wrong relation: gold MeasuredBy -> other x8; wrong relation: gold subtaskOf -> other x7; wrong relation: gold enhancedBy -> no_relation x7; wrong relation: gold subtaskOf -> no_relation x5; wrong relation: gold partOf -> other x5; wrong relation: gold UsedFor -> other x4; wrong relation: gold MeasuredBy -> no_relation x4; wrong relation: gold MeasuredBy -> evaluatedBy x4; wrong relation: gold trainedWith -> UsedFor x3; wrong relation: gold partOf -> compareWith x3
- endpoint drops: {}
- outcomes (selected pairs): {'no_relation': 845, 'other': 465, 'edge': 503, 'rejected': 27}

## arm R7 (neighbours)

- choice-step losses (overlap): wrong relation: gold enhancedBy -> no_relation x7; wrong relation: gold partOf -> other x6; wrong relation: gold MeasuredBy -> other x6; wrong relation: gold subtaskOf -> no_relation x5; wrong relation: gold trainedWith -> other x5; wrong relation: gold UsedFor -> no_relation x4; wrong relation: gold MeasuredBy -> evaluatedBy x4; wrong relation: gold partOf -> compareWith x3; wrong relation: gold similarWith -> other x3; wrong relation: gold similarWith -> partOf x3
- endpoint drops: {'endpoint_fit / not gold-linked': 1}
- outcomes (selected pairs): {'no_relation': 879, 'other': 431, 'edge': 501, 'rejected': 29}

## arm R8 (R6, no partOf)

- choice-step losses (overlap): wrong relation: gold UsedFor -> other x8; wrong relation: gold MeasuredBy -> other x7; wrong relation: gold enhancedBy -> no_relation x6; wrong relation: gold compareWith -> no_relation x6; wrong relation: gold subtaskOf -> other x5; wrong relation: gold MeasuredBy -> no_relation x5; wrong relation: gold subtaskOf -> no_relation x4; wrong relation: gold MeasuredBy -> evaluatedBy x4; wrong relation: gold compareWith -> enhancedBy x3; wrong relation: gold partOf -> compareWith x3
- endpoint drops: {'endpoint_fit / not gold-linked': 2}
- outcomes (selected pairs): {'no_relation': 829, 'other': 519, 'edge': 476, 'rejected': 16}

## arm R9 (R7, no partOf)

- choice-step losses (overlap): wrong relation: gold MeasuredBy -> other x10; wrong relation: gold UsedFor -> other x8; wrong relation: gold MeasuredBy -> no_relation x7; wrong relation: gold subtaskOf -> no_relation x6; wrong relation: gold UsedFor -> no_relation x6; wrong relation: gold trainedWith -> UsedFor x6; wrong relation: gold enhancedBy -> other x5; wrong relation: gold compareWith -> no_relation x4; wrong relation: gold partOf -> enhancedBy x4; wrong relation: gold MeasuredBy -> evaluatedBy x4
- endpoint drops: {'endpoint_fit / not gold-linked': 3}
- outcomes (selected pairs): {'no_relation': 878, 'other': 483, 'edge': 454, 'rejected': 25}
