"""CR-017: load frozen CR-012 P&D-E2E runs and evaluate them with the unified five-metric evaluator (no model call, nothing written into a source run).

uv run python -m cumap.cr017.run --tag heldout --level E0 --out reports/cr017/_scratch_E0.json"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr017 import headline as HL

ROOT = Path(".")
SHEETS = {
    "pilot": ("data/gold/pd_e2e_pilot_blind.csv", ["1.5", "2.6"]),
    "heldout": (
        "data/gold/pd_e2e_test_blind.csv",
        ["4.4", "4.5", "5.4", "6.3", "7.1", "8.2", "9.3"],
    ),
}


def run_ids(tag: str, level: str, sections: list[str]) -> dict[str, str]:
    return {sid: f"cr012_{tag}_{sid.replace('.', '_')}_{level}" for sid in sections}


def load_units(tag: str, level: str) -> tuple[dict[str, HL.UnitInput], set[str], list[Path], Path]:
    sheet, sections = SHEETS[tag]
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    reg = PD.registry()
    gold, problems = PD.load_gold(ROOT / sheet, secs, reg)
    assert not problems, problems[:2]
    sym = {r.name for r in reg.all_relations() if r.symmetric}
    units, paths = {}, []
    for sid, rid in run_ids(tag, level, sections).items():
        f = PG.run_path(rid) / "checkpoint.json"
        if not f.exists():
            continue
        cp = PG.load_run(rid)
        if not cp.get("relation_results_v3"):
            continue
        pg = PG.graph_for_sections(cp, {sid: secs[sid]})[sid]
        units[sid] = HL.UnitInput(
            gold[sid],
            pg["nodes"],
            pg["edges"],
            PG.proposed_pairs(cp, sid),
            HL.classifier_from_checkpoint(cp, sid),
        )
        paths.append(f)
    return units, sym, paths, ROOT / sheet


def evaluate_run(tag: str, level: str, boot: bool = True) -> dict:
    units, sym, paths, gold_path = load_units(tag, level)
    out = HL.evaluate(units, sym, boot=boot)
    out |= {
        "schema_version": "cr017-v1",
        "run_id": f"cr012_{tag}_*_{level}",
        "benchmark": "P&D-E2E (canonical graph)",
        "sections": sorted(units),
        "prediction_artifact": [str(p) for p in paths],
        "gold_artifact": str(gold_path),
        "scorer_version": "cr017-1",
        "provenance": HL.provenance(paths, gold_path),
    }
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="heldout")
    ap.add_argument("--level", default="E0")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = evaluate_run(a.tag, a.level)
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=1, default=str))
    h = r["headline"]
    print({k: (v.get("f1") if "f1" in v else v.get("recall")) for k, v in h.items()})
