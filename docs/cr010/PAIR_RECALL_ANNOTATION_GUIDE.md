# Pair-recall annotation guide (CR-010 STOP 4, 450 pairs)

You will see 450 concept pairs with the text they were found in. For each pair decide, **from the text shown**, whether
that text states a relation between concept A and concept B. You are not told where a pair came from or what any system
decided. Do not look at model output.

Fill exactly these columns (the first five are pre-filled):

| column | values |
|---|---|
| `true_relation_exists` | `yes` — the shown text states or clearly implies a relation between A and B that a knowledge graph of this textbook should hold; `no` — they merely co-occur, are listed together, or are unrelated; `unclear` — you cannot decide (use rarely, say why in `notes`) |
| `relation_if_yes` | one relation name from the list below, or `other` (say what in `notes`). Leave empty if `no`/`unclear` |
| `direction_if_yes` | `a_to_b` — the relation reads "A *relation* B"; `b_to_a` — reads "B *relation* A"; `symmetric`. Empty if no relation |
| `evidence_supported` | `yes` — the shown text itself supports the relation; `no` — it is true only from your own knowledge or from text not shown. Empty (or `na`) if no relation |
| `notes` | free text, optional |

Rules: judge the relation between **these two concepts**, not between words near them. A list ("TCP, UDP and IP") is not a
relation. A pair whose evidence is two sentences may relate across the sentences. Concepts are judged as named; if a name is
a clearly wrong match for the words in the text, answer `no` and say so in `notes`.

Relations (registry):

- `performs` — {X} performs {Y} (Actor/component/protocol source carries out activity target (an operation, procedure or algorithm step).)
- `triggers` — {X} triggers {Y} (By protocol rule, event/state source initiates action or state change target. Put the context in conditions.)
- `precedes` — {X} happens before {Y} (In a process or protocol, step/phase source happens before step/phase target.)
- `acts_on` — {X} handles {Y} (sends, receives, forwards, transforms, checks, stores or drops it) (Component, protocol or mechanism source does something to data unit target: sends, receives, forwards, transforms, checks, stores, drops or generates it. The verb class goes in action_type; the exact verb in surface_phrase.)
- `causes` — {X} causes {Y} (Source brings about target as a consequence (not a designed protocol rule).)
- `prevents` — {X} prevents {Y} (Source stops or avoids target from happening.)
- `increases` — {X} increases {Y} (More/activation of source raises the value of target (qualitative proportionality +). Advantages/disadvantages = increases/decreases on quality attributes (throughput, delay, overhead, efficiency).)
- `decreases` — {X} decreases {Y} (More/activation of source lowers the value of target (qualitative proportionality −).)
- `has_purpose` — {X} exists in order to achieve {Y} (Source (a designed mechanism, protocol, field or component) exists or is used in order to achieve goal target.)
- `uses` — {X} uses {Y} (Source employs target as a means, mechanism or data structure to do its job.)
- `requires` — {X} cannot work unless {Y} (Source cannot work or be valid unless target holds (a technical dependency or constraint). Put the context in conditions.)
- `is_a` — {X} is a kind of {Y} (Source is a kind/subtype of target.)
- `part_of` — {X} is part of {Y} (Source is a part of target. REQUIRED qualifier part_type: component (field/module of a structured whole), member (element of a collection/group), phase (step/stage of a process).)
- `has_property` — {X} has the property {Y} (Source has the characteristic, behaviour, value or constraint named by target.)
- `connected_to` — {X} is directly connected to {Y} (Component source is physically or logically linked to component target so the two can exchange data directly (network topology).)
- `contrasts_with` — {X} differs from {Y} (Source and target are commonly compared and differ; name what differs in the dimension qualifier and state it in the statement. Use for confusable pairs.)
- `prerequisite_of` — understanding {X} is needed to understand {Y} (Understanding source is needed to understand target (educational dependency; NOT book order).)

Save your marked copy to `data/gold/` (the code never writes there) and check it with
`uv run python -m cumap.cr010.pair_recall validate --sheet <your file>`.
