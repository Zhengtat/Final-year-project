# CR-009 — Concept extraction v4: a KG-aware generator, a rule-based verifier with iterative prompting, and a pruner

**Status:** requested by the owner (Zheng Tat Wong), 2026-10-02. This is a draft for approval; the owner approves it by handing it to Claude Code. It was reviewed twice against both source papers before issue (§17).
**Branch:** `cr-009-concept-gvp`, created from `main` **after** CR-008 is merged and tagged `cr-008-complete`. Merge with `--no-ff` and tag `cr-009-complete`.
**Scope:** the concept stage only (generator → verifier → pruner), plus the small hooks that let its output feed canonicalisation and relation pair selection. Validated on the IIR benchmark (dev, then test once), then a P&D ch. 1–3 re-run. Expert KG only.

**Depends on:**
- CR-007 merged:
  - concept configuration v3 (chosen at CR-007 STOP 2);
  - longest-match mentions (§4.1);
  - first occurrence and roles (§4.2);
  - type compatibility (§4.3);
  - coverage-aware pair selection (§5.3).
- CR-008 merged:
  - the term lexicon R0 (`configs/term_lexicon.yaml`) and the R1 normalisation key, which the verifier reuses;
  - registry v1.3 (no `equivalent_to`; equivalence lives in node aliases) and relation prompt v2.1;
  - the textbook misconception stage (CR-008 §5), which this CR's re-run includes.

**Supersedes:**
- CR-007 E3 **consistency propagation**. It is replaced by the existing-node sweep and the backfill pass (§3.7).
- The **concept** part of CR-007 §5.4 (generate → verify → prune). The relation part of §5.4 is unchanged.

**Sources (both read in full, 2026-10-02):**
- **SAC-KG:** Chen, Shen, Lv, Wang, Ni & Ye (2024), *SAC-KG: Exploiting Large Language Models as Skilled Automatic Constructors for Domain Knowledge Graphs*, ACL 2024 (arXiv 2410.02811).
  - Generator: retrieves domain text and open-KG triples (the triples are in-context format examples).
  - Verifier: rule-based and parameter-free. Quantity, format and conflict checks feed error-type-specific re-prompts (Table 6).
    - App. B: if more flagged triples than the threshold (3), regenerate;
    - if fewer, delete them.
  - Pruner: a T5 + LoRA classifier, trained on DBpedia head entities ("growing") vs tail entities ("pruned"). It decides whether a tail entity is **expanded** at the next level. Pruned tails stay in the KG.
  - Precision 89.32% (GPT-4-judged; GPT-4 vs humans κ 0.613).
  - Ablations:
    - without the pruner, level-3 precision is 44.82% vs 76.74%;
    - without the verifier, level-1 precision is 76.47% vs 88.81%.
- **PiVe:** Han, Collier, Buntine & Shareghi (2024), *PiVe: Prompting with Iterative Verification Improving Graph-based Generative Capability of LLMs*, Findings of ACL 2024.
  - **The loop:** a small trained verifier names a missing triple, and that triple is added to a new prompt ("…also add the given triples…"). This repeats until the verifier outputs "Correct", up to 3 iterations.
  - **Accumulation:** the given triples accumulate across iterations, which "prevents the LLM from making the same mistakes as in previous iterations".
  - **Demonstrations:** corrective rounds use a demonstration that itself contains given triples (App. G).
  - **Online vs offline:** iterative prompting beat offline correction (KELM-sub, single verifier: triple F1 20.17 vs 18.55 after 3 iterations), though offline correction also improved on the base (13.50).
  - **Self-Refine** (LLM self-feedback) gave no real gain: triple F1 13.50 → 13.79, while graph-match F1 fell from 4.89 to 2.28.
- **Also cited:**
  - ConExion (Norouzi, Hertling & Sack 2025, NSLP @ ESWC 2025, CEUR-WS 3977): an LLM extractor of all present concepts. Code and data are public. It is the comparison method in §7.1–7.2;
  - iText2KG (Lairgi et al. 2024, WISE): incremental matching of new entities against the global graph, the closest precedent for our node cards;
  - Lu et al. (2022, ACL), cited by PiVe §6.1: few-shot order sensitivity.

---

## 1. Why

| Evidence | Cause | Fix in this CR |
|---|---|---|
| Some concepts are extracted partially (owner observation, 2026-10-02). On IIR dev v1, 4-gram recall was 0.250 against 0.719 for 3-grams | No examples of complete spans; no check that a span is the whole term | Few-shot bank of complete concepts (§3.5); a partial-span rule (§4.1, M2) |
| Each section is extracted **blind to the KG**. In CR-005, 170 of 223 "same" merges were exact duplicates sent to the LLM afterwards | The generator cannot see what is already known | The generator sees the relevant existing nodes and links mentions to them directly (§3.2–3.3) |
| Known concepts were tagged afterwards by string matching (CR-007 E3). CR-006 counted 15 of 87 ch2 edges "late", because ch2's extraction had missed concepts in its own text | Offline string propagation cannot tell word senses apart and writes tags silently | Propagation is replaced by a sweep inside the generator and an end-of-chapter backfill. Every string match gets a decision with evidence or a reason (§3.7) |
| A new concept arrives with no record of how it relates to what is known, so relation extraction must rediscover the link. 86% of concepts had no typed edge, and the pair cap was the main cause | Relatedness noticed during extraction is thrown away | **Anchors**: a new concept records which existing node(s) it relates to, how, and the cue sentence. Anchor pairs go first in pair selection (§3.6, §6.3) |
| The CR-007 concept verifier is an LLM judge | Untested here. PiVe's LLM self-feedback did not help | The verifier is rule-based code (SAC-KG). An LLM check is an optional, measured arm (§4.4) |
| Every verified concept becomes a node, and with a KG-aware generator a weak node is **shown again** to every later section | No pruner | A pruner decides growing vs pruned; pruned items are never shown again and never paired (§5) |

---

## 2. Order of work and stop points

Commit per step with the prefix `CR-009:`.

