# REL-MAP-180 annotation guide (blind)

You see 180 short evidence passages, each with two concepts (A, B). Judge what the TEXT says. You are not shown any
system output; do not look for it. Work on a copy saved as `data/gold/cr010_relmap180_blind_sheet_annotator1.csv`.

## Columns to fill

| column | allowed values |
|---|---|
| annotator_id | your id (every row) |
| current_semantic_relation_judgement | one relation name from the list below, or `none` (the text states no relation between A and B), or `other` (a relation the list lacks; say which in notes) |
| direction_judgement | `a_to_b` (A is the first term of the relation as written in its template), `b_to_a`, `symmetric`, `not_applicable` |
| erst_applies_yes_no | `yes` if the two concepts sit in different discourse units that stand in one of the discourse relations below; `no` if both are in one unit or no discourse relation links them |
| erst_relation_1 / erst_relation_2_optional | an eRST label below (the second only for a concurrent relation); leave blank when erst_applies is `no` |
| nuclearity_judgement_if_relevant | `nucleus_a`, `nucleus_b` (the unit holding that concept is the nucleus), `both_nuclei` (multinuclear), `either`, `not_applicable` |
| machine_useful_meaning_survives_yes_no | `yes` if the eRST judgement alone would still let a program recover what you wrote in the semantic-relation column (kind, part, mechanism, direction, ...); `no` if something useful is lost |
| loss_* (11 columns) | `yes` only for the kinds of information that would be lost; otherwise leave blank |
| other_loss_notes, annotator_notes | free text |

Loss kinds: taxonomy; part/whole composition; mechanism; network topology; identifier semantics; encapsulation/payload semantics; causal sign/direction; technical dependency; trade-off semantics; pedagogical prerequisite; principle-instance organisation.

## Semantic relations (registry v1.3)

| name | definition | template |
|---|---|---|
| performs | Actor/component/protocol source carries out activity target (an operation, procedure or algorithm step). | {X} performs {Y} |
| triggers | By protocol rule, event/state source initiates action or state change target. Put the context in conditions. | {X} triggers {Y} |
| precedes | In a process or protocol, step/phase source happens before step/phase target. | {X} happens before {Y} |
| acts_on | Component, protocol or mechanism source does something to data unit target: sends, receives, forwards, transforms, checks, stores, drops or generates it. The verb class goes in action_type; the exact verb in surface_phrase. | {X} handles {Y} (sends, receives, forwards, transforms, checks, stores or drops it) |
| causes | Source brings about target as a consequence (not a designed protocol rule). | {X} causes {Y} |
| prevents | Source stops or avoids target from happening. | {X} prevents {Y} |
| increases | More/activation of source raises the value of target (qualitative proportionality +). Advantages/disadvantages = increases/decreases on quality attributes (throughput, delay, overhead, efficiency). | {X} increases {Y} |
| decreases | More/activation of source lowers the value of target (qualitative proportionality −). | {X} decreases {Y} |
| has_purpose | Source (a designed mechanism, protocol, field or component) exists or is used in order to achieve goal target. | {X} exists in order to achieve {Y} |
| uses | Source employs target as a means, mechanism or data structure to do its job. | {X} uses {Y} |
| requires | Source cannot work or be valid unless target holds (a technical dependency or constraint). Put the context in conditions. | {X} cannot work unless {Y} |
| is_a | Source is a kind/subtype of target. | {X} is a kind of {Y} |
| part_of | Source is a part of target. REQUIRED qualifier part_type: component (field/module of a structured whole), member (element of a collection/group), phase (step/stage of a process). | {X} is part of {Y} |
| has_property | Source has the characteristic, behaviour, value or constraint named by target. | {X} has the property {Y} |
| connected_to | Component source is physically or logically linked to component target so the two can exchange data directly (network topology). | {X} is directly connected to {Y} |
| contrasts_with | Source and target are commonly compared and differ; name what differs in the dimension qualifier and state it in the statement. Use for confusable pairs. | {X} differs from {Y} |
| prerequisite_of | Understanding source is needed to understand target (educational dependency; NOT book order). | understanding {X} is needed to understand {Y} |

