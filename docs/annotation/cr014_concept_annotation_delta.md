# CR-014 concept annotation — delta guide (pilot sections)

Base rules: `docs/annotation/pd_e2e_codebook.md` (CONCEPT / MENTION rows, `node_type`, identity rule). This delta only adds what the span-exact concept benchmark needs. You are shown **no system output**; do not look at any CR-014 prediction before the sheet is frozen.

Files: `data/interim/checks/cr014/pd_concept_pilot_text.txt` (numbered sentences of the two pilot sections), `pd_concept_pilot_sentences.csv` (same, with character offsets), and the blank sheet `pd_concept_pilot_blind.csv` to fill in.

## What to annotate
Exhaustive at section level: **every** concept the section names or uses, not only the important ones. One row per mention.

| row_type | fields |
|---|---|
| `CONCEPT` | `concept_id`, `canonical_name`, `node_type`, `aliases` (`|` separated) |
| `MENTION` | `sentence_id`, `span_text` (copied EXACTLY from that sentence), `occurrence` (1, 2, ... for repeated text in the sentence), `concept_id`, `nested_valid`, `boundary_notes` |

## Delta rules
1. **Exact surface span.** `span_text` is the whole term as the text uses it, copied character for character. No extra general adjectives; keep technical modifiers ("TCP congestion control", not "the TCP congestion control").
2. **Nested concepts.** If both an inner and an outer term are valid concepts in that sentence ("congestion control" inside "TCP congestion control"), annotate both as separate MENTION rows and set `nested_valid=yes` on the inner one. If the inner words are only part of a longer term and not a concept on their own there, annotate only the outer term.
3. **Ambiguous boundaries.** When two boundaries are both defensible, choose the one you would put in a glossary, and write the alternative in `boundary_notes`. Leave `boundary_notes` empty otherwise.
4. **One-word concepts** are concepts when the field gives them a specific meaning ("router", "bandwidth", "frame"); generic discourse words are not.
5. **Proposal vs final concept.** Annotate concepts, not candidates: do not mark a phrase because a program might extract it. Values (numbers, sizes), clauses and lists are not concepts.
6. Mentions of the same concept share a `concept_id` (plurals, abbreviations, short forms) exactly as in the base codebook.

## Process
- Annotate before looking at any system output. Freeze (commit) the sheet to `data/gold/` yourself; code never writes there.
- If a second annotator is available, give them a frozen subset; if not, agreement is reported as `NOT_EVALUABLE` (no LLM substitutes for the second human).
- Pilot sections are development data and never contribute to held-out results.
