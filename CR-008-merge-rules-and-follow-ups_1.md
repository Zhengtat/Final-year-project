# CR-008 — Term lexicon, merge rules, equivalence as a node property, and a textbook misconception layer (follow-ups after CR-007)

**Status:**
- items 1 and 3 approved by owner (Zheng Tat Wong), 2026-10-01;
- items 5 and 6 requested by the owner, 2026-10-02;
- item 2 pending; item 4 moved to CR-009.

This CR collects the changes requested after the CR-007 hand-off. Further items are added to §11 as they are approved.
**Branch:** `cr-008-merge-rules`, created from `main` **after** CR-007 is merged and tagged `cr-007-complete`. Merge with `--no-ff` and tag `cr-008-complete`.
**Scope:** on the CR-007 P&D ch. 1–3 run:
- canonicalisation (merging), as a **$0 re-keying pass**;
- the registry change that makes equivalence a node property (v1.3);
- a new **textbook misconception layer** stage, which makes a small number of paid calls.

The same rules and stage are then built into the pipeline for every later run, including the full book. Expert KG only (the misconception layer is textbook-sourced; student data stays deferred).

**Depends on:**
- CR-007 merged: registry final (v1.1, or v1.1.1 if a gated relation fails);
- the CR-007 fusion conflict detection (§5.6b);
- the CR-007 type-compatibility map (§4.3).

**Sources:**
- Schwartz & Hearst (2003), *A Simple Algorithm for Identifying Abbreviation Definitions in Biomedical Text*, PSB 2003. It needs no training data and reports 96% precision / 82% recall on the Medstract gold standard, and 95% / 82% on 1,000 MEDLINE abstracts.
- Hearst (1992), *Automatic Acquisition of Hyponyms from Large Text Corpora*, COLING 1992: lexico-syntactic patterns.
- Neumann et al. (2019), *ScispaCy*, BioNLP workshop. It provides `AbbreviationDetector`, an implementation of Schwartz & Hearst.
- **Refutation text (item 6):** passages that state a wrong idea, reject it and give the correct one.
  - Tippett (2010), *Refutation text in science education: A review of two decades of research*, International Journal of Science and Mathematics Education 8(6):951–970.
  - Guzzetti, Snyder, Glass & Gamas (1993), *Promoting conceptual change in science: A comparative meta-analysis of instructional interventions from reading education and science education*, Reading Research Quarterly, 117–159.
  - Schroeder & Kucera (2022), *Refutation Text Facilitates Learning: a Meta-Analysis of Between-Subjects Experiments*, Educational Psychology Review 34:957–987: a moderate positive effect, g = 0.41, over 44 comparisons (n = 3,869).
- **Misconceptions coexist with correct knowledge** (Shtulman & Valcarcel 2012) and are best modelled as small perturbations of an expert region (Brown & Burton 1978, BUGGY; CR-004 §9).

---

## 1. Why

**What the merge sheets showed:**
- Many duplicates were obvious and never needed an LLM call:
  - case or hyphen variants: "Non-Return-to-Zero (NRZ)" vs "non-return to zero (NRZ)"; "frequency-hopping" vs "frequency hopping";
  - plurals: "BBUs" vs "BBU";
  - concept names that embed an acronym: "cyclic redundancy check" vs "cyclic redundancy check (CRC)";
  - textbook alias statements: "the ARP cache or ARP table".
- In CR-005, 170 of 223 "same" merges were exact-string duplicates that still went through the LLM.
- **Textbook alias wording can be loose.** "a forwarding table (sometimes called a routing table)" (P&D §3.1) is contradicted by P&D §3.4, and the owner marked that merge wrong.
- Owner preference (2026-10-01): case variants, "X also known as Y" and "X (Y)" should merge as a matter of course.

**What this CR does:**
1. Adds a **deterministic, auditable alias layer** before any LLM merge call.
2. Gives every merge a recorded rule and evidence.
3. Separates **strong** textbook signals from **weak** ones.
4. Adds a **curated term lexicon** (item 3), with two running lists: terms that are the **same**, and terms that **look the same but are different**. It remembers every human merge decision so it is never re-litigated, and it outranks every automatic rule.
5. Makes **equivalence a node property, never an edge** (item 5).
   - Equivalent terms become one node, all their edges move onto it, and the other names are stored as aliases.
   - `equivalent_to` is removed from the registry (v1.3), so no "equivalent to" edge can be drawn.
   - **Why:** an equivalence edge splits one concept across two nodes. That divides its edges and its sphere importance. It also lets chains of "equivalent" links bypass the strict "same" rule and the lexicon.
