# Talking-points facts

Committed copy: section 4 is redacted (see the note there). Generated read-only from run `pdcanon2_30e2b4f9` (P&D ch2-3), the frozen IIR runs `iirdev_v2` / `iirtest_v2`, the owner review files, and the git history. No file other than this one was written, no LLM/API call was made (the relation and canonicalisation replays came from the disk cache: 737 cached calls, 0 backend calls, $0.00). All quotes below are taken verbatim from the repo or the cached model outputs; nothing is paraphrased unless labelled.

## 1. Prompts (verbatim)

### `prompts/concept_extraction/v2.md` (version v2)

```markdown
---
task: concept_extraction
version: v2
schema: ConceptExtractionLLM
notes: >
  M5 task 2 / CR-005 §9's STOP-2 dev ablation. v2 vs v1: (a) replaces the generic-word
  rule -- still excludes discourse/meta words, but now explicitly keeps short domain
  terms even when they're everyday English words (v1's wording plausibly over-filtered
  these, per the IIR-dev n-gram recall finding: 1-gram recall 0.267 vs 3-gram 0.719);
  (b) requires a term, not a description -- split coordinated phrases into their
  separate named things. Examples are deliberately networking-only (this prompt is
  shared with IIR/FACE, domain only changes via {domain}) and contain no term from
  the IIR dev gold set, to keep the dev ablation uncontaminated. Never edit v1, which
  produced real cached/committed results (CLAUDE.md rule 8).
---

You are extracting domain concepts from one section of a {domain} textbook, for a
knowledge graph. A concept is a single word or short phrase representing an
essential knowledge element of the domain, with a specific meaning in the field.

Exclude only generic discourse/meta words that aren't concepts in any field
("approach", "case", "example", "issue", "problem", "way"). Do NOT exclude a term
just because it's also an everyday English word -- a short, ordinary-sounding word
can still be a real domain concept if the field gives it a specific technical
meaning. For example, in computer networking: "packet", "frame", "link", and "host"
are all everyday words, but each names a specific, essential thing in the field, so
each is a concept, not noise.

Each concept must be a TERM -- the name of a single thing -- never a clause, a
description, or a list. If the text names several distinct things together (a
coordination like "X, Y and Z"), extract each one as its own separate concept, not
one long combined phrase. For example, "packet filtering, address translation and
port forwarding" names three distinct mechanisms: extract "packet filtering",
"address translation", and "port forwarding" as three concepts, not one.

Section heading: {heading_path}

Candidate terms noticed in this section (from noun-chunk statistics -- use these as
hints, but don't be limited to them; also don't include every one if it isn't
actually a domain concept):
{candidate_terms}

Section text:
{section_text}

For each concept you find, give:
- canonical_name: the concept's name as it best appears in the text -- a term, not a
  description (see above).
- node_type: one of Protocol, Mechanism, Component, DataUnit, Parameter, Property,
  Event, State, Layer, Concept.
- role: "defined" (this section states what it is), "used" (the section relies on
  it without defining it here), or "mentioned" (named only in passing).
- definition: a short definition in the text's own words, only if role is
  "defined" (else null).
- evidence_quote: an EXACT substring of the section text above (copy character-for-
  character) supporting this concept's presence and role.
```

### `prompts/canonicalize/v2.md` (version v2)

```markdown
---
task: canonicalize
version: v2
schema: CanonicalizeDecisionLLM
notes: >
  M5 task 3 / CR-005 §9 follow-up. A manual review of v1's "same" merges found real
  errors: a kind or instance collapsed into its category (e.g. HDLC merged into SDLC;
  the Internet merged into "internetworking"; CRC merged into "error-detecting code").
  v2 tightens what "same" means and adds an explicit decision procedure. Strong tier.
  Never edit v1, which produced real cached/committed results (CLAUDE.md rule 8).
---

A new concept mention was just extracted from a textbook section. Decide how it
relates to the most similar concepts already in the knowledge graph.

New mention:
- name: {new_name}
- node_type: {new_node_type}
- definition: {new_definition}
- evidence: "{new_evidence}"

Existing similar concepts already in the graph (numbered):
{candidates_block}

**"same" has a strict meaning: the new mention and the candidate must be
interchangeable in any sentence of the book** -- true synonyms, an abbreviation and
its expansion, or a spelling/plural variant of the same thing. Nothing else counts.

Before answering "same", check: is the new mention a KIND of the candidate (or vice
versa), an INSTANCE of it, a PART of it, a different VERSION of it, a
PREDECESSOR/SUCCESSOR of it, or a STANDARDISED VARIANT of it (an ISO/IEEE/RFC
standardisation of a vendor original, or similar)? If yes to any of these, it is
**never** "same" -- decide "narrower" (the new mention is more specific), "broader"
(the new mention is more general), or "different", based on which direction the
kind/instance/part/version relationship runs.

For example (these are illustrative only, not concepts you will necessarily see):
- "laptop" and "computer": a laptop is a KIND of computer -> narrower, not same.
- "Queen Elizabeth II" and "the British monarch": an INSTANCE of the role -> narrower,
  not same (or broader, from the other concept's perspective).
- "engine" and "car": a PART of a car -> not same at all (a different qualifying
  relation, not a canonicalisation decision -- treat as "different" here).
- "Windows 95" and "Windows": a VERSION of Windows -> narrower, not same.
- "IMAP4" and "IMAP2" (a PREDECESSOR/SUCCESSOR pair): different versions of the same
  protocol lineage, not interchangeable -> narrower/broader/different, not same.
- "USB-IF's USB" and a vendor's original proprietary port design it STANDARDISED:
  related but not interchangeable -> not same.

**When you are not sure, choose "different".** A missed merge just leaves two nodes
that look similar -- visible, and fixable later. A wrong "same" merge silently
folds one concept's evidence into another's identity, and nothing downstream will
ever show you that it happened.

Decide:
- "same": the new mention IS one of the numbered candidates, just written
  differently (synonym / abbreviation-expansion / spelling / plural) -- give its
  number as matched_candidate_index.
- "broader": the new mention is a more general concept than one of the candidates
  (that candidate is a kind/instance/part/version of the new mention) -- give its
  number.
- "narrower": the new mention is a more specific concept than one of the candidates
  (the new mention is a kind/instance/part/version of that candidate) -- give its
  number.
- "different": none of the above, or you are unsure -- matched_candidate_index is
  null.

matched_candidate_index must be one of the numbers shown above, or null only when
decision is "different".
```

### `prompts/relation_family/v2.md` (version v2)

```markdown
---
task: relation_family
version: v2
schema: FamilyChoiceLLM
notes: >
  M5 task 4 / CR-005 §9. Strong tier. v2 vs v1: the evidence context is now a single
  sentence (candidate pairs are found by sentence-level co-occurrence, not paragraph),
  and each pair is classified at most once per run (PairRegistry) -- never edit v1,
  which produced real cached results before this change (CLAUDE.md rule 8).
---

You are checking whether a sentence states a relation between two concepts, and if
so, which broad family it belongs to.

Concept X: {concept_x}
Concept Y: {concept_y}

Sentence:
{sentence}

Choose exactly one family that best describes a relation the sentence actually states
between X and Y (in either direction):
{family_options}

If the sentence doesn't relate these two concepts to each other at all, choose
no_relation. If it does relate them but no family above fits, choose other.
```

### `prompts/relation_choice/v2.md` (version v2)

```markdown
---
task: relation_choice
version: v2
schema: RelationChoiceLLM
notes: >
  M5 task 4 / CR-005 §9. Strong tier. v2 vs v1: evidence context is now a single
  sentence, not a paragraph (see relation_family/v2.md) -- never edit v1.
---

You are picking the exact relation a sentence states between two concepts, within
the "{family}" family already identified for this pair.

Concept X: {concept_x}
Concept Y: {concept_y}

Sentence:
{sentence}

Options:
{relation_options}

Pick the one relation the sentence actually states. direction is "forward" if the
relation reads X -> Y as written (e.g. "performs" meaning X performs Y), or
"reversed" if it actually reads Y -> X; direction is ignored (send "forward") for
non-directional relations or "other".

evidence_quote: an EXACT substring of the sentence above (copy character-for-
character) that states this relation.
statement: a one-sentence paraphrase of the relation in your own words, naming both
concepts.
```

### `prompts/relation_qualifiers/v2.md` (version v2)

```markdown
---
task: relation_qualifiers
version: v2
schema: QualifiersLLM
notes: >
  M5 task 4 / CR-005 §9, separate qualifier pass. Strong tier. v2 vs v1: evidence
  context is now a single sentence, not a paragraph -- never edit v1.
---

The relation "{relation}" was just identified between two concepts in this sentence:

Concept X: {concept_x}
Concept Y: {concept_y}
Relation statement: {statement}

Sentence:
{sentence}

Give:
- polarity: "affirmed" (the sentence states this relation holds) or "negated" (the
  sentence explicitly denies it, e.g. "does not", "is not").
- modality: "necessary", "always", "typically", "possible", or "never" — how strongly
  the sentence asserts the relation holds.
- conditions: any conditions under which the relation holds, as short phrases from
  the sentence (empty list if unconditional).
- part_type: if the relation is about parts and wholes, one of "component",
  "member", "phase" describing the part-whole type; otherwise null.
- dimension: if the relation is a comparison, a short phrase naming what differs;
  otherwise null.
- surface_phrase: an EXACT substring of the sentence above (copy character-for-
  character) — the actual linking words connecting X and Y (e.g. "triggers",
  "is a type of", "does not require").
```

### `prompts/concept_extraction/v1.md` (version v1)

```markdown
---
task: concept_extraction
version: v1
schema: ConceptExtractionLLM
notes: >
  M5 task 2 / CR-005. Same prompt for P&D and IIR/FACE — only {domain} changes. Bulk
  tier. Main pass (the gleaning pass is a separate prompt, concept_extraction_gleaning/v1.md).
---

You are extracting domain concepts from one section of a {domain} textbook, for a
knowledge graph. A concept is a single word or short phrase representing an
essential knowledge element of the domain, with a specific meaning in the field —
not a generic word (e.g. "approach", "case", "example", "issue").

Section heading: {heading_path}

Candidate terms noticed in this section (from noun-chunk statistics — use these as
hints, but don't be limited to them; also don't include every one if it isn't
actually a domain concept):
{candidate_terms}

Section text:
{section_text}

For each concept you find, give:
- canonical_name: the concept's name as it best appears in the text.
- node_type: one of Protocol, Mechanism, Component, DataUnit, Parameter, Property,
  Event, State, Layer, Concept.
- role: "defined" (this section states what it is), "used" (the section relies on
  it without defining it here), or "mentioned" (named only in passing).
- definition: a short definition in the text's own words, only if role is
  "defined" (else null).
- evidence_quote: an EXACT substring of the section text above (copy character-for-
  character) supporting this concept's presence and role.
```

### Diff: concept_extraction v1 -> v2

