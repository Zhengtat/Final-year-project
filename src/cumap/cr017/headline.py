"""CR-017 unified five-metric evaluator (scorer only; no model call; no frozen artefact changed).

One entry point, `evaluate(units, symmetric)`, returns the five headline metrics beside the legacy diagnostics. It REUSES the frozen CR-012 scorer for Concept F1 (untyped `canonical_node`), Pair Recall
and Strict E2E Edge F1 (`cumap.cr012.scoring.score_graph_unit`), and the CR-017 hierarchy scorer for Ancestor Hierarchy F1; Relation Macro F1 is new. Frozen semantics: configs/cr017_eval.yaml.

Relation Macro F1 (CR-017 §8, Research rulings 2026-10-14):
  population  = gold edges (deduplicated by the strict-edge key) whose two canonical endpoint concepts have predicted nodes AND whose endpoint pair reached relation classification;
  prediction  = the relation of the classifier's edge for that pair (the gold relation if the classifier produced it among the edges, else the first edge); if the pair ended as
                `other`, `no_relation`, `rejected` or a gated/consolidated-away edge there is NO relation prediction: a false negative for the gold class and a false positive for no class;
  per class r = P_r, R_r, F1_r from TP_r (gold r predicted r), FP_r (gold of another class predicted r), FN_r (gold r not predicted r);
  macro       = mean F1_r over classes with gold support in the population; direction is a separate diagnostic; micro F1 is a diagnostic; classes with support <= 3 are flagged."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from cumap.cr012 import scoring as S
from cumap.cr012.bootstrap import MIN_UNITS_FOR_CI, RESAMPLES, SEED, ci_status
from cumap.cr012.types import PRF, PredEdge, PredNode, UnitGold
from cumap.cr017 import hierarchy as H

CFG_PATH = Path("configs/cr017_eval.yaml")
LOW_SUPPORT = 3
NO_PREDICTION = "<no_relation_prediction>"


@dataclass
class UnitInput:
    gold: UnitGold
    nodes: list[PredNode]
    edges: list[PredEdge]
    proposed_pairs: set[frozenset[str]] | None
    classifier: dict[frozenset[str], list[dict]] = field(
        default_factory=dict
    )  # unordered concept pair -> classifier results {outcome, relation, src, tgt}


def classifier_from_checkpoint(cp: dict, section_id: str) -> dict[frozenset[str], list[dict]]:
    """Every classifier result of the production run for the section's SELECTED pairs, with the same edge filters as `production_graph.graph_for_sections`."""
    out: dict[frozenset[str], list[dict]] = defaultdict(list)
    for r in cp["relation_results_v3"]:
        if r.get("group", "selected") != "selected" or r["pair"]["section_id"] != section_id:
            continue
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        is_edge = (
            r["outcome"] == "edge" and not r.get("gated_dropped") and not r.get("consolidated_into")
        )
        src, tgt = (y, x) if r.get("direction") == "reversed" else (x, y)
        out[frozenset((x, y))].append(
            {
                "outcome": "edge"
                if is_edge
                else (r["outcome"] if r["outcome"] != "edge" else "gated_or_consolidated"),
                "relation": r.get("relation") if is_edge else None,
                "src": src,
                "tgt": tgt,
            }
        )
    return dict(out)


# ---------------------------------------------------------------- relation macro
def relation_rows(u: UnitInput, symmetric: set[str]) -> list[dict]:
    al = S.align_nodes(u.nodes, u.gold.mentions)
    n2c, c2n = al["node_to_concept"], al["concept_to_nodes"]
    keys = {
        S._edge_key(r.src_concept, r.tgt_concept, r.relation, symmetric): r
        for r in u.gold.relations
        if r.src_concept and r.tgt_concept
    }
    rows = []
    for r in keys.values():
        if r.src_concept not in c2n or r.tgt_concept not in c2n or u.proposed_pairs is None:
            continue
        node_pairs = [(a, b) for a in c2n[r.src_concept] for b in c2n[r.tgt_concept]]
        if not any(frozenset(p) in u.proposed_pairs for p in node_pairs):
            continue  # never reached the classifier: a Pair Recall failure
        hits = [x for p in node_pairs for x in u.classifier.get(frozenset(p), [])]
        edges = [h for h in hits if h["outcome"] == "edge"]
        exact = [h for h in edges if h["relation"] == r.relation]
        pick = exact[0] if exact else (edges[0] if edges else None)
        if pick is None:
            outcomes = sorted({h["outcome"] for h in hits}) or ["not_in_results"]
            rows.append(
                {
                    "gold": r.relation,
                    "pred": NO_PREDICTION,
                    "outcome": outcomes[0],
                    "direction_ok": None,
                }
            )
            continue
        direction_ok = None
        if pick["relation"] == r.relation:
            direction_ok = r.relation in symmetric or n2c.get(pick["src"]) == r.src_concept
        rows.append(
            {
                "gold": r.relation,
                "pred": pick["relation"],
                "outcome": "edge",
                "direction_ok": direction_ok,
            }
        )
    return rows


