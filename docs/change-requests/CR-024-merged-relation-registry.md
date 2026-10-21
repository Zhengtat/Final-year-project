# CR-024 — One merged relation list: registry v1.4 = v1.3 + SciNLP

**Status:** built and tested 2026-10-22 (owner instruction). **Not adopted in production** (`configs/default.yaml` still names `relations_v1.3.yaml`); the owner reviews the definitions I wrote first. Branch `cr-024-merged-relation-registry` from `main`.

## What the owner asked
Combine the SciNLP relation list and the original (networking) list into one new list; where they overlap, merge them.

## Result (`configs/relations_v1.4.yaml`, generated from `configs/registry-patches/CR-024-relations-v1.4.yaml`)
| SciNLP label | v1.4 relation | How |
|---|---|---|
| subclassOf | `is_a` | merged |
| partOf | `part_of` | merged (SciNLP has no `part_type`; that qualifier stays required in production use) |
| UsedFor | `has_purpose` | merged |
| compareWith | `contrasts_with` | merged (both symmetric) |
| trainedWith | `uses` | merged (close fit) |
| subtaskOf | `subtask_of` (new, transitive, classification_structure) | added |
| enhancedBy | `enhanced_by` (new, function_means) | added |
| MeasuredBy / evaluatedBy / evaluatedOn | `measured_by`, `evaluated_by`, `evaluated_on` (new family `evaluation`) | added |
| similarWith | `similar_to` (new, symmetric, comparison; explicitly never a merge or alias, so CR-008 equivalence-as-node-property still holds) | added |

17 v1.3 relations + 6 = 23; nothing removed. A merged relation records the SciNLP label in a new optional field `external_labels` (schema change, backwards compatible).

## Hierarchy set
Derived from the registry: `classification_structure` relations that are transitive = `is_a`, `subtask_of`, i.e. SciNLP labels `{subclassOf, subtaskOf}` (= CR-022's H2). `part_of` stays out (only transitive within a part type, as CR-017).

## Consequences
- The SciNLP -> v1.3 mapping draft of CR-022 is replaced by `external_labels` (the draft file was removed). With one list there is no unmapped label, so CR-022 Part B changes meaning: it would run the relation stage with v1.4 on the same SciNLP pairs and score all 11 labels, instead of the 60% mappable subset. Part B is still not approved.
- Production adoption (default registry -> v1.4) needs the relation prompts re-versioned (their choice sets come from the registry) and a re-run; not done.
- Supersedes the 2026-10-10 Research ruling "SciNLP registry never merged with v1.3" by owner decision.
