"""CR-005 §3.1: FACE-protocol concept scoring. Exact match (a predicted concept's
name, or one of its normalised forms, equals a gold concept's name or alias) and
lenient match (also allows a lemma match or an embedding-similarity match above a
threshold) -- both computed per section, then aggregated micro (pool every section's
TP/FP/FN, one P/R/F1) and macro (P/R/F1 per section, averaged over sections that have
at least one gold concept). Caveat this always carries, stated once here rather than
on every chart: FACE was supervised with 5-fold CV on the same book; this is zero/
few-shot on held-out chapters -- not a like-for-like comparison, just the closest
available reference point.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def ngram_len(text: str) -> int:
    return len(text.split())


@dataclass
class GoldConcept:
    section_id: str
    concept: str
    aliases: list[str] = field(default_factory=list)

    def names(self) -> set[str]:
        return {normalize(self.concept)} | {normalize(a) for a in self.aliases}


@dataclass
class PredictedConcept:
    section_id: str
    canonical_name: str
    role: str  # "defined" | "used" | "mentioned"


@dataclass
class MatchResult:
    predicted: PredictedConcept
    matched_gold: GoldConcept | None
    match_type: str | None  # "exact" | "lemma" | "embedding" | None (unmatched -> a false positive)


def load_gold_concepts(csv_path) -> list[GoldConcept]:
    df = pd.read_csv(csv_path)
    df = df[df["is_gold"]]
    concepts = []
    for _, row in df.iterrows():
        aliases_raw = row.get("aliases", "[]")
        aliases = ast.literal_eval(aliases_raw) if isinstance(aliases_raw, str) else []
        concepts.append(
            GoldConcept(section_id=row["section_id"], concept=row["concept"], aliases=aliases)
        )
    return concepts


def _lemmatize(text: str, nlp) -> str:
    doc = nlp(text)
    return " ".join(tok.lemma_.lower() for tok in doc)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def _group_by_section(items: list) -> dict[str, list]:
    grouped: dict[str, list] = defaultdict(list)
    for item in items:
        grouped[item.section_id].append(item)
    return grouped


def match_predictions(
    predicted: list[PredictedConcept],
    gold: list[GoldConcept],
    *,
    lenient: bool,
    nlp=None,
    embed_fn=None,
    embedding_threshold: float = 0.75,
) -> list[MatchResult]:
    """Each gold concept can be matched by at most one predicted concept (first
    predicted concept in `predicted`'s order that reaches it wins) -- avoids one gold
    concept inflating recall by matching several near-duplicate predictions.
    """
    gold_by_section = _group_by_section(gold)
    predicted_by_section = _group_by_section(predicted)
    results: list[MatchResult] = []

    for section_id, section_predicted in predicted_by_section.items():
        section_gold = gold_by_section.get(section_id, [])
        gold_used = [False] * len(section_gold)

        for p in section_predicted:
            p_norm = normalize(p.canonical_name)
            match_type, matched = None, None

            for i, g in enumerate(section_gold):
                if not gold_used[i] and p_norm in g.names():
                    match_type, matched, gold_used[i] = "exact", g, True
                    break

            if match_type is None and lenient and nlp is not None:
                p_lemma = _lemmatize(p.canonical_name, nlp)
                for i, g in enumerate(section_gold):
                    if gold_used[i]:
                        continue
                    if p_lemma == _lemmatize(g.concept, nlp):
                        match_type, matched, gold_used[i] = "lemma", g, True
                        break

            if match_type is None and lenient and embed_fn is not None:
                p_emb = embed_fn(p.canonical_name)
                best_sim, best_i = -1.0, None
                for i, g in enumerate(section_gold):
                    if gold_used[i]:
                        continue
                    sim = _cosine(p_emb, embed_fn(g.concept))
                    if sim > best_sim:
                        best_sim, best_i = sim, i
                if best_i is not None and best_sim >= embedding_threshold:
                    match_type, matched, gold_used[best_i] = "embedding", section_gold[best_i], True

            results.append(MatchResult(predicted=p, matched_gold=matched, match_type=match_type))

    return results


@dataclass
class PRF1:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


def _prf1(tp: int, fp: int, fn: int) -> PRF1:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return PRF1(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn)


def _false_negatives(results: list[MatchResult], gold: list[GoldConcept]) -> list[GoldConcept]:
    matched_gold_keys = {
        (r.matched_gold.section_id, normalize(r.matched_gold.concept))
        for r in results
        if r.matched_gold is not None
    }
    return [g for g in gold if (g.section_id, normalize(g.concept)) not in matched_gold_keys]


def micro_prf1(results: list[MatchResult], gold: list[GoldConcept]) -> PRF1:
    tp = sum(1 for r in results if r.matched_gold is not None)
    fp = sum(1 for r in results if r.matched_gold is None)
    fn = len(_false_negatives(results, gold))
    return _prf1(tp, fp, fn)


def macro_prf1(results: list[MatchResult], gold: list[GoldConcept]) -> PRF1:
    """Averages P/R/F1 over sections that have at least one gold concept OR at least
    one prediction (a section with neither contributes nothing to score either way).
    """
    by_section_results: dict[str, list[MatchResult]] = defaultdict(list)
    for r in results:
        by_section_results[r.predicted.section_id].append(r)
    by_section_gold = _group_by_section(gold)
    section_ids = set(by_section_results) | set(by_section_gold)

    per_section: list[PRF1] = []
    for section_id in section_ids:
        section_results = by_section_results.get(section_id, [])
        section_gold = by_section_gold.get(section_id, [])
        if not section_results and not section_gold:
            continue
        tp = sum(1 for r in section_results if r.matched_gold is not None)
        fp = sum(1 for r in section_results if r.matched_gold is None)
        fn = len(_false_negatives(section_results, section_gold))
        per_section.append(_prf1(tp, fp, fn))

    if not per_section:
        return _prf1(0, 0, 0)
    precision = sum(p.precision for p in per_section) / len(per_section)
    recall = sum(p.recall for p in per_section) / len(per_section)
    f1 = sum(p.f1 for p in per_section) / len(per_section)
    return PRF1(
        precision=precision,
        recall=recall,
        f1=f1,
        tp=sum(p.tp for p in per_section),
        fp=sum(p.fp for p in per_section),
        fn=sum(p.fn for p in per_section),
    )


def prf1_by_ngram_length(results: list[MatchResult], gold: list[GoldConcept]) -> dict[int, PRF1]:
    """Recall broken down by the GOLD concept's own n-gram length (1-4) -- the
    standard breakdown for a keyphrase-style task: does the system systematically
    miss longer phrases? Precision/F1 are reported for completeness but attributed to
    the *matched* gold concept's length (an unmatched prediction has no gold length,
    so it's excluded from this breakdown, not silently dropped from micro/macro).
    """
    by_length: dict[int, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for r in results:
        if r.matched_gold is not None:
            by_length[ngram_len(r.matched_gold.concept)]["tp"] += 1
    fns = _false_negatives(results, gold)
    for g in fns:
        by_length[ngram_len(g.concept)]["fn"] += 1
    return {
        length: _prf1(counts["tp"], counts["fp"], counts["fn"])
        for length, counts in by_length.items()
    }


def precision_by_role(results: list[MatchResult]) -> dict[str, PRF1]:
    """Precision-only breakdown by the *predicted* concept's role (gold concepts
    carry no role, so recall/F1 aren't meaningful per role)."""
    by_role: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0})
    for r in results:
        role = r.predicted.role
        if r.matched_gold is not None:
            by_role[role]["tp"] += 1
        else:
            by_role[role]["fp"] += 1
    return {role: _prf1(counts["tp"], counts["fp"], 0) for role, counts in by_role.items()}


@dataclass
class ErrorExample:
    section_id: str
    concept: str
    kind: str  # "false_positive" | "false_negative"


def sample_errors(
    results: list[MatchResult], gold: list[GoldConcept], *, n: int = 10
) -> list[ErrorExample]:
    false_positives = [
        ErrorExample(
            section_id=r.predicted.section_id,
            concept=r.predicted.canonical_name,
            kind="false_positive",
        )
        for r in results
        if r.matched_gold is None
    ]
    false_negatives = [
        ErrorExample(section_id=g.section_id, concept=g.concept, kind="false_negative")
        for g in _false_negatives(results, gold)
    ]
    return false_positives[:n] + false_negatives[:n]
