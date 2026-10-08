"""CR-011 closure: the no-op CR-012 handoff has the required state and, where the local run data exists, every hash resolves."""

import json
from pathlib import Path

import pytest

from cumap.sleep import closure as CL

HANDOFF = Path("reports/cr011_sleep/CR012_EVAL_HANDOFF.json")


def test_handoff_records_a_no_op_closure():
    assert CL.validate(HANDOFF, check_files=False) == []
    h = json.loads(HANDOFF.read_text())
    assert h["sleep_adopted"] is False and h["automatic_merge_enabled"] is False
    assert (
        h["merge_transactions"] == []
        and h["edge_rewrites"] == []
        and h["id_map_status"] == "identity_no_change"
    )
    assert (
        h["post_sleep_snapshot"]["checkpoint_sha256"]
        == h["pre_sleep_snapshot"]["checkpoint_sha256"]
    )


def test_handoff_validator_rejects_a_faked_migration(tmp_path):
    h = json.loads(HANDOFF.read_text())
    h["sleep_adopted"] = True
    h["post_sleep_snapshot"]["checkpoint_sha256"] = "0" * 64
    bad = tmp_path / "h.json"
    bad.write_text(json.dumps(h))
    problems = CL.validate(bad, check_files=False)
    assert any("sleep_adopted" in p for p in problems) and any(
        "same snapshot" in p for p in problems
    )


def test_handoff_hashes_resolve_when_the_run_data_is_present():
    if not (Path("data/processed/kg") / CL.RUN / "checkpoint.json").exists():
        pytest.skip("run data is not in this checkout (gitignored)")
    assert CL.validate(HANDOFF, check_files=True) == []
