# LLM-based concept (node) extraction: does FACE transfer, and what to try next

*2026-09-30. Context: B1 results (IIR, FACE gold). v2 test exact micro F1 0.474 and lenient 0.568, vs FACE's supervised 0.76. Papers are in `running-paper-list.md`, "LLM-based concept / term extraction".*

## 1. Does FACE "translate" to LLM extraction?

**Partly.** Separate FACE's three contributions:

| FACE part | Transfers? | How we use it |
|---|---|---|
| **Method:** a supervised feature classifier over noun-phrase candidates, trained with 5-fold CV on the *same book's* labels | **No** (not directly) | It needs labelled sections from the target book, and P&D has none. It can't run zero-shot. |
| **Dataset + codebook:** section-level expert annotations for IIR; the annotation guideline (Wang et al. 2020) | **Yes** | B1 benchmark; training labels for the CR-002 concept scorer; the codebook can go into the prompt as a guideline (GoLLIE-style). |
| **Feature insights:** linguistic > statistical > external; unigrams are hardest | **Yes** | Prompt design (v2's short-term rule); features in the CR-002 scorer; a candidate list for hybrid prompting. |

**Suggested wording for the report:**
> "FACE's supervised classifier does not carry over to zero-shot LLM extraction, because it learns from labels on the same book, which don't exist for P&D. Its annotated dataset and codebook do carry over: we use them as the benchmark and as guidance. Part of the remaining gap reflects FACE having learned its annotators' conventions from those labels."

**Why the gap is partly about convention, not capability:**
- **The task is convention-heavy.**
  - Untrained crowd workers scored 0.39 on FACE's set.
  - FACE's own experts agreed at only 0.25 before iterating the codebook (0.9 after).
  - On ACTER term extraction, human inter-annotator F1 is about 0.59, and LLMs reach 0.36–0.72 (Rigouts Terryn 2026).
- **Our v2 change (telling the model to keep short domain terms) lifted test 1-gram recall from 0.228 to 0.326.** That is convention alignment, not new knowledge.
- **Exact match undercounts LLM output** (KPEval 2024). Many "errors" are defensible boundary choices (Rigouts Terryn 2026).
- **The convention hypothesis is testable** (§3, item 1). Don't state it as fact until it's tested.

## 2. What recent LLM work shows

1. **Recall is the usual LLM weakness.** LLMs are conservative, and domain constraints make them drop valid phrases (ConExion 2025). This matches our v1.
2. **Hybrid prompting beats free extraction alone.** Combine free extraction with a candidate list from a classical extractor; role prompting also helps (Kang & Shin, COLING 2025).
3. **Multi-sample aggregation is the most reliable boost** (Mohan et al., NAACL Findings 2025). Specialised instructions were inconsistent.
4. **Few-shot demonstrations help a little.** One example was best in ConExion. Choosing examples by syntactic similarity helps term boundaries (Chun et al. 2025).
5. **Consistency across a corpus is a large, free gain.** If a term is accepted in one place, tag it everywhere it occurs (DiSTER 2025).
6. **Distillation works.** A small model trained on GPT-4o pseudo-labels matches the teacher (DiSTER). GLiNER is a cheap zero-shot extractor. These are options for scale, not needed now.
7. **Education-specific evidence:**
   - LLM knowledge components can match or beat human ones when judged by student-data fit (Moon et al., EDM 2025);
   - but at KC granularity LLMs over-generate and need merging (Wang, Lin & Koedinger 2025);
   - the back-of-book index is an expert concept list you get for free (Alpizar-Chacon & Sosnovsky, WWW 2022).
8. **Evaluate semantically as well as exactly** (KPEval), and **adjudicate disagreements** rather than treating every mismatch as an error (Rigouts Terryn 2026).

## 3. Proposed experiments (dev first; each new version runs on test once)

| # | Change | Cost | Tests |
|---|---|---|---|
| 1 | Put FACE's annotation guideline (Wang et al. 2020 codebook) in the prompt, with no labels | ~$0.01 per run | The convention hypothesis |
| 2 | Aggregate 3 varied runs (union, ≥2-of-3 vote); report P/R for each | ~$0.03 | Recall via sampling (Mohan et al.) |
| 3 | Corpus-consistency rule: a concept accepted in one section is also tagged in any other section where it appears verbatim | $0 | DiSTER-style propagation (may cost precision) |
| 4 | 1–3 few-shot examples from dev sections | ~$0.01 | ConExion |
| 5 | Adjudicated error audit: 20 FP + 20 FN on test, owner marks each "defensible" or "real error" | $0, ~15 min | How much the metric understates |
| 6 | IIR back-of-book index as a weak-label source for CR-003 §5 | $0 | Free expert concept list |

**Rules:**
- Tune on dev only.
- A new prompt version (v3) runs on test once; v1 and v2 test results stay as they are.
- Items 3 and 5 are post-processing and analysis, so no prompt changes.

**Couldn't read:** arXiv 2602.17111 ("Instructor-Aligned Knowledge Graphs for Personalized Learning") was rate-limited. Check it later.
