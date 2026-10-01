# CR-007 STOP 1: $0 diagnostics

 Generated read-only from run `pdcanon2_30e2b4f9` / org `org_f3c0874b`; no API calls, no writes other than this file.

## (a) Did the CR-005 spot-check failures come from substring mentions?

Test: for each edge, is an endpoint's surface form (canonical name or alias, token-boundary, case-insensitive) found in the evidence sentence **inside a longer concept mention** (the 'bit' inside 'bit rate' case)? Endpoint names are the sheet's triple; the concept list is the 736 P&D concepts.

- Failures (incorrect + wrong-direction): **1 of 7** have an endpoint sitting inside a longer concept mention.
- Correct edges: 13 of 23 do (baseline rate).

| id | mark | triple | endpoint inside a longer concept mention |
|---|---|---|---|
| 4 | incorrect | switch -[equivalent_to]-> forwarding | - |
| 5 | incorrect | wire -[contrasts_with]-> air | - |
| 6 | wrong-direction | signal -[requires]-> clock | - |
| 10 | wrong-direction | ones’ complement arithmetic -[has_property]-> bit | - |
| 17 | incorrect | bit -[contrasts_with]-> baud rate | 'bit' inside ['bit rate'] |
| 19 | incorrect | bit -[contrasts_with]-> frame | - |
| 28 | incorrect | link -[has_property]-> SONET | - |
| 2 | correct | Ethernet -[requires]-> CRC | 'CRC' inside ['crc-32'] |
| 8 | correct | switch -[performs]-> Spanning tree | 'Spanning tree' inside ['spanning tree algorithm'] |
| 9 | correct | encoding -[increases]-> baud rate | 'encoding' inside ['manchester encoding'] |
| 11 | correct | softwarization -[causes]-> network | 'network' inside ['access network'] |
| 12 | correct | clock -[requires]-> transition | 'clock' inside ['clock recovery'] |
| 13 | correct | routing protocol -[has_purpose]-> routing | 'routing protocol' inside ['intradomain routing protocol']; 'routing' inside ['intradomain routing protocol', 'routing protocol'] |
| 16 | correct | latency -[decreases]-> edge | 'latency' inside ['low latency connectivity']; 'edge' inside ['edge service'] |
| 20 | correct | host -[part_of]-> IP address | 'host' inside ['host part'] |
| 23 | correct | sliding window protocol -[is_a]-> protocol | 'protocol' inside ['sliding window protocol'] |
| 24 | correct | network edge -[is_a]-> edge | 'edge' inside ['network edge'] |
| 25 | correct | Outstanding frame -[is_a]-> frame | 'frame' inside ['outstanding frame'] |
| 29 | correct | Internet -[uses]-> checksum | 'Internet' inside ['internet protocol'] |
| 30 | correct | exclusive OR (XOR) -[has_purpose]-> remainder | 'exclusive OR (XOR)' inside ['exclusive or (xor)'] |

