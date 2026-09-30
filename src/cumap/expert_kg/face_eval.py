"""CR-005 §3.1: evaluate a concepts-only run against FACE gold labels and package
everything the demo report needs -- metrics (exact + lenient, micro + macro), recall by
n-gram length, precision by role, per-section match status for the section viewer, and
10 false positives + 10 false negatives with context and a rule-based *likely cause*.

Causes are deliberately simple, computed from the strings alone (no LLM): for a false
negative -- the model predicted a more specific / more general phrase, the gold term is
a unigram, or a long phrase; for a false positive -- over-specific / over-general vs a
gold term, description-like (>= 4 words), mentioned-only, single word. The CR's example
labels "generic term" and "missed definition" are NOT computed: neither can be detected
reliably from strings alone, so they'd be guesses presented as findings.
"""

from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path

from cumap.expert_kg.face_scorer import (
    GoldConcept,
    PredictedConcept,
    false_negatives,
    load_gold_concepts,
    macro_prf1,
    match_predictions,
    micro_prf1,
    ngram_len,
    normalize,
    precision_by_role,
    recall_by_ngram_length,
)

# FACE's published reference points (Chau et al. 2020, Table 3, as quoted in CR-003/CR-005).
# FACE was supervised with 5-fold CV on the same book; ours is zero/few-shot on held-out
# chapters -- the caveat travels with these numbers everywhere they're shown.
FACE_PUBLISHED = {
    "FACE (supervised) micro F1": 0.76,
    "FACE (supervised) macro F1": 0.60,
    "FACE linguistic-only micro F1": 0.65,
    "CopyRNN micro F1": 0.23,
    "MTurk humans micro F1": 0.39,
}
FACE_CAVEAT = (
    "FACE was supervised with 5-fold CV on the same book; ours is zero/few-shot on "
    "held-out chapters -- not a like-for-like comparison."
)

_STOP = {"of", "the", "a", "an", "and", "or", "in", "on", "for", "to", "with"}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _contains_phrase(longer: str, shorter: str) -> bool:
    a, b = _tokens(longer), _tokens(shorter)
    if not b or len(b) >= len(a):
        return False
    return any(a[i : i + len(b)] == b for i in range(len(a) - len(b) + 1))


def _sentence_with(text: str, term: str, max_chars: int = 320) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if term.lower() in sentence.lower():
            return sentence if len(sentence) <= max_chars else sentence[: max_chars - 1] + "…"
    return ""


def false_negative_cause(gold: GoldConcept, section_predictions: list[str]) -> str:
    if any(_contains_phrase(p, gold.concept) for p in section_predictions):
        return "prediction is more specific than the gold term"
    if any(_contains_phrase(gold.concept, p) for p in section_predictions):
        return "prediction is more general than the gold term"
    n = ngram_len(gold.concept)
    if n == 1:
        return "unigram"
    if n >= 3:
        return "long phrase (3+ words)"
    return "other"


def false_positive_cause(pred: PredictedConcept, section_gold: list[str]) -> str:
    if any(_contains_phrase(pred.canonical_name, g) for g in section_gold):
        return "over-specific (contains a gold term)"
    if any(_contains_phrase(g, pred.canonical_name) for g in section_gold):
        return "over-general (inside a gold term)"
    n = ngram_len(pred.canonical_name)
    if n >= 4:
        return "description-like (4+ words)"
    if pred.role == "mentioned":
        return "mentioned only"
    if n == 1:
        return "single word"
    return "other"


