"""CR-011 §8 pair scorer: logistic regression + probability calibration + three-way operating policy, with the specified gradient-
boosted ablation. Development uses historical owner labels only (grouped cross-validation by normalised-form family);
SLEEP-240 held-out labels never enter. Out-of-fold probabilities are the only basis for any metric or threshold reported."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from cumap.eval.stats import wilson_ci
from cumap.sleep.features import FEATURES, GROUPS

SEED = 20261008
N_SPLITS = 5


def make_lr(c: float = 1.0):
    return LogisticRegression(C=c, class_weight="balanced", max_iter=2000, random_state=SEED)


def make_gb():
    return GradientBoostingClassifier(
        n_estimators=100, max_depth=2, learning_rate=0.1, subsample=0.8, random_state=SEED
    )


def _fit_predict(kind: str, xtr, ytr, xte):
    if kind == "lr":
        sc = StandardScaler().fit(xtr)
        m = make_lr().fit(sc.transform(xtr), ytr)
        return m.predict_proba(sc.transform(xte))[:, 1]
    m = make_gb().fit(xtr, ytr)
    return m.predict_proba(xte)[:, 1]


def oof_scores(x: np.ndarray, y: np.ndarray, groups: np.ndarray, kind: str = "lr") -> np.ndarray:
    """Out-of-fold raw scores with GroupKFold (a normalised-form family never straddles train and test)."""
    out = np.zeros(len(y))
    n_splits = min(N_SPLITS, len(set(groups)))
    for tr, te in GroupKFold(n_splits=n_splits).split(x, y, groups):
        out[te] = _fit_predict(kind, x[tr], y[tr], x[te])
    return out


def platt(raw: np.ndarray, y: np.ndarray):
    """Sigmoid calibration fitted on out-of-fold scores (small n: no isotonic)."""
    z = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / (1 - np.clip(raw, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    cal = LogisticRegression(C=1e6, max_iter=1000).fit(z, y)
    return cal


def apply_platt(cal, raw: np.ndarray) -> np.ndarray:
    z = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / (1 - np.clip(raw, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    return cal.predict_proba(z)[:, 1]


def calibration_report(p: np.ndarray, y: np.ndarray, bins: int = 5) -> dict:
    edges = np.linspace(0, 1, bins + 1)
    rows, ece = [], 0.0
    for lo, hi in pairwise(edges):
        m = (p >= lo) & ((p < hi) | (hi == 1.0) & (p <= hi))
        if m.any():
            conf, acc = float(p[m].mean()), float(y[m].mean())
            ece += m.mean() * abs(conf - acc)
            rows.append(
                {
                    "bin": [round(lo, 2), round(hi, 2)],
                    "n": int(m.sum()),
                    "mean_pred": conf,
                    "frac_pos": acc,
                }
            )
    return {"brier": float(brier_score_loss(y, p)), "ece": float(ece), "bins": rows}


def discrimination(p: np.ndarray, y: np.ndarray) -> dict:
    if len(set(y)) < 2:
        return {"auc": None, "average_precision": None}
    return {
        "auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
    }


@dataclass
class Operating:
    t_auto: float | None
    t_review: float | None
    auto_status: str
    detail: dict


def choose_thresholds(p: np.ndarray, y: np.ndarray, *, review_recall: float = 0.90) -> Operating:
    """`t_auto` = the smallest threshold with precision >= 0.98 AND Wilson 95% lower bound >= 0.95 (the CR's safety criterion,
    applied when the sample permits); otherwise ML auto-merge is DISABLED and the scorer is review-ranking only.
    `t_review` = the largest threshold that still recovers `review_recall` of the gold SAME cases (a recall-driven proposal;
    the queue-size side is reported separately)."""
    order = np.unique(np.round(p, 6))
    best = None
    for t in sorted(order):
        sel = p >= t
        k, n = int(y[sel].sum()), int(sel.sum())
        if n == 0:
            continue
        prec = k / n
        w = wilson_ci(k, n)
        if prec >= 0.98 and w.low >= 0.95:
            best = {"t": float(t), "precision": prec, "k": k, "n": n, "wilson_low": w.low}
            break
    pos = np.sort(p[y == 1])
    t_review = None
    if len(pos):
        idx = int(np.floor((1 - review_recall) * len(pos)))
        t_review = float(pos[min(idx, len(pos) - 1)])
    if best is None:
        cand = {}
        for t in sorted(order):
            sel = p >= t
            if sel.sum():
                w = wilson_ci(int(y[sel].sum()), int(sel.sum()))
                cand[float(t)] = (float(y[sel].mean()), w.low, int(sel.sum()))
        top = max(cand.items(), key=lambda kv: (kv[1][1], kv[0])) if cand else None
        return Operating(
            None,
            t_review,
            "DISABLED: no threshold meets precision >= 0.98 with Wilson lower >= 0.95",
            {"best_wilson_lower_over_thresholds": top},
        )
    return Operating(best["t"], t_review, "ENABLED (development, labelled distribution only)", best)


def evaluate(x: np.ndarray, y: np.ndarray, groups: np.ndarray, kind: str, cols: list[str]) -> dict:
    idx = [FEATURES.index(c) for c in cols]
    raw = oof_scores(x[:, idx], y, groups, kind)
    return {"oof_raw": raw, **discrimination(raw, y)}


def group_ablation(x: np.ndarray, y: np.ndarray, groups_arr: np.ndarray) -> dict:
    out = {}
    base = evaluate(x, y, groups_arr, "lr", FEATURES)
    out["all_features"] = {k: base[k] for k in ("auc", "average_precision")}
    for g, cols in GROUPS.items():
        keep = [c for c in FEATURES if c not in cols]
        r = evaluate(x, y, groups_arr, "lr", keep)
        out[f"without_{g}"] = {
            "auc": r["auc"],
            "average_precision": r["average_precision"],
            "delta_auc": (r["auc"] - base["auc"])
            if r["auc"] is not None and base["auc"] is not None
            else None,
        }
    for g, cols in GROUPS.items():
        r = evaluate(x, y, groups_arr, "lr", cols)
        out[f"only_{g}"] = {"auc": r["auc"], "average_precision": r["average_precision"]}
    return out


warnings.filterwarnings("ignore", category=UserWarning)
