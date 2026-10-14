"""CR-017 STOP 6: the five metric definitions are frozen (code and config hashes pinned) and the headline values are reproducible from the
machine-readable outputs alone (pooled per-section counts equal the headline counts)."""

import hashlib
import json
from pathlib import Path

import pytest

FROZEN = {
    "src/cumap/cr017/headline.py": "f335336a475b32158dc7c8708c48de0752705f0bf428854cec2edaf6f0135d18",
    "src/cumap/cr017/hierarchy.py": "b1523a34fe369a253532385dad15d3751c343f88ffd211f27b6ecf5d72d06d95",
    "configs/cr017_eval.yaml": "41100298d0e2c31e863f027a8bb9c5bccfad7e0fcb7bd4451ec595aeffc85105",
}


@pytest.mark.parametrize("path", sorted(FROZEN))
def test_metric_definitions_are_frozen(path):
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == FROZEN[path]


def test_headline_counts_are_reproducible_from_the_per_section_diagnostics():
    hm = json.loads(Path("reports/cr017/headline_metrics.json").read_text())
    dg = json.loads(Path("reports/cr017/diagnostics.json").read_text())
    for lv, r in hm["pd"]["heldout"].items():
        h, ps = r["headline"], dg["pd"]["heldout"][lv]["per_section"]
        for key, sec in (
            ("strict_e2e_edge_f1", "strict"),
            ("concept_f1", "concept"),
            ("ancestor_hierarchy_f1", "hierarchy"),
        ):
            got = [sum(v[sec][k] for v in ps.values()) for k in ("tp", "fp", "fn")]
            assert got == [h[key][k] for k in ("tp", "fp", "fn")], (lv, key)
        reached = sum(v["pair_recall"][0] for v in ps.values())
        denom = sum(v["pair_recall"][1] for v in ps.values())
        assert (reached, denom) == (h["pair_recall"]["reached"], h["pair_recall"]["denominator"])


def test_frozen_cr012_values_are_reproduced_exactly():
    hm = json.loads(Path("reports/cr017/headline_metrics.json").read_text())
    fz = json.loads(Path("reports/cr012/stop4_heldout_results.json").read_text())["pd"]["levels"]
    for lv, r in hm["pd"]["heldout"].items():
        assert all(x["match"] for x in r["frozen_compat"].values()), lv
        assert r["headline"]["strict_e2e_edge_f1"]["f1"] == fz[lv]["pooled_strict_e2e"]["f1"]
    assert hm["meta"]["model_calls"] == 0 and hm["meta"]["frozen_artifacts_changed"] == []