def macro_from_rows(rows: list[dict]) -> dict:
    gold_n, tp, fp = Counter(), Counter(), Counter()
    for r in rows:
        gold_n[r["gold"]] += 1
        if r["pred"] == r["gold"]:
            tp[r["gold"]] += 1
        elif r["pred"] != NO_PREDICTION:
            fp[r["pred"]] += 1
    classes = {}
    for c in sorted(set(gold_n) | set(fp)):
        t, f, n = tp[c], fp[c], gold_n[c] - tp[c]
        p = t / (t + f) if t + f else None
        rec = t / gold_n[c] if gold_n[c] else None
        f1 = (
            2 * p * rec / (p + rec)
            if p is not None and rec is not None and p + rec
            else (0.0 if gold_n[c] else None)
        )
        classes[c] = {
            "support": gold_n[c],
            "tp": t,
            "fp": f,
            "fn": n,
            "precision": p,
            "recall": rec,
            "f1": f1,
            "low_support": 0 < gold_n[c] <= LOW_SUPPORT,
        }
    scored = [v["f1"] for v in classes.values() if v["support"] > 0]
    tpt, fpt = sum(tp.values()), sum(fp.values())
    micro_p = tpt / (tpt + fpt) if tpt + fpt else None
    micro_r = tpt / len(rows) if rows else None
    dir_rows = [r["direction_ok"] for r in rows if r["direction_ok"] is not None]
    return {
        "macro_f1": float(np.mean(scored)) if scored else None, "classes_in_macro": len(scored), "classes": classes, "population": len(rows),
        "micro": {"precision": micro_p, "recall": micro_r, "f1": (2 * micro_p * micro_r / (micro_p + micro_r)) if micro_p and micro_r else (0.0 if rows else None)},
        "direction_accuracy_given_correct_label": (sum(dir_rows) / len(dir_rows)) if dir_rows else None, "no_prediction_by_outcome": dict(Counter(r["outcome"] for r in rows if r["pred"] == NO_PREDICTION)),
    }  # fmt: skip


# ---------------------------------------------------------------- bootstrap
def bootstrap(stat, unit_ids: list[str], b: int = RESAMPLES, seed: int = SEED) -> dict:
    """Percentile 95% interval of `stat(list_of_unit_ids)`, resampling whole sections (same RNG recipe as cr012/bootstrap.cluster_bootstrap)."""
    keys = sorted(unit_ids)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(b, len(keys)))
    vals = np.array(
        [v if (v := stat([keys[i] for i in row])) is not None else np.nan for row in idx]
    )
    ok = vals[~np.isnan(vals)]
    return {
        "ci95": [float(np.percentile(ok, 2.5)), float(np.percentile(ok, 97.5))]
        if len(ok)
        else None,
        "ci_status": ci_status(len(keys)),
        "bootstrap": {
            "unit": "section",
            "units": len(keys),
            "resamples": b,
            "seed": seed,
            "valid_resamples": len(ok),
        },
    }


def _prf_stat(per: dict[str, PRF], field_: str):
    def f(ids):
        t, p_, n = (
            sum(per[i].tp for i in ids),
            sum(per[i].fp for i in ids),
            sum(per[i].fn for i in ids),
        )
        return PRF(t, p_, n).__getattribute__(field_) if (t + p_ + n) else None

    return f


