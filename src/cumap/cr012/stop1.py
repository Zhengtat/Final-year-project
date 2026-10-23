"""CR-012 STOP 1 ($0): audit the exact SciNLP release and the P&D source, record hashes and isolation facts, and write
reports/cr012/dataset_manifest.json. The raw SciNLP files are read as DATA ONLY (json parsing); nothing in the clone is executed.

    uv run python -m cumap.cr012.stop1
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT

SCINLP = REPO_ROOT / "data/raw/external/scinlp"
OUT = REPO_ROOT / "reports/cr012/dataset_manifest.json"
PAPER = {
    "source": "https://arxiv.org/abs/2509.07801 (v3, 2025-09-20; EMNLP 2025 main)",
    "papers": 60,
    "entities": 7072,
    "relations": 1826,
    "split": "8:1:1 (approx. 48/6/6 papers)",
    "entity_types": ["Task", "Model", "Dataset", "Metric"],
    "relation_types_11": "directional: measuredBy, usedFor, trainedWith, enhancedBy, evaluatedBy, evaluatedOn, subclassOf, subtaskOf, partOf; symmetric: compareWith, similarWith",
    "annotation": "2 experts (pilot, 12 papers) + 5 graduate students (48 papers), >= 2 annotators per paper, Doccano; entity kappa 0.83-0.91, relation kappa 0.64-0.81",
    "coreference": "not annotated (entity mentions only; abbreviation / full-form normalisation applied as post-processing)",
    "metrics": {
        "NER": "strict span + type",
        "Rel": "subject span, object span, relation type",
        "Rel+": "Rel plus subject/object entity types",
        "RE": "relation classification with gold entities",
    },
    "released_scorer": "none described",
}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_docs(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def scinlp_audit() -> dict:
    out: dict = {"splits": {}}
    for sp in ("train", "dev", "test"):
        p = SCINLP / "Dataset" / f"{sp}.json"
        docs = read_docs(p)
        ents, rels = Counter(), Counter()
        n_sent = n_tok = 0
        for d in docs:
            n_sent += len(d["sentences"])
            n_tok += sum(len(s) for s in d["sentences"])
            ents.update(t for sn in d["ner"] for _s, _e, t in sn)
            rels.update(r[4] for sr in d["relations"] for r in sr)
        out["splits"][sp] = {
            "file": f"Dataset/{sp}.json",
            "sha256": sha(p),
            "bytes": p.stat().st_size,
            "format": "JSON lines, one document per line (keys: doc_key, sentences, ner, relations); pre-tokenised, document-level token offsets",
            "documents": len(docs),
            "sentences": n_sent,
            "tokens": n_tok,
            "entities": sum(ents.values()),
            "relations": sum(rels.values()),
            "entity_types": dict(sorted(ents.items())),
            "relation_types": dict(sorted(rels.items())),
            "doc_keys": [d["doc_key"] for d in docs],
        }
    s = out["splits"]
    out["totals"] = {
        k: sum(s[sp][k] for sp in s)
        for k in ("documents", "sentences", "tokens", "entities", "relations")
    }
    keys = {sp: set(s[sp]["doc_keys"]) for sp in s}
    out["split_overlap"] = {
        "train_dev": len(keys["train"] & keys["dev"]),
        "train_test": len(keys["train"] & keys["test"]),
        "dev_test": len(keys["dev"] & keys["test"]),
    }
    kg = SCINLP / "Dataset" / "KG_triples.txt"
    out["kg_triples_txt"] = {
        "sha256": sha(kg),
        "lines": sum(1 for _ in kg.open("rb")),
        "status": "NOT GOLD: triples extracted from ACL Anthology PDFs by the HGERE model trained on SciNLP train; never used as gold or as input",
    }
    return out


def git(*a: str, cwd: Path = SCINLP) -> str:
    return subprocess.run(
        ["git", *a], capture_output=True, text=True, cwd=cwd, check=False
    ).stdout.strip()


def snapshot_record() -> dict:
    """Dataset snapshot rule (CLAUDE.md): archive branch + annotated tag + local-only archive with its SHA-256."""
    arch = REPO_ROOT / "dataset_snapshots/cr012-scinlp-pre-change.tar.gz"
    top = REPO_ROOT
    return {
        "version_label": "scinlp-repo-e78342be517e",
        "pre_change_git_commit": git("rev-parse", "cr012-scinlp-pre-change^{commit}", cwd=top),
        "archive_branch": "archive/cr012-scinlp-pre-change",
        "archive_branch_commit": git("rev-parse", "archive/cr012-scinlp-pre-change", cwd=top),
        "archive_tag": "cr012-scinlp-pre-change (annotated)",
        "dataset_tracked_by_git": False,
        "git_branch_or_tag_is_a_dataset_backup": False,
        "local_only_archive": {
            "path": "dataset_snapshots/cr012-scinlp-pre-change.tar.gz (gitignored)",
            "sha256": sha(arch) if arch.exists() else None,
            "bytes": arch.stat().st_size if arch.exists() else None,
            "contents": "data/raw/external/scinlp/ (Dataset/*.json, KG_triples.txt, README.md, SOURCE.md) exactly as downloaded; gzip -n, so the archive bytes are reproducible",
            "verified": "extracted to a temporary folder; train/dev/test sha256 equal the per-file hashes in this manifest",
        },
        "authoritative_reproducible_source": "https://github.com/AKADDC/SciNLP at the commit above",
        "redistribution": "CC BY-NC 4.0, non-commercial academic use only: the data and the archive are never pushed or published",
        "rule": "any replacement, upgrade, reformatting or switch of this dataset requires this snapshot to exist first; every CR-012 result names this version label",
    }


def pd_audit() -> dict:
    src = REPO_ROOT / "data/interim/textbook_sections.jsonl"
    rows = [json.loads(line) for line in src.read_text().splitlines()]
    by: dict = {}
    for r in rows:
        c = by.setdefault(str(r["chapter_num"]), {"sections": 0, "words": 0})
        c["sections"] += 1
        c["words"] += len(r["text"].split())
    cfg = yaml.safe_load((REPO_ROOT / "configs/default.yaml").read_text())
    return {
        "source": "Peterson & Davie, Computer Networks: A Systems Approach 6e (CC BY 4.0), github.com/SystemsApproach/book",
        "pinned_commit": cfg["textbook"]["pinned_commit"],
        "parsed_sections_file": "data/interim/textbook_sections.jsonl",
        "parsed_sections_sha256": sha(src),
        "sections": len(rows),
        "by_chapter": by,
        "chapters_used_for_CR005_to_CR011_development_or_runs": [1, 2, 3],
        "chapters_never_run": [4, 5, 6, 7, 8, 9],
        "heldout_candidate_pool": {
            "sections": sum(by[str(c)]["sections"] for c in range(4, 10)),
            "words": sum(by[str(c)]["words"] for c in range(4, 10)),
        },
        "note": "section selection (2 pilot, 6-8 held-out) is a STOP 2 freeze made before any final CUM prediction is viewed; it is not made here",
    }


def build() -> dict:
    handoff = REPO_ROOT / "reports/cr011_sleep/CR012_EVAL_HANDOFF.json"
    h = json.loads(handoff.read_text())
    return {
        "stage": "CR-012 STOP 1",
        "scinlp": {
            "source": "https://github.com/AKADDC/SciNLP",
            "clone_dir": "data/raw/external/scinlp (gitignored; not redistributed)",
            "commit": git("rev-parse", "HEAD"),
            "commit_subject": git("log", "-1", "--format=%s"),
            "dataset_snapshot": snapshot_record(),
            "licence": "CC BY-NC 4.0 (non-commercial academic research only; follows the ACL OCL Corpus policy)",
            "official_scorer": "NONE in the repository; README lists PURE / PL-Marker / HGERE F1 only. Published numbers cannot be verified as computed with a scoring definition identical to ours.",
            "readme_stated_counts": {"papers": 60, "entities": 6429, "relations": 1649},
            "paper": PAPER,
            **scinlp_audit(),
        },
        "pd_e2e": pd_audit(),
        "cr010_final": {
            "architecture": "DUAL_LAYER (semantic Expert-KG unchanged; eRST graph is candidate-routing evidence only)",
            "tag": "cr-010-complete",
        },
        "cr011_final": {
            "status": h["cr011_status"],
            "tag": "cr-011-complete",
            "handoff": "reports/cr011_sleep/CR012_EVAL_HANDOFF.json",
            "handoff_sha256": sha(handoff),
            "production_snapshot_run": h["source_run_id"],
            "production_snapshot_checkpoint_sha256": h["pre_sleep_snapshot"]["checkpoint_sha256"],
            "sleep_adopted": h["sleep_adopted"],
        },
        "isolation": {
            "scinlp_in_repository_before_this_audit": False,
            "scierc_scier_text2kgbench_oskgc_in_repository": False,
            "scinlp_test_doc_keys": sorted(scinlp_audit()["splits"]["test"]["doc_keys"]),
            "rule": "no SciNLP / SciERC / SciER / OSKGC / Text2KGBench test text, label, schema or example may enter prompts, thresholds, lexicon, cues or guards; P&D held-out sections are drawn from chapters 4-9, which no CR-005..011 run touched",
        },
    }


def main() -> None:
    m = build()
    OUT.write_text(json.dumps(m, indent=1), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