def _round_robin_sample(items: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_cause: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_cause[item["cause"]].append(item)
    for group in by_cause.values():
        rng.shuffle(group)
    out: list[dict] = []
    while len(out) < n and any(by_cause.values()):
        for cause in sorted(by_cause, key=lambda c: -len(by_cause[c])):
            if by_cause[cause] and len(out) < n:
                out.append(by_cause[cause].pop())
    return out


def _prf(x) -> dict:
    return {
        "precision": x.precision,
        "recall": x.recall,
        "f1": x.f1,
        "tp": x.tp,
        "fp": x.fp,
        "fn": x.fn,
    }


def evaluate_mentions(
    mentions_by_section: dict[str, list[dict]],
    gold: list[GoldConcept],
    section_texts: dict[str, str],
    *,
    nlp=None,
    embed_fn=None,
    embedding_threshold: float = 0.75,
    n_examples: int = 10,
    seed: int = 42,
) -> dict:
    """`mentions_by_section`: checkpoint-style dicts (canonical_name, role, evidence_quote)."""
    gold = [g for g in gold if g.section_id in mentions_by_section]
    predicted = [
        PredictedConcept(sid, m["canonical_name"], m["role"])
        for sid, ms in mentions_by_section.items()
        for m in ms
    ]
    evidence = {
        (sid, m["canonical_name"]): m.get("evidence_quote", "")
        for sid, ms in mentions_by_section.items()
        for m in ms
    }
    exact = match_predictions(predicted, gold, lenient=False)
    lenient = match_predictions(
        predicted,
        gold,
        lenient=True,
        nlp=nlp,
        embed_fn=embed_fn,
        embedding_threshold=embedding_threshold,
    )

    metrics = {
        "n_predicted": len(predicted),
        "n_gold": len(gold),
        "exact": {"micro": _prf(micro_prf1(exact, gold)), "macro": _prf(macro_prf1(exact, gold))},
        "lenient": {
            "micro": _prf(micro_prf1(lenient, gold)),
            "macro": _prf(macro_prf1(lenient, gold)),
        },
        "recall_by_ngram": {
            "exact": {
                str(n): vars(r) for n, r in sorted(recall_by_ngram_length(exact, gold).items())
            },
            "lenient": {
                str(n): vars(r) for n, r in sorted(recall_by_ngram_length(lenient, gold).items())
            },
        },
        "precision_by_role": {k: vars(v) for k, v in precision_by_role(lenient).items()},
    }

    missed = false_negatives(lenient, gold)
    missed_by_section: dict[str, list[GoldConcept]] = defaultdict(list)
    for g in missed:
        missed_by_section[g.section_id].append(g)

    per_section = []
    for sid in mentions_by_section:
        rows = [r for r in lenient if r.predicted.section_id == sid]
        per_section.append(
            {
                "section_id": sid,
                "predicted": [
                    {
                        "name": r.predicted.canonical_name,
                        "role": r.predicted.role,
                        "evidence": evidence.get((sid, r.predicted.canonical_name), ""),
                        "status": r.match_type or "extra",
                        "matched_gold": r.matched_gold.concept if r.matched_gold else None,
                    }
                    for r in rows
                ],
                "missed_gold": [g.concept for g in missed_by_section.get(sid, [])],
            }
        )

    gold_names: dict[str, list[str]] = defaultdict(list)
    for g in gold:
        gold_names[g.section_id].append(g.concept)
    preds_names: dict[str, list[str]] = defaultdict(list)
    for p in predicted:
        preds_names[p.section_id].append(p.canonical_name)

    fp_items = [
        {
            "section_id": r.predicted.section_id,
            "concept": r.predicted.canonical_name,
            "role": r.predicted.role,
            "cause": false_positive_cause(r.predicted, gold_names[r.predicted.section_id]),
            "context": _sentence_with(
                section_texts.get(r.predicted.section_id, ""), r.predicted.canonical_name
            ),
        }
        for r in lenient
        if r.matched_gold is None
    ]
    fn_items = [
        {
            "section_id": g.section_id,
            "concept": g.concept,
            "cause": false_negative_cause(g, preds_names[g.section_id]),
            "context": _sentence_with(section_texts.get(g.section_id, ""), g.concept),
        }
        for g in missed
    ]
    cause_counts = {
        "false_positive": _count(fp_items),
        "false_negative": _count(fn_items),
    }
    return {
        "metrics": metrics,
        "per_section": per_section,
        "cause_counts": cause_counts,
        "false_positives": _round_robin_sample(fp_items, n_examples, seed),
        "false_negatives": _round_robin_sample(fn_items, n_examples, seed),
        "embedding_threshold": embedding_threshold,
    }


def _count(items: list[dict]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for i in items:
        out[i["cause"]] += 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def evaluate_run(
    run_dir: Path, gold_csv: Path, sections_jsonl: Path, *, nlp=None, embed_fn=None
) -> dict:
    """Reads run_dir/checkpoint.json + gold + section texts; writes run_dir/face_eval.json."""
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text())
    texts = {}
    with sections_jsonl.open() as f:
        for line in f:
            row = json.loads(line)
            texts[row["section_id"]] = row["text"]
    result = evaluate_mentions(
        checkpoint["mentions_by_section"],
        load_gold_concepts(gold_csv),
        texts,
        nlp=nlp,
        embed_fn=embed_fn,
    )
    result["run_id"] = checkpoint["run_id"]
    (run_dir / "face_eval.json").write_text(json.dumps(result, indent=2))
    return result


__all__ = ["FACE_CAVEAT", "FACE_PUBLISHED", "evaluate_mentions", "evaluate_run", "normalize"]
