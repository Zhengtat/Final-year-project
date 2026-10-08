# CR-011 Migration and Rollback Specification

## Principle

A sleep merge is a **transaction**, not an in-place destructive edit.

The source run/snapshot is immutable. Every accepted consolidation writes into a new `sleep_id` namespace and records enough forward and inverse state to reconstruct the pre-sleep graph exactly under stable canonical serialization.

## Transaction order

```text
PRE-SLEEP SNAPSHOT
    ↓
generate merge_plan.jsonl
    ↓
validate CR-008 SAME/DIFFERENT + type/contradiction guards
    ↓
apply one MergeTransaction
    ↓
re-key edges
    ↓
union aliases/evidence/history
    ↓
deduplicate identical edges with evidence union
    ↓
record merge-created self-loops/rejections
    ↓
run structural validators
    ↓
run rollback simulation
    ↓
commit transaction
```

## Minimum `MergeTransaction`

```yaml
merge_id: str
sleep_id: str

source_node_ids: [str]
survivor_node_id: str

decision:
  origin: R0 | R1 | R2 | R3 | ML | LLM | HUMAN
  merge_probability: float | null
  model_version: str | null
  prompt_version: str | null
  config_version: str

support:
  evidence_ids: [str]
  section_ids: [str]
  rule_ids: [str]

before:
  node_hashes: {}
  edge_ids: []
  alias_records: []
  description_records: []

operations:
  alias_additions: []
  edge_rekeys: []
  edge_deduplications: []
  self_loop_rejections: []
  node_tombstones: []

inverse_operations: []

validation:
  lexicon_guards_passed: bool
  cluster_consistency_passed: bool
  evidence_retention_passed: bool
  rollback_test_passed: bool
```

## Evidence retention

For every pre-sleep evidence record:

```text
old evidence_id
    → post-sleep edge_id + preserved evidence_id
OR
    → explicit rejection record
```

There is no permitted "not found" outcome.

When two edges become identical after re-keying, keep one canonical edge and the **union of all evidence references and qualifiers that remain semantically valid**. Record the old edge IDs in the rewrite/deduplication map.

Aliases remain provenance objects with rule/source/evidence, never flattened to strings.

## Raw identities

Absorbed source nodes remain in the lineage store. A canonical view may expose one survivor ID, but raw extraction identity and current canonical identity remain distinguishable.

## Rollback acceptance test

Starting from S:

1. apply sleep → S′;
2. apply the generated inverse patch → S″;
3. canonicalise serialization order;
4. exclude only explicitly volatile fields such as timestamps;
5. compare content hashes.

Required recovery: 100% for node IDs, edge IDs or explicit mappings, aliases, evidence, description histories, validation state, relation qualifiers and provenance.

Any mismatch blocks commit of that sleep transaction/version.

## Namespace

Use the repository's actual run layout if equivalent. Otherwise the research-approved shape is:

```text
data/processed/kg/<run_id>/
    snapshots/
    sleep/
        <sleep_id>/
            manifest.json
            candidate_pairs.jsonl
            pair_features.parquet
            pair_scores.jsonl
            merge_plan.jsonl
            merge_transactions.jsonl
            id_map.jsonl
            edge_rewrites.jsonl
            rejected_merges.jsonl
            suspected_splits.jsonl
            review_sheet.csv
            metrics.json
            rollback/
                inverse_patch.jsonl
                roundtrip_report.json
```

Do not mutate the original run directory.

## CR-006 replay

After a successful canonical sleep version is produced, replay CR-006 organisation on that version and report the diff. CR-006 organisation is downstream only and must not be used as evidence that two nodes are equivalent.
