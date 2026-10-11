# CR-013 STOP 2: trace model

Base commit (Research D3): `2e50b6538ab5a8c97c9df3a218ab70646af90695` (the exact audited `viz-kg-explorer` commit). Branch `cr-013-process-explainability`. Derived trace `slice3_c2/77c22e3d915a` under `data/processed/explainability/` (gitignored). $0, no model call, no prediction change.

## 1. Trace schema (`src/cumap/explain/trace.py`, version 1.0)

`TraceEvent` (pydantic, `extra=forbid`) has the CR 5.1 fields plus three provenance additions: `layer` (RECORDED / REPLAYED / JOINED), `join` (`{method, key}` for deterministic joins, Research D2) and `attrs` (stage-specific recorded values, never inferred).

| field | type | |
|---|---|---|
| `event_id` | `str` | required |
| `run_id` | `str` | required |
| `dataset_mode` | `Literal['pd', 'scinlp', 'other']` | required |
| `document_id` | `str` | required |
| `section_id` | `str | None` | default None |
| `stage` | `Literal['source', 'generator', 'verifier', 'correction', 'pruner', 'canonicalisation', 'pair_generation', 'pair_selection', 'relation_classification', 'validation', 'graph_commit', 'organisation']` | required |
| `object_type` | `Literal['span', 'mention', 'concept', 'pair', 'edge', 'organisation_record']` | required |
| `object_id` | `str` | required |
| `input_refs` | `list[str]` | default PydanticUndefined |
| `output_refs` | `list[str]` | default PydanticUndefined |
| `action` | `str` | required |
| `outcome` | `Literal['accepted', 'corrected', 'rejected', 'merged', 'blocked', 'selected', 'not_selected', 'no_relation', 'emitted', 'not_recorded']` | required |
| `reason_code` | `str | None` | default None |
| `rule_id` | `str | None` | default None |
| `evidence_refs` | `list[str]` | default PydanticUndefined |
| `score` | `float | None` | default None |
| `threshold` | `float | None` | default None |
| `rank` | `int | None` | default None |
| `eligible_count` | `int | None` | default None |
| `budget` | `int | None` | default None |
| `model_id` | `str | None` | default None |
| `prompt_version` | `str | None` | default None |
| `config_hash` | `str | None` | default None |
| `registry_version` | `str | None` | default None |
| `authority` | `Literal['RULE', 'MODEL', 'SCORE', 'HUMAN', 'STRUCTURAL', 'UNKNOWN']` | default 'UNKNOWN' |
| `source_artifact` | `str` | required |
| `source_locator` | `str | None` | default None |
| `layer` | `Literal['RECORDED', 'REPLAYED', 'JOINED']` | default 'RECORDED' |
| `join` | `dict | None` | default None |
| `attrs` | `dict` | default PydanticUndefined |

Stages: source, generator, verifier, correction, pruner, canonicalisation, pair_generation, pair_selection, relation_classification, validation, graph_commit, organisation. Outcomes and authorities as in the CR. Object ids keep the production ids behind a namespace prefix (`concept:`, `v4node:`, `mention:`, `unit:`, `pair:`, `relrow:`, `edge:`).

## 2. Replay layer (Research D1)

The retained run kept only the selected pairs and aggregate stats. The frozen deterministic selection code was re-run (no model call) on the run's own retained concepts, anchors and the section texts. **Reproduction check: VALID** (mismatches: none): the replay reproduces the retained selected pair ids in order, the retained 50-pair unselected sample and the retained selection stats exactly, and a second replay run is byte-identical (`deterministic = True`). Eligible pool 8604 pairs; budget 1,100. Replayed ranks are labelled `REPLAYED` everywhere and rendered as 'not originally recorded'. Rank is the position of the concept pair's best-ranked occurrence by cue score; selection also uses a per-section minimum, an anchor phase and a coverage phase, so rank alone is not a cut-off. The 226 anchor pairs (`AP-` ids) enter selection directly from the anchors, outside the enumerated pool, and carry no rank; 3 `MP-` verification pairs come from the misconception stage, not from pair selection.

Code hashes used by the replay: `pair_selection.py` `6d993959622f`, `relations.py` `11512fab572a`, `slice_rerun.py` `70360db77829`.

## 3. Sample lineages (read from the built trace; text is rendered by the deterministic renderer)

### 3.1 A final node: `concept:c_802_11_wi_fi_standard`

