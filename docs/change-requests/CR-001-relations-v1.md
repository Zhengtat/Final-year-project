# CR-001 — Relation registry v1, diagnostic edge fields, model defaults

**Status:** approved by owner (Zheng Tat Wong), 2026-09-28
**Applies to:** repo state after M0–M2 are complete and while M3 is in progress
**Rationale:** `docs/research/relation-mapping-research.md` (linguistics → education → LLM evidence)
**New file:** `configs/relations_v1.yaml` (provided; do not hand-edit except as instructed below)

This change request tells the coding agent what to change, in what order, and when to stop for the human. **Read it fully before touching code.** If the existing code already differs from `ARCHITECTURE.md` (because of decisions logged during M0–M2), reconcile with those decisions. Don't overwrite them, and ask if in doubt.

---

## 1. Summary of changes

| # | Change | Why (short) |
|---|---|---|
| A | Registry **v0 → v1**: 14 → **16 relations** in **6 families + pedagogical**. **New relations:** `has_purpose` (function/goal), `performs` (actor → activity). Each relation now carries a `family`, a `template`, `examples`, and `near_misses`. | Purpose was missing from v0 (qualia telic / SBF function). Mechanistic reasoning needs actor → activity. Templates and near-misses let the LLM *choose* rather than invent. |
| B | **New qualifiers** on the core edge fields: `part_type` (required for `part_of`: component / member / phase), `dimension` (recommended for `contrasts_with`), `surface_phrase` (the linking words as written). Plus a derived `relation_family`. | Part-of transitivity fails across types. Comparisons need the dimension that differs. Keeping the original wording preserves partial knowledge (Yin et al. 2005). |
| C | **New reasoning layer: `ChainLink`** (edge → edge) with types cause / purpose / condition / sequence / contrast. | Catches the case where a student knows both facts but links them with the wrong reason. Follows PDTB-3. |
| D | **Match types extended** for family-level partial credit and chain-link errors. | Lets the diagnosis tell the right family / wrong relation apart from a wrong family. |
| E | **Gold migration tooling** for M3 files already written with v0. | `data/gold/` is human-owned. The agent proposes; the human applies. |
| F | **M3 additions:** a relation-set agreement test (κ per relation); gold-editor support for the new fields and chain links. | Checks that humans can apply the relation set consistently; merge relations they can't separate. |
| G | **Plan changes for M5–M7** (implement when you reach them): family-first multiple-choice relation verification with reverse and "none" options; a separate qualifier pass; conformance and hallucination metrics; new ablations. | Evidence: QA4RE, Sainz et al. 2021, GoLLIE, Text2KGBench, reversal curse, negation benchmark. |
| H | **Model defaults:** strong tier `gpt-6-sol` (was `gpt-6-astra`); bulk tier `gpt-6-luna`; `gpt-6-astra` only as an optional *ceiling*. Bulk calls escalate to Sol on low confidence or failed checks. Optional Batch API. A model bake-off before full runs. | Sol ≈ 90% of Astra's task success at ≈ 20% of the cost; cascades cut cost (FrugalGPT). |

---

## 2. Order of work and stop points

Do the steps in order. Commit after each step with the message prefix `CR-001:`.

1. **Registry v1** (§3): add `configs/relations_v1.yaml` (already provided), extend the registry model and logic, and point config at v1. Keep `relations_v0.yaml` loadable.
2. **Schema changes** (§4): core edge qualifiers, `ChainLink`, match types, diagnosis fields. Keep backward-compatible loading of v0 files.
3. **Validator** (§5): `cumap gold validate` becomes version-aware.
4. **Gold migration tool** (§6): dry-run report plus proposed v1 files under `data/interim/suggestions/migrations/v1/`.
   **⛔ STOP 1:** show me the migration report. I'll review it and copy the files into `data/gold/` myself.
5. **M3 tooling updates** (§7): gold editor fields, chain-link editing, relation-agreement sampling and scoring, mismatch report.
   **⛔ STOP 2:** tell me the agreement-test files are ready to annotate.
6. **LLM client: tiers, escalation, batch** (§8), plus config and `.env.example` updates.
7. **Docs** (§9): update `ARCHITECTURE.md`, `BUILD_PLAN.md`, `CLAUDE.md`, `DECISIONS.md`, `PROGRESS.md`.
8. **Acceptance checks** (§10), then report back.

