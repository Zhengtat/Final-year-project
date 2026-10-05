# CR-010 STOP 2 — freeze before the held-out IIR test run

Written 2026-10-05, committed and tagged `cr-010-stop2-freeze` BEFORE any test-split call. Code commit: `179bbeb4af3f42c49466d43de870fb6b80130c9c`.

## Protocol (owner instruction, 2026-10-05)
- The held-out IIR test split (70 sections) is run **once**. No tuning, no selective re-runs, no threshold changes, no change of arm after seeing test results. All results are reported, including contradictions.
- **N1 is the sole confirmatory arm; N2 and N3 are descriptive.** Criteria for N1 (unchanged from dev, `configs/cr010_node.yaml`): exact micro F1 +0.02 absolute, or paired section-bootstrap 95% lower bound > 0 (10,000 resamples, seed 20261005), and precision drop <= 0.02, against the **frozen CR-009 N0** (`data/processed/concepts_v4/test1/TEST_V4.json`, tau 0.1), the historical comparator.
- N2 uses the dev-frozen trigger theta = 3.0 (items per 100 words below 3.0 in N0's output; 14 of 70 test sections fire by a $0 count).
- One **fresh N0 replication** on the test split (G1, depth 1, M4/M5 off, tau 0.1, started from the dev N0 state `data/processed/cr010/dev/N0.json`) is run as a baseline-stability sensitivity check only; it selects nothing.
- **No automatic adoption.** The N1/N0 decision is returned to Research.
- Failure handling: an infrastructure failure (crash, truncated JSON) is reported as a failure with its count; the run is not re-tried selectively. A crash that stops a command before it finishes may be resumed from the cache of identical calls (the same computation); this will be stated if it happens.
- Cost: STOP 2 cap $5 (owner-approved), $0.17 spent; dry-run estimate for the test split about $0.30 for the arms plus about $0.45 for the N0 replication.

## Frozen files (sha256, first 16 hex digits)
| file | sha256 |
|---|---|
| `configs/cr010_node.yaml` | `b579c9fad61b0d2a` |
| `configs/concept_gvp.yaml` | `40d4c383cda1291d` |
| `configs/default.yaml` | `f7374ce4dc561c4f` |
| `prompts/concept_rescue/v1.md` | `ccfb7e1d99174f78` |
| `prompts/concept_generator/v4.md` | `ba407e4d1293e57f` |
| `prompts/concept_backfill/v1.md` | `26363a2987e97cb1` |
| `src/cumap/cr010/candidates.py` | `0dd30e15c414fd2d` |
| `src/cumap/cr010/rescue.py` | `6a6c56868aa09d3b` |
| `src/cumap/cr010/nodes_exp.py` | `85a12cf8ea5d7724` |
| `src/cumap/cr010/nodes_report.py` | `2094a8ff44b830b4` |
| `src/cumap/eval/stats.py` | `260d47cf9f4068d5` |
| `data/processed/concepts_v4/test1/TEST_V4.json` | `59b30e8396cb39b2` |
| `data/processed/cr010/dev/N0.json` | `1a98475af5130aeb` |
| `data/interim/external/iir_test_gold_concepts_v3.csv` | `c54063d2b2dfb51c` |

## Commands (exactly once each)
```
uv run python -m cumap.cr010.nodes_exp n0-test-replicate
uv run python -m cumap.cr010.nodes_exp arms --split test --arms N1 N3 N2 --max-usd 2
uv run python -m cumap.cr010.nodes_exp report --split test
```
