# CR-063 addendum 2: relaxed evaluations, 57 SciNLP train / dev papers (evaluation only, beside `IDXR1-P1`, rule 35)

## Set `all`

| profile @ grounding | spans credited | concept P / R / F2 (F1) | relation P / R / F1 |
|---|---|---|---|
| v5 @ IDXR1-P1 | 0 | 0.342 / 0.731 / **0.596** (0.466) | 0.141 / 0.133 / 0.137 |
| v5 @ IDXR1T2-P1 | 22 | 0.344 / 0.735 / **0.599** (0.469) | 0.141 / 0.133 / 0.137 |
| v5 @ IDXR1W1-P1 | 530 | 0.386 / 0.825 / **0.672** (0.526) | 0.176 / 0.166 / 0.171 |
| v5 @ IDXR1HW-P1 | 227 | 0.361 / 0.772 / **0.629** (0.492) | 0.155 / 0.146 / 0.150 |
| v5 @ IDXR1OV-P1 | 834 | 0.411 / 0.879 / **0.716** (0.560) | 0.194 / 0.183 / 0.188 |
| v11 @ IDXR1-P1 | 0 | 0.349 / 0.747 / **0.609** (0.476) | 0.152 / 0.142 / 0.147 |
| v11 @ IDXR1T2-P1 | 39 | 0.352 / 0.754 / **0.614** (0.480) | 0.152 / 0.142 / 0.147 |
| v11 @ IDXR1W1-P1 | 462 | 0.387 / 0.829 / **0.675** (0.528) | 0.177 / 0.166 / 0.171 |
| v11 @ IDXR1HW-P1 | 243 | 0.369 / 0.790 / **0.644** (0.503) | 0.167 / 0.156 / 0.161 |
| v11 @ IDXR1OV-P1 | 765 | 0.412 / 0.882 / **0.719** (0.562) | 0.195 / 0.183 / 0.189 |

## Set `first`

| profile @ grounding | spans credited | concept P / R / F2 (F1) | relation P / R / F1 |
|---|---|---|---|
| v5 @ IDXR1-P1 | 0 | 0.356 / 0.751 / **0.615** (0.483) | 0.157 / 0.149 / 0.153 |
| v5 @ IDXR1T2-P1 | 8 | 0.358 / 0.755 / **0.618** (0.486) | 0.157 / 0.149 / 0.153 |
| v5 @ IDXR1W1-P1 | 194 | 0.401 / 0.847 / **0.693** (0.544) | 0.199 / 0.189 / 0.194 |
| v5 @ IDXR1HW-P1 | 81 | 0.375 / 0.791 / **0.647** (0.509) | 0.176 / 0.167 / 0.171 |
| v5 @ IDXR1OV-P1 | 300 | 0.426 / 0.899 / **0.736** (0.578) | 0.216 / 0.205 / 0.210 |
| v11 @ IDXR1-P1 | 0 | 0.365 / 0.771 / **0.631** (0.496) | 0.169 / 0.161 / 0.165 |
| v11 @ IDXR1T2-P1 | 8 | 0.367 / 0.775 / **0.634** (0.498) | 0.169 / 0.161 / 0.165 |
| v11 @ IDXR1W1-P1 | 154 | 0.401 / 0.847 / **0.693** (0.544) | 0.199 / 0.189 / 0.194 |
| v11 @ IDXR1HW-P1 | 84 | 0.385 / 0.812 / **0.665** (0.522) | 0.189 / 0.179 / 0.184 |
| v11 @ IDXR1OV-P1 | 260 | 0.426 / 0.899 / **0.736** (0.578) | 0.216 / 0.205 / 0.210 |

## Set `rest`

| profile @ grounding | spans credited | concept P / R / F2 (F1) | relation P / R / F1 |
|---|---|---|---|
| v5 @ IDXR1-P1 | 0 | 0.335 / 0.720 / **0.586** (0.457) | 0.132 / 0.124 / 0.128 |
| v5 @ IDXR1T2-P1 | 14 | 0.337 / 0.724 / **0.589** (0.460) | 0.132 / 0.124 / 0.128 |
| v5 @ IDXR1W1-P1 | 336 | 0.378 / 0.813 / **0.661** (0.516) | 0.162 / 0.152 / 0.157 |
| v5 @ IDXR1HW-P1 | 146 | 0.354 / 0.760 / **0.618** (0.483) | 0.142 / 0.133 / 0.138 |
| v5 @ IDXR1OV-P1 | 534 | 0.403 / 0.867 / **0.705** (0.551) | 0.181 / 0.170 / 0.175 |
| v11 @ IDXR1-P1 | 0 | 0.340 / 0.734 / **0.596** (0.465) | 0.141 / 0.131 / 0.136 |
| v11 @ IDXR1T2-P1 | 31 | 0.344 / 0.743 / **0.603** (0.471) | 0.141 / 0.131 / 0.136 |
| v11 @ IDXR1W1-P1 | 308 | 0.380 / 0.819 / **0.665** (0.519) | 0.164 / 0.152 / 0.158 |
| v11 @ IDXR1HW-P1 | 159 | 0.361 / 0.778 / **0.632** (0.493) | 0.153 / 0.143 / 0.148 |
| v11 @ IDXR1OV-P1 | 505 | 0.405 / 0.873 / **0.709** (0.553) | 0.182 / 0.170 / 0.176 |

