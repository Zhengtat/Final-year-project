# PROMPT-CR-012 — Coding-agent handoff

Implement **CR-012 — End-to-End Expert Knowledge Graph Evaluation and Error Attribution** exactly as specified in `docs/change-requests/CR-012-end-to-end-evaluation.md`.

## Dependency gate

Do not freeze a production baseline until:

1. CR-010 has a final architecture decision;
2. CR-011 has completed its experiments and selected production outcome;
3. CR-011 STOP 5 has emitted `reports/cr011_sleep/CR012_EVAL_HANDOFF.json`.

Architecture-independent scaffolding may be built earlier, but must remain unfrozen.

## First action — STOP 1 only

No paid evaluation.

1. Reconcile final CR-010 and CR-011 state against the actual repository.
2. Verify the CR-011 evaluation handoff and immutable pre/post hashes.
3. Locate production concept/relation/canonicalisation/sleep configs and record hashes.
4. Audit the exact SciNLP release: source, version/commit, counts, split, schema inventories, licence, hashes and official scorer.
5. Audit optional benchmarks only if enabled.
6. Confirm benchmark/test isolation from prior development.
7. Estimate documents, calls, prompt sizes/tokens and spend from actual repository configuration.
8. Fill `reports/cr012/STOP1_BENCHMARK_AUDIT.md` and `dataset_manifest.json`.
9. If benchmark facts materially contradict the Research specification, stop with `RESEARCH DECISION REQUIRED`.

## STOP 2

Build the adapter/scorer/oracle/bootstrap/stability/failure-attribution infrastructure. Freeze 2 P&D pilot sections and 6–8 held-out sections **before viewing final CUM predictions**. Produce blind annotation sheets. Do not run held-out evaluation.

## STOP 3

Validate only on SciNLP train/dev and the P&D pilot. Validate strict span/type/identity/relation/direction/symmetric/qualifier rules, pair denominator, oracle isolation, earliest-error attribution, pre/post snapshot identity, bootstrap grouping and cost estimation. Freeze evaluation code/config afterwards.

## STOP 4

Run held-out once under the freeze: E0, E1, E2 where supported, E3 and E4 on SciNLP test and P&D-E2E held-out. No tuning from results.

## STOP 5

Evaluate CR-011 pre/post using the exact same extraction snapshots and run the frozen stability repetitions. Produce final analysis only; do not modify production architecture.

## Non-negotiable rules

- Headline metric is `STRICT_E2E_EDGE_F1`.
- Do not replace it with a composite score.
- Missing endpoint is a concept/node failure, not a pair failure.
- Pair-recall denominator includes only gold edges whose endpoint nodes exist.
- E3 exposes endpoint pairs, never gold relation labels.
- External schemas remain external; do not translate them into networking ontology labels.
- Held-out labels never enter prompts, thresholds, lexicon, cues or guards.
- No best-run selection in stability analysis.
- Bootstrap by document/section, never independent edges.
- `data/gold` is read-only to pipeline code.
- No paid call before preflight.
- Any methodological ambiguity is `RESEARCH DECISION REQUIRED`.