6. Produces a **textbook misconception layer** (item 6).
   - Passages where the book warns against a wrong idea ("a common mistake is…", "X is not Y") become wrong edges in a separate layer.
   - Each wrong edge is linked to the correct edge it contradicts, with quotes.
   - **Why:** diagnosis must tell "contradicted" from "missing". The textbook's own warnings give labelled wrong paths before any student data.

---

## 2. Order of work and stop points

Commit per step with the prefix `CR-008:`.

1. **⛔ STOP 1: plan + $0 backtest** (no API calls). In ≤ 10 lines:
   - (a) **Backtest R1–R3 against both owner merge sheets** (CR-005 and CR-007):
     - for each rule, how many owner-marked merges it would have produced;
     - **how many of those the owner marked wrong**, listed;
     - which owner-marked "ok" merges the rules would miss.
   - (b) On the CR-007 run:
     - how many **currently separate** nodes R1–R3 would merge, per rule, with 10 examples per rule;
     - acronym collisions found;
     - weak-pattern (R3-weak) items found.
   - (c) How many CR-007 R4 (LLM) merge calls R1–R3 would have replaced. This is the estimated saving for the full book.
   - (d) **Lexicon seed** (§3.0): derive `same` and `different` entries from both owner merge sheets and the existing `never_merge` / `force_merge` overrides. For each research-chat seed confusable in `configs/term_lexicon.yaml`, search the slice text ($0) for a sentence where P&D **distinguishes** the pair. Write the seed approval sheet (§7).
   - (e) **Equivalence audit** (§3.5): every `equivalent_to` edge in the CR-007 run, with what R0–R3 would do with each.
   - (f) **Misconception cue scan** (§5.2, $0):
     - hits per cue family on the CR-007 run, with 5 examples each;
     - the number of `corrects_intuition` edges;
     - the preflight (call count and cost) for the structuring step (§5.3).

   Wait for the owner's OK.
2. **Build:**
   - the lexicon (R0 + guards) and R1–R4 (§3), as canonicalisation code + `configs/term_lexicon.yaml` + `configs/alias_rules.yaml`;
   - registry **v1.3** (`configs/registry-patches/CR-008-relations-v1.3.yaml`) and relation prompt **v2.1** (§3.5);
   - the **misconception stage** (§5, `configs/misconception_cues.yaml`);
   - tests (§8).
3. **Re-key the CR-007 run** (§4, including the `equivalent_to` migration) under a new `run_id`, $0. Then:
   - conflict detection;
   - logic-inference recompute;
   - **the misconception stage** (§5; paid, within the STOP 1 preflight);
   - `kg organise` (new `org_id`).

   **⛔ STOP 2:**
   - the before/after table (§6);
   - the conflict list and `alias_contradicted` flags;
   - the equivalence migration table;
   - the misconception list;
   - the merge sheet and the misconception sheet ready (§7).
4. After the owner's marks: precision per rule with Wilson CIs, any demotions, and the report refreshed.
   **⛔ STOP 3:** owner sign-off, then merge and tag.

---

## 3. Term lexicon and deterministic alias rules
These run **before** any embedding or LLM merge decision, in order **R0 → R1 → R2 → R3 → R4**. The first matching rule applies.

### 3.0 R0 — The term lexicon: two running lists (item 3)
`configs/term_lexicon.yaml` is a **curated, versioned memory of merge decisions**. Rules R1–R3 are recomputed on every run; the lexicon is not. It holds only decisions a human made or confirmed.

**The `same` list** holds synonym sets, each with:
- a canonical form;
- all its surface forms;
- a scope: `book:pd6e` (default), `chapter:N` for an ambiguous acronym, or `global`;
- a source: an owner sheet row, the `force_merge` list, or an owner-confirmed textbook alias statement with its quote and section.

Any concept whose form is in a set **merges into that set's node, with no LLM call**.