Reading: the granularity failures (#17 bit vs baud rate, #19 bit vs frame, #28 link vs SONET) are the cases to check; a failure without a substring hit points at a different cause (a list read as a contrast, e.g. #5, or a wrong relation).

## (b) CR-005 baselines

### Linked share by role (ch3 snapshot, 736 concepts; linked = at least one typed edge)

| basis | role | linked / concepts | share |
|---|---|---|---|
| strongest role | defined | 76 / 509 | 14.9% |
| strongest role | used | 21 / 159 | 13.2% |
| strongest role | mentioned | 7 / 68 | 10.3% |
| has any defined mention | defined | 76 / 509 | 14.9% |
| has any used mention | used | 50 / 210 | 23.8% |
| has any mentioned mention | mentioned | 24 / 98 | 24.5% |
| all | all | 104 / 736 | 14.1% |

### Relation outcomes of the 381 resolved pairs

| outcome | pairs | share |
|---|---|---|
| family_no_relation | 143 | 37.5% |
| edge | 121 | 31.8% |
| relation_other | 114 | 29.9% |
| family_other | 3 | 0.8% |

OTHER (relation_other + family_other) = 117 = **30.7%** of pairs (the CR's '~32%' uses 114/361 = 31.6%; on the 381 pairs actually resolved it is 30.7%); NO_RELATION = 143 = **37.5%**; accepted edges = 121 = 31.8%. Accepted mechanism_process edges: 2.

### Pair cap (30 per section, sentence-level, run-deduped)

- Sections at the cap (overflow > 0): **17 of 17**; pairs kept 510; **pairs dropped by the cap: 7550** (before run-level dedup); new unique pairs after dedup 381.

| section | ch | kept | dropped |
|---|---|---|---|
| 2-problem-connecting-to-a-network | 2 | 30 | 158 |
| 2.1 | 2 | 30 | 330 |
| 2.2 | 2 | 30 | 142 |
| 2.3 | 2 | 30 | 315 |
| 2.4 | 2 | 30 | 145 |
| 2.5 | 2 | 30 | 416 |
| 2.6 | 2 | 30 | 430 |
| 2.7 | 2 | 30 | 586 |
| 2.8 | 2 | 30 | 575 |
| 2-perspective-race-to-the-edge | 2 | 30 | 241 |
| 3-problem-not-all-networks-are-directly-connected | 3 | 30 | 99 |
| 3.1 | 3 | 30 | 635 |
| 3.2 | 3 | 30 | 442 |
| 3.3 | 3 | 30 | 1345 |
| 3.4 | 3 | 30 | 766 |
| 3.5 | 3 | 30 | 740 |
| 3-perspective-virtual-networks-all-the-way-down | 3 | 30 | 185 |

With a cap of 40 the drop would be smaller by at most 170 pairs (upper bound; the pipeline ranks by cue score).

## (c) Owner merge errors vs embedding similarity (43 marks)

Similarity = cosine of all-MiniLM-L6-v2 embeddings of 'name: definition' for the merged mention and the concept it was merged into (the text the canonicaliser embeds). Threshold used by the pipeline: 0.6.

- 43 marked merges; 2 wrong. Similarity range 0.41 to 0.98; median 0.69.
- The wrong merges: 'routing table' -> 'forwarding table' at 0.59; 'destination address' -> 'DestinationAddr' at 0.65.

| similarity band | merges | wrong |
|---|---|---|
| 0.0 to 0.6 | 10 | 1 |
| 0.6 to 0.7 | 13 | 1 |
| 0.7 to 0.8 | 10 | 0 |
| 0.8 to 0.9 | 7 | 0 |
| 0.9 to 1.0 | 3 | 0 |

Strip plot (each mark one merge, sorted by similarity; `.` ok, `X` wrong):

```
.........X..X..............................   (0.41 ... 0.98)
```

**Reading:** with only 2 wrong merges out of 43 there is very little to fit a band to. If both sit at the low end, a conservative band (send merges below the median similarity to review) would catch them; if not, similarity does not separate errors and type-awareness has to carry §4.3. Stated as evidence, not as a tuned rule.


## (d) Why 86% of concepts are unlinked: the pair cap, not the classifier (new finding)

Measured offline with the CR-005 enumeration (sentence-level candidate pairs, window 0, cue-score ranked, cap 30 per section):

| | count |
|---|---|
| unique candidate pairs in ch2-3 before any cap | **5,824** |
| pairs the CR-005 run classified (kept unique) | 381 (6.5%) |
| concepts that appear in at least one candidate pair | 660 of 736 |
| concepts appearing in at least one *classified* pair | **152 of 736** |
| concepts with an accepted typed edge | 104 |

So 508 concepts had a candidate pair that was never classified because every section hit the cap (all 17 sections; 7,550 sentence-level pairs dropped before dedup). Raising the cap from 30 to 40 adds at most about 170 pairs and would barely move coverage. A **coverage-aware selection** (first give every concept its best-cue candidate pair, then fill by cue score, same per-section budget) is cost-neutral per pair and could touch up to 660 concepts with about 330 to 700 pairs. Proposed change to CR-007 §5.3 (needs the owner's OK).

## (e) Dry-run cost estimates (from the real call log; nothing was called)

Measured per real call in the CR-005 run (strong tier, $2 / $10 per 1M): relation_family $0.00206 (378 in / 131 out tokens), relation_choice $0.00309 (516 / 205), relation_qualifiers $0.00308 (485 / 211), canonicalize $0.00311 (922 / 127). Concept extraction runs on the bulk tier: about $0.0013 per call (roughly $0.002 per P&D section).

**Measured cost per fully classified pair (family + choice for all, qualifiers for accepted): $0.0049** (CR-005: 381 pairs, $1.88). The CR's $8-13 relation estimate implies about $0.0137 per pair, the earlier pre-measurement estimate that CR-005 already disproved.

**§3 (IIR concept extraction v3), dry run**

| item | assumption | estimate |
|---|---|---|
| dev ablation: E1, E4, E5 singly (13 sections each) + E2 (3 runs) + best combination | about 8 dev passes at $0.002 to $0.004 per section (bigger prompts) | about $0.25 |
| test split: v2 once + v3 once (about 73 sections; v3 possibly 3 runs if E2 wins) | $0.002 and $0.004 to $0.012 per section | about $0.15 to $0.9 |
| **§3 total** | | **about $0.4 to $1.2** (CR estimate < $1) |

**§6 (P&D ch1-3 slice re-run), dry run** (24 sections; ch1 has no extraction yet)

| item | assumption | estimate |
|---|---|---|
| concepts v3, bulk tier, 24 sections, up to 3 runs | $0.004 per section per run | $0.1 to $0.3 |
| canonicalisation v2, strong tier | CR-005 spent $1.38 on 943 mentions; ch1 adds about 35% more, 3-run union may add more | $1.9 to $3.5 |
| relations, cap 30 (about 720 pairs, about 540 unique) | $0.0049 x 1.4 to 1.7 for the longer filled-option prompts = $0.007 to $0.008 per pair | $3.8 to $4.5 |
| relations, cap 40 or coverage-aware at about 720 unique pairs | same | $5.0 to $5.8 |
| STOP 3 pilot (114 OTHER pairs re-classified) | 3 calls each at the v1.1 price | about $0.8 to $1.0 (pre-approved <= $2) |
| **§6 total** | | **about $6 to $10** |

Everything is under the $20 hard cap; the largest item is canonicalisation, not relations. The batch API is not implemented (CR-001 deferred it); at these sizes it is not needed.
