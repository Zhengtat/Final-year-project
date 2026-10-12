"""CR-014 STOP 4 isolation: the held-out prediction path cannot read gold and refuses to run unfrozen."""

import subprocess
import sys
from pathlib import Path

PRED_MODULES = ["union", "proposal", "llm_stage", "v3_core", "heldout_run"]
FORBIDDEN_TEXT = ["data/gold", "pilot_score", "face_scorer", "load_gold", "GoldConcept", "nodes_exp", "stage_b_eval", "split_data"]


def test_prediction_modules_do_not_reference_gold_or_scorers():
    for m in PRED_MODULES:
        src = Path(f"src/cumap/cr014/{m}.py").read_text()
        body = src.split('"""', 2)[2] if src.startswith('"""') else src  # docstring may describe the guard
        hits = [f for f in FORBIDDEN_TEXT if f in body and not (m == "heldout_run" and f == "data/gold")]
        assert not hits, (m, hits)


def test_prediction_process_never_imports_scoring_or_gold_loaders():
    code = (
        "import sys; import cumap.cr014.heldout_run as h; import cumap.cr014.v3_core, cumap.cr014.union, cumap.cr014.llm_stage;"
        "bad=[m for m in sys.modules if m in ('cumap.cr014.pilot_score','cumap.cr014.stage_b','cumap.cr014.stage_b_eval','cumap.cr014.pilot_run','cumap.cr010.nodes_exp')];"
        "print(bad)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]", out


def test_audit_hook_blocks_gold_opens():
    code = (
        "import cumap.cr014.heldout_run as h; h.install_gold_guard();"
        "import sys\n"
        "try:\n open('data/gold/pd_concept_pilot_blind.csv')\n print('OPENED')\n"
        "except PermissionError as e:\n print('BLOCKED')\n"
        "except FileNotFoundError:\n print('NOTFOUND')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()
    assert out == "BLOCKED", out


def test_run_refuses_without_freeze_or_gold_manifest(monkeypatch, tmp_path):
    import cumap.cr014.heldout_run as h

    monkeypatch.setattr(h, "FREEZE", tmp_path / "none.json")
    try:
        h.check_preconditions()
        raise AssertionError("should refuse")
    except SystemExit as e:
        assert "not frozen" in str(e)