## What each relaxed variant credits (v11, all 57 papers)

**IDXR1T2-P1**: {'prediction inside gold (gold longer)': 39}

- 'RNMT' -> gold 'RNMT +' x17
- 'NYT95' -> gold "NYT95 '" x4
- 'weighted A' -> gold 'weighted A *' x4
- 'SST-2' -> gold 'SST-2 (' x1
- 'DFG-label ( Neighbor' -> gold 'DFG-label ( Neighbor )' x1
- 'DFG-label ( Paragraph' -> gold 'DFG-label ( Paragraph )' x1
- 'DFG-label ( Document' -> gold 'DFG-label ( Document )' x1
- 'Span-Attribute tagging ( SA-T' -> gold 'Span-Attribute tagging ( SA-T )' x1
- 'Pearson correlation' -> gold 'Pearson correlation ρ' x1
- 'Pearson ’ s' -> gold 'Pearson ’ s ρ' x1
- 'Pointwise Mutual Information ( PMI' -> gold 'Pointwise Mutual Information ( PMI )' x1
- 'pointwise mutual information ( PMI' -> gold 'pointwise mutual information ( PMI )' x1
- 'Spearman ’ s' -> gold 'Spearman ’ s ρ' x1
- 'Weighted A' -> gold 'Weighted A *' x1
- 'dovetailing WA' -> gold 'dovetailing WA *' x1

**IDXR1W1-P1**: {'prediction inside gold (gold longer)': 216, 'gold inside prediction (prediction longer)': 243, 'partial overlap': 3}

- 'RNMT' -> gold 'RNMT +' x17
- 'test accuracy' -> gold 'accuracy' x7
- 'parsing accuracy' -> gold 'accuracy' x7
- 'Boltzmann-machine distribution' -> gold 'Boltzmann-machine' x6
- 'component accuracy' -> gold 'accuracy' x6
- 'tagging accuracy' -> gold 'accuracy' x6
- 'MDL principle' -> gold 'MDL' x5
- 'Big model' -> gold 'Transformer Big model' x5
- 'translation consensus' -> gold 'graph-based translation consensus' x4
- 'NYT95' -> gold "NYT95 '" x4
- 'average TER score' -> gold 'TER' x4
- 'weighted A' -> gold 'weighted A *' x4
- 'confidence measures' -> gold 'confidence' x3
- 'entropy thresholds' -> gold 'entropy' x3
- 'confidence weights' -> gold 'confidence' x3

**IDXR1HW-P1**: {'prediction inside gold (gold longer)': 118, 'gold inside prediction (prediction longer)': 125}

- 'test accuracy' -> gold 'accuracy' x7
- 'parsing accuracy' -> gold 'accuracy' x7
- 'component accuracy' -> gold 'accuracy' x6
- 'tagging accuracy' -> gold 'accuracy' x6
- 'Big model' -> gold 'Transformer Big model' x5
- 'translation consensus' -> gold 'graph-based translation consensus' x4
- 'EM' -> gold 'IP + EM' x4
- 'bidirectional LSTM' -> gold 'LSTM' x3
- 'modified Levenshtein alignment' -> gold 'Levenshtein alignment' x3
- 'Big models' -> gold 'Transformer Big models' x3
- 'supertag accuracy' -> gold 'accuracy' x3
- 'next-word suggestion accuracy' -> gold 'accuracy' x2
- 'expected accuracy' -> gold 'accuracy' x2
- 'thresholded precision' -> gold 'precision' x2
- 'tree cut model' -> gold 'MDL-based ( Minimum Description Length ) tree cut model' x2

**IDXR1OV-P1**: {'prediction inside gold (gold longer)': 441, 'gold inside prediction (prediction longer)': 312, 'partial overlap': 12}

- 'RNMT' -> gold 'RNMT +' x17
- 'test accuracy' -> gold 'accuracy' x7
- 'parsing accuracy' -> gold 'accuracy' x7
- 'Boltzmann-machine distribution' -> gold 'Boltzmann-machine' x6
- 'component accuracy' -> gold 'accuracy' x6
- 'tagging accuracy' -> gold 'accuracy' x6
- 'IP' -> gold 'IP + EM' x6
- 'MDL principle' -> gold 'MDL' x5
- 'WORDNET 1.7.1 test set' -> gold 'WORDNET 1.7.1' x5
- 'Big model' -> gold 'Transformer Big model' x5
- 'translation consensus' -> gold 'graph-based translation consensus' x4
- 'NYT95' -> gold "NYT95 '" x4
- 'average TER score' -> gold 'TER' x4
- 'weighted A' -> gold 'weighted A *' x4
- 'confidence measures' -> gold 'confidence' x3
