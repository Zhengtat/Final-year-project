# CR-007 STOP 3: registry v1.1 and relation prompts v3

For the owner's approval: the final registry YAML, the prompt diffs and the pilot re-classification of the 114 CR-005 OTHER pairs. Nothing has been run on the slice yet.

## 1. Registry v1.1 (`configs/relations_v1.1.yaml`, generated from v1 + `configs/registry-patches/CR-007-relations-v1.1.yaml`)

v1 is unchanged. v1.1 adds 5 relations (2 core, 3 gated), the node type `Identifier`, 3 qualifiers, the two OTHER output fields, one-line family glosses (used by the family step) and widens `dimension` to `trades_off_with`. CR-004's `instantiates` patch becomes v1.2 (not applied). Full file: 21 relations.

Node types: `['Protocol', 'Mechanism', 'Component', 'DataUnit', 'Parameter', 'Property', 'Event', 'State', 'Layer', 'Concept', 'Identifier']`. Output fields (relation-choice schema): `['other_description', 'other_suggested_label']`.

### Qualifiers added or changed

```yaml
action_type:
  values:
  - send
  - receive
  - forward
  - transform
  - check
  - store
  - drop
  - generate
  - other
  applies_to:
  - acts_on
  required: true
  note: Closed list for the verb class. Keep the exact verb in surface_phrase (e.g. 'retransmits' -> send).
corrects_intuition:
  type: bool
  applies_to: all
  required: false
  note: True only when the text explicitly warns against a belief ('a common misconception', 'it is tempting to
    think', 'note that X does not'). Store the belief as text in `intuition`.
intuition:
  type: str | None
  applies_to: all
  required: false
dimension:
  type: str
  applies_to:
  - contrasts_with
  - trades_off_with
  required: recommended
  note: what differs, e.g. 'clock recovery', 'cwnd growth rate'
```

### Family glosses (family step)

```yaml
mechanism_process: something acts or happens: an actor performs, triggers or precedes an activity, or handles a data unit (send, receive, forward, transform, check, store, drop)
cause_effect: one thing brings about, prevents or changes the amount of another
function_means: what something is for, or what it uses to achieve its purpose
dependency: one thing needs, requires or is constrained by another (including a stated absence of that need)
comparison: two things are alike, different or in tension along a stated dimension
classification_structure: what kind of thing something is, what it is made of, what it is attached or connected to, what carries or names it
```

### The five new relations