---

## 3. Registry v1

**`RelationType` model gains:**
- `family: str` (must be one of `families[].name`)
- `status: str | None`
- `template: str` (contains `{X}` and `{Y}`)
- `examples: list[str]` (≥ 1)
- `near_misses: list[NearMiss]`, where `NearMiss = {relation, example, why}` (≥ 1)
- `transitive: bool | Literal["within_same_part_type"]`

**`RelationRegistry` also loads:**
- `families`: list of {name, label, diagnostic_prior, grounding}
- `qualifiers`: dict describing allowed and required qualifiers per relation
- `chain_link_types`: list of {name, template, cues}
- `version`, `supersedes`

**New or changed registry functions** (keep the existing ones working):
- `family_of(relation) -> str`
- `same_family(a, b) -> bool`
- `template_for(relation, x, y, reverse=False) -> str`: fills the template. `reverse=True` is only valid for directional relations.
- `choice_set(pair_context, families=None) -> list[Choice]`: builds a multiple-choice option list (used in M5/M6). Contents:
  - filled templates for the relations in the given families;
  - reversed versions for directional relations;
  - `NO_RELATION`;
  - `OTHER`.
- `can_chain(edge_a, edge_b) -> bool`: transitive inference. For `part_of`, only when both edges have the same `part_type`.
- `required_qualifiers(relation) -> set[str]`: e.g. `part_of` → {`part_type`, `polarity`, `modality`}.
- `normalise`, `is_reversal`, `conflicts`, `compatible`, `check_types`: unchanged behaviour, updated for the new relations.

**Config:** `configs/default.yaml` → `relation_registry: configs/relations_v1.yaml`. Add `registry_version_supported: [0, 1]`.

**Tests (new):**
- v1 loads with 16 relations; every relation has a family, template, ≥ 1 example and ≥ 1 near-miss.
- The `conflicts` and `compatible` tables are symmetric.
- `part_of` without `part_type` fails validation.
- `can_chain` for part_of: component + component → true; component + member → false.
- `choice_set` for a directional relation includes the reversed option, `NO_RELATION` and `OTHER`.
- `has_purpose` domain/range check rejects `Event → has_purpose`.
- Compatibility: `causes` ↔ `has_purpose` = partial; `uses` ↔ `performs` = partial.
- v0 still loads (history).

---

## 4. Schema changes

### 4.1 Core edge fields (shared by `ExpertEdge` and `StudentEdge`)
| Field | Type | Rule |
|---|---|---|
| `part_type` | `Literal["component","member","phase"] \| None` | **Required iff** `relation == "part_of"`; must be None otherwise |
| `dimension` | `str \| None` | Allowed only for `contrasts_with` (warn if missing) |
| `surface_phrase` | `str \| None` | Required on `StudentEdge`; required on LLM-extracted `ExpertEdge` (`extracted_by` not None); optional on human-authored expert edges |
| `relation_family` | `str` | Derived from the registry at load or validation time. If present in a file, it must match the registry (error otherwise) |
| `registry_version` | `int` | Stamped on every edge written by code (default 1) |

Keep `chain_id` and `chain_position` on `ExpertEdge`: they still group edges into a chain. The *type* of each link now lives in `ChainLink`.

### 4.2 New model `ChainLink`
```python
class ChainLink(BaseModel):
    link_id: str
    from_edge_id: str            # the supported proposition (A)
    to_edge_id: str              # the supporting proposition (B)
    type: Literal["cause", "purpose", "condition", "sequence", "contrast"]
    statement: str               # e.g. "cwnd is reset to 1 MSS because a timeout signals severe congestion"
    surface_phrase: str | None   # the connective as written ("because", "so that"...)
    evidence: list[Evidence]     # expert: textbook / reference answer; student: answer span
    origin: Literal["textbook", "reference_answer", "manual", "student"]
    question_ids: list[str]      # expert links: questions where this link is expected
    validation: Validation | None
```
- **Expert links** live in `data/gold/expert_pilot/<qid>.yaml` under a new top-level `chain_links:` list (and later in `data/processed/kg/<run_id>/chain_links.jsonl`).
- **Student links** live in the student graph file under `chain_links:`.