- `concept:c_802_11_wi_fi_standard` (canonical_of_v4_node/JOINED)
  - [canonicalisation · MODEL · RECORDED] “802.11” was linked to this concept (outcome: merged; rule: NOT_RECORDED; similarity: 0.793). Recorded reason: “802.11” is shorthand for the 802.11 Wi-Fi standard; candidate 0 names the same standard..
  - [graph_commit · STRUCTURAL · RECORDED] This concept was committed to the graph; first introduced in chapter 1.
  - [canonicalisation · STRUCTURAL · JOINED] Generator node n_0255 resolves to this concept by an exact name join (key: 802.11 wi-fi standard). This is a deterministic join, not a recorded decision.
  - evidence: `data/processed/kg/slice3_c2/checkpoint.json::concepts[286].mentions[0].quote` -> “the 802.11 Wi-Fi standards”
  - `v4node:n_0255` (proposed_in_unit; supported_by_mention)
    - [pruner · SCORE · RECORDED] The pruner recorded a score of 0.082 for “802.11 Wi-Fi standard” (threshold: NOT_RECORDED); outcome: accepted.
    - [generator · MODEL · RECORDED] The generator proposed “802.11 Wi-Fi standard” as a candidate Protocol; it was not yet a final KG node. Recorded model reason: NOT_RECORDED.
  - `v4node:n_0652` (proposed_in_unit; supported_by_mention)
    - [generator · MODEL · RECORDED] The generator proposed “802.11” as a candidate Protocol; it was not yet a final KG node. Recorded model reason: NOT_RECORDED.
    - [pruner · SCORE · RECORDED] The pruner recorded a score of 0.833 for “802.11” (threshold: NOT_RECORDED); outcome: accepted.
    - `mention:n_0255#0` (mention_in_unit)
      - [generator · MODEL · RECORDED] The phrase “802.11 Wi-Fi standard” was recorded as a mention (role: mentioned) in section 1.3.
      - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0255.mentions[0].evidence` -> “the 802.11 Wi-Fi standards”
    - `unit:1.3#2` (part_of_section/JOINED)
      - [source · STRUCTURAL · RECORDED] This unit of source text (1.3#2) belongs to a textbook section; its text hash is 73ae1406fd524ce1c5ca5263ffb8dbf40a3a98361e2ecbd62398c486a283ef9e.
    - `mention:n_0652#0` (mention_in_unit)
      - [generator · MODEL · RECORDED] The phrase “802.11” was recorded as a mention (role: mentioned) in section 2.6.
      - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0652.mentions[0].evidence` -> “such as 802.11 networks (also known as Wi-Fi)”
    - `mention:n_0652#1` (mention_in_unit)
      - [generator · MODEL · RECORDED] The phrase “802.11” was recorded as a mention (role: used) in section 2.7.
      - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0652.mentions[1].evidence` -> “Wi-Fi (more formally known as 802.11)”
    - `mention:n_0652#2` (mention_in_unit)
      - [generator · MODEL · RECORDED] The phrase “802.11” was recorded as a mention (role: used) in section 2.7.
      - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0652.mentions[2].evidence` -> “802.11 addresses these problems”
    - `mention:n_0652#3` (mention_in_unit)
      - [generator · MODEL · RECORDED] The phrase “802.11” was recorded as a mention (role: mentioned) in section 2.8.
      - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0652.mentions[3].evidence` -> “Like 802.11”
    - `mention:n_0652#4` (mention_in_unit)
      - [generator · RULE · RECORDED] The phrase “802.11” was recorded as a mention (role: mentioned) in section 1.3.
      - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0652.mentions[4].evidence` -> “such as the 802.11 Wi-Fi standards”

### 3.2 A final edge: `edge:RP-1-problem-building-a-network-0`

- `edge:RP-1-problem-building-a-network-0` (committed_from_relation_row/JOINED; endpoint_source; endpoint_target)
  - [graph_commit · STRUCTURAL · RECORDED] This edge was committed to the graph: relation has_purpose, from section 1-problem-building-a-network.
  - [graph_commit · STRUCTURAL · JOINED] The committed edge resolves to its relation-classification row by an exact pair-id join (key: RP-1-problem-building-a-network-0). This is a deterministic join.
  - evidence: `data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[156].evidence_quote` -> “computer network, one that has the potential to grow to global proportions and to support applications”
  - `concept:c_application` (canonical_of_v4_node/JOINED)
    - [generator · RULE · RECORDED] “data” was recorded as a name for this concept (outcome: not_recorded; rule: G-link). Recorded reason: NOT_RECORDED.
    - [graph_commit · STRUCTURAL · RECORDED] This concept was committed to the graph; first introduced in chapter 1.
    - [graph_commit · STRUCTURAL · RECORDED] This concept was committed to the graph; first introduced in chapter 1.
    - evidence: `data/processed/kg/slice3_c2/checkpoint.json::concepts[32].mentions[0].quote` -> “not optimized for a particular application”
  - `concept:c_computer_network` (canonical_of_v4_node/JOINED)
    - [graph_commit · STRUCTURAL · RECORDED] This concept was committed to the graph; first introduced in chapter 1.
    - [organisation · STRUCTURAL · RECORDED] The organisation layer recorded “node_new” in chapter 1 (from NOT_RECORDED to outer). This reorganises the existing graph; it does not decide whether a fact is true.
    - [graph_commit · STRUCTURAL · RECORDED] This concept was committed to the graph; first introduced in chapter 1.
    - evidence: `data/processed/kg/slice3_c2/checkpoint.json::concepts[0].mentions[0].quote` -> “Suppose you want to build a computer network”
  - `relrow:RP-1-problem-building-a-network-0:0` (classification_of_pair)
    - [validation · RULE · RECORDED] Validation outcome: accepted (reason code: NOT_RECORDED); evidence grounding: quote_x=True; quote_y=True; sentence_x=True; sentence_y=True; type errors: NOT_RECORDED.
    - [relation_classification · MODEL · RECORDED] The relation classifier outcome for this pair was emitted (reason code: NOT_RECORDED); model gpt-6-sol, prompt version v4. Recorded decision: relation has_purpose, direction forward, family function_means. Recorded model reason: The sentence describes supporti
    - evidence: `data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[156].pair.sentence` -> “Suppose you want to build a computer network, one that has the potential to grow to global proportions and to support applications as divers”
    - `v4node:n_0033` (proposed_in_unit; supported_by_mention)
      - [pruner · SCORE · RECORDED] The pruner recorded a score of 0.598 for “application” (threshold: NOT_RECORDED); outcome: accepted.
      - [generator · MODEL · RECORDED] The generator proposed “application” as a candidate Concept; it was not yet a final KG node. Recorded model reason: There are no known nodes in this section to relate it to..
    - `v4node:n_0001` (proposed_in_unit; supported_by_mention)
      - [generator · MODEL · RECORDED] The generator proposed “computer network” as a candidate Concept; it was not yet a final KG node. Recorded model reason: No known nodes were provided to relate this concept to..
      - [pruner · SCORE · RECORDED] The pruner recorded a score of 0.224 for “computer network” (threshold: NOT_RECORDED); outcome: accepted.
    - `pair:RP-1-problem-building-a-network-0` (endpoint_x; endpoint_y)
      - [pair_generation · SCORE · REPLAYED] REPLAYED layer (recomputed by the frozen selection code; not originally recorded): this pair was an eligible candidate with cue score 1.000 and co-occurrence count 3.
      - [pair_selection · SCORE · REPLAYED] REPLAYED layer (recomputed by the frozen selection code and verified to reproduce the retained selected set exactly; not originally recorded): this pair ranked 420 out of 8604 eligible pairs by cue score; the run's budget was 1100; outcome: selected.
      - [pair_selection · SCORE · RECORDED] This pair was selected for relation classification (recorded). The run selected 1100 pairs from 8604 eligible pairs; cue score 1.000. Pair origin (from the retained pair id): candidate-pool pair (retained pair id prefix RP-). Rank and selection phase for this 
      - evidence: `data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[156].sentence` -> “Suppose you want to build a computer network, one that has the potential to grow to global proportions and to support applications as divers”
      - `mention:n_0033#0` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “application” was recorded as a mention (role: used) in section 1-problem-building-a-network.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0033.mentions[0].evidence` -> “not optimized for a particular application”
      - `mention:n_0033#1` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “applications” was recorded as a mention (role: used) in section 1.1.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0033.mentions[1].evidence` -> “the applications—a group that has greatly expanded”
      - `mention:n_0033#10` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “applications” was recorded as a mention (role: used) in section 1.1.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0033.mentions[10].evidence` -> “multimedia applications later in the book”
      - `mention:n_0033#11` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “applications” was recorded as a mention (role: used) in section 1.1.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0033.mentions[11].evidence` -> “the diversity of applications that can be built”
      - `mention:n_0033#12` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “application” was recorded as a mention (role: used) in section 1.2.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0033.mentions[12].evidence` -> “new applications are invented”
      - `mention:n_0001#0` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “computer network” was recorded as a mention (role: used) in section 1-problem-building-a-network.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0001.mentions[0].evidence` -> “Suppose you want to build a computer network”
      - `mention:n_0001#1` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “computer network” was recorded as a mention (role: defined) in section 1.2.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0001.mentions[1].evidence` -> “to understand how to build a computer network from the ground up”
      - `mention:n_0001#2` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “computer network” was recorded as a mention (role: used) in section 1.2.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0001.mentions[2].evidence` -> “view a computer network as simply delivering packets”
      - `mention:n_0001#3` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “computer network” was recorded as a mention (role: used) in section 1.3.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0001.mentions[3].evidence` -> “a computer network must provide”
      - `mention:n_0001#4` (mention_in_unit)
        - [generator · MODEL · RECORDED] The phrase “computer networks” was recorded as a mention (role: used) in section 1.4.
        - evidence: `data/processed/kg/slice3_c2/v4_concepts.json::nodes.n_0001.mentions[4].evidence` -> “understanding computer networks”

### 3.3 A pair that was NOT delivered, with its `Why not?` answer

Pair `pair:RP-2.6-44` between `concept:c_network` and `concept:c_repeater`:

- [pair_generation · SCORE · REPLAYED] REPLAYED layer (recomputed by the frozen selection code; not originally recorded): this pair was an eligible candidate with cue score 1.000 and co-occurrence count 2.
- [pair_selection · SCORE · REPLAYED] REPLAYED layer (recomputed by the frozen selection code and verified to reproduce the retained selected set exactly; not originally recorded): this pair ranked 1101 out of 8604 eligible pairs by cue score; the run's budget was 1100; outcome: not_selected.

`Why not?` (production mode):

- concept:c_network is a node of the final graph? -> **yes**
- concept:c_repeater is a node of the final graph? -> **yes**
- identity of the two concepts valid? -> **not_assessed_in_production** - needs a reference; see evaluation mode
- eligible pair generated? -> **yes**
- selected for relation classification? -> **no** ({'rank': 1101, 'eligible_count': 8604, 'budget': 1100, 'rank_layer': 'REPLAYED'})

Earliest observable failure: **P0**. The pair was never sent to relation classification, so the classifier had no opportunity to decide whether a semantic relation exists. The pair ranked 1101 out of 8604 eligible pairs (REPLAYED rank); the run's budget was 1100. Selection also uses a per-section minimum, anchor and coverage phases, so rank alone is not a cut-off.

## 4. Trace coverage (real `slice3_c2` build)

| measure | value |
|---|---|
| final concepts whose lineage reaches resolvable evidence | 1243 / 1243 = 100.0% |
| final edges whose lineage reaches resolvable evidence | 528 / 528 = 100.0% |
| evidence locators that resolve | 10569 / 10569 = 100.0% |
| evidence quotes found in the source section text (informative; whitespace-normalised) | 8207 / 8378 = 98.0% (of the 171 not found, 54 are evidence strings of verifier-rejected candidates (rule F2/F3: not verbatim); 117 are verbatim only in OTHER section(s): the retained section id of that pair differs from the section(s) that contain its cited sentence (recorded as `SECTION_ATTRIBUTION_MISMATCH`, or `_AMBIGUOUS` when several sections contain it, with all section ids; nothing was corrected); 0 remain unexplained) |
| explanation sentences whose every value equals its trace field | 111936 / 111936 values = 100.0% (42511 sentences over 36730 events) |
| unrecorded fields rendered as NOT_RECORDED | 6201/6201 = 100.0% |
| replay determinism (two builds, identical trace hash) | True (`3af9d569c8cc3870…`) |
| events / lineage links / gaps | 36730 / 30982 / 6 |

Stage presence in the lineage of final objects (% of objects; verifier events attach to a generator unit, not to a concept, so they are counted unit-scoped):

| stage | concepts | edges |
|---|---|---|
| canonicalisation | 100.0 | 100.0 |
| correction | 0.0 | 0.0 |
| generator | 100.0 | 100.0 |
| graph_commit | 100.0 | 100.0 |
| organisation | 100.0 | 100.0 |
| pair_generation | 0.0 | 100.0 |
| pair_selection | 0.0 | 99.6 |
| pruner | 100.0 | 100.0 |
| relation_classification | 0.0 | 100.0 |
| source | 100.0 | 100.0 |
| validation | 0.0 | 100.0 |
| verifier | 0.0 | 0.0 |

Unit-scoped verifier presence for concepts (events in a unit the concept's mentions come from): {'verifier': 1243} of 1243.

## 5. Trace gaps (kept explicit; nothing invented)

| scope | stage | field | status | detail |
|---|---|---|---|---|
| run  | canonicalisation | alias_provenance | NOT_RECORDED | alias_provenance and merged_from are empty on every concept (legacy run); the v4-node link is an exact name join |
| run  | generator | input_hash_link | NOT_RECORDED | generator calls are not linked to sections/iterations by input hash in the retained artifacts |
| run  | relation_classification | confidence | NOT_RECORDED | no confidence or score is stored with relation decisions; rejected alternatives are only in the prompt text |
| run  | canonicalisation | blocked_merges | NOT_RECORDED | no retained record of blocked merges (lexicon DIFFERENT veto) in this run |
| object relrow:MP-3 | graph_commit | edge_commit | INCONSISTENT | relation row 1150 is a misconception-verification edge (retained pair id prefix MP-, created outside pair selection) with outcome 'edge', but no snapshot edge has id MP-3; the reason it was not committed is not recorded |
| object relrow:RP-1.2-260:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 1.2; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[359].pair.sentence) |
| object relrow:RP-1.2-431:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 1.2; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[373].pair.sentence) |
| object pair:RP-1.2-260 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 1.2; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[359].sentence) |
| object pair:RP-1.2-431 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 1.2; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[373].sentence) |
| object relrow:RP-1.2-72:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 1.2; the cited sentence is verbatim only in section 1.5 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[215].pair.sentence) |
| object relrow:RP-1.2-398:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 1.2; the cited sentence is verbatim only in section 1.5 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[371].pair.sentence) |
| object pair:RP-1.2-72 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 1.2; the cited sentence is verbatim only in section 1.5 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[215].sentence) |
| object pair:RP-1.2-398 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 1.2; the cited sentence is verbatim only in section 1.5 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[371].sentence) |
| object relrow:RP-2-perspective-race-to-the-edge-54:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2-perspective-race-to-the-edge; the cited sentence is verbatim only in section 2.8 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[445].pair.sentence) |
| object pair:RP-2-perspective-race-to-the-edge-54 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2-perspective-race-to-the-edge; the cited sentence is verbatim only in section 2.8 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[445].sentence) |
| object relrow:RP-2.2-11:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.2; the cited sentence is verbatim only in section 2-problem-connecting-to-a-network (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[169].pair.sentence) |
| object pair:RP-2.2-11 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.2; the cited sentence is verbatim only in section 2-problem-connecting-to-a-network (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[169].sentence) |
| object relrow:RP-2.3-296:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.3; the cited sentence is verbatim only in section 2.2 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[484].pair.sentence) |
| object pair:RP-2.3-296 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.3; the cited sentence is verbatim only in section 2.2 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[484].sentence) |
| object relrow:RP-2.3-153:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.3; the cited sentence is verbatim only in section 2.6 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[478].pair.sentence) |
| object pair:RP-2.3-153 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.3; the cited sentence is verbatim only in section 2.6 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[478].sentence) |
| object relrow:RP-2.5-142:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.5; the cited sentence is verbatim only in section 2-problem-connecting-to-a-network (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[510].pair.sentence) |
| object pair:RP-2.5-142 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.5; the cited sentence is verbatim only in section 2-problem-connecting-to-a-network (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[510].sentence) |
| object relrow:RP-2.5-464:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.5; the cited sentence is verbatim only in section 2.4 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[1055].pair.sentence) |
| object pair:RP-2.5-464 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.5; the cited sentence is verbatim only in section 2.4 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[1055].sentence) |
| object relrow:RP-2.6-30:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.6; the cited sentence is verbatim only in section 2.1 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[254].pair.sentence) |
| object pair:RP-2.6-30 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.6; the cited sentence is verbatim only in section 2.1 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[254].sentence) |
| object relrow:RP-2.7-420:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.7; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[565].pair.sentence) |
| object pair:RP-2.7-420 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.7; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[565].sentence) |
| object relrow:RP-2.7-553:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.7; the cited sentence is verbatim only in section 2.1 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[570].pair.sentence) |
| object pair:RP-2.7-553 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.7; the cited sentence is verbatim only in section 2.1 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[570].sentence) |
| object relrow:RP-2.7-20:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.7; the cited sentence is verbatim only in section 2.6 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[178].pair.sentence) |
| object pair:RP-2.7-20 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.7; the cited sentence is verbatim only in section 2.6 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[178].sentence) |
| object relrow:RP-2.7-99:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_AMBIGUOUS | retained section 2.7; the cited sentence is verbatim only in section 3.1, 3.4, 4.4 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[267].pair.sentence) |
| object pair:RP-2.7-99 | pair_selection | section_attribution | SECTION_ATTRIBUTION_AMBIGUOUS | retained section 2.7; the cited sentence is verbatim only in section 3.1, 3.4, 4.4 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[267].sentence) |
| object relrow:RP-2.8-148:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.8; the cited sentence is verbatim only in section 1-perspective-feature-velocity (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[580].pair.sentence) |
| object pair:RP-2.8-148 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.8; the cited sentence is verbatim only in section 1-perspective-feature-velocity (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[580].sentence) |
| object relrow:RP-2.8-267:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.8; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[587].pair.sentence) |
| object pair:RP-2.8-267 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.8; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[587].sentence) |
| object relrow:RP-2.8-295:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.8; the cited sentence is verbatim only in section 2.2 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[590].pair.sentence) |
| object pair:RP-2.8-295 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 2.8; the cited sentence is verbatim only in section 2.2 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[590].sentence) |
| object relrow:RP-3-perspective-virtual-networks-all-the-way-down-55:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3-perspective-virtual-networks-all-the-way-down; the cited sentence is verbatim only in section 3.2 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[608].pair.sentence) |
| object pair:RP-3-perspective-virtual-networks-all-the-way-down-55 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3-perspective-virtual-networks-all-the-way-down; the cited sentence is verbatim only in section 3.2 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[608].sentence) |
| object relrow:RP-3.1-142:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.1; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[285].pair.sentence) |
| object pair:RP-3.1-142 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.1; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[285].sentence) |
| object relrow:RP-3.1-200:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.1; the cited sentence is verbatim only in section 2.4 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[624].pair.sentence) |
| object pair:RP-3.1-200 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.1; the cited sentence is verbatim only in section 2.4 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[624].sentence) |
| object relrow:RP-3.1-16:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.1; the cited sentence is verbatim only in section 3-problem-not-all-networks-are-directly-connected (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[74].pair.sentence) |
| object pair:RP-3.1-16 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.1; the cited sentence is verbatim only in section 3-problem-not-all-networks-are-directly-connected (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[74].sentence) |
| object relrow:RP-3.3-12:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[32].pair.sentence) |
| object relrow:RP-3.3-31:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[78].pair.sentence) |
| object pair:RP-3.3-12 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[32].sentence) |
| object pair:RP-3.3-31 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.2 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[78].sentence) |
| object relrow:RP-3.3-134:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[192].pair.sentence) |
| object relrow:RP-3.3-233:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[290].pair.sentence) |
| object relrow:RP-3.3-237:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[291].pair.sentence) |
| object relrow:RP-3.3-29:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[77].pair.sentence) |
| object pair:RP-3.3-134 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[192].sentence) |
| object pair:RP-3.3-233 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[290].sentence) |
| object pair:RP-3.3-237 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[291].sentence) |
| object pair:RP-3.3-29 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.3 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[77].sentence) |
| object relrow:RP-3.3-320:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.4 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[295].pair.sentence) |
| object pair:RP-3.3-320 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 1.4 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[295].sentence) |
| object relrow:RP-3.3-204:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 2.6 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[194].pair.sentence) |
| object relrow:RP-3.3-560:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 2.6 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[698].pair.sentence) |
| object pair:RP-3.3-204 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 2.6 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[194].sentence) |
| object pair:RP-3.3-560 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 2.6 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[698].sentence) |
| object relrow:RP-3.3-948:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 3-perspective-virtual-networks-all-the-way-down (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[717].pair.sentence) |
| object pair:RP-3.3-948 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 3-perspective-virtual-networks-all-the-way-down (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[717].sentence) |
| object relrow:RP-3.3-225:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 3-problem-not-all-networks-are-directly-connected (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[289].pair.sentence) |
| object pair:RP-3.3-225 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 3-problem-not-all-networks-are-directly-connected (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[289].sentence) |
| object relrow:RP-3.3-394:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 3.4 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[300].pair.sentence) |
| object pair:RP-3.3-394 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.3; the cited sentence is verbatim only in section 3.4 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[300].sentence) |
| object relrow:RP-3.4-266:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.4; the cited sentence is verbatim only in section 1.1 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[720].pair.sentence) |
| object pair:RP-3.4-266 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.4; the cited sentence is verbatim only in section 1.1 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[720].sentence) |
| object relrow:RP-3.4-603:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.4; the cited sentence is verbatim only in section 2.3 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[744].pair.sentence) |
| object pair:RP-3.4-603 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.4; the cited sentence is verbatim only in section 2.3 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[744].sentence) |
| object relrow:RP-3.4-496:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.4; the cited sentence is verbatim only in section 3.1 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[739].pair.sentence) |
| object pair:RP-3.4-496 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.4; the cited sentence is verbatim only in section 3.1 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[739].sentence) |
| object relrow:RP-3.5-440:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.5; the cited sentence is verbatim only in section 1-perspective-feature-velocity (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[766].pair.sentence) |
| object pair:RP-3.5-440 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.5; the cited sentence is verbatim only in section 1-perspective-feature-velocity (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[766].sentence) |
| object relrow:RP-3.5-477:0 | relation_classification | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.5; the cited sentence is verbatim only in section 3.1 (data/processed/kg/slice3_c2/checkpoint.json::relation_results_v3[768].pair.sentence) |
| object pair:RP-3.5-477 | pair_selection | section_attribution | SECTION_ATTRIBUTION_MISMATCH | retained section 3.5; the cited sentence is verbatim only in section 3.1 (data/processed/kg/slice3_c2/checkpoint.json::selected_pairs[768].sentence) |
| run  | pruner | threshold | NOT_RECORDED | the pruner threshold is not stored in the artifact (run recipe: pruner off, tau 0) |

