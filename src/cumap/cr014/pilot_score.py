"""CR-014 STOP 3B: span-exact scoring against the human-annotated P&D pilot sheet (CONCEPT / MENTION rows, see docs/annotation/cr014_concept_annotation_delta.md).

Gold spans come from `sentence_id` + `span_text` + `occurrence` located in `pd_concept_pilot_sentences.csv` (character offsets in the section text).
Predictions are surface lists; each surface is placed at its occurrences by longest-match, non-overlapping (rule 17), so a prediction is a set of
(start, end) mentions. This module reads gold only to score; it never feeds a prediction path. Not pooled with the IIR normalised-name metric."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

Span = tuple[int, int]


@dataclass(frozen=True)
class GoldMention:
    section_id: str
    start: int
    end: int
    concept_id: str
    nested_valid: bool


def load_gold(sheet: Path, sentences: Path) -> list[GoldMention]:
    sents = {r["sentence_id"]: r for r in csv.DictReader(sentences.open(encoding="utf-8"))}
    out: list[GoldMention] = []
    for r in csv.DictReader(sheet.open(encoding="utf-8")):
        if r["row_type"] != "MENTION":
            continue
        s = sents[r["sentence_id"]]
        text = s["sentence_text"]
        occ = int(r["occurrence"] or 1)
        pos = -1
        for _ in range(occ):
            pos = text.find(r["span_text"], pos + 1)
            if pos < 0:
                raise ValueError(f"span not in sentence: {r['sentence_id']} {r['span_text']!r}")
        base = int(s["char_start"])
        out.append(
            GoldMention(
                s["section_id"],
                base + pos,
                base + pos + len(r["span_text"]),
                r["concept_id"],
                (r["nested_valid"] or "").strip().lower() in {"yes", "true", "1"},
            )
        )
    return out


def place(surfaces: list[str], text: str, nested: bool = False) -> list[Span]:
    """Longest-match, non-overlapping placement of surfaces in the section text (token-boundary regex, case-insensitive). `nested=True` keeps every occurrence of every surface (nested concepts both counted)."""
    found: list[Span] = []
    for s in sorted({x.strip() for x in surfaces if x.strip()}, key=lambda x: (-len(x), x)):
        pat = re.compile(
            r"(?<!\w)" + r"\s+".join(re.escape(w) for w in s.split()) + r"(?!\w)", re.IGNORECASE
        )
        for m in pat.finditer(text):
            a, b = m.span()
            if nested or all(b <= x or a >= y for x, y in found):
                found.append((a, b))
    return sorted(set(found))


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": p,
        "recall": r,
        "f1": 2 * p * r / (p + r) if p + r else 0.0,
    }


def classify_boundary(pred: Span, golds: list[Span]) -> str:
    """Relation of an unmatched predicted span to the gold spans that overlap it."""
    ov = [g for g in golds if pred[0] < g[1] and g[0] < pred[1]]
    if not ov:
        return "no_overlap"
    if any(pred[0] <= g[0] and g[1] <= pred[1] for g in ov):
        return "over_specific_contains_gold"
    if any(g[0] <= pred[0] and pred[1] <= g[1] for g in ov):
        return "over_general_inside_gold"
    return "shifted_partial_overlap"


def score(
    pred_spans: dict[str, list[Span]], gold: list[GoldMention], texts: dict[str, str]
) -> dict:
    sids = sorted(pred_spans)
    tp = fp = fn = 0
    tp1 = n1 = pp1 = ptp1 = 0
    cats: dict[str, int] = {}
    miss: dict[str, int] = {"not_overlapped": 0, "overlapped_inexact": 0}
    for sid in sids:
        g = {(m.start, m.end) for m in gold if m.section_id == sid}
        p = set(pred_spans[sid])
        tp += len(g & p)
        fp += len(p - g)
        fn += len(g - p)
        one = lambda sp, t=texts[sid]: len(t[sp[0] : sp[1]].split()) == 1
        n1 += sum(one(x) for x in g)
        tp1 += sum(one(x) for x in g & p)
        pp1 += sum(one(x) for x in p)
        ptp1 += sum(one(x) for x in p & g)
        for x in p - g:
            c = classify_boundary(x, sorted(g))
            cats[c] = cats.get(c, 0) + 1
        for x in g - p:
            miss[
                "overlapped_inexact"
                if any(x[0] < q[1] and q[0] < x[1] for q in p)
                else "not_overlapped"
            ] += 1
    nested = [m for m in gold if m.nested_valid and m.section_id in sids]
    return {
        "mention_span_exact": _prf(tp, fp, fn),
        "one_token": {"gold": n1, "recall": tp1 / n1 if n1 else None, "predicted": pp1, "precision": ptp1 / pp1 if pp1 else None},
        "false_positive_boundary_categories": cats,
        "missed_gold": miss,
        "nested_valid_gold": len(nested),
    }  # fmt: skip
