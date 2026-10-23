"""CR-010 STOP 4: the 60-item double-annotation subset of REL-MAP-180 and the IAA gate status.

Composition (Research decision 2026-10-05): 40 accepted-edge, 10 NO_RELATION, 10 OTHER/near-miss items. Items are chosen
round-robin over the hidden current relation (accepted edges) or the hidden rejection reason (the other strata), with a
seeded generator, from the hidden manifest ONLY. This module never opens an annotator-1 sheet when selecting.

    uv run python -m cumap.cr010.iaa freeze
    uv run python -m cumap.cr010.iaa status [--sheet1 <annotator 1>] [--sheet2 <annotator 2>]

kappa >= 0.67 needs a second HUMAN annotator. Without one the gate is NOT_EVALUABLE and FULL_ERST_REPLACEMENT is ineligible.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr010.relmap import BLIND_COLUMNS, PREFILLED

CHECKS = REPO_ROOT / "data/interim/checks"
SEED = 20261008
COMPOSITION = {"ACCEPTED_EDGE": 40, "NO_RELATION": 10, "OTHER_NEAR_MISS": 10}
KAPPA_GATE = 0.67
HIDDEN_COLUMNS = [
    "item_id",
    "stratum_hidden",
    "current_relation_hidden",
    "relation_family_hidden",
    "selected_for_iaa",
    "freeze_hash",
]


def round_robin(items: list[dict], group_of, n: int, rng: random.Random) -> list[dict]:
    """n items, one from each group in turn (group order and the order inside a group are seeded)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for it in sorted(items, key=lambda x: x["item_id"]):
        groups[group_of(it)].append(it)
    names = sorted(groups)
    rng.shuffle(names)
    for g in names:
        rng.shuffle(groups[g])
    out: list[dict] = []
    while len(out) < n and any(groups.values()):
        for g in names:
            if groups[g] and len(out) < n:
                out.append(groups[g].pop())
    return out


def select(key_rows: list[dict], seed: int = SEED) -> list[str]:
    """Item ids of the IAA subset. Reads stratum / current_relation / current_reason only."""
    rng = random.Random(seed)
    chosen: list[dict] = []
    for stratum, n in COMPOSITION.items():
        pool = [r for r in key_rows if r["stratum"] == stratum]
        group = (
            (lambda r: r["current_relation"])
            if stratum == "ACCEPTED_EDGE"
            else (lambda r: r["current_reason"] or r["current_outcome"])
        )
        chosen += round_robin(pool, group, n, rng)
    ids = sorted(r["item_id"] for r in chosen)
    assert len(ids) == len(set(ids)) == sum(COMPOSITION.values())
    return ids


