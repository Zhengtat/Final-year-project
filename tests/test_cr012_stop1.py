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
        if f.parts[2] == "cr021" and f.name in {"review.py", "adjudicator.py", "rebuild_report.py"}:
            continue  # CR-021 owner review sheet: reads retained runs, writes a local draft, builds no prompt
        if f.parts[2] == "cr025":
            continue  # CR-025 model comparison: launches the existing SciNLP dev runner per model and scores retained runs (dev split only)
        if f.parts[2] == "cr022":
            continue  # CR-022 Part A: rescoring of retained SciNLP runs and a mapping helper (no prompt, no model call)
        if f.parts[2] == "cr040":
            continue  # CR-040: renders a registry wording review sheet from config files (no prompt, no model call)
        if f.parts[2] == "cr033":
            continue  # CR-033: fact-F1 scorer / report over retained runs (no prompt, no model call)
        if f.parts[2] == "cr032":
            continue  # CR-032: scorer / report over retained runs and a blind owner sheet (no prompt, no model call)
        if f.parts[2] == "cr031":
            continue  # CR-031: read-only rescoring of retained SciNLP oracle runs (no prompt, no model call)
        if f.parts[2] == "cr020":
            continue  # CR-020 dev experiment runner and scorer (SciNLP dev split only, no test-split run)
        if f.parts[2] == "cr057":
            continue  # CR-057: the frozen SciNLP runner with profile v6 (train / dev only; no new prompt)
        if f.parts[2] == "cr056":
            continue  # CR-056: the frozen SciNLP runner with profile v5 and read-only rescoring of train / dev runs (no new prompt, no test split)
        if f.parts[2] == "cr063":
            continue  # CR-063: a grounding variant and its $0 measurement over retained train / dev runs (no prompt, no model call)
        if f.parts[2] == "cr062":
            continue  # CR-062: $0 sizing of domain-free verifier rules over retained train / dev runs (no prompt, no model call)
        if f.parts[2] == "cr060":
            continue  # CR-060: the SciNLP runner with profile v10 (an assembly alias rule) and a $0 noun-phrase hint sizing (first-set train / dev papers only, no test split)
        if f.parts[2] == "cr059":
            continue  # CR-059 DRAFT: the SciNLP runner with profile v7 and the profile drafter (train-paper text only, no gold, no test split)
        if f.parts[2] == "cr058":
            continue  # CR-058: read-only diagnostics page over retained runs (no prompt, no model call); test runs read for reporting only, as CR-031
        if f.parts[2] == "cr055":
            continue  # CR-055: the frozen SciNLP runner with profile v4 (train / dev only; prompt v6_scinlp holds no SciNLP test material)
        if f.parts[2] == "cr054":
            continue  # CR-054: read-only trace of retained train / dev runs (no prompt, no model call)
        if f.parts[2] == "cr053":
            continue  # CR-053: the frozen SciNLP runner with profile v3 (generator prompt v5_scinlp, train / dev only; the prompt holds no SciNLP test material)
        if f.parts[2] == "cr052":
            continue  # CR-052: read-only span analysis and rescoring of retained train / dev runs (no prompt, no model call)
        if f.parts[2] == "cr051":
            continue  # CR-051: re-scores the adopted adjudicator on the CR-050 owner sheet (train / dev rows only; no new prompt)
        if f.parts[2] == "cr050":
            continue  # CR-050: builds a local blind owner sheet from retained train / dev runs (no prompt, no model call, no test split)
        if f.parts[2] == "cr049":
            continue  # CR-049: identity-judge measurement over the CR-021 sheet rows (SciNLP test rows left out; the prompt has no SciNLP text)
        if f.parts[2] == "cr047":
            continue  # CR-047: the frozen SciNLP runner with profile v2, and a relation-only check on train / dev papers (no new prompt, no test split)
        if f.parts[2] == "cr043":
            continue  # CR-043: launches the existing SciNLP runner on train / dev papers and scores retained runs (no prompt, no test split)
        if f.parts[2] == "cr019" and f.name in {
            "run.py",
            "variants.py",
            "stage_b.py",
            "stage_b_score.py",
        }:
            continue  # CR-019 evaluation code: rescoring (no model) and the Stage B dev-split runner (like cr012/scinlp_run, test split
            # locked by split_allowed); the gold-free occurrence index stays guarded
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
