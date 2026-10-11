# P&D-E2E annotation codebook (CR-012)

You are building an independent GOLD knowledge graph for whole textbook sections. Annotate EXHAUSTIVELY what the text states: every
concept mention, which mentions are the same concept, and every relation the text supports. You are not shown any system output
and must not look at any. A language model may suggest, but you are the ground truth; nothing here is written for you.

Sheets: `data/interim/checks/cr012/pd_e2e_pilot_blind.csv` (pilot: 1.5 (3643 words), 2.6 (2921 words)) and `pd_e2e_test_blind.csv` (held-out: 4.4 (4091 words), 5.4 (4597 words), 6.3 (4108 words), 7.1 (4799 words), 8.2 (4110 words), 9.3 (5093 words), 4.5 (3255 words)).
Held-out sections 4.4, 9.3 are annotated independently by two people when a second human exists
(an LLM is not a second human). Save your marked copy in the human-owned gold folder; code never writes there.

## How the sheet works
The sheet has one `SECTION` row and one `SENTENCE` row per sentence (pre-filled). ADD rows of these types (any order, same file):

| row_type | fill these columns |
|---|---|
| `CONCEPT` | `concept_id` (your own id, e.g. C001), `canonical_name`, `node_type`, `aliases` (separated by `|`) |
| `MENTION` | `sentence_id`, `span_text` (copied EXACTLY from that sentence), `occurrence` (1 for the first occurrence of that text in the sentence, 2 for the second...), `concept_id` |
| `RELATION` | `source_concept_id`, `relation`, `target_concept_id`, `qualifiers` (`name=value` separated by `|`), `evidence_sentence_ids` (separated by `|`) |
| `NOT_SAME` | `concept_id`, `not_same_concept_id` (two concepts that look alike but are different, where this could be confused) |

Put your id in `annotator_id` on every row you add. Use `notes` freely.

## Concepts and mentions
- One CONCEPT per real concept in the section; every mention of it (full forms, short forms, abbreviations, plurals) is a MENTION row of the same `concept_id`.
- Annotate the whole noun phrase, dropping purely general adjectives; split coordinations; abbreviations in brackets are mentions of the same concept.
- Different senses, kinds, parts, versions, predecessors, or process-versus-entity are DIFFERENT concepts (CR-008 identity rule). When two things could be confused, add a NOT_SAME row.
- `node_type` is one of: Protocol, Mechanism, Component, DataUnit, Parameter, Property, Event, State, Layer, Concept, Identifier.

## Relations
- A RELATION says what the text supports between two concepts, source then target as in the template below. Direction matters except for symmetric relations.
- Give the relation-specific qualifiers in the last column (for example part_type for part_of); polarity and modality are optional notes. Give at least one evidence sentence. Do not enumerate absence of relation: no NO_RELATION rows.
- Annotate only relations the text states or clearly implies. A list or co-mention is not a relation.

| relation | definition | template | required qualifiers |
|---|---|---|---|
| `performs` | Actor/component/protocol source carries out activity target (an operation, procedure or algorithm step). | {X} performs {Y} | - |
| `triggers` | By protocol rule, event/state source initiates action or state change target. Put the context in conditions. | {X} triggers {Y} | - |
| `precedes` | In a process or protocol, step/phase source happens before step/phase target. | {X} happens before {Y} | - |
| `acts_on` | Component, protocol or mechanism source does something to data unit target: sends, receives, forwards, transforms, checks, stores, drops or generates it. The verb class goes in action_type; the exact verb in surface_phrase. | {X} handles {Y} (sends, receives, forwards, transforms, checks, stores or drops it) | action_type |
| `causes` | Source brings about target as a consequence (not a designed protocol rule). | {X} causes {Y} | - |
| `prevents` | Source stops or avoids target from happening. | {X} prevents {Y} | - |
| `increases` | More/activation of source raises the value of target (qualitative proportionality +). Advantages/disadvantages = increases/decreases on quality attributes (throughput, delay, overhead, efficiency). | {X} increases {Y} | - |
| `decreases` | More/activation of source lowers the value of target (qualitative proportionality −). | {X} decreases {Y} | - |
| `has_purpose` | Source (a designed mechanism, protocol, field or component) exists or is used in order to achieve goal target. | {X} exists in order to achieve {Y} | - |
| `uses` | Source employs target as a means, mechanism or data structure to do its job. | {X} uses {Y} | - |
| `requires` | Source cannot work or be valid unless target holds (a technical dependency or constraint). Put the context in conditions. | {X} cannot work unless {Y} | - |
| `is_a` | Source is a kind/subtype of target. | {X} is a kind of {Y} | - |
| `part_of` | Source is a part of target. REQUIRED qualifier part_type: component (field/module of a structured whole), member (element of a collection/group), phase (step/stage of a process). | {X} is part of {Y} | part_type |
| `has_property` | Source has the characteristic, behaviour, value or constraint named by target. | {X} has the property {Y} | - |
| `connected_to` | Component source is physically or logically linked to component target so the two can exchange data directly (network topology). | {X} is directly connected to {Y} | - |
| `contrasts_with` | Source and target are commonly compared and differ; name what differs in the dimension qualifier and state it in the statement. Use for confusable pairs. | {X} differs from {Y} | - |
| `prerequisite_of` | Understanding source is needed to understand target (educational dependency; NOT book order). | understanding {X} is needed to understand {Y} | - |

## Agreement
If a second human annotates the same sections independently, we report concept, relation, direction and SAME / NOT_SAME agreement. Disagreements are adjudicated only after both sheets are frozen.
