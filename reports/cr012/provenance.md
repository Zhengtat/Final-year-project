# CR-012 provenance completeness

Every graph element is traceable to a located source quote under the frozen workflow (evidence-or-it-doesn't-enter-the-graph).

- P&D E0: provenance completeness 0.976 over 790 nodes and 174 edges (edges with located quote: 174 / 174).
- SciNLP E0: see `unsupported_facts.md` (completeness 1.000).
- Run provenance: every model run is recorded in `reports/cr012/stop4_log.jsonl` (run id, level, tag, seconds, cumulative spend); prompt text per call is in `data/logs/llm_prompts.jsonl` (rule 16); configuration and code hashes in `frozen_hashes.json` (STOP-3 freeze plus the STOP-4 execution addendum); gold provenance in `heldout_gold_provenance.json` (sha256, single annotator).
- Dataset versions: P&D 6e textbook sections (CC BY 4.0); SciNLP release `SciNLP-repo-e78342be` (`dataset_manifest.json`). Results are never mixed across dataset versions.
