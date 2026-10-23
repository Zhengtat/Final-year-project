"""CR-042: the CR-032 report shows the real-identity SciNLP Hierarchy F1 once the owner's scoped sheet exists (no network)."""

import copy
import json

from cumap.config import REPO_ROOT
from cumap.cr032 import report

RES = json.loads((REPO_ROOT / "reports/cr032/hier_t1.json").read_text(encoding="utf-8"))


def test_real_identity_column_is_rendered_when_marks_are_present():
    md = report.markdown(RES)
    assert "`HIER-T1` real identity P / R / F1" in md
    if RES["real_identity_marks"] == "present":
        assert "real identity comes from the owner's scoped sheet" in md
        assert "waits for the owner's scoped identity sheet" not in md


def test_without_marks_the_report_says_it_is_waiting():
    r = copy.deepcopy(RES)
    r["real_identity_marks"] = "AWAITING_OWNER_IDENTITY_SHEET"
    for s in r["scinlp"].values():
        for e in s["variants"].values():
            e["HIER_T1_real_identity"] = "AWAITING_OWNER_IDENTITY_SHEET"
    md = report.markdown(r)
    assert "waits for the owner's scoped identity sheet" in md
    assert "AWAITING_OWNER_IDENTITY_SHEET" in md
