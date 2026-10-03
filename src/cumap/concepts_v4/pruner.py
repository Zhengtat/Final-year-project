"""CR-009 §5: the pruner (SAC-KG-inspired): a small local growing/pruned classifier on a TERM's form.

P1 = logistic regression on the term's embedding plus a few surface features. It decides, for each verified NEW
concept, whether it becomes a node (growing) or goes to pruned.jsonl. Rows come from IIR dev ONLY; the general-
knowledge bank and CSO membership are FEATURES, never a source of rows. Leave-one-chapter-out models score the
held-out chapter so no chapter is pruned by a model trained on its own gold. P2 (T5 + LoRA) is not built here."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import numpy as np
from sklearn.linear_model import LogisticRegression

from cumap.expert_kg.stats import extract_candidate_terms

_UNIT = re.compile(r"\d|\b(?:kb|mb|gb|ms|mbps|gbps|hz|khz|mhz|bytes?|bits?)\b", re.IGNORECASE)


def norm(t: str) -> str:
    return " ".join(t.lower().split())


def term_features(
    term: str, nlp, bank: set[str] | None = None, cso: set[str] | None = None
) -> list[float]:
    doc = nlp(term)
    toks = [t for t in doc if not t.is_punct]
    return [
        float(len(toks)),
        float(bool(_UNIT.search(term))),
        float(term.isupper() and len(term) >= 2),
        float(any(t.pos_ == "VERB" for t in toks)),  # noun phrase vs clause
        float(norm(term) in (bank or set())),
        float(norm(term) in (cso or set())),
    ]


def build_rows(
    gold_by_section: dict[str, set[str]],
    cand_by_section: dict[str, set[str]],
    sections_in_train: Iterable[str],
) -> list[tuple[str, int]]:
    """(term, label) rows over the training sections only: growing = gold in ANY training section;
    pruned = a candidate noun phrase that is gold in none of them. Deduplicated per term."""
    secs = list(sections_in_train)
    gold = set().union(*(gold_by_section.get(s, set()) for s in secs)) if secs else set()
    cand = set().union(*(cand_by_section.get(s, set()) for s in secs)) if secs else set()
    return [(t, 1) for t in sorted(gold)] + [(t, 0) for t in sorted(cand - gold)]


@dataclass
class P1Model:
    embed_fn: Callable[[str], np.ndarray]
    nlp: object
    bank: set[str] = field(default_factory=set)
    cso: set[str] = field(default_factory=set)
    clf: LogisticRegression | None = None
    cache: dict[str, np.ndarray] = field(default_factory=dict)

    def _vec(self, term: str) -> np.ndarray:
        k = norm(term)
        if k not in self.cache:
            e = np.asarray(self.embed_fn(term), dtype=float)
            self.cache[k] = np.concatenate([e, term_features(term, self.nlp, self.bank, self.cso)])
        return self.cache[k]

    def fit(self, rows: list[tuple[str, int]]) -> P1Model:
        x = np.stack([self._vec(t) for t, _ in rows])
        y = np.array([lab for _, lab in rows])
        self.clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced").fit(x, y)
        return self

    def p_growing(self, term: str) -> float:
        assert self.clf is not None, "fit the pruner first"
        return float(
            self.clf.predict_proba(self._vec(term).reshape(1, -1))[
                0, list(self.clf.classes_).index(1)
            ]
        )


def dev_rows(
    gold_rows: list[dict], sections: list[dict], nlp
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Per-section gold terms (names and aliases) and candidate noun phrases for the IIR dev sections."""
    gold: dict[str, set[str]] = {}
    for r in gold_rows:
        if str(r["is_gold"]) == "True":
            forms = {r["concept"], *eval(r["aliases"])}
            gold.setdefault(r["section_id"], set()).update(norm(f) for f in forms)
    cand = {
        s["section_id"]: {norm(t) for t in extract_candidate_terms(s["text"], nlp)}
        for s in sections
    }
    return gold, cand


def is_value_like(term: str) -> bool:
    return bool(_UNIT.search(term))


def choose_tau(
    p_by_item: list[tuple[str, float]],
    score_at: Callable[[float], dict],
    base: dict,
    grid: Iterable[float],
) -> tuple[float, list[dict]]:
    """Pre-registered rule (CR-009 §5.4): the highest exact micro F1 among tau values whose recall drops by <= 0.01
    relative to no pruner; if no tau > 0 qualifies, tau = 0. `score_at(tau)` -> {'f1', 'recall'}."""
    table, best = [], (0.0, base["f1"])
    for tau in grid:
        s = score_at(tau)
        ok = base["recall"] - s["recall"] <= 0.01
        table.append({"tau": tau, **s, "eligible": ok})
        if tau > 0 and ok and s["f1"] > best[1]:
            best = (tau, s["f1"])
    return best[0], table
