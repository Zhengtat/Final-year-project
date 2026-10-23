# CR-015 blind boundary audit — guide (about 120 families, 441 rows)

Purpose: find out which boundary convention a careful human reader applies to overlapping candidate spans, so that CR-015 can confirm or fix the annotation convention before Stage B. This must be **your own judgement as a human reader**. If the labels are produced or filled in by a model, the audit cannot do its job and should be reported as `NOT_HUMAN`.

Files: `data/interim/checks/cr015/boundary_audit_blind.csv` (fill the last three columns). The hidden key is under `data/processed/` and must not be opened until the sheet is finished.

## What you see
One family = one stretch of a sentence, marked `<< >>`, and several overlapping candidate spans taken from inside it. Each row is one candidate span. You do not see any gold annotation or any system output, and families are in random order.

## Column 1 — `valid_boundary_yes_no_unsure`
Is this **exact span** a correct term boundary here, i.e. would a glossary of this textbook list the term written exactly like this, as the sentence uses it?
- **yes**: the span is a complete technical term as used ("TCP congestion control", "router").
- **no**, too long: it adds a wrapper, a modifier that is not part of the term, or turns the term into a descriptive phrase ("effective congestion control", "operation of the routing protocol").
- **no**, too short: it is only a fragment of a longer term that the sentence uses as one unit ("control" in "congestion control" when "control" alone is not meaningful here).
- **no**, other: not a term at all (generic word, clause, value).
- **unsure**: use sparingly.
More than one span in a family can be `yes`.

## Column 2 — `independent_term_if_inside_a_longer_valid_term_yes_no_na`
Fill this only for a span that lies **inside** a longer span you marked `yes`. Is the shorter span **also** independently meaningful as a term in this sentence ("congestion control" inside "TCP congestion control" = `yes`; "TCP" alone inside "TCP congestion control" may be `yes`; "effective" or a head fragment is `no`)? Write `na` when no longer valid span encloses it.

## Column 3 — `note`
Optional: why, in a few words, especially for a surprising choice.

## After you finish
Save the file (keep the same name and columns) and tell me. I will then compare your labels with (1) the model-generated gold, (2) the frozen A2 selector decisions, and report where the conventions disagree. Fixing the convention is a separate, explicit step: nothing changes automatically.
