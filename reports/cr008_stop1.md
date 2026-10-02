# CR-008 STOP 1 — plan and $0 backtest

Run: `slice3_a1` (P&D ch. 1–3, 982 concepts, 24 sections). No API calls made.

## (a) Backtest of R1–R3 against both owner merge sheets

**CR-005**: 43 rows (41 same / 2 different).
**CR-007**: 40 rows (38 same / 2 different).

| Rule | owner `same` | owner `different` (wrong) |
|---|---|---|
| R1 | 12 | 0 |
| R1-blocked(acronym collision) | 0 | 0 |
| R2 | 25 | 0 |
| R3-strong | 0 | 0 |
| R3-weak | 2 | 0 |
| no rule (would go to R4) | 40 | 4 |

Owner-marked **wrong/different** pairs, and what the rules do with each:

- CR-005 #29 “routing table” / “forwarding table” → rule: **None**
- CR-005 #37 “destination address” / “DestinationAddr” → rule: **None**
- CR-007 #4 “Telco Central Office” / “Central Office” → rule: **None**
- CR-007 #8 “data link protocol” / “Link-level protocol” → rule: **None**

Owner-marked **same** pairs that no auto rule (R1, R2, R3-strong) would merge (they stay R4 or review):

- CR-005 #2 “access network” / “last-mile link” → R3-weak
- CR-005 #4 “mobile network” / “cellular network” → R4
- CR-005 #8 “4B/5B encoding” / “4B/5B” → R4
- CR-005 #10 “HDLC protocol” / “High-Level Data Link Control (HDLC)” → R4
- CR-005 #11 “bit-oriented framing protocol” / “bit-oriented protocol” → R4
- CR-005 #12 “data rate” / “bit rate” → R4
- CR-005 #16 “multi-access network” / “multiple-access network” → R4
- CR-005 #17 “last-mile” / “last-mile link” → R4
- CR-005 #19 “Evolved NodeB (eNodeB)” / “Broadband Base Unit (BBU)” → R4
- CR-005 #20 “millimeter wave (mmWave)” / “millimeter-wave band” → R4
- CR-005 #23 “Telco Central Office” / “Central Office” → R4
- CR-005 #24 “public Internet” / “Internet” → R4
- CR-005 #26 “route” / “path” → R4
- CR-005 #27 “data link protocol” / “Link-level protocol” → R4
- CR-005 #28 “connection-oriented model” / “connection-oriented approach” → R4
- CR-005 #30 “L2 switch” / “Layer 2 switch” → R4
- CR-005 #31 “Spanning tree protocol” / “Spanning tree algorithm” → R4
- CR-005 #32 “VLAN tag” / “VLAN ID” → R4
- CR-005 #34 “Classless Interdomain Routing” / “classless addressing” → R4
- CR-005 #35 “ARP table” / “ARP cache” → R4
- CR-005 #38 “network prefix” / “prefix” → R4
- CR-005 #39 “network interface card” / “network adaptor” → R4
- CR-005 #40 “physical memory” / “main memory” → R4
- CR-005 #43 “VXLAN VID” / “Virtual Network Id (VNI)” → R4
- CR-007 #2 “TCP/IP architecture” / “Internet architecture” → R4
- CR-007 #6 “gateway” / “router” → R4
- CR-007 #7 “access network” / “last-mile link” → R3-weak
- CR-007 #10 “bit rate” / “data rate” → R4
- CR-007 #11 “CIDR” / “Classless Interdomain Routing” → R4
- CR-007 #12 “OSI reference model” / “OSI architecture” → R4
- CR-007 #14 “millimeter wave (mmWave)” / “millimeter-wave band” → R4
- CR-007 #15 “bit-oriented framing protocol” / “bit-oriented protocol” → R4
- CR-007 #17 “Evolved NodeB (eNodeB)” / “Broadband Base Unit (BBU)” → R4
- CR-007 #19 “IEEE 802.11” / “802.11 Wi-Fi standards” → R4
- CR-007 #20 “ARP table” / “ARP cache” → R4
- CR-007 #27 “VXLAN VID” / “Virtual Network Id (VNI)” → R4
- CR-007 #29 “Payload” / “Message body” → R4
- CR-007 #30 “networked application” / “network application” → R4
- CR-007 #31 “physical memory” / “main memory” → R4
- CR-007 #33 “application-level protocol” / “Application layer protocol” → R4
- CR-007 #38 “multi-access network” / “multiple-access network” → R4
- CR-007 #39 “link” / “physical medium” → R4

**Owner marks that disagree across the two sheets: 2** (the lexicon validator refuses a pair in both lists, so these need your ruling):

