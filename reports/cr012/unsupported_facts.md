# CR-012 unsupported facts

Definitions (fixed before reading results): an **unsupported node** has no mention span that can be located inside its recorded evidence quotes (rule 24: mentions come only from the generator, with evidence); an **unsupported edge** has an evidence quote that cannot be located in the unit text. Evidence quotes are verified exact substrings at generation time (rule 3), so unsupported edges are expected to be rare.

Distinct from this: a predicted edge that no gold edge matches is **not confirmed by the gold**, which is not the same as unsupported by the text (the gold is a single-annotator reference and may be incomplete, and SciNLP is selectively annotated). Those counts are the false-positive columns in `pd_e2e.md` / `external_e2e.md`.

## P&D

| run | nodes | nodes without a grounded mention span (rate) | edges | edges without a located evidence quote (rate) | edges dropped: endpoint node absent | provenance completeness |
|---|---|---|---|---|---|---|
| E0 | 790 | 23 (0.029) | 174 | 0 (0.000) | 0 | 0.976 |
| E1 | 705 | 2 (0.003) | 156 | 0 (0.000) | 0 | 0.998 |
| E2 | 539 | 1 (0.002) | 177 | 0 (0.000) | 0 | 0.999 |
| E3 | 539 | 1 (0.002) | 328 | 4 (0.012) | 0 | 0.994 |
| E4 | 539 | 1 (0.002) | 212 | 4 (0.019) | 0 | 0.993 |

## SciNLP

| run | nodes | nodes without a grounded mention span (rate) | edges | edges without a located evidence quote (rate) | edges dropped: endpoint node absent | provenance completeness |
|---|---|---|---|---|---|---|
| E0 | 225 | 0 (0.000) | 111 | 0 (0.000) | 1 | 1.000 |
| E1 | 197 | 0 (0.000) | 100 | 0 (0.000) | 0 | 1.000 |
| E3-M | 237 | 0 (0.000) | 164 | 0 (0.000) | 2 | 1.000 |
| E4-M | 237 | 0 (0.000) | 135 | 0 (0.000) | 2 | 1.000 |

SciNLP E0: 0 negated relations were dropped (never emitted as positive edges); 1 edges were dropped because an endpoint or the evidence span could not be grounded at token level.
