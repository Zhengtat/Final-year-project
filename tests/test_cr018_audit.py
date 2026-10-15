"""CR-018 STOP 2: the blind boundary-audit sample is deterministic, balanced, gold-free and exposed-only, and the scorer refuses non-human sheets.
The 'filled' sheets below are SYNTHETIC test fixtures derived from the hidden key inside tmp_path; they are never real annotations and are not written into the repo."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from cumap.cr018 import audit_sample as SM
from cumap.cr018 import audit_score as AS

pytestmark = pytest.mark.skipif(
    not SM.KEY.exists() or not SM.SHEET.exists(), reason="audit sheet/key absent"
)
FRESH = {"4.3", "5.1", "5.2", "6.2", "6.5", "8.1", "9.1", "9.4"}


def _rows(p):
    return list(csv.DictReader(p.open(encoding="utf-8")))


def test_sample_is_balanced_blind_exposed_only_and_deterministic():
    rows, key = _rows(SM.SHEET), _rows(SM.KEY)
    assert len(rows) == len(key) == 480 and len({r["audit_family"] for r in rows}) == 120
    fam_stratum = {k["audit_family"]: k["stratum"] for k in key}
    assert {s: list(fam_stratum.values()).count(s) for s in SM.STRATA} == SM.QUOTA
    assert set(rows[0]) == set(SM.COLS) and not any(
        r[c] for r in rows for c in ("q1_exact_complete_boundary_yes_no_unsure", "boundary_label")
    )
    assert not ({k["section_id"] for k in key} & FRESH)
    blob = SM.SHEET.read_text().lower()
    assert "gold" not in blob and "stratum" not in blob and "a2_selected" not in blob
    per = {}
    for k in key:
        per.setdefault((k["stratum"], k["section_id"]), set()).add(k["audit_family"])
    assert max(len(v) for v in per.values()) <= SM.MAX_PER_SECTION  # cap per stratum and section
    before = (
        hashlib.sha256(SM.SHEET.read_bytes()).hexdigest(),
        hashlib.sha256(SM.KEY.read_bytes()).hexdigest(),
    )
    meta = SM.main()
    assert (meta["blind_sheet_sha256"], meta["key_sha256"]) == before


def _fill(tmp_path, labeller, name="filled.csv", sidecar=True):
    key = {k["span_id"]: k for k in _rows(SM.KEY)}
    rows = _rows(SM.SHEET)
    for r in rows:
        lab = labeller(key[r["span_id"]])
        r[AS.LAB], r[AS.Q1] = lab, AS.CFG["q1_by_label"][lab]
        r[AS.Q2] = "yes" if lab == "VALID_NESTED" else "na"
    p = tmp_path / name
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    side = tmp_path / "annotator.json"
    if sidecar:
        side.write_text(
            json.dumps({"annotator_id": "T", "role": "human", "model_assistance": "none"})
        )
    return p, side


def _score(p, side, tmp_path):
    return AS.main(["--sheet", str(p), "--sidecar", str(side), "--out", str(tmp_path / "o.json")])


def test_scorer_agrees_when_human_equals_gold_and_flags_a_systematic_gold_gap(tmp_path):
    p, side = _fill(tmp_path, lambda k: "VALID_EXACT" if k["gold_exact"] == "1" else "OVERLONG")
    r = _score(p, side, tmp_path)
    assert r["analysis"]["overall"]["agreement"] == 1.0
    assert r["recommendation"]["outcome"] == "CONVENTION_COMPATIBLE"
    p2, side2 = _fill(tmp_path, lambda k: "VALID_NESTED", name="all_valid.csv")
    r2 = _score(p2, side2, tmp_path)
    rec = r2["recommendation"]
    assert (
        rec["outcome"] == "STOPPED_BOUNDARY_GOLD_AMBIGUOUS"
        and rec["direction"] == "gold_under_annotates"
    )
    assert rec["systematic"] and any(x.startswith("R2") for x in rec["rules_fired"])


def test_scorer_refuses_model_named_unsigned_edited_or_inconsistent_sheets(tmp_path):
    ok = lambda k: "VALID_EXACT" if k["gold_exact"] == "1" else "OVERLONG"
    p, side = _fill(tmp_path, ok, name="boundary_audit_blind_model_filled.csv")
    with pytest.raises(AS.InvalidSheet, match="model"):
        _score(p, side, tmp_path)
    p, _ = _fill(tmp_path, ok, name="a.csv", sidecar=False)
    with pytest.raises(AS.InvalidSheet, match="declaration"):
        _score(p, tmp_path / "none.json", tmp_path)
    p, side = _fill(tmp_path, ok, name="b.csv")
    (tmp_path / "annotator.json").write_text(
        json.dumps({"annotator_id": "x", "role": "model", "model_assistance": "gpt"})
    )
    with pytest.raises(AS.InvalidSheet, match="human"):
        _score(p, side, tmp_path)
    (tmp_path / "annotator.json").write_text(
        json.dumps({"annotator_id": "x", "role": "human", "model_assistance": "none"})
    )
    rows = _rows(p)
    rows[0]["context_sentence"] += " edited"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(AS.InvalidSheet, match="edited"):
        _score(p, side, tmp_path)
    rows = _rows(SM.SHEET)
    rows[0][AS.LAB], rows[0][AS.Q1] = "VALID_EXACT", "no"
    q = tmp_path / "c.csv"
    with q.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(AS.InvalidSheet):
        _score(q, side, tmp_path)
    with pytest.raises(AS.InvalidSheet, match="missing or invalid"):
        _score(SM.SHEET, side, tmp_path)  # the blank sheet itself is not a completed audit


def test_frozen_materials_match_the_audit_manifest():
    import yaml

    m = yaml.safe_load(Path("configs/cr018_audit_manifest.yaml").read_text())
    assert m["status"] in {"AWAITING_HUMAN_ANNOTATOR", "HUMAN_SHEET_RECEIVED"}
    for p, h in m["hashes"].items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == h, p
    inst = Path("data/interim/checks/cr018/BOUNDARY_AUDIT_INSTRUCTIONS.md").read_bytes()
    assert (
        hashlib.sha256(inst).hexdigest() == m["hashes"]["docs/cr018/BOUNDARY_AUDIT_INSTRUCTIONS.md"]
    )