```yaml
- name: acts_on
  family: mechanism_process
  layer: semantic
  status: new_in_v1_1
  gate: core
  definition: 'Component, protocol or mechanism source does something to data unit target: sends, receives, forwards,
    transforms, checks, stores, drops or generates it. The verb class goes in action_type; the exact verb in surface_phrase.'
  template: '{X} handles {Y} (sends, receives, forwards, transforms, checks, stores or drops it)'
  examples:
  - the switch forwards the frame out of one port -> switch acts_on frame (forward)
  - 'the sender retransmits the frame after a timeout -> sender acts_on frame (send; conditions: timeout)'
  - the adaptor encodes the bits using Manchester encoding -> adaptor acts_on bit (transform)
  - 'the receiver discards corrupted frames -> receiver acts_on frame (drop; conditions: CRC error)'
  near_misses:
  - relation: performs
    example: transparent bridge performs backward learning
    why: the target is an activity, not a thing being handled
  - relation: uses
    example: TCP uses sequence numbers
    why: a means the actor relies on, not an object it acts on
  - relation: encapsulates
    example: an Ethernet frame carries an IP packet
    why: containment between two data units; no actor
  domain_types:
  - Component
  - Protocol
  - Mechanism
  - Layer
  range_types:
  - DataUnit
  - Concept
  directional: true
  symmetric: false
  transitive: false
  inverse_of: acted_on_by
  conflicts_with: []
  compatible_with:
    performs: partial

- name: connected_to
  family: classification_structure
  layer: semantic
  status: new_in_v1_1
  gate: core
  definition: Component source is physically or logically linked to component target so the two can exchange data
    directly (network topology).
  template: '{X} is directly connected to {Y}'
  examples:
  - hosts are connected to the switch by point-to-point links -> host connected_to switch
  - a bridge connects two LAN segments -> bridge connected_to LAN segment
  near_misses:
  - relation: part_of
    example: the link is part of the network
    why: membership in a whole, not adjacency between peers
  - relation: uses
    example: the host uses the link
    why: use of a resource, not a topological connection
  domain_types:
  - Component
  - Concept
  range_types:
  - Component
  - Concept
  directional: false
  symmetric: true
  transitive: false
  inverse_of: connected_to
  conflicts_with: []
  compatible_with: {}

- name: identifies
  family: classification_structure
  layer: semantic
  status: new_in_v1_1
  gate: gated
  definition: Identifier source (address, ID, number or name) uniquely names or selects entity target within some
    scope.
  template: '{X} identifies {Y}'
  examples:
  - each adaptor has a unique Ethernet address -> Ethernet address identifies adaptor
  - the VCI identifies the virtual circuit on that link -> VCI identifies virtual circuit
  near_misses:
  - relation: has_property
    example: a frame has a length
    why: an attribute of the thing, not a name that picks it out
  domain_types:
  - Identifier
  - Parameter
  - Property
  range_types:
  - Component
  - Protocol
  - Mechanism
  - DataUnit
  - Concept
  - Layer
  directional: true
  symmetric: false
  transitive: false
  inverse_of: identified_by
  conflicts_with: []
  compatible_with:
    has_property: partial

- name: encapsulates
  family: classification_structure
  layer: semantic
  status: new_in_v1_1
  gate: gated
  definition: Data unit source carries data unit target as its payload (layering and encapsulation).
  template: '{X} carries {Y} as its payload'
  examples:
  - an Ethernet frame carries an IP datagram in its body -> Ethernet frame encapsulates IP datagram
  - the IP datagram carries a TCP segment -> IP datagram encapsulates TCP segment
  near_misses:
  - relation: part_of
    example: the header is part of the frame
    why: a component of one data unit, not the payload from another layer
  - relation: acts_on
    example: the host encapsulates the packet
    why: an actor doing the encapsulation; use acts_on (transform)
  domain_types:
  - DataUnit
  range_types:
  - DataUnit
  directional: true
  symmetric: false
  transitive: true
  inverse_of: carried_in
  conflicts_with:
  - part_of
  compatible_with: {}

- name: trades_off_with
  family: comparison
  layer: semantic
  status: new_in_v1_1
  gate: gated
  definition: Improving property or parameter source tends to worsen target, so a design must balance them. Put
    the design choice that sets the balance in `dimension`.
  template: there is a trade-off between {X} and {Y}
  examples:
  - 'a larger window improves throughput but needs more buffer space -> throughput trades_off_with buffer space
    (dimension: window size)'
  - 'smaller frames reduce latency but add header overhead -> latency trades_off_with header overhead (dimension:
    frame size)'
  near_misses:
  - relation: contrasts_with
    example: CSMA/CD contrasts with token passing
    why: two alternatives that differ, not a see-saw between two qualities
  - relation: increases
    example: a larger window increases throughput
    why: a one-way effect with no opposing cost stated
  domain_types:
  - Property
  - Parameter
  - Concept
  range_types:
  - Property
  - Parameter
  - Concept
  directional: false
  symmetric: true
  transitive: false
  inverse_of: trades_off_with
  conflicts_with: []
  compatible_with:
    contrasts_with: partial

```

## 2. Prompt diffs (v2 -> v3; v2 files are untouched)

### `prompts/relation_family/`

```diff
--- relation_family/v2.md
+++ relation_family/v3.md
@@ -2,13 +2,14 @@
 task: relation_family
-version: v2
+version: v3
 schema: FamilyChoiceLLM
 notes: >
-  M5 task 4 / CR-005 §9. Strong tier. v2 vs v1: the evidence context is now a single
-  sentence (candidate pairs are found by sentence-level co-occurrence, not paragraph),
-  and each pair is classified at most once per run (PairRegistry) -- never edit v1,
-  which produced real cached results before this change (CLAUDE.md rule 8).
+  CR-007 §5.2, registry v1.1. v3 vs v2: every family is shown with a one-line gloss and its relation
+  names (so "handles a data unit" routes to mechanism_process -> acts_on); a stated OR DENIED
+  relation is routed to its family (the polarity qualifier records the denial; v2 tended to answer
+  OTHER for negated dependencies); a mere listing or co-mention is NO_RELATION (v2 answered OTHER for
+  lists and scoping). Never edit v2, which produced saved results (CLAUDE.md rule 8).
 ---
 
-You are checking whether a sentence states a relation between two concepts, and if
-so, which broad family it belongs to.
+You are checking whether a sentence states a relation between two concepts, and if so, which broad
+family it belongs to.
 
@@ -20,7 +21,13 @@
 
-Choose exactly one family that best describes a relation the sentence actually states
-between X and Y (in either direction):
+Families (what each covers, and the relations inside it):
 {family_options}
 
-If the sentence doesn't relate these two concepts to each other at all, choose
-no_relation. If it does relate them but no family above fits, choose other.
+Rules:
+- If the sentence states OR DENIES a relation between X and Y, choose the family of that relation.
+  A denial (for example "does not need", "is independent of") is recorded later as a qualifier, so
+  do not answer no_relation or other for a denial.
+- If X and Y are only listed together, only mentioned in the same sentence, or one merely sets the
+  scene for the other, choose no_relation.
+- Choose other only if the sentence really relates X and Y but none of the families above fits.
+
+Give the family and a one-sentence reason.
```

