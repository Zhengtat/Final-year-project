"""CR-031: oracle ladder report (fixture-driven; the frozen-number gate runs only when the local runs exist)."""

import json
from pathlib import Path

import pytest

from cumap.config import REPO_ROOT
from cumap.cr012.types import PRF
from cumap.cr031 import oracle_ladder as OL


def _fixture(tmp_path):
    keys = ["d1", "d2"]
    paths = {}
    for k in keys:
        for lv in OL.LEVELS:
            rid = OL.sc_run_id(k, lv)
            p = tmp_path / rid
            p.mkdir()
            (p / "checkpoint.json").write_text(json.dumps({"id": rid}))
            paths[rid] = p

    def score(doc, gold, cp, sym, variant):
        tp = 2 if variant != "FROZEN" else 1
        return {
            "scores": {"rel": PRF(tp, 1, 1), "entity_strict": PRF(3, 1, 0)},
            "pred": None,
            "edges": {"predicted": 4, "unplaced": 1},
        }

    return keys, paths, score


def test_ladder_aggregates_codes_and_flags_unchanged_sources(tmp_path):
    keys, paths, score = _fixture(tmp_path)
    res = OL.ladder(
        keys,
        ("E0", "E1"),
        ("FROZEN", "IDX-P1"),
        docs={k: k for k in keys},
        gold_all={k: k for k in keys},
        sym=set(),
        load_run=lambda rid: json.loads((paths[rid] / "checkpoint.json").read_text()),
        run_path=lambda rid: paths[rid],
        score=score,
        attribution=lambda *a: ["N0", None, "P0"],
    )
    r = res["E0/IDX-P1"]
    assert r["rel"]["tp"] == 4 and r["predicted_edges"] == 8 and r["unplaced_edges"] == 2
    assert r["earliest_failure"] == {"N0": 2, "recovered": 2, "P0": 2}
    assert res["E0/FROZEN"]["rel"]["tp"] == 2 and res["sources_unchanged"] is True
    md = OL.render_md(res, ("E0", "E1"))
    assert "FROZEN" in md and "right fact, not credited" in md and "True" in md
    assert json.dumps(OL.to_jsonable(res))  # serialisable


def test_ladder_detects_a_changed_source(tmp_path):
    keys, paths, score = _fixture(tmp_path)

    def mutating_score(*a):
        (paths[OL.sc_run_id("d1", "E0")] / "checkpoint.json").write_text("changed")
        return score(*a)

    res = OL.ladder(
        keys, ("E0",), ("FROZEN",), docs={k: k for k in keys}, gold_all={k: k for k in keys},
        sym=set(), load_run=lambda rid: {}, run_path=lambda rid: paths[rid],
        score=mutating_score, attribution=lambda *a: [],
    )  # fmt: skip
    assert res["sources_unchanged"] is False


ACCEPT = {  # handoff Appendix A
    "E0": {"FROZEN": 0.050, "IDX-P1": 0.195, "IDXR1-P1": 0.195, "IDX-P3": 0.332},
    "E1": {"FROZEN": 0.255, "IDX-P1": 0.236, "IDXR1-P1": 0.236, "IDX-P3": 0.427},
    "E3": {"FROZEN": 0.463, "IDX-P1": 0.433, "IDXR1-P1": 0.432, "IDX-P3": 0.574},
    "E4": {"FROZEN": 0.473, "IDX-P1": 0.462, "IDXR1-P1": 0.462, "IDX-P3": 0.617},
}


@pytest.mark.skipif(
    not Path(REPO_ROOT / "data/processed/kg/cr012_scinlp_heldout_P17_1058_grobid_E4").exists(),
    reason="local frozen SciNLP runs not present",
)
def test_frozen_numbers_reproduce_and_the_acceptance_table_holds():
    res = OL.ladder()
    assert res["sources_unchanged"] is True
    for lv, row in ACCEPT.items():
        for v, f1 in row.items():
            assert round(res[f"{lv}/{v}"]["rel"]["f1"], 3) == f1, (lv, v)
    assert res["E0/IDX-P1"]["earliest_failure"]["P0"] == 67
    sa = json.loads((REPO_ROOT / "reports/cr019/stage_a.json").read_text())["stage_a"]["scinlp"]
    for v in ("FROZEN", "IDX-P1", "IDX-P3"):
        assert res[f"E0/{v}"]["rel"]["f1"] == pytest.approx(
            sa[v]["strict_relation"]["f1"], abs=1e-12
        )
        assert res[f"E0/{v}"]["entity_strict"]["f1"] == pytest.approx(
            sa[v]["concept_f1_entity_strict"]["f1"], abs=1e-12
        )