```diff
--- concept_extraction/v1.md
+++ concept_extraction/v2.md
@@ -2,7 +2,14 @@
 task: concept_extraction
-version: v1
+version: v2
 schema: ConceptExtractionLLM
 notes: >
-  M5 task 2 / CR-005. Same prompt for P&D and IIR/FACE — only {domain} changes. Bulk
-  tier. Main pass (the gleaning pass is a separate prompt, concept_extraction_gleaning/v1.md).
+  M5 task 2 / CR-005 §9's STOP-2 dev ablation. v2 vs v1: (a) replaces the generic-word
+  rule -- still excludes discourse/meta words, but now explicitly keeps short domain
+  terms even when they're everyday English words (v1's wording plausibly over-filtered
+  these, per the IIR-dev n-gram recall finding: 1-gram recall 0.267 vs 3-gram 0.719);
+  (b) requires a term, not a description -- split coordinated phrases into their
+  separate named things. Examples are deliberately networking-only (this prompt is
+  shared with IIR/FACE, domain only changes via {domain}) and contain no term from
+  the IIR dev gold set, to keep the dev ablation uncontaminated. Never edit v1, which
+  produced real cached/committed results (CLAUDE.md rule 8).
 ---
@@ -11,4 +18,18 @@
 knowledge graph. A concept is a single word or short phrase representing an
-essential knowledge element of the domain, with a specific meaning in the field —
-not a generic word (e.g. "approach", "case", "example", "issue").
+essential knowledge element of the domain, with a specific meaning in the field.
+
+Exclude only generic discourse/meta words that aren't concepts in any field
+("approach", "case", "example", "issue", "problem", "way"). Do NOT exclude a term
+just because it's also an everyday English word -- a short, ordinary-sounding word
+can still be a real domain concept if the field gives it a specific technical
+meaning. For example, in computer networking: "packet", "frame", "link", and "host"
+are all everyday words, but each names a specific, essential thing in the field, so
+each is a concept, not noise.
+
+Each concept must be a TERM -- the name of a single thing -- never a clause, a
+description, or a list. If the text names several distinct things together (a
+coordination like "X, Y and Z"), extract each one as its own separate concept, not
+one long combined phrase. For example, "packet filtering, address translation and
+port forwarding" names three distinct mechanisms: extract "packet filtering",
+"address translation", and "port forwarding" as three concepts, not one.
 
@@ -16,3 +37,3 @@
 
-Candidate terms noticed in this section (from noun-chunk statistics — use these as
+Candidate terms noticed in this section (from noun-chunk statistics -- use these as
 hints, but don't be limited to them; also don't include every one if it isn't
@@ -25,3 +46,4 @@
 For each concept you find, give:
-- canonical_name: the concept's name as it best appears in the text.
+- canonical_name: the concept's name as it best appears in the text -- a term, not a
+  description (see above).
 - node_type: one of Protocol, Mechanism, Component, DataUnit, Parameter, Property,
```

### One real relation call, fully rendered (replayed from cache)

The pipeline classifies a pair in up to three separate strong-tier calls (family -> relation+direction -> qualifiers). **Note on how the menu really works** (this differs from a flat 'choice_set' menu): the *family* menu offers each family plus `no_relation` and `other`; the *relation* menu lists only the relations in the chosen family plus `other`; **direction (`forward`/`reversed`) is a separate structured field, not a menu option.** The reversed option text appears in the flat CR-001 `choice_set` below, which is shown for reference and is **not** what was sent to the model. **Also note:** the relation-step option lines contain the template text with literal `{X}` / `{Y}` placeholders (e.g. `"{X} is a kind of {Y}"`) - the model was NOT shown option sentences filled with the two concepts' names. (The 'Step 2' panel in the HTML report shows filled-in sentences; that is a presentation choice and differs from the real prompt.)

Pair `RP-2-problem-connecting-to-a-network-0` (network / link); the model judged the relation reversed (Y -> X).

**Call: `relation_family` - prompt v2, tier strong, model `gpt-6-sol` (cache hit, replayed)**

Rendered prompt sent:
```
You are checking whether a sentence states a relation between two concepts, and if
so, which broad family it belongs to.

Concept X: network
Concept Y: link

Sentence:
In Chapter 1 we saw that networks consist of links interconnecting nodes.

Choose exactly one family that best describes a relation the sentence actually states
between X and Y (in either direction):
- mechanism_process: Mechanism & process — SBF behaviour; mechanistic reasoning; PDTB Temporal
- cause_effect: Cause & quantitative effect — PDTB Contingency.Cause; SemEval Cause-Effect; Qualitative Process Theory
- function_means: Function & means — Qualia telic; SBF function; ConceptNet UsedFor
- dependency: Dependency & constraint — PDTB Condition; ConceptNet HasPrerequisite
- comparison: Comparison — Chaffin & Herrmann contrast family; PDTB Comparison
- classification_structure: Classification & structure — WordNet; Winston et al.; qualia formal/constitutive; SBF structure
- no_relation: nothing meaningful is stated between these two concepts here
- other: a real relation is stated, but it doesn't fit any family above

If the sentence doesn't relate these two concepts to each other at all, choose
no_relation. If it does relate them but no family above fits, choose other.
```

Structured output:
```json
{
  "family": "classification_structure",
  "reason": "The sentence states that networks consist of links, a part–whole structural relation."
}
```

**Call: `relation_choice` - prompt v2, tier strong, model `gpt-6-sol` (cache hit, replayed)**

Rendered prompt sent:
```
You are picking the exact relation a sentence states between two concepts, within
the "classification_structure" family already identified for this pair.

Concept X: network
Concept Y: link

Sentence:
In Chapter 1 we saw that networks consist of links interconnecting nodes.

Options:
- is_a: Source is a kind/subtype of target. e.g. "{X} is a kind of {Y}" [not part_of ("extension header part_of IPv6 packet" — a component, not a subtype); not has_property ("Manchester encoding has_property self-clocking" — an attribute, not a category)]
- part_of: Source is a part of target. REQUIRED qualifier part_type: component (field/module of a structured whole), member (element of a collection/group), phase (step/stage of a process). e.g. "{X} is part of {Y}" [not is_a ("CSMA/CD is_a MAC protocol" — a subtype, not a part); not precedes ("slow start precedes congestion avoidance" — ordering between phases, not membership)]
- has_property: Source has the characteristic, behaviour, value or constraint named by target. e.g. "{X} has the property {Y}" [not has_purpose ("carrier extension has_purpose collision detection" — a designed goal, not an attribute); not increases ("frame bursting increases efficiency" — an effect on a quantity, not a static attribute)]
- other: none of the above fit, even though the pair is in this family

Pick the one relation the sentence actually states. direction is "forward" if the
relation reads X -> Y as written (e.g. "performs" meaning X performs Y), or
"reversed" if it actually reads Y -> X; direction is ignored (send "forward") for
non-directional relations or "other".

evidence_quote: an EXACT substring of the sentence above (copy character-for-
character) that states this relation.
statement: a one-sentence paraphrase of the relation in your own words, naming both
concepts.
```

Structured output:
```json
{
  "relation": "part_of",
  "direction": "reversed",
  "evidence_quote": "networks consist of links",
  "statement": "Links are components of networks."
}
```

**Call: `relation_qualifiers` - prompt v2, tier strong, model `gpt-6-sol` (cache hit, replayed)**

Rendered prompt sent:
```
The relation "part_of" was just identified between two concepts in this sentence:

Concept X: network
Concept Y: link
Relation statement: Links are components of networks.

Sentence:
In Chapter 1 we saw that networks consist of links interconnecting nodes.

Give:
- polarity: "affirmed" (the sentence states this relation holds) or "negated" (the
  sentence explicitly denies it, e.g. "does not", "is not").
- modality: "necessary", "always", "typically", "possible", or "never" — how strongly
  the sentence asserts the relation holds.
- conditions: any conditions under which the relation holds, as short phrases from
  the sentence (empty list if unconditional).
- part_type: if the relation is about parts and wholes, one of "component",
  "member", "phase" describing the part-whole type; otherwise null.
- dimension: if the relation is a comparison, a short phrase naming what differs;
  otherwise null.
- surface_phrase: an EXACT substring of the sentence above (copy character-for-
  character) — the actual linking words connecting X and Y (e.g. "triggers",
  "is a type of", "does not require").
```

Structured output:
```json
{
  "polarity": "affirmed",
  "modality": "necessary",
  "conditions": [],
  "part_type": "component",
  "dimension": null,
  "surface_phrase": "consist of"
}
```

Reference only - the flat CR-001 `choice_set` for the chosen family (contains the explicit reversed, no-relation and other options; not sent by the pipeline):

```
[relation] network is a kind of link
[relation reversed] link is a kind of network
[relation] network is part of link
[relation reversed] link is part of network
[relation] network has the property link
[relation reversed] link has the property network
[no_relation] No relation is stated between these.
[other] Other (not in this list) — give the phrase.
```

## 2. Node examples (P&D ch2-3)

Selection: seeded random draw (seed 11) - 5 `defined` (with a definition), 4 `used`, 3 `mentioned`, spread over ch2 and ch3. 'Verified' = the evidence quote is an exact substring of the section text after whitespace normalisation.

| # | concept | role | section | definition | evidence quote (verified) | aliases |
|---|---|---|---|---|---|---|
| 1 | interleaving | defined | 2.3 (ch2) | Transmitting a byte from each constituent frame in turn to keep their bytes evenly paced. | "a byte from the first frame is transmitted, then a byte from the second frame is transmitted, and so on." (yes) | (none) |
| 2 | Version field | defined | 3.3 (ch3) | The field that specifies the version of IP. | "The Version field specifies the version of IP." (yes) | (none) |
| 3 | relay agent | defined | 3.3 (ch3) | A node configured with the DHCP server's IP address that forwards discovery messages to that server and returns its response to the client. | "DHCP uses the concept of a relay agent. There is at least one relay agent on each network, and it is configured with just one piece of information: the IP address of the DHCP server." (yes) | (none) |
| 4 | Broadband Network Gateway (BNG) | defined | 2.8 (ch2) | Telco equipment that meters Internet traffic for billing and serves as the gateway between the access network and the Internet. | "the BNG (Broadband Network Gateway) is a piece of Telco equipment that, among many other things, meters Internet traffic for the sake of billing." (yes) | (none) |
| 5 | routing | defined | 3.1 (ch3) | The harder problem of creating forwarding tables in large, complex networks with dynamically changing topologies and multiple paths between destinations. | "That harder problem is known as routing" (yes) | (none) |
| 6 | MAC address | used | 3.2 (ch3) | (none) | "the source media access control (MAC) address contained in the packet" (yes) | (none) |
| 7 | switch | used | 2-perspective-race-to-the-edge (ch2) | (none) | "servers, switches, and access devices" (yes) | (none) |
| 8 | Ethernet address | used | 3.1 (ch3) | (none) | "the 48-bit address used for Ethernet." (yes) | (none) |
| 9 | Round-trip time | used | 2.5 (ch2) | (none) | "a 45-ms round-trip time" (yes) | round-trip time |
| 10 | Address Resolution Protocol | mentioned | 3.4 (ch3) | (none) | "the last piece of information is provided by the Address Resolution Protocol." (yes) | (none) |
| 11 | electromagnetic radiation | mentioned | 2-problem-connecting-to-a-network (ch2) | (none) | "through which electromagnetic radiation (e.g., radio waves) can be transmitted" (yes) | (none) |
| 12 | Internet | mentioned | 3-problem-not-all-networks-are-directly-connected (ch3) | (none) | "the core idea of the Internet" (yes) | public Internet |

### Three merged concepts (before / after), all owner-marked `ok`

