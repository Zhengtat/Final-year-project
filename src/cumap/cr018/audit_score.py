"""CR-018 STOP 2: score the completed HUMAN boundary-audit sheet against the development-gold convention and recommend a gate outcome.

The scorer refuses anything that is not a complete human sheet (see `check_sheet`): no sidecar declaring a human annotator, a file name suggesting a model, edited blind columns,
missing or inconsistent labels. It never fills or edits a sheet. The decision rule is frozen in `configs/cr018_audit.yaml`.

    uv run python -m cumap.cr018.audit_score --sheet <filled.csv> [--out reports/cr018/boundary_audit_scores.json]"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(".")
CFG = yaml.safe_load((ROOT / "configs/cr018_audit.yaml").read_text())
BLIND = ROOT / "data/interim/checks/cr018/boundary_audit_blind.csv"
KEY = ROOT / "data/processed/cr018/boundary_audit_key.csv"
Q1, Q2, LAB = (
    "q1_exact_complete_boundary_yes_no_unsure",
    "q2_independently_meaningful_if_inside_longer_term_yes_no_na",
    "boundary_label",
)
FILL = {Q1, Q2, LAB, "note"}


class InvalidSheet(ValueError):
    pass


def _rows(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def check_sheet(sheet: Path, blind: Path = BLIND, sidecar: Path | None = None) -> list[dict]:
    prov = CFG["provenance"]
    if any(w in sheet.name.lower() for w in prov["refuse_filenames_containing"]):
        raise InvalidSheet(f"file name {sheet.name!r} suggests a model-filled sheet")
    side = sidecar or ROOT / prov["required_sidecar"]
    if not side.exists():
        raise InvalidSheet(f"missing human-annotator declaration {side}")
    d = json.loads(side.read_text())
    if d.get("role") != "human" or d.get("model_assistance") != "none" or not d.get("annotator_id"):
        raise InvalidSheet(
            "sidecar must declare role=human, model_assistance=none and an annotator_id"
        )
    rows, ref = _rows(sheet), _rows(blind)
    if len(rows) != len(ref):
        raise InvalidSheet(f"{len(rows)} rows, expected {len(ref)}")
    for r, b in zip(rows, ref, strict=True):
        if any(r[c] != b[c] for c in b if c not in FILL):
            raise InvalidSheet(f"blind column edited at {b['span_id']}")
        lab = (r[LAB] or "").strip()
        if lab not in CFG["labels"]:
            raise InvalidSheet(f"{b['span_id']}: boundary_label {lab!r} missing or invalid")
        if (r[Q1] or "").strip().lower() != CFG["q1_by_label"][lab]:
            raise InvalidSheet(f"{b['span_id']}: q1 {r[Q1]!r} inconsistent with {lab}")
        q2 = (r[Q2] or "").strip().lower()
        if q2 not in ("yes", "no", "na") or (lab == "VALID_NESTED" and q2 != "yes"):
            raise InvalidSheet(f"{b['span_id']}: q2 {r[Q2]!r} invalid for {lab}")
    return rows


def _rate(a: int, b: int) -> float | None:
    return a / b if b else None


def kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else None


def analyse(rows: list[dict], key: list[dict]) -> dict:
    valid = set(CFG["valid_labels"])
    recs = []
    for r, k in zip(rows, key, strict=True):
        assert r["span_id"] == k["span_id"]
        lab = r[LAB].strip()
        recs.append({
            "fam": k["audit_family"], "stratum": k["stratum"], "gold": bool(int(k["gold_exact"])),
            "rel": k["gold_relation"], "a2": bool(int(k["a2_selected"])), "lab": lab,
            "hv": lab in valid, "unc": lab == "UNCERTAIN",
        })  # fmt: skip

    def stats(rs: list[dict]) -> dict:
        d = [r for r in rs if not r["unc"]]
        agree = sum(r["hv"] == r["gold"] for r in d)
        gm = [r for r in d if r["gold"]]
        gu = [r for r in d if not r["gold"]]
        return {
            "spans": len(rs), "uncertain": len(rs) - len(d), "agreement": _rate(agree, len(d)),
            "kappa": kappa([(r["hv"], r["gold"]) for r in d]),
            "gold_unmarked_judged_valid": _rate(sum(r["hv"] for r in gu), len(gu)), "n_gold_unmarked": len(gu),
            "gold_marked_judged_invalid": _rate(sum(not r["hv"] for r in gm), len(gm)), "n_gold_marked": len(gm),
            "to_valid_disagreements": sum(r["hv"] and not r["gold"] for r in d),
            "to_invalid_disagreements": sum((not r["hv"]) and r["gold"] for r in d),
        }  # fmt: skip

    out = {
        "overall": stats(recs),
        "by_stratum": {},
        "by_gold_relation": {},
        "label_by_gold_relation": {},
        "a2_selected_vs_human": None,
    }
    for s in sorted({r["stratum"] for r in recs}):
        out["by_stratum"][s] = stats([r for r in recs if r["stratum"] == s])
    for rel in sorted({r["rel"] for r in recs}):
        rs = [r for r in recs if r["rel"] == rel]
        out["by_gold_relation"][rel] = stats(rs)
        out["label_by_gold_relation"][rel] = dict(Counter(r["lab"] for r in rs))
    d2 = [r for r in recs if not r["unc"]]
    out["a2_selected_vs_human"] = {"agreement": _rate(sum(r["a2"] == r["hv"] for r in d2), len(d2)), "a2_kept_judged_invalid": _rate(sum((not r["hv"]) for r in d2 if r["a2"]), sum(r["a2"] for r in d2)), "a2_dropped_judged_valid": _rate(sum(r["hv"] for r in d2 if not r["a2"]), sum(not r["a2"] for r in d2))}  # fmt: skip
    fams = defaultdict(list)
    for r in recs:
        fams[r["fam"]].append(r)
    out["family_level"] = {
        "families": len(fams),
        "with_two_or_more_human_valid_spans": sum(sum(r["hv"] for r in v) >= 2 for v in fams.values()),
        "with_no_human_valid_span": sum(not any(r["hv"] for r in v) for v in fams.values()),
        "human_valid_set_equals_gold_set": sum(all(r["hv"] == r["gold"] for r in v if not r["unc"]) for v in fams.values()),
    }  # fmt: skip
    b = CFG["bootstrap"]
    rng = random.Random(b["seed"])
    ids = sorted(fams)
    ci = defaultdict(list)
    for _ in range(b["resamples"]):
        rs = [r for f in (rng.choice(ids) for _ in ids) for r in fams[f]]
        s = stats(rs)
        for k in ("agreement", "gold_unmarked_judged_valid", "gold_marked_judged_invalid"):
            if s[k] is not None:
                ci[k].append(s[k])
    out["overall_ci95_family_bootstrap"] = {
        k: [sorted(v)[int(0.025 * len(v))], sorted(v)[int(0.975 * len(v)) - 1]] for k, v in ci.items()
    }  # fmt: skip
    return out


def recommend(a: dict) -> dict:
    m, o = CFG["material"], a["overall"]
    fired = []
    if o["agreement"] is not None and o["agreement"] < m["min_span_agreement"]:
        fired.append(f"R1 span agreement {o['agreement']:.3f} < {m['min_span_agreement']}")
    if (o["gold_unmarked_judged_valid"] or 0) > m["max_gold_unmarked_judged_valid"]:
        fired.append(
            f"R2 gold-unmarked judged valid {o['gold_unmarked_judged_valid']:.3f} > {m['max_gold_unmarked_judged_valid']}"
        )
    if (o["gold_marked_judged_invalid"] or 0) > m["max_gold_marked_judged_invalid"]:
        fired.append(
            f"R3 gold-marked judged invalid {o['gold_marked_judged_invalid']:.3f} > {m['max_gold_marked_judged_invalid']}"
        )
    for s, v in a["by_stratum"].items():
        if v["agreement"] is not None and v["agreement"] < m["min_stratum_agreement"]:
            fired.append(
                f"R4 stratum {s} agreement {v['agreement']:.3f} < {m['min_stratum_agreement']}"
            )
    dis = o["to_valid_disagreements"] + o["to_invalid_disagreements"]
    share = max(o["to_valid_disagreements"], o["to_invalid_disagreements"]) / dis if dis else 0.0
    direction = (
        "gold_under_annotates"
        if o["to_valid_disagreements"] >= o["to_invalid_disagreements"]
        else "gold_over_annotates"
    )
    systematic = dis >= CFG["min_disagreements"] and share >= CFG["systematic_direction_share"]
    unreliable = o["spans"] and o["uncertain"] / o["spans"] > CFG["max_uncertain_rate"]
    key = (
        "both_material_and_systematic"
        if fired and systematic
        else ("material_not_systematic" if fired else "not_material")
    )
    return {"outcome": CFG["outcomes"][key], "rules_fired": fired, "systematic": systematic, "direction": direction, "direction_share": share, "disagreements": dis, "sheet_unreliable_uncertain_rate": bool(unreliable), "rule_version": CFG["version"]}  # fmt: skip


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True, type=Path)
    ap.add_argument("--sidecar", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "reports/cr018/boundary_audit_scores.json")
    ns = ap.parse_args(argv)
    rows = check_sheet(ns.sheet, sidecar=ns.sidecar)
    a = analyse(rows, _rows(KEY))
    res = {"analysis": a, "recommendation": recommend(a), "sheet": str(ns.sheet)}
    ns.out.write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
