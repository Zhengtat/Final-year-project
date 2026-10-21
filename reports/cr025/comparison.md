# CR-025: three models on the SciNLP dev split

Written for: the project owner. Descriptive comparison; no adoption decision.

Corpus: SciNLP release `SciNLP-repo-e78342be`, **dev split, 6 papers**, E0 (the real pipeline end to end), CR-021 recipe with production settings (R1-key matching, rejected-link adjudicator). The test split was not opened (rule 9). Each arm runs ONE model for both tiers (strong effort medium, bulk effort low, escalation off), one run per arm. **o4-mini deviates**: at the production settings it failed twice with truncated answers (status=incomplete: hidden reasoning used the whole output cap, 768 of 800 tokens, then 2,368 of 2,400 even at 3x), so its arm runs with effort LOW on both tiers and every output cap x3; its cost includes the calls of those two failed attempts (resumed steps reuse the cache). No sampling parameters; run-to-run variation is not separated and n=6 papers, so small gaps are not evidence. Scorers: frozen CR-012 strict mention-level scorer, CR-019 occurrence index (IDXR1-P1 = primary here because the runs use R1-key matching), CR-022 hierarchy / macro scorers. Prices (USD per 1M tokens, in / out): gpt-6-sol 2.0 / 10.0; o4-mini 1.1 / 4.4; gpt-6-luna 0.1 / 0.5 (o4-mini and luna from the repo config / third-party listings).

## Headline (IDXR1-P1 grounding, pooled over the papers)

| arm | cost (USD) | concept F1 | relation P / R / F1 | direct hierarchy F1 (H2) | surface-ancestor F1 (H2) | relation macro F1 | concepts | edges |
|---|---|---|---|---|---|---|---|---|
| gpt-6-luna (both tiers) | 0.18 | 0.420 | 0.144 / 0.095 / **0.114** | 0.000 | 0.000 | 0.257 (11 classes) | 442 | 117 |
| o4-mini (both tiers) | 1.98 | 0.369 | 0.147 / 0.056 / **0.081** | 0.000 | 0.000 | 0.156 (9 classes) | 251 | 66 |
| gpt-6-sol (both tiers) | 3.63 | 0.502 | 0.165 / 0.145 / **0.154** | 0.077 | 0.145 | 0.280 (11 classes) | 398 | 146 |
| reference: CR-021 dev rebuild (gpt-6-sol strong + gpt-6-luna bulk, mixed, earlier run) | 0.63 | 0.420 | 0.128 / 0.095 / **0.109** | 0.000 | 0.053 | 0.252 (11 classes) | 439 | 132 |
| reference: CR-019 dev runs (earlier production settings, mixed tiers) | 2.44 | 0.433 | 0.114 / 0.084 / **0.096** | 0.000 | 0.053 | 0.282 (11 classes) | 423 | 132 |

Reference rows are earlier runs with a different tier mix (and for CR-019 older settings); they show the run-to-run spread of the existing setup, not a fourth model.

## Other groundings (relation strict F1, concept F1)

| arm | FROZEN rel F1 | IDX-P1 rel F1 | IDXR1-P1 rel F1 | FROZEN concept F1 | IDXR1-P1 concept F1 |
|---|---|---|---|---|---|
| gpt-6-luna (both tiers) | 0.054 | 0.088 | 0.114 | 0.325 | 0.420 |
| o4-mini (both tiers) | 0.030 | 0.065 | 0.081 | 0.234 | 0.369 |
| gpt-6-sol (both tiers) | 0.089 | 0.148 | 0.154 | 0.409 | 0.502 |
| reference: CR-021 dev rebuild (gpt-6-sol strong + gpt-6-luna bulk, mixed, earlier run) | 0.053 | 0.083 | 0.109 | 0.321 | 0.420 |
| reference: CR-019 dev runs (earlier production settings, mixed tiers) | 0.069 | 0.096 | 0.096 | 0.319 | 0.433 |

## Cost and speed (this run's calls, cache hits excluded)

| arm | USD | calls | input tokens | output tokens | model-call minutes (sequential) | USD per relation-F1 point (x100) |
|---|---|---|---|---|---|---|
| gpt-6-luna (both tiers) | 0.182 | 975 | 699,484 | 224,061 | 91.8 | 0.016 |
| o4-mini (both tiers) | 1.978 | 642 | 632,868 | 291,334 | 48.8 | 0.244 |
| gpt-6-sol (both tiers) | 3.627 | 831 | 764,430 | 209,787 | 61.4 | 0.235 |
| reference: CR-021 dev rebuild (gpt-6-sol strong + gpt-6-luna bulk, mixed, earlier run) | 0.631 | 209 | 207,836 | 57,977 | 15.0 | 0.058 |
| reference: CR-019 dev runs (earlier production settings, mixed tiers) | 2.438 | 801 | 696,680 | 220,851 | 66.4 | 0.253 |

## Per paper: relation strict F1 (IDXR1-P1)

| paper | gpt-6-luna | o4-mini | gpt-6-sol | reference: CR-021 dev rebuild | reference: CR-019 dev runs |
|---|---|---|---|---|---|
| 2021.acl-long.295 | 0.025 | 0.053 | 0.115 | 0.025 | 0.050 |
| 2024.acl-long.144-1-9.grobid | 0.292 | 0.197 | 0.302 | 0.257 | 0.186 |
| P05-1008.grobid | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| P16-1007.grobid | 0.000 | 0.043 | 0.051 | 0.000 | 0.042 |
| P02-1004.grobid | 0.174 | 0.000 | 0.188 | 0.154 | 0.154 |
| P03-1014.grobid | 0.038 | 0.000 | 0.030 | 0.038 | 0.036 |

Missing runs: none.

## How to read this

- Cost is what the run's own calls would cost at the listed prices; a model that writes more reasoning tokens costs more than its list price suggests (compare the token columns).
- A cheaper model changes everything downstream (concepts, pairs, relations), so differences are end-to-end, not per call.
- The reference rows bound the noise: if the three arms differ by less than the two reference rows differ from each other, the data cannot rank them.
