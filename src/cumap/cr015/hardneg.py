"""CR-015 development hard-negative bank (CR §13) and retrieval of contrastive demonstrations (CR §15).

Built from DEVELOPMENT gold only (the exposed CR-014 sections). Each gold mention contributes a positive and boundary negatives made by permitted transformations
(gold span +-1/2 tokens, head-only, modifier-only, parent noun chunk). A negative is dropped if its span is itself a gold mention. Retrieval for a query in section X never
uses X's own gold (leave-one-section-out). Fresh held-out gold never enters the bank."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import spacy

from cumap.cr015.dev_data import DevSection

ROOT = Path(".")
STOP_EDGE = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "is",
    "are",
    "be",
    "by",
    "with",
    "that",
    "this",
    "as",
    "at",
    "it",
    "its",
}
MAX_PER_GOLD = 5


def _sentences() -> dict[str, tuple[int, int, str]]:
    out = {}
    for f in (
        "data/interim/checks/cr014/pd_concept_pilot_sentences.csv",
        "data/interim/checks/cr014/pd_concept_test_sentences.csv",
    ):
        for r in csv.DictReader((ROOT / f).open(encoding="utf-8")):
            out[r["sentence_id"]] = (int(r["char_start"]), int(r["char_end"]), r["sentence_text"])
    return out


def build_bank(dev: list[DevSection]) -> dict:
    nlp = spacy.load("en_core_web_sm")
    sents = _sentences()
    by_sec: dict[str, list] = {}
    for sid, (a, b, t) in sents.items():
        by_sec.setdefault(sid.split("_s")[0], []).append((a, b, t, sid))
    groups = []
    for d in dev:
        gold_spans = {(m.start, m.end) for m in d.gold}
        spans_by_sent: dict[tuple, list] = {}
        for m in d.gold:
            for a, b, t, sid in by_sec.get(d.sid, []):
                if a <= m.start and m.end <= b:
                    spans_by_sent.setdefault((a, b, t, sid), []).append((m.start, m.end))
                    break
        for (a, b, t, sid), spans in spans_by_sent.items():
            doc = nlp(t)
            toks = [(x.idx + a, x.idx + a + len(x.text), x) for x in doc]
            starts = {s: i for i, (s, _e, _x) in enumerate(toks)}
            ends = {e: i for i, (_s, e, _x) in enumerate(toks)}
            chunks = [(c.start, c.end) for c in doc.noun_chunks]
            for gs, ge in spans:
                if gs not in starts or ge not in ends:
                    continue
                i, j = starts[gs], ends[ge]
                negs: list[tuple[int, int, str, str]] = []

                def add(
                    x: int, y: int, why: str, expect: str, i=i, j=j, toks=toks, negs=negs
                ) -> None:
                    if x < 0 or y >= len(toks) or x > y:
                        return
                    first, last = toks[x][2], toks[y][2]
                    if (
                        first.is_punct
                        or last.is_punct
                        or first.text.lower() in STOP_EDGE
                        or last.text.lower() in STOP_EDGE
                    ):
                        return
                    sp = (toks[x][0], toks[y][1])
                    if sp in gold_spans or sp == (toks[i][0], toks[j][1]):
                        return
                    negs.append((sp[0], sp[1], why, expect))

                add(i - 1, j, "gold_plus_1_left", "over-long wrapper")
                add(i, j + 1, "gold_plus_1_right", "over-long wrapper")
                add(i, j + 2, "gold_plus_2_right", "over-long")
                if j > i:
                    add(i + 1, j, "gold_minus_first_token", "under-long (modifier dropped)")
                    add(i, j - 1, "modifier_only", "under-long (head dropped)")
                    add(j, j, "head_only", "under-long (head only)")
                for cs, ce in chunks:
                    if cs <= i and j <= ce - 1 and (cs, ce - 1) != (i, j):
                        add(cs, ce - 1, "parent_noun_chunk", "over-long parent phrase")
                seen, keep = set(), []
                for n in negs:
                    if n[:2] not in seen:
                        seen.add(n[:2])
                        keep.append(n)
                head = toks[j][2].lemma_.lower()
                groups.append(
                    {
                        "group_id": f"{sid}@{gs}", "source_section": d.sid, "sentence": t, "sentence_start": a, "sentence_id": sid, "n_tokens": j - i + 1, "head": head,
                        "positive": {"start": gs, "end": ge, "surface": t[gs - a : ge - a]},
                        "negatives": [{"hard_negative_id": f"{sid}@{gs}#{k}", "source_gold_id": f"{sid}@{gs}", "transformation": n[2], "source_sentence": t, "span": t[n[0] - a : n[1] - a],
                                       "start_offset": n[0], "end_offset": n[1], "reason_expected_negative": n[3]} for k, n in enumerate(keep[:MAX_PER_GOLD])],
                    }
                )  # fmt: skip
    groups = [g for g in groups if g["negatives"]]
    bank = {
        "groups": groups,
        "n_groups": len(groups),
        "n_negatives": sum(len(g["negatives"]) for g in groups),
    }
    bank["sha256"] = hashlib.sha256(json.dumps(groups, sort_keys=True).encode()).hexdigest()
    return bank


def retrieve(bank: dict, query_section: str, n_tokens: int, head: str, k: int = 2) -> list[dict]:
    """Contrast groups from OTHER sections: same head first, then same length (ranking features are returned with each hit)."""
    scored = []
    for g in bank["groups"]:
        if g["source_section"] == query_section:
            continue
        f = {
            "same_head": float(g["head"] == head),
            "same_length": float(g["n_tokens"] == n_tokens),
            "len_gap": abs(g["n_tokens"] - n_tokens),
        }
        scored.append(
            (2 * f["same_head"] + 1.5 * f["same_length"] - 0.25 * f["len_gap"], g["group_id"], g, f)
        )
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [{**g, "ranking_features": f, "score": sc} for sc, _id, g, f in scored[:k]]


def render_group(g: dict) -> str:
    s0 = g["sentence_start"]
    pos = g["positive"]
    t = g["sentence"]
    marked = t[: pos["start"] - s0] + "<<" + pos["surface"] + ">>" + t[pos["end"] - s0 :]
    lines = [f"- {marked}\n  VALID boundary: {pos['surface']}"]
    for n in g["negatives"][:2]:
        lines.append(f"  INVALID ({n['reason_expected_negative']}): {n['span']}")
    return "\n".join(lines)
