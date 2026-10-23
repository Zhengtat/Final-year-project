# CR-011 SLEEP-POS-160 - frozen residual challenge set (Research decision 2026-10-09, Option B)

Built label-blind and frozen before any annotation. SLEEP-240 is unchanged and is not pooled with these labels.

- Universe: pairs that are still DIFFERENT canonical nodes in `slice3_c2`; excluded: all 240 SLEEP-240 pairs, CR-008 `different`, type-incompatible pairs (frozen map). Selection reads similarity features and candidate signals only: no SLEEP-240 outcome, owner decision or gold file.
- Sources and quotas (rank-based, no similarity threshold): alias / acronym / `same_concept` queue 12 (pool had 3), high-support bridges 22 (pool 35), evidence similarity 14, definition similarity 18, cross-chapter same-surface / same-head 22, same-type same-sense 22, name similarity 22, lexical similarity 28 (pools of 100 by rank). Drawn per source: {'alias_acronym_queue': 3, 'bridge_high_support': 24, 'evidence_similarity': 15, 'definition_similarity': 19, 'cross_chapter_same_surface': 24, 'same_type_same_sense': 23, 'name_similarity': 23, 'lexical_similarity': 29}; total 160, shortfall 0.
- Split by candidate family (shared node or normalised key): 98 families, largest 7; development 80 / held-out 80; leakage: {'shared_families': 0, 'shared_nodes': 0, 'shared_normalised_keys': 0, 'ok': True}.
- Sheets: `data/interim/checks/cr011/sleep_pos160_dev_blind_sheet.csv` (sha256 `85573743b989c509`), `sleep_pos160_heldout_blind_sheet.csv` (`c275216fd1bcdd6f`), hidden manifest `sleep_pos160_manifest_DO_NOT_SHARE.csv` (`7291b235d9d94493`). Same blind contract and codebook as SLEEP-240; order and A/B randomised.
- Viability rule (Research): after the 80 development items are annotated, gold SAME >= 20 lets STOP 3 proceed; otherwise stop and return to Research before any paid call. Check: `uv run python -m cumap.sleep.stop2 viability --sheet <marked dev sheet>`. No replacement of labelled items.
- Cost: $0.