**The `different` list** holds look-alike pairs (or groups) that must **never** merge, each with:
- `kind`: `confusable` | `kind_of` | `instance_of` | `part_of` | `field_of` | `predecessor` | `different_type` | `book_distinguishes`;
- `why`: one line;
- `distinction_dimension`: what differs;
- a source: an owner sheet row, the `never_merge` list, or an owner-approved seed with a textbook quote.

**Where it is applied, and why:**
- **At the start.** It runs before R1–R4 in canonicalisation, so a known decision is applied before any relation pair is built on the node IDs. Waiting until the pruner would spend relation calls on wrongly merged or split nodes, and the error would spread through pairs, edges and the sphere.
- **As a guard at every later merge point.** The `different` list is also checked:
  - in the R1–R3 rules (a normalisation or alias match never overrides it);
  - in the CR-007 global merge sweep (§5.6a);
  - in the CR-008 re-keying (§4);
  - **in the verifier/pruner**, which may not accept a correction that renames a concept into its listed look-alike (e.g. a verifier `wrong_span` fix turning "routing table" into "forwarding table").

**Two further uses of the `different` list:**
1. **Pair selection:** a `different` pair that co-occurs in a sentence gets **priority in the coverage phase**, so the relation step gets a chance to record a `contrasts_with` edge with a grounded `dimension`.
2. **Unexplained confusables ($0):** a `different` pair with no `contrasts_with` (or other) edge after the run is flagged. Either the book never explains the difference, which is input for the CR-004 §11 structure audit, or extraction missed it. These pairs also feed the misconception layer (§5): students confuse exactly these. This matches Linn's "distinguish ideas" and the neuroscience finding that misconceptions coexist.

**Governance:**
- **Only approved entries take effect.** `status: proposed` entries are ignored by the pipeline.
- **The learning loop:**
  - after every owner merge sheet, Claude Code writes **proposals**: an `ok` mark → a `same` entry; a `wrong` mark → a `different` entry, with the owner's note as `why`; R3-weak review outcomes → whichever list the owner chose;
  - each proposal cites its sheet row;
  - entries derived from **owner marks** count as approved, with scope `book:pd6e`;
  - research-chat seeds and textbook-derived pairs need the owner's tick on the seed approval sheet (§7).
- **Code never writes `data/gold/`.** It only reads the sheets to propose entries.
- **Validation and versioning:** the lexicon validator refuses to load if one pair is in both lists, if an entry has no source, or if a scope is malformed. Every change bumps the lexicon `version` and adds a CHANGELOG line.
- **Rule outputs are not lexicon entries.** Automatic merges from R1–R3 stay rule outputs, recomputed and measured per rule. A merge enters the lexicon only once a human has confirmed it.


**Applies to every rule:**
- **Overrides and type checks:** the lexicon (R0) always wins (`never_merge` and `force_merge` are folded into it), and the CR-007 §4.3 type-compatibility check applies.
- **Provenance:** every merge records `{rule_id, surface_forms, section_id, evidence_quote}` in the alias list. A merge is **reversible** by adding a `never_merge` entry.
- **Display name:** the form used in the concept's **first definition**. Otherwise the most frequent surface form; all other forms become aliases.

### 3.1 R1 — Normalisation key (auto-merge when keys are equal)
- **The key:**
  - Unicode NFKC + casefold;
  - unified dashes and quotes;
  - hyphen / space / no-space variants collapsed ("frequency-hopping" = "frequency hopping"; "multi-access" = "multiaccess");
  - a leading article stripped ("the Internet" = "Internet");
  - the head noun singularised by lemma ("BBUs" = "BBU");
  - a small British/American spelling map in config ("adaptor" = "adapter").
- **Acronym-collision guard:** if one form is all capitals (an acronym of ≥ 2 letters) and the other is all lower-case **and** a common English word (config word list), do **not** auto-merge; send the pair to review. Examples: "AS" (autonomous system) vs "as"; "CAN" vs "can".