- “Telco Central Office” / “Central Office”: CR-005 #23 = same, CR-007 #4 = different
- “data link protocol” / “Link-level protocol”: CR-005 #27 = same, CR-007 #8 = different

## (b) Currently separate nodes the rules would merge (CR-007 run)

| Rule | pairs merged |
|---|---|
| R1 | 4 |
| R2 | 45 |
| R3-strong | 2 |
| R3-weak (review only) | 3 |

Pairs blocked by an existing `never_merge`: 0. Concept names with an embedded acronym to split (R2): 38. R1 acronym collisions (sent to review): 0 []. Ambiguous acronyms (one short form, ≥ 2 long forms): 1 {'SWP': ['slidingwindowprotocol', 'swpwouldcallsend']}.

**R1 — up to 10 examples**

- “computer network” + “computer networks”
- “last mile” + “last-mile”
- “Software Defined Network” + “Software Defined Networks”
- “exclusive OR” + “exclusive-OR”

**R2 — up to 10 examples**

- “HTTP” + “Hypertext Transfer Protocol (HTTP)”
- “TCP” + “Transmission Control Protocol (TCP)”
- “round-trip time” + “round-trip time (RTT)”
- “Internet Service Provider” + “Internet Service Provider (ISP)”
- “ISP” + “Internet Service Provider (ISP)”
- “CRC” + “cyclic redundancy check (CRC)”
- “Synchronous Optical Network” + “Synchronous Optical Network (SONET)”
- “SONET” + “Synchronous Optical Network (SONET)”
- “exclusive OR” + “exclusive OR (XOR)”
- “exclusive-OR” + “exclusive OR (XOR)”

**R3-strong — up to 10 examples**

- “latency” + “delay”
- “Automatic repeat request” + “ARQ”

**R3-weak items (evidence quotes)**

- [often_referred] “end hosts” ~ “frames”: …to the end node. This is the framing problem, and the messages delivered to the end hosts are often called frames (or sometimes packets). Third, because frames are sometimes corrupted during transm…
- [often_referred] “base stations” ~ “Broadband Base Units (BBU”: …t are connected to a wired network. In the case of the cellular network, the base stations are often called Broadband Base Units (BBU), the mobile devices that connect to them are usually referred t…
- [or_alternatively] “last-mile links” ~ “access networks”: …unter in coffee shops, airports, universities, etc.) or through so-called last-mile links (or alternatively, access networks) provided by an ISP, as illustrated in Figure. These link types are summar…

## (c) R4 (LLM) merge calls R1–R3 would have replaced

CR-007 logged **236** LLM-decided candidate pairs (24 merged, 16 review-band, 196 broader/narrower; “different” outcomes are not stored, so this is a lower bound). R1–R3 would have replaced **21** of them (9%): {('merge', 'R2'): 4, ('merge', 'R1'): 8, ('review', 'R2'): 6, ('review', 'R1'): 2, ('taxonomy', 'R2'): 1}. A further 1003 exact-string merges were already free. At ≈ $0.0031 per call this is a saving of $0.065 on this slice; the full-book saving scales roughly with the number of sections.

## (d) Lexicon seed

- From owner marks: **79 `same`** and **9 `different`** candidate entries (duplicates between the sheets and the `never_merge` list are collapsed on load).
- `different` pairs with a sentence in the slice that contains both forms: 5 of 9; of those, 0 contain a distinguishing cue (unlike / whereas / differs / …).
- **Research-chat seed confusables: not found.** `configs/term_lexicon.yaml` does not exist in the repo and no seed list is in `docs/`. I have not invented any. Please paste or drop the seed list; until then the seed approval sheet (`data/interim/checks/cr008_seed_sheet.csv`) has no research-chat rows.

