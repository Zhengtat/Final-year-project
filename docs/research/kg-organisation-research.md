# Organising the Knowledge Graph — from learning theory to LLM pipelines (H420020)

Compiled 2026-09-28. Question: *how should the expert KG (and the student graphs laid over it) be organised so that it mirrors how people build and structure knowledge, and so that it diagnoses understanding well?*

Order: (1) education theory → (2) technology that tried to replicate it → (3) LLM pipelines that can build it → (4) recommendation for this project.

---

## 0. Key takeaways

1. **Learning theory agrees that knowledge is layered by abstraction.** Big ideas/principles sit above core concepts, which sit above details. Learners assimilate new material under what they already know (Ausubel). Experts organise knowledge around core concepts and deep principles; novices organise it around surface features and isolated facts (Chi, Feltovich & Glaser 1981; *How People Learn*, 2000). **Our KG has no principle tier yet.** Adding one is the biggest structural gap.
2. **Knowledge also differs in kind:** factual, conceptual, procedural (revised Bloom's knowledge dimension; KLI knowledge components). Errors differ by kind (a wrong value vs a wrong causal link vs steps in the wrong order), so nodes should carry a `knowledge_type`.
3. **Understanding shows in how connected an answer is, not only in which facts are right.** SOLO (Biggs & Collis) grades answers from one relevant idea, to several unconnected ideas, to an integrated structure, to generalising beyond the question. Novice programmers often get stuck at the "several unconnected ideas" level (Lister et al. 2006). **A SOLO-style structural level can be computed from our student graphs** and gives a second, explainable diagnostic output.
4. **Misconceptions are structured, not random:** fragments of intuitive knowledge (diSessa), synthetic models (Vosniadou), wrong-category assignments (Chi). Technology has long modelled them as **perturbations of the expert model** (the BUGGY "bug library"), which matches our `match_type` design.
5. **The classic technical pattern is an *overlay*:** the student model is a marked-up copy of the expert model. Knowledge-space theory, knowledge tracing and learning maps (Dynamic Learning Maps: ~2,000+ nodes per subject with precursor → target → successor levels) all add **prerequisite/progression structure** and ways to **validate it against student data**.
6. **LLM pipelines now implement these ideas directly:**
   - hierarchical summarisation trees (RAPTOR) and community hierarchies (GraphRAG) give an abstraction tier;
   - hippocampus-inspired KG memory (HippoRAG) gives "pattern completion" from partial cues via Personalized PageRank, useful for linking vague student wording to the right region of the KG;
   - evolving linked notes (A-Mem) mirror assimilation and accommodation;
   - LLM-built concept graphs improve cognitive diagnosis (HCGCDM, *Engineering* 2026), and LLM knowledge tracing uses global + student-specific KGs (2T-KT, *Information Fusion* 2026).

---

## 1. Education theory: how people learn and organise knowledge

### 1.1 Assimilation under existing knowledge (hierarchy by abstraction)
- **Meaningful learning** (Ausubel 1968; as used by Novak & Cañas 2008):
  - new knowledge is anchored ("subsumed") under more general concepts the learner already holds;
  - **progressive differentiation:** general ideas are refined into finer ones;
  - **integrative reconciliation:** links are made across branches.

  *KG implication:* organise nodes in abstraction tiers (general → specific) and value **cross-links** between branches as evidence of integrated understanding.
- **Expertise** (*How People Learn*, Bransford, Brown & Cocking 2000, ch. 2). Experts:
  - notice meaningful patterns;
  - have knowledge "organized in ways that reflect a deep understanding of their subject matter" (around core concepts / big ideas);
  - hold knowledge that is **"conditionalized"** (it records when it applies);
  - retrieve it fluently.

  **Chi, Feltovich & Glaser (1981)**: experts sorted physics problems by underlying principles; novices by surface features.

  *KG implication:*
  - a **principle / big-idea tier**;
  - **conditions** on edges (we already have the `conditions` qualifier);
  - diagnosing depth = checking whether an answer connects details to principles.
- **Knowledge organisation** (Ambrose et al. 2010, *How Learning Works*, ch. 2; companion to the ch. 1 already reviewed): novices' knowledge is sparse and loosely connected; experts' is dense and organised around meaningful features. Concept-map structure types (**spoke / chain / net**; Kinchin, Hay & Adams 2000) describe this.

### 1.2 Kinds of knowledge
- **Revised Bloom's taxonomy** (Anderson & Krathwohl 2001), knowledge dimension: **factual** (terms, specific details), **conceptual** (classifications, principles, models), **procedural** (algorithms, methods, when to use them), **metacognitive**.
- **KLI framework** (Koedinger, Corbett & Perfetti 2012, *Cognitive Science*): learning is described through *knowledge components*, with different learning processes: memory & fluency; induction & refinement; understanding & sense-making. Different kinds of component need different instruction and feedback.
- *KG implication:* add `knowledge_type ∈ {factual, conceptual, procedural}` to nodes and edges. Networking examples:
  - factual: "127.0.0.0/8 is reserved for loopback";
  - conceptual: "congestion arises when demand exceeds capacity";
  - procedural: "slow start → congestion avoidance on reaching ssthresh".

  Errors then point to different feedback: memorise, explain, or walk through the procedure.

### 1.3 How understanding grows: quality of structure
- **SOLO taxonomy** (Biggs & Collis 1982). Five levels:
  - *prestructural:* no relevant idea;
  - *unistructural:* one relevant aspect;
  - *multistructural:* several relevant aspects, not related to each other;
  - *relational:* the aspects are integrated into a coherent whole;
  - *extended abstract:* generalises to principles beyond the question.
- In CS: novice programmers often stay multistructural when explaining code (Lister et al. 2006, "Not seeing the forest for the trees", ITiCSE).
- *KG implication:* SOLO levels can be read straight off the student graph once expected concepts, relations, chain links and a principle tier exist (§4.3).
- **Knowledge integration** (Linn & Eylon 2011): learners hold a *repertoire of ideas*. Learning means eliciting, adding, **distinguishing** and **sorting out** ideas, not replacing them.
  - *KG implication:* the diagnosis should say which of the student's ideas to *distinguish*. This is the confusable-pair (`contrasts_with`) machinery.
- **Learning progressions** (e.g. Corcoran, Mosher & Rogat 2009, CPRE): ordered, increasingly sophisticated ways of thinking about a big idea. **Threshold concepts** (Meyer & Land 2003; in CS, Boustedt et al. 2007, SIGCSE) are transformative, integrative and often troublesome concepts that unlock a subject.
  - *KG implication:* flag threshold concepts (candidates in networking: layering/abstraction, end-to-end argument, statistical multiplexing, feedback-based congestion control). Weight them high in diagnosis.

### 1.4 How misconceptions are structured (already in the review; relevant again here)
- **Knowledge in pieces** (diSessa 1993): novice knowledge is a loosely connected set of intuitive fragments ("p-prims"), activated by context. Expertise *reorganises* them rather than replacing them.
- **Synthetic models** (Vosniadou 1994) and **wrong ontological category** (Chi 2005).
- *KG implication:* model a misconception as a **small alternative subgraph attached to the expert region it distorts**, not a single wrong edge. Expect the same fragment to recur across questions.

---

## 2. Technology that tried to replicate this

| Approach | Core idea | What to borrow |
|---|---|---|
| **Semantic networks** (Collins & Quillian 1969; Collins & Loftus 1975) | Concepts as nodes in an is-a hierarchy with inherited properties; spreading activation | Inheritance of properties down `is_a`; activation spreading from a student's mentioned concepts to find the relevant region |
| **Overlay student model** (Carr & Goldstein 1977; widely used in adaptive systems) | The student model is a marked-up copy of the expert model (known / unknown per element) | Each student graph = overlay states on expert edges: expressed / missing / contradicted / unseen |
| **Bug libraries / perturbation models** (Brown & Burton 1978, BUGGY) | Errors come from systematic "bugs", i.e. perturbations of correct procedures | Misconception layer = catalogued perturbations of expert subgraphs; `match_type` = perturbation type |
| **Knowledge Space Theory** (Doignon & Falmagne 1985; used in ALEKS) | A learner's state is a feasible subset of items, constrained by prerequisite ("surmise") relations | Consistency check: an answer that expresses an advanced edge but misses its prerequisites is an **upstream gap** or a **memorised fragment** |
| **Knowledge tracing:** BKT (Corbett & Anderson 1995), DKT (Piech et al. 2015), graph-based KT (Nakagawa, Iwasawa & Matsuo 2019) | Estimate mastery per knowledge component over time; GKT uses the concept graph to share evidence between neighbours | Future learner model (needs student IDs; SAF lacks them). The GKT idea of spreading evidence to neighbouring concepts carries over to the overlay |
| **Learning maps** (Dynamic Learning Maps: ELA 2,089 nodes / 5,045 connections; maths 2,399 / 5,200; linkage levels *initial precursor → distal → proximal precursor → target → successor*) | A fine-grained graph of the steps towards each target skill, used for diagnostic assessment | **Mini-maps per question:** each question's expected subgraph with its precursors and successors |
| **Empirical validation of map structure** (Thompson & Nash 2022, *Frontiers in Education*) | Diagnostic classification models test whether student data support the hypothesised ordering (~4% mastery reversals in their case) | Validate our prerequisite/progression layer with SAF labels: count "reversals" (advanced edge expressed, precursor missing) |
| **Educational KG builders** (KnowEdu, Chen et al. 2018, *IEEE Access*; ACE, Aytekin & Saygın 2024, *JEDM*) | Concepts + prerequisite relations from teaching data; ACE ranks pairs by AI scores and experts label only the best candidates, with graph inference cutting expert effort | Human-in-the-loop by prioritised review (already in CR-002/003) |

---

## 3. LLM pipelines that can build this organisation

| Pipeline | Mechanism | Maps to theory | Use in H420020 |
|---|---|---|---|
| **GraphRAG** (Edge et al. 2024, Microsoft) | LLM extracts an entity graph → community detection (Leiden) → hierarchical **community summaries** | Progressive differentiation / big ideas | Detect topic modules in the P&D KG; the LLM summarises each; the summaries seed the **principle tier** |
| **RAPTOR** (Sarthi et al., ICLR 2024) | Recursively embed, cluster and summarise text into a **tree** (details → summaries), then retrieve at any level | Subsumption hierarchy | Build section → chapter → book summaries; propose principles; link concepts upward |
| **HippoRAG** (Gutiérrez, Shu, Gu, Yasunaga & Su, NeurIPS 2024) | LLM = "neocortex", KG = "hippocampal index", **Personalized PageRank** = pattern completion from partial cues; up to 20% better multi-hop QA, 10–20× cheaper than iterative retrieval | Spreading activation / associative recall | From the concepts a student mentions, run PPR over the KG to find **what region they're talking about**. Improves linking vague student wording and choosing expected edges |
| **A-Mem** (Xu et al., NeurIPS 2025) | Zettelkasten-style notes with keywords, tags and links; new notes **update older notes** ("memory evolution") | Assimilation + accommodation | When later chapters add information, revise earlier concept descriptions and links (fits the chapter-by-chapter build) |
| **Generative agents** (Park et al., UIST 2023) | Memory stream + periodic **reflection** that synthesises higher-level insights from observations | Abstraction from experience | Reflection-style prompts to derive principles from many edges |
| **Zep / Graphiti** (Rasmussen et al. 2025; already listed) | Episodic → semantic → community subgraphs; edges carry validity periods | Memory consolidation | Versioned, time-stamped edges (already adopted as "deprecate, don't delete") |
| **HCGCDM** (Sheng et al., *Engineering* 2026) | LLM builds a heterogeneous concept graph (**prerequisite, parallel, synergistic** relations) for cognitive diagnosis. Removing the LLM-built graph hurt diagnosis most; GPT-4o gave better relations than Llama-3-8B | LLM-built structure improves diagnosis | Direct evidence that LLM-built concept structure helps diagnosis. Cite for motivation |
| **2T-KT** (Li, Wang, Jose & Ge, *Information Fusion* 2026) | LLM knowledge tracing with **global subject KG + student-specific KGs**, a "teacher thinking" prompt, verified graph completion | Overlay + learner model | Blueprint for the (stretch) learner model: global expert KG + per-student overlay graph |

---

## 4. Recommendation: how to organise the H420020 KG

### 4.1 One set of concept nodes, organised along five axes
| Axis | What it encodes | Grounding | Status |
|---|---|---|---|
| **A. Abstraction tier** | `principle` (big ideas, ~8–12 for networking) → `core` concept → `detail` | Ausubel; How People Learn; Chi et al. 1981; RAPTOR/GraphRAG | **New** |
| **B. Knowledge type** | `factual` / `conceptual` / `procedural` on nodes (and derived for edges) | Anderson & Krathwohl; KLI | **New** |
| **C. Relation layers** | taxonomy, semantic (6 families), prerequisite, reasoning chain links, misconception | Relation research + CR-001 | Exists |
| **D. Progression** | prerequisite_of + per-question mini-maps (precursor → target → successor) | Learning progressions; DLM; KST | Partly exists (prerequisite layer) |
| **E. Curriculum / structure** | book → chapter → section; `introduced_in` | Piriyapongpipat; structure layer | Exists |

**Principle tier (A), concretely:**
- Candidate big ideas for networking come from P&D's own framing (its Foundation chapter sets out requirements and design principles), community summaries and RAPTOR-style chapter summaries. Examples:
  - layering & abstraction
  - statistical multiplexing / resource sharing
  - reliable delivery over unreliable channels
  - scalability through hierarchy & aggregation
  - feedback-based control (flow/congestion)
  - the end-to-end argument
  - naming / addressing / forwarding separation
- A human approves ~8–12. That's a small, cheap human step.
- New relation proposal for **registry v1.1**: `instantiates` (core concept/mechanism → principle), family `classification_structure`, with a template ("{X} is an instance of the principle {Y}"). Per the CR-001 rule, relation changes go through a registry version + DECISIONS entry.
- Flag **threshold concepts** (`is_threshold: bool`) on the principles and core concepts that act as gateways.

### 4.2 Misconceptions as perturbation subgraphs
- A `Misconception` = a small alternative subgraph (1–4 edges) plus the expert region it perturbs, a perturbation type (substitution, reversal, over-generalisation, wrong category, missing condition) and evidence answers.
- Mined from SAF feedback (M8) and seeded from literature where it exists.
- Recurring fragments across questions are flagged as possible intuitive "pieces".

### 4.3 Diagnostic outputs organised by the same theory
For each answer, in addition to correct / incomplete / contradictory:

| Output | How it's computed from the graphs |
|---|---|
| **SOLO-style structural level** | *prestructural:* no expected concept matched. *Unistructural:* 1 required edge matched. *Multistructural:* ≥ 2 required edges matched but no chain links or connecting relations among them. *Relational:* matched edges are connected (chain links / shared-node paths) covering the question's core. *Extended abstract:* relational **plus** a correct `instantiates` link to a principle, or a valid extra edge outside the question's subgraph |
| **Knowledge-type profile** | Share of missing/contradicted edges by `knowledge_type`, which points to the feedback strategy (memorise / explain / walk through the procedure) |
| **Integration score** | Number of distinct KG communities (or principle branches) the answer connects correctly (cross-links, following Novak, Linn) |
| **Progression check** | Advanced edges expressed while their precursors are missing (KST/DLM "reversal"): flag *upstream gap* or *memorised fragment* |
| **Class overlay heatmap** (demo) | Across all answers to a question: how often each expert edge is expressed / missing / contradicted (overlay model at class level; SAF has no student IDs) |

**Evaluation hooks:**
- SOLO level vs SAF score: the correlation should be positive and monotonic.
- A small blind human SOLO coding of ~60 answers for agreement (κ).
- The progression-reversal rate as an empirical test of the prerequisite layer (Thompson & Nash 2022 approach).

### 4.4 LLM pipeline to build the organisation (fits M5–M7)
1. **Base KG** (M5, as planned).
2. **Communities + summaries:** Leiden on the semantic layer; LLM summary per community (GraphRAG-style).
3. **Principle proposals:** RAPTOR-style recursive summaries (section → chapter → book) + community summaries + the Foundation chapter → the LLM proposes 12–15 principles with evidence → 👤 the human approves ~8–12.
4. **`instantiates` links:** for each core concept, family-first multiple choice over the approved principles (+ "none"), with evidence required.
5. **Knowledge type:** LLM choice among factual / conceptual / procedural per node, with a node_type prior (e.g. Mechanism → procedural, Property/Parameter → factual). Check a small blind sample.
6. **Tier assignment:** principle (approved) → core (has an `instantiates` edge or high centrality in its community) → detail (the rest), then sanity-check it against the scorer's importance.
7. **Memory evolution:** when a later chapter adds an edge to an earlier concept, re-generate that concept's description and community summary (A-Mem style); record the version.
8. **Student side:** Personalized PageRank from the student's linked concepts to rank the expected region and candidate links (HippoRAG-style); overlay states; SOLO level; heatmap.

### 4.5 Priorities for an FYP-sized scope
1. **Principle tier + `instantiates` + SOLO-style level:** the biggest gain in explanatory power, and cheap.
2. **Knowledge type on nodes:** cheap; enriches feedback and analysis.
3. **Progression-reversal check:** reuses SAF labels; gives empirical validation of the prerequisite layer.
4. **Class overlay heatmap:** a strong demo feature.
5. *Stretch:* PPR linking, memory evolution, perturbation-subgraph misconceptions, learner model (needs data with student IDs).

---

## 5. How big ideas are determined, and how an LLM pipeline can mimic it (added 2026-09-28)

### 5.1 What counts as a big idea
- A big idea is a **generalisation stated as a full sentence**, not a topic label. Harlen's big ideas and Wiggins & McTighe's "enduring understandings" are both written as declarative statements.
- It explains many specific phenomena, sits at the heart of the discipline, transfers to new situations, and usually has to be "uncovered" because it's abstract or often misunderstood.
- Example: *"Senders must infer congestion from indirect feedback and adapt their rate, because no single node sees the whole network"*, not the label "congestion control".

### 5.2 How education researchers determine them (usually several methods combined)
| Method | How it works | Example |
|---|---|---|
| **Criteria-based expert panels** | Experts screen candidates against explicit criteria | Harlen (2010): 10 international experts, 4 criteria (explanatory power over many phenomena; basis for decisions; satisfaction from answering questions; cultural significance) → 14 big ideas. NRC Framework (2012): a core idea should meet ≥ 2 (preferably 3–4) of: broad importance / key organising concept; key tool for more complex ideas; relevance to students; teachable over years at increasing depth. Wiggins & McTighe's UbD "filters": enduring value beyond the classroom, heart of the discipline, requires uncoverage, potential to engage |
| **Delphi studies** | Anonymous expert rounds rating items; group results fed back; repeat until consensus | Goldman et al. (2008, SIGCSE): Delphi rating of **importance and difficulty** of concepts in introductory computing, used to scope concept inventories |
| **Disciplinary / document analysis** | Mine standards and foundational texts for the organising principles | CS2023 Networking & Communication knowledge area (layering and encapsulation, the hourglass model, circuit vs packet switching, queueing and congestion, reliability support, routing and forwarding); IAB RFC 1958 *Architectural Principles of the Internet* (end-to-end argument, connectivity as the goal, heterogeneity, simplicity, scalability, minimal state / fate-sharing, modularity); Denning's *Great Principles of Computing*; P&D's own Foundation chapter (requirements + architecture) |
| **Expert–novice studies** | See which principles experts use to organise problems | Chi, Feltovich & Glaser (1981): experts sort by principles, which reveals the organising ideas |
| **Student-difficulty evidence** | Interviews, concept inventories and difficulty ratings show which ideas are troublesome gateways | Threshold concepts (Meyer & Land 2003; Boustedt et al. 2007, via interviews): transformative, integrative, troublesome. This decides which big ideas need most attention, not what the big ideas are |

Typical sequence: candidates from documents → screening against criteria by a panel → Delphi rounds → checking with teachers and students.

### 5.3 LLM pipeline that mimics this (with human touchpoints)
1. **Candidates from documents** (mimics disciplinary analysis):
   - the LLM reads P&D's Foundation chapter, the RAPTOR chapter summaries, the KG community summaries, the CS2023 NC knowledge area and RFC 1958;
   - it proposes 20–30 candidate big ideas as **full sentences, each with citations**;
   - duplicates are merged.
2. **Explanatory power measured on the KG** (mimics "explains many phenomena / heart of the discipline"). This is the part an LLM alone can't do reliably:
   - the LLM links concepts to candidates with `instantiates` (a multiple-choice question, including "none", with evidence required);
   - then compute, per candidate: the number of concepts instantiating it, the chapters and topic communities it spans, and the share of SAF questions whose expected subgraph touches it.
3. **Simulated criteria panel, Delphi-style** (mimics expert panels):
   - 3–5 LLM "panellists" (different models or tiers plus perspectives: networking researcher, instructor, curriculum designer, student) rate each candidate on the NRC criteria plus UbD's "requires uncoverage", with rationales;
   - round 2 shows the anonymised median and reasons, and panellists may revise.
   - **Caveat:** in a medical Delphi simulation, eight LLMs reached *higher* consensus than 43 human experts (93.3% vs 81.5%) with 78.5% concordance, and followed guidelines more closely where humans drew on experience. So an LLM panel can produce **false consensus**. Use it only to pre-screen, and diversify the models.
4. **Troublesomeness from student data** (mimics difficulty and threshold evidence): rates of missing or contradicted SAF edges under each candidate → threshold-concept flags. This comes from data, not the LLM.
5. **Granularity and overlap checks:** reject candidates that are too broad ("networks move data") or too narrow (a single mechanism); merge candidates whose instantiating concepts overlap heavily (Jaccard).
6. **Human Delphi on the shortlist:** you + your supervisor (+ a networking lecturer if possible) run two quick rounds on ~12–15 candidates → final 8–12. Report agreement.
7. **External validity check:** report **recall** (the share of RFC 1958 / CS2023 core principles represented) and **precision** (the share of chosen ideas traceable to an authoritative source or clearly supported by the KG).

**Combined score for ranking candidates:**
- KG explanatory breadth;
- panel median on the criteria;
- source authority (the number of independent sources).

Troublesomeness is used only to flag threshold concepts.

**What a principle node stores:** its statement, source citations, scores on each criterion (panel and human), KG breadth metrics, the threshold flag, and the approval record.

### 5.4 Illustrative networking candidates (to be validated, not final)
- Layering lets each protocol rely on the service below it through an interface, so layers can change independently (CS2023 layering/encapsulation; P&D Foundation).
- Packet switching lets many flows share links statistically, trading guaranteed capacity for efficiency, which creates queueing delay and loss (CS2023 switching and queueing).
- Reliable delivery is built end-to-end on top of unreliable links using sequence numbers, acknowledgements and retransmission (CS2023 reliability support).
- Senders must infer congestion from indirect feedback and adapt their rate, because no single node sees the whole network (P&D congestion chapter).
- Functions that need end-point knowledge belong at the end points, keeping the network simple (RFC 1958 end-to-end).
- Hierarchy and aggregation in addressing and routing are what let the network scale (RFC 1958 scalability).
