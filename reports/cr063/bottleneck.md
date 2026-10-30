# CR-063: bottlenecks under the overlap headline (v11, 57 SciNLP train / dev papers, $0)

Check: funnel credited (overlap) = 247, overlap relation tp = 247.

## Gold relations reaching each stage

| stage | strict | pass | overlap | pass |
|---|---|---|---|---|
| gold | 1354 | – | 1354 | – |
| endpoints_placed | 707 | 52% | 972 | 72% |
| pair_selected | 620 | 88% | 855 | 88% |
| family_right | 503 | 81% | 691 | 81% |
| choice_right | 283 | 56% | 384 | 56% |
| checks_passed | 260 | 92% | 349 | 91% |
| assembled | 259 | 100% | 348 | 100% |
| credited | 192 | 74% | 247 | 71% |

## Gold concept mentions missed (5664 gold mentions)

| reason | strict | overlap |
|---|---|---|
| never_proposed | 480 | 480 |
| lost_after_generator | 81 | 81 |
| hint_rejected | 48 | 48 |
| node_not_placed | 29 | 29 |
| span | 793 | 28 |

## Gold relations lost at the choice step (overlap)

- declined (no relation chosen): 0
- right relation, wrong direction: 9
- wrong relation: 298; most frequent: gold trainedWith -> evaluatedOn x38; gold enhancedBy -> UsedFor x27; gold compareWith -> other x18; gold trainedWith -> UsedFor x11; gold partOf -> other x10; gold evaluatedOn -> UsedFor x9; gold trainedWith -> enhancedBy x9; gold enhancedBy -> other x9; gold compareWith -> no_relation x8; gold MeasuredBy -> evaluatedBy x7; gold subtaskOf -> UsedFor x7; gold MeasuredBy -> enhancedBy x7; gold MeasuredBy -> other x7; gold similarWith -> partOf x6; gold partOf -> subclassOf x6; gold subtaskOf -> subclassOf x5; gold trainedWith -> MeasuredBy x5; gold MeasuredBy -> UsedFor x5; gold evaluatedBy -> UsedFor x5; gold UsedFor -> evaluatedOn x4; gold partOf -> compareWith x4; gold UsedFor -> enhancedBy x4; gold MeasuredBy -> no_relation x4; gold subclassOf -> other x3; gold partOf -> UsedFor x3; gold UsedFor -> other x3; gold subclassOf -> compareWith x3; gold evaluatedBy -> MeasuredBy x3; gold com

Pairs never classified (overlap): {'same_sentence': 117}

Examples (overlap, never proposed): Nystro ¨ m, confidence, seq2seq models, code-switched, copying mechanism, NLL, phrase-based, graph-based consensus, seq2seq model, identifying question topic and question focus, world model, topological parse, natural language understanding, Nystro ¨ m methodology, discriminative ranker, convolutional filter, TDT4, Large Language Models, data generation, response generation, template reranking, template-aware summary generation, accurate, single-sentence, sentence-pair tasks, deep syntactic analysis, topological tree, XSLT transformations, attention mechanisms, multiple convolutional filters