1. **⛔ STOP 1: plan + $0 diagnostics + drafts** (no API calls). In ≤ 10 lines plus attachments:
   - (a) **Partial-span baseline:** run the M2 detector (§4.1) over the CR-007 P&D run and the v3 IIR dev outputs. Give the rate and 20 examples. Run it over the few-shot bank's expected outputs too: it must raise **no** flags there.
   - (b) **Propagation audit:** how many mentions in the CR-007 run came from propagation (or would have, if E3 was not adopted), split forward vs backward. List 20 for the owner to mark same sense / different sense.
   - (c) **Retriever dry run** (§3.2): cards per section (median / max) and the prompt tokens they add. Also the backfill call count the detector predicts (§3.7).
   - (d) **Pruner training data:** counts per label, after term-level dedup, and conflicts resolved (§5.3).
   - (e) **Quantity floor:** proposed ρ, from IIR dev gold density (§4.1, Q1).
   - (f) **Drafts for approval:**
     - the prompt diff against v3 (`prompts/concept_generator_v4.md`);
     - the corrective-instruction table (`configs/concept_gvp.yaml`);
     - the few-shot bank, on a seed approval sheet (§10).
   - (g) **Comparison set-up (§7.1–7.2):**
     - confirm access to ConExion's repo (prompt template, scorer, data, released outputs);
     - confirm the dataset licences;
     - run the scorer validity gate ($0 if outputs are released).
   - (h) The preflight for the STOP 2 work, including the comparison arms and the external check.

   Wait for the owner's OK and the approved bank.
2. **Build** the generator (§3), the verifier and its loop (§4), the pruner (§5) and the backfill pass (§3.7), with tests (§11). Delete E3.
3. **IIR experiments** (§7).
   **⛔ STOP 2:**
   - the dev table and the configuration picked by the pre-registered rule;
   - the comparison arms on dev (§7.1);
   - then v4 and the comparison arms each run **once** on the test split;
   - the external check (§7.2).
4. **Downstream hooks** (§6).
5. **P&D ch. 1–3 re-run** under a new `run_id` (§8).
   **⛔ STOP 3:** the comparison table (§9) and the owner sheets (§10).
6. After the owner's marks: precision with Wilson CIs, rule demotions and the report refresh.
   **⛔ STOP 4:** owner sign-off, then merge and tag.

---

## 3. Module 1: the generator

### 3.1 Inputs, per section
- **Text:** the section, split into numbered paragraphs P1…Pn. Use paragraph units if v3 adopted E6.
- **EXISTING NODES:** cards from the retriever (§3.2).
- **LOOK-ALIKES:** approved `different` pairs from the lexicon (CR-008 R0) where at least one side is a shown card or occurs in the text, each with its one-line `why`.
- **DEFINITIONS:** v3's definition text unchanged (the E1 guideline and E5 granularity rules, if they were adopted), plus the complete-span rules and the strict "same" rule (§3.3).
- **EXAMPLES:** the approved few-shot bank, in a fixed order (§3.5).

### 3.2 Node retriever
This is our own idea, inspired by SAC-KG's retrievers (which pass relevant text and external KG triples as format examples) and closest to iText2KG's incremental matching. Here the retriever passes the generator the **existing nodes of the graph being built** that are relevant to the section.

- **Eligible nodes (main pass):** only **growing** nodes (§5), from **earlier sections** of the **same run**, in book order. Never gold labels.
- **Selection:**
  1. **String hits:** nodes with a longest-match mention in the section, on any form: name, alias, or lexicon `same` form, compared by R1 key. These are marked `in_text: yes`.
  2. **Semantic hits:** the top-k nodes by embedding similarity between the card and each paragraph (k = 30 per section after dedup; config). These are marked `in_text: no`.
  3. The lexicon `different` partners of any hit.
- **Cap:** 120 cards. String hits come first, in order of first occurrence; then semantic hits by score.
- **Card format:**

  ```
  n_0142 | cyclic redundancy check | aka: CRC | Mechanism | def §2.4 | in_text: yes | "an error-detecting code computed over the frame..." (≤ 25 words)
  ```

  `def` is the section of the node's first definition, or `—` if it has none.
- **Logging:** the shown card set is logged per section. Linking to a card that was not shown is error F4.
- **Cold start:** the first sections have no cards. The procedure still runs, and every concept is independent.

### 3.3 The meta-structured prompt
The prompt always has the same skeleton, in this order:

**ROLE → TASK → DEFINITIONS → INPUTS → PROCEDURE → OUTPUT SCHEMA → EXAMPLES → FINAL CHECKLIST**

The draft is `prompts/concept_generator_v4.md`.

**Procedure:**
1. **Open read.** From the text alone, before consulting EXISTING NODES, list every term the text treats as a domain concept. Use the **complete span**.
2. **Existing-node sweep.** For every card marked `in_text: yes`, decide:
   - mentioned here in the same sense → an **existing mention** (with role, the type of what the text refers to, and exact evidence);
   - or not → a **not-mention**, with reason `different_sense`, `generic_use` or `inside_longer_term`.
3. **Match.** For each step-1 term:
   - **SAME** as a card under the strict rule → an existing mention;
   - otherwise → **NEW**.

   The strict rule: same only if interchangeable in any sentence of the book. Kind / instance / part / version / predecessor is never same. When unsure, the term is new.
4. **Relate or confirm independence.** For each NEW concept, check every card:
   - if **this text** relates it to a card that the text names → `anchored`, with anchor(s) {node_id, anchor_type, cue}. The cue is a verbatim quote.
   - otherwise → `independent`, with `independence_check` filled in.
5. **Anchor-aided discovery.** Having read the cards, add any further concept in the text that relates to a card and that step 1 missed. Mark it `found_via_anchor: true`.
6. **Role, type, evidence** for every item, then the final checklist.

**Complete-span rules** (added to DEFINITIONS):
- Use the whole term as the text names it ("program counter", not "counter").
- If the text gives a long form and an acronym, the name is the long form and the acronym is an alias.
- Keep compound terms whole. List the head word on its own only if the text also uses it on its own as a concept.
- Don't stretch a span over words that are not part of the name: articles, quantities, ordinary adjectives.
- A device or component and the process it performs are separate concepts ("scheduler" vs "scheduling").
- **Not concepts:** everyday words used in their everyday sense, descriptive phrases, and specific values (numbers, sizes, rates, dates).

### 3.4 Single call (G1) or two passes (G2)
- **G1:** all six steps in one call.
- **G2:**
  - **Pass A, the open pass:** steps 1 and 6, with **no** EXISTING NODES block. Every term is new. This is the independent extraction: the model cannot fixate on known nodes.
  - **Pass B, the linking pass:** steps 2–6, with EXISTING NODES and Pass A's list (given as "terms found by an independent reader"). Pass B outputs the final list.
- **Choice:** made on IIR dev by the pre-registered rule (§7). G2 matches the owner's description most closely; G1 is cheaper.

### 3.5 Few-shot bank (complete, valid concepts)
- **Source:** 6 worked examples + 1 corrective-round example, **written for the bank** in computer-science areas that **neither book covers**: operating systems, databases and computer architecture.
  - No networking and no IR content, so no example paraphrases a P&D section we score or spot-check, and FACE label conventions stay out.
  - A test checks that no example passage matches any section text.
  - Draft: `configs/fewshot/concepts_v4_draft.yaml`. The owner approves it at STOP 1.
