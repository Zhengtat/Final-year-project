"""CR-011 STOP 2 driver ($0, local): candidate recall on historical labels, scorer development, calibration, proposed operating
points, predicted review volume. Gold files are read through a caller-supplied directory; nothing is written there.

    uv run python -m cumap.sleep.stop2 scorer --gold-dir <dir with the owner's historical merge sheets>
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from cumap.config import REPO_ROOT
from cumap.sleep import build as B
from cumap.sleep import features as F
from cumap.sleep import labels as L
from cumap.sleep import scorer as S
from cumap.sleep.typecompat import TypeMap

OUT = REPO_ROOT / "data/interim/sleep"
LOGIT = lambda p: np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))


class Vectoriser:
    """Embeddings for real nodes (precomputed) and string pseudo-nodes (encoded on demand)."""

    def __init__(self, vec):
        from sentence_transformers import SentenceTransformer

        self.vec, self.model, self.cache = (
            vec,
            SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2"),
            {},
        )
        self.row = {i: k for k, i in enumerate(vec.ids)}

    def enc(self, text: str) -> np.ndarray:
        if text not in self.cache:
            v = np.asarray(self.model.encode(text, show_progress_bar=False), dtype=float)
            self.cache[text] = v / (np.linalg.norm(v) or 1)
        return self.cache[text]

    def __call__(self, node) -> F.Vecs:
        r = self.row.get(node.id)
        if r is not None:
            return F.Vecs(
                self.vec.name[r],
                self.vec.definition[r] if self.vec.has_definition[r] else None,
                self.vec.evidence[r],
            )
        ev = F.evidence_for(node)
        return F.Vecs(self.enc(node.name), None, self.enc(ev) if ev else None)


def erst_linked_set(snap, sections) -> set[frozenset[str]]:
    from cumap.cr010.p3 import GRAPH, linked_pairs
    from cumap.expert_kg.pipeline import _restore_concept_registry, load_checkpoint

    cp = load_checkpoint(snap.path.parent)
    concepts = _restore_concept_registry(cp, lambda t: np.zeros(1)).all()
    return set(linked_pairs(json.loads(GRAPH.read_text()), sections, concepts))


def build_dataset(
    items: list[L.Labelled], vz, ctx, types, erst
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows, y, g = [], [], []
    for it in items:
        rows.append(
            F.pair_features(it.node_a, it.node_b, vz(it.node_a), vz(it.node_b), ctx, types, erst)
        )
        y.append(it.label)
        g.append(it.group)
    return F.matrix(rows), np.array(y), np.array(g)


def run_scorer(gold_dir: Path) -> dict:
    sections, snap, lex, ctx, vec = B.load_all()
    types = TypeMap.load()
    vz = Vectoriser(vec)
    erst = erst_linked_set(snap, sections)
    cs = B.candidates(snap, vec, ctx)
    hist = L.load_historical(gold_dir)
    neg_lex, pos_lex = L.lexicon_pairs(lex)
    for lst in (hist, neg_lex, pos_lex):
        L.resolve(lst, snap, ctx.cfg)
    L.groups(hist + neg_lex, ctx.cfg)
    # ---- candidate recall of the labelled SAME pairs that exist as distinct snapshot nodes
    res_count = Counter((h.label, h.resolution) for h in hist)
    pos_distinct = [h for h in hist if h.label == 1 and h.resolution == "distinct_nodes"]
    covered = [h for h in pos_distinct if frozenset((h.node_a.id, h.node_b.id)) in cs.signals]
    by_sig = Counter(s for h in covered for s in cs.signals[frozenset((h.node_a.id, h.node_b.id))])
    lex_neg_nodes = [h for h in neg_lex if h.resolution == "distinct_nodes"]
    recall = {
        "labelled_pairs": len(hist),
        "by_label_and_resolution": {
            f"{'SAME' if k[0] else 'NOT_SAME'}/{k[1]}": v for k, v in sorted(res_count.items())
        },
        "same_pairs_that_are_distinct_nodes": len(pos_distinct),
        "same_pairs_already_co_clustered_by_baseline": res_count[(1, "same_node")],
        "candidate_recall_on_distinct": (len(covered) / len(pos_distinct))
        if pos_distinct
        else None,
        "covered": len(covered),
        "covering_signals": dict(by_sig),
        "lexicon_different_pairs_as_distinct_nodes": len(lex_neg_nodes),
        "lexicon_different_pairs_in_candidates": sum(
            frozenset((h.node_a.id, h.node_b.id)) in cs.signals for h in lex_neg_nodes
        ),
        "lexicon_same_pairs_as_distinct_nodes": sum(
            h.resolution == "distinct_nodes" for h in pos_lex
        ),
        "note": "positives that were already merged online (same_node) are baseline successes; partial/strings are not nodes of this snapshot",
    }
    # ---- name-level replay: had the alias string been a separate provisional node, would retrieval have proposed its partner?
    # (the partner's ALIASES are excluded, otherwise the check is circular: the alias is now one of the node's forms)
    from cumap.expert_kg.alias_rules import r1_key as _r1
    from cumap.sleep.candidates import tokens as _tok

    nvec = vec.name
    replay = Counter()
    n_replay = 0
    for h in hist:
        if h.label != 1:
            continue
        pair_nodes = [
            n for n in (h.node_a, h.node_b) if n is not None and not n.id.startswith("label:")
        ]
        # the real node's canonical name vs the other string (the one that is not the canonical name)
        cand = None
        for node in {n.id: n for n in pair_nodes}.values():
            for probe in (h.a, h.b):
                if probe.casefold() != node.name.casefold() and (
                    h.a.casefold() == node.name.casefold()
                    or h.b.casefold() == node.name.casefold()
                    or h.resolution == "distinct_nodes"
                ):
                    cand = (probe, node)
        if cand is None:
            continue
        probe, node = cand
        n_replay += 1
        sig = set()
        if _r1(probe, ctx.cfg) == _r1(node.name, ctx.cfg):
            sig.add("r1_key")
        tp, tn = _tok(probe), _tok(node.name)
        if len(tp) >= 2 and len(tn) >= 2 and len(tp & tn) / len(tp | tn) >= 0.5:
            sig.add("token_overlap")
        v = vz.enc(probe)
        sims = nvec @ v
        order = np.argsort(-sims)
        rank = int(np.where(np.array(vec.ids)[order] == node.id)[0][0]) + 1
        if rank <= 20:
            sig.add("name_embedding_top20")
        if rank <= 5:
            sig.add("name_embedding_top5")
        for sname in sig:
            replay[sname] += 1
        replay["any_of_r1_token_name20"] += bool(
            sig & {"r1_key", "token_overlap", "name_embedding_top20"}
        )
        replay["_ranks"] = replay.get("_ranks", 0)
    recall["name_level_replay"] = {
        "same_pairs_replayed": n_replay,
        "retrieved_by": {k: v for k, v in replay.items() if not k.startswith("_")},
        "union_recall": (replay["any_of_r1_token_name20"] / n_replay) if n_replay else None,
        "note": "definition/evidence/graph signals are unavailable for a bare alias string, so this is a conservative (name-only) recall",
    }
    # ---- training data: owner labels (+ the approved lexicon `different` pairs as negatives); R0 `same` entries are
    # deterministic-path positives and are kept OUT of training so the scorer learns the non-R0 judgement
    train = hist + neg_lex
    x, y, g = build_dataset(train, vz, ctx, types, erst)
    out = {
        "recall": recall,
        "n_train": len(y),
        "n_pos": int(y.sum()),
        "n_neg": int((1 - y).sum()),
        "groups": len(set(g)),
    }
    lr = S.evaluate(x, y, g, "lr", F.FEATURES)
    gb = S.evaluate(x, y, g, "gb", F.FEATURES)
    cal = S.platt(lr["oof_raw"], y)
    p_lr = S.apply_platt(cal, lr["oof_raw"])
    out["logistic"] = {
        "auc": lr["auc"],
        "average_precision": lr["average_precision"],
        "calibration": S.calibration_report(p_lr, y),
        "calibration_before_platt": S.calibration_report(lr["oof_raw"], y),
    }
    out["boosted_ablation"] = {"auc": gb["auc"], "average_precision": gb["average_precision"]}
    op = S.choose_thresholds(p_lr, y)
    out["operating_point_dev_labelled_distribution"] = {
        "t_auto": op.t_auto,
        "t_review": op.t_review,
        "auto_status": op.auto_status,
        "detail": op.detail,
    }
    out["group_ablation"] = S.group_ablation(x, y, g)
    # slices on the out-of-fold calibrated scores
    one = np.array([1.0 if r else 0.0 for r in x[:, F.FEATURES.index("one_token_any")]]).astype(
        bool
    )
    slices = {}
    for name, m in (("one_token_any", one), ("multi_token", ~one)):
        if m.sum() and len(set(y[m])) > 1:
            slices[name] = {
                "n": int(m.sum()),
                "pos": int(y[m].sum()),
                **S.discrimination(p_lr[m], y[m]),
            }
        else:
            slices[name] = {"n": int(m.sum()), "pos": int(y[m].sum())}
    out["slices"] = slices
    # ---- final model on all labels, applied to the candidate pool under the hard guards
    sc = S.StandardScaler().fit(x)
    final = S.make_lr().fit(sc.transform(x), y)
    pool = sorted(cs.signals, key=lambda p: tuple(sorted(p)))
    feats, vetoed = [], Counter()
    keep = []
    for p in pool:
        a, b = (snap.nodes[i] for i in sorted(p))
        if lex.is_different(a.name, b.name) or any(
            lex.is_different(fa, fb) for fa in a.forms() for fb in b.forms()
        ):
            vetoed["lexicon_different"] += 1
            continue
        if not types.compatible(a.type, b.type):
            vetoed["type_incompatible"] += 1
            continue
        keep.append(p)
        feats.append(F.pair_features(a, b, vz(a), vz(b), ctx, types, erst))
    xp = F.matrix(feats)
    raw = final.predict_proba(sc.transform(xp))[:, 1]
    pc = S.apply_platt(cal, raw)
    prior_train = float(y.mean())
    scen = {}
    for pi in (None, 0.05, 0.02, 0.01, 0.005):
        adj = (
            pc
            if pi is None
            else 1
            / (
                1
                + np.exp(
                    -(LOGIT(pc) - np.log(prior_train / (1 - prior_train)) + np.log(pi / (1 - pi)))
                )
            )
        )
        row = {}
        if op.t_review is not None:
            lo, hi = op.t_review, op.t_auto if op.t_auto is not None else 1.01
            row["review_band_pairs"] = int(((adj >= lo) & (adj < hi)).sum())
            row["above_review_pairs"] = int((adj >= lo).sum())
        if op.t_auto is not None:
            row["auto_pairs"] = int((adj >= op.t_auto).sum())
        scen["uncorrected" if pi is None else f"assumed_pool_base_rate_{pi}"] = row
    out["candidate_pool"] = {
        "candidates": len(pool),
        "vetoed_before_scoring": dict(vetoed),
        "scored": len(keep),
        "score_quantiles": {str(q): float(np.quantile(pc, q)) for q in (0.5, 0.9, 0.99, 0.999)},
        "training_prior": prior_train,
        "predicted_review_volume": scen,
        "caveat": "UNVALIDATED: the scorer is trained on a positive-skewed set of owner-reviewed pairs, not on the candidate pool; the pool base rate is unknown until SLEEP-240 dev labels exist, so the volumes are scenarios, not forecasts",
    }
    out["features_absent"] = ["concept_score (not stored on checkpoint nodes)"]
    out["candidates"] = {**cs.counts(), "per_node": cs.counts()["union"] * 2 / len(snap.nodes)}
    out["one_token"] = {
        "one_token_nodes": sum(n.one_token for n in snap.nodes.values()),
        "candidates_with_one_token_node": sum(
            any(snap.nodes[i].one_token for i in p) for p in cs.signals
        ),
        "one_token_pairs_with_only_embedding_signals": sum(
            any(snap.nodes[i].one_token for i in p)
            and sig
            <= {"name_embedding", "definition_embedding", "evidence_embedding", "graph_neighbours"}
            for p, sig in cs.signals.items()
        ),
        "rule": "embedding-only one-token auto-merge is forbidden; such pairs can only reach review",
    }
    (OUT / "stop2_scorer.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out


def pool_features(snap, sections, ctx, vec, cs, types, lex, vz, erst):
    """Features and guard flags for every candidate pair (cached on disk)."""
    import pickle

    cache = OUT / f"pool_features_{snap.sha256[:12]}.pkl"
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    cp = json.loads(snap.path.read_text())
    tax = {frozenset((r["concept_id"], r["matched_concept_id"])) for r in cp["taxonomy_candidates"]}
    tax |= {frozenset((r["concept_id"], r["related_concept_id"])) for r in cp["related_candidates"]}
    out = {}
    for p in sorted(cs.signals, key=lambda q: tuple(sorted(q))):
        a, b = (snap.nodes[i] for i in sorted(p))
        feats = F.pair_features(a, b, vz(a), vz(b), ctx, types, erst)
        flags = {
            "lexicon_different": lex.is_different(a.name, b.name)
            or any(lex.is_different(fa, fb) for fa in a.forms() for fb in b.forms()),
            "type_incompatible": not types.compatible(a.type, b.type),
            "taxonomy": p in tax,
        }
        out[p] = (feats, flags)
    cache.write_bytes(pickle.dumps(out))
    return out


def run_sleep240() -> dict:
    from cumap.sleep import sleep240 as Z

    sections, snap, lex, ctx, vec = B.load_all()
    types = TypeMap.load()
    vz = Vectoriser(vec)
    erst = erst_linked_set(snap, sections)
    cs = B.candidates(snap, vec, ctx)
    pf = pool_features(snap, sections, ctx, vec, cs, types, lex, vz, erst)
    strong = {p for p, (f, fl) in pf.items() if (cs.signals[p] & Z.DET) or f["name_cos"] >= 0.85}

    def risky(x, y):
        pr = frozenset((x, y))
        if pr in pf:
            f, fl = pf[pr]
            return fl["type_incompatible"] or fl["lexicon_different"] or f["name_cos"] < 0.6
        a, b = snap.nodes[x], snap.nodes[y]
        return not types.compatible(a.type, b.type)

    bridges = Z.bridge_pairs(strong, risky)
    pool = {}
    for p, (f, fl) in pf.items():
        a, b = (snap.nodes[i] for i in sorted(p))
        m = Z.membership(a, b, f, cs.signals[p], fl, bridges)
        if m:
            pool[tuple(sorted(p))] = m
    for p in bridges:  # bridge pairs need not be candidates themselves
        tp = tuple(sorted(p))
        if tp not in pool:
            pool[tp] = ["cluster_bridge_transitive_risk"]
    items, rep = Z.allocate(pool)
    out = {"strata_availability": rep, "bridge_pairs": len(bridges), "strong_edges": len(strong)}
    if rep["shortfall"]:
        out["status"] = "SHORTFALL: cannot fill every stratum under the frozen design"
        (OUT / "stop2_sleep240.json").write_text(
            json.dumps(out, indent=1, default=str), encoding="utf-8"
        )
        return out
    Z.families(items, snap.nodes, ctx.cfg)
    sp = Z.split(items)
    out["split"] = sp
    if sp["status"] != "ok":
        out["status"] = "SPLIT FAILED"
        (OUT / "stop2_sleep240.json").write_text(
            json.dumps(out, indent=1, default=str), encoding="utf-8"
        )
        return out
    out["leakage"] = Z.leakage_check(items, snap.nodes, ctx.cfg)
    if not out["leakage"]["ok"]:
        out["status"] = "LEAKAGE"
        return out
    d = REPO_ROOT / "data/interim/checks/cr011"
    out["files"] = Z.sheets(items, snap.nodes, snap.run_id, d)
    for sname in ("dev", "heldout"):
        Z.assert_blind(d / f"sleep240_{sname}_blind_sheet.csv")
    out["summary"] = Z.summary(items)
    out["status"] = "ok"
    (OUT / "stop2_sleep240.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["scorer", "sleep240"])
    ap.add_argument("--gold-dir")
    a = ap.parse_args()
    if a.phase == "sleep240":
        print(json.dumps(run_sleep240(), indent=1, default=str))
    else:
        print(json.dumps(run_scorer(Path(a.gold_dir)), indent=1, default=str))


if __name__ == "__main__":
    main()
