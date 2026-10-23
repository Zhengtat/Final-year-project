---
task: concept_extraction
version: v3x
schema: ConceptExtractionLLM
notes: >
  CR-007 §3.2 EXPERIMENT TEMPLATE (dev ablation only; the chosen combination is materialised as
  v3.md afterwards, so no version that produced saved results is ever edited -- CLAUDE.md rule 8).
  v3x = v2 plus four optional blocks that render to an empty string when off:
  {codebook_block} (E1: FACE code-book conventions in our own words), {granularity_block} (E5),
  {few_shot_block} (E4: leave-one-section-out examples from OTHER dev sections) and {pass_note}
  (E2: per-run variation). With all four empty it is v2 with different whitespace. Block texts live
  in prompts/concept_extraction/blocks_v3x/. All examples are networking-only and contain no term
  from the IIR gold sets.
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

{codebook_block}{granularity_block}Section heading: {heading_path}

{few_shot_block}
Candidate terms noticed in this section (from noun-chunk statistics -- use these as
hints, but don't be limited to them; also don't include every one if it isn't
actually a domain concept):
{candidate_terms}

Section text:
{section_text}
{pass_note}
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
