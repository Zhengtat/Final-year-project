# CR-012 external benchmark (SciNLP-repo-e78342be) held-out results

3 test documents; mention-level strict scoring (exact span + type for typed; relation direction and symmetry per registry). **CI_status = NOT_EVALUABLE_SMALL_N**: micro, per-document, macro mean and min/max are reported; no entity- or edge-level bootstrap. Identity metrics, E2 and canonical-node F1: **NOT_SUPPORTED** (no identity gold). Not pooled with P&D.

| level | relation strict micro P / R / F1 | per-document F1 | macro F1 | min / max doc F1 | entity strict micro F1 | entity typed micro F1 |
|---|---|---|---|---|---|---|
| E0 | 0.364 / 0.027 / 0.050 | 2021=0.046; 2024=0.057; P17-1058=0.000 | 0.034 | 0.000 / 0.057 | 0.352 | 0.342 |
| E1 | 0.635 / 0.159 / 0.255 | 2021=0.232; 2024=0.284; P17-1058=0.000 | 0.172 | 0.000 / 0.284 | 0.979 | 0.975 |
| E3-M | 0.730 / 0.339 / 0.463 | 2021=0.494; 2024=0.429; P17-1058=0.000 | 0.308 | 0.000 / 0.494 | 0.983 | 0.979 |
| E4-M | 0.781 / 0.339 / 0.473 | 2021=0.498; 2024=0.446; P17-1058=0.000 | 0.315 | 0.000 / 0.498 | 0.983 | 0.979 |

Gold relations per document: {'2021.acl-long.353': 164, '2024.acl-long.108-1-9.grobid': 130, 'P17-1058.grobid': 1}. **P17-1058 has a single gold relation**, so its per-document F1 is almost uninformative.

E0 -> E1: 0.050 -> 0.255; E1 -> E3-M: 0.255 -> 0.463 (**post-mention / endpoint-delivery loss**, not pure pair-selection loss, because there is no E2 identity oracle); E3-M -> E4-M: 0.463 -> 0.473.
E3-M / E4-M operate on surface-level pseudo-nodes (one node per distinct normalised surface string; canonicalisation replaced). E1 keeps the normal canonicalisation.

The SciNLP gold is selectively annotated (few entities per document), whereas the pipeline extracts every concept; over-extraction relative to the benchmark's selectivity is a legitimate architecture-transfer outcome and was not tuned on.
