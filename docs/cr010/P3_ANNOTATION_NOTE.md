# P3 pair-recall sheet — note for the annotator

Sheet: `data/interim/pair_recall/p3_blind_sheet.csv` (150 pairs, ids PQ001-PQ150). Same columns, values and rules as
`PAIR_RECALL_ANNOTATION_GUIDE.md`; the same truth definition applies. Differences in what you see:

- The evidence shows **two sentences of one section**. If they are not neighbours they are joined by ` [...] `.
- Judge whether **the two sentences together** state a relation between concept A and concept B. A relation that needs
  text you are not shown is `evidence_supported = no`.
- You are not told how a pair was found or what any system decided. Do not open the KEY or SEALED files.

Save the marked copy to the human-owned gold folder and check it with
`uv run python -m cumap.cr010.p3 validate --sheet <your file>`.
