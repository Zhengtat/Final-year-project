"""CR-032 ($0, no model call): broader Hierarchy F1 `HIER-T1` / `HIER-T1-SURF-R1`, reported beside the frozen numbers.

    uv run python -m cumap.cr032.run [--write-sheet]

Determinism gate first (the generic scorer with the hierarchy set {is_a} must equal the frozen CR-017 scorer per section and pooled, and with surface
identity and {subclassOf, subtaskOf} the CR-022 A2 figures), source hashes before and after, then the report. Writes only `reports/cr032/` and, with
`--write-sheet`, the blind owner sheet under `data/interim/suggestions/`."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.types import PRF
from cumap.cr017 import hierarchy as FH
from cumap.cr017 import run as R17
from cumap.cr022 import run as R22
from cumap.cr022 import scoring as C22
from cumap.cr032 import hier_t1 as H
from cumap.cr032 import scinlp_t1 as ST
from cumap.expert_kg.alias_rules import AliasConfig
from cumap.schemas.relations import RelationRegistry

OUT = REPO_ROOT / "reports/cr032"
HEADLINE = REPO_ROOT / "reports/cr017/headline_metrics.json"
PART_A = REPO_ROOT / "reports/cr022/part_a.json"
PD_LEVELS = ("E0", "E1", "E2", "E3", "E4")


def prf_d(x: PRF) -> dict:
    return {
        "tp": x.tp,
        "fp": x.fp,
        "fn": x.fn,
        "precision": x.precision,
        "recall": x.recall,
        "f1": x.f1,
    }


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def registries(cfg: dict) -> tuple[RelationRegistry, RelationRegistry]:
    return (
        RelationRegistry.from_yaml(REPO_ROOT / cfg["pd"]["registry"]),
        RelationRegistry.from_yaml(REPO_ROOT / cfg["scinlp"]["registry"]),
    )


def scinlp_labels(reg: RelationRegistry, rels: frozenset[str], source: str) -> frozenset[str]:
    return frozenset(
        lab
        for r in reg.all_relations()
        if r.name in rels
        for lab in r.external_labels.get(source, [])
    )


# ---------------------------------------------------------------- P&D
def pd_level(tag: str, level: str, rels, typed, secs) -> dict | None:
    units, _sym, paths, _gold = R17.load_units(tag, level)
    if not units:
        return None
    t1, frozen, frozen_is_a = {}, {}, {}
    for sid, u in units.items():
        rid = R17.run_ids(tag, level, [sid])[sid]
        pts = H.edge_part_types(PG.load_run(rid), sid)
        t1[sid] = H.pd_unit(u.gold, u.nodes, u.edges, rels, typed, pts)
        frozen[sid] = H.pd_unit(u.gold, u.nodes, u.edges, frozenset({"is_a"}), frozenset())
        frozen_is_a[sid] = FH.score_hierarchy_unit(u.gold, u.nodes, u.edges)["ancestor_hierarchy"]
    return {
        "sections": sorted(units),
        "frozen_is_a_cr017": prf_d(
            FH.pool({s: {"ancestor_hierarchy": x} for s, x in frozen_is_a.items()})
        ),
        "generic_scorer_on_is_a": prf_d(H.pool(frozen)),
        "HIER_T1": prf_d(H.pool(t1)),
        "HIER_T1_direct_edges": prf_d(H.pool(t1, "direct")),
        "HIER_T1_per_relation": {r: prf_d(x) for r, x in H.pool_per_relation(t1).items()},
        "gold_pairs": sum(u["gold_pairs"] for u in t1.values()),
        "gold_direct_edges": sum(u["gold_direct_edges"] for u in t1.values()),
        "cycles": {
            s: {"gold": u["gold_cycles"], "pred": u["pred_cycles"]}
            for s, u in t1.items()
            if u["gold_cycles"] or u["pred_cycles"]
        },
        "direct_only_edges": {
            "gold": sum(u["direct_only_edges"]["gold"] for u in t1.values()),
            "predicted": sum(u["direct_only_edges"]["predicted"] for u in t1.values()),
        },
        "_frozen_per_section": {s: (x.tp, x.fp, x.fn) for s, x in frozen_is_a.items()},
        "_generic_per_section": {
            s: (u["prf"].tp, u["prf"].fp, u["prf"].fn) for s, u in frozen.items()
        },
        "_paths": [str(p) for p in paths],
    }


# ---------------------------------------------------------------- SciNLP
def scinlp_set(split, rid, docs_keys, variants, ad, sym, labels, h2, marks, acfg) -> dict:
    gold = ad.gold(split)
    dmap = {d.doc_key: d for d in ad.load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)}
    out: dict = {
        "documents": [d for d in docs_keys if (PG.run_path(rid(d)) / "checkpoint.json").exists()],
        "variants": {},
    }
    for v in variants:
        r1_units, sheet_units, surf_units, gate_units, coll = {}, {}, {}, {}, {}
        for d in out["documents"]:
            cp = json.loads((PG.run_path(rid(d)) / "checkpoint.json").read_text())
            doc, g = dmap[d], gold[d]
            p = C22.place(doc, cp, v)
            ident, st = ST.r1_identity(doc, acfg)
            r1_units[d] = ST.scinlp_unit(g, p.rels, p.unplaced_by_label, v, labels, ident)
            surf_units[d] = ST.scinlp_unit(
                g, p.rels, p.unplaced_by_label, v, labels, ST.surface_identity(doc)
            )
            gate_units[d] = ST.scinlp_unit(
                g, p.rels, p.unplaced_by_label, v, h2, ST.surface_identity(doc)
            )
            if marks is not None:
                sheet_units[d] = ST.scinlp_unit(
                    g, p.rels, p.unplaced_by_label, v, labels, ST.sheet_identity(d, marks)
                )
            if v == variants[0]:
                coll[d] = {**ST.collision_report(doc, g, ident), **st}
        entry = {
            "HIER_T1_SURF_R1": prf_d(H.pool(r1_units)),
            "HIER_T1_SURF_R1_direct_edges": prf_d(H.pool(r1_units, "direct")),
            "HIER_T1_SURF_R1_per_relation": {
                r: prf_d(x) for r, x in H.pool_per_relation(r1_units).items()
            },
            "gold_pairs": sum(u["gold_pairs"] for u in r1_units.values()),
            "gold_direct_edges": sum(u["gold_direct_edges"] for u in r1_units.values()),
            "unplaced_counted_as_fp": sum(u["unplaced_counted_as_fp"] for u in r1_units.values()),
            "cycles": {
                d: {"gold": u["gold_cycles"], "pred": u["pred_cycles"]}
                for d, u in r1_units.items()
                if u["gold_cycles"] or u["pred_cycles"]
            },
            "same_set_surface_identity": prf_d(H.pool(surf_units)),
            "_gate_h2_surface": prf_d(H.pool(gate_units)),
            "_gate_h2_surface_per_doc": {
                d: (u["prf"].tp, u["prf"].fp, u["prf"].fn) for d, u in gate_units.items()
            },
        }
        entry["HIER_T1_real_identity"] = (
            prf_d(H.pool(sheet_units)) if sheet_units else "AWAITING_OWNER_IDENTITY_SHEET"
        )
        out["variants"][v] = entry
        if coll:
            out["collisions"] = coll
    return out


# ---------------------------------------------------------------- gate
def gate(pd_res: dict, sc_frozen: dict) -> dict:
    checks: dict[str, bool] = {}
    headline = json.loads(HEADLINE.read_text())["pd"]
    for key, lv in pd_res.items():
        tag, level = key.split("/")
        checks[f"pd_{tag}_{level}_generic_equals_frozen_per_section"] = (
            lv["_generic_per_section"] == lv["_frozen_per_section"]
        )
        ref = headline.get(tag, {}).get(level, {}).get("headline", {}).get("ancestor_hierarchy_f1")
        if ref and "tp" in ref:
            f = lv["frozen_is_a_cr017"]
            checks[f"pd_{tag}_{level}_equals_cr017_headline_json"] = (
                f["tp"],
                f["fp"],
                f["fn"],
            ) == (ref["tp"], ref["fp"], ref["fn"]) and abs(f["f1"] - ref["f1"]) < 1e-12
    pa = json.loads(PART_A.read_text())["sets"]
    ref_set = next(v for k, v in pa.items() if k.startswith("test:frozen"))
    for v, e in sc_frozen["variants"].items():
        ref = ref_set["variants"][v]["A2_HIER_ANC_SURF"]["H2 {subclassOf, subtaskOf}"]
        g = e["_gate_h2_surface"]
        checks[f"scinlp_test_frozen_{v}_surface_H2_equals_cr022_part_a"] = (
            g["tp"],
            g["fp"],
            g["fn"],
        ) == (ref["tp"], ref["fp"], ref["fn"])
    return {"checks": checks, "passed": all(checks.values())}


def main(write_sheet: bool = False) -> dict:
    cfg = H.load_config()
    reg_pd, reg_sc = registries(cfg)
    rels_pd, typed_pd = H.hierarchy_relations(reg_pd, cfg)
    rels_sc, _typed_sc = H.hierarchy_relations(reg_sc, cfg)
    labels = scinlp_labels(reg_sc, rels_sc, cfg["scinlp"]["source"])
    h2 = frozenset({"subclassOf", "subtaskOf"})
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    acfg = AliasConfig.load()

    sources = [HEADLINE, PART_A]
    OUT.mkdir(parents=True, exist_ok=True)
    pd_res: dict = {}
    for tag in ("heldout", "pilot"):
        for level in PD_LEVELS:
            r = pd_level(tag, level, rels_pd, typed_pd, secs)
            if r:
                pd_res[f"{tag}/{level}"] = r
                sources += [Path(p) for p in r["_paths"]]
    marks_path = REPO_ROOT / cfg["scinlp"]["identity_marks"]
    marks = ST.load_identity_marks(marks_path) if marks_path.exists() else None
    sc: dict = {}
    for split, label, rid, docs, variants in R22.SETS[:2]:
        vs = ("FROZEN", "IDX-P1") if "frozen" in label else ("FROZEN", "IDX-P1", "IDXR1-P1")
        sources += [
            PG.run_path(rid(d)) / "checkpoint.json"
            for d in docs
            if (PG.run_path(rid(d)) / "checkpoint.json").exists()
        ]
        sc[label] = scinlp_set(split, rid, docs, vs, ad, sym, labels, h2, marks, acfg)
    before = {str(p): sha(p) for p in sources}
    sc_frozen = next(v for k, v in sc.items() if "frozen" in k)
    g = gate(pd_res, sc_frozen)
    after = {str(p): sha(p) for p in sources}
    sheet_rows = None
    if write_sheet:
        golds = ad.gold("test")
        docs = {d.doc_key: d for d in ad.load_documents("test", paragraph_every=SR.PARAGRAPH_EVERY)}
        sheet_rows = ST.write_identity_sheet(
            docs, golds, labels, REPO_ROOT / cfg["scinlp"]["identity_sheet"]
        )
    res = {
        "hierarchy_set_pd": sorted(rels_pd),
        "typed_relations_pd": sorted(typed_pd),
        "hierarchy_set_scinlp": sorted(rels_sc),
        "scinlp_labels": sorted(labels),
        "gate": g,
        "hashes_unchanged": before == after,
        "n_hashed": len(before),
        "pd": {k: {a: b for a, b in v.items() if not a.startswith("_")} for k, v in pd_res.items()},
        "scinlp": {
            lab: {**{a: b for a, b in s.items() if a != "variants"}, "variants": {v: {a: b for a, b in e.items() if not a.startswith("_")} for v, e in s["variants"].items()}}
            for lab, s in sc.items()
        },
        "identity_sheet_rows_written": sheet_rows,
        "real_identity_marks": "present" if marks is not None else "AWAITING_OWNER_IDENTITY_SHEET",
    }  # fmt: skip
    (OUT / "hier_t1.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    from cumap.cr032 import report

    (OUT / "hier_t1.md").write_text(report.markdown(res), encoding="utf-8")
    print(
        "gate", g["passed"], "hashes unchanged", res["hashes_unchanged"], "sheet rows", sheet_rows
    )
    if not g["passed"]:
        print({k: v for k, v in g["checks"].items() if not v})
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-sheet", action="store_true")
    main(ap.parse_args().write_sheet)