# ---------------------------------------------------------------- evaluator
def evaluate(units: dict[str, UnitInput], symmetric: set[str], *, boot: bool = True) -> dict:
    per_score = {
        sid: S.score_graph_unit(
            u.gold, u.nodes, u.edges, symmetric, proposed_pairs=u.proposed_pairs
        )
        for sid, u in units.items()
    }
    hier = {sid: H.score_hierarchy_unit(u.gold, u.nodes, u.edges) for sid, u in units.items()}
    rel_rows = {sid: relation_rows(u, symmetric) for sid, u in units.items()}
    ids = sorted(units)
    concept = {sid: per_score[sid]["canonical_node"] for sid in ids}
    strict = {sid: per_score[sid]["strict_e2e_edge"] for sid in ids}
    hprf = {sid: hier[sid]["ancestor_hierarchy"] for sid in ids}
    den = {sid: per_score[sid]["pair_recall"]["denominator"] for sid in ids}
    hit = {sid: per_score[sid]["pair_recall"]["reached_classification"] or 0 for sid in ids}

    def pooled(d: dict[str, PRF]) -> PRF:
        return PRF(
            sum(v.tp for v in d.values()),
            sum(v.fp for v in d.values()),
            sum(v.fn for v in d.values()),
        )

    def block(d: dict[str, PRF]) -> dict:
        p = pooled(d)
        out = {
            "precision": p.precision,
            "recall": p.recall,
            "f1": p.f1,
            "tp": p.tp,
            "fp": p.fp,
            "fn": p.fn,
        }
        out |= (
            bootstrap(_prf_stat(d, "f1"), ids)
            if boot
            else {"ci95": None, "ci_status": ci_status(len(ids))}
        )
        return out

    headline: dict = {"concept_f1": block(concept) | {"variant": "canonical_node_untyped"}}
    gold_pairs_total = sum(h["gold_ancestor_pairs"] for h in hier.values())
    if gold_pairs_total == 0:
        headline["ancestor_hierarchy_f1"] = {
            "status": "NOT_EVALUABLE",
            "reason": "HIERARCHY_GOLD_GAP",
            "f1": None,
            "ci95": None,
        }
    else:
        headline["ancestor_hierarchy_f1"] = block(hprf) | {
            "status": "OK",
            "gold_ancestor_pairs": gold_pairs_total,
        }
    d_tot, h_tot = sum(den.values()), sum(hit.values())
    headline["pair_recall"] = {
        "recall": (h_tot / d_tot) if d_tot else None,
        "reached": h_tot,
        "denominator": d_tot,
        "missing_endpoint_excluded": sum(
            per_score[s]["pair_recall"]["missing_endpoint_excluded"] for s in ids
        ),
    }
    headline["pair_recall"] |= (
        bootstrap(
            lambda sel: (
                (sum(hit[i] for i in sel) / s_) if (s_ := sum(den[i] for i in sel)) else None
            ),
            ids,
        )
        if boot
        else {"ci95": None, "ci_status": ci_status(len(ids))}
    )
    all_rows = [r for sid in ids for r in rel_rows[sid]]
    macro = macro_from_rows(all_rows)
    headline["relation_macro_f1"] = {
        "f1": macro["macro_f1"],
        "classes": macro["classes"],
        "population": macro["population"],
        "classes_in_macro": macro["classes_in_macro"],
    }
    headline["relation_macro_f1"] |= (
        bootstrap(
            lambda sel: macro_from_rows([r for i in sel for r in rel_rows[i]])["macro_f1"], ids
        )
        if boot
        else {"ci95": None, "ci_status": ci_status(len(ids))}
    )
    headline["strict_e2e_edge_f1"] = block(strict)
    diagnostics = {
        "relation": {"micro": macro["micro"], "direction_accuracy_given_correct_label": macro["direction_accuracy_given_correct_label"], "no_prediction_by_outcome": macro["no_prediction_by_outcome"], "low_support_classes": [c for c, v in macro["classes"].items() if v["low_support"]]},
        "hierarchy": {"direct_parent_f1_pooled": pooled({s: hier[s]["direct_parent_diagnostic"] for s in ids}).to_dict(), "predicted_cycles": {s: hier[s]["predicted_cycles"] for s in ids if hier[s]["predicted_cycles"]}, "gold_cycles": {s: hier[s]["gold_cycles"] for s in ids if hier[s]["gold_cycles"]}},
        "legacy": {sid: {"canonical_node_typed": per_score[sid]["canonical_node_typed"].to_dict(), "concept_mentions_typed": per_score[sid]["concept_mentions_typed"].to_dict(), "identity": per_score[sid]["identity"], "relation_conditional": per_score[sid]["relation_conditional"],
                         "relation_confusion": per_score[sid]["relation_confusion"], "qualifier_accuracy": per_score[sid]["qualifier_accuracy"], "alignment": per_score[sid]["alignment"]} for sid in ids},
        "per_section": {sid: {"concept": concept[sid].to_dict(), "hierarchy": hprf[sid].to_dict(), "pair_recall": [hit[sid], den[sid]], "relation_population": len(rel_rows[sid]), "strict": strict[sid].to_dict()} for sid in ids},
    }  # fmt: skip
    return {"headline": headline, "diagnostics": diagnostics}


def provenance(prediction_paths: list[Path], gold_path: Path) -> dict:
    def sha(paths):
        h = hashlib.sha256()
        for p in paths:
            h.update(p.read_bytes())
        return h.hexdigest()

    return {
        "prediction_hash": sha(sorted(prediction_paths)), "gold_hash": sha([gold_path]), "config_hash": sha([CFG_PATH]),
        "code_revision": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip(),
        "scorer_files_sha256": {f: hashlib.sha256(Path(f).read_bytes()).hexdigest()[:16] for f in ("src/cumap/cr012/scoring.py", "src/cumap/cr017/hierarchy.py", "src/cumap/cr017/headline.py")},
    }  # fmt: skip


def load_config() -> dict:
    return yaml.safe_load(CFG_PATH.read_text())


__all__ = [
    "MIN_UNITS_FOR_CI",
    "UnitInput",
    "classifier_from_checkpoint",
    "evaluate",
    "json",
    "load_config",
    "macro_from_rows",
    "provenance",
    "relation_rows",
]