## 6. Tests

`tests/test_cr013_trace.py`: **33 passed in 0.18s**. Covered: hash identity before/after a build; TraceEvent round trip; deterministic ids and `extra=forbid`; lineage reaches evidence for a node and an edge; many-mentions-to-one-concept and many-evidence-to-one-edge DAG fan-in; joins carry method and key; renderer determinism and support verification (and a tampered sentence is detected); `NOT_RECORDED` rendering; rank above/below the boundary; recorded taxonomy guard stays separate; relation explanation from stored fields only; `Why not?` localises N0 / P0 (not eligible and not selected) / R0 / R3 / E0 and an existing edge; no `should exist` claim; unknown replay -> `unknown`; the frozen evaluation attribution localises N0, N1, C0, C1, P0, R0, R1, R2, R3, E0 and a recovered edge; production modules import no gold or evaluation code; coverage and gap honesty; build-twice identity; and the real `slice3_c2` build meets the integrity criteria.

## 7. Source hash-integrity proof

`source_hashes_unchanged = True`: the SHA-256 of every source artifact was taken before the build and again after writing all outputs, and the two maps are identical.

| source artifact | sha256 (before = after) |
|---|---|
| `data/interim/textbook_sections.jsonl` | `665029b32e45ffc4fd0e150b1d13de719562a3657f7004efb22a94356a7d14f3` |
| `data/logs/llm_calls.jsonl` | `02f97b6b64386d6d6bf0e674b3cc0a999f974edfd8af0a7a587620271681a87e` |
| `data/processed/kg/slice3_c2/checkpoint.json` | `54eb0f194ca0271da08d38500b781c17eefa6af79638e85e865bdcfedaafde99` |
| `data/processed/kg/slice3_c2/misconceptions.jsonl` | `b472c55b143d05b49d66f6ad2c62327dc985138770217a6da34d8c4958aed18f` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch1/communities.jsonl` | `33f3aeba5452c3f70f82ec28c328a18bfc7d03fb48c71279cb2b3165454da355` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch1/events.jsonl` | `6717d1d4556d9cefe3730ddb84142d155e2cb9bbb5e148a3b71a914fde6db7ac` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch1/org_nodes.jsonl` | `bd10773eb7472f410734405515c2ba29ce5aed464b78ddd1a06f6c7297901c37` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch2/communities.jsonl` | `fd8f9539dfebbcf1a4522ba9c6a30674095973269fc8b5945697cc9df265b37a` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch2/events.jsonl` | `e59a5c361031656e29a0ba0c0b799b219a710a2b3f31def8060cfbeddaf10dc7` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch2/org_nodes.jsonl` | `63fdcdc6388c29b0e41b8b00fb4faec2ee7e6037c877d61393f676b762ad8661` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch3/communities.jsonl` | `35379fa73e424afae12e6a056280d1e4aa852f4136ae0235dc64a0e77cc1627f` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch3/events.jsonl` | `ff52e22d07ca264e79977965b1e2e0471006e7d67919348d386f5bbbf6c4401f` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/ch3/org_nodes.jsonl` | `38a5c945d85bf84376da7bbfbd970be9e6e808c79b260a18b48782238496861d` |
| `data/processed/kg/slice3_c2/organisation/org_b6ebb5bc/manifest.json` | `0a649fd2e5cb19997681f93d1bce137cc1a5eca326d7b9479fef788bbb01db02` |
| `data/processed/kg/slice3_c2/snapshots/ch1/edges.jsonl` | `cf3258abc1828272ab08e50047d72254ac2da05c282263c3318a01b5fb57aaeb` |
| `data/processed/kg/slice3_c2/snapshots/ch1/manifest.json` | `9cd592288a8eba7af157df38acd6a0eebd33fb72c57d41531f0ee561a665b59f` |
| `data/processed/kg/slice3_c2/snapshots/ch1/merges.jsonl` | `49dcc50ba869116001efb03a956fb57d6dc7907b3565d3afb1af4734059ff6f0` |
| `data/processed/kg/slice3_c2/snapshots/ch1/nodes.jsonl` | `3ece4ff08706e95ac0efa613443faa46ed779452930f06029d421979e74df1e4` |
| `data/processed/kg/slice3_c2/snapshots/ch1/rejected.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `data/processed/kg/slice3_c2/snapshots/ch2/edges.jsonl` | `9a6006d7076a0d0f2cacc9171271c3175d5e95b53e7a5b14a701f03de3cd050e` |
| `data/processed/kg/slice3_c2/snapshots/ch2/manifest.json` | `03c37567b5cf7f6a5dae10e40cd69d6a3d27d120a378ed1b716f11b7fa4ba2f4` |
| `data/processed/kg/slice3_c2/snapshots/ch2/merges.jsonl` | `1bb24bd1b690334f83c299df1a529a15b20324d82ba87aa5cd56ccb0cedcd0fc` |
| `data/processed/kg/slice3_c2/snapshots/ch2/nodes.jsonl` | `f462655bfaf5fef0d9b0855030150343565b8a873ca1b7b19dd832464c71b5c8` |
| `data/processed/kg/slice3_c2/snapshots/ch2/rejected.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `data/processed/kg/slice3_c2/snapshots/ch3/edges.jsonl` | `09936c9da878f7cb0a757e5bd8ebee73d4247ad20827f144a872832e8423a086` |
| `data/processed/kg/slice3_c2/snapshots/ch3/manifest.json` | `d243bf5e2a748390430b590be150f989fe264aa2efe6b5bec7319c36dbe2c693` |
| `data/processed/kg/slice3_c2/snapshots/ch3/merges.jsonl` | `27f6f1d1a0091062696c387be8a811e8b5d992d21e96695da7dc112ae9c574f8` |
| `data/processed/kg/slice3_c2/snapshots/ch3/nodes.jsonl` | `0ee9fdd423a8ab1cddaecdabc7ba1f5c122f8b82764f85e337dc0159841fc929` |
| `data/processed/kg/slice3_c2/snapshots/ch3/rejected.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `data/processed/kg/slice3_c2/v4_concepts.json` | `dd8f74b0d6974c661e209eddc48489ecc01e787e06a56a8fdd1d8805c6264c86` |

