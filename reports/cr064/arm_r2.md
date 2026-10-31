# CR-064: arm R2 (registry v1.0.2 + relation_choice v9, no node types) on 20 first-set papers

Adoption rule (pre-registered): overlap relation F1 >= v5 -0.005. Delta +0.0113: **passes**. trainedWith wording is gold-informed (owner option B).

| arm | overlap concept P / R / F2 | overlap relation P / R / F1 | strict relation P / R / F1 | spend |
|---|---|---|---|---|
| v5 | 0.426 / 0.899 / 0.736 | 0.216 / 0.205 / **0.210** | 0.157 / 0.149 / 0.153 |  |
| arm R (CR-059) | 0.426 / 0.899 / 0.736 | 0.176 / 0.221 / **0.196** | 0.125 / 0.157 / 0.139 | $0.4633 |
| arm R2 | 0.426 / 0.899 / 0.736 | 0.204 / 0.243 / **0.222** | 0.145 / 0.173 / 0.158 | $0.5756 |

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
