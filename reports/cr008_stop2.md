# CR-008 STOP 2 — before/after (slice3_a1 → slice3_b3)

Re-keying and the lexicon cost $0. The misconception stage cost **$0.55** in total across all attempts (preflight $0.77, hard cap $3). No marks from you yet, so every precision figure below is pending.

## §6 metrics

| Metric | Before (CR-007) | After (CR-008) |
|---|---|---|
| Nodes | 982 | 916 |
| Merges per rule (re-key) | – | R0 38, R1 1, R2 25, R3-strong 2 (R4 unchanged: the LLM merges already in the run are kept) |
| R3-weak items sent to review | – | 1 |
| Acronym collisions (R1 guard) / ambiguous acronyms scoped (R2) | – | 0 / 0 |
| Lexicon `same` / `different` (approved) | – | 60 / 5 (+18 proposed seeds, ignored until you tick them) |
| Merges blocked by `different` (R1–R3 / chain / candidates to the LLM) | – | 0 / 0 / 0 |
| Unexplained confusables (approved `different` pair, no edge) | – | 4 |
| Edges (before/after consolidation) | 297 | 294 (1 consolidated, 0 merge self-loops rejected, 0 secondary on a shared pair) |
| Linked share, all concepts / `defined` concepts | 38.4% / 43.5% | 39.5% / 44.8% |
| `alias_contradicted` flags / conflict groups after re-key / cycles | – | 0 / 0 / 0 |
| Sphere ch3: core–periphery label | weak core | weak core |
| Sphere ch3: Δρ (primary null) | 0.030 | 0.041 |
| Sphere ch3: core (centre+inner) soft Jaccard vs CR-007 (old ids mapped to survivors) | – | 0.82 (72 → 72 nodes) |
| `equivalent_to` edges in any layer | 3 | **0** |
| LLM merge calls R1–R3 would have replaced (STOP 1 backtest) | – | 21 of 236 on this slice (9%; 1003 exact-string merges were already free) |

## Owner precision per rule

Pending your marks on the merge sheet. R1/R2/R3-strong must have no wrong merges; any that does is inspected and gets a guard or is demoted to review (logged in DECISIONS).

## Top-15 importance changes (ch3)

- Before: node, switch, packet, frame, message, router, host, physical medium, protocol, network, Internet, physical network, application, bit, IP
- After: node, packet, switch, frame, router, Internet, message, Internet Protocol, host, physical network, physical medium, network, protocol, application, bit
- Entered: Internet Protocol; left: IP

## Equivalence migration (`equivalent_to` edges)

| Pair | Section | What happened |
|---|---|---|
| forwarding table ≡ routing table | 3.4 | retired (`equivalent_to_retired`, kept in the run); lexicon `different` D-CR-005-29; the pair is queued for normal relation classification at the next relation run |
| delay ≡ latency | 1.5 | merged into one node by a rule (the edge disappears into it) |
| cloudification ≡ softwarization | 1-perspective-feature-velocity | held out of the graph; on your merge sheet as an `equivalence_migration` item |

## Conflicts and `alias_contradicted`

- Conflict groups (detection only; no adjudication call made): 0
- `alias_contradicted` flags: 0

## Unexplained confusables (no edge between the pair)

Approved `different` pairs: routing table / forwarding table; destination address / DestinationAddr; Internet / internetworking; cyclic redundancy check / error-detecting code

If you approve the research seeds, these would also be unexplained: switch / switching; bit / bit rate; bandwidth / throughput; latency / round-trip time; bandwidth / data rate; flow control / congestion control; frame / packet; MAC address / IP address; hub / switch; router / switch; CSMA/CD / CSMA/CA; error detection / error correction

## Merge sheet

`data/interim/checks/cr008_merge_sheet.csv` (+ key): {'R1': 1, 'R2': 10, 'R3-strong': 2, 'R3-weak': 1, 'equivalence_migration': 1}. Judgement: same / different. Save your copy to `data/gold/merges/`.

## Misconception layer

- Cue scan: 35 candidate sentences ⇒ `is_warning` = yes: 6 ⇒ in the layer: **2**, held as `needs_correct_edge`: 3, owner review after failed checks: 1; dismissed as plain facts: 28.
- By perturbation type: {'polarity_flip': 1, 'conflation': 1}; by prevalence cue: {'stated_possible': 1, 'none': 1}.
- Proposed correct edges accepted by the verifier (bulk tier): 1; rejected: 3.
- Cost $0.55 vs preflight $0.77.

**M-2.7-796585** — polarity_flip / stated_possible: If a sender hears no other transmissions, a hidden node cannot cause a collision at the receiver.
  - wrong edge: hidden node —causes→ collision (negated); contradicts ['E:MP-5']
  - quote: “The Carrier Sense part seems simple enough: Before sending a packet, the transmitter checks if it can hear any other transmissions; if not, it sends.”

**M-3.4-579827** — conflation / none: A routing table and a forwarding table are the same thing.
  - wrong edge: routing table —conflated_with→ forwarding table (affirmed); contradicts ['L:D-CR-005-29']
  - quote: “the terms forwarding table and routing table are sometimes used interchangeably”

**Owner review (checks failed twice)** §2.4: At first glance, it would seem that correction is always better, since with detection we are forced to throw away the message and, in general, ask for another c
  - failed: the wrong edge is not a modality_error of any contradicted edge

**Held as `needs_correct_edge`** (the book states the correct idea but the verifier did not accept the proposed edge):

- Connecting hosts is enough to provide host-to-host connectivity without assigning addresses. (§1.2)
- Increasing bandwidth improves latency at the same rate. (§1.5)
- If C hears B transmitting, C cannot transmit to anyone. (§2.7)

Sheet: `data/interim/checks/cr008_misconception_sheet.csv` (+ key).