## eRST discourse relations (31; `SAME-UNIT` is a technical label and is never used)

Nuclearity: `→←` satellite relation in either direction; `Λ` multinuclear; `←` the nucleus comes first and the satellite after; `→` the satellite comes first.

| label | nuclearity | definition |
|---|---|---|
| ADVERSATIVE-ANTITHESIS | →← | Reader is meant to prefer the nucleus as an alternative to the satellite. |
| ADVERSATIVE-CONCESSION | →← | Reader is meant to look past an incompatibility of nucleus with satellite. |
| ADVERSATIVE-CONTRAST | Λ | Writer presents multiple nuclei as incompatible but equally prominent. |
| ATTRIBUTION-NEGATIVE | →← | Satellite states that a potential source is not a source of the information in the nucleus. |
| ATTRIBUTION-POSITIVE | →← | Satellite states a source for the information in the nucleus. |
| CAUSAL-CAUSE | →← | Satellite is the cause of the nucleus; nucleus is more prominent. |
| CAUSAL-RESULT | →← | Satellite is the result of the nucleus; equivalently the nucleus is the cause of the satellite and is more prominent. |
| CONTEXT-BACKGROUND | →← | Satellite provides information that increases the reader’s understanding of the nucleus. |
| CONTEXT-CIRCUMSTANCE | →← | Satellite gives circumstances, often spatio-temporal, under which the nucleus applies. |
| CONTINGENCY-CONDITION | →← | The nucleus occurs depending on the satellite. |
| ELABORATION-ADDITIONAL | ← | Satellite elaborates on the nucleus as a whole in cases not covered by attribute elaboration. |
| ELABORATION-ATTRIBUTE | ← | Satellite elaborates on a participant within the nucleus rather than on the entire proposition. |
| EVALUATION-COMMENT | →← | Satellite provides the writer’s assessment of the nucleus; the reader need not share it. |
| EXPLANATION-EVIDENCE | →← | Satellite provides evidence that increases the reader’s belief in the nucleus. |
| EXPLANATION-JUSTIFY | →← | Satellite increases the reader’s acceptance of the writer’s right to say the nucleus. |
| EXPLANATION-MOTIVATION | →← | Satellite is meant to influence the reader’s willingness to act according to the nucleus. |
| JOINT-DISJUNCTION | Λ | Writer presents multiple nuclei as interchangeable alternatives. |
| JOINT-LIST | Λ | Writer presents multiple nuclei in parallel as additive to one another. |
| JOINT-OTHER | Λ | Other collection of unlike discourse units of equal prominence at the same level of hierarchy. |
| JOINT-SEQUENCE | Λ | Multiple nuclei form a temporally ordered sequence of events. |
| MODE-MANNER | →← | Satellite indicates the manner in which the nucleus happens. |
| MODE-MEANS | →← | Satellite indicates the means by which the nucleus happens. |
| ORGANIZATION-HEADING | → | Explicit text-organizing device such as a heading. |
| ORGANIZATION-PHATIC | →← | Writer holds the floor without contributing propositional content. |
| ORGANIZATION-PREPARATION | → | Satellite is primarily used to signal an upcoming nucleus. |
| PURPOSE-ATTRIBUTE | →← | Satellite gives the purpose of a participant in the nucleus rather than the entire proposition. |
| PURPOSE-GOAL | →← | The proposition in the nucleus exists or is initiated in order to realize the satellite. |
| RESTATEMENT-PARTIAL | ← | Satellite partly realizes the same role and content as a previous nucleus. |
| RESTATEMENT-REPETITION | Λ | Multiple nuclei realize the same role and content. |
| TOPIC-QUESTION | → | Nucleus is the answer to the question posed by the satellite. |
| TOPIC-SOLUTIONHOOD | →← | Nucleus is a solution to a problem presented by the satellite. |

Do not skip rows. A row you cannot judge: `none` / `no` and say why in annotator_notes.
