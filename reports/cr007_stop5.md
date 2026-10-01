# CR-007 STOP 5: gate table and precision (run `slice3_a1`, org `org_baa0d058`)

Marks read from `data/gold` (owner copies). $0, read-only.

## 1. Gate table (CR-007 §5.1; rule applied as written: >=5 instances AND >=80% of the sampled correct)

| relation | instances in re-run | sampled (owner-marked) | correct | % correct | decision |
|---|---|---|---|---|---|
| identifies | 13 | 8 | 5 | 62% | drop (correct 5/8 < 80%) |
| encapsulates | 2 | 2 | 2 | 100% | drop (instances 2 < 5) |
| trades_off_with | 1 | 1 | 1 | 100% | drop (instances 1 < 5) |
| acts_on | 35 | 5 | 5 | 100% | report only |
| connected_to | 10 | 5 | 4 | 80% | report only |

## 2. Precision (Wilson 95%)

- Edges overall: 29/39 = **74% (59-85%)** (CR-005 spot-check: 23/30 = 77% (59-88%)).

| family | correct / sampled | Wilson |
|---|---|---|
| cause_effect | 1/3 | 33% (6-79%) |
| classification_structure | 14/18 | 78% (55-91%) |
| comparison | 4/4 | 100% (51-100%) |
| dependency | 1/3 | 33% (6-79%) |
| function_means | 3/3 | 100% (44-100%) |
| mechanism_process | 6/8 | 75% (41-93%) |

- Pipeline merges: 23/24 = **96% (80-99%)** (CR-005: 41/43).

## 3. Merge errors by similarity bucket (review band stays at 0.70, provisional)

| bucket | source | owner mark | rows |
|---|---|---|---|
| <0.70 | band | different | 1 |
| <0.70 | band | same | 15 |
| >=0.70 | merged | different | 1 |
| >=0.70 | merged | same | 23 |

`merged` rows were merged by the pipeline (similarity >= 0.70 by construction, so wrong merges can only fall in the upper bucket); `band` rows were held back for review, so a `same` mark there is a missed merge, not a wrong one.

## 4. corrects_intuition diagnosis (no fix applied; counts kept out of the demo report)

4 flagged of 750 classified results.

- [edge/selected] network -[has_property]-> maximum transmission unit | polarity affirmed | intuition: The maximum transmission unit is the largest packet size on the network.
  - sentence: The central idea here is that every network type has a maximum transmission unit (MTU), which is the largest IP datagram that it can carry in a frame.\ [#]_ Note that this value is smaller than the largest packet size on that network because the IP datagram needs to fit in the payload of the link-layer frame.
- [edge/sample] edge -[connected_to]-> customers | polarity affirmed | intuition: The names imply that these sites are centralized or at the root of the hierarchy, rather than at the network’s edge.
  - sentence: These edge sites are commonly called Central Offices in the Telco world and Head Ends in the cable world, but despite their names implying “centralized” and “root of the hierarchy” these sites are at the very edge of the ISP’s network; the ISP-side of the last-mile that directly connects to customers.
- [edge/selected] application -[causes]-> network | polarity affirmed | intuition: Understanding how networks work today is sufficient without understanding the underlying concepts.
  - sentence: While it is tempting to settle for just understanding the way it’s done today, it is important to recognize the underlying concepts because networks are constantly changing as technology evolves and new applications are invented.
- [edge/selected] implementation -[performs]-> Piggybacking | polarity negated | intuition: This particular implementation supports piggybacking ACKs on data frames.
  - sentence: Note that this particular implementation does not support piggybacking ACKs on data frames.

Reading (Claude, run slice3_a1; a human judgement, not a metric). Cause: the prompt/schema, not post-processing. `build_pair_registry` and the snapshot writer never read the flag, so nothing in our code sets it; the model sets it. Two things in `relation_qualifiers/v3.md` drive wrong flags: the cue list includes "note that ... does not", which fires on ordinary caveats; and the flag is asked about the *sentence* while the edge is about the *pair*, so a sentence that warns against a belief flags an unrelated edge. Of the flagged results, by my reading 3 are genuine warnings against a belief (the MTU note, the Central Offices/Head Ends "despite their names" sentence, "it is tempting to settle") and 1 is not (the piggybacking caveat, which restates a limitation). Of the 3 genuine ones, 1 sits on an edge the owner marked incorrect (application -[causes]-> network), and 1 is an unselected-sample result that is not in the graph. Counts are left out of the demo report until the owner decides.

## 5. Spend by stage, this run (actual from the call log; cache hits cost nothing)

| stage | actual | preflight |
|---|---|---|
| canonicalize | $1.47 | $1.54 |
| concepts | $0.01 | - |
| relations | $5.13 | $5.17 |
| **run total** | **$6.61** | |