- different: “routing table” / “forwarding table” (CR-005 sheet row 29) — §3.1: “To decide how to forward a packet, a switch consults a forwarding table (sometimes called a routing table), an example of which is depicted in Table.”
- different: “destination address” / “DestinationAddr” (CR-005 sheet row 37) — no co-occurring sentence
- different: “Telco Central Office” / “Central Office” (CR-007 sheet row 4) — §2-perspective-race-to-the-edge: “This initiative is often called CORD, which is an acronym for C\ entral O\ ffice R\ e-architected as a D\ atacenter, and as the name suggests, the idea is to build the Telco Central Office (or the Cab”
- different: “data link protocol” / “Link-level protocol” (CR-007 sheet row 8) — no co-occurring sentence
- different: “High-Level Data Link Control (HDLC)” / “Synchronous Data Link Control (SDLC)” (configs/canonical_overrides.yaml never_merge) — §2.3: “The Synchronous Data Link Control (SDLC) protocol developed by IBM is an example of a bit-oriented protocol; SDLC was later standardized by the ISO as the High-Level Data Link Control (HDLC) protocol.”
- different: “Internet” / “internetworking” (configs/canonical_overrides.yaml never_merge) — §1.3: “The Internet’s application layer is considered to be at layer 7, its transport layer is layer 4, the IP (internetworking or just network) layer is layer 3, and the link or subnet layer below IP is lay”
- different: “cyclic redundancy check” / “error-detecting code” (configs/canonical_overrides.yaml never_merge) — no co-occurring sentence
- different: “routing table” / “forwarding table” (configs/canonical_overrides.yaml never_merge) — §3.1: “To decide how to forward a packet, a switch consults a forwarding table (sometimes called a routing table), an example of which is depicted in Table.”
- different: “destination address” / “DestinationAddr” (configs/canonical_overrides.yaml never_merge) — no co-occurring sentence

## (e) Equivalence audit — `equivalent_to` edges

3 edge(s) in the run:

- “forwarding table” ≡ “routing table” (direction forward): R0–R3 → **no rule → equivalence_migration item on the merge sheet**. Quote: “While the terms forwarding table and routing table are sometimes used interchangeably, we will make a distinction between them here.”
- “delay” ≡ “latency” (direction forward): R0–R3 → **R3-strong**. Quote: “latency (also called delay)”
- “cloudification” ≡ “softwarization” (direction forward): R0–R3 → **no rule → equivalence_migration item on the merge sheet**. Quote: “called the “cloudification” or “softwarization” of the network”

## (f) Misconception cue scan ($0)

3291 sentences scanned.

| Family | hits |
|---|---|
| explicit_error | 0 |
| tempting_belief | 7 |
| confusion | 0 |
| negated_identity | 18 |
| existing: `corrects_intuition` edges | 4 |
| existing: `different` pairs co-mentioned | 5 |

**explicit_error — 5 examples**

- (none)

**tempting_belief — 5 examples**

- §1.4: The main abstraction of the socket interface, not surprisingly, is the socket.
- §2.4: If the transmitted message is P(x), we may think of the introduction of errors as the addition of another polynomial E(x), so the recipient sees P(x) + E(x).
- §2.4: At first glance, it would seem that correction is always better, since with detection we are forced to throw away the message and, in general, ask for another copy to be transmitted.
- §2.5: Also note that the relationship between the window size and the sequence number space depends on an assumption that is so obvious that it is easy to overlook, namely that frames are not reordered in transit.
- §2.7: At first glance, it might seem that a wireless protocol would follow the same algorithm as the Ethernet—wait until the link becomes idle before transmitting and back off should a collision occur—and, to a first approximation, this is what 802.11 does.

**confusion — 5 examples**

- (none)

**negated_identity — 5 examples**

- §1.2: Just because a set of hosts are directly or indirectly connected to each other does not mean that we have succeeded in providing host-to-host connectivity.
- §1.3: In this sense, the schematic given in Figure is not a protocol graph, per se, but rather a reference model for a protocol graph.
- §1.3: First, as best illustrated by Figure, the Internet architecture does not imply strict layering.
- §1.5: To quote Scotty from Star Trek, “Ye cannae change the laws of physics.” In other words, “high speed” does not mean that latency improves at the same rate as bandwidth; the transcontinental RTT of a 1-Gbps link is the same 100 ms as it is for a 1-Mbps link.
- §2.6: (An adaptor can also be programmed to run in promiscuous mode, in which case it delivers all received frames to the host, but this is not the normal mode.) In addition to these unicast addresses, an Ethernet address consisting of all 1s is treated as a broadca

**`corrects_intuition` edges**

- Every network type has a maximum transmission unit that limits the size of an IP datagram it can carry in a frame. — “every network type has a maximum transmission unit (MTU)”
- The edge of the ISP’s network connects directly to customers via the last-mile link. — “edge of the ISP’s network; the ISP-side of the last-mile that directly connects to customers”
- The invention of new applications contributes to changes in networks. — “networks are constantly changing as technology evolves and new applications are invented”
- This implementation does not perform piggybacking of ACKs on data frames. — “implementation does not support piggybacking ACKs on data frames”

**Preflight for structuring (§5.3):** 33 distinct candidate sentences ⇒ 33 strong-tier calls × ≈ $0.022 (3.5k in / 1.5k out incl. reasoning) ≈ **$0.73**; family 4 is noisy, so most calls should end at `is_warning: no`. Verifying proposed correct edges is extra (≈ $0.1–0.3 in the CR). Cap stays $3.