### 3.2 R2 — Acronym–expansion pairs (auto-merge)
- **Detection:** the Schwartz & Hearst algorithm (scispaCy's `AbbreviationDetector`, or about 50 lines of code), run over the section text. It finds both "long form (SF)" and "SF (long form)", e.g. "maximum transmission unit (MTU)", "Carrier Sense, Multiple Access with Collision Detect (CSMA/CD)".
- **Merge:** the short form becomes an alias of the long-form concept.
- **Concept names containing the pattern** (e.g. the extractor's "cyclic redundancy check (CRC)") are split: canonical name = long form, alias = short form.
- **Ambiguous acronyms are scoped, not global.** If one short form maps to ≥ 2 different long forms anywhere in the processed text (e.g. MAC = media access control in ch. 2 vs message authentication code in the security chapter), the short form is **not** a global alias. Each mention links to the nearest preceding definition in the same chapter, or else goes to review. Log the collision.
- **Not an alias:** parentheticals that are examples, hedges or comparisons, i.e. containing "e.g.", "such as", "for example", "or the similar", "see", "like" or "cf." (e.g. "4B/5B encoding (or the similar 8B/10B)").

### 3.3 R3 — Textbook alias statements (Hearst-style patterns over the text)
- **Strong patterns** (auto-merge, evidence required):
  - "X, also known as Y";
  - "X (also called Y)", "X, also called Y";
  - "X, abbreviated Y", "Y stands for X", "Y is short for X";
  - "X, or simply Y".
- **Weak patterns** (never auto-merge; go to the review sheet with the evidence quote):
  - "X (sometimes called Y)", "X is often referred to as Y";
  - "X (or alternatively Y)", "X, or Y,";
  - "X, i.e. Y";
  - "Y officially goes by another name, X";
  - "the terms X and Y are used interchangeably".
- **Later distinction check:** after re-keying, flag any R3 merge whose two forms the book later **distinguishes** as an `alias_contradicted` conflict for the owner. "Distinguishes" means separate definitions, a `contrasts_with` edge, or "unlike X, Y …".

### 3.4 R4 — Everything else
This follows the existing CR-007 path: embedding candidates → LLM same / broader / narrower / different under the strict rule, with the < 0.70 review band.

**Demotion:** an auto rule (R1, R2, R3-strong) that produces any wrong merge on the owner's sheet is inspected, then either gains a guard or is demoted to review in the next version. Log it in DECISIONS.

### 3.5 Equivalence is a node property, never an edge (item 5)
**Rule:** two terms that mean the same thing are **one node**. The node keeps one display name and stores every other name in `aliases`. There is no "equivalent to" edge anywhere in the graph.

- **Registry v1.3** (`configs/registry-patches/CR-008-relations-v1.3.yaml`):
  - removes `equivalent_to` from the comparison family, and from `contrasts_with`'s `conflicts_with` and near-misses;
  - the validator rejects any edge whose relation is `equivalent_to`, in every layer.
- **Versioning:**
  - v1.3 is built on the final CR-007 registry (v1.1, or v1.1.1).
  - v1.2 stays reserved for CR-004's `instantiates`. When CR-004 runs, its patch is rebased onto v1.3, and DECISIONS records the resulting version.
- **How equivalent terms become one node:** only through the merge path:
  1. R0 lexicon `same` sets;
  2. the R1–R3 alias rules;
  3. the R4 strict "same" decision;
  4. from CR-009, generator links.

  Every merge stores the merged form as an alias with `{form, rule_id, section_id, evidence_quote}`.
- **All edges move onto the surviving node** (§4): they are re-keyed, duplicates become one edge with every quote, and merge-created self-loops are rejected. `merged_from` keeps the old IDs, so nothing is lost and a merge can be undone with a `never_merge` entry.
- **Relation prompt v2.1:**
  - the comparison family loses the `equivalent_to` option and gains a **`same_concept` outcome**: "{X} and {Y} are two names for the same thing";
  - choosing it creates **no edge**. The pair is queued as a merge candidate for canonicalisation (R0–R4, strict rule);
  - the count is reported.
- **Existing `equivalent_to` edges in the CR-007 run** are migrated during re-keying (§4):
  1. each pair goes through R0–R3. If a rule merges it, the edge disappears into the merged node;
  2. otherwise it goes on the merge sheet as an `equivalence_migration` item (same / not same);
  3. **"same"** → merged;
  4. **"not same"** → the edge is retired: it is kept in `rejected.jsonl` with reason `equivalent_to_retired`, and the pair is queued for normal relation classification at the next relation run (the CR-009 re-run).

  These are not merged automatically because some `equivalent_to` edges are functional equivalences rather than synonyms. CR-001's own example was "carrier extension ≡ extending the slot time to 512 bytes".
- **Where aliases are used:**
  - mention matching (CR-007 §4.1);
  - the CR-009 node cards;
  - display and exports;
  - later, linking student wording to nodes.

---

## 4. Re-keying the CR-007 run ($0)
- **Order:** apply the lexicon (R0) first, then R1–R3.
- **Merging:** the merged nodes collapse, and edges, evidence, roles, `description_history` and aliases are re-keyed to the surviving node. Nothing is deleted; the pre-merge IDs are kept in a `merged_from` field.
- **Edge consolidation:** after re-keying, edges with the same relation and direction between the same pair become **one edge with several evidence quotes**.
- **Conflicts:** pairs with conflicting relations go through the CR-007 §5.6b **detection** and are listed. **Adjudication calls need the owner's OK.** Preflight them; this is expected to cost ≤ $0.50.
- **`equivalent_to` migration** (§3.5): every `equivalent_to` edge is resolved, either merged (by rule or owner mark) or retired. Afterwards the validator must find **0** `equivalent_to` edges.
- **Self-loops** created by a merge (A rel A) are rejected with reason `merge_self_loop`.
- **Re-checks:**
  - acyclicity of `is_a`, `part_of`, `encapsulates` and `prerequisite_of`;
  - logic-inferred edges recomputed;
  - LLM-inferred edges re-keyed, not regenerated.
- **Organisation:** `kg organise` is re-run with the same config. Compare it with the CR-007 sphere using the soft-matched stability metrics (CR-007 §6.1).
- **Pipeline integration:** the same rules run inside canonicalisation for every future run, including the full book.

## 5. Textbook misconception layer (item 6)
**The idea:**
- Textbooks sometimes say outright what learners get wrong: "a common mistake is…", "it is tempting to think…", "X should not be confused with Y", "X is not Y". These are **refutation passages**: they state a wrong idea, reject it and give the correct one.
- Refutation text is a well-supported conceptual-change tool (Tippett 2010; Guzzetti et al. 1993; Schroeder & Kucera 2022, g = 0.41).
- This stage turns each such passage into a **wrong edge** in a separate `misconception` layer, linked to the **correct edge** it contradicts, with quotes.

### 5.1 The layer
- **Separate:** misconception edges never mix with the expert layers. They are excluded from:
  - expert-edge precision;
  - sphere importance;
  - pair selection, prerequisites and fusion;
  - expected subgraphs.

  In the report and the sphere they are a toggle: dashed red, drawn from the wrong edge to the correct edge.
- **Why separate:** misconceptions coexist with correct knowledge, and are modelled as small perturbations of an expert region (BUGGY; CR-004 §9), not as errors to delete.
- **A misconception edge has:**
  - `source`, `relation`, `target`, `polarity` and qualifiers: the wrong belief in registry terms.
    - Endpoints are existing expert nodes.
    - The relation is any registry relation, plus `conflated_with` (misconception layer only) for "X and Y are the same" beliefs.
  - `perturbation_type`: `polarity_flip` | `reversed` | `substituted_concept` | `conflation` | `wrong_category` | `wrong_relation` | `condition_error` | `modality_error`. These line up with the M7 match types, so diagnosis can match them directly.
  - `contradicts` (**required**): at least one expert edge ID. For `conflation`, a `contrasts_with` edge or an approved lexicon `different` entry. An item with nothing to contradict never enters the layer.
  - `intuition`: the wrong belief in plain words, as the book states it.
  - `misconception_quote` and `correction_quote`: {section_id, quote}, verbatim. Often the same sentence.
  - `prevalence_cue`: `stated_common` ("a common mistake") | `stated_possible` ("one might think") | `none`.
  - `origin: textbook_warning`. Later, SAF-mined items (M8) join the same layer with `origin: student_data`.
  - `status`: `proposed` | `owner_confirmed` | `owner_rejected`.

### 5.2 Finding the passages ($0)
**Cue scan** over every section with `configs/misconception_cues.yaml`, in five families:
1. **Explicit error:** "a common mistake / misconception / error / pitfall", "it is a mistake to", "it is incorrect to", "contrary to popular belief", "is a myth", "misleading", "misnomer".
2. **Tempting belief:** "it is tempting to think / assume", "one / you / we might think / assume / expect", "naively", "at first glance", "it may seem", "one would expect", "surprisingly", "counter-intuitive", "it is easy to forget / overlook / assume".
3. **Confusion:** "not to be confused with", "should not be confused with", "is often confused with", "do not confuse".
4. **Negated identity or implication:** "X is not (a | the | just | simply | merely) Y", "is not the same as", "does not mean / imply / guarantee", "it is not the case that", "not … but rather".
5. **Existing signals:**
   - relation edges with the CR-007 `corrects_intuition` qualifier. Item 2's fix is still pending, but these edges feed this family either way;
   - approved lexicon `different` pairs co-mentioned in one sentence.

Family 4 is noisy, because technical text negates facts all the time. Its hits are only candidates, and the structuring step decides.

### 5.3 Structuring the passage (LLM, strong tier, one call per candidate)
- **Input:**
  - the sentence and its paragraph;
  - cards for the expert nodes mentioned in the paragraph;
  - the expert edges, with IDs, whose evidence lies in that paragraph or that join those nodes;
  - the registry relations with their templates;
  - the perturbation types;
  - any lexicon `different` pair present.
- **Output (structured):**
  - `is_warning`: does the text describe a belief that is wrong? Plus a one-line reason. Most family-4 hits should stop here with "no".
  - the `intuition`, the wrong edge, its `perturbation_type`, the `prevalence_cue` and both quotes;
  - `contradicts`: the IDs of the correct edges shown. If the correct edge is stated in the passage but is not yet in the KG, a `proposed_correct_edge` (source, relation, target, polarity, quote) instead.
- **Proposed correct edges** go through the CR-007 relation verifier (fresh context, the other tier) and the structural checks.
  - **Accepted:** they enter the expert layer as normal textbook edges, with `found_by: misconception_stage`.
  - **Rejected:** the item goes to the owner sheet as `needs_correct_edge` and does not enter the layer.

### 5.4 Checks (code, $0)
- **Basics:**
  - quotes are verbatim;
  - endpoints are shown expert nodes;
  - the wrong edge differs from every edge it contradicts.
- **Perturbation consistency,** checked against the linked correct edge:
  - `polarity_flip`: same triple, opposite polarity;
  - `reversed`: same directional relation, endpoints swapped;
  - `substituted_concept`: same relation, one endpoint shared, the other different;
  - `conflation`: relation `conflated_with`; the correct side is a `contrasts_with` edge or a lexicon `different` entry for the same two nodes;
  - `wrong_category`: `is_a` on both sides, same source, different target;
  - `wrong_relation`: same endpoints, different relation;
  - `condition_error` / `modality_error`: same triple, different conditions / modality.
- **Failures:** a failed check gets **one** corrective re-prompt, as in CR-009 §4.3. If it still fails, the item goes to the owner sheet unchanged.
- **Lexicon link:** a `conflation` item proposes a lexicon `different` entry (status `proposed`, source: the textbook quote) for the owner's seed sheet.

### 5.5 Later use in diagnosis (deferred)
- **M7:** a student edge is checked against the misconception layer **before** it can be called an unsupported extra. A match:
  - makes the edge `contradicted`, never "missing";
  - names the misconception;
  - points to the correct edge and both quotes, which feedback can use.
- **M8:** misconceptions mined from SAF feedback join the same layer with `origin: student_data`. The textbook warnings give a prior on which ones to expect.

### 5.6 Where it runs
- **In the pipeline:** a stage after relations, prerequisites and fusion, and before `kg organise`.
- **In this CR:** it runs once, on the re-keyed CR-007 run (step 3).
- **Later:** every later run (the CR-009 re-run, the full book) runs it again.

## 6. Metrics (before → after, same run)

| Metric | Reported |
|---|---|
| Nodes; merges per rule (**R0**, R1, R2, R3-strong, R4); R3-weak items sent to review; acronym collisions | Yes |
| **Lexicon:** size of the `same` and `different` lists (approved / proposed); R0 merges; merges **blocked** by `different` at each guard point (R1–R3, sweep, re-key, verifier); **unexplained confusables** (no edge between a `different` pair), listed | Yes |
| Owner precision per rule (Wilson 95% CI); demotions | Yes; auto rules should have no wrong merges |
| `alias_contradicted` flags; new conflict groups after re-keying; `merge_self_loop` rejections | Yes |
| Edges before/after consolidation; linked share overall and for `defined` concepts | Yes |
| Estimated LLM merge calls saved per run (from the STOP 1 backtest) | Yes |
| Sphere: core–periphery Δρ; soft core Jaccard vs CR-007; top-15 changes | Yes |
| **Equivalence:** `equivalent_to` edges migrated → merged by rule / merged by owner / retired; `same_concept` outcomes queued; validator count of `equivalent_to` edges in any layer | Yes; the count must be 0 |
| **Misconception layer:** cue hits per family → `is_warning` = yes → items in the layer, by perturbation type and prevalence cue; proposed correct edges accepted / rejected; `needs_correct_edge` items; owner precision (Wilson CI); cost vs preflight | Yes |

## 7. Sheets

**Seed approval sheet** (STOP 1; ~10 min): one row per proposed lexicon entry, showing the forms, the list (`same` or `different`), the `kind`, the `why`, and the textbook quote if one was found. The judgement is approve / reject / edit. Entries derived from owner marks are listed for information only.

**Merge sheet** (STOP 2; ~10–15 min).

The sheet goes in `data/interim/checks/`; the owner saves the filled copy to `data/gold/merges/`. It is stratified by rule:
- up to 10 R1 merges;
- up to 10 R2 merges;
- every R3-strong merge (or 10 if there are more);
- every R3-weak review item;
- every acronym collision;
- every `alias_contradicted` flag;
- every `equivalence_migration` item (§3.5; ~2 min).

The judgement is ok / wrong / unsure. No model output is shown beyond the two forms, their sections and the evidence quote.

**Misconception sheet** (STOP 2; ~10 min):
- **Rows:**
  - every item (or 40, stratified by perturbation type, if there are more);
  - plus every `needs_correct_edge` item.
- **What it shows:** the quotes, the wrong belief and the correct edge, written as plain sentences.
- **Judgements:**
  - (a) Does the book give this warning? yes / no.
  - (b) Is the wrong edge a faithful version of it? yes / fix (write it).
  - (c) Is the linked correct edge the right one? yes / no.
- **Result:** precision with a Wilson CI. Confirmed items get `status: owner_confirmed`.
- **Optional recall sample** (~5 min): 20 negation sentences the cue scan did not catch, judged warning yes / no. This gives a rough idea of what the cues miss.

## 8. Tests (no network, no key)
- **R1:**
  - merges "Ethernet" / "ethernet", "frequency-hopping" / "frequency hopping", "the Internet" / "Internet", "BBUs" / "BBU", "adaptor" / "adapter";
  - the acronym guard blocks "AS" vs "as".
- **R2:**
  - detects "maximum transmission unit (MTU)" and "MTU (maximum transmission unit)";
  - splits the name "cyclic redundancy check (CRC)";
  - rejects "4B/5B encoding (or the similar 8B/10B)";
  - scopes an ambiguous acronym (MAC with two expansions) instead of merging it globally.
- **R3:**
  - "also known as" auto-merges;
  - "(sometimes called …)" goes to review;
  - a later "unlike X, Y" raises `alias_contradicted`.
- **Lexicon (R0):**
  - a `same` set merges with no LLM call;
  - a `different` pair blocks R1, R2, R3, R4, the sweep, re-keying and a verifier correction;
  - `proposed` entries are ignored;
  - the validator rejects a pair in both lists and an entry with no source;
  - a `chapter:N` scope is respected;
  - owner-sheet proposals cite their row;
  - `different` pairs get coverage priority;
  - the unexplained-confusables report lists pairs with no edge.
- **Overrides and provenance:**
  - `never_merge` overrides every rule;
  - the type-compatibility check applies;
  - every merge has a `rule_id` and an evidence quote.
- **Re-keying:**
  - edges are consolidated with all evidence kept;
  - a merge-created self-loop is rejected;
  - acyclicity is re-checked;
  - nothing is deleted (`merged_from` is kept).
- **Equivalence:**
  - the validator rejects an `equivalent_to` edge in any layer;
  - registry v1.3 loads without it;
  - a `same_concept` choice creates no edge and queues a merge candidate;
  - migration fixtures: merged by rule, merged by owner, retired;
  - after a merge, the surviving node holds every edge and every alias, each with provenance.
- **Misconception layer:**
  - cue fixtures for each family, including a negated plain fact that the (mocked) structuring step rejects;
  - each perturbation-consistency rule;
  - an item without `contradicts` never enters the layer;
  - misconception edges are excluded from importance, pair selection, expert precision and expected subgraphs;
  - a proposed correct edge goes through the relation verifier;
  - a `conflation` item proposes a lexicon entry.
- **Hygiene:** nothing writes to `data/gold/`.

## 9. Docs
- **`ARCHITECTURE.md`:**
  - the term lexicon (R0, its guard points and the learning loop);
  - the alias layer R1–R4, merge provenance, re-keying and consolidation;
  - **equivalence as a node property** (aliases; registry v1.3);
  - **the misconception layer** (fields, cue scan, structuring, checks, exclusions).
- **`DECISIONS.md`:**
  - the rule order;
  - the strong vs weak pattern lists;
  - the acronym-guard word list;
  - the scoping rule for ambiguous acronyms;
  - demotions;
  - registry v1.3 (`equivalent_to` removed; v1.2 reserved for CR-004 and rebased);
  - relation prompt v2.1;
  - the misconception cue-list version.
- **`CLAUDE.md`**, new rules:
  - "Every merge records its rule and evidence. Deterministic alias rules run before any LLM merge call, and 'sometimes called' never auto-merges."
  - "The term lexicon outranks every automatic rule. Only approved entries take effect, and a `different` pair is never merged at any stage."
  - "Equivalence is a node property: one node with aliases, never an edge."
  - "Misconception edges live in layer `misconception`, always link to the correct edge they contradict, and never count as expert knowledge."
- **`PROGRESS.md`:** a CR-008 row with §6.

## 10. Cost and time
- **API:**
  - $0 for re-keying, the lexicon and the equivalence migration;
  - optional conflict adjudication ≤ $0.50, only with the owner's OK after a preflight;
  - **misconception structuring ≈ $0.5–1.5** (strong tier, one call per candidate; STOP 1 gives the exact count);
  - verifying proposed correct edges ≈ $0.1–0.3;
  - **hard cap $3**.
- **Future runs** save LLM merge calls; STOP 1 (c) estimates how many.
- **Owner time:**
  - merge sheet ~12–17 min, including the equivalence items;
  - misconception sheet ~10 min (+ an optional ~5 min recall sample);
  - STOP reviews ~15 min.

## 11. Items log
| # | Item | Status |
|---|---|---|
| 1 | Deterministic alias rules R1–R4 + re-keying of the CR-007 run (§2–§4, §6–§10) | Approved 2026-10-01 |
| 3 | **Term lexicon:** running `same` and `different` (look-alike) lists, applied first (R0) and enforced as a guard at every merge point, including the verifier/pruner. Owner-marked decisions feed it; it gives `different` pairs coverage priority and an unexplained-confusables report (§3.0) | Approved 2026-10-01 |
| 2 | `corrects_intuition` fix | **Pending.** It waits for the CR-007 STOP 5 diagnosis (whether the cause is the prompt/schema or the code), then the research chat specifies the fix here |
| 4 | **Concept extraction redesign** (KG-aware generator, rule verifier with PiVe-style iterative prompting, SAC-KG-inspired pruner, backfill replacing propagation) | **Moved to its own CR-009** (2026-10-02, owner request), because it changes the concept stage rather than merging. CR-009 starts after `cr-008-complete` and reuses this CR's lexicon (R0) and R1 key. The CR-009 concept verifier applies the R0 guard (rule C1) |
| 5 | **Equivalence as a node property:** equivalent terms are one node with aliases, and their edges move onto it. `equivalent_to` is removed from the registry (v1.3). Relation prompt v2.1 gets a `same_concept` outcome. Existing `equivalent_to` edges are migrated (§3.5) | Requested by owner 2026-10-02 |
| 6 | **Textbook misconception layer:** refutation-style passages become wrong edges in layer `misconception`, each linked to the correct edge it contradicts, with quotes. Runs as a pipeline stage (§5) | Requested by owner 2026-10-02 |
| — | Further post-CR-007 changes | Added here as they are approved |