### `prompts/relation_choice/`

```diff
--- relation_choice/v2.md
+++ relation_choice/v3.md
@@ -2,11 +2,15 @@
 task: relation_choice
-version: v2
-schema: RelationChoiceLLM
+version: v3
+schema: RelationChoiceV3LLM
 notes: >
-  M5 task 4 / CR-005 §9. Strong tier. v2 vs v1: evidence context is now a single
-  sentence, not a paragraph (see relation_family/v2.md) -- never edit v1.
+  CR-007 §5.2, registry v1.1. v3 vs v2: the options are the registry templates FILLED with the two
+  concepts' names, in both directions for directional relations (QA4RE-faithful; v2 showed the literal
+  {X}/{Y} templates); the answer set adds no_relation; a stated or denied relation must be chosen
+  (polarity is a later qualifier); a list or co-mention is no_relation; OTHER requires
+  other_description and other_suggested_label; contrasts_with / trades_off_with require a
+  comparison_dimension named in the sentence, otherwise no_relation. Never edit v2.
 ---
 
-You are picking the exact relation a sentence states between two concepts, within
-the "{family}" family already identified for this pair.
+You are picking the exact relation a sentence states between two concepts, within the "{family}"
+family already identified for this pair.
 
@@ -18,13 +22,22 @@
 
-Options:
+Options. Each reading is filled in with the two concepts; give the relation name and the direction
+of the reading that matches the sentence:
 {relation_options}
 
-Pick the one relation the sentence actually states. direction is "forward" if the
-relation reads X -> Y as written (e.g. "performs" meaning X performs Y), or
-"reversed" if it actually reads Y -> X; direction is ignored (send "forward") for
-non-directional relations or "other".
+Rules:
+- Pick the reading the sentence actually states. If the sentence states OR DENIES a relation, choose
+  that relation: a denial is recorded by the polarity qualifier in a later step, so it is not a
+  reason to choose no_relation or other.
+- If X and Y are only listed together or co-mentioned, choose no_relation.
+- direction is "forward" for a reading that names X first, "reversed" for a reading that names Y
+  first; send "forward" for symmetric relations, no_relation and other.
+- Choose other only if the sentence relates X and Y but no option fits. Then other_description (one
+  sentence saying what the sentence expresses) and other_suggested_label (a 1 to 3 word verb phrase,
+  such as "connects" or "is carried in") are REQUIRED. For every other answer both are null.
+- For contrasts_with and trades_off_with, comparison_dimension is REQUIRED: the dimension along which
+  the two differ or trade off, named in the sentence. If the sentence names no dimension, choose
+  no_relation instead. For every other relation comparison_dimension is null.
 
-evidence_quote: an EXACT substring of the sentence above (copy character-for-
-character) that states this relation.
-statement: a one-sentence paraphrase of the relation in your own words, naming both
-concepts.
+evidence_quote: an EXACT substring of the sentence (copy character-for-character) that states the
+relation, and it must contain both X and Y (or their names).
+statement: a one-sentence paraphrase of the relation in your own words, naming both concepts.
```

### `prompts/relation_qualifiers/`

