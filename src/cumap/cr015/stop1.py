"""CR-015 STOP 1 ($0, no model call): reproduce the frozen CR-014 V3 error counts from saved artefacts and locate where nested mentions are suppressed, over-long spans
appear, boundary and concepthood are conflated and accepted concepts are lost at placement. Development-only: the CR-014 held-out is now exposed, so reading its gold
here is permitted analysis, never a held-out claim."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import spacy
import yaml

from cumap.cr014 import heldout_run as H
from cumap.cr014.pilot_score import load_gold, place
from cumap.cr014.union import build_section_union
from cumap.expert_kg.alias_rules import AliasConfig

ROOT = Path(".")
OUT = ROOT / "reports/cr015"
MAN = yaml.safe_load((ROOT / "configs/cr014_manifest.yaml").read_text())
SECS = MAN["heldout_sealed"]
norm = lambda s: " ".join(s.lower().split())


def main() -> dict:
    nlp, cfg = spacy.load("en_core_web_sm"), AliasConfig.load()
    gold = load_gold(
        ROOT / "data/gold/pd_concept_test_blind.csv",
        ROOT / "data/interim/checks/cr014/pd_concept_test_sentences.csv",
    )
    texts = {s: H.section_row(s)["text"] for s in SECS}
    res: dict = {"placement_loss": Counter(), "over_long": Counter(), "over_long_words": Counter(), "verifier_rejections_of_gold_surfaces": Counter(),
                 "boundary_loss_causes": Counter(), "families": Counter(), "calls": 0}  # fmt: skip
    nested_unplaced_valid = 0
    for sid in SECS:
        text = texts[sid]
        v3 = json.loads((H.OUT / f"V3_{sid}.json").read_text())
        out, meta = v3["outcome"], v3["meta"]
        acc = out["accepted"]
        placed = place(sorted(acc), text)
        placed_set = set(placed)
        g = [m for m in gold if m.section_id == sid]
        gset = {(m.start, m.end) for m in g}
        row = H.section_row(sid)
        sec = {"section_id": sid, "text": text, "heading": sid, "chapter_num": row["chapter_num"]}
        u = build_section_union(
            sec, set(row.get("emphasized_terms") or []), nlp, cfg, H.u0_surfaces(sid)[1]
        )
        verdict_of = {
            v["surface"]: v["verdict"] for v in out["verdicts"].values() if "surface" in v
        }
        decisions_by_surface: dict[str, set[str]] = {}
        rej_members: dict[str, set[str]] = {}
        replaced: dict[str, set[str]] = {}
        by_id = {c.cid: c.surface for c in u.cands.values()}
        for decs in out["boundary"].values():
            for d in decs:
                if d["surface"]:
                    decisions_by_surface.setdefault(norm(d["surface"]), set()).add(
                        d["decision"] + ":" + d["reason_code"]
                    )
                    for cid in d["source_candidate_ids"]:
                        if by_id.get(cid) and norm(d["surface"]) != by_id[cid]:
                            replaced.setdefault(by_id[cid], set()).add(d["decision"])
                else:
                    for cid in d["source_candidate_ids"]:
                        rej_members.setdefault(by_id.get(cid, ""), set()).add(
                            "REJECT:" + d["reason_code"]
                        )
        unaddressed = {by_id.get(c, "") for c in out["unaddressed"]}
        res["families"]["families"] += meta["families"]
        res["families"]["candidates"] += meta["candidates"]
        res["families"]["multi_member_families_sent_to_boundary"] += len(out["boundary"])
        res["calls"] += meta["calls"]
        for m in g:
            surf = norm(text[m.start : m.end])
            if (m.start, m.end) in placed_set:
                continue
            if surf in acc:  # accepted surface, this mention not placed
                cover = [
                    p
                    for p in placed
                    if p[0] <= m.start and m.end <= p[1] and (p[0], p[1]) != (m.start, m.end)
                ]
                part = [p for p in placed if p[0] < m.end and m.start < p[1]]
                kind = (
                    "suppressed_inside_longer_placed_span"
                    if cover
                    else ("partial_overlap_with_placed_span" if part else "unplaced_no_overlap")
                )
                res["placement_loss"][kind] += 1
                res["placement_loss"][
                    "nested_valid_gold_among_lost"
                    if m.nested_valid
                    else "not_nested_valid_among_lost"
                ] += 1
                nested_unplaced_valid += int(m.nested_valid and bool(cover))
            elif surf in u.cands:
                if surf in verdict_of:
                    res["verifier_rejections_of_gold_surfaces"][verdict_of[surf]] += 1
                elif surf in rej_members:
                    res["boundary_loss_causes"][min(rej_members[surf])] += 1
                elif surf in replaced:
                    res["boundary_loss_causes"][
                        "replaced_by_a_different_span_(" + min(replaced[surf]) + ")"
                    ] += 1
                elif surf in unaddressed:
                    res["boundary_loss_causes"]["unaddressed_by_boundary_decisions"] += 1
                else:
                    res["boundary_loss_causes"]["other_not_verified"] += 1
        for p in (
            placed
        ):  # over-long: a placed span that strictly contains a gold span and is not itself gold
            if p in gset:
                continue
            inner = [q for q in gset if p[0] <= q[0] and q[1] <= p[1] and q != p]
            if inner:
                s = norm(text[p[0] : p[1]])
                res["over_long"]["placed_spans_containing_a_gold_span"] += 1
                res["over_long_words"][str(min(len(s.split()), 6))] += 1
                for k in decisions_by_surface.get(
                    s, {"no boundary decision (pass-through singleton family or U2 candidate)"}
                ):
                    res["over_long"]["origin:" + k] += 1
    res["placement_loss"]["nested_valid_gold_suppressed_by_longer_span"] = nested_unplaced_valid
    res = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in res.items()}
    (OUT / "stop1_analysis.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
