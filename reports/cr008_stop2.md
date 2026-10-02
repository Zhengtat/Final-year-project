# CR-008 STOP 2 — before/after (slice3_a1 → slice3_b4)

Re-keying and the lexicon cost $0. The misconception stage cost **$1.06** in total across all attempts (preflight $0.77, hard cap $3). No marks from you yet, so every precision figure below is pending.

## §6 metrics

| Metric | Before (CR-007) | After (CR-008) |
|---|---|---|
| Nodes | 982 | 913 |
| Merges per rule (re-key) | – | R0 54, R1 0, R2 15, R3-strong 0 (R4 unchanged: the LLM merges already in the run are kept) |
| R3-weak items sent to review | – | 1 |
| Acronym collisions (R1 guard) / ambiguous acronyms scoped (R2) | – | 0 / 0 |
| Lexicon `same` / `different` (approved) | – | 77 / 21 (+0 proposed seeds, ignored until you tick them) |
| Merges blocked by `different` (R1–R3 / chain / candidates to the LLM) | – | 0 / 0 / 0 |
| Unexplained confusables (approved `different` pair, no edge) | – | 15 |
| Edges (before/after consolidation) | 297 | 294 (1 consolidated, 0 merge self-loops rejected, 0 secondary on a shared pair) |
| Linked share, all concepts / `defined` concepts | 38.4% / 43.5% | 39.5% / 44.9% |
| `alias_contradicted` flags / conflict groups after re-key / cycles | – | 0 / 0 / 0 |
| Sphere ch3: core–periphery label | weak core | weak core |
| Sphere ch3: Δρ (primary null) | 0.030 | 0.043 |
| Sphere ch3: core (centre+inner) soft Jaccard vs CR-007 (old ids mapped to survivors) | – | 0.79 (71 → 72 nodes) |
| `equivalent_to` edges in any layer | 3 | **0** |
| LLM merge calls R1–R3 would have replaced (STOP 1 backtest) | – | 21 of 236 on this slice (9%; 1003 exact-string merges were already free) |

## Owner precision per rule

| Rule | marked same | n | Wilson 95% CI |
|---|---|---|---|
| R1 | 1 | 1 | [0.21, 1.00] |
| R2 | 10 | 10 | [0.72, 1.00] |
| R3-strong | 2 | 2 | [0.34, 1.00] |
| R3-weak | 0 | 1 | [0.00, 0.79] |
| equivalence_migration | 1 | 1 | [0.21, 1.00] |

Row 14 ("end hosts / frames", R3-weak) was marked `same` in the sheet; you ruled it a slip, so it counts as `different` here. The gold file is unchanged.
Auto rules (R1, R2, R3-strong) have **no wrong merge**: no guard or demotion needed. R3-weak stays review-only, and its one item was wrong, which supports never auto-merging it.

## Top-15 importance changes (ch3)

- Before: node, switch, packet, frame, message, router, host, physical medium, protocol, network, Internet, physical network, application, bit, IP
- After: switch, packet, node, frame, message, physical network, router, Internet, Internet Protocol, network, host, protocol, application, bit, latency
- Entered: Internet Protocol, latency; left: IP, physical medium

## Equivalence migration (`equivalent_to` edges)

| Pair | Section | What happened |
|---|---|---|
| forwarding table ≡ routing table | 3.4 | retired (`equivalent_to_retired`, kept in the run); lexicon `different` D-CR-005-29; the pair is queued for normal relation classification at the next relation run |
| delay ≡ latency | 1.5 | merged into one node by a rule (the edge disappears into it) |
| cloudification ≡ softwarization | 1-perspective-feature-velocity | merged into one node by a rule (the edge disappears into it) |

## Conflicts and `alias_contradicted`

- Conflict groups (detection only; no adjudication call made): 0
- `alias_contradicted` flags: 0

## Unexplained confusables (no edge between the pair)

Approved `different` pairs: routing table / forwarding table; destination address / DestinationAddr; Internet / internetworking; cyclic redundancy check / error-detecting code; switch / switching; bit / bit rate; bandwidth / data rate; flow control / congestion control; frame / packet; MAC address / IP address; hub / switch; router / switch; CSMA/CD / CSMA/CA; error detection / error correction; end hosts / frames

If you approve the research seeds, these would also be unexplained: (none)

## Merge sheet

`data/interim/checks/cr008_merge_sheet.csv` (+ key): {'R2': 10, 'R3-weak': 1}. Judgement: same / different. Save your copy to `data/gold/merges/`.