```diff
--- relation_qualifiers/v2.md
+++ relation_qualifiers/v3.md
@@ -2,7 +2,8 @@
 task: relation_qualifiers
-version: v2
-schema: QualifiersLLM
+version: v3
+schema: QualifiersV3LLM
 notes: >
-  M5 task 4 / CR-005 §9, separate qualifier pass. Strong tier. v2 vs v1: evidence
-  context is now a single sentence, not a paragraph -- never edit v1.
+  CR-007 §5.2, registry v1.1. v3 vs v2: adds action_type (required for acts_on, null otherwise),
+  corrects_intuition / intuition (only when the text explicitly warns against a belief), and states
+  that a denial is polarity "negated". Never edit v2.
 ---
@@ -19,14 +20,19 @@
 Give:
-- polarity: "affirmed" (the sentence states this relation holds) or "negated" (the
-  sentence explicitly denies it, e.g. "does not", "is not").
-- modality: "necessary", "always", "typically", "possible", or "never" — how strongly
-  the sentence asserts the relation holds.
-- conditions: any conditions under which the relation holds, as short phrases from
-  the sentence (empty list if unconditional).
-- part_type: if the relation is about parts and wholes, one of "component",
-  "member", "phase" describing the part-whole type; otherwise null.
-- dimension: if the relation is a comparison, a short phrase naming what differs;
+- polarity: "affirmed" (the sentence states this relation holds) or "negated" (the sentence
+  explicitly denies it, e.g. "does not", "need not", "is independent of").
+- modality: "necessary", "always", "typically", "possible", or "never": how strongly the sentence
+  asserts the relation holds.
+- conditions: any conditions under which the relation holds, as short phrases from the sentence
+  (empty list if unconditional).
+- part_type: if the relation is about parts and wholes, one of "component", "member", "phase";
   otherwise null.
-- surface_phrase: an EXACT substring of the sentence above (copy character-for-
-  character) — the actual linking words connecting X and Y (e.g. "triggers",
-  "is a type of", "does not require").
+- dimension: if the relation is a comparison or a trade-off, a short phrase naming what differs or
+  trades off; otherwise null.
+- action_type: only for the relation acts_on, the class of the verb: send, receive, forward,
+  transform, check, store, drop, generate, or other; otherwise null.
+- surface_phrase: an EXACT substring of the sentence (copy character-for-character): the actual
+  linking words connecting X and Y (e.g. "triggers", "is a type of", "does not require").
+- corrects_intuition: true ONLY if the sentence explicitly warns against a belief (for example "a
+  common misconception", "it is tempting to think", "note that ... does not"); otherwise false.
+- intuition: when corrects_intuition is true, the belief being corrected, in one sentence; otherwise
+  null.
```

## 3. One real call, rendered from the LOGGED prompts (data/logs/llm_prompts.jsonl, by input hash)

Pair: **node** / **frame**. Sentence: "Recall from Chapter 1 that we are focusing on packet-switched networks, which means that blocks of data (called frames at this level), not bit streams, are exchanged between nodes."

**family** (task `relation_family`, prompt v3, model tier strong, input hash `53949a1e32ee`)

```
You are checking whether a sentence states a relation between two concepts, and if so, which broad
family it belongs to.

Concept X: node
Concept Y: frame

Sentence:
Recall from Chapter 1 that we are focusing on packet-switched networks, which means that blocks of data (called frames at this level), not bit streams, are exchanged between nodes.

Families (what each covers, and the relations inside it):
- mechanism_process: something acts or happens: an actor performs, triggers or precedes an activity, or handles a data unit (send, receive, forward, transform, check, store, drop) (relations: performs, triggers, precedes, acts_on)
- cause_effect: one thing brings about, prevents or changes the amount of another (relations: causes, prevents, increases, decreases)
- function_means: what something is for, or what it uses to achieve its purpose (relations: has_purpose, uses)
- dependency: one thing needs, requires or is constrained by another (including a stated absence of that need) (relations: requires)
- comparison: two things are alike, different or in tension along a stated dimension (relations: contrasts_with, equivalent_to, trades_off_with)
- classification_structure: what kind of thing something is, what it is made of, what it is attached or connected to, what carries or names it (relations: is_a, part_of, has_property, connected_to, identifies, encapsulates)
- no_relation: nothing meaningful is stated between these two concepts here
- other: a real relation is stated, but it does not fit any family above

Rules:
- If the sentence states OR DENIES a relation between X and Y, choose the family of that relation.
  A denial (for example "does not need", "is independent of") is recorded later as a qualifier, so
  do not answer no_relation or other for a denial.
- If X and Y are only listed together, only mentioned in the same sentence, or one merely sets the
  scene for the other, choose no_relation.
- Choose other only if the sentence really relates X and Y but none of the families above fits.

Give the family and a one-sentence reason.
```

**choice** (task `relation_choice`, prompt v3, model tier strong, input hash `2c1727b7e02b`)