- **What the examples cover:**
  - complete spans with acronyms;
  - compound terms kept whole;
  - component vs process;
  - an existing mention, and not-mentions (`different_sense`, `inside_longer_term`);
  - anchors (part_of, acts_on, performed_by, used_for, kind_of + compared_with on one concept, uses, property_of);
  - independent concepts (including cold start);
  - `found_via_anchor`;
  - a look-alike kept separate;
  - `refined`;
  - negatives (a partial span, a descriptive phrase, a value, a verb use).
- **Rendering:**
  - **G1 and Pass B** show the full expected output.
  - **Pass A** shows every item as a new concept: the examples' existing mentions are rendered as new concepts too, so Pass A never learns to skip basic terms. `refined` becomes `defined` there, since Pass A has no cards.
  - **Corrective iterations only** add example 7 (GIVEN ITEMS + `hint_responses`). This follows PiVe App. G, which swaps in a demonstration that contains the given triples. Backfill calls do not use it.
- **Order** is fixed (Lu et al. 2022). The bank's token cost goes in the preflight.
- **If v3 adopted E4** (few-shot from other dev sections): the bank replaces it.

### 3.6 Output schema and node properties
Per section, the generator returns:
- `existing_mentions`: [{node_id, surface, node_type, role ∈ used | mentioned | refined | defined, evidence, para}].
  - `node_type` is the type of what the text refers to here (used by C2).
  - `defined` is allowed only when the card shows `def —`.
- `not_mentions`: [{node_id, reason}].
- `new_concepts`: [{name, aliases, node_type, role, evidence, para, extraction_origin ∈ anchored | independent, anchors: [{node_id, anchor_type, cue}], independence_check, found_via_anchor}].
- `hint_responses`: [{hint_id, decision ∈ added | rejected, reason}]. Only in corrective iterations and backfill.

**New node properties** (recorded at first occurrence):
- `extraction_origin`;
- `anchors`;
- `found_via_anchor`;
- `added_via_hint` (null, or the hint type).

Anchors from later sections accumulate, deduplicated, in the mention log. Each mention records `linked_by` ∈ `generator` | `verifier_hint` | `backfill`.

**Anchor types:** the relation of the new concept *to* the node.
- `kind_of`, `instance_of`, `part_of`, `property_of`;
- `performed_by`, `acts_on`, `uses`, `used_for`;
- `requires`, `causes`, `compared_with`;
- `other`.

Each type is glossed in the prompt and mapped to a registry family in config, for pair priority only (§6.3). **An anchor is never an edge.**

### 3.7 Propagation replaced: forward sweep + backfill
CR-007 E3 tagged an accepted concept wherever its form occurs, **in both directions**, with role `mentioned`. It is deleted (its config flag goes; its history stays in git). It is replaced by two steps in which the generator decides every match:

- **Forward (each section): the existing-node sweep** (§3.3 step 2) and verifier rule M1. These cover nodes from **earlier** sections.
- **Backward (end of each chapter): the backfill pass.**
  - **What it covers:** nodes first created in this chapter whose forms also occur, unrecorded, in **earlier** sections. This is the "late-counted edges" case.
  - **Detection ($0):** the longest-match detector finds them.
  - **Scope:** "earlier" means every earlier section in the run (the book so far), not only this chapter.
  - **The call:** each affected earlier section gets **one** call. It uses a short **mention-check** prompt (the same in G1 and G2): ROLE, the roles and strict "same" rule from DEFINITIONS, the section text, the given cards as GIVEN ITEMS (`backfill_mention`), and a schema with only `existing_mentions` and `hint_responses`. The usual accept-with-evidence / reject-with-reason protocol applies.
  - **Checks:** F2, F3, C1 and C2 run on the output. Failing mentions are dropped; there is no corrective round.
  - **Limits:** backfill cannot add new concepts and is not iterated. Its call count comes from the detector, so it is known before spending.
  - **Effects:** accepted mentions get `linked_by: backfill` and can move a node's `first_section` earlier (CR-007 §4.2). Snapshots and `kg organise` are computed after the run, so they pick this up.

**The matcher becomes a detector.** The CR-007 §4.1 longest-match matcher is kept for retriever string hits, M1 and backfill detection. **It never writes a mention.**

**Why:**
- **The decisive reason:** word sense. String propagation cannot tell "register" the verb from a CPU register, or a switch's output "port" from a transport port. The generator confirms each match with evidence, or rejects it with a reason, and both are logged.
- **Supporting evidence (PiVe Table 3):** feeding corrections back into the prompt beat applying them offline. Offline correction still helped, so PiVe supports "online beats offline", not "offline is useless".

### 3.8 Generator links are merges
- **When a link is a merge:** an existing mention whose surface form differs from every one of the node's forms (after R1).
- **Rules it must obey:**
  - the strict "same" rule;
  - the lexicon;
  - the type-compatibility map.
- **Logging:** `merges.jsonl`, with `rule_id: G-link` and the evidence. Non-trivial G-links are sampled on the owner sheet.
- **Trivial links** (the R1 key equals a node form) need no review.

---

## 4. Module 2: the verifier (SAC-KG rules + PiVe iteration)

The verifier is **code, not a model**: parameter-free and $0, like SAC-KG's. It never reads a rationale, so it cannot be steered by one.

### 4.1 Rule repository: `configs/concept_gvp.yaml` → `verifier.rules`
This is our equivalent of SAC-KG's RuleHub.

