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
  `section_id, title, keywords, content`. **Only 13 sections have text here: all of
  chapters 1–3** (`iir_1`, `iir_1_1..1_4`, `iir_2_1..2_4`, `iir_3_1..3_4`) — no other
  chapter's raw text is included in this repo. This is what fixes CR-005's "B1 dev
  chapters" choice to chapters 1–3: they're not just a reasonable default, they're the
  *only* chapters this repo actually provides section text for. Chapters 4–16 have gold
  labels but no text here (out of scope for now — CR-005 §6 skips the IIR test split).

## Counts (real, from this commit)
- 13 sections with text, chapters 1–3 (5 + 4 + 4 — chapter 2 and 3's first subsection
  doubles as that chapter's opening section, so there's no separate "iir_2"/"iir_3"
  chapter-level record; see the loader for how this is handled).
- 13 matching annotation files for those sections (`iir-1.csv`, `iir-1.1.csv`, ...,
  `iir-3.4.csv`); 73 more annotation files exist for chapters 4–16 (no text).
