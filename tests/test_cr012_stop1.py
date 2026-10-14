"""CR-012 STOP 1: the dataset manifest records the facts the audit relies on and keeps the isolation rules explicit."""

import json
from pathlib import Path

M = json.loads(Path("reports/cr012/dataset_manifest.json").read_text())


def test_scinlp_release_is_pinned_and_split_is_disjoint():
    s = M["scinlp"]
    assert len(s["commit"]) == 40 and s["totals"]["documents"] == 60
    assert s["split_overlap"] == {"train_dev": 0, "train_test": 0, "dev_test": 0}
    assert sum(sp["documents"] for sp in s["splits"].values()) == 60
    assert s["splits"]["test"]["documents"] == 3  # the fact behind decision D1
    assert all(len(sp["sha256"]) == 64 for sp in s["splits"].values())


def test_repository_counts_and_paper_counts_are_both_recorded():
    s = M["scinlp"]
    assert (s["totals"]["entities"], s["totals"]["relations"]) == (6429, 1649)
    assert (s["paper"]["entities"], s["paper"]["relations"]) == (7072, 1826)
    assert s["official_scorer"].startswith("NONE")
    assert "NOT GOLD" in s["kg_triples_txt"]["status"]


def test_baseline_is_the_unchanged_cr011_snapshot_and_heldout_pool_excludes_tuned_chapters():
    assert M["cr011_final"]["sleep_adopted"] is False
    assert M["cr011_final"]["production_snapshot_run"] == "slice3_c2"
    pd = M["pd_e2e"]
    assert (
        pd["chapters_never_run"] == [4, 5, 6, 7, 8, 9]
        and 1 in pd["chapters_used_for_CR005_to_CR011_development_or_runs"]
    )
    assert M["isolation"]["scinlp_in_repository_before_this_audit"] is False


def test_no_pipeline_module_reads_scinlp_text_into_prompts():
    for f in Path("src/cumap").rglob("*.py"):
        if f.parts[2] in {"cr012", "cr017", "explain"} or f.name == "kg_explorer.py":
            continue  # evaluation code (CR-017 replay scores frozen outputs only) and read-only reporting / explainability modules (they never build prompts or call a model)
        assert "scinlp" not in f.read_text().lower(), f


def test_scinlp_snapshot_record_follows_the_snapshot_rule():
    snap = M["scinlp"]["dataset_snapshot"]
    assert (
        snap["archive_branch"] == "archive/cr012-scinlp-pre-change"
        and snap["dataset_tracked_by_git"] is False
    )
    assert snap["git_branch_or_tag_is_a_dataset_backup"] is False
    assert (
        len(snap["local_only_archive"]["sha256"]) == 64 and "never pushed" in snap["redistribution"]
    )
    assert snap["pre_change_git_commit"] == snap["archive_branch_commit"]