- **Before:** two separate mentions - `IP` and `Internet protocol` (section 3-problem-not-all-networks-are-directly-connected). **After:** one node `Internet protocol` with aliases ['Internet Protocol', 'IP'].
  - model reason: "The evidence explicitly expands IP as Internet Protocol, matching candidate 0; the capitalization difference does not change the protocol's identity."
  - evidence quote: "the Internet Protocol (IP)"
- **Before:** two separate mentions - `public Internet` and `Internet` (section 2-perspective-race-to-the-edge). **After:** one node `Internet` with aliases ['public Internet'].
  - model reason: "“Public Internet” refers to the Internet; “public” emphasizes its accessibility rather than identifying a distinct kind or version."
  - evidence quote: "connect it to the public Internet"
- **Before:** two separate mentions - `Non-Return-to-Zero (NRZ)` and `non-return to zero (NRZ)` (section 2.3). **After:** one node `non-return to zero (NRZ)` with aliases ['Non-Return-to-Zero (NRZ)'].
  - model reason: "Both name NRZ and define it as encoding 1 with a high signal and 0 with a low signal."
  - evidence quote: "the simple encoding described in the previous section where 1s are high and 0s are low."

### Three taxonomy candidates (never merged; logged for a later is_a pass). Totals: 155 narrower, 35 broader.

- `L3 router` is **narrower** than `router` (section 3.5): "An L3 router specifies a router operating at the network layer, making it more specific than the unqualified concept 'router'."
- `static routing` is **narrower** than `routing` (section 3.4): "Static routing is a specific approach to routing, not an interchangeable name for routing in general."
- `protocol` is **broader** than `Internet protocol` (section 3-problem-not-all-networks-are-directly-connected): "The mention uses “protocol” generically; Internet protocol is a specific protocol, not an interchangeable name for protocols in general."

## 3. Owner spot-check (n=30)

Marks (owner): {'correct': 23, 'incorrect': 5, 'wrong-direction': 2}. The `direction` column is the model's direction flag on the pair as enumerated (`reversed` = it swapped subject/object); subject/relation/object below are already in the model's chosen direction. Marks normalised: `ok`/`correct` -> correct; `wrong-directon` (typo) / `wrong-direction` -> wrong-direction.

| id | source sentence | subject | relation | object | direction | family | owner mark | owner note |
|---|---|---|---|---|---|---|---|---|
| 1 | Before getting into the details of routing, we need to remind ourselves of the key question we should be asking anytime we try to build a mechanism for the Internet: “Does this solution scale?” The answer for the algorithms and protocols described in this section is “not so much.” They are designed for networks of fairly modest size—up to a few hundred nodes, in practice. | routing | requires | node | reversed | dependency | correct |  |
| 2 | On an Ethernet, for example, a frame carrying up to 12,000 bits (1500 bytes) of data requires only a 32-bit CRC code, or as it is commonly expressed, uses CRC-32. | Ethernet | requires | CRC | forward | dependency | correct |  |
| 3 | We also introduced the “cloud” abstraction to represent a network without revealing all of its internal complexities. | cloud | has_purpose | network | reversed | function_means | correct |  |
| 4 | This function is sometimes referred to as either switching or forwarding, and in terms of the Open Systems Interconnection (OSI) architecture, it is considered a function of the network layer. | switch | equivalent_to | forwarding | forward | comparison | incorrect |  |
| 5 | The medium may be a length of wire, a piece of optical fiber, or some less tangible medium (such as air) through which electromagnetic radiation (e.g., radio waves) can be transmitted. | wire | contrasts_with | air | forward | comparison | incorrect |  |
| 6 | If the receiver’s clock is even slightly faster or slower than the sender’s clock, then it does not correctly decode the signal. | signal | requires | clock | forward | dependency | wrong-direction |  |
| 7 | The first step in turning nodes and links into usable building blocks is to understand how to connect them in such a way that bits can be transmitted from one node to the other. | link | has_purpose | bit | forward | function_means | correct |  |
| 8 | This problem is addressed by having the switches run a distributed spanning tree algorithm. | switch | performs | Spanning tree | forward | mechanism_process | correct |  |
| 9 | In the case of the Manchester encoding, the bit rate is half the baud rate, so the encoding is considered only 50% efficient. | encoding | increases | baud rate | forward | cause_effect | correct |  |
| 10 | Add them together using 16-bit ones’ complement arithmetic (explained below) and then take the ones’ complement of the result. | ones’ complement arithmetic | has_property | bit | reversed | classification_structure | wrong-direction |  |
| 11 | As we start to explore how softwarization is transforming the network, we should recognize that it is the access network that connects homes, businesses, and mobile users to the Internet that is undergoing the most radical change. | softwarization | causes | network | reversed | cause_effect | correct |  |
| 12 | The second problem is that frequent transitions from high to low and vice versa are necessary to enable clock recovery. | clock | requires | transition | forward | dependency | correct |  |
| 13 | Specifically, the protocols described in this section are collectively known as intradomain routing protocols, or interior gateway protocols (IGPs). | routing protocol | has_purpose | routing | reversed | function_means | correct |  |
| 14 | Today, the industry is at 4G (supporting data rates typically measured in the few megabits per second) and is in the process of transitioning to 5G (with the promise of a tenfold increase in data rates). | 4G | precedes | 5G | forward | mechanism_process | correct |  |
| 15 | The medium may be a length of wire, a piece of optical fiber, or some less tangible medium (such as air) through which electromagnetic radiation (e.g., radio waves) can be transmitted. | wire | has_purpose | electromagnetic radiation | forward | function_means | correct |  |
| 16 | Their goal is to enable new classes of edge services—e.g., Public Safety, Autonomous Vehicles, Automated Factories, Internet-of-Things (IoT), Immersive User Interfaces—that benefit from low latency connectivity to end users, and more importantly, to the increasing number of devices those users surround themselves with. | latency | decreases | edge | forward | cause_effect | correct |  |
| 17 | In the case of the Manchester encoding, the bit rate is half the baud rate, so the encoding is considered only 50% efficient. | bit | contrasts_with | baud rate | forward | comparison | incorrect |  |
| 18 | Once we interconnect a whole lot of links and networks with switches and routers, there are likely to be many different possible ways to get from one point to another. | network | increases | path | forward | cause_effect | correct |  |
| 19 | Recall from Chapter 1 that we are focusing on packet-switched networks, which means that blocks of data (called frames at this level), not bit streams, are exchanged between nodes. | bit | contrasts_with | frame | forward | comparison | incorrect |  |
| 20 | Specifically, IP addresses consist of two parts, usually referred to as a network part and a host part. | host | part_of | IP address | forward | classification_structure | correct |  |
| 21 | The sender maintains three variables: The send window size, denoted SWS, gives the upper bound on the number of outstanding (unacknowledged) frames that the sender can transmit; LAR denotes the sequence number of the last acknowledgment received; and LFS denotes the sequence number of the last frame sent. | frame | requires | SWS | forward | dependency | correct |  |
| 22 | As we start to explore how softwarization is transforming the network, we should recognize that it is the access network that connects homes, businesses, and mobile users to the Internet that is undergoing the most radical change. | softwarization | causes | last-mile link | reversed | cause_effect | correct |  |
| 23 | It turns out that the sending window size can be no more than half as big as the number of available sequence numbers when RWS = SWS, or stated more precisely, Intuitively, what this is saying is that the sliding window protocol alternates between the two halves of the sequence number space, just as stop-and-wait alternates between sequence numbers 0 and 1. | sliding window protocol | is_a | protocol | reversed | classification_structure | correct |  |
| 24 | This is all part of the growing trend to move functionality out of the datacenter and closer to the network edge, a trend that puts cloud providers and network operators on a collision course. | network edge | is_a | edge | forward | classification_structure | correct |  |
| 25 | The main shortcoming of the stop-and-wait algorithm is that it allows the sender to have only one outstanding frame on the link at a time, and this may be far below the link’s capacity. | Outstanding frame | is_a | frame | reversed | classification_structure | correct |  |
| 26 | The medium may be a length of wire, a piece of optical fiber, or some less tangible medium (such as air) through which electromagnetic radiation (e.g., radio waves) can be transmitted. | optical fiber | contrasts_with | air | forward | comparison | correct |  |
| 27 | Like wired links, issues of bit errors are of great concern—typically even more so due to the unpredictable noise environment of most wireless links. | wire | contrasts_with | wireless link | forward | comparison | correct |  |
| 28 | So the question to ask is “How does the receiver know where each frame starts and ends?” We consider this question for the lowest-speed SONET link, which is known as STS-1 and runs at 51.84 Mbps. | link | has_property | SONET | forward | classification_structure | incorrect |  |
| 29 | This section outlines the basic CRC algorithm, but before discussing that approach, we first describe the simpler checksum scheme used by several Internet protocols. | Internet | uses | checksum | forward | function_means | correct |  |
| 30 | - The remainder obtained when B(x) is divided by C(x) is obtained by performing the exclusive OR (XOR) operation on each pair of matching coefficients. | exclusive OR (XOR) | has_purpose | remainder | forward | function_means | correct |  |

### Five best 'correct' examples for slides

Chosen by reading, not by a formula: owner-marked correct, one clear sentence, subject and object literally in it, relation a plain reading of the wording, and a spread of families (classification, dependency, mechanism x2, comparison). Substitute your own eye.

- **#20** (classification_structure) - "Specifically, IP addresses consist of two parts, usually referred to as a network part and a host part." -> **host - part_of -> IP address** (model direction flag: forward).
- **#2** (dependency) - "On an Ethernet, for example, a frame carrying up to 12,000 bits (1500 bytes) of data requires only a 32-bit CRC code, or as it is commonly expressed, uses CRC-32." -> **Ethernet - requires -> CRC** (model direction flag: forward).
- **#14** (mechanism_process) - "Today, the industry is at 4G (supporting data rates typically measured in the few megabits per second) and is in the process of transitioning to 5G (with the promise of a tenfold increase in data rates)." -> **4G - precedes -> 5G** (model direction flag: forward).
- **#8** (mechanism_process) - "This problem is addressed by having the switches run a distributed spanning tree algorithm." -> **switch - performs -> Spanning tree** (model direction flag: forward).
- **#27** (comparison) - "Like wired links, issues of bit errors are of great concern—typically even more so due to the unpredictable noise environment of most wireless links." -> **wire - contrasts_with -> wireless link** (model direction flag: forward).

**Owner-marked correct but I would not put on a slide** (debatable on a plain reading; the marks are yours, this is only a heads-up): #3 cloud -has_purpose-> network, #9 encoding -increases-> baud rate (the sentence says bit rate is half the baud rate), #16 latency -decreases-> edge, #21 frame -requires-> SWS, #26 optical fiber -contrasts_with-> air (compare #5, wire contrasts_with air, which you marked incorrect on the same sentence).


### The seven failures

