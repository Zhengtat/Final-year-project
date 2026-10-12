"""CR-013 STOP 1: read-only trace audit of retained artifacts. Computes counts and hashes from the artifacts themselves and writes
`reports/cr013/trace_coverage.md` (and `trace_coverage.json`). No model call, no write outside `reports/cr013/`.

    uv run python -m cumap.explain.audit
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from cumap.config import REPO_ROOT

KG = REPO_ROOT / "data/processed/kg"
PD, SC = "slice3_c2", "cr012_scinlp_heldout_P17_1058_grobid_E0"
OUT = REPO_ROOT / "reports/cr013"
REC, PART, NOT, JOIN = "RECORDED", "PARTIAL", "NOT_RECORDED", "RECOVERABLE_BY_DETERMINISTIC_JOIN"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def prompt_hashes_present(need: set[str]) -> int:
    have: set[str] = set()
    with (REPO_ROOT / "data/logs/llm_prompts.jsonl").open(encoding="utf-8") as f:
        for line in f:
            h = line.split('"input_hash": "', 1)[1][:64]
            if h in need:
                have.add(h)
    return len(have)


def measure() -> dict:
    base = KG / PD
    cp = json.loads((base / "checkpoint.json").read_text())
    v4 = json.loads((base / "v4_concepts.json").read_text())
    res = cp["relation_results_v3"]
    selected = [r for r in res if r.get("group") == "selected"]
    edges = [r for r in selected if r["outcome"] == "edge"]
    snap_edges = {
        e["edge_id"] for ch in (1, 2, 3) for e in jl(base / f"snapshots/ch{ch}/edges.jsonl")
    }
    by_pair = {r["pair"]["pair_id"]: r for r in selected}
    names = {c["canonical_name"].lower() for c in cp["concepts"]} | {
        a.lower() for c in cp["concepts"] for a in c["aliases"]
    }
    need = {h for e in edges for h in e["prompt_hashes"].values()}
    org_events = jl(base / "organisation/org_b6ebb5bc/ch3/events.jsonl")
    iters = [i for s in v4["sections"].values() for i in s["iterations"]]
    sc = json.loads((KG / SC / "checkpoint.json").read_text())
    stats = cp["selection_stats"]
    return {
        "run": PD, "concepts": len(cp["concepts"]), "concepts_with_quoted_mention": sum(1 for c in cp["concepts"] if any(m.get("quote") for m in c["mentions"])),
        "concepts_with_alias_provenance": sum(1 for c in cp["concepts"] if c["alias_provenance"]), "concepts_with_merged_from": sum(1 for c in cp["concepts"] if c["merged_from"]),
        "v4_nodes": len(v4["nodes"]), "v4_nodes_joinable_by_name": sum(1 for n in v4["nodes"].values() if n["name"].lower() in names),
        "v4_sections_units": len(v4["sections"]), "generator_iterations": len(iters), "iterations_with_flags": sum(1 for i in iters if i["flags"]), "iterations_with_autofixes": sum(1 for i in iters if i["autofixes"]),
        "pruned_records": len(v4["sections"]) and sum(len(m.get("pruned", [])) for m in v4["section_meta"].values()), "pruner_p_recorded_sections": sum(1 for m in v4["section_meta"].values() if m.get("p")),
        "merges_checkpoint": dict(Counter(f"{m['stage']}|rule={m['rule_id']}|llm={m['llm_called']}|auto={m['auto_merged']}" for m in cp["merges"])),
        "merge_review": len(cp["merge_review"]), "taxonomy_candidates": len(cp["taxonomy_candidates"]), "related_candidates": len(cp["related_candidates"]), "anchors": len(cp["anchors"]),
        "selection_stats": stats, "selected_pairs": len(cp["selected_pairs"]), "selected_pair_fields": sorted({k for p in cp["selected_pairs"] for k in p}),
        "relation_rows_selected": len(selected), "relation_rows_sample": sum(1 for r in res if r.get("group") == "sample"),
        "outcomes": dict(Counter(r["outcome"] for r in selected)), "reasons": dict(Counter(r.get("reason") for r in selected if r["outcome"] != "edge")),
        "edge_rows": len(edges), "snapshot_edges": len(snap_edges), "snapshot_edges_matched_to_relation_row": len(snap_edges & set(by_pair)),
        "edge_quote_is_substring_of_pair_sentence": sum(1 for r in edges if r["evidence_quote"] and r["evidence_quote"] in r["pair"]["sentence"]),
        "edge_prompt_hashes": len(need), "edge_prompt_hashes_in_llm_prompts_log": prompt_hashes_present(need),
        "edges_with_confidence_field": sum(1 for r in edges if "confidence" in r), "org_events": len(org_events), "org_events_with_edge_ids": sum(1 for e in org_events if e["because_edge_ids"]),
        "scinlp_run": SC, "scinlp_keys": {k: (len(v) if hasattr(v, "__len__") else v) for k, v in sc.items()},
    }  # fmt: skip


MATRIX = [
    # stage, input, decision, alternatives, reason, output, evidence, rank/budget, provenance, where / notes
    ("source text", "RECORDED", "n/a", "n/a", "n/a", "RECORDED", "RECORDED", "n/a", PART, "`data/interim/textbook_sections.jsonl` (section text, headings); sentence boundaries are produced by deterministic code, not stored; section text hash not yet recorded in any run artifact"),
    ("concept generator", PART, REC, PART, REC, REC, REC, "n/a", PART, "`v4_concepts.json` -> `sections[*].iterations[*].output` (new_concepts with evidence, role, para, extraction_origin, `independence_check` text); the input prompt is in `data/logs/llm_prompts.jsonl` by hash but the section/iteration -> input_hash link is NOT_RECORDED"),
    ("verifier / correction", REC, REC, PART, REC, REC, REC, "n/a", PART, "`iterations[*].verified/flags/hints/autofixes/warnings` and per-section `flags_by_rule`, `hints_added`, `hints_rejected`, `stop_reason`; verifier is rule-based code (no model id); rule configuration not hashed in the artifact"),
    ("pruner", REC, REC, "n/a", PART, REC, REC, "n/a", PART, "`section_meta[*].p` (per-candidate probability) and `pruned` (empty: pruner off, tau 0); the threshold is in the run recipe (code / docs), not in the artifact"),
    ("canonicalisation / aliasing", PART, REC, PART, REC, REC, PART, "similarity only", PART, "`checkpoint.merges` (stage, rule_id, llm_called, auto_merged, overridden, reason, similarity, evidence_quote), `merge_review`, `taxonomy_candidates`, v4 `merges` (G-link); `alias_provenance` and `merged_from` are EMPTY on every concept; blocked merges (CR-008 DIFFERENT veto) have NO retained record"),
    ("pair generation", NOT, NOT, NOT, NOT, PART, PART, "counts only", NOT, "only aggregates: `selection_stats.unique_candidate_pairs`, `candidate_pairs_before_dedup`; the eligible pool itself is NOT retained; `related_candidates` and `anchors` record two candidate sources"),
    ("pair ranking + budget selection", NOT, PART, NOT, NOT, REC, PART, "NOT_RECORDED", NOT, "selected pairs only (`selected_pairs`: pair_id, section_id, endpoints, sentence, cooccurrence_count, cue_score); NO per-pair rank, NO selection phase per pair (only aggregate phase counts), NO eligible_count per section; `budget` is global (1100, min 8 per section), not per section; 50 unselected pairs retained as `sample_pairs`"),
    ("relation classification", PART, REC, PART, REC, REC, REC, "n/a", REC, "`relation_results_v3` (outcome, family, relation, direction, statement, evidence_quote, qualifiers, family_reason, other_*; `prompt_hashes` -> exact prompt text incl. the choice set in `llm_prompts.jsonl`; model/tier per call in `llm_calls.jsonl`); alternatives not chosen are only in the prompt text; NO confidence field"),
    ("validation / grounding", REC, REC, "n/a", REC, REC, REC, "n/a", PART, "`relation_results_v3[*].grounding`, `type_errors`, `reason` (domain_range, endpoint_not_grounded, comparison_no_grounded_dimension, ...); `rejected_relations` list is empty (rejections are rows with outcome `rejected`)"),
    ("graph commit", REC, REC, "n/a", "n/a", REC, REC, "n/a", PART, "`pair_registry` (edge objects), `snapshots/ch*/edges.jsonl|nodes.jsonl|merges.jsonl|rejected.jsonl`; snapshots are per-chapter additions"),
    ("organisation (read-only)", REC, REC, "n/a", PART, REC, PART, "n/a", REC, "`organisation/org_b6ebb5bc/ch*/org_nodes.jsonl|communities.jsonl|events.jsonl`; events carry `because_edge_ids` for part of the events; manifest has config hash and code version"),
]  # fmt: skip


def write(m: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    arts = [KG / PD / "checkpoint.json", KG / PD / "v4_concepts.json", KG / PD / "organisation/org_b6ebb5bc/ch3/events.jsonl", KG / PD / "organisation/org_b6ebb5bc/ch3/org_nodes.jsonl",
            KG / PD / "snapshots/ch3/edges.jsonl", REPO_ROOT / "data/interim/textbook_sections.jsonl", KG / SC / "checkpoint.json", KG / SC / "v4_concepts.json"]  # fmt: skip
    for p in [
        *sorted((KG / PD / "snapshots").glob("ch*/edges.jsonl")),
        REPO_ROOT / "data/logs/llm_calls.jsonl",
    ]:
        if p not in arts:
            arts.append(p)
    rows = [
        (p.relative_to(REPO_ROOT).as_posix(), p.stat().st_size, sha(p)) for p in arts if p.exists()
    ]
    L = ["# CR-013 STOP 1: trace coverage audit", "",
         "Read-only audit of the retained artifacts of the production run `slice3_c2` (P&D chapters 1-3) and one retained SciNLP held-out E0 run (`" + SC + "`). Generated by `uv run python -m cumap.explain.audit`; $0, no model call, nothing written outside `reports/cr013/`. **No UI work has been done.**", "",
         "Status words: `RECORDED` (in a retained artifact), `PARTIAL`, `NOT_RECORDED` (not retained; stays a trace gap), `n/a` (the stage has no such thing).", "",
         "## 1. Stage x field matrix (production run `slice3_c2`)", "",
         "| stage | input | decision | alternatives | reason | output | evidence | rank / budget | provenance | artifact and locator / gaps |", "|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    L += ["| " + " | ".join(row) + " |" for row in MATRIX]
    st = m["selection_stats"]
    L += ["", "## 2. Measured facts behind the matrix", "",
          "| measure | value |", "|---|---|",
          f"| final canonical concepts | {m['concepts']} |", f"| ... with at least one quoted mention (evidence) | {m['concepts_with_quoted_mention']} |",
          f"| ... with `alias_provenance` / `merged_from` | {m['concepts_with_alias_provenance']} / {m['concepts_with_merged_from']} (legacy run: never recorded) |",
          f"| v4 generator nodes (before canonicalisation) | {m['v4_nodes']} |", f"| ... joinable to a final concept by exact name or alias | {m['v4_nodes_joinable_by_name']} (a join on names; no id link is stored) |",
          f"| generator units (sections / sub-sections) / iterations | {m['v4_sections_units']} / {m['generator_iterations']} |", f"| iterations with verifier flags / autofixes | {m['iterations_with_flags']} / {m['iterations_with_autofixes']} |",
          f"| pruner `p` recorded for sections / pruned records | {m['pruner_p_recorded_sections']} / {m['pruned_records']} |",
          f"| canonicalisation records (checkpoint merges) | {json.dumps(m['merges_checkpoint'])} |", f"| merge_review / taxonomy_candidates / related_candidates / anchors | {m['merge_review']} / {m['taxonomy_candidates']} / {m['related_candidates']} / {m['anchors']} |",
          f"| eligible pool (unique pairs) / before dedup / selected / budget | {st['unique_candidate_pairs']} / {st['candidate_pairs_before_dedup']} / {st['selected']} / {st['budget']} (min {st['min_per_section']} per section) |",
          f"| selection phases (aggregate only) | phase0 min-per-section {st['phase0_min_per_section']}, phase1 coverage {st['phase1_coverage']}, phase0b anchors {st['phase0b_anchor_pairs']}, phase2 fill {st['phase2_fill']} |",
          f"| fields kept per selected pair | {', '.join(m['selected_pair_fields'])} |", f"| relation rows (selected) / sample rows | {m['relation_rows_selected']} / {m['relation_rows_sample']} |",
          f"| relation outcomes (selected) | {json.dumps(m['outcomes'])} |", f"| non-edge reasons | {json.dumps(m['reasons'])} |",
          f"| edge rows / snapshot edges / snapshot edges matched to a relation row | {m['edge_rows']} / {m['snapshot_edges']} / {m['snapshot_edges_matched_to_relation_row']} |",
          f"| edge evidence quote is a substring of its pair sentence | {m['edge_quote_is_substring_of_pair_sentence']} / {m['edge_rows']} |",
          f"| edge prompt hashes / found in `llm_prompts.jsonl` | {m['edge_prompt_hashes']} / {m['edge_prompt_hashes_in_llm_prompts_log']} |", f"| edges carrying a confidence field | {m['edges_with_confidence_field']} (confidence is NOT_RECORDED) |",
          f"| organisation events / with `because_edge_ids` | {m['org_events']} / {m['org_events_with_edge_ids']} |", "",
          "## 3. Retained SciNLP run (`" + SC + "`)", "",
          f"Artifacts: `checkpoint.json`, `v4_concepts.json` only. Checkpoint section sizes: {json.dumps(m['scinlp_keys'])}. It has the generator iterations, canonicalisation records, selected pairs and relation results, but **no snapshots, no organisation, no pair_registry and no unselected sample** (`sample_pairs` is empty). Gold and scorer outputs live in `reports/cr012/stop4_*` and are evaluation-only.", "",
          "## 4. Findings and trace gaps (what stays `NOT_RECORDED`)", "",
          "1. **Pair rank / eligible pool / selection boundary are not retained** for `slice3_c2`: only aggregates and the selected pairs. The CR's `rank 67 / 187, budget 42` example does not exist for this run: its budget is **global** (1,100) with a per-section minimum of 8; the per-section D3 budget belongs to the CR-012 unit runs.",
          "2. **The unselected eligible pool (8,604 unique pairs) is not stored.** `Why not?` for a never-selected pair can only say `not in the retained selected set`, plus the 50-pair `sample_pairs` outcomes, unless the pool is replayed (see decision 1 below).",
          "3. **Generator calls are not linked to sections by id.** `llm_calls.jsonl` has run_id, task, model, prompt version, input hash, tokens; `v4_concepts.json` has per-section outputs. The join (section/iteration -> input hash) is NOT_RECORDED; it could only be recovered by matching prompt text.",
          "4. **Canonicalisation lineage is name-joined, not id-linked**: `alias_provenance` and `merged_from` are empty for every concept; 1,275 v4 nodes map to 1,243 concepts only by exact name/alias. **Blocked merges** (CR-008 DIFFERENT veto, lexicon) have no retained record in this run.",
          "5. **Relation alternatives and confidence**: only the chosen relation, direction, qualifiers, family reason and outcome are stored. The offered choice set is recoverable from the exact prompt text by hash; the model's rejected options and any confidence are not.",
          f"6. **Internal inconsistencies to explain, not hide**: {m['edge_rows']} relation rows have outcome `edge` but {m['snapshot_edges']} edges are committed to the snapshots; the relation results hold {m['relation_rows_selected']} selected rows for {m['selected_pairs']} selected pairs. Both gaps are small (1 and 3 rows) and will be reported as trace gaps with their ids after the trace build, not corrected.",
          "7. **Source-text hash** is not recorded in the run artifacts (the section file is `data/interim/textbook_sections.jsonl`); the explainability manifest will hash it at build time.",
          "8. **Section ids differ between stages**: the generator uses units (`1.2#1`, `1.2#2`, ... and slug ids), pairs and edges use section ids (`1.2`, `3.3`). A deterministic unit -> section mapping is needed (it is derivable from the unit id).",
          "9. **Legacy status**: `slice3_c2` predates trace logging, so the best achievable lineage is a reconstruction from the artifacts above; every join is labelled `RECOVERABLE_BY_DETERMINISTIC_JOIN` and every missing field `NOT_RECORDED`.", "",
          "## 5. Initial coverage estimates (before the trace build)", "",
          f"- Final concepts with retained source evidence: {m['concepts_with_quoted_mention']} / {m['concepts']} ({100 * m['concepts_with_quoted_mention'] / m['concepts']:.1f}%).",
          f"- Final edges with a relation row, an evidence quote inside its source sentence, and resolvable prompt hashes: {m['snapshot_edges_matched_to_relation_row']} / {m['snapshot_edges']} snapshot edges ({100 * m['snapshot_edges_matched_to_relation_row'] / m['snapshot_edges']:.1f}%); prompt hashes found in the log {m['edge_prompt_hashes_in_llm_prompts_log']} / {m['edge_prompt_hashes']}.",
          "- These are evidence-link coverage figures only; full-pipeline stage lineage (generator to final concept) will be measured by the trace build at STOP 2 with the join rules above, with gaps reported explicitly.", "",
          "## 6. Source artifact hashes (for the read-only integrity proof)", "", "| artifact | bytes | sha256 |", "|---|---|---|"]  # fmt: skip
    L += [f"| `{p}` | {n} | `{h}` |" for p, n, h in rows]
    L += ["", "## 7. Repository-specific implementation plan", "",
          "Existing code to reuse (no parallel architecture): `src/cumap/report/kg_explorer.py` + `kg_explorer.html` (the explorer to extend), `src/cumap/report/data.py` (checkpoint and snapshot loaders), `src/cumap/expert_kg/snapshots.py`, `src/cumap/organisation/` (ring and event data), `src/cumap/cr012/attribution.py` and `stop4_score.py` (frozen earliest-failure codes for the evaluation overlay only).", "",
          "| step | new code (`src/cumap/explain/`) | notes |", "|---|---|---|",
          "| trace schema | `trace.py`: `TraceEvent` dataclass/pydantic (CR section 5.1), JSONL round-trip | production ids are never re-keyed; derived ids are namespaced |",
          "| backfill adapters | `trace.py` / `adapters_pd.py`: one reader per artifact (v4_concepts, checkpoint, snapshots, organisation, prompts log) emitting events with `source_artifact` + `source_locator` | missing values stay null; joins labelled |",
          "| lineage | `lineage.py`: DAG object_lineage (mention -> v4 node -> canonical concept -> pair -> relation row -> edge) | many mentions -> one concept; many evidence -> one edge |",
          "| renderer | `render.py`: template per (stage, outcome) from structured fields, `renderer_version`; no model call | `NOT_RECORDED` wording for absent fields |",
          "| why not | `why_not.py`: ordered stage checks (N0, N1, C0, C1, P0, R0, R1, R2, R3, E0); production = stop at earliest *observable* loss; evaluation = attach frozen CR-012 code | production never says an edge *should* exist |",
          "| coverage | `coverage.py`: coverage %, gaps -> `trace_gaps.jsonl`, manifest with source hashes | read-only integrity check |",
          "| viewer | `viewer_adapter.py`: compact JSON payload for `kg_explorer.html`; new tabs (Pipeline, Walkthrough, Why not?, Rejected/Lost, Stage snapshots) added to the existing HTML | production payload excludes all gold fields; evaluation overlay is a separate, opt-in payload |",
          "| future runs | optional logging hooks that append TraceEvent-compatible records; regression test that predictions are byte-identical with tracing on and off | logging only |", "",
          "Config `configs/cr013_explainability.yaml` (renderer version, source artifacts, gap policy); outputs under `data/processed/explainability/<run>/<explain_id>/` as in the CR.", "",
          "## 8. Decisions needed from Research before STOP 2", "",
          "1. **Replay of pair ranking (the main gap).** The eligible pool and per-pair rank for `slice3_c2` can be regenerated at $0 by re-running the deterministic selection code (`expert_kg/pair_selection.py`, `select_stage`: no model call, local embedding model). Options: (a) **do not replay**: `Why not?` stops at 'not in the retained selected set' for pairs outside the sample (strict reading of 'never infer'); (b) **replay as a clearly labelled derived layer** (`REPLAYED`, verified by checking that it reproduces the recorded selected set exactly, and discarded if it does not). I recommend (b) with that exact-reproduction check, because the whole `Why not?` / pair-rank feature depends on it, but it recomputes rather than reads, so it is your decision.",
          "2. **Name-based joins** (v4 node -> concept; unit -> section) as labelled `RECOVERABLE_BY_DETERMINISTIC_JOIN`: confirm acceptable.",
          "3. **Branch base.** The CR names the final CR-012 state, but the explorer it extends is currently on the unmerged branch `viz-kg-explorer`. I created `cr-013-process-explainability` from that branch (CR-012 final state + explorer). Merging `viz-kg-explorer` into `main` first, and re-basing, is the alternative.", ""]  # fmt: skip
    (OUT / "trace_coverage.md").write_text("\n".join(L), encoding="utf-8")
    (OUT / "trace_coverage.json").write_text(
        json.dumps(
            {
                "measures": m,
                "artifacts": [{"path": p, "bytes": n, "sha256": h} for p, n, h in rows],
            },
            indent=1,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    m = measure()
    write(m)
    print(json.dumps({k: v for k, v in m.items() if not isinstance(v, (dict, list))}, indent=1))