```
You are picking the exact relation a sentence states between two concepts, within the "mechanism_process"
family already identified for this pair.

Concept X: node
Concept Y: frame

Sentence:
Recall from Chapter 1 that we are focusing on packet-switched networks, which means that blocks of data (called frames at this level), not bit streams, are exchanged between nodes.

Options. Each reading is filled in with the two concepts; give the relation name and the direction
of the reading that matches the sentence:
- performs: Actor/component/protocol source carries out activity target (an operation, procedure or algorithm step).
    forward  (X first): "node performs frame"
    reversed (Y first): "frame performs node"
    not uses: "TCP uses sliding window" (sliding window is a means/structure, not an activity the actor carries out)
    not triggers: "three duplicate ACKs triggers fast retransmit" (the source is an event, not an actor)
- triggers: By protocol rule, event/state source initiates action or state change target. Put the context in conditions.
    forward  (X first): "node triggers frame"
    reversed (Y first): "frame triggers node"
    not causes: "simultaneous transmission causes a collision" (a physical/logical consequence, not a designed protocol rule)
    not precedes: "slow start precedes congestion avoidance" (ordering only; the first does not initiate the second by rule)
- precedes: In a process or protocol, step/phase source happens before step/phase target.
    forward  (X first): "node happens before frame"
    reversed (Y first): "frame happens before node"
    not triggers: "timeout triggers retransmission" (the first initiates the second; use triggers)
    not part_of: "slow start part_of[phase] TCP congestion control" (membership of a phase in a process, not order)
- acts_on: Component, protocol or mechanism source does something to data unit target: sends, receives, forwards, transforms, checks, stores, drops or generates it. The verb class goes in action_type; the exact verb in surface_phrase.
    forward  (X first): "node handles frame (sends, receives, forwards, transforms, checks, stores or drops it)"
    reversed (Y first): "frame handles node (sends, receives, forwards, transforms, checks, stores or drops it)"
    not performs: "transparent bridge performs backward learning" (the target is an activity, not a thing being handled)
    not uses: "TCP uses sequence numbers" (a means the actor relies on, not an object it acts on)
    not encapsulates: "an Ethernet frame carries an IP packet" (containment between two data units; no actor)
- no_relation: X and Y are only listed together or co-mentioned; no relation is stated between them
- other: the sentence relates X and Y, but none of the relations above fits

Rules:
- Pick the reading the sentence actually states. If the sentence states OR DENIES a relation, choose
  that relation: a denial is recorded by the polarity qualifier in a later step, so it is not a
  reason to choose no_relation or other.
- If X and Y are only listed together or co-mentioned, choose no_relation.
- direction is "forward" for a reading that names X first, "reversed" for a reading that names Y
  first; send "forward" for symmetric relations, no_relation and other.
- Choose other only if the sentence relates X and Y but no option fits. Then other_description (one
  sentence saying what the sentence expresses) and other_suggested_label (a 1 to 3 word verb phrase,
  such as "connects" or "is carried in") are REQUIRED. For every other answer both are null.
- For contrasts_with and trades_off_with, comparison_dimension is REQUIRED: the dimension along which
  the two differ or trade off, named in the sentence. If the sentence names no dimension, choose
  no_relation instead. For every other relation comparison_dimension is null.

evidence_quote: an EXACT substring of the sentence (copy character-for-character) that states the
relation, and it must contain both X and Y (or their names).
statement: a one-sentence paraphrase of the relation in your own words, naming both concepts.
```

**qualifiers** (task `relation_qualifiers`, prompt v3, model tier strong, input hash `8b10494ff846`)

```
The relation "acts_on" was just identified between two concepts in this sentence:

Concept X: node
Concept Y: frame
Relation statement: Nodes exchange frames with one another.

Sentence:
Recall from Chapter 1 that we are focusing on packet-switched networks, which means that blocks of data (called frames at this level), not bit streams, are exchanged between nodes.

Give:
- polarity: "affirmed" (the sentence states this relation holds) or "negated" (the sentence
  explicitly denies it, e.g. "does not", "need not", "is independent of").
- modality: "necessary", "always", "typically", "possible", or "never": how strongly the sentence
  asserts the relation holds.
- conditions: any conditions under which the relation holds, as short phrases from the sentence
  (empty list if unconditional).
- part_type: if the relation is about parts and wholes, one of "component", "member", "phase";
  otherwise null.
- dimension: if the relation is a comparison or a trade-off, a short phrase naming what differs or
  trades off; otherwise null.
- action_type: only for the relation acts_on, the class of the verb: send, receive, forward,
  transform, check, store, drop, generate, or other; otherwise null.
- surface_phrase: an EXACT substring of the sentence (copy character-for-character): the actual
  linking words connecting X and Y (e.g. "triggers", "is a type of", "does not require").
- corrects_intuition: true ONLY if the sentence explicitly warns against a belief (for example "a
  common misconception", "it is tempting to think", "note that ... does not"); otherwise false.
- intuition: when corrects_intuition is true, the belief being corrected, in one sentence; otherwise
  null.
```

Structured outputs the model returned:

```json
{
 "family": "mechanism_process",
 "relation": "acts_on",
 "direction": "forward",
 "statement": "Nodes exchange frames with one another.",
 "evidence_quote": "frames at this level), not bit streams, are exchanged between nodes",
 "qualifiers": {
  "polarity": "affirmed",
  "modality": "necessary",
  "conditions": [
   "packet-switched networks"
  ],
  "part_type": null,
  "dimension": null,
  "action_type": "send",
  "surface_phrase": "are exchanged between",
  "corrects_intuition": false,
  "intuition": null
 }
}
```

## 4. Pilot: where the 114 CR-005 OTHER pairs land (run `pilot_0ed8eb73`, strong tier, $0.787, 222 calls)

| outcome | pairs | share |
|---|---|---|
| accepted edge | 27 | 23.7% |
| NO_RELATION | 36 | 31.6% |
| still OTHER (with description + suggested label) | 35 | 30.7% |
| rejected by a check | 16 | 14.0% |

Reasons behind the non-edges: relation_other 35, family_no_relation 33, endpoint_not_grounded 13, domain_range 3, comparison_no_grounded_dimension 2, relation_no_relation 1.

Accepted edges by relation: acts_on 15, connected_to 5, uses 2, requires 2, has_property 1, part_of 1, is_a 1.

New relations among the 27: **acts_on 15, connected_to 5** (20 of 27); gated relations `identifies`, `encapsulates`, `trades_off_with`: **0 instances** in this pilot (they can only reach 5 in the ch1-3 re-run, so their gate may well fail).

### The 27 accepted edges

| subject | relation (action / polarity) | object | sentence |
|---|---|---|---|
| node | acts_on / other / affirmed | bit | The first is encoding bits onto the transmission medium so that they can be understood by a receiving node. |
| host | connected_to / affirmed | cloud | So we also need to address the similar problem of connecting a host to a cloud. |
| link | connected_to / affirmed | router | At one end of the spectrum, network operators that build global networks must deal with links that span hundreds or thousands of kilometers connecting refrigerator-sized  |
| encoding | acts_on / transform / affirmed | bit | Let’s return to the problem of encoding bits onto signals. |
| encoding | acts_on / transform / affirmed | signal | Let’s return to the problem of encoding bits onto signals. |
| Manchester encoding | acts_on / transform / affirmed | signal | An alternative, called Manchester encoding, does a more explicit job of merging the clock with the signal by transmitting the exclusive OR of the NRZ-encoded data and the |
| link | connected_to / affirmed | node | The first step in turning nodes and links into usable building blocks is to understand how to connect them in such a way that bits can be transmitted from one node to the |
| node | acts_on / transform / affirmed | signal | The task, therefore, is to encode the binary data that the source node wants to send into the signals that the links are able to carry and then to decode the signal back  |
| framing | uses / affirmed | frame | 2.3.1 Byte-Oriented Protocols (PPP)  One of the oldest approaches to framing—it has its roots in connecting terminals to mainframes—is to view each frame as a collection  |
| node | acts_on / send / affirmed | frame | Recall from Chapter 1 that we are focusing on packet-switched networks, which means that blocks of data (called frames at this level), not bit streams, are exchanged betw |
| frame | has_property / affirmed | Sequence number | To address this problem, the header for a stop-and-wait protocol usually includes a 1-bit sequence number—that is, the sequence number can take on the values 0 and 1—and  |
| protocol | acts_on / send / affirmed | ACK | An acknowledgment (ACK for short) is a small control frame that a protocol sends back to its peer saying that it has received an earlier frame. |
| buffer | acts_on / store / affirmed | frame | Notice that the sender has to be willing to buffer up to SWS frames since it must be prepared to retransmit them until they are acknowledged. |
| host | acts_on / transform / affirmed | frame | Minimally, a frame must contain at least 46 bytes of data, even if this means the host has to pad the frame before transmitting it. |
| frequency hopping | uses / affirmed | frequency | (Spread spectrum was originally designed for military use, so these “other devices” were often attempting to jam the signal.) For example, frequency hopping is a spread s |
| switch | acts_on / forward / affirmed | packet | The core job of a switch is to take packets that arrive on an input and forward (or switch) them to the right output so that they will reach their appropriate destination |
| multiple-access network | part_of / affirmed | network | To build a global network, we need a way to interconnect these different types of links and multi-access networks. |
| host | connected_to / affirmed | switch | A star topology has several attractive properties:  -  Even though a switch has a fixed number of inputs and outputs, which limits the number of hosts that can be connect |
| host | acts_on / send / affirmed | packet | Datagram networks have the following characteristics:  -  A host can send a packet anywhere at any time, since any packet that turns up at a switch can be immediately for |
| switch | acts_on / transform / affirmed | header | One entry in the VC table on a single switch contains:  -  A virtual circuit identifier (VCI) that uniquely identifies the connection at this switch and which will be car |
| datagram | is_a / affirmed | packet | 3.1.1 Datagrams  The idea behind datagrams is incredibly simple: You just include in every packet enough information to enable any switch to decide how to get it to its d |
| switch | acts_on / forward / affirmed | frame | (The IEEE 802.1 specification is based on this algorithm.) In practice, this means that each switch decides the ports over which it is and is not willing to forward frame |
| bridge | acts_on / receive / affirmed | frame | In their simplest variants, bridges simply accept LAN frames on their inputs and forward them out on all other outputs. |
| host | connected_to / affirmed | local area network | Then, whenever the bridge receives a frame on port 1 that is addressed to host A, it would not forward the frame out on port 2; there would be no need because host A woul |
| bridge | requires / negated | port | Whenever a frame from host A that is addressed to host B arrives on port 1, there is no need for the bridge to forward the frame out over port 2. |
| forwarding | acts_on / forward / affirmed | packet | Such a device, running suitable software, can receive packets on one of its interfaces, perform any of the switching or forwarding functions described in this chapter, an |
| data plane | requires / affirmed | control plane | The exact same control plane software stack used in a software switch still runs on the control CPU, but in addition, data plane “programs” are loaded onto the NPU to ref |

