"""CR-017 STOP 5: the scorecard (markdown, payload and explorer page) is rendered from the machine-readable replay outputs only, shows exactly five
headline metrics, keeps diagnostics / audit / organisation separate and never shows organisation metrics as accuracy."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from cumap.cr017 import scorecard as SCR

HM = Path("reports/cr017/headline_metrics.json")
pytestmark = pytest.mark.skipif(not HM.exists(), reason="replay outputs absent")
KEYS = [k for k, _, _ in SCR.METRICS]


def test_payload_has_exactly_five_headline_cards_equal_to_the_json():
    hm, p = json.loads(HM.read_text()), SCR.build_scorecard()
    assert p["meta"]["composite_score"] is False
    for tag in ("heldout", "pilot"):
        for lv, r in p["datasets"][f"pd_{tag}"]["levels"].items():
            assert [c["key"] for c in r["headline"]] == KEYS
            src = hm["pd"][tag][lv]["headline"]
            for c, (k, _, f) in zip(r["headline"], SCR.METRICS, strict=True):
                if src[k].get("status") == "NOT_EVALUABLE":
                    assert c["value"] is None and c["status"] == "NOT_EVALUABLE"
                else:
                    assert c["value"] == src[k][f]
    for lv, r in p["datasets"]["scinlp"]["levels"].items():
        assert [c["key"] for c in r["headline"]] == KEYS
        by = {c["key"]: c for c in r["headline"]}
        assert (
            by["ancestor_hierarchy_f1"]["value"] is None
            and by["relation_macro_f1"]["value"] is None
        )
        assert (
            by["concept_f1"]["analogue"]
            and by["concept_f1"]["value"] == hm["scinlp"][lv]["concept_f1"]["f1"]
        )


def test_markdown_values_reproduce_the_json_and_keep_levels_separate():
    p = SCR.build_scorecard()
    md = SCR.render_markdown(p)
    heads = [m.start() for m in re.finditer(r"^## ", md, re.MULTILINE)]
    titles = re.findall(r"^## (.*)$", md, re.MULTILINE)
    assert titles[0].startswith("HEADLINE") and titles[1].startswith("DIAGNOSTICS")
    assert titles[2] == "AUDIT" and titles[3].startswith("ORGANISATION") and len(heads) == 4
    headline_part = md.split("## DIAGNOSTICS")[0]
    for r in p["datasets"]["pd_heldout"]["levels"].values():
        for c in r["headline"]:
            assert f"{c['value']:.3f}" in headline_part
    assert "0.643 [0.589, 0.698]†" in headline_part and "0.484" in headline_part
    assert "⚠" in headline_part  # Relation Macro low-support warning
    for word in ("modularity", "PageRank", "rings"):
        assert word not in headline_part and word in md.split("## ORGANISATION")[1]
    pilot = md.split("### P&D-E2E pilot")[1].split("### SciNLP")[0]
    assert "[" not in pilot  # no intervals over 1-2 sections


def test_rendered_report_on_disk_is_current():
    SCR.main()
    assert Path("reports/cr017/scorecard.md").read_text() == SCR.render_markdown(
        SCR.build_scorecard()
    )


@pytest.fixture(scope="module")
def page_out(tmp_path_factory):
    if (
        shutil.which("node") is None
        or not Path(
            "data/processed/kg/cr012_scinlp_heldout_P17_1058_grobid_E0/checkpoint.json"
        ).exists()
    ):
        pytest.skip("node or source runs absent")
    from cumap.report.kg_explorer import build

    root = tmp_path_factory.mktemp("scorecard")
    html = build(root / "index.html")
    out = root / "out.json"
    subprocess.run(
        ["node", "tests/js/scorecard_harness.js", str(html), str(out)], check=True, timeout=600
    )
    return json.loads(out.read_text())


def test_page_renders_the_scorecard_for_every_dataset_level_and_view(page_out):
    r = page_out
    assert "fatal" not in r and r["errors"] == []
    assert r["entry_tab"] == "evscore" and "Scorecard" in r["tabs"]
    p = SCR.build_scorecard()
    n = sum(len(d["levels"]) for d in p["datasets"].values())
    assert len(r["renders"]) == 2 * n
    assert r["after_leaving_has_scorecard"] is False


def test_page_separates_headline_diagnostics_audit_organisation_and_matches_values(page_out):
    h = page_out["renders"]["review|pd_heldout|E0"]
    pos = [h.index(x) for x in ("HEADLINE", "DIAGNOSTICS", "AUDIT", "ORGANISATION")]
    assert pos == sorted(pos)
    head = h[pos[0] : pos[1]]
    assert head.count('class="card sccard"') == 5
    for needle in ("0.643", "0.114", "0.163", "0.484", "0.053", "low support"):
        assert needle in head, needle
    assert "modularity" not in head and "no composite score" in head
    assert "not accuracy" in h[pos[3] :]
    assert "excluded (no gold)" in h and "<details" in h
    sc = page_out["renders"]["review|scinlp|E0"]
    assert "mention-level analogue" in sc and "NOT_EVALUABLE" in sc and "NOT_COMPUTED" in sc