## 8. Secondary trace: retained SciNLP held-out E0 run (`cr012_scinlp_heldout_P17_1058_grobid_E0`)

Built with the same adapter and no replay (the sections differ; replay not enabled). Events 656, links 703, gaps 8. Final objects are taken from the checkpoint (no snapshots exist): concepts 68 with 100.0% lineage to evidence, edges 15 with 100.0%; locators resolve 100.0%. Source hashes unchanged: True. The derived SciNLP trace contains SciNLP text (CC BY-NC) and stays local and gitignored.

## 9. Applied Research decisions

- D1: replay is a labelled REPLAYED layer that reproduces the retained selected set exactly (valid here); an invalid replay would emit no ranks.
- D2: only exact, run-scoped, deterministic joins (exact name or alias, unique; `#` suffix strip; equal pair id, unique; anchor key, unique); ambiguous or unresolved joins become `AMBIGUOUS_JOIN` / `UNRESOLVED` gaps (see section 5).
- D3: branch base `2e50b6538ab5a8c97c9df3a218ab70646af90695`; `viz-kg-explorer` was not merged into `main`.

## 10. Findings this build surfaced

- Anchor (`AP-`) pairs and misconception verification (`MP-`) pairs are not ranked pool pairs; their origin is shown from the retained pair id and the retained anchor / relation records.
- One `MP-` edge row has outcome `edge` but no committed snapshot edge (trace gap with its id); 2 other `MP-` edges are committed.
- No data from the evaluation side (gold, scorer, attribution) is read by any production module; the frozen CR-012 attribution is reachable only from `why_not_eval.py`.