## Misconception layer

- Cue scan: 89 candidate sentences ⇒ `is_warning` = yes: 13 ⇒ in the layer: **2**, held as `needs_correct_edge`: 10, owner review after failed checks: 1; dismissed as plain facts: 75.
- By perturbation type: {'polarity_flip': 1, 'conflation': 1}; by prevalence cue: {'none': 2}.
- Proposed correct edges accepted by the verifier (bulk tier): 1; rejected: 10.
- Cost $1.06 vs preflight $0.77.

**M-3.1-078589** — polarity_flip / none: Fast parallel hardware switches can only be built using fixed-length cells.
  - wrong edge: hardware switch —requires→ cell (affirmed); contradicts ['E:MP-12']
  - quote: “fast parallel hardware switches can only be built using fixed-length cells”

**M-3.4-579827** — conflation / none: A routing table and a forwarding table are the same thing.
  - wrong edge: routing table —conflated_with→ forwarding table (affirmed); contradicts ['L:D-CR-005-29']
  - quote: “the terms forwarding table and routing table are sometimes used interchangeably”

**Owner review (checks failed twice)** §2.4: At first glance, it would seem that correction is always better, since with detection we are forced to throw away the message and, in general, ask for another c
  - failed: the wrong edge is not a modality_error of any contradicted edge

**Held as `needs_correct_edge`** (the book states the correct idea but the verifier did not accept the proposed edge):

- If hosts are connected, they already have host-to-host connectivity without needing addresses. (§1.2)
- A higher-bandwidth link must improve latency at the same rate as bandwidth. (§1.5)
- Bit rate is always less than or equal to baud rate. (§2.2)
- Bit rate is always less than or equal to baud rate. (§2.2)
- The Checksum field is a checksum. (§2.3)
- Error correction is always better than error detection because it avoids retransmissions. (§2.4)
- If C hears B transmitting, C cannot transmit to anyone. (§2.7)
- A collision can occur only if the sender can hear another transmission before sending. (§2.7)
- The names Central Office and Head End suggest that these edge sites are centralized, at the root of the ISP’s network hierarchy. (§2.8)
- Switching is what distinguishes an SVC from a PVC. (§3.1)

### Owner marks on the misconception layer (carried over by quote)

- (a) the book gives this warning: **4 of 5** marked entries (Wilson 95% CI [0.38, 0.96]). The one `no` is the forwarding/routing-table conflation: "sometimes used interchangeably … we will make a distinction" is a terminology note, not a refuted belief.
- (b) 2 entries carry an owner rewrite (`owner_fix`); (c) correct-edge judgement carried where the entry still has one.
- 7 entries are new since your marks (delta sheet).

### Structuring yield (family 5 not narrowed this run)

| source | candidates | kept (items + needs_correct_edge + review) | dismissed as plain facts |
|---|---|---|---|
| text cue: negated_identity | 18 | 4 | 14 |
| text cue: contrast | 11 | 3 | 8 |
| pair: frame | packet | 10 | 0 | 10 |
| pair: bit | bit rate | 9 | 2 | 7 |
| pair: router | switch | 8 | 1 | 7 |
| text cue: tempting_belief | 7 | 1 | 6 |
| pair: routing table | forwarding table | 6 | 1 | 4 |
| pair: VLAN | VXLAN | 4 | 0 | 4 |
| pair: Internet | internetworking | 3 | 0 | 3 |
| pair: bit | bit stream | 3 | 0 | 3 |
| pair: bandwidth | data rate | 2 | 0 | 2 |
| pair: error detection | error correction | 2 | 1 | 1 |
| pair: 4B/5B | 8B/10B | 1 | 0 | 1 |
| pair: CSMA/CD | CSMA/CA | 1 | 0 | 1 |
| pair: High-Level Data Link Control (HDLC) | Synchronous Data Link Control (SDLC) | 1 | 0 | 1 |
| pair: NRZ | NRZI | 1 | 0 | 1 |
| pair: hub | switch | 1 | 0 | 1 |
| pair: switch | switching | 1 | 0 | 1 |

Lexicon-pair candidates kept 5 of 53; text-cue candidates kept 8 of 36.

Sheets: the sheet you marked is `cr008_misconception_sheet.csv` (rows refer to the CR-008 STOP 2 run); new entries are on `cr008_misconception_sheet_delta.csv`; the recall sample is `cr008_recall_sample_sheet.csv` (20 negation sentences the cues did not catch).