def freeze() -> dict:
    with (CHECKS / "cr010_relmap180_MANIFEST_KEY_DO_NOT_SHARE.csv").open(encoding="utf-8") as f:
        key = list(csv.DictReader(f))
    ids = select(key)
    h = hashlib.sha256(json.dumps(ids).encode()).hexdigest()
    chosen = set(ids)
    hidden = [
        {
            "item_id": r["item_id"],
            "stratum_hidden": r["stratum"],
            "current_relation_hidden": r["current_relation"],
            "relation_family_hidden": r["current_family"],
            "selected_for_iaa": "yes" if r["item_id"] in chosen else "no",
            "freeze_hash": h,
        }
        for r in sorted(key, key=lambda x: x["item_id"])
    ]
    _write(CHECKS / "cr010_relmap180_iaa_hidden_manifest_DO_NOT_SHARE.csv", hidden, HIDDEN_COLUMNS)
    # annotator 2 gets the same blind columns, prefilled evidence only: rebuilt from the committed BLANK template rows
    with (CHECKS / "cr010_relmap180_blind_sheet.csv").open(encoding="utf-8-sig") as f:
        blind = [r for r in csv.DictReader(f) if r["item_id"] in chosen]
    sheet2 = [{c: (r[c] if c in PREFILLED else "") for c in BLIND_COLUMNS} for r in blind]
    _write(CHECKS / "cr010_relmap180_iaa_annotator2_blind_sheet.csv", sheet2, BLIND_COLUMNS)
    by = {s: Counter() for s in COMPOSITION}
    for r in key:
        if r["item_id"] in chosen:
            by[r["stratum"]][
                r["current_relation"] if r["stratum"] == "ACCEPTED_EDGE" else r["current_reason"]
            ] += 1
    rec = {
        "frozen_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": SEED,
        "composition": {s: sum(c.values()) for s, c in by.items()},
        "accepted_edge_items_per_relation": dict(by["ACCEPTED_EDGE"]),
        "split": dict(Counter(r["split"] for r in key if r["item_id"] in chosen)),
        "freeze_hash_sha256_of_sorted_item_ids": h,
        "selected_from": "hidden manifest fields only (stratum, current relation, rejection reason); no annotator-1 field was read",
        "TIMING_DEVIATION": "annotator 1 had ALREADY completed and saved all 180 rows (the owner's marked sheet, saved 2026-10-06) when this "
        "subset was frozen. The selection cannot depend on those labels (it never reads them) but the CR's 'freeze before "
        "annotator-1 outcomes are known' was not met. Disclosed to Research.",
        "second_human_annotator": "NOT RECORDED in the repository or this session: IAA = NOT_EVALUABLE until one is named",
        "blind_sheet_for_annotator_2": "cr010_relmap180_iaa_annotator2_blind_sheet.csv (blank judgement columns)",
    }
    (CHECKS / "cr010_relmap180_iaa_freeze.json").write_text(
        json.dumps(rec, indent=1), encoding="utf-8"
    )
    return rec


def _write(path: Path, rows: list[dict], cols: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0 or n != len(b):
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def status(sheet1: Path | None, sheet2: Path | None, human_second: bool = False) -> dict:
    """`human_second` must be asserted by the owner: nothing in a CSV proves the annotator is human."""
    frozen = json.loads((CHECKS / "cr010_relmap180_iaa_freeze.json").read_text())
    out = {"subset_size": sum(frozen["composition"].values()), "second_annotation": "absent"}
    if not (sheet1 and sheet2 and sheet2.exists()):
        return {
            **out,
            "iaa_gate": "NOT_EVALUABLE",
            "reason": "no second annotator sheet",
            "full_erst_replacement": "INELIGIBLE",
        }
    ids = {
        r["item_id"]
        for r in csv.DictReader(
            (CHECKS / "cr010_relmap180_iaa_annotator2_blind_sheet.csv").open(encoding="utf-8-sig")
        )
    }
    r1 = {r["item_id"]: r for r in csv.DictReader(sheet1.open(encoding="utf-8-sig"))}
    r2 = {r["item_id"]: r for r in csv.DictReader(sheet2.open(encoding="utf-8-sig"))}
    col = "current_semantic_relation_judgement"
    common = sorted(i for i in ids if r2.get(i, {}).get(col, "").strip() and i in r1)
    k = cohen_kappa([r1[i][col].strip() for i in common], [r2[i][col].strip() for i in common])
    ok = human_second and len(common) >= sum(COMPOSITION.values()) and k is not None
    return {
        **out,
        "second_annotation": f"{len(common)} items",
        "kappa_current_relation": k,
        "iaa_gate": ("PASS" if k is not None and k >= KAPPA_GATE else "FAIL")
        if ok
        else "NOT_EVALUABLE",
        "reason": None
        if ok
        else "second annotator not asserted human, or fewer than 60 items judged",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["freeze", "status"])
    ap.add_argument("--sheet1")
    ap.add_argument("--sheet2")
    ap.add_argument("--second-is-human", action="store_true")
    a = ap.parse_args()
    if a.phase == "freeze":
        print(json.dumps(freeze(), indent=1))
        return
    s1, s2 = (Path(x) if x else None for x in (a.sheet1, a.sheet2))
    print(json.dumps(status(s1, s2, a.second_is_human), indent=1))


if __name__ == "__main__":
    main()
