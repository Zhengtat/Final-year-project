# SciNLP (external benchmark, CR-012)

- Source: https://github.com/AKADDC/SciNLP (Duan, Zhang, Peng, Zhang; EMNLP 2025 main; arXiv 2509.07801)
- Cloned commit: `e78342be517e34ec26c69da3261e5ae002d66ea6` (see `reports/cr012/dataset_manifest.json` for the full commit hash and per-file sha256; the clone's `.git` was removed so the folder is not a nested repository)
- Licence: CC BY-NC 4.0, non-commercial academic research only. Only this SOURCE.md is committed; the data files stay local and are not redistributed.
- Role: CR-012 external end-to-end benchmark. Test documents are sealed from every development decision (prompts, few-shot banks, thresholds, lexicon, cues, guards).
- `Dataset/KG_triples.txt` is model-generated (HGERE), not gold.