### 4.3 Match types (`StudentEdge.alignment.match_type`)
Add or clarify:
- `family_match`: same endpoints and same family, but a different relation that isn't `compatible`. Verdict `inaccurate` (partial credit).
- `part_type_error`: `part_of` with the right endpoints but the wrong `part_type`. Verdict `inaccurate`.
- Existing `partial_relation` = the relations are `compatible: partial`.
- Existing `wrong_type` = a conflicting relation, or a different family with a domain/range violation. Verdict `contradictory`.

New **chain-link alignment** (`ChainLinkAlignment`) — `match_type`:

| match_type | Meaning |
|---|---|
| `exact` | same link type, same edges |
| `wrong_link_type` | same edges, different type, e.g. cause vs purpose |
| `reversed_link` | from/to swapped for cause, purpose or condition |
| `missing_link` | both edges present, link not stated |
| `unsupported_link` | the student links two edges that have no expert link |

Verdict mapping: `wrong_link_type` and `reversed_link` → `contradictory` (a reasoning misconception candidate); `missing_link` → `incomplete`.

### 4.4 `DiagnosisRecord` additions
- `chain_link_results: list[ChainLinkAlignment]`
- `reasoning_errors: list[link_id]`
- `family_coverage: dict[family, float]`: weighted coverage of required edges per family

`label_3way` rules are unchanged: missing never makes an answer contradictory. A `wrong_link_type` or `reversed_link` on a required link **does** count as a contradiction.

### 4.5 LLM-facing schemas
Add flat versions following the Structured Outputs constraints: all fields required, optionals typed `X | None`, no defaults.
- `part_type`, `dimension` and `surface_phrase` appear in the LLM output schemas.
- `relation_family` does **not**: it is derived.
- The relation field is an enum of the 16 names + `"other"`.

---

## 5. Validator (`cumap gold validate`)
- Detect the version from a top-level `registry_version:` key in each gold file. **Missing key = v0.**
- **v1 rules:**
  - required qualifiers present;
  - `part_type` only on `part_of`;
  - the `relation_family` matches the registry;
  - `ChainLink.from_edge_id` / `to_edge_id` exist in the same file (or in the referenced expert file for student links);
  - evidence substring checks as before, including chain-link evidence.
- **v0 files:** validate with v0 rules and print a one-line hint: "run `cumap gold migrate-v1 --dry-run`".
- `--registry v1` forces v1 rules on all files. It is used after the human has migrated.

---

## 6. Gold migration tool (M3 files written with v0)

`cumap gold migrate-v1 [--dry-run]`:
1. Reads every file in `data/gold/` (**read-only**) and writes proposed v1 versions to `data/interim/suggestions/migrations/v1/<same relative path>`.
2. It **never** writes to `data/gold/`. Add a test that asserts this, e.g. by pointing gold at a read-only temp directory.
3. Automatic, safe changes:
   - add `registry_version: 1`;
   - derive `relation_family`;
   - for student edges, pre-fill `surface_phrase` from the text between the endpoints inside `evidence_span`. Mark it `# auto: check`.
4. Suggested changes, **flagged, not applied**:
   - `part_of` edges: suggest a `part_type` from node types (target is Mechanism/State → `phase`; a collection-like target such as "network" or "domain" → `member`; otherwise `component`). Mark `# SUGGESTED: confirm`.
   - `has_property` or `uses` edges whose statement contains purpose cues ("in order to", "so that", "to ensure", "to avoid", "purpose", "used to"): suggest `has_purpose`.
   - `uses` edges whose target is an activity (Mechanism node named with a verb or "-ing"): suggest `performs`.
   - Consecutive edges with the same `chain_id`: suggest `ChainLink`s (type guessed from connectives in the statements or evidence; default `sequence`). Mark `# SUGGESTED`.
5. Report `reports/migration_v1.md`, per file:
   - counts of automatic changes;
   - a table of suggestions (edge_id, current, suggested, reason);
   - files that would fail v1 validation as they are.

**⛔ STOP 1 here.** The human reviews the suggestions, edits, copies them to `data/gold/`, then runs `cumap gold validate --registry v1`.

---

