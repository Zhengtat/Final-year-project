"""CR-018 STOP 2: draw the frozen 120-family BLIND human boundary-convention audit sample from the EXPOSED development sections (CR-014 pilot + held-out; no fresh section).

Strata (CR-018 handover §7: ~30 each) are defined from the geometry of the family's candidate spans against the development gold. They are used only for sampling and are never shown:
  OVERLONG          a candidate that is not gold strictly contains a gold span
  INVALID_NESTED    a candidate that is not gold lies strictly inside a gold span (both edges interior)
  UNDERLONG_PARTIAL a candidate that is not gold is a prefix/suffix truncation of a gold span (shares one edge) or partially overlaps one
  NESTED_PAIR       >= 2 candidates are gold spans (nested pair in the gold); checked first so the nested convention itself is sampled (15)
  GOLD_SILENT       no candidate is gold and none overlaps gold: the gold marks nothing here, so any valid span is a gold omission or a non-term (15)
(order: NESTED_PAIR, OVERLONG, INVALID_NESTED, UNDERLONG_PARTIAL, GOLD_SILENT; each family gets one stratum). No model decision, selector output or verifier verdict is used to draw or shown. The human sees the section heading, the previous /
marked / next sentence, the family's candidate spans and one target span per row; the key (gold relation, stratum, A2-kept flag) is hidden under data/processed/cr018/.

    uv run python -m cumap.cr018.audit_sample"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from pathlib import Path

from cumap.cr014.llm_stage import mark
from cumap.cr014.pilot_score import classify_boundary
from cumap.cr015 import placement as PL
from cumap.cr015.dev_data import load_dev
from cumap.cr015.stage_a import OUT as STAGE_A
from cumap.cr015.stage_a import unions

ROOT = Path(".")
SEED = "cr018-boundary-audit-v1"
STRATA = ["OVERLONG", "UNDERLONG_PARTIAL", "INVALID_NESTED", "NESTED_PAIR", "GOLD_SILENT"]
QUOTA = {
    "OVERLONG": 30,
    "UNDERLONG_PARTIAL": 30,
    "INVALID_NESTED": 30,
    "NESTED_PAIR": 15,
    "GOLD_SILENT": 15,
}  # NESTED_PAIR + GOLD_SILENT = the 30 nested / ambiguous
MAX_PER_SECTION = 6
SHEET = ROOT / "data/interim/checks/cr018/boundary_audit_blind.csv"
KEY = ROOT / "data/processed/cr018/boundary_audit_key.csv"
META = ROOT / "reports/cr018/boundary_audit_sample.json"
COLS = [
    "audit_family", "span_id", "section_heading", "context_before", "context_sentence",
    "context_after", "family_spans", "target_span", "q1_exact_complete_boundary_yes_no_unsure",
    "q2_independently_meaningful_if_inside_longer_term_yes_no_na", "boundary_label", "note",
]  # fmt: skip
_ws = lambda s: re.sub(r"\s+", " ", s).strip()


def stratum(spans: dict[str, tuple[int, int]], gold: set[tuple[int, int]]) -> str | None:
    hit = [c for c, sp in spans.items() if sp in gold]
    if len(hit) >= 2:
        return "NESTED_PAIR"
    non = {c: sp for c, sp in spans.items() if c not in hit}
    golds = list(gold)
    rel = {c: classify_boundary(sp, golds) for c, sp in non.items()}
    if any(r == "over_specific_contains_gold" for r in rel.values()):
        return "OVERLONG"
    interior, edge = False, False
    for c, r in rel.items():
        if r != "over_general_inside_gold":
            continue
        g = next(g for g in golds if g[0] <= spans[c][0] and spans[c][1] <= g[1])
        if spans[c][0] > g[0] and spans[c][1] < g[1]:
            interior = True
        else:
            edge = True
    if interior:
        return "INVALID_NESTED"
    if edge or any(r == "shifted_partial_overlap" for r in rel.values()):
        return "UNDERLONG_PARTIAL"
    if not hit and all(r == "no_overlap" for r in rel.values()):
        return "GOLD_SILENT"
    return None  # a single gold span, no wrong alternative: not informative about conventions


def _context(u, si: int) -> tuple[str, str]:
    prev = _ws(u.text[u.sents[si - 1][0] : u.sents[si - 1][1]]) if si > 0 else ""
    nxt = _ws(u.text[u.sents[si + 1][0] : u.sents[si + 1][1]]) if si + 1 < len(u.sents) else ""
    return prev[-400:], nxt[:400]


def main() -> dict:
    dev = load_dev()
    us = unions(dev)
    pools: dict[str, list] = {s: [] for s in STRATA}
    for d in dev:
        u = us[d.sid]
        gold = {(m.start, m.end) for m in d.gold}
        a2 = json.loads((STAGE_A / f"A2_{d.sid}.json").read_text())
        by_id = {c.cid: c for c in u.cands.values()}
        for f in u.families:
            if not 3 <= len(f.members) <= 7:
                continue
            a, b, si = f.occurrences[0]
            s0, s1 = u.sents[si]
            if len(u.text[s0:s1].split()) > 60:
                continue
            spans = {}
            for cid in f.members:
                sp = [
                    x
                    for x in PL.spans_inside_occurrence(u, by_id[cid].surface, f.occurrences[0])
                    if a <= x[0] and x[1] <= b
                ]
                if sp:
                    spans[cid] = sp[0]  # fmt: skip
            if len(spans) < 3:
                continue
            st = stratum(spans, gold)
            if st:
                pools[st].append((d.sid, f, spans, set(a2["selected"].get(f.fid, []))))
    rng = random.Random(SEED)
    picked = []
    for st in STRATA:
        items = sorted(pools[st], key=lambda x: (x[0], x[1].fid))
        rng.shuffle(items)
        per_sec: dict[str, int] = {}
        n = 0
        for it in items:
            if per_sec.get(it[0], 0) >= MAX_PER_SECTION:
                continue
            per_sec[it[0]] = per_sec.get(it[0], 0) + 1
            picked.append((st, *it))
            n += 1
            if n >= QUOTA[st]:
                break
    rng.shuffle(picked)
    by_sec = {d.sid: d for d in dev}
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    KEY.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with (
        SHEET.open("w", newline="", encoding="utf-8") as fh,
        KEY.open("w", newline="", encoding="utf-8") as fk,
    ):
        w, k = csv.writer(fh), csv.writer(fk)
        w.writerow(COLS)
        k.writerow(["audit_family", "span_id", "section_id", "family_id", "stratum", "gold_exact", "gold_relation", "a2_selected", "start", "end"])  # fmt: skip
        for n, (st, sid, f, spans, a2sel) in enumerate(picked):
            u, d = us[sid], by_sec[sid]
            by_id = {c.cid: c for c in u.cands.values()}
            si = f.occurrences[0][2]
            before, after = _context(u, si)
            heading = " > ".join(d.row.get("heading_path") or [sid])
            order = sorted(spans, key=lambda c: (spans[c][0], -(spans[c][1] - spans[c][0])))
            fam = " | ".join(_ws(u.text[spans[c][0] : spans[c][1]]) for c in order)
            golds = [(m.start, m.end) for m in d.gold]
            for j, cid in enumerate(order):
                rid = f"AF{n:03d}.{j}"
                sent = mark(u.text, u.sents[si], spans[cid], 900)
                w.writerow(
                    [
                        f"AF{n:03d}",
                        rid,
                        heading,
                        before,
                        sent,
                        after,
                        fam,
                        _ws(u.text[spans[cid][0] : spans[cid][1]]),
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                exact = spans[cid] in set(golds)
                rel = "exact" if exact else classify_boundary(spans[cid], golds)
                k.writerow([f"AF{n:03d}", rid, sid, f.fid, st, int(exact), rel, int(by_id[cid].surface in a2sel), *spans[cid]])  # fmt: skip
                rows += 1
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    meta = {
        "seed": SEED, "families": len(picked), "rows": rows,
        "per_stratum": {s: sum(1 for p in picked if p[0] == s) for s in STRATA},
        "available_per_stratum": {s: len(v) for s, v in pools.items()},
        "sections": sorted({p[1] for p in picked}), "blind_sheet_sha256": sha(SHEET), "key_sha256": sha(KEY),
    }  # fmt: skip
    META.write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
