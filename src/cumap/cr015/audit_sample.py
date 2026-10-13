"""CR-015: sample ~120 overlap families from the exposed development sections for a BLIND human boundary audit.

Stratified by the (model-generated) gold's pattern in the family's first run occurrence, never by any model decision: nested pair kept / only the longest span / only a shorter span / none.
The human sheet shows the sentence and the candidate spans only: no gold, no selector output, no verifier verdict. The key (hidden) is written under data/processed/.
    uv run python -m cumap.cr015.audit_sample"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path

from cumap.cr014.llm_stage import mark
from cumap.cr015 import placement as PL
from cumap.cr015.dev_data import load_dev
from cumap.cr015.stage_a import unions

ROOT = Path(".")
SEED = "cr015-boundary-audit-v1"
PER_STRATUM = 30
OUT = ROOT / "data/interim/checks/cr015"
KEY = ROOT / "data/processed/cr015/boundary_audit_key.csv"


def main() -> dict:
    dev = load_dev()
    us = unions(dev)
    by_stratum: dict[str, list] = {
        "nested_pair_in_gold": [],
        "only_longest_in_gold": [],
        "only_shorter_in_gold": [],
        "no_candidate_in_gold": [],
    }
    for d in dev:
        u = us[d.sid]
        gold = {(m.start, m.end) for m in d.gold}
        by_id = {c.cid: c for c in u.cands.values()}
        for f in u.families:
            if not 3 <= len(f.members) <= 7:
                continue
            occ = f.occurrences[0]
            a, b, si = occ
            s0, s1 = u.sents[si]
            if len(u.text[s0:s1].split()) > 60:
                continue
            spans = {}
            for cid in f.members:
                sp = [
                    x
                    for x in PL.spans_inside_occurrence(u, by_id[cid].surface, occ)
                    if a <= x[0] and x[1] <= b
                ]
                if sp:
                    spans[cid] = sp[0]
            if len(spans) < 3:
                continue
            hit = [cid for cid, sp in spans.items() if sp in gold]
            longest = max(spans, key=lambda c: spans[c][1] - spans[c][0])
            if not hit:
                st = "no_candidate_in_gold"
            elif len(hit) >= 2:
                st = "nested_pair_in_gold"
            elif hit[0] == longest:
                st = "only_longest_in_gold"
            else:
                st = "only_shorter_in_gold"
            by_stratum[st].append((d.sid, f, spans, hit))
    rng = random.Random(SEED)
    picked = []
    for st, items in by_stratum.items():
        items = sorted(items, key=lambda x: (x[0], x[1].fid))
        rng.shuffle(items)
        per_sec: dict[str, int] = {}
        for it in items:
            if per_sec.get(it[0], 0) >= 6:
                continue
            per_sec[it[0]] = per_sec.get(it[0], 0) + 1
            picked.append((st, *it))
            if sum(1 for p in picked if p[0] == st) >= PER_STRATUM:
                break
    rng.shuffle(picked)
    by_sec = {d.sid: d for d in dev}
    OUT.mkdir(parents=True, exist_ok=True)
    KEY.parent.mkdir(parents=True, exist_ok=True)
    n_rows = 0
    with (
        (OUT / "boundary_audit_blind.csv").open("w", newline="", encoding="utf-8") as fh,
        KEY.open("w", newline="", encoding="utf-8") as fk,
    ):
        w, k = csv.writer(fh), csv.writer(fk)
        w.writerow(
            [
                "audit_family",
                "section_id",
                "span_id",
                "sentence_marked_run",
                "candidate_span",
                "valid_boundary_yes_no_unsure",
                "independent_term_if_inside_a_longer_valid_term_yes_no_na",
                "note",
            ]
        )
        k.writerow(
            ["audit_family", "span_id", "family_id", "stratum", "gold_exact", "start", "end"]
        )
        for n, (st, sid, f, spans, hit) in enumerate(picked):
            u = us[sid]
            d = by_sec[sid]
            a, b, si = f.occurrences[0]
            sent = mark(u.text, u.sents[si], (a, b), 900)
            by_id = {c.cid: c for c in u.cands.values()}
            for j, cid in enumerate(
                sorted(spans, key=lambda c: (spans[c][0], -(spans[c][1] - spans[c][0])))
            ):
                row_id = f"AF{n:03d}.{j}"
                w.writerow([f"AF{n:03d}", sid, row_id, sent, by_id[cid].surface, "", "", ""])
                k.writerow(
                    [f"AF{n:03d}", row_id, f.fid, st, int(cid in hit), spans[cid][0], spans[cid][1]]
                )
                n_rows += 1
    meta = {"seed": SEED, "families": len(picked), "rows": n_rows, "per_stratum": {st: sum(1 for p in picked if p[0] == st) for st in by_stratum}, "available_per_stratum": {st: len(v) for st, v in by_stratum.items()},
            "blind_sheet_sha256": hashlib.sha256((OUT / "boundary_audit_blind.csv").read_bytes()).hexdigest(), "key_sha256": hashlib.sha256(KEY.read_bytes()).hexdigest()}  # fmt: skip
    Path("reports/cr015/boundary_audit_sample.json").write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