These 27 are the model's readings, **unjudged**; the owner's blind sheet at STOP 4 is what measures precision. Two things visible already: the negated dependency the audit worried about is now recorded as `bridge requires port` with polarity `negated` (the model no longer avoids the relation), and `acts_on` captures the actor -> thing-handled sentences that made up the largest OTHER theme.

### Still OTHER: 35 pairs, each with the model's own description and label

| family | X / Y | suggested label | what the sentence expresses |
|---|---|---|---|
| classification_structure | network / Internet Service Provider | has a network | The sentence describes an Internet Service Provider connecting a new customer to its network, rather than stating that the network is a component of t |
| classification_structure | signal / binary data | encodes | The sentence says that binary data is represented through encoding in the signal. |
| mechanism_process | network / network operator | builds | The sentence states that network operators build global networks. |
| mechanism_process | bit / signal | is converted into | The sentence describes conversion between bits and signals in both directions. |
| classification_structure | signal / transition | is a change in | The sentence describes a transition as a change in the signal’s value. |
| mechanism_process | bit / clock | paces | The sentence expresses that bit transmission and recovery occur once per clock cycle. |
| mechanism_process | encoding / clock | is driven by | The sentence says that a clock drives the encoding process. |
| classification_structure | link / frame | transmits bits of | Bits arriving over the link are collected to form the corresponding frame. |
| classification_structure | bit / single-bit error | affects | The term single-bit error describes an error that affects one bit, not an error of which a bit is a component. |
| classification_structure | link / protocol | operates at | The sentence describes protocols as operating at the link level. |
| classification_structure | Internet / protocol | is associated with | The sentence describes the protocols as Internet protocols without stating that either concept is a subtype or part of the other. |
| comparison | SWS / RWS | can equal | The sentence describes a configuration in which RWS is set equal to SWS, not an equivalence between the two concepts. |
| classification_structure | host / repeater | are positioned between | The sentence limits how many repeaters can be positioned between two hosts. |
| mechanism_process | frame / collision | is involved in | The sentence describes a frame being involved in a collision with another frame. |
| mechanism_process | network / host | transmits onto | The host places a signal on the Ethernet, and that signal is broadcast across the network. |
| classification_structure | host / bit | addressed using | The sentence specifies the bit length of the address used to identify a host. |
| classification_structure | Internet Service Provider / PON | starts in | The sentence says that PON begins at a point in the Internet Service Provider’s network. |
| comparison | network operator / cloud | heads toward conflict | The sentence says network operators and cloud providers are on a collision course as functionality moves toward the network edge. |
| mechanism_process | network / internetworking | interconnects | The sentence defines internetworking as the interconnection of different types of networks. |
| classification_structure | Internet / internetworking | is based on | The sentence says that internetworking is the name for the core idea behind the Internet. |
| function_means | link / switch | interconnects | The sentence says that switches are devices that interconnect links of the same type. |
| mechanism_process | packet / output | is forwarded to | The sentence describes a packet being forwarded to an output, rather than the packet or output performing an action on the other. |
| mechanism_process | switch / Designated switch | elects | The sentence states that a switch elects another switch as the designated switch. |
| classification_structure | switch / address | records in table | The sentence says that no switch has the destination address in its forwarding table. |
| classification_structure | host / Internet protocol | runs on | The sentence states that Internet protocol runs on hosts. |
| dependency | path / routing | establishes path | Routing is considered for the connection request, while subsequent packets follow the same path as that request. |
| classification_structure | node / routing table | records route to | The routing table records a next hop for reaching a node, rather than containing or identifying the node itself. |
| mechanism_process | packet / main memory | is copied into | The sentence identifies main memory as the destination for bytes copied from the packet by NIC 1. |
| classification_structure | local area network / tenant | is assigned | The sentence says each tenant can be assigned a dedicated local area network. |
| comparison | virtual machine / physical machine | has features of | The sentence says that a virtual machine has all the features of a physical machine. |
| mechanism_process | network / virtualization | virtualizes | The sentence says that virtualization applies to every aspect of the network. |
| mechanism_process | network / network virtualization | virtualizes | The sentence says network virtualization extends to every aspect of networking, rather than handling a data unit. |
| classification_structure | local area network / Internet protocol | runs on top of | The sentence describes a virtual local area network operating over an Internet protocol-based network. |
| classification_structure | local area network / virtual network | runs over | The sentence describes the virtual network as layered above an IP-based network that may run within a VLAN. |
| classification_structure | Internet protocol / Virtual LAN | runs within | The sentence says that an Internet protocol–based network can run within a Virtual LAN. |

