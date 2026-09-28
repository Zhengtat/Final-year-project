# Relation Mapping Research — how to represent relationships between concepts (H420020)

Compiled 2026-09-28. Purpose: decide **which relationships the expert KG and student graphs should encode, and how an LLM can reliably map text into a small, fixed set of relations**. Builds on `architecture-and-build-plan.md` §4 and `configs/relations_v0.yaml`.

---

## 0. Key takeaways

1. **No field agrees on one "correct" relation inventory.** Linguistics has "lumpers" (a few general relations) and "splitters" (long lists). Reviews conclude the set must be chosen for the application (Khoo & Na 2006). So the project needs a justified, *application-specific* set, tested by whether humans can apply it consistently.
2. **Across linguistics and education, the same few families keep reappearing:** classification (is-a), composition (part-of), attributes, function/purpose, cause and effect, process and sequence, conditions, and comparison. A set of ~15 relations grouped into ~6 families covers them.
3. **Education research says the relations that reveal *depth* of understanding are behavioural, functional and causal, not taxonomic.** Novices describe structures; experts connect structures to behaviours and functions (Hmelo-Silver & Pfeffer 2004). Strong explanations chain mechanisms and causes (McLure 2023; Russ et al. 2008). Diagnosis should weight these relations most.
4. **A fixed relation set has a known cost.** In concept-map assessment, making students choose from a fixed list of linking phrases raised scoring reliability (0.92 vs 0.81) and allowed automatic scoring. It also hid partial knowledge: 15% vs 41% of propositions got partial credit, and students could not express some relations (Yin et al. 2005). Fix: **let students write freely, map what they wrote onto the fixed set, keep their original wording, and allow "partial" match types.**
5. **LLMs are much better at choosing between well-defined options than at inventing relation labels.** Four findings support this:
   - Turning relation extraction into multiple-choice questions over plain-language relation templates closes most of the gap to fine-tuned models (QA4RE, 2023).
   - Relation templates + entailment work zero-shot, and each template takes under 15 minutes to write (Sainz et al. 2021).
   - Detailed annotation guidelines drive zero-shot extraction quality (GoLLIE, ICLR 2024).
   - The main error source is deciding when *no* relation holds.
6. **Known LLM weak spots map directly onto our edge fields:**
   - **direction:** the "reversal curse";
   - **negation:** LLMs handle affirmative sentences well but negated ones poorly;
   - **vague or hallucinated links:** recurring failures in LLM-generated concept maps.
   Direction and polarity need their own checks, not a single extraction pass.
