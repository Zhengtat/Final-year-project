"""CR-013 STOP 5: the final manifest, the final report's required statements, and the recorded check results (accessibility, cross-engine smoke, demo flow). Skipped when the generated
reports are absent."""

import json
from pathlib import Path

import pytest

R = Path("reports/cr013")
MAN = R / "final_trace_manifest.json"
FIN = R / "FINAL_EXPLAINABILITY.md"
pytestmark = pytest.mark.skipif(
    not (MAN.exists() and FIN.exists()), reason="final reports not generated"
)


def test_manifest_records_integrity_hashes_and_ids():
    m = json.loads(MAN.read_text())
    assert m["read_only_integrity"]["all_audited_source_artifacts_byte_identical"] is True
    assert m["source_run_ids"] == ["slice3_c2", "cr012_scinlp_heldout_P17_1058_grobid_E0"]
    for run in m["derived_traces"].values():
        assert (
            run["unchanged_during_build"]
            and run["unchanged_now_vs_build_time"]
            and all(run["unchanged_now_vs_stop1_audit"].values())
        )
        assert (
            run["source_artifact_hashes"] == run["source_hashes_after_build"]
            and run["derived_trace_hashes"]["trace_events.jsonl"]
            and run["two_builds_identical_trace_hash"] is True
        )
        assert all(len(h) == 64 for h in run["source_artifact_hashes"].values())
    assert (
        m["derived_traces"]["slice3_c2"]["replay"]["valid"] is True
        and m["derived_traces"]["slice3_c2"]["replay"]["deterministic"] is True
    )
    assert (
        m["overlay_frozen_inputs"]["unchanged"] is True
        and m["explorer"]["second_build_identical"] is True
    )
    assert len(m["cr013_code_combined_sha256"]) == 64 and any(
        k.startswith("src/cumap/explain/") for k in m["cr013_code_and_config_hashes"]
    )
    assert m["git"]["base_commit"] == "2e50b6538ab5a8c97c9df3a218ab70646af90695"


def test_final_report_contains_the_required_statements():
    t = FIN.read_text()
    for needle in (
        "CR-013 changes explainability/observability only; it makes no accuracy-improvement claim.",
        "gold-derived evaluation observations, not ground truth about why the system reasoned incorrectly",
        "earliest observed failure location, not an explanation of internal model intent",
        "RECORDED", "REPLAYED", "JOINED", "NOT_EVALUATED", "headless Chromium 153 only",
        "we do not claim compatibility with released Safari or Firefox versions", "Crowded labels",
        "NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION", "byte-identical",
    ):  # fmt: skip
        assert needle in t, needle
    u = (R / "usability_face_check.md").read_text()
    assert "NOT_EVALUATED" in u and "none were fabricated" in u
    assert (
        "ratings" not in (R / "usability_face_check.csv").read_text().split("\n")[1]
    )  # the sheet is blank (no responses)
    rows = (R / "usability_face_check.csv").read_text().splitlines()[1:]
    assert len(rows) == 10 and all(r.count(",,") >= 4 or r.endswith(",") for r in rows)


def test_recorded_check_results_are_clean():
    ax = json.loads((R / "checks/accessibility_performance.json").read_text())
    assert (
        all(len(v["violations"]) == 0 for v in ax["axe"].values())
        and ax["manual"]["buttons_without_accessible_name"] == 0
        and ax["manual"]["inputs_without_label"] == []
    )
    assert (
        ax["manual"]["zoom_200_no_horizontal_page_scroll"]
        and ax["perf"]["load_to_interactive_ms"] < 2000
    )
    xb = json.loads((R / "checks/cross_browser_smoke.json").read_text())
    for engine in ("firefox", "webkit"):
        assert (
            all(v is True for k, v in xb[engine].items() if isinstance(v, bool))
            and "EXCEPTION" not in xb[engine]
        )
    demo = json.loads((R / "checks/demo_and_task_feasibility.json").read_text())
    assert (
        demo["demo_all_steps_ok"]
        and len(demo["demo_steps"]) == 13
        and demo["all_tasks_completable"]
        and demo["page_errors"] == []
    )
    for f in ("browser_checks_production.json", "browser_checks_evaluation.json"):
        assert all(json.loads((R / "checks" / f).read_text()).values())
