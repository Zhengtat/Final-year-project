# CR-054: where missed SciNLP concepts are lost (run `cr053v5`, 20 papers, `IDXR1-P1`)

Generated from `cumap.cr054.recall` ($0, read-only; numbers in `concept_recall.json`). A missed concept = a gold mention that no predicted
mention matches exactly (concept recall 0.701: 1424 of 2032 found, 608 missed). Each miss is traced to the earliest stage that lost it.

| stage | misses | share | what it means |
|---|---|---|---|
| span | 296 | 49% | the concept was found; the predicted span differs (shorter 2:1 over longer; generic head noun, "( ACRONYM )", modifiers, coordination) |
| never proposed | 269 | 44% | the surface is in no generator output of any iteration and in no verifier hint |
| lost after the generator | 40 | 7% | proposed, then gone: 31 left out by a later corrective iteration, 8 dropped by the verifier (F2: quote not verbatim), 1 F3 |
| node exists, occurrence not placed | 3 | <1% | "CRF" / "CRFs" |
| verifier hint rejected by the generator | 0 | 0% | |
| pruned | 0 | 0% | the pruner is off (tau 0) |

**The verifier and the pruner remove almost nothing** (9 mentions): recall is lost by what the generator chooses to extract, by span conventions,
and by corrective iterations that drop items found earlier.

**Never proposed (269):** method 177, task 50, metric 28, dataset 14. Short phrases 122, single common words 95, acronyms / model names 35,
long descriptive phrases 13, names with numbers 4. Most frequent surfaces: n-gram / n-grams / ngram / trigram / bigram (42), confidence (13),
"nystro ¨ m" (9, a PDF-extraction artefact), fine-tuning (8), phrase-based system (8), graph-based consensus (6), Auto L / Auto T (8),
Kneser-Ney (4), transformer (3), coverage (3); also "language model(s)", "pre-trained language model", "LM", "LMs", "MASK", "SEMCOR".

**v4 against v5:** v5 recovered 123 mentions (metrics: accuracy 9, entropy 6, precision 4, fluency 4, recall 3; HPSG 8, standard fine-tuning 8)
and lost 116 (fine-tuning 8 now extracted as "standard fine-tuning"; phrase-based system 8, topological parser 4, Kneser-Ney 4 and others that
vary run to run). About 120 mentions change between two runs of the same paper: generator variance is as large as a prompt change.

**Sizing ($0; marking rates from the 14 train papers only):**

| fix | misses it can reach | concept recall if all recovered |
|---|---|---|
| keep items found in an earlier iteration + whitespace / diacritic-tolerant quote check | 40 | 0.701 -> 0.720 |
| generic terms the train gold marks at least half the time (n-gram family, coverage, precision, p-value, MLE, ...) | 63 | 0.701 -> 0.732 |
| acronym / model-name hints | 22 | 0.701 -> 0.712 |
| CR-052 span rules (head noun, "( ACRONYM )"), measured | | 0.701 -> 0.742 |