7. **Keep the relation set small and put the nuance in qualifiers** (polarity, modality, conditions, part type, comparison dimension). This is the "hyper-relational" pattern (Wikidata-style qualifiers; StarE, EMNLP 2020). It gives expressiveness without an ever-growing relation list.
8. **Add two relation types and one new layer to v0:**
   - **`has_purpose`**: the function/purpose relation (Pustejovsky's "telic" role; SBF "function"). It is central for designed systems like protocols and was missing.
   - **`performs`**: actor → activity (mechanistic reasoning: entities *and* activities).
   - A **proposition-to-proposition "reasoning" layer** (cause / purpose / condition / sequence / contrast, following PDTB) that links edges into explanation chains.

---

## 1. Linguistics: how relations between concepts are classified

### 1.1 Two kinds of relation (Khoo & Na 2006)
- **Paradigmatic** (lexical-semantic): hold between concepts in general, are stated by generic, always-true sentences, and form a fairly *closed*, enumerable class. Examples: is-a, part-whole, synonymy, antonymy. This is what an **expert KG** stores.
- **Syntagmatic**: arise from how words combine in particular sentences (case roles, discourse links). They form an *open* class. This is what a **student answer** contains.
- **Implication:** the core technical job is mapping open, sentence-level student statements onto a closed set of generic relations. That's why canonicalisation, and keeping the student's original wording, matter.
- Thesaurus standards group everything into three super-families: **equivalence, hierarchical, associative**. Ontologies are richer (UMLS has 54 relations under IS-A and associated-with).

### 1.2 Lexical-semantic relations
- **WordNet** (Miller 1995; Fellbaum 1998) organises nouns mainly by **hyponymy (is-a)** and **meronymy (part-of)**, plus synonymy and antonymy.
- **Chaffin & Herrmann (1984)** found people group relations into five families: **contrast, similars, class inclusion, case relations, part-whole**.
- **Winston, Chaffin & Herrmann (1987)** identify six **part-whole** types:
  - component–integral object
  - member–collection
  - portion–mass
  - stuff–object
  - feature–activity
  - place–area

  They are distinguished by whether the parts are functional, homeomerous (like the whole) and separable. **Key point: transitivity fails when different part-whole types are mixed.**
  - *Implication:* `part_of` needs a `part_type` qualifier, and transitive inference should only chain within one type. Networking examples:
    - component: extension header → IPv6 packet
    - member: host → collision domain
    - feature–activity / phase: slow start → TCP congestion control
- **Qualia structure** (Pustejovsky 1991, Generative Lexicon) describes a concept's meaning through four roles:
  - **formal:** what kind of thing it is (≈ is-a, properties);
  - **constitutive:** what it's made of (≈ part-of);
  - **telic:** what it's *for* (purpose/function);
  - **agentive:** how it comes about.

  *Implication:* our v0 registry had formal and constitutive relations but **no telic (purpose) relation**. For engineered artifacts like protocols, purpose is essential ("frame bursting exists to…").

### 1.3 Roles inside events and sentences
- **Case/thematic roles** (Fillmore; FrameNet; PropBank → **AMR**, the representation MitiGaTe used) include agent, instrument, patient, etc. They describe one event's internal structure and are open-class: PropBank has thousands of verb frames.
  - *Implication:* too fine-grained and open to use as the KG relation set. At most, use them as an intermediate step on the student side. What we borrow: **actor → activity** (`performs`) and **instrument** (`uses`).

### 1.4 Relations between statements (discourse)
- **Rhetorical Structure Theory** (Mann & Thompson 1988) and the **Penn Discourse Treebank 3.0** (Webber, Prasad et al. 2019) classify how *statements* relate. PDTB-3's four top classes:
  - **Temporal:** synchronous, asynchronous
  - **Contingency:** cause, purpose, condition, negative-condition
  - **Comparison:** contrast, concession, similarity
  - **Expansion:** conjunction, instantiation, level-of-detail, equivalence, …

  Its level-3 labels encode *only direction*.
  - *Implication:* explanations are built from **links between propositions** ("A happens *because* B", "X is done *in order to* Y", "*if* C then D"). Many misconceptions sit in these links, not in single facts. This supports a **second, small relation layer between edges**, turning `chain_id` into typed links (cause / purpose / condition / sequence / contrast). PDTB's two-level hierarchy (4 classes → ~17 senses) is also a model for a **coarse-to-fine** label space.

### 1.5 Computational relation inventories
- **SemEval-2010 Task 8** (Hendrickx et al.): 9 relations + Other:
  - Cause–Effect
  - Instrument–Agency
  - Product–Producer
  - Content–Container
  - Entity–Origin
  - Entity–Destination
  - Component–Whole
  - Member–Collection
  - Message–Topic
- **ConceptNet 5.5** (Speer et al., AAAI 2017): a closed set of about three dozen relations, e.g. IsA, PartOf, **UsedFor**, CapableOf, Causes, HasPrerequisite, HasProperty, DistinctFrom, Antonym.
- *Implication:* general-purpose sets converge on cause, use/purpose, part-whole, is-a, property and contrast. Spatial/container/origin relations matter little for networking concepts.

---

## 2. Education: how learning research maps relations between concepts

### 2.1 Concept maps and propositions
- In a concept map, the unit of meaning is a **proposition**: concept – *linking phrase* – concept (Novak & Cañas 2008). Links between distant parts of the map ("cross-links") signal integrated understanding.
- **Linking phrases are where understanding shows, and where automatic scoring struggles.**
  - Vague phrases like "has" can mean different relations ("person has arm" = part; "person has children" = kinship), so propositions need a typed relation before they can be scored automatically (da Costa Jr, da Rocha & Favero 2004).
  - Specific linking phrases ("cristae *part of* mitochondria") indicate deeper understanding than generic ones (Javonillo & Martin-Dunlop 2019, who provide 105+ phrases for introductory biology covering quantitative, structural and temporal relations).
- **Fixed vs free linking phrases** (Yin, Vanides, Ruiz-Primo, Ayala & Shavelson 2005, JRST):
  - **Selected** (fixed list) phrases gave higher inter-rater reliability (0.92 vs 0.81) and allowed computer scoring.
  - Created (free) phrases captured more partial knowledge (40.9% vs 15.1% of propositions got mid-range scores) and more complex, network-like maps (55.1% vs 26.7%).
  - Students could not express some relations with the fixed list. Scoring used 0 = wrong, 1 = partially incorrect, 2 = correct but thin, 3 = scientifically correct.
  - **→ Design rule for this project:** the *student* writes freely and the *system* maps into the fixed set. Keep the student's surface phrase on every student edge, and score partial matches (our `partial_relation`, `modality_error`, etc.) instead of forcing right/wrong.
- **Knowledge maps with fixed link types** (Dansereau and colleagues; Lambiotte et al. 1989; Chmielewski & Dansereau 1998) teach learners a small labelled set: **Characteristic (C), Type (T), Part, Leads-to (L), Influences (I), Example (Ex)**, among others. A small typed set is usable by learners, not just machines.
- **SemNet** (Fisher; Faletti & Fisher 1996): the ability to generate and use relations effectively distinguishes good from poor biology students. Designing relations and using them consistently is itself hard, which argues for testing inter-annotator agreement on the relation set.

### 2.2 Which relations signal deeper understanding
- **Structure–Behaviour–Function (SBF)** (Hmelo-Silver & Pfeffer 2004, Cognitive Science; Goel, Rugaber & Vattam 2009, AI EDAM):
  - Novices focus on "perceptually available, static components" (structures).
  - Experts integrate structures with **behaviours** (how it works) and **functions** (what it's for).
  - Networking protocols are designed systems, so SBF fits directly:
    - **structure** = `is_a`, `part_of`, `has_property`
    - **behaviour** = `performs`, `triggers`, `precedes`, `causes`, `increases`/`decreases`
    - **function** = `has_purpose`, `uses`
- **Mechanistic reasoning** (Russ, Scherr, Hammer & Mikeska 2008, from Machamer, Darden & Craver 2000):
  - Good explanations identify **entities**, their properties and organisation, and the **activities** that change them.
  - They **chain** forward or backward through the mechanism.
  - This needs actor → activity (`performs`) and activity → effect (`causes`/`increases`/`triggers`) relations, plus chain links.
- **Causal explanation quality** (McLure 2023, already reviewed): higher levels link observations, unseen mechanisms and theory in causal chains. This supports weighting causal/mechanistic edges and chain completeness in diagnosis.
- **Qualitative reasoning** (Forbus 1984, Qualitative Process Theory; Bredeweg & Forbus 2003, AI Magazine, on use in education): "how quantities affect each other" is expressed as influences and **qualitative proportionalities** (↑/↓). This justifies `increases`/`decreases`.
  - Networking is full of such trade-offs: a bigger window gives higher throughput; frame bursting raises efficiency but delays other stations.
  - **Advantages and disadvantages can be expressed as ↑/↓ on quality attributes** (throughput, delay, overhead, efficiency), so no separate "advantage" relation is needed.
- **Category mistakes** (Chi 2005, JLS): robust misconceptions arise when a process is assigned to the wrong *kind* (e.g. treating an emergent process as a direct one).
  - This needs node types plus `is_a`, so "wrong category" can be detected.
  - Hypothesis to test in networking: treating congestion as a single sender's property rather than an emergent effect of many flows.
- **Expectations and misconceptions as propositions** (AutoTutor; Nye, Graesser & Hu 2014, IJAIED): tutors compare student answers with lists of expected propositions and known misconception propositions. This mirrors our reference propositions + misconception layer.

---

## 3. LLMs: modelling relations within a fixed set

### 3.1 What the evidence says
| Finding | Source | Implication |
|---|---|---|
| Plain prompted LLMs still underperform small fine-tuned models on relation extraction, partly because it is rare in instruction-tuning data. Reframing it as **multiple-choice QA over plain-language relation templates** outperforms strong zero-shot baselines. | Zhang, Gutiérrez & Su, Findings of ACL 2023 (QA4RE) | Classify relations by *choosing* among options, not free generation. |
| Writing each relation as a **plain-language template** and solving by entailment gives 63% F1 zero-shot and 69% with 16 examples per relation on TACRED. Templates take under 15 minutes per relation. **Main error: detecting "no relation".** | Sainz et al., EMNLP 2021 | Each registry entry gets a template. Always include a "none of these" option, and calibrate it. |
| **Detailed annotation guidelines** (definitions, positive/negative cases) are key to zero-shot extraction on unseen label sets. | Sainz et al., ICLR 2024 (GoLLIE) | The registry is the guideline: definition + examples + near-miss negatives. |
| **Extract openly → define → canonicalise** onto the schema, retrieving only the relevant schema parts, scales to large schemas. | Zhang & Soh, EMNLP 2024 (EDC) | Allow an `other` relation with the free-text phrase; review and cluster these periodically to evolve the registry. |
| Evaluate generated graphs for **ontology conformance** (domain/range) and **hallucination**, not just precision/recall. | Mihindukulasooriya et al., ISWC 2023 (Text2KGBench) | Add conformance and unsupported-by-text rates to M5/M6 reports. |
| Few-shot GPT-3 came near the best results, but **exact-match scoring undercounts** correct generative outputs; human evaluation was needed. | Wadhwa, Amir & Wallace, ACL 2023 | Use lenient matching plus human checks for relation evaluation. |
| LLMs trained on "A is B" often fail on "B is A" (**reversal curse**). | Berglund et al., ICLR 2024 | Verify **direction** explicitly (offer "reverse" as a choice). |
| LLMs classify affirmative sentences well but **struggle with negation**, relying on surface cues. | García-Ferrero et al., EMNLP 2023 | Extract and verify **polarity** in a focused step; test on negated items. |
| LLM-generated concept maps show **hallucinated nodes, vague linking phrases, missing cross-links**. Human-in-the-loop and knowledge-base grounding help. | Zhai 2025, systematic review of 28 studies | Evidence quotes, schema grounding and human review are needed, as planned. |
| **Hyper-relational** facts (main triple + qualifiers) improve modelling over plain triples. | Galkin et al., EMNLP 2020 (StarE) | Keep relations few; put context in qualifiers (polarity, modality, conditions, part_type, dimension). |
| Relation patterns (symmetry, antisymmetry, inversion, composition) can be modelled explicitly in embedding space; inside LLMs many relations decode as approximately **linear maps**. | Sun et al., ICLR 2019 (RotatE); Hernandez et al., ICLR 2024 | Background for learned representations: registry properties (symmetric/inverse/transitive) have direct counterparts in embedding models. |

### 3.2 A recipe for a fixed relation set with an LLM
1. **Two-level label space** (coarse → fine, like PDTB): pick the family first (6 options), then the relation (2–4 options within the family). If unsure, back off to the family label; it still earns partial credit.
2. **Registry entry = guideline:** definition, plain-language template ("X is done in order to achieve Y"), 2 positive examples, 2 near-miss negatives (e.g. `triggers` vs `causes`), allowed source/target types, properties.
3. **Generate candidates, then verify by multiple choice:**
   - Stage A proposes candidate concept pairs with an evidence quote.
   - Stage B asks a QA4RE-style question whose options are the templates filled with X and Y, **the same templates reversed (Y, X)**, and **"no relation / not stated"**.
   - Direction and "none" are checked in the same step.
4. **Separate qualifier pass:** polarity (negation cues), modality (always / can / never), conditions, stance. This targets the known negation weakness. Test it on a small set of negated and hedged sentences.
5. **Escape valve:** `other` + free-text phrase. Cluster the "other" cases each run and decide whether to add a relation (a new registry version) or map them to an existing one.
6. **Always store the surface phrase** (textbook or student wording) next to the canonical relation.
7. **Enforce the set syntactically** with Structured Outputs (relation as an enum). Enforce it *semantically* with the definitions, domain/range checks and evidence checks.
8. **Validate the relation set itself:** two annotators label relations for ~100 textbook sentences → Cohen's κ per relation. Merge any pair humans can't separate reliably (likely candidates: `triggers`/`causes`, `uses`/`requires`, `has_purpose`/`uses`).

---

## 4. What relations to focus on (recommendation for v1)

### 4.1 What SAF questions demand
| SAF question type (examples) | Relation families needed |
|---|---|
| Define or explain a concept (IPv6 extension headers, DQDB, piggybacking) | classification, structure, **function**, properties |
| Compare two things (sync vs async transmission; binary vs Manchester encoding) | **comparison** + the properties that differ |
| Advantages / disadvantages (frame bursting) | **function** + **quantitative effects (↑/↓ on quality attributes)** |
| Procedures / phases (TCP congestion-control phases, transparent bridge operation, reverse-path forwarding) | **mechanism/process**: performs, triggers, precedes, part_of[phase] |
| Requirements / constraints (CSMA/CD collision-domain diameter; spanning trees) | **dependency** + conditions + quantitative effects |
| Facts / values (reserved Class A addresses) | properties |

### 4.2 Proposed v1 inventory: 6 families, 16 relations (2 new)
| Family (priority for diagnosis) | Relations | Grounding |
|---|---|---|
| **1. Mechanism & process (behaviour)** | **`performs`** (NEW: actor → activity), `triggers` (event → action; conditions), `precedes` (step order) | SBF behaviour; mechanistic reasoning; PDTB Temporal |
| **2. Cause & quantitative effect** | `causes`, `prevents`, `increases`, `decreases` | PDTB Contingency.Cause; SemEval Cause–Effect; ConceptNet Causes; Qualitative Process Theory |
| **3. Function & means** | **`has_purpose`** (NEW: artifact/mechanism → goal), `uses` | Qualia telic; SBF function; ConceptNet UsedFor; SemEval Instrument |
| **4. Dependency & constraint** | `requires` (+ conditions) | PDTB Condition; ConceptNet HasPrerequisite (semantic sense) |
| **5. Classification & structure** | `is_a`, `part_of` (+ `part_type`: component / member / phase), `has_property` | WordNet; Winston et al. 1987; qualia formal/constitutive; SBF structure; Dansereau Type/Part/Characteristic |
| **6. Comparison** | `contrasts_with` (+ `dimension` qualifier naming what differs), `equivalent_to` | Chaffin & Herrmann contrast; PDTB Comparison; ConceptNet DistinctFrom |
| *Pedagogical layer (separate)* | `prerequisite_of` | PREAP; prerequisite literature |

**New or changed qualifiers**
- `part_type` on `part_of`; transitivity only within the same type.
- `dimension` on `contrasts_with`, e.g. "clocking", "growth rate".
- `surface_phrase` on every edge (expert and student).
- `relation_family`, so a correct family with the wrong fine relation can get partial credit.

**New reasoning layer (edge → edge)**
- `chain_links: [{from_edge, to_edge, type: cause | purpose | condition | sequence | contrast}]`, following PDTB top classes.
- This lets the diagnosis say *"the student knows A and B, but links them with the wrong reason"*, a key misconception pattern the concept-level graph can't express.

**Deliberately left out:** spatial/location, origin/agentive, generic "related_to" (too vague), fine-grained PropBank roles, instance-level facts.

### 4.3 Priority for diagnosis weighting (initial, to be learned in M7)
1. Mechanism/process and cause/effect edges, plus chain links (depth of understanding).
2. Function and dependency edges.
3. Comparison edges (the main source of confusable-pair misconceptions).
4. Classification and structure edges: needed as scaffolding; category errors are rarer but serious (Chi).

---

## 5. Next steps (fit into the build plan)
- **M2:** update the registry to v1 (add `has_purpose` and `performs`, the new qualifiers, templates, near-miss negatives, families); add `chain_links` to the schema.
- **M2/M3:** run the relation-set agreement test (~100 sentences, 2 annotators, κ per relation); merge or split relations accordingly; log in DECISIONS.
- **M5/M6:** implement candidate → multiple-choice verification with reverse and "none" options; a separate qualifier pass; report conformance, hallucination, direction accuracy and polarity accuracy separately.
- **M7:** ablation "concept overlap only" vs "+relation family" vs "+fine relation" vs "+qualifiers" vs "+chain links", to show which level of relation detail drives diagnosis.