| id | mark | source sentence | model triple | owner note |
|---|---|---|---|---|
| 4 | incorrect (`incorrect`) | This function is sometimes referred to as either switching or forwarding, and in terms of the Open Systems Interconnection (OSI) architecture, it is considered a function of the network layer. | switch -[equivalent_to]-> forwarding (comparison) | (no note) |
| 5 | incorrect (`incorrect`) | The medium may be a length of wire, a piece of optical fiber, or some less tangible medium (such as air) through which electromagnetic radiation (e.g., radio waves) can be transmitted. | wire -[contrasts_with]-> air (comparison) | (no note) |
| 6 | wrong-direction (`wrong-directon`) | If the receiver’s clock is even slightly faster or slower than the sender’s clock, then it does not correctly decode the signal. | signal -[requires]-> clock (dependency) | (no note) |
| 10 | wrong-direction (`wrong-direction`) | Add them together using 16-bit ones’ complement arithmetic (explained below) and then take the ones’ complement of the result. | ones’ complement arithmetic -[has_property]-> bit (classification_structure) | (no note) |
| 17 | incorrect (`incorrect`) | In the case of the Manchester encoding, the bit rate is half the baud rate, so the encoding is considered only 50% efficient. | bit -[contrasts_with]-> baud rate (comparison) | (no note) |
| 19 | incorrect (`incorrect`) | Recall from Chapter 1 that we are focusing on packet-switched networks, which means that blocks of data (called frames at this level), not bit streams, are exchanged between nodes. | bit -[contrasts_with]-> frame (comparison) | (no note) |
| 28 | incorrect (`incorrect`) | So the question to ask is “How does the receiver know where each frame starts and ends?” We consider this question for the lowest-speed SONET link, which is known as STS-1 and runs at 51.84 Mbps. | link -[has_property]-> SONET (classification_structure) | (no note) |

## 4. IIR error examples (prompt v2)

Causes are the rule-based labels computed by `expert_kg/face_eval.py` from strings alone: over-specific / over-general (a prediction contains, or is contained in, a gold term), unigram, long phrase (3+ words), description-like (4+ words), mentioned-only, single word, otherwise `other`. **'Generic term' and 'missed definition' are not computed** - they can't be detected from strings; treat `other` honestly as 'not explained by a simple rule'. Examples are drawn round-robin across causes with a fixed seed. Reminder: the test split is for reporting only - reading these is descriptive, and no prompt was or will be changed from them.

### test (corrected text) - run `iirtest_v2`

Lenient micro P/R/F1 0.720/0.469/0.568; exact micro F1 0.474. Cause counts over ALL errors - false positives: {'other': 45, 'over-specific (contains a gold term)': 27, 'single word': 17, 'mentioned only': 12, 'over-general (inside a gold term)': 7}; false negatives: {'other': 103, 'unigram': 84, 'prediction is more specific than the gold term': 51, 'long phrase (3+ words)': 43, 'prediction is more general than the gold term': 34}.

**False positives (model said concept, gold did not)**

| section | concept (model output) | likely cause |
|---|---|---|
| iir_4_4 | sequential read | other |
| iir_4_2 | term frequency | over-specific (contains a gold term) |
| iir_4_3 | compression | single word |
| iir_9_2 | narrower term | mentioned only |
| iir_6_1 | Boolean retrieval | over-general (inside a gold term) |
| iir_6_3 | Euclidean normalization | other |
| iir_4_1 | disk access | over-specific (contains a gold term) |
| iir_4_1 | indexer | single word |
| iir_6 | language | mentioned only |
| iir_6_2 | vector | over-general (inside a gold term) |

**False negatives (gold concept the model missed)**

(Omitted from the committed copy: the missed terms are FACE gold annotations and the context sentences are IIR text (© Cambridge University Press); both are kept out of git. The full version is in `reports/talking_points_facts.local.md`, which is gitignored.)

### dev - run `iirdev_v2`

Lenient micro P/R/F1 0.673/0.561/0.612; exact micro F1 0.486. Cause counts over ALL errors - false positives: {'other': 58, 'single word': 28, 'over-specific (contains a gold term)': 26, 'mentioned only': 16, 'over-general (inside a gold term)': 4}; false negatives: {'other': 72, 'unigram': 58, 'prediction is more specific than the gold term': 39, 'prediction is more general than the gold term': 36, 'long phrase (3+ words)': 8}.

**False positives (model said concept, gold did not)**

| section | concept (model output) | likely cause |
|---|---|---|
| iir_2_4 | compound indexing scheme | other |
| iir_1_3 | hashtable | single word |
| iir_3_3 | weighted edit distance | over-specific (contains a gold term) |
| iir_2_1 | document type | mentioned only |
| iir_1_1 | postings | over-general (inside a gold term) |
| iir_1_2 | contiguous memory | other |
| iir_3_2 | suffix | single word |
| iir_2_3 | index update | over-specific (contains a gold term) |
| iir_1_3 | in-memory data | mentioned only |
| iir_3_1 | wildcard | over-general (inside a gold term) |

**False negatives (gold concept the model missed)**

(Omitted from the committed copy: the missed terms are FACE gold annotations and the context sentences are IIR text (© Cambridge University Press); both are kept out of git. The full version is in `reports/talking_points_facts.local.md`, which is gitignored.)

## 5. The 114 `relation_other` pairs (cache replay, $0)

