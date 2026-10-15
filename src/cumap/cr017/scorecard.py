"""CR-017 STOP 5: the three-level scorecard (HEADLINE / DIAGNOSTICS / ORGANISATION) rendered from the machine-readable replay outputs only.

Nothing is recomputed here: every number is read from reports/cr017/headline_metrics.json and diagnostics.json, so the rendered report, the explorer
scorecard and the JSON cannot disagree. Organisation metrics are described but never enter a headline card.

uv run python -m cumap.cr017.scorecard"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path("reports/cr017")
MIN_CI_UNITS = 3
METRICS = [
    ("concept_f1", "Concept F1", "f1"),
    ("ancestor_hierarchy_f1", "Ancestor Hierarchy F1", "f1"),
    ("pair_recall", "Pair Recall", "recall"),
    ("relation_macro_f1", "Relation Macro F1", "f1"),
    ("strict_e2e_edge_f1", "Strict E2E Edge F1", "f1"),
]
ORGANISATION = [
    "community modularity and stability",
    "centrality / PageRank / k-core",
    "centre / inner / middle / outer rings",
    "principle / core / detail distribution",
    "chapter importance trajectories",
]
SC_NOTE = (
    "Mention-level benchmark without identity gold: Concept F1 is the entity-strict analogue and Pair Recall the "
    "endpoints-present analogue; hierarchy is not evaluable; Relation Macro F1 is not computed. Never pooled with P&D."
)
SC_KEYS = {
    "concept_f1": "concept_f1",
    "ancestor_hierarchy_f1": "ancestor_hierarchy_f1",
    "pair_recall": "pair_recall",
    "relation_macro_f1": "relation_macro_f1",
    "strict_e2e_edge_f1": "strict_e2e_edge_f1",
}


def _card(key: str, label: str, field: str, m: dict, analogue: bool = False) -> dict:
    status = m.get("status")
    value = None if status in ("NOT_EVALUABLE", "NOT_COMPUTED") else m.get(field)
    if "tp" in m:
        counts = f"{m['tp']}/{m['fp']}/{m['fn']} (tp/fp/fn)"
    elif "reached" in m:
        counts = f"{m['reached']}/{m['denominator']}"
    else:
        counts = ""
    units = (m.get("bootstrap") or {}).get("units", 0)
    ci = (
        m.get("ci95") if units >= MIN_CI_UNITS else None
    )  # 1-2 sections give a degenerate interval: show none
    classes = m.get("classes") or {}
    precision, recall = m.get("precision"), m.get("recall")
    # macro P/R: same class set and zero-fill rule as the macro F1
    if key == "relation_macro_f1" and classes:
        scored = [v for v in classes.values() if v["support"] > 0]
        precision = sum(v["precision"] or 0.0 for v in scored) / len(scored) if scored else None
        recall = sum(v["recall"] or 0.0 for v in scored) / len(scored) if scored else None
    if status in ("NOT_EVALUABLE", "NOT_COMPUTED"):
        precision = recall = None
    low = sorted(c for c, v in classes.items() if v.get("low_support"))
    return {
        "key": key,
        "label": label,
        "value": value,
        "precision": precision,
        "recall": recall,
        "status": status or "OK",
        "reason": m.get("reason"),
        "ci95": ci,
        "ci_status": m.get("ci_status"),
        "units": units,
        "counts": counts,
        **{k: m[k] for k in ("tp", "fp", "fn", "reached", "denominator") if k in m},
        "analogue": analogue,
        "low_support_classes": low,
        "n_classes": len(classes),
    }


def _relation_table(m: dict) -> list[dict]:
    return [
        {"relation": c, **{k: v[k] for k in ("support", "tp", "fp", "fn", "precision", "recall", "f1", "low_support")}}
        for c, v in sorted((m.get("classes") or {}).items())
    ]  # fmt: skip


def build_scorecard() -> dict:
    hm = json.loads((OUT / "headline_metrics.json").read_text())
    dg = json.loads((OUT / "diagnostics.json").read_text())
    sets: dict = {}
    for tag, label in (
        ("heldout", "P&D-E2E held-out (7 sections, headline)"),
        ("pilot", "P&D-E2E pilot (development)"),
    ):
        lv: dict = {}
        for level, r in hm["pd"][tag].items():
            h, d = r["headline"], dg["pd"][tag].get(level, {})
            lv[level] = {
                "sections": r["sections"],
                "headline": [_card(k, lab, f, h[k]) for k, lab, f in METRICS],
                "diagnostics": {
                    "relation_classes": _relation_table(h["relation_macro_f1"]),
                    "relation_micro": d.get("relation", {}).get("micro"),
                    "direction_accuracy": d.get("relation", {}).get("direction_accuracy_given_correct_label"),
                    "no_prediction_by_outcome": d.get("relation", {}).get("no_prediction_by_outcome"),
                    "direct_parent_f1": d.get("hierarchy", {}).get("direct_parent_f1_pooled"),
                    "per_section": {
                        s: {
                            "concept_f1": v["concept"]["f1"],
                            "hierarchy_f1": v["hierarchy"]["f1"] if v["hierarchy"].get("f1") is not None else None,
                            "pair_recall": v["pair_recall"],
                            "strict_f1": v["strict"]["f1"],
                        }
                        for s, v in d.get("per_section", {}).items()
                    },
                    "legacy_sections": sorted(d.get("legacy", {})),
                },
            }  # fmt: skip
        sets[f"pd_{tag}"] = {"label": label, "benchmark": "P&D-E2E (canonical graph)", "levels": lv}
    sc = {}
    for level, s in hm["scinlp"].items():
        cards = [
            _card(
                k,
                lab,
                f,
                s[SC_KEYS[k]],
                analogue=k in ("concept_f1", "pair_recall", "strict_e2e_edge_f1"),
            )
            for k, lab, f in METRICS
        ]
        sc[level] = {"sections": s["documents"], "headline": cards, "diagnostics": {}}  # fmt: skip
    sets["scinlp"] = {
        "label": "SciNLP held-out (3 documents; separate benchmark)",
        "benchmark": "SciNLP",
        "note": SC_NOTE,
        "levels": sc,
    }
    return {
        "meta": {
            "scorer_version": hm["meta"]["scorer_version"],
            "sources": ["reports/cr017/headline_metrics.json", "reports/cr017/diagnostics.json"],
            "composite_score": False,
            "model_calls": hm["meta"]["model_calls"],
            "interval_note": "Section-bootstrap intervals are descriptive when fewer than 10 units.",
            "low_support_note": "Relation Macro F1 is read with its per-class support table; classes with support <=3 are flagged.",
            "legacy_note": "Legacy detailed metrics (typed canonical node, typed mentions, identity, relation confusion, qualifiers, alignment) remain in diagnostics.json.",
        },
        "datasets": sets,
        "organisation": {
            "title": "ORGANISATION — structural view, not accuracy",
            "note": "Organisation metrics describe how the graph is arranged. They are not accuracy metrics and never enter a headline card.",
            "items": ORGANISATION,
        },
    }


def _n(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def _fmt(c: dict) -> str:
    if c["value"] is None:
        return c["status"]
    s = f"{c['value']:.3f}"
    if c["ci95"]:
        s += f" [{c['ci95'][0]:.3f}, {c['ci95'][1]:.3f}]†"
    return s


def render_markdown(p: dict) -> str:
    m = p["meta"]
    L = [
        "# CR-017 scorecard",
        "",
        f"Scorer `{m['scorer_version']}` · model calls {m['model_calls']} · no composite score · {m['interval_note']} † = descriptive interval (fewer than 10 sections); none is shown for fewer than 3.",
        "",
        "## HEADLINE — five metrics only",
    ]
    for ds, d in p["datasets"].items():
        L += ["", f"### {d['label']}", ""]
        if d.get("note"):
            L += [f"> {d['note']}", ""]
        L += ["| Level | " + " | ".join(c["label"] + (" ⚠" if c["key"] == "relation_macro_f1" else "") for c in next(iter(d["levels"].values()))["headline"]) + " |", "|---" * 6 + "|"]  # fmt: skip
        for lv, r in d["levels"].items():
            L.append(f"| {lv} | " + " | ".join(_fmt(c) for c in r["headline"]) + " |")
    L += [
        "",
        f"⚠ {m['low_support_note']}",
        "",
        "## DIAGNOSTICS — detailed components",
        "",
        m["legacy_note"],
        "",
    ]
    for ds in ("pd_heldout",):
        r = p["datasets"][ds]["levels"]["E0"]["diagnostics"]
        L += ["### Relation classes (P&D held-out, E0)", "", "| relation | support | tp | fp | fn | F1 | low support |", "|---|---|---|---|---|---|---|"]  # fmt: skip
        for x in r["relation_classes"]:
            L.append(f"| {x['relation']} | {x['support']} | {x['tp']} | {x['fp']} | {x['fn']} | {_n(x['f1'])} | {'excluded (no gold)' if not x['support'] else ('yes' if x['low_support'] else '')} |")  # fmt: skip
        mi = r["relation_micro"]
        L += ["", f"Micro P/R/F1 {mi['precision']:.3f}/{mi['recall']:.3f}/{mi['f1']:.3f}; direction accuracy {r['direction_accuracy']:.3f}; no-prediction outcomes {r['no_prediction_by_outcome']}.", ""]  # fmt: skip
    L += ["## AUDIT", "", "Per-item traces, confusion matrices, provenance and hashes: `diagnostics.json`, `historical_replay.md`, and the explorer's Failure map / Gold relations tabs.", ""]  # fmt: skip
    o = p["organisation"]
    L += [f"## {o['title']}", "", o["note"], ""] + [f"- {i}" for i in o["items"]] + [""]
    return "\n".join(L)


def main() -> None:
    p = build_scorecard()
    (OUT / "scorecard.md").write_text(render_markdown(p))
    print("wrote", OUT / "scorecard.md")


if __name__ == "__main__":
    main()
