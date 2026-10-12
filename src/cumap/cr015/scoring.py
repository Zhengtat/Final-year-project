"""CR-015 frozen scorer definition (nested-aware). Scoring is a function of the SET of predicted mention spans, independent of how a system placed them, so placement policies
(longest-match, nested-aware, a system's own mention records) are all scored by the same code. Built on the frozen CR-014 span matcher; nothing in CR-014 is changed.

Definitions (frozen with this module's hash in `reports/cr015/FREEZE_SCORER.json`):
- Mention-level span-exact P/R/F1: a predicted mention is correct iff its (start, end) equals a gold mention's (start, end) in the same section.
- Placement views of a surface list: `longest_match` = CR-014's rule-17 placement (longest first, no overlap); `nested_aware_all` = every occurrence of every accepted surface.
  (A system with its own placement policy supplies its own spans and is scored directly.)
- Nested slices: gold mentions flagged `nested_valid` vs not; a predicted mention is "nested" if it strictly contains or is strictly contained in another predicted mention.
- Over-long / under-long false positives: an unmatched predicted span that contains a gold span / lies inside a gold span (`classify_boundary`).
- Distinct-surface view: per section, the set of normalised predicted surfaces vs the set of normalised gold surfaces.
Gold is read only through the arguments; this module never opens a file."""

from __future__ import annotations

from cumap.cr014.pilot_score import GoldMention, Span, classify_boundary, place, score

__all__ = ["GoldMention", "Span", "classify_boundary", "place", "placement_views", "score_mentions"]

_norm = lambda s: " ".join(s.lower().split())


def placement_views(
    surfaces: dict[str, list[str]], texts: dict[str, str]
) -> dict[str, dict[str, list[Span]]]:
    return {
        "longest_match": {sid: place(s, texts[sid]) for sid, s in surfaces.items()},
        "nested_aware_all": {sid: place(s, texts[sid], nested=True) for sid, s in surfaces.items()},
    }


def _is_nested(sp: Span, others: list[Span]) -> bool:
    return any(
        o != sp and ((o[0] <= sp[0] and sp[1] <= o[1]) or (sp[0] <= o[0] and o[1] <= sp[1]))
        for o in others
    )


def score_mentions(
    pred: dict[str, list[Span]], gold: list[GoldMention], texts: dict[str, str]
) -> dict:
    base = score(pred, gold, texts)
    sids = sorted(pred)
    nested_gold = [m for m in gold if m.section_id in sids and m.nested_valid]
    flat_gold = [m for m in gold if m.section_id in sids and not m.nested_valid]
    pset = {sid: set(pred[sid]) for sid in sids}
    hit = lambda ms: sum((m.start, m.end) in pset[m.section_id] for m in ms)
    pn_tp = pn = pf_tp = pf = 0
    for sid in sids:
        g = {(m.start, m.end) for m in gold if m.section_id == sid}
        for sp in pred[sid]:
            if _is_nested(sp, pred[sid]):
                pn += 1
                pn_tp += sp in g
            else:
                pf += 1
                pf_tp += sp in g
    gs = {
        sid: {_norm(texts[sid][m.start : m.end]) for m in gold if m.section_id == sid}
        for sid in sids
    }
    tp = fp = fn = 0
    for sid in sids:
        ps = {_norm(texts[sid][a:b]) for a, b in pred[sid]}
        tp, fp, fn = tp + len(ps & gs[sid]), fp + len(ps - gs[sid]), fn + len(gs[sid] - ps)
    p, r = (tp / (tp + fp) if tp + fp else 0.0), (tp / (tp + fn) if tp + fn else 0.0)
    cats = base["false_positive_boundary_categories"]
    return {
        **base,
        "nested_gold_recall": {"n": len(nested_gold), "recall": hit(nested_gold) / len(nested_gold) if nested_gold else None},
        "non_nested_gold_recall": {"n": len(flat_gold), "recall": hit(flat_gold) / len(flat_gold) if flat_gold else None},
        "predicted_nested": {"n": pn, "precision": pn_tp / pn if pn else None},
        "predicted_non_nested": {"n": pf, "precision": pf_tp / pf if pf else None},
        "over_long_fp": cats.get("over_specific_contains_gold", 0),
        "under_long_fp": cats.get("over_general_inside_gold", 0),
        "distinct_surface": {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0},
    }  # fmt: skip