## 7. M3 tooling updates

1. **Gold editor** (`app/gold_editor.py` or the templated YAML):
   - fields for `part_type` (dropdown, shown only for part_of), `dimension` (for contrasts_with) and `surface_phrase`;
   - a relation dropdown grouped by family, showing each relation's definition and near-misses as help text;
   - a **chain-links panel**: pick two edges, a link type and the connective, then save.
2. **Suggest commands** (`suggest-expert`, `suggest-student`): switch prompts to new versions (`v2`) that use the v1 registry. Include the definitions, templates and near-misses in the prompt, output the new qualifiers, and propose chain links. Don't edit old prompt versions.
3. **Relation-set agreement test:**
   - `cumap gold sample-relation-items --n 100 --seed <seed>`:
     - Picks sentences from the pilot questions' textbook sections that mention ≥ 2 pilot-gold concepts.
     - Writes `data/interim/relation_agreement/items.csv` with columns: item_id, section_id, sentence, concept_x, concept_y.
     - Writes two blank annotation sheets, `annotator_A.csv` and `annotator_B.csv`. Annotator columns: relation (16 + `no_relation` + `other`), direction (x→y / y→x / symmetric), part_type, dimension, other_phrase.
     - Stratify so each of the 6 semantic families (not `pedagogical`) appears at least 8 times, using the LLM suggestions only to pick items. Don't pre-fill the answers.
   - 👤 **HUMAN:** two annotators fill in the sheets independently and save them to `data/gold/relation_agreement/`.
   - `cumap eval relation-agreement` → `reports/m3_relation_agreement.md`:
     - Cohen's κ at the **relation** level and at the **family** level, and a direction-agreement rate;
     - per-relation κ, plus a confusion matrix;
     - a list of relation pairs confused in > 20% of the items where either was chosen.
   - **Decision rule (written into the report as a recommendation only):** if a relation's κ < 0.6, or it's confused > 20% with another relation, propose merging, splitting or redefining it (likely candidates: triggers/causes, uses/requires, has_purpose/uses). The human decides; the agent logs the decision in `DECISIONS.md` and creates `relations_v1.1.yaml` if needed.
4. **Mismatch report** (`cumap gold mismatch-report`): also tabulate `family_match`, `part_type_error` and the chain-link match types; report agreement at both family and relation level.

**⛔ STOP 2:** tell me the agreement sheets are ready.

---

## 8. LLM client: tiers, escalation, batch

1. **Tiers in config** (`configs/default.yaml`, with env overrides):
   ```yaml
   llm:
     tiers:
       strong:  {model: ${OPENAI_MODEL_STRONG:-gpt-6-sol},   reasoning_effort: medium}
       bulk:    {model: ${OPENAI_MODEL_BULK:-gpt-6-luna},    reasoning_effort: low}
       ceiling: {model: ${OPENAI_MODEL_CEILING:-gpt-6-astra}, reasoning_effort: low}   # never a default; opt-in only
     escalation:
       enabled: true
       from: bulk
       to: strong
       when: [schema_error, evidence_check_failed, low_confidence]
       confidence_threshold: 0.6
   ```
   Adapt the syntax to however `config.py` already handles env. Note: `gpt-6-astra` doesn't support reasoning effort `none`.
2. **Escalation:** any bulk-tier task whose LLM schema includes a `confidence: float` field is retried once on the strong tier if any `when` condition holds. Log `escalated: true` with the reason. The run manifest reports the escalation rate and the cost split by tier.
3. **Batch API (optional flag `--batch`):** for full-split bulk runs (M4 labelling, M6 extraction). Submit JSONL, poll, then read results back **through the same cache**, so cached results are identical whether produced by batch or live calls. The dry-run cost estimate uses batch prices when `--batch` is set.
4. **Prompt layout for caching:** static content (instructions, registry guideline block, few-shot examples) goes **first**; per-item content goes last.
5. **Model bake-off command** (used before the M5 and M4 full runs): `cumap eval model-bakeoff --tiers bulk,strong,ceiling --task <task> --items <gold subset>`. It runs the same prompt on each tier over a gold subset and reports F1/κ, cost and latency. **Recommendation rule:** the cheapest tier within 0.05 of the best score. The human decides; log it in `DECISIONS.md`.
6. Update `.env.example`: add `OPENAI_MODEL_CEILING=gpt-6-astra` and change `OPENAI_MODEL_STRONG=gpt-6-sol`.

