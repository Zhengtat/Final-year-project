# CR-011 SLEEP-240 Blind Annotation Codebook

## Question

For each pair, answer only:

> **Would merging these two nodes remove a conceptual distinction that the textbook or domain needs?**

Do not try to predict what the system will do.

## Decisions

### `SAME`

Use when both records are alternate names/forms for one concept.

Evidence that may support `SAME` includes:

- long form and unambiguous acronym;
- explicitly stated alias;
- purely orthographic / hyphen / plural variation where sense is unchanged;
- interchangeable naming with compatible definitions and usages.

### `NOT_SAME`

Use when keeping two conceptual identities is necessary.

Typical reasons:

- broader/narrower;
- kind-of;
- instance-of;
- whole/part;
- process/mechanism vs component/entity;
- field/value;
- predecessor/version;
- similar-purpose alternative;
- confusable terms;
- same surface word used in a different technical sense;
- other related-but-distinct concepts;
- unrelated concepts.

### `UNSURE`

Use when the supplied evidence is insufficient to decide identity confidently. Do **not** infer sameness from similar wording, nearby occurrence or similar graph neighbourhood.

`UNSURE` is a mandatory review outcome, not an automatic negative.

## `different_kind`

When `decision = NOT_SAME`, choose exactly one:

- `broader_narrower`
- `kind_of`
- `instance_of`
- `part_of`
- `field_or_value`
- `predecessor_or_version`
- `process_vs_entity`
- `same_surface_different_sense`
- `confusable`
- `related_other`
- `unrelated`

## Blindness requirements

The sheet must not expose:

- candidate source;
- rule ID;
- embedding score;
- merge probability;
- model name/output;
- confidence band;
- proposed merge action;
- experiment arm.

Pair row order is randomised. A/B order is independently randomised. Annotators work independently. Disagreements are adjudicated only after both sheets are frozen.

## Evidence sufficiency

Set `evidence_sufficient = yes` only if the shown definitions/excerpts are enough to support the decision without relying on outside inference.

## Preferred canonical form

Fill only when useful. This field does **not** itself make the pair `SAME`.

## Test hygiene

Held-out examples must not be added to prompts, rules, the term lexicon or model-training data until after held-out reporting is complete.