| ID | Category | Fires when | Action |
|---|---|---|---|
| Q1 `quantity_insufficient` | quantity | items (new + existing mentions) < max(3, ρ × tokens / 100). ρ is calibrated at STOP 1 from IIR dev gold density | One corrective round per section at most. If it still fires afterwards, it becomes a logged warning and no longer blocks "Correct", since short sections may never reach the floor |
| F1 `schema_invalid` | format | JSON, schema or enum error | Re-prompt |
| F2 `quote_not_verbatim` | format | evidence or cue is not a verbatim substring (after whitespace normalisation) | Auto-fix whitespace; otherwise flag the item |
| F3 `span_not_in_quote` | format | the item's surface (or an alias) is not inside its evidence quote | Flag the item |
| F4 `unknown_node` | format | `node_id` not in the shown card set | Mention: flag it. Anchor: **drop that anchor only** |
| F5 `anchor_cue_invalid` | format | the cue does not contain the new concept (its name or an alias), or the anchor node is not named in the cue, its paragraph or the paragraph before. A node form inside the new concept's own span counts (e.g. "clock" in "clock cycle") | **Drop that anchor only** |
| F6 `origin_incomplete` | format | `independent` without `independence_check`, or `anchored` without anchors | Auto-fix: if every anchor was dropped, set `independent` with `independence_check: "anchor removed by verifier"`; otherwise flag |
| C1 `lexicon_violation` | conflict | a link or same-as decision across an approved `different` pair, or two nodes for one `same` set. **Anchors and relation edges between a `different` pair are allowed**; only treating them as one node is blocked | Flag |
| C2 `type_conflict` | conflict | an existing mention whose `node_type` is incompatible with the card's type (CR-007 §4.3) | Flag |
| C3 `duplicate_new` | conflict | a NEW concept whose R1 key equals a shown node's form | Auto-fix → existing mention (unless C1) |
| C4 `role_conflict` | conflict | `defined` on a node already defined earlier | Auto-fix → `refined` |
| C5 `self_anchor` | conflict | a new concept anchored to a node with the same R1 key | Treated as C3 |
| M1 `missed_existing_mention` | coverage | a card with `in_text: yes` that is neither recorded nor in `not_mentions` | Hint |
| M2 `partial_span` | coverage | an item's span is the **final word(s)** of a **term-like** longer candidate in the same evidence quote (definition below) | Hint |
| M3 `possible_anchor_missed` | coverage | an `independent` concept shares a head noun or R1-key token with a card named in the same sentence | Hint |
| M4 `missed_candidate` | coverage | optional (decided at STOP 2): a definition-pattern term ("X is a/an…", "called X", "known as X"), an R2 long form, or an emphasised term (the section's `emphasized_terms` from the M1 parser, where available) that no item covers | Hint |

**M2: when a span counts as partial.** This keeps M2 from firing on ordinary modifiers, or on a term that is part of another term.
- **Strip first:** determiners, quantifiers, numerals and possessives ("each", "several", "its", "five", "an SSD's").
- **Term-like longer candidate:** the remaining chunk must be one of:
  - a noun–noun compound (dependency `compound`, e.g. "signal handler");
  - an R2 long form (e.g. "cyclic redundancy check (CRC)");
  - an emphasised term (the section's `emphasized_terms` from the M1 parser, where available);
  - a card or lexicon form;
  - an adjective + noun chunk that recurs ≥ 2 times in the chapter.
- **All three must also hold:**
  1. the item is the **final word(s)** (the head end) of that candidate, compared on surface tokens, not lemmas;
  2. the longer candidate is **not already an item**;
  3. the short form does **not** also occur on its own in the same quote.
- **Examples:**
  - fires: "handler" inside "signal handler";
  - does not fire:
    - "each incoming frame", "a tiny capacitor" (not term-like);
    - "DRAM" inside "DRAM cell", "Ethernet" inside "Ethernet frame" (a modifier, not the head; usually a separate concept);
    - "lock" near "two-phase locking" (different tokens).

**All M rules skip items the generator has already rejected with a reason.** This means "Correct" is always reachable.

**"Correct"** = after auto-fixes, no Q, F, C or M rule fires.

### 4.2 Correction (SAC-KG §3.2 and App. B)
1. **Auto-fixes first** (F2 whitespace, F6, C3, C4, anchor-level drops), logged as `verifier_autofix`.
2. **Few precision flags, no coverage flags:**
   - SAC-KG deletes the flagged triples when there are fewer than its threshold (3), and regenerates when there are more. It does not say what happens at exactly 3.
   - We drop the flagged items **when ≤ 3 items carry only F/C flags**. They go to `rejected.jsonl` with the rule id.
3. **Otherwise** (more than 3 flagged items, a Q1 flag, or any M flag): run a corrective iteration (§4.3).
   - The rule that coverage flags always trigger a re-prompt is **ours**, not SAC-KG's: missing items cannot be fixed by deleting.

### 4.3 Iterative prompting (PiVe)
- **The new prompt** = the original generator prompt (same inputs) + a **CORRECTIONS** block.
  - It contains one corrective instruction per error type found. This is the equivalent of SAC-KG's Table 6; the wording is in config.
  - It also contains the **GIVEN ITEMS**: the specific hints, i.e. missed cards, longer spans, possible anchors and candidates.
  - Example 7 is added to the EXAMPLES (§3.5).
  - PiVe's wording, adapted: *"Extract the concepts again, and also review the given items. Include each one the text supports, with role and exact evidence, or reject it with a reason."*
- **Deliberate deviation:** the generator **may reject a hint**.
  - PiVe adds the given triples outright because its verifier is trained. Ours are string rules, and forced inclusion would bring back propagation's false positives.
  - Reasons: `different_sense`, `generic_use`, `inside_longer_term`, `not_a_concept`, `not_related_here`.
  - A rejected hint is logged and not sent again.
- **Hints accumulate across iterations** (PiVe).
- **Regenerate, don't patch.** The generator starts again from the original inputs, as in PiVe. In G2, only Pass B is re-run.
- **Carry-forward (our addition, against churn):**
  - an item that passed every rule in an earlier iteration and disappears later **without** being rejected is restored — unless its span overlaps an item in the latest output (the model may have replaced a partial span itself);
  - restored items are counted and reported.
- **Stop** when any of these holds:
  - the verifier returns Correct;
  - **max_iterations** is reached: ≤ 3, as in PiVe; the exact value is chosen on dev (§7);
  - an iteration changes nothing;
  - the per-section call budget is reached.
- **After stopping:**
  - remaining F/C flags → drop, with the rule id;
  - unresolved M1 → `unconfirmed_mention` (not counted; listed);
  - unresolved M2–M4 → logged.
- **Stored per section:** iteration-0 and every iteration's output, so later analysis can be replayed.
- **Same model in every iteration.** The generator's tier does not change inside the loop, and the CR-001 escalation rule is not used here.
- **Rule quality:**
  - hit rates are reported per rule;
  - the owner audits a sample of flags (§10);
  - a rule with a high false-flag rate becomes a warning in the next version (DECISIONS).

### 4.4 Optional semantic check (arm V2)
- **What:** CR-007's LLM concept verifier, unchanged: a fresh context, the strong tier, and verdicts `supported` | `not_supported` | `wrong_span` | `wrong_type`. It runs **once, after the loop**, on new concepts only.
- **Why it is optional and measured:**
  - PiVe's evidence is about **self**-feedback, where it gave no gain.
  - V2 is a different setting: another tier, a fresh context, acting as a filter rather than feedback. So PiVe neither supports nor rules it out.
- **Adoption:** only if it wins on dev under the rule.
- **If v3 already included E7:** V2 is simply v3's verifier kept on.

### 4.5 Not in this CR
**PiVe's trained verifier** (a T5 trained on gold graphs with one item deleted).
- **Why not now:** it needs gold concept lists per section. Our only gold is IIR dev (~485 concepts, 13 sections), which also selects the configuration.
- **When to revisit:** if the M rules leave a clear recall gap, in a later CR.

---

## 5. Module 3: the pruner (SAC-KG-inspired)

### 5.1 Role, and how it differs from SAC-KG's
- **What it decides:** for each **verified NEW concept**:
  - **growing** → becomes a KG node. It is shown to the generator in later sections, eligible for relation pairs and counted in the sphere.
  - **pruned** → not a node. Kept in `pruned.jsonl` with p(growing), so it can be recovered.

  Mentions of existing nodes are not re-pruned.
- **Deviation from SAC-KG, stated plainly:**
  - SAC-KG's pruner only stops a tail entity from being **expanded**: the triple stays in the KG. It is trained on head vs tail entities.
  - Ours decides **whether the term becomes a node at all**, and it is trained on concept vs non-concept. It is a concept-validity classifier in SAC-KG's growing/pruned form.
  - **The reason:** our verifier is rule-only and has no semantic "is this a concept?" check, so the pruner takes on that job as well as gating expansion.
  - **What SAC-KG's ablation supports:** gating expansion (no pruner: 44.82% vs 76.74% at level 3). It does not test deleting nodes. Our evidence for the deletion part comes from the owner's false-prune sample (§10).

### 5.2 Model (small, local, $0 per call)
- **P1:** logistic regression on the term's embedding (the embedding model already used for merges) plus features:
  - token count;
  - contains a digit or unit;
  - all-caps acronym;
  - noun phrase vs clause;
  - in the general-knowledge bank (§5.6);
  - exact CSO/ACM match (if loaded);
  - node type.
- **P2:** flan-T5-small (or T5-small) + LoRA, outputting `growing` / `pruned` from the term text. Settings follow SAC-KG: 2 epochs, batch 64, learning rate 1e-3.
- **Models trained locally:** **four** per arm. Three are leave-one-chapter-out on dev; one is trained on all dev. Model files are gitignored; tests use a stub.
- **Input:** like SAC-KG, the term's form, not the passage.
  - SAC-KG App. I.4 argues that deciding "whether an entity can function as a head entity does not necessitate an extensive domain-specific knowledge".
  - It also relies on DBpedia already containing the domain's basic nouns. That part does not carry over.
  - **Our training rows are IR, not networking (§5.3), so for P&D the pruner is out of domain.** The owner's P&D false-prune sample (§10) is the real check of it. This is also why τ is recall-safe.

### 5.3 Training data
- **Rows come from IIR dev only:**
  - **growing:** gold concepts;
  - **pruned:** candidate noun phrases (from the candidate-term step, BUILD_PLAN M5 task 1, `textbook/stats.py`) that are gold in **no** dev section.
- **Conflicts:** labels are decided per term after dedup. A term that is gold in any dev section counts as growing.
- **Features, not rows:** CSO membership and bank membership are features only. Neither is a source of training rows, so no feature defines its own label.
- **Excluded:**
  - IIR test chapters;
  - **P&D owner marks** (CR-005/007), because they come from the same ch. 1–3 the owner re-checks in this CR. They may be added for chapters beyond the slice, later.
- **Which model is used where:**
  - **dev chapter k:** the model trained on the other two dev chapters;
  - **the test run:** starts from the final dev run's state (ch. 1–3 already pruned leave-one-chapter-out), then uses the all-dev model from ch. 4 on;
  - **P&D:** the all-dev model.

### 5.4 Decision rule and guards
- **Rule:** prune if p(growing) < τ.
  - τ is chosen on dev: the highest exact micro F1 among values whose recall drops by **≤ 0.01** relative to no pruner. This is pre-registered.
  - If no τ > 0 meets that, τ = 0. Report it honestly.
- **Guards:**
  1. A lexicon `same` form is always growing.
  2. A concept with role `defined` that falls below τ is pruned like any other, but flagged `pruned_defined` and **always** listed on the owner sheet.
  3. Pruning is **per occurrence.** A term pruned in ch1 is judged again when extracted later.
  4. The lexicon `different` guard applies.

### 5.5 Where pruned items go
- **A pruned value-like term** (digits or units) with an anchor to a Parameter or Property node is stored as an **attribute** of that node: {value, evidence, section}.
  - Expected to be rare, since the prompt tells the generator not to extract values. It is a salvage path, reported as a count.
- **Everything else** goes to `pruned.jsonl`.
- **Pruned items are never shown as cards and never paired.**

### 5.6 The general-knowledge bank
- **What it is:** the owner's planned list of common nouns.
- **How it is used:**
  - as a P1 feature;
  - as a hard prune rule for **bare** generic nouns (no domain modifier).
- **Who approves it:** the owner approves its entries.
- **What is never in it:** CR-006's domain foundations (link, node, network, frame).

---

## 6. Downstream hooks

### 6.1 Canonicalisation
- **Where it runs:** after the pruner, on growing new concepts.
- **Order:** R0 lexicon → R1–R3 → R4 LLM (CR-008). New concepts from the same section are compared with each other and with the registry.
- **Expected effect:** far fewer R4 calls. Report R4 calls against CR-007.

### 6.2 Mentions and first occurrence
- **Mentions** (generator, verifier-hint and backfill) feed spread counts, first occurrence and pair enumeration.
- **Unchanged:** the CR-007 §4.2 semantics.
- **Report:** mention counts against CR-007's propagated counts, including the number of `different_sense` rejections.

### 6.3 Relation pair selection (CR-007 §5.3)
- **Coverage phase, in order:**
  1. **Anchor pairs** (new concept ↔ its anchor node). Use the anchor's cue sentence as the evidence sentence when it mentions both.
  2. The other verified defined/used concepts.

  Then the fill phase.
- **The anchor type is never shown to the relation generator or the relation verifier.** It only sets priority.
- **Report:**
  - **anchor → edge conversion:** the share of anchor pairs that end with an accepted edge;
  - the agreement between the anchor type's family and the accepted relation's family;
  - the NO_RELATION rate on anchor pairs.
- **Expansion round:** anchored concepts with 0 edges go first.

### 6.4 Unchanged
These come from CR-007/CR-008 and are not changed by this CR:
- the registry (v1.3) and relation prompt (v2.1);
- the relation verifier;
- prerequisite judgement;
- fusion;
- the misconception stage;
- the sphere code.

Generator links (§3.8) add aliases to the node; they never create an edge.

---

## 7. IIR experiments (dev ch. 1–3; tune on dev, test once)

**Protocol:**
- Every run processes sections in book order.
- Cards come only from the run's own growing nodes.
- The pruner is leave-one-chapter-out on dev.
- **Until step 4**, every verified new concept counts as growing.
- **Backfill** runs in every arm.

**Scoring:**
- **New concepts:** scored as in v3 (name + aliases, as the current scorer does).
- **Existing mentions:** scored like new concepts, on the surface form in that section **plus** the node's name and aliases. Mentions must not be scored more strictly than new concepts; v3's outputs were all new concepts.
- **Unconfirmed mentions and pruned items:** not predictions.

**Selection metric for this CR:** **exact micro F1 on dev.**
- **Why exact:** CR-007 selected on lenient, but this CR's main target is span completeness, which lenient matching partly hides. Exact is also the headline against FACE.
- **Tie rule:** within 0.02, the simpler arm wins (fewer calls or components).
- **Also reported:** lenient micro F1 and macro F1. **1-gram recall** is watched, since complete spans could lower it.

**Fixed by design** (owner requirements; not chosen by the rule):
- all three modules;
- existing nodes visible to the generator;
- anchors;
- propagation replaced by sweep + backfill;
- the PiVe loop.

**Chosen on dev by the rule:**

| Step | Arms | Decides | How it is run |
|---|---|---|---|
| 1 | **G1** vs **G2**, each with the verifier, loop max 3, no pruner | the generator form | live runs |
| 2 | max_iterations ∈ {1, 2, 3} on the step-1 winner (PiVe saw the biggest jump in the first iteration) | the loop depth | replay of stored iterations |
| 3 | ± **M4** `missed_candidate` hints | whether M4 is on | live run |
| 4 | pruner **P1** vs **P2**, with τ under §5.4 | the model and τ | replay |
| 5 | ± **V2** LLM concept verifier | whether V2 is on | live run (V2 calls only) |

**Reported, not selected** (all replays, $0):
- **B0** = v3 (CR-007 STOP 2 outputs);
- **iteration-0** of the step-1 winner (the generator alone, no corrective rounds);
- **L0** = iteration-0 with the rules applied **offline**: auto-fixes, flagged items dropped, M1 hints written as mentions, M2 spans replaced, no re-prompt. This is PiVe's "iterative offline correction", and close to the old forward propagation.
  - It is optimistic: its cards came from loop-corrected earlier sections.

**Replay caveat:** a replay cannot show how a different depth, the pruner or offline fixes would have changed the cards for later sections. So the chosen configuration is then **run once end-to-end on dev**. Its numbers are the reported dev numbers.

**Report:**
- exact and lenient micro F1, and macro F1;
- recall by n-gram length 1–4;
- precision by role;
- **verifier:**
  - an iterations histogram;
  - flags per rule;
  - the share of sections reaching Correct;
  - hints accepted vs rejected;
  - churn, and items carried forward;
- **backfill:** calls and mentions added;
- **pruner:** prune rate;
- **anchors:** anchored vs independent share;
- cost per section.

**Test:**
- **v4 runs once** on the same test split as CR-007, scored the same way.
- It starts from the final dev run's state (§5.3) and processes the following chapters in book order. Chapters in between that are not scored are context only.
- v3's CR-007 test result is reused, not re-run.
- The comparison arms in §7.1 also run once each on the test split (pre-registered; never used for selection).
- **Headline table (test, exact micro F1):** B0 (v3), the SAC-KG-style arm, the PiVe-style arm, the ConExion arm, v4, and FACE (0.76, supervised).

### 7.1 Comparison with published methods (pre-registered; reported, never selected)
**Why this is needed:** the published numbers of SAC-KG, PiVe and ConExion cannot be compared with ours directly. They differ in:
- the task (triples or keyphrases vs concepts);
- the data (rice corpora, Wikidata texts, scientific abstracts vs a textbook);
- the scoring (GPT-4 judge, triple F1, keyphrase F1 vs FACE human labels).

So each method's core idea is **re-implemented as an arm on our benchmark**: the same IIR sections, gold, scorer and exact micro F1. Every arm is fixed now, before results.
- **Dev:** each arm runs on IIR dev and is reported in the dev table.
- **Test:** each arm runs **once** on the test split.
- **Selection:** no arm is ever a selection candidate (`selection_eligible: false`).

| Arm | Generator | Verifier / loop | Pruner | What it isolates |
|---|---|---|---|---|
| **B0** | v3 prompt (CR-007), no cards | none | none | The baseline (existing outputs, $0) |
| **C-SAC** (SAC-KG-style) | v3 prompt, no cards | SAC-KG's own checks only: Q1 and F1–F3, with its error-type prompts. ≤ 3 flagged items → delete; more → regenerate **once**. No coverage hints, no loop | P2 (T5 + LoRA), using its growing/pruned label directly, as SAC-KG does (no τ). Leave-one-chapter-out on dev | SAC-KG's verifier + pruner on our task |
| **C-PiVe** (PiVe-style) | v3 prompt, no cards | Missing-item hints only (M2 longer spans and M4 missed candidates; M1 needs cards, so it does not apply). As in PiVe, given items are **added outright** (no rejection) and accumulate. Regenerate, ≤ 3 iterations, stop when no hints remain | none | PiVe's iterative prompting on our task |
| **C-PiVe-off** | as C-PiVe | The same hints applied **offline**: added to the output with no re-prompt (PiVe's "iterative offline correction") | none | Online vs offline, replicated on our task |
| **C-ConExion** | ConExion's best published setup (Norouzi et al. 2025): their prompt template, "few-shot 1-random", and their filter that keeps only concepts present in the text. The one example is a random IIR **dev** section with its FACE labels (fixed seed; never the section being extracted; never a test section). Our bulk model | none | none | A published LLM concept extractor on our data |
| **v4** | §3 | §4 | §5 | Our design |

**Honest caveats** (stated wherever these arms are reported):
- C-SAC and C-PiVe are **SAC-KG-style and PiVe-style**, not reproductions. PiVe's verifier is a trained model; ours gives rule hints. SAC-KG extracts triples around a root entity; here only its checks and pruner are carried over.
- C-ConExion uses our model, not their best one (Llama-3-70B). §7.2 separates the effect of model from method.

### 7.2 External check on ConExion's public benchmark
**Why ConExion:** ConExion (Norouzi, Hertling & Sack 2025, NSLP @ ESWC 2025, CEUR 3977) is the closest published LLM method to our task.
- It extracts **all** domain concepts present in a text, not just the key ones, and scores them by **exact** match.
- It releases code and data.
- No LLM study evaluated on the FACE/IIR benchmark was found, so this is the best available external comparison.

**What runs:** on SemEval-2017 Task 10 (test, 100 documents) and Inspec (test, 486 documents), each scored with ConExion's scorer and metrics (P / R / F1 exact; F1@5 and F1@10 secondary):
1. **ConExion's prompt with our bulk model.** This separates model from method.
2. **v3** (cold start).
3. **v4 cold start:** each document is independent, so there are no cards and no backfill. The verifier and the pruner are on; the pruner was trained on IIR, so it is out of domain here.

**What they are compared with:** ConExion's published table. Their best: Llama-3-70B few-shot 1-random, F1 0.451 (Inspec) and 0.311 (SemEval-2017).

**Validity gate:** before any of our runs, re-score ConExion's released outputs, if the repo includes them, with the adopted scorer. It must reproduce their published numbers (±0.005). If no outputs are released, re-run their prompt with our model and only report like-for-like rows.

**Caveats:**
- These are scientific abstracts with keyphrase or ScienceIE-style gold, not exhaustive concept lists. Precision is therefore under-estimated for every system.
- The run tests the generator, verifier and pruner without KG awareness, which is v4's main idea.

**Data:** these datasets stay local and are never committed, the same rule as the IIR text.

---

## 8. P&D ch. 1–3 re-run
- **Order:**
  1. concepts (generator → verifier → pruner, with backfill at each chapter end);
  2. canonicalisation (R0–R4);
  3. pair selection (anchors first);
  4. relations (prompt v2.1 + verifier + expansion round);
  5. prerequisites;
  6. fusion;
  7. the misconception stage (CR-008 §5);
  8. structural checks;
  9. snapshots;
  10. `kg organise`;
  11. report refresh.
- **Bookkeeping:** new `run_id` and `org_id`; the CR-007 and CR-008 runs are kept.
- **Cost safety:** preflight every stage. Byte-identical prompts hit the LLM cache at $0; the preflight shows expected cache hits.

## 9. Metrics: CR-008 run vs CR-009 run

| Metric | Reported |
|---|---|
| New nodes; existing mentions by `linked_by`; not-mentions by reason; `unconfirmed_mention` | Yes |
| Partial-span rate: detector before vs after, plus the owner's estimate | Should fall |
| G-links: trivial / non-trivial; owner precision for non-trivial (Wilson CI); R4 calls vs CR-007 | Yes |
| Anchored vs independent share, overall and by chapter; anchor types; `found_via_anchor`; owner anchor precision | Yes |
| Verifier: iterations; flags per rule; Correct-reached share; hints added / rejected; churn and carry-forward; owner false-flag rate for the 2 busiest rules | Yes |
| Backfill: calls; mentions added; `first_section` changes | Yes |
| Pruner: prune rate; attributes; `pruned_defined`; owner false-prune rate (Wilson CI) | Yes |
| Concept precision (owner, Wilson CI) by independent / anchored / found_via_anchor | Yes |
| Anchor → edge conversion; family agreement; NO_RELATION rate on anchor pairs | Yes |
| Linked share overall and for `defined` concepts; unlinked share; late-counted edges | Should improve; late ≈ 0 |
| Sphere: core–periphery Δρ; soft core Jaccard vs CR-008 | Yes |
| Misconception layer: items vs the CR-008 run, by perturbation type; how many re-linked to new correct edges | Yes |
| Cost per stage vs preflight | Yes |

## 10. Owner sheets

All sheets follow the CR-003 rules: in `data/interim/checks/`, saved by the owner to `data/gold/`; no model scores shown; any pre-fill labelled.

**STOP 1:**
- **Few-shot bank approval** (~10 min): approve / edit / reject each example.
- **Propagation audit** (20 items, ~5 min): same sense / different sense.

**STOP 3** (~30 min):
- **Concepts** (40; ~15 min):
  - 12 independent, 12 anchored, 6 found_via_anchor, 10 random;
  - judgement: valid complete concept / partial span (write the full one) / not a concept / generic;
  - for anchored items, also judge the anchor: correct / wrong / should be independent.
- **Non-trivial G-links** (≤ 15; ~5 min): same / not same.
- **Pruned** (15: 10 random + every `pruned_defined`, up to 5 more; ~5 min): correctly pruned / should be a node.
- **Not-mentions and backfill rejections** (10; ~3 min): correct rejection / actually a mention.
- **Verifier flags** (10 from the two busiest rules; ~3 min): valid flag / false flag.

## 11. Tests (no network, no key)

- **Generator:**
  - prompt sections appear in the fixed order;
  - G2 Pass A has no EXISTING NODES block, and its examples render every item as new;
  - main-pass cards come only from growing nodes in earlier sections, and the cap holds;
  - example 7 appears only in corrective iterations;
  - no example passage matches any section text;
  - the schema validates.
- **Verifier:**
  - a fixture for each rule (Q1, F1–F6, C1–C5, M1–M4);
  - **the bank's expected outputs raise no flags**;
  - M2 fires on "handler" inside "signal handler", but not on "each incoming frame" or on "DRAM" inside "DRAM cell" (when "DRAM cell" is an item);
  - F4/F5 drop only the anchor; F5 accepts an alias of the new concept and a node form inside the new span;
  - C1 blocks linking but allows an anchor between a `different` pair;
  - auto-fixes;
  - ≤ 3 F/C-only items → drop, with no call;
  - Q1 triggers at most one round, then becomes a warning;
  - the loop stops on Correct / max / no change / budget;
  - hints accumulate; rejected hints are neither re-sent nor re-flagged;
  - regeneration uses the original inputs;
  - carry-forward restores a dropped clean item but not an overlapping one;
  - the verifier makes no API call.
- **Backfill:**
  - only detector-hit sections get a call;
  - it uses the mention-check prompt;
  - F2/F3/C1/C2 run on its output;
  - no new concepts;
  - not iterated;
  - `first_section` updates.
- **Pruner:**
  - stub model; τ applied;
  - leave-one-chapter-out models on dev; the test run starts from the dev state;
  - no training rows from CSO, the bank or P&D marks;
  - `same` forms always growing;
  - `pruned_defined` always listed;
  - value → attribute;
  - pruned items are never cards and never paired.
- **Propagation:** no code path writes a mention without a generator or backfill decision.
- **Downstream:**
  - anchor pairs first;
  - no anchor information in relation prompts;
  - G-links logged with evidence.
- **Comparison arms:**
  - each arm is marked `selection_eligible: false` and cannot win the selection rule;
  - C-SAC makes at most one regeneration and uses no coverage rules;
  - C-PiVe never lets the generator reject a hint;
  - C-ConExion's example is never a test section, nor the section being extracted;
  - the external scorer reproduces a fixture of ConExion's published scoring.
- **Hygiene:** nothing writes to `data/gold/`; IIR, Inspec and SemEval-2017 text is not committed.

## 12. Docs
- **`ARCHITECTURE.md`:**
  - the concept stage as generator → verifier → pruner;
  - cards;
  - anchors;
  - the rule repository and the loop;
  - backfill;
  - the pruner and its deviation from SAC-KG;
  - propagation replaced.
- **`DECISIONS.md`:**
  - G1/G2, max_iterations, M4, the pruner model and τ, V2;
  - ρ;
  - the switch to exact F1 for this CR's selection;
  - rule demotions;
  - the bank version.
- **`CLAUDE.md`**, new rules:
  - "In the main pass, the concept generator sees only growing nodes from earlier sections of the same run, never gold. Backfill may show later nodes to earlier sections, as hints only."
  - "Mentions are written only by the generator (main pass or backfill), with evidence. String matching only produces hints."
  - "The concept verifier is rule-based code. Any LLM check is a separate, measured arm."
  - "Pruned concepts are never shown to the generator and never paired."
  - "Anchors set pair priority but are never shown to the relation generator or verifier."
- **`PROGRESS.md`:** a CR-009 row with the §9 table and the run IDs.

## 13. Cost and time (estimate; confirm with dry runs)

| Item | Estimate |
|---|---|
| IIR dev live arms: G1, G2, M4 (bulk tier, ≤ 5 calls per section) + V2 calls (strong tier) + the final end-to-end dev run | ~$0.4–1.2 |
| IIR v4 test, once | ~$0.3–1.0 |
| Comparison arms C-SAC, C-PiVe, C-ConExion (dev + test once; C-PiVe-off is a replay) | ~$0.3–0.8 |
| External check on Inspec + SemEval-2017 test (3 systems, short abstracts) | ~$0.2–0.6 |
| Pruner training (local) + embeddings | ~$0–0.05 |
| P&D concepts ch. 1–3 (generator → verifier → pruner) + backfill | ~$1–3 |
| Canonicalisation R4 (fewer calls than before) | ~$0.2–0.5 |
| Relations + verifier + expansion round (cache hits for unchanged prompts) | ~$3–7 |
| Prerequisites + fusion | ~$1–3 |
| **Total** | **≈ $7–16; hard cap $18** |

The per-call budget check and per-stage caps stay as in CR-005 §9.

**Owner time:**
- STOP reviews: ~30 min;
- STOP 1 sheets: ~15 min;
- STOP 3 sheets: ~30 min.

## 14. If time is short

Drop things in this order:
1. the V2 arm;
2. the external check (§7.2), keeping the IIR comparison arms;
3. P2 (keep P1). C-SAC then uses P1's label at τ = 0.5 and says so;
4. M4;
5. the L0 and iteration-0 rows;
6. the G1 vs G2 comparison (use G2).

**Never drop:**
- cards with anchors and not-mentions;
- backfill;
- the rule verifier and the PiVe loop;
- the pruner (P1);
- the IIR comparison rows (B0, C-SAC, C-PiVe, C-ConExion), because they are the evidence for the design;
- the preflight;
- human-label measurement.

## 15. What we take from each paper, and what we don't

| Paper idea | Here |
|---|---|
| SAC-KG verifier: rule-based quantity / format / conflict checks; error-type prompts; few flagged items → delete, many → regenerate | Kept, with concept rules (Q, F, C). Ours: coverage flags (M) always re-prompt |
| SAC-KG pruner: T5 + LoRA, growing vs pruned, gating expansion | P2 (same model family and settings) and P1. **Deviation:** ours also decides node creation and is trained on concept vs non-concept (§5.1) |
| SAC-KG retrievers: relevant text + external KG triples as format examples | **Inspiration only.** Our cards are the graph being built (closer to iText2KG). Examples come from a fixed, approved bank |
| PiVe: append the verifier's output to the prompt; iterate to "Correct", max 3; corrections accumulate; corrective rounds use a demonstration with given items | The loop in §4.3, example 7, and the coverage rules (M) that produce PiVe-style "missing item" hints |
| **Not taken:** GPT-4 as judge | Every accuracy figure comes from human labels (project rule) |
| **Not taken:** PiVe's trained verifier | No per-section gold beyond IIR dev (§4.5) |
| **Not taken:** PiVe adding the given triples unconditionally | Our hints can be rejected with a reason |
| **Added:** carry-forward of clean items | PiVe takes the last iteration as-is. Ours restores clean items that were dropped without a reason |

**Caveats to state when presenting:**
- SAC-KG reports recall as a count of triples, not a rate, and its precision is LLM-judged.
- PiVe's gains are modest in absolute terms (KELM-sub triple F1 13.50 → 23.11 with the unified verifier), and its verifier only catches missing triples.
- Neither paper extracts concepts from textbooks. §7 tests whether the ideas transfer.

## 16. Pipeline at a glance

```
growing nodes (earlier sections) ──► retriever ──► cards ─┐
lexicon (R0 look-alikes) ─────────────────────────────────┤
section text (P1..Pn) + few-shot bank ────────────────────┴─► GENERATOR
                                                               open pass → linking pass (G2)
                                                               │
                                     ┌── corrective prompt ◄───┤ flags (Q/F/C/M)
                                     │   + accumulated hints   │
                                     └──► re-run linking pass  ▼
                                                     VERIFIER (rules, $0) ── Correct / max / no change
                                                               │
                                                               ▼
                                                     PRUNER (P1/P2, $0)
                                       growing ─► node: card for later sections, pairs (anchors first)
                                       pruned  ─► pruned.jsonl (values with an anchor → attribute)
end of chapter: BACKFILL ── new nodes' unrecorded forms in earlier sections → one hint call per section
```

## 17. Review before issue (2026-10-02)

Two independent review passes against both papers found every cited number correct. A second pass then settled the remaining points:
- M2 fires only on the head end of a longer term, so the bank passes its own test;
- F5 accepts aliases;
- the pruner is stated to be out of domain on P&D;
- existing mentions are scored like new concepts;
- backfill has its own mention-check prompt, with checks;
- Q1 cannot block "Correct".

The first pass led to these changes:
- M2 now requires a term-like longer candidate, and every M rule skips rejected items (otherwise "Correct" was unreachable);
- the test run starts from the dev state, so no chapter's nodes are pruned by a model trained on its own gold;
- pruner training uses IIR dev rows only, with no label-defining features and no P&D marks from the re-checked slice;
- Pass A renders every example item as new;
- the examples moved to domains neither book covers, plus a corrective-round example (PiVe App. G);
- C2 gets the mention's type;
- anchor errors drop only the anchor;
- carry-forward against churn;
- backfill restores backward propagation;
- the pruner is described as a deviation from SAC-KG;
- this CR selects on exact F1.