`relation_other` = the family step picked a family, then the relation step answered `other` (none of that family's relations fit). The relation schema has **no free-text 'other phrase' field**; the closest recoverable text is the model's one-sentence `statement` (plus its `evidence_quote`) from that call, and the family step's `reason`. Those are what is shown.

Family the model picked before answering `other`: {'dependency': 8, 'function_means': 8, 'mechanism_process': 56, 'classification_structure': 32, 'comparison': 5, 'cause_effect': 5}.

### Themes (keyword grouping of the model's `statement`, first match wins; heuristic, registry unchanged)

| theme | count of 114 |
|---|---|
| Actor -> thing handled ("host sends a packet", "switch forwards frames"): Y is an object, not an action, so performs/triggers/precedes do not fit | 27 |
| Topology / connectivity ("interconnects", "connects", "runs over") | 22 |
| Uncategorised | 21 |
| Encoding, spreading or encapsulating a signal or frame | 13 |
| Possession, naming or identification ("has an address", "identified by", "given its own") | 9 |
| Sentence lists or scopes the two concepts without relating them ("listed together", "described as", "means") | 8 |
| Absence or limit of a need ("X need not / does not require Y", "independent of") - a negated dependency the model would not map | 8 |
| Trend / conflict between parties ("collision course", "moving toward") | 6 |

### 15 examples (round-robin over families, seed 9)

| family | X / Y | sentence | model statement | theme |
|---|---|---|---|---|
| mechanism_process | host / Internet protocol | One way to think of IP is that it runs on all the nodes (both hosts and routers) in a collection of networks and defines the infrastructure that allows these nodes and networks to function as a single logical internetwork. | Internet protocol runs on hosts; the sentence does not state that either concept performs, triggers, or precedes the other. | Topology / connectivity ("interconnects", "connects", "runs over") |
| classification_structure | frame / protocol | 2.3.1 Byte-Oriented Protocols (PPP) One of the oldest approaches to framing—it has its roots in connecting terminals to mainframes—is to view each frame as a collection of bytes (characters) rather than a collection of bits. | The sentence discusses frames in the context of byte-oriented protocols but states no classification or structural relation between a frame and a protocol. | Uncategorised |
| dependency | network / IP address | IP addresses are discussed in a later section—for now, the important thing to know is that IP defines its own global address space, independent of whatever physical networks it runs over. | IP addresses belong to a global address space that is independent of the physical networks IP runs over. | Absence or limit of a need ("X need not / does not require Y", "independent of") - a negated dependency the model would not map |
| function_means | link / switch | Devices that interconnect links of the same type are often called switches, or sometimes Layer 2 (L2) switches. | A switch is a device that interconnects links; the sentence does not say that a link is its purpose or a means it uses. | Topology / connectivity ("interconnects", "connects", "runs over") |
| comparison | air / Ethernet | Like the Aloha network, the fundamental problem faced by the Ethernet is how to mediate access to a shared medium fairly and efficiently (in Aloha, the medium was the atmosphere, while in the Ethernet the medium was originally a coax cable). | Air was Aloha's medium, whereas Ethernet originally used coax cable; the sentence does not directly compare air with Ethernet. | Uncategorised |
| cause_effect | network operator / datacenter | This is all part of the growing trend to move functionality out of the datacenter and closer to the network edge, a trend that puts cloud providers and network operators on a collision course. | The sentence says that moving functionality out of the datacenter brings network operators into conflict with cloud providers, not that network operators cause or change datacenters. | Trend / conflict between parties ("collision course", "moving toward") |
| mechanism_process | signal / frequency | The idea behind spread spectrum is to spread the signal over a wider frequency band, so as to minimize the impact of interference from other devices. | The signal is spread over a wider frequency band; neither concept performs, triggers, or precedes the other. | Encoding, spreading or encapsulating a signal or frame |
| classification_structure | Internet Service Provider / PON | PON adopts a point-to-multipoint design, which means the network is structured as a tree, with a single point starting in the ISP’s network and then fanning out to reach up to 1024 homes. | PON starts at a point in the Internet Service Provider’s network and fans out to homes; the sentence does not say that either concept is a subtype, part, or property of the other. | Topology / connectivity ("interconnects", "connects", "runs over") |
| dependency | host / switch | A star topology has several attractive properties: - Even though a switch has a fixed number of inputs and outputs, which limits the number of hosts that can be connected to a single switch, large networks can be built by interconnecting a number of switches. | A switch’s fixed number of inputs and outputs limits how many hosts can connect to it, but the sentence does not say either requires the other. | Absence or limit of a need ("X need not / does not require Y", "independent of") - a negated dependency the model would not map |
| function_means | packet / switch | The core job of a switch is to take packets that arrive on an input and forward (or switch) them to the right output so that they will reach their appropriate destination. | A switch forwards packets; the packets are what it handles, not a means it uses or a goal it exists to achieve. | Sentence lists or scopes the two concepts without relating them ("listed together", "described as", "means") |
| comparison | wire / Ethernet | Sometimes this link will be a wireless (Wi-Fi) link in a coffee shop; sometimes it’s an Ethernet link in an office building or university; sometimes it is a smartphone connected to a cellular network; for an increasingly large slice of the population it is a fiber optic link provided by an ISP; and many others use some sort of copper wire or cable to connect. | The sentence lists Ethernet links and copper wire as ways to connect, without stating that Ethernet and wire are equivalent or inherently different. | Topology / connectivity ("interconnects", "connects", "runs over") |
| cause_effect | network operator / edge | This is all part of the growing trend to move functionality out of the datacenter and closer to the network edge, a trend that puts cloud providers and network operators on a collision course. | Moving functionality toward the network edge puts network operators on a collision course with cloud providers, but the sentence states no causal relation between network operators and the edge. | Trend / conflict between parties ("collision course", "moving toward") |
| mechanism_process | encoding / clock | Intuitively, the clock recovery problem is that both the encoding and decoding processes are driven by a clock—every clock cycle the sender transmits a bit and the receiver recovers a bit. | The encoding process is driven by a clock. | Encoding, spreading or encapsulating a signal or frame |
| classification_structure | Ethernet / Ethernet address | Addresses Each host on an Ethernet—in fact, every Ethernet host in the world—has a unique Ethernet address. | An Ethernet host has an Ethernet address; the sentence does not state a direct classification or part–whole relation between Ethernet and Ethernet address. | Possession, naming or identification ("has an address", "identified by", "given its own") |
| dependency | spread spectrum / spectrum | One idea that shows up a lot when spectrum is shared among many devices and applications is spread spectrum. | Spread spectrum is an idea often encountered when spectrum is shared among many devices and applications, but the sentence states no strict dependency. | Absence or limit of a need ("X need not / does not require Y", "independent of") - a negated dependency the model would not map |

## 6. Growth facts

Manifests (as stored after the direction-fix rebuild):

```json
{
  "2": {
    "run_id": "pdcanon2_30e2b4f9",
    "chapter_num": 2,
    "node_count": 419,
    "edge_count": 87,
    "merge_count": 106,
    "rejected_count": 0,
    "prerequisite_candidate_count": 17,
    "forward_reference_count": 25
  },
  "3": {
    "run_id": "pdcanon2_30e2b4f9",
    "chapter_num": 3,
    "node_count": 352,
    "edge_count": 34,
    "merge_count": 101,
    "rejected_count": 0,
    "prerequisite_candidate_count": 28,
    "forward_reference_count": 3
  }
}
```

**Definition of a cross-chapter edge.** In `SnapshotEdge`, `source_chapter` / `target_chapter` are the chapters in which the edge's two endpoint concepts were *first mentioned by concept extraction* (`concept_first_chapter`). An edge is cross-chapter when those two differ. An edge belongs to the snapshot of the chapter whose section its sentence came from. It is NOT 'an edge whose sentence spans two chapters' (sentences are single-section).

- **ch2 snapshot:** 87 edges, **13 cross-chapter**; endpoint first-chapter pairs (source, target): {(2, 2): 72, (2, 3): 10, (3, 2): 3, (3, 3): 2}.
- **ch3 snapshot:** 34 edges, **22 cross-chapter**; endpoint first-chapter pairs (source, target): {(2, 2): 6, (2, 3): 9, (3, 3): 6, (3, 2): 13}.

Why does a chapter-2 sentence produce cross-chapter edges at all? Candidate pairs are found by matching concept *names* inside a sentence (`relations.find_candidate_pairs`), independent of whether extraction had already 'introduced' the concept in that chapter. A ch2 sentence can therefore contain a concept that extraction first recorded in ch3, giving an edge in the ch2 snapshot whose endpoint is 'first introduced' in ch3. (Consequence for the time-bar graph: such an edge only appears once its ch3 endpoint appears.)

Five ch2-snapshot cross-chapter edges (source chapter -> target chapter):

- byte-oriented protocol (first ch2) -[is_a]-> protocol (first ch3), section 2.3
- Link-level protocol (first ch2) -[is_a]-> protocol (first ch3), section 2.4
- protocol (first ch3) -[uses]-> checksum (first ch2), section 2.4
- frame (first ch2) -[is_a]-> header (first ch3), section 2.5
- SWP (first ch2) -[is_a]-> protocol (first ch3), section 2.5

**Forward references** = a concept is `used` in a section that comes *before* the section where it is `defined` (book order), from `prerequisites.find_forward_references`. Recomputed now: {2: 25, 3: 3} (manifests say ch2 25, ch3 3).

- **ch2:** 25 forward references; 11 are defined later in the same chapter, 14 in a later chapter. Used-in sections: {'2-problem-connecting-to-a-network': 2, '2.1': 8, '2.8': 1, '2-perspective-race-to-the-edge': 3, '2.7': 2, '2.3': 3, '2.5': 3, '2.6': 1, '2.4': 2}.
  - `network` used in `2-problem-connecting-to-a-network` (order 10), defined in `3.3` (order 23).
  - `link` used in `2-problem-connecting-to-a-network` (order 10), defined in `2.1` (order 11).
  - `wireless link` used in `2.1` (order 11), defined in `2.7` (order 17).
  - `Ethernet` used in `2.1` (order 11), defined in `2.6` (order 16).
  - `Wi-Fi` used in `2.1` (order 11), defined in `2.7` (order 17).
  - `router` used in `2.1` (order 11), defined in `3-problem-not-all-networks-are-directly-connected` (order 20).
- **ch3:** 3 forward references; 3 are defined later in the same chapter, 0 in a later chapter. Used-in sections: {'3.1': 2, '3.5': 1}.
  - `latency` used in `3.1` (order 21), defined in `3.4` (order 24).
  - `routing table` used in `3.1` (order 21), defined in `3.4` (order 24).
  - `virtual machine` used in `3.5` (order 25), defined in `3-perspective-virtual-networks-all-the-way-down` (order 26).

**Why ch2 has 25 forward references and ch3 has 3 (what the data shows):**

1. A forward reference needs a `used` mention *before* a `defined` mention in book order, both inside the processed slice (ch2-3). Of the 25 in ch2, 14 have their `defined` mention in **ch3**, 11 later in ch2.
2. Many of the ch3 'definitions' are not first introductions. Example: `network` is `used` in ch2 (`2-problem-connecting-to-a-network`) but its `defined` mention is in 3.3, whose evidence is: "we use network to mean either a directly connected or a switched network of the kind described in the previous section and the previous chapter. Such a network uses one technology" - a local re-definition ('we use network to mean ...'), while the concept was really introduced in ch1, which is outside the slice. The same pattern likely explains `router` (defined mention in the ch3 opening section). This is my reading of those examples, not something I tested for every one of the 14.
3. The ch2 count is concentrated in a few sections: [('2.1', 8), ('2-perspective-race-to-the-edge', 3), ('2.3', 3)]. Section 2.1 (Technology Landscape) is a survey that uses many terms (wireless link, Ethernet, Wi-Fi, ...) that later sections (2.6, 2.7) define properly.
4. By ch3 nearly everything it uses was already defined in ch2 (backward references, which are normal and counted as prerequisite candidates instead), leaving only 3 forward references, all within ch3 (latency, routing table, virtual machine).
So the 25-vs-3 gap reflects book order plus slice boundaries plus how the extractor tags `defined`, not a difference in how well the two chapters were processed.

## 7. Project facts

### Git log (58 commits, oldest first)

```
2026-09-28 106165e M0: repo scaffold, LLM wrapper (cache/mock/client), CLI stubs
2026-09-28 9f17d59 M1 (up to human step): SAF ingestion, textbook parse, EDA, coverage suggestions
2026-09-28 3f321d6 M1: fix coverage-guess prompt truncation, re-run for all 31 questions
2026-09-28 3c6b6e0 M2: Pydantic schemas, relation registry logic, cumap gold validate
2026-09-28 54c24c3 M1: record human-approved pilot questions
2026-09-28 80cd1e4 M3 (WIP, paused for CR-001): sampling, LLM drafting, Streamlit gold editor
2026-09-28 52fb2c7 CR-001: registry v1 (§3)
2026-09-28 18e0885 CR-001: schema changes (§4)
2026-09-28 357e5ac CR-001: version-aware validator (§5)
2026-09-28 5b13e87 CR-001: gold migration tool (§6) — STOP 1
2026-09-28 c0d27e8 CR-001: v2 prompts for suggest-expert/suggest-student (§7.2)
2026-09-28 eb840ad CR-001: gold editor v1 fields + chain-links panel (§7.1)
2026-09-28 23ffa72 CR-001: relation-agreement sampler + mismatch report extension (§7.3-7.4)
2026-09-28 e291b17 CR-001: LLM client tiers, escalation, batch-key guarantee (§8)
2026-09-28 7857b10 CR-001: documentation updates (§9)
2026-09-28 3a4ad06 CR-001: acceptance checks (§10) — final step, CR-001 complete
2026-09-28 e81a076 Scope decision: expert knowledge graph only, student-side deferred
2026-09-28 7143095 CR-005: start at STOP 1 (plan + dry-run cost estimate)
2026-09-29 cda6cae CR-005: iir_face loader (CR-003 §3, iir_face only)
2026-09-29 5644683 CR-005: M5 subset pipeline pieces (§2)
2026-09-29 2b42fae CR-005: redo cost estimate with tier pricing (§2 step 3)
2026-09-29 b924dbb CR-005: calibration run findings, stopped at Step 5's line (§2 step 4)
2026-09-29 619b7c9 CR-005: scope-reduction decision + pipeline orchestration with live budget cap
2026-09-29 4c16ee9 CR-005: IIR-dev run stopped at $14.03, found the real cause (§2 step 5)
2026-09-29 b58e219 CR-005: §9 amendment -- scope split, live budget cap, run-level pair dedup (§9)
2026-09-29 bb50aff CR-005: IIR-dev concepts-only run succeeded, $0.0114 (§9 execution order step 1)
2026-09-29 cbec02c CR-005: FACE concept scorer (§3.1)
2026-09-29 d03d577 CR-005: fix misleading precision=1.0 in FACE scorer's n-gram breakdown
2026-09-29 b5fcfa6 CR-005: STOP 2 -- real FACE concept metrics on IIR dev
2026-09-29 0809276 CR-005: concept-extraction prompt v2 + targeted gleaning v2+g (STOP 2 response)
2026-09-30 ccda1fe CR-005: dev ablation result -- v2 selected, lenient micro F1 0.539 -> 0.612
2026-09-30 00f1be0 CR-005: update PROGRESS.md -- ablation done, flag IIR test-chapter text gap
2026-09-30 891aa27 CR-005: log new source -- Stanford NLP IR-book HTML edition (before fetching)
2026-09-30 deca384 CR-005: fix parse_gold_concepts crash on an unescaped apostrophe (iir_face)
2026-09-30 78be6e9 CR-005: IIR-test headline result -- lenient micro F1 0.407 (v2, dev was 0.612)
2026-09-30 6f53276 CR-005: wire the chosen v2 (no-gleaning) prompt into the pipeline defaults
2026-09-30 bf9dd88 CR-005: raise concept_extraction max_output_tokens 3500 -> 8000 for P&D
2026-09-30 8a962cd CR-005: raise canonicalize max_output_tokens 300 -> 800
2026-09-30 20a09a7 CR-005: STOP 1b -- real P&D pair enumeration, exact relation cost $4.93
2026-09-30 9c0f900 CR-005: fix wrong canonicalization merges (kind/instance collapsed into category)
2026-09-30 449b2a7 CR-005: real canonicalize-v2 re-run, $1.38, 43 non-trivial merges for owner review
2026-09-30 272675c CR-005: PROGRESS -- canonicalisation fix status and per-stage cost since the amendment
2026-09-30 585ac43 CR-005: correct the IIR-test headline (0.407 -> 0.568); root cause was my scraping
2026-09-30 e8b1e1f CR-005: owner merge review (41/43 ok), block the 2 wrong pairs, raise relation token ceilings
2026-09-30 02a59b6 CR-005: relations run on P&D ch2-3 ($1.88), snapshots built, STOP 3 sheet ready
2026-09-30 60d84db CR-005: STOP 3 -- owner spot-check of 30 edges, strict precision 0.767 (Wilson [0.591, 0.882])
2026-09-30 f410626 CR-005: fix snapshot edge direction (ignored 'reversed'); add face_eval for the report
2026-09-30 6a789e0 CR-005: STOP 4 -- offline visual report (cumap demo build), 13 tests, DECISIONS/PROGRESS
2026-09-30 65180ac CR-005: STOP 4 signed off by owner
2026-09-30 d894d37 Docs: add CR-002/003/004 change requests, KG-organisation research note, registry patches
2026-09-30 b540f21 CR-005: growth graph as a section-by-section time-bar animation (+ animated SVG figure)
2026-09-30 0b35922 CR-005: growth-only page (reports/demo/growth.html) alongside the full report
2026-09-30 ae3064c CR-005: 3D interactive growth graph (growth3d.html): spin, zoom, click a concept
2026-09-30 564e047 CR-005: growth graph page -- no auto-spin, +50% zoom, 2D/3D toggle with morph, UI pass
2026-09-30 45e2517 CR-005: remove redundant growth.html (2D/3D toggle covers it); BUILD_PLAN M5.0 updated to as-built status
2026-09-30 605be61 CR-005: growth3d UI pass (impeccable, taste, emil): find box, keyboard and touch, states, cleaner chrome
2026-09-30 f689a2b Ignore installed skill packages; commit skills-lock.json to pin them
2026-09-30 80f6f2e CR-005: remove pop-up ring on new nodes in growth3d (fade in only)
```

Commits mentioning a CR or milestone: 56. First commit 2026-09-28, latest 2026-09-30.

### FYP dates / deadlines

Search of `docs/` and `CLAUDE.md` for deadline / due date / submission / viva / hand-in: **nothing found.** The only schedule-like text is the milestone durations in BUILD_PLAN.md (e.g. 'M5 ... (2.5 wk)') and the 'supervisor meeting' mention in CR-005; no calendar dates.

### Counts

- Source files: 66 `.py` files under `src/` (10772 lines) across 10 packages/dirs.
- Tests: 31 test files, 265 `test_` functions (last full `pytest` run: 271 passed).
- Prompts: 17 versioned prompt files in 9 task folders: canonicalize/v1.md, canonicalize/v2.md, concept_extraction/v1.md, concept_extraction/v2.md, concept_extraction_gleaning/v1.md, concept_extraction_gleaning/v2.md, coverage_guess/v1.md, expert_subgraph/v1.md, expert_subgraph/v2.md, relation_choice/v1.md, relation_choice/v2.md, relation_family/v1.md, relation_family/v2.md, relation_qualifiers/v1.md, relation_qualifiers/v2.md, student_graph/v1.md, student_graph/v2.md.

### Citations found in ARCHITECTURE.md, BUILD_PLAN.md, the CRs and docs/research

**The docs cite in short form: author(s) and year, sometimes a venue (e.g. 'Speer et al., AAAI 2017', 'Chen et al. 2018, IEEE Access'). No paper has a title, full author list or DOI in `docs/`; the only full-form entries in the repo are the FACE and Wang et al. ones in `data/raw/external/iir_face/SOURCE.md` (quoted below).** I did not use the web (not allowed for this task), so I am not filling in titles/venues from memory - that risks fabricated details. Each row is the docs' own text with file:line. Treat every row as 'cited in the docs, full citation still to be looked up'. Some rows are venue tokens (AAAI, ACL, EMNLP ...) picked up next to a year; read the context column.

| cited as | year in docs | where (file:line) | docs' own context |
|---|---|---|---|
| AAAI | 2017 | relation-mapping-research.md:88 | - **ConceptNet 5.5** (Speer et al., AAAI 2017): a closed set of about three dozen relations, e.g. IsA, PartOf, **UsedFor**, CapableOf, Causes, HasPrerequisite, HasProperty, DistinctFrom, Antonym. |
| ACL | 2023 | relation-mapping-research.md:136; relation-mapping-research.md:141 | \| Plain prompted LLMs still underperform small fine-tuned models on relation extraction, partly because it is rare in instruction-tuning data. Reframing it as **multiple-choice QA over plain-language relation templates** outperfor |
| Ambrose et al. | 2010 | CR-004-knowledge-organisation.md:22; kg-organisation-research.md:45 | - Ambrose et al. (2010), ch. 2. |
| Anderson & Krathwohl | 2001 | kg-organisation-research.md:48 | - **Revised Bloom's taxonomy** (Anderson & Krathwohl 2001), knowledge dimension: **factual** (terms, specific details), **conceptual** (classifications, principles, models), **procedural** (algorithms, methods, when to use them), |
| Ausubel | 1968 | kg-organisation-research.md:27 | - **Meaningful learning** (Ausubel 1968; as used by Novak & Cañas 2008): |
| Ayala & Shavelson | 2005 | relation-mapping-research.md:100 | - **Fixed vs free linking phrases** (Yin, Vanides, Ruiz-Primo, Ayala & Shavelson 2005, JRST): |
| Aytekin & Saygın | 2024 | kg-organisation-research.md:89 | \| **Educational KG builders** (KnowEdu, Chen et al. 2018, *IEEE Access*; ACE, Aytekin & Saygın 2024, *JEDM*) \| Concepts + prerequisite relations from teaching data; ACE ranks pairs by AI scores and experts label only the best cand |
| Biggs & Collis | 1982 | kg-organisation-research.md:58 | - **SOLO taxonomy** (Biggs & Collis 1982). Five levels: |
| Boustedt et al. | 2007 | kg-organisation-research.md:186; kg-organisation-research.md:68 | - **Learning progressions** (e.g. Corcoran, Mosher & Rogat 2009, CPRE): ordered, increasingly sophisticated ways of thinking about a big idea. **Threshold concepts** (Meyer & Land 2003; in CS, Boustedt et al. 2007, SIGCSE) are tra |
| Bredeweg & Forbus | 2003 | relation-mapping-research.md:121 | - **Qualitative reasoning** (Forbus 1984, Qualitative Process Theory; Bredeweg & Forbus 2003, AI Magazine, on use in education): "how quantities affect each other" is expressed as influences and **qualitative proportionalities** ( |
| Brown & Burton | 1978 | kg-organisation-research.md:84 | \| **Bug libraries / perturbation models** (Brown & Burton 1978, BUGGY) \| Errors come from systematic "bugs", i.e. perturbations of correct procedures \| Misconception layer = catalogued perturbations of expert subgraphs; `match_typ |
| Brown & Cocking | 2000 | kg-organisation-research.md:33 | - **Expertise** (*How People Learn*, Bransford, Brown & Cocking 2000, ch. 2). Experts: |
| Carr & Goldstein | 1977 | kg-organisation-research.md:83 | \| **Overlay student model** (Carr & Goldstein 1977; widely used in adaptive systems) \| The student model is a marked-up copy of the expert model (known / unknown per element) \| Each student graph = overlay states on expert edges: |
| Chaffin & Herrmann | 1984 | relation-mapping-research.md:41 | - **Chaffin & Herrmann (1984)** found people group relations into five families: **contrast, similars, class inclusion, case relations, part-whole**. |
| Chaffin & Herrmann | 1987 | relation-mapping-research.md:42 | - **Winston, Chaffin & Herrmann (1987)** identify six **part-whole** types: |
| Chen et al. | 2018 | kg-organisation-research.md:89 | \| **Educational KG builders** (KnowEdu, Chen et al. 2018, *IEEE Access*; ACE, Aytekin & Saygın 2024, *JEDM*) \| Concepts + prerequisite relations from teaching data; ACE ranks pairs by AI scores and experts label only the best cand |
| Chi | 2005 | kg-organisation-research.md:73; relation-mapping-research.md:124 | - **Synthetic models** (Vosniadou 1994) and **wrong ontological category** (Chi 2005). |
| Chi et al. | 1981 | kg-organisation-research.md:113 | \| **A. Abstraction tier** \| `principle` (big ideas, ~8–12 for networking) → `core` concept → `detail` \| Ausubel; How People Learn; Chi et al. 1981; RAPTOR/GraphRAG \| **New** \| |
| Chmielewski & Dansereau | 1998 | relation-mapping-research.md:105 | - **Knowledge maps with fixed link types** (Dansereau and colleagues; Lambiotte et al. 1989; Chmielewski & Dansereau 1998) teach learners a small labelled set: **Characteristic (C), Type (T), Part, Leads-to (L), Influences (I), Ex |
| Collins & Loftus | 1975 | kg-organisation-research.md:82 | \| **Semantic networks** (Collins & Quillian 1969; Collins & Loftus 1975) \| Concepts as nodes in an is-a hierarchy with inherited properties; spreading activation \| Inheritance of properties down `is_a`; activation spreading from a |
| Collins & Quillian | 1969 | kg-organisation-research.md:82 | \| **Semantic networks** (Collins & Quillian 1969; Collins & Loftus 1975) \| Concepts as nodes in an is-a hierarchy with inherited properties; spreading activation \| Inheritance of properties down `is_a`; activation spreading from a |
| Corbett & Anderson | 1995 | kg-organisation-research.md:86 | \| **Knowledge tracing:** BKT (Corbett & Anderson 1995), DKT (Piech et al. 2015), graph-based KT (Nakagawa, Iwasawa & Matsuo 2019) \| Estimate mastery per knowledge component over time; GKT uses the concept graph to share evidence b |
| Corbett & Perfetti | 2012 | kg-organisation-research.md:49 | - **KLI framework** (Koedinger, Corbett & Perfetti 2012, *Cognitive Science*): learning is described through *knowledge components*, with different learning processes: memory & fluency; induction & refinement; understanding & sens |
| Darden & Craver | 2000 | relation-mapping-research.md:116 | - **Mechanistic reasoning** (Russ, Scherr, Hammer & Mikeska 2008, from Machamer, Darden & Craver 2000): |
| Doignon & Falmagne | 1985 | kg-organisation-research.md:85 | \| **Knowledge Space Theory** (Doignon & Falmagne 1985; used in ALEKS) \| A learner's state is a feasible subset of items, constrained by prerequisite ("surmise") relations \| Consistency check: an answer that expresses an advanced e |
| Edge et al. | 2024 | kg-organisation-research.md:97 | \| **GraphRAG** (Edge et al. 2024, Microsoft) \| LLM extracts an entity graph → community detection (Leiden) → hierarchical **community summaries** \| Progressive differentiation / big ideas \| Detect topic modules in the P&D KG; the |
| EMNLP | 2020 | relation-mapping-research.md:145; relation-mapping-research.md:23 | 7. **Keep the relation set small and put the nuance in qualifiers** (polarity, modality, conditions, part type, comparison dimension). This is the "hyper-relational" pattern (Wikidata-style qualifiers; StarE, EMNLP 2020). It gives |
| EMNLP | 2021 | relation-mapping-research.md:137 | \| Writing each relation as a **plain-language template** and solving by entailment gives 63% F1 zero-shot and 69% with 16 examples per relation on TACRED. Templates take under 15 minutes per relation. **Main error: detecting "no r |
| EMNLP | 2023 | CR-002-concept-confidence.md:16; CR-002-concept-confidence.md:17; relation-mapping-research.md:143 | - For chat-tuned models, stated confidence can be better calibrated than token probabilities (Tian et al., EMNLP 2023). It is one useful signal, not the answer. |
| EMNLP | 2024 | relation-mapping-research.md:139 | \| **Extract openly → define → canonicalise** onto the schema, retrieving only the relevant schema parts, scales to large schemas. \| Zhang & Soh, EMNLP 2024 (EDC) \| Allow an `other` relation with the free-text phrase; review and cl |
| Faletti & Fisher | 1996 | relation-mapping-research.md:106 | - **SemNet** (Fisher; Faletti & Fisher 1996): the ability to generate and use relations effectively distinguishes good from poor biology students. Designing relations and using them consistently is itself hard, which argues for te |
| Fellbaum | 1998 | relation-mapping-research.md:40 | - **WordNet** (Miller 1995; Fellbaum 1998) organises nouns mainly by **hyponymy (is-a)** and **meronymy (part-of)**, plus synonymy and antonymy. |
| Feltovich & Glaser | 1981 | CR-004-knowledge-organisation.md:21; kg-organisation-research.md:11; kg-organisation-research.md:185; kg-organisation-research.md:39 | - Chi, Feltovich & Glaser (1981); |
| Forbus | 1984 | relation-mapping-research.md:121 | - **Qualitative reasoning** (Forbus 1984, Qualitative Process Theory; Bredeweg & Forbus 2003, AI Magazine, on use in education): "how quantities affect each other" is expressed as influences and **qualitative proportionalities** ( |
| Framework | 2012 | CR-004-knowledge-organisation.md:140; kg-organisation-research.md:182 | **Criteria used throughout** (1–5 Likert), adapted from the NRC Framework (2012) and Wiggins & McTighe (UbD): |
| García-Ferrero et al. | 2023 | ARCHITECTURE.md:256 | 3. **Qualifier pass (separate).** Polarity, modality, conditions, `part_type`/`dimension`/`surface_phrase` are extracted in their own pass, targeting the well-documented LLM weakness on negation (García-Ferrero et al. 2023) — a si |
| Goldman et al. | 2008 | kg-organisation-research.md:183 | \| **Delphi studies** \| Anonymous expert rounds rating items; group results fed back; repeat until consensus \| Goldman et al. (2008, SIGCSE): Delphi rating of **importance and difficulty** of concepts in introductory computing, use |
| GoLLIE | 2024 | ARCHITECTURE.md:118 | \| `near_misses` \| list[{relation, example, why}]: the annotation-guideline negatives that make choice-based extraction reliable (QA4RE 2023; GoLLIE 2024) \| |
| Graesser & Hu | 2014 | relation-mapping-research.md:127 | - **Expectations and misconceptions as propositions** (AutoTutor; Nye, Graesser & Hu 2014, IJAIED): tutors compare student answers with lists of expected propositions and known misconception propositions. This mirrors our referenc |
| Hammer & Mikeska | 2008 | relation-mapping-research.md:116 | - **Mechanistic reasoning** (Russ, Scherr, Hammer & Mikeska 2008, from Machamer, Darden & Craver 2000): |
| Harlen | 2010 | kg-organisation-research.md:182 | \| **Criteria-based expert panels** \| Experts screen candidates against explicit criteria \| Harlen (2010): 10 international experts, 4 criteria (explanatory power over many phenomena; basis for decisions; satisfaction from answerin |
| Hay & Adams | 2000 | kg-organisation-research.md:45 | - **Knowledge organisation** (Ambrose et al. 2010, *How Learning Works*, ch. 2; companion to the ch. 1 already reviewed): novices' knowledge is sparse and loosely connected; experts' is dense and organised around meaningful featur |
| Herrmann | 1987 | ARCHITECTURE.md:100 | \| `part_type` \| `component \\| member \\| phase \\| None` \| Required iff `relation == part_of`; catches `part_type_error` (right endpoints, wrong part-whole type — transitivity fails across types, Winston/Chaffin/Herrmann 1987) \| |
| Hmelo-Silver & Pfeffer | 2004 | relation-mapping-research.md:109; relation-mapping-research.md:11 | 3. **Education research says the relations that reveal *depth* of understanding are behavioural, functional and causal, not taxonomic.** Novices describe structures; experts connect structures to behaviours and functions (Hmelo-Si |
| ICLR | 2019 | relation-mapping-research.md:146 | \| Relation patterns (symmetry, antisymmetry, inversion, composition) can be modelled explicitly in embedding space; inside LLMs many relations decode as approximately **linear maps**. \| Sun et al., ICLR 2019 (RotatE); Hernandez et |
| ICLR | 2024 | CR-002-concept-confidence.md:15; kg-organisation-research.md:98; relation-mapping-research.md:138; relation-mapping-research.md:142 | - LLMs' **stated confidence is overconfident**, especially on specialist knowledge. **Agreement across several responses** and better aggregation reduce this (Xiong et al., ICLR 2024). |
| IJAIED | 2021 | CR-002-concept-confidence.md:14 | - **FACE** (Chau et al., IJAIED 2021): a logistic-regression concept probability let the authors trade precision against recall, from about 98% precision at 19% recall to about 97% recall at 37% precision (AUC 0.94). Different dow |
| ISWC | 2023 | relation-mapping-research.md:140 | \| Evaluate generated graphs for **ontology conformance** (domain/range) and **hallucination**, not just precision/recall. \| Mihindukulasooriya et al., ISWC 2023 (Text2KGBench) \| Add conformance and unsupported-by-text rates to M5/ |
| Iwasawa & Matsuo | 2019 | kg-organisation-research.md:86 | \| **Knowledge tracing:** BKT (Corbett & Anderson 1995), DKT (Piech et al. 2015), graph-based KT (Nakagawa, Iwasawa & Matsuo 2019) \| Estimate mastery per knowledge component over time; GKT uses the concept graph to share evidence b |
| Javonillo & Martin-Dunlop | 2019 | relation-mapping-research.md:99 | - Specific linking phrases ("cristae *part of* mitochondria") indicate deeper understanding than generic ones (Javonillo & Martin-Dunlop 2019, who provide 105+ phrases for introductory biology covering quantitative, structural and |
| Karpierz & Wolfman | 2014 | BUILD_PLAN.md:351 | 3. Second domain: *Open Data Structures* + Mohler. Re-run M1 (ingestion), M5 and M6/M7 in score mode, and compare RMSE with MitiGaTe's reported 0.762 on Mohler (note the protocol differences). Seed misconceptions from Karpierz & W |
| Khoo & Na | 2006 | relation-mapping-research.md:33; relation-mapping-research.md:9 | 1. **No field agrees on one "correct" relation inventory.** Linguistics has "lumpers" (a few general relations) and "splitters" (long lists). Reviews conclude the set must be chosen for the application (Khoo & Na 2006). So the pro |
| Lambiotte et al. | 1989 | relation-mapping-research.md:105 | - **Knowledge maps with fixed link types** (Dansereau and colleagues; Lambiotte et al. 1989; Chmielewski & Dansereau 1998) teach learners a small labelled set: **Characteristic (C), Type (T), Part, Leads-to (L), Influences (I), Ex |
| Linguistics | 2024 | CR-003-reduce-manual-labelling.md:17 | - LLMs are useful first-pass annotators (Gilardi et al., PNAS 2023: better than crowd workers on 4 of 5 tasks, ~$0.003 per item). They still don't replace human checking (Ziems et al., Computational Linguistics 2024: fair agreemen |
| Linn & Eylon | 2011 | kg-organisation-research.md:66 | - **Knowledge integration** (Linn & Eylon 2011): learners hold a *repertoire of ideas*. Learning means eliciting, adding, **distinguishing** and **sorting out** ideas, not replacing them. |
| Lister et al. | 2006 | CR-004-knowledge-organisation.md:24; kg-organisation-research.md:13; kg-organisation-research.md:64 | Kinds of knowledge (factual, conceptual, procedural) need different feedback (revised Bloom; KLI). Understanding shows in **how connected** an answer is (SOLO; Lister et al. 2006). |
| Mann & Thompson | 1988 | relation-mapping-research.md:68 | - **Rhetorical Structure Theory** (Mann & Thompson 1988) and the **Penn Discourse Treebank 3.0** (Webber, Prasad et al. 2019) classify how *statements* relate. PDTB-3's four top classes: |
| McLure | 2023 | relation-mapping-research.md:11; relation-mapping-research.md:120 | 3. **Education research says the relations that reveal *depth* of understanding are behavioural, functional and causal, not taxonomic.** Novices describe structures; experts connect structures to behaviours and functions (Hmelo-Si |
| Meyer & Land | 2003 | kg-organisation-research.md:186; kg-organisation-research.md:68 | - **Learning progressions** (e.g. Corcoran, Mosher & Rogat 2009, CPRE): ordered, increasingly sophisticated ways of thinking about a big idea. **Threshold concepts** (Meyer & Land 2003; in CS, Boustedt et al. 2007, SIGCSE) are tra |
| Miller | 1995 | relation-mapping-research.md:40 | - **WordNet** (Miller 1995; Fellbaum 1998) organises nouns mainly by **hyponymy (is-a)** and **meronymy (part-of)**, plus synonymy and antonymy. |
| Mosher & Rogat | 2009 | kg-organisation-research.md:68 | - **Learning progressions** (e.g. Corcoran, Mosher & Rogat 2009, CPRE): ordered, increasingly sophisticated ways of thinking about a big idea. **Threshold concepts** (Meyer & Land 2003; in CS, Boustedt et al. 2007, SIGCSE) are tra |
| NeurIPS | 2024 | kg-organisation-research.md:99 | \| **HippoRAG** (Gutiérrez, Shu, Gu, Yasunaga & Su, NeurIPS 2024) \| LLM = "neocortex", KG = "hippocampal index", **Personalized PageRank** = pattern completion from partial cues; up to 20% better multi-hop QA, 10–20× cheaper than i |
| NeurIPS | 2025 | kg-organisation-research.md:100 | \| **A-Mem** (Xu et al., NeurIPS 2025) \| Zettelkasten-style notes with keywords, tags and links; new notes **update older notes** ("memory evolution") \| Assimilation + accommodation \| When later chapters add information, revise ear |
| Novak & Cañas | 2008 | kg-organisation-research.md:27; relation-mapping-research.md:96 | - **Meaningful learning** (Ausubel 1968; as used by Novak & Cañas 2008): |
| Piech et al. | 2015 | kg-organisation-research.md:86 | \| **Knowledge tracing:** BKT (Corbett & Anderson 1995), DKT (Piech et al. 2015), graph-based KT (Nakagawa, Iwasawa & Matsuo 2019) \| Estimate mastery per knowledge component over time; GKT uses the concept graph to share evidence b |
| PNAS | 2023 | CR-003-reduce-manual-labelling.md:17 | - LLMs are useful first-pass annotators (Gilardi et al., PNAS 2023: better than crowd workers on 4 of 5 tasks, ~$0.003 per item). They still don't replace human checking (Ziems et al., Computational Linguistics 2024: fair agreemen |
| Prasad et al. | 2019 | relation-mapping-research.md:68 | - **Rhetorical Structure Theory** (Mann & Thompson 1988) and the **Penn Discourse Treebank 3.0** (Webber, Prasad et al. 2019) classify how *statements* relate. PDTB-3's four top classes: |
| Pustejovsky | 1991 | relation-mapping-research.md:55 | - **Qualia structure** (Pustejovsky 1991, Generative Lexicon) describes a concept's meaning through four roles: |
| QA4RE | 2023 | ARCHITECTURE.md:118; ARCHITECTURE.md:252; relation-mapping-research.md:14 | \| `near_misses` \| list[{relation, example, why}]: the annotation-guideline negatives that make choice-based extraction reliable (QA4RE 2023; GoLLIE 2024) \| |
| Rasmussen et al. | 2025 | kg-organisation-research.md:102 | \| **Zep / Graphiti** (Rasmussen et al. 2025; already listed) \| Episodic → semantic → community subgraphs; edges carry validity periods \| Memory consolidation \| Versioned, time-stamped edges (already adopted as "deprecate, don't de |
| Reed & Clark | 1984 | CR-004-knowledge-organisation.md:156 | - Optional: Saltzer, Reed & Clark (1984) end-to-end paper (summary only, if accessible); Denning's *Great Principles* (summary only) |
| RFC | 1958 | CR-004-knowledge-organisation.md:155; CR-004-knowledge-organisation.md:219; kg-organisation-research.md:184; kg-organisation-research.md:192 | - **RFC 1958**, *Architectural Principles of the Internet* (IETF; RFC text is freely reusable; record it) |
| Rocha & Favero | 2004 | relation-mapping-research.md:98 | - Vague phrases like "has" can mean different relations ("person has arm" = part; "person has children" = kinship), so propositions need a typed relation before they can be scored automatically (da Costa Jr, da Rocha & Favero 2004 |
| Rugaber & Vattam | 2009 | relation-mapping-research.md:109 | - **Structure–Behaviour–Function (SBF)** (Hmelo-Silver & Pfeffer 2004, Cognitive Science; Goel, Rugaber & Vattam 2009, AI EDAM): |
| Russ et al. | 2008 | relation-mapping-research.md:11 | 3. **Education research says the relations that reveal *depth* of understanding are behavioural, functional and causal, not taxonomic.** Novices describe structures; experts connect structures to behaviours and functions (Hmelo-Si |
| Sainz et al. | 2021 | ARCHITECTURE.md:252; CR-001-relations-v1.md:22; relation-mapping-research.md:15 | Plain-prompted relation extraction underperforms; turning it into **multiple-choice over plain-language templates** closes most of the gap to fine-tuned models (QA4RE 2023; Sainz et al. 2021 EMNLP). The extraction pipeline is four |
| Sessa | 1993 | kg-organisation-research.md:72 | - **Knowledge in pieces** (diSessa 1993): novice knowledge is a loosely connected set of intuitive fragments ("p-prims"), activated by context. Expertise *reorganises* them rather than replacing them. |
| System | 2012 | CR-003-reduce-manual-labelling.md:56 | \| `acm_ccs` \| ACM Computing Classification System 2012 (SKOS/XML) \| acm.org/publications/class-2012 (check terms of use) \| `acm_ccs_concepts.csv` + `acm_ccs_broader.csv` \| |
| Thompson & Nash | 2022 | CR-004-knowledge-organisation.md:301; kg-organisation-research.md:151; kg-organisation-research.md:88 | - Population-level **reversal rate** per question = the share of answers with ≥ 1 flag. Report it as an empirical check of the prerequisite layer (after Thompson & Nash 2022). Questions with high reversal rates point to prerequisi |
| UIST | 2023 | kg-organisation-research.md:101 | \| **Generative agents** (Park et al., UIST 2023) \| Memory stream + periodic **reflection** that synthesises higher-level insights from observations \| Abstraction from experience \| Reflection-style prompts to derive principles from |
| VLDB | 2017 | CR-003-reduce-manual-labelling.md:18 | - Snorkel (Ratner et al., VLDB 2017) combines noisy labelling sources into probabilistic training labels. |
| Vosniadou | 1994 | kg-organisation-research.md:73 | - **Synthetic models** (Vosniadou 1994) and **wrong ontological category** (Chi 2005). |
| Winston et al. | 1987 | relation-mapping-research.md:182 | \| **5. Classification & structure** \| `is_a`, `part_of` (+ `part_type`: component / member / phase), `has_property` \| WordNet; Winston et al. 1987; qualia formal/constitutive; SBF structure; Dansereau Type/Part/Characteristic \| |
| Yin et al. | 2005 | ARCHITECTURE.md:102; CR-001-relations-v1.md:17; relation-mapping-research.md:12 | \| `surface_phrase` \| str \\| None \| The linking words as written; required on `StudentEdge` and on LLM-extracted `ExpertEdge`; preserves partial knowledge even after canonicalisation (Yin et al. 2005) \| |
| Zhai | 2025 | relation-mapping-research.md:144 | \| LLM-generated concept maps show **hallucinated nodes, vague linking phrases, missing cross-links**. Human-in-the-loop and knowledge-base grounding help. \| Zhai 2025, systematic review of 28 studies \| Evidence quotes, schema grou |

### Year mismatches / flags

- **FACE (Chau et al.): 2020 vs 2021.** `docs/DECISIONS.md:27` says 'Chau et al. 2020 (IJAIED, the FACE paper)'; `data/raw/external/iir_face/SOURCE.md` says 'Chau, Labutov, Thaker, He, Brusilovsky. "Automatic Concept Extraction for Domain and Student Modeling in Adaptive Textbooks." IJAIED 31 (2021)'. IJAIED volume 31 is the 2021 volume, so the 2020 is probably the online-first year. **Verify on the publisher page and use one year everywhere.**
- SOURCE.md's 'Cited as' for the dataset: 'Wang, Chau, Thaker, Brusilovsky, He. "Knowledge Annotation for Intelligent Textbooks." Technology, Knowledge and Learning (2021).' (the only other full-form entry in the repo).
- `data/raw/external/iir_face/SOURCE.md` is stale: it still says 'CR-005 §6 skips the IIR test split', but chapters 4/6/9 were later fetched from the Stanford IR-book pages and run (see DECISIONS.md). (Not edited - read-only task.)
- Same author token with more than one year across the docs (may be different papers - check): {'ICLR': [2019, 2024], 'EMNLP': [2020, 2021, 2023, 2024], 'Brown': [1978, 2000], 'Corbett': [1995, 2012], 'Chi': [1981, 2005], 'Collins': [1969, 1975], 'NeurIPS': [2024, 2025], 'Chaffin': [1984, 1987]}

### FACE paper details as recorded in the repo (for the slide footnote)

```markdown
# Source: FACE / IIR concept-extraction dataset

- **Repo:** https://github.com/PAWSLabUniversityOfPittsburgh/Concept-Extraction
- **Commit pinned:** `9f03208fd995fc4e92c14fa1d371c185629ead56` (2021-11-22)
- **Cited as:** Wang, Chau, Thaker, Brusilovsky, He. "Knowledge Annotation for Intelligent
  Textbooks." Technology, Knowledge and Learning (2021).
  Also: Chau, Labutov, Thaker, He, Brusilovsky. "Automatic Concept Extraction for
  Domain and Student Modeling in Adaptive Textbooks." IJAIED 31 (2021) — this is the
  FACE paper CR-003/CR-005 compare against (micro F1 0.76, macro F1 0.60, etc.).
- **Licence:** no LICENSE file in the repo. Used here for local, non-redistributed
  academic research only (this project's own comparison against the paper's published
  numbers), matching CR-003 §3's framing. `data/raw/` and `data/interim/external/` are
  both gitignored — the underlying IIR text and this repo's gold annotations are never
  committed to this project's git history.

## What's in it
- `IIR-dataset/annotation/*.csv` — 86 files, one per section of *Introduction to
  Information Retrieval* (Manning, Raghavan & Schütze), covering the book's first 16
  chapters. Each row: a candidate concept (as a Python-list-repr string of surface
  forms/aliases) + 3 annotators' binary (0/1) concept judgement.
- `IIR-dataset/book_section_samples/iir.sections.txt` — tab-separated
  `section_
```

## 8. Reproducibility

**Where the IIR test scraper lives:** in a session scratch directory, **not** in the repo and **not** promoted into `src/`:

```
/private/tmp/claude-501/-Users-wongzhengtat-Desktop-h420020-mapper/34bcb7cf-4023-4042-ab5e-7798b1331913/scratchpad/
  scrape_v2.py  (exists now)
  fetch_iir_test_chapters.py  (exists now)
  iir_test_v2data_run.py  (exists now)
  iir_replays.py  (exists now)
  iir_test_run.py  (exists now)
  iir_dev_concepts_run.py  (exists now)
  pd_run.py  (exists now)
  pd_relations_run.py  (exists now)
  pd_canonicalize_v2_run.py  (exists now)
  rebuild_snapshots.py  (exists now)
```

Tracked files in git matching scrape/fetch_iir/iir_test: none. This scratch directory is temporary (session-scoped) and can be deleted by the OS, so the scraper is at risk of being lost; the *output* it produced is safe on disk at `data/interim/external/iir_test_sections_v2.jsonl` (gitignored, third-party text). Promoting `scrape_v2.py` (+ its validation and a test) into `src/cumap/data/` is an open follow-up.

**Commands to reproduce (all read-only / $0; none call the API):**

```
# 1. IIR dev/test FACE scores from the frozen extractions saved on disk (no LLM, no network)
uv run python - <<'EOF'
import json
for run in ("iirdev_v2", "iirtest_v2"):
    m = json.load(open(f"data/processed/kg/{run}/face_eval.json"))["metrics"]
    print(run, "lenient micro P/R/F1 =", [round(m["lenient"]["micro"][k], 3) for k in ("precision","recall","f1")],
          "exact micro F1 =", round(m["exact"]["micro"]["f1"], 3))
EOF

# 2. Recompute those metrics from the run checkpoints (spaCy + embeddings, still no LLM); also rebuilds the report
uv run cumap demo build --run pdcanon2_30e2b4f9 --refresh-eval

# 3. Rebuild the IIR extractions themselves from the disk cache ($0, 0 backend calls; needs the scratch script above
#    and data/interim/external/iir_*.jsonl)
uv run python <scratchpad>/iir_replays.py

# 4. P&D run summary (counts) and its spend
uv run python - <<'EOF'
import json, collections
cp = json.load(open("data/processed/kg/pdcanon2_30e2b4f9/checkpoint.json"))
print("concepts", len(cp["concepts"]), "mentions", sum(len(v) for v in cp["mentions_by_section"].values()),
      "merges", len(cp["merges"]), "taxonomy candidates", len(cp["taxonomy_candidates"]),
      "pairs", len(cp["pair_registry"]), "accepted edges", sum(1 for p in cp["pair_registry"] if p.get("edge")))
print(json.load(open("data/processed/kg/pdcanon2_30e2b4f9/relations_result.json")))
EOF
python3 - <<'EOF'   # spend from the call log (cache-hit replays cost 0)
import json
tot = sum(((r.get("usage") or {}).get("input_tokens", 0) * 2 + (r.get("usage") or {}).get("output_tokens", 0) * 10) / 1e6
          for r in map(json.loads, open("data/logs/llm_calls.jsonl")) if r["run_id"] == "pdcanon2_30e2b4f9" and not r["cache_hit"] and r["model_tier"] == "strong")
print("strong-tier spend for this run id, USD:", round(tot, 4))
EOF
```

Output of the P&D summary right now:

```
concepts 736 mentions 943 merges 207 taxonomy candidates 190 pairs 381 accepted edges 121
{'run_id': 'pdcanon2_30e2b4f9', 'total_spend': 1.9026740000000018, 'pairs_resolved': 381, 'accepted_edges': 121, 'rejected': 260, 'rejection_reasons': {'family_no_relation': 143, 'relation_other': 114, 'family_other': 3}, 'families': {'classification_structure': 68, 'function_means': 29, 'comparison': 9, 'dependency': 7, 'cause_effect': 6, 'mechanism_process': 2}}
strong-tier logged spend under run id pdcanon2_30e2b4f9 (non-cache calls only, $2/$10 per 1M): $1.9027  (matches relations_result.json total_spend; per DECISIONS.md the relations stage cost $1.88 and the canonicalize v2 re-run $1.38, so this run id's log does not capture every stage)
```

- `iirdev_v2` lenient micro P/R/F1 = [0.673, 0.561, 0.612], exact micro F1 = 0.486
- `iirtest_v2` lenient micro P/R/F1 = [0.72, 0.469, 0.568], exact micro F1 = 0.474

## Not found / could not do

- FYP dates / deadlines (none in docs/ or CLAUDE.md)
- IIR test scraper in the repo/src (only in scratch)
- Full bibliographic citations (titles, full author lists, DOIs) for cited papers: only short forms exist in the repo; web lookup was out of scope.