**Themes in the remaining OTHER (evidence for a later registry version, nothing added here):** layering / 'runs on' (labels runs on, runs over, runs within, runs on top of, operates at: about 5), 'interconnects' (3), 'virtualizes' (3), encoding / converting (encodes, is converted into: 3), 'is driven by / paces' (2), plus singletons (elects, records in table, starts in, is copied into, is forwarded to). Registry v1.2+ candidates, to be decided by a CR, not by this run.

### Rejected by a check: 16 pairs

- **`endpoint_not_grounded`: 13.** For 11 of them an endpoint is not a longest-match mention even anywhere in the sentence (for example `bit` appearing only inside a longer concept). These pairs were proposed by CR-005's substring matching and **the new longest-match enumeration would never propose them**, so this is the granularity fix working, not lost recall. Only 2 (host / Ethernet, Ethernet / switch) are grounded in the sentence but not in the evidence quote; sentence-scope grounding would rescue those 2 (7% of the 27 edges) at the cost of no longer guaranteeing that the quote itself names both endpoints. **Kept at quote scope as the CR says; owner may relax.**
- **`domain_range`: 3** (`has_purpose` node -> access point, `has_purpose` link -> packet, `uses` Virtual LAN -> tenant): all three look like genuine type errors, so the check is not over-strict here.

### Estimated effect on the OTHER share

If the other 267 CR-005 pairs behaved as before, the slice-level OTHER share would fall from 30.7% (117 of 381) to about **9%** (35 of 381), under the CR's 15% expectation. This is an extrapolation from the pilot only; the re-run measures it.

## 5. Pair selection (owner-approved change), measured offline on the CR-005 ch2-3 candidates ($0)

Longest-match enumeration cuts the unique candidate pairs from 5,824 to **3,360** (substring matching created pairs from concepts hidden inside longer terms). CR-005 classified 381 pairs and touched 152 of 736 concepts. Coverage-aware selection at the SAME budget of 381 pairs (per-section minimum 8, defined/used coverage, then fill):

| budget | concepts in a selected pair | defined/used concepts covered (of 595 that have any candidate) |
|---|---|---|
| 381 (= CR-005) | 471 | 458 |
| 480 | 608 | 595 (all) |
| 700 | 611 | 595 (all) |

Attempted coverage is not linked coverage: it is the ceiling the classifier then works within. For the ch1-3 re-run the global budget is about 700 pairs; a random sample of 50 unselected pairs is also classified (about $0.25) to estimate the missed-relation rate with a Wilson CI.

## 6. Cost and safety

Pilot $0.787 (222 backend calls; cap $2.00, pre-approved). CR-007 spend so far about $1.0 of the $20 hard cap. All calls through `LLMClient` with the stage budget cap; exact prompts logged; tests use fixtures only.

## 7. What I need from the owner at STOP 3

1. Approve (or edit) the registry v1.1 YAML: the two core relations, the three gated ones, `Identifier`, the qualifiers and the family glosses.
2. Approve the prompt v3 diffs (filled options, negation and lists rules, OTHER needs description and label, comparison dimension rule).
3. Grounding scope: keep the quote (as the CR says) or relax to the sentence (rescues 2 of 27 in the pilot).
4. Go ahead with the ch1-3 re-run (§6, about $6 to $10).