Tests: mock backend returns low confidence → the call escalates exactly once; a schema error escalates; batch and live paths produce identical cache keys.

---

## 9. Documentation updates (apply to the current files; don't replace them wholesale)

**`docs/ARCHITECTURE.md`**
- §2 layers table: add the row `reasoning (edge → edge) | cause, purpose, condition, sequence, contrast | ChainLink; expert from textbook/reference answers, student from connectives`. Add `performs`, `has_purpose` to the semantic row.
- §4a: add the registry fields `family`, `template`, `examples`, `near_misses`, `qualifiers`, `chain_link_types`.
- §4b/§4c: add `part_type`, `dimension`, `surface_phrase`, `relation_family`, `registry_version` to the core fields; add the new match types and the verdict mapping; add §4e **ChainLink** and §4f **ChainLinkAlignment** (copy from §4.2–4.3 above).
- §4d: add `chain_link_results`, `reasoning_errors`, `family_coverage`.
- New §6 "Relation extraction method" (for M5/M6): family-first multiple-choice verification with reversed, `NO_RELATION` and `OTHER` options; a separate qualifier pass; a chain-link pass; an `other`-relation review. This is the same method listed under the BUILD_PLAN M5 bullet below.

**`docs/BUILD_PLAN.md`**
- Add a milestone **"M2.1 — CR-001: registry v1 migration"** between M2 and M3, summarising §2 of this CR with its stop points.
- **M3:** add the relation-agreement test and chain-link annotation; acceptance: agreement report exists and decisions are logged.
- **M5** tasks 4–7 → relation extraction becomes:
  - (a) Stage A candidate pairs + evidence;
  - (b) Stage B **family-first multiple-choice** verification using `choice_set` (filled templates, reversed options, `NO_RELATION`, `OTHER`);
  - (c) a separate **qualifier pass** (polarity, modality, conditions) with a small negation/hedge test fixture;
  - (d) a chain-link pass;
  - (e) an `other`-relation review report each run.

  Add to the M5 evaluation: **ontology conformance rate** (domain/range), **unsupported-by-text rate**, **direction accuracy**, **polarity accuracy**, reported separately.
- **M6:** student extraction outputs `surface_phrase` and chain links from connectives; evaluate chain-link P/R against M3 gold.
- **M7:** add ablations: concept overlap only → + family → + fine relation → + qualifiers → + chain links. Add `family_coverage` and reasoning errors to the results.
- **Timeline:** model bake-off before the M4 and M5 full runs; the cost section uses Sol/Luna and batch prices.

**`CLAUDE.md`**
- OpenAI section: strong = `gpt-6-sol`, bulk = `gpt-6-luna`, ceiling = `gpt-6-astra` (opt-in only); escalation; batch; prompt layout for caching.
- New rule: **"Relations change only through a new registry version (`relations_vX.Y.yaml`) plus a DECISIONS entry. Never add or rename a relation inside code or prompts."**
- New rule: **"Relation classification is always a choice among registry options (including reversed, none and other), never free-text labels."**

**`docs/DECISIONS.md`**: add dated entries:
- registry v1 (with the reasons above);
- ChainLink reasoning layer;
- model tier change to Sol/Luna with Astra as ceiling;
- gold migration approach.

**`docs/PROGRESS.md`**: add a CR-001 row, and log what was verified at the end.

---

## 10. Acceptance checks for CR-001
- `uv run pytest` passes (all old tests and the new ones in §3, §5, §6, §8) with no network access and no API key.
- `uv run ruff check .` is clean.
- `cumap gold validate` passes on fixtures for both v0 and v1. After the human migrates, `cumap gold validate --registry v1` passes on `data/gold/`.
- `reports/migration_v1.md` exists; a test proves the migration never writes into `data/gold/`.
- The relation-agreement sampler produces 100 items covering each of the 6 semantic families ≥ 8 times.
- Dry-run cost estimates show tier names and batch pricing when `--batch` is set.
- The docs are updated as in §9, and `PROGRESS.md` records the numbers verified.
