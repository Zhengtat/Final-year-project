"""CR-018 STOP 1 ($0, no model call): repeat the fresh-section contamination audit across every earlier CR and report data exposure.

A candidate section is 'untouched' only if (1) three 70-character snippets of its text occur in no logged prompt, (2) it is in no gold sheet, (3) it is in no CR-016 corpus/query file,
(4) no saved output (data/processed, reports) is keyed by its id. Read-only.

uv run python -m cumap.cr018.stop1_audit"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(".")
OUT = ROOT / "reports/cr018"
CANDIDATES = ["4.3", "5.1", "5.2", "6.2", "6.5", "8.1", "9.1", "9.4"]
norm = lambda s: " ".join(s.lower().split())


def section_texts() -> dict[str, dict]:
    rows = [
        json.loads(x)
        for x in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines()
    ]
    return {r["section_id"]: r for r in rows}


def snippets(text: str) -> list[str]:
    t = norm(text)
    n = len(t)
    return [t[int(n * f) : int(n * f) + 70] for f in (0.15, 0.5, 0.85)]


def prompt_hits(snips: dict[str, list[str]]) -> dict[str, int]:
    hits = dict.fromkeys(snips, 0)
    flat = [(sid, s) for sid, ss in snips.items() for s in ss]
    n = 0
    with (ROOT / "data/logs/llm_prompts.jsonl").open() as f:
        for line in f:
            n += 1
            low = norm(line)
            for sid, s in flat:
                if s in low:
                    hits[sid] += 1
    hits["_prompts_scanned"] = n
    return hits


def gold_sections() -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}
    for p in sorted((ROOT / "data/gold").glob("*.csv")):
        with p.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                sid = r.get("section_id")
                if sid:
                    out.setdefault(p.name, set()).add(sid)
    return {k: sorted(v) for k, v in out.items()}


def cr016_sections() -> dict[str, list[str]]:
    d = ROOT / "data/processed/cr016/stage2"
    res = {}
    for name in ("corpus.jsonl", "queries.jsonl"):
        p = d / name
        if p.exists():
            res[name] = sorted(
                {
                    json.loads(x).get("section") or json.loads(x).get("section_id")
                    for x in p.read_text().splitlines()
                }
                - {None}
            )
    return res


def filename_hits(ids: list[str]) -> dict[str, list[str]]:
    pats = {
        sid: re.compile(rf"(?<![\d.]){sid.split('.')[0]}[._]{sid.split('.')[1]}(?![\d])")
        for sid in ids
    }
    hits: dict[str, list[str]] = {sid: [] for sid in ids}
    for base in ("data/processed", "data/interim", "reports"):
        for p in (ROOT / base).rglob("*"):
            if p.is_file() or p.is_dir():
                for sid, rx in pats.items():
                    if rx.search(p.name):
                        hits[sid].append(str(p))
    return hits


def main() -> dict:
    secs = section_texts()
    snips = {sid: snippets(secs[sid]["text"]) for sid in CANDIDATES}
    res = {
        "candidates": {sid: secs[sid]["word_count"] for sid in CANDIDATES},
        "prompt_snippet_hits": prompt_hits(snips),
        "gold_sheets_naming_candidates": {
            k: sorted(set(v) & set(CANDIDATES))
            for k, v in gold_sections().items()
            if set(v) & set(CANDIDATES)
        },
        "cr016_corpus_query_sections": cr016_sections(),
        "filename_hits": filename_hits(CANDIDATES),
    }
    res["cr016_candidate_overlap"] = {
        k: sorted(set(v) & set(CANDIDATES)) for k, v in res["cr016_corpus_query_sections"].items()
    }
    (OUT / "contamination_audit.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
