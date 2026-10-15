"""CR-019 Stage 0 + Stage A ($0, no model call). Reads frozen runs and gold; writes only reports/cr019/.

    uv run python -m cumap.cr019.run            # stage0 (train/dev + P&D pilot) and stage A (frozen held-out runs, pre-registered variants)

Stage 0 uses SciNLP train/dev and the P&D development (pilot) sheet only; the pre-registration in DECISIONS.md (2026-10-15) was written from it
before Stage A touched the held-out runs. Stage A never tunes anything: every variant is scored once and printed beside the frozen numbers."""

from __future__ import annotations

import bisect
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012 import attribution as A
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import no_relation_pairs, sc_attribution
from cumap.cr017 import headline as HL
from cumap.cr017 import run as R17
from cumap.cr019 import variants as V

OUT = REPO_ROOT / "reports/cr019"
SC_DOCS = ["2021.acl-long.353", "2024.acl-long.108-1-9.grobid", "P17-1058.grobid"]
FROZEN_012 = REPO_ROOT / "reports/cr012/stop4_heldout_results.json"
FROZEN_017 = REPO_ROOT / "reports/cr017/headline_metrics.json"


def sc_run_id(dk: str, level: str = "E0") -> str:
    return f"cr012_scinlp_heldout_{dk.replace('.', '_').replace('-', '_')}_{level}"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def source_files() -> list[Path]:
    fs = [PG.run_path(sc_run_id(d)) / "checkpoint.json" for d in SC_DOCS]
    for tag in ("heldout", "pilot"):
        sheet, secs = R17.SHEETS[tag]
        fs += [REPO_ROOT / sheet] + [
            PG.run_path(r) / "checkpoint.json" for r in R17.run_ids(tag, "E0", secs).values()
        ]
    return [f for f in fs if f.exists()] + [FROZEN_012, FROZEN_017]


# ---------------------------------------------------------------- Stage 0 (no held-out data)
_norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())


def _key(a, b, r, sym):
    return (frozenset((a, b)), r) if r in sym else (a, b, r)


def stage0_scinlp() -> dict:
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    out = {}
    for split in ("train", "dev"):
        docs, gold = {d.doc_key: d for d in ad.load_documents(split)}, ad.gold(split)
        dist, tokd, n = Counter(), [], 0
        cooc = annot = 0
        tot = defaultdict(lambda: [0, 0, 0])
        for k, g in gold.items():
            d = docs[k]
            sid = lambda t, d=d: bisect.bisect_right(d.sentence_ends, t)
            F = lambda sp, d=d: _norm(" ".join(d.tokens[sp[0] : sp[1]]))
            G = {_key(r.src_span, r.tgt_span, r.relation, sym) for r in g.relations}
            ment = defaultdict(list)
            for m in g.mentions:
                ment[F(m.span)].append(m.span)
            by_sent = defaultdict(set)
            for m in g.mentions:
                by_sent[sid(m.span[0])].add(F(m.span))
            rel_s, crel = set(), {}
            for r in g.relations:
                n += 1
                dd = abs(sid(r.src_span[0]) - sid(r.tgt_span[0]))
                dist[
                    "same_sentence"
                    if dd == 0
                    else "adjacent"
                    if dd == 1
                    else "2_3"
                    if dd <= 3
                    else "4_plus"
                ] += 1
                tokd.append(abs(r.src_span[0] - r.tgt_span[0]))
                rel_s.add((sid(r.src_span[0]), frozenset((F(r.src_span), F(r.tgt_span)))))
                crel.setdefault((F(r.src_span), F(r.tgt_span), r.relation), []).append(
                    sid(r.src_span[0])
                )
            pairs = {p for _, p in rel_s if len(p) == 2}
            for s, forms in by_sent.items():
                for p in pairs:
                    if p <= forms:
                        cooc += 1
                        annot += (s, p) in rel_s
            ins = lambda f, s, ment=ment, sid=sid: [m for m in ment[f] if sid(m[0]) == s]
            win = lambda f, s, w, ment=ment, sid=sid: [
                m for m in ment[f] if abs(sid(m[0]) - s) <= w
            ]
            P = {x: set() for x in ("P1", "P2", "P3", "P4", "P5")}
            for (a, b, rel), sents in crel.items():
                if a == b:
                    continue
                P["P1"] |= {
                    _key(x, y, rel, sym)
                    for x in ins(a, sents[0])
                    for y in ins(b, sents[0])
                    if x != y
                }
                for s in {sid(m[0]) for m in ment[a]} & {sid(m[0]) for m in ment[b]}:
                    xs, ys = ins(a, s), ins(b, s)
                    P["P2"] |= {_key(x, y, rel, sym) for x in xs for y in ys if x != y}
                    pr = [(abs(x[0] - y[0]), x, y) for x in xs for y in ys if x != y]
                    if pr:
                        _, x, y = min(pr)
                        P["P3"].add(_key(x, y, rel, sym))
                for s in {sid(m[0]) for m in ment[a]}:
                    for w, name in ((1, "P4"), (3, "P5")):
                        P[name] |= {
                            _key(x, y, rel, sym) for x in ins(a, s) for y in win(b, s, w) if x != y
                        }
            for name, PP in P.items():
                tp = len(PP & G)
                tot[name][0] += tp
                tot[name][1] += len(PP) - tp
                tot[name][2] += len(G) - tp
        tokd.sort()
        out[split] = {
            "documents": len(gold), "relations": n, "endpoint_sentence_distance": dict(dist),
            "token_distance_median": tokd[len(tokd) // 2], "token_distance_p90": tokd[int(0.9 * len(tokd))],
            "cooccurring_annotated_pair_sentences": cooc, "of_which_annotated": annot,
            "projection_ceiling": {k: S.prf(*v).to_dict() for k, v in sorted(tot.items())},
        }  # fmt: skip
    return out


def stage0_pd() -> dict:
    """P&D development (pilot) sheet only: how many evidence sentences a gold relation cites, and whether both endpoints occur in one of them."""
    sheet, sections = R17.SHEETS["pilot"]
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    gold, problems = PD.load_gold(REPO_ROOT / sheet, secs, PD.registry())
    assert not problems, problems[:2]
    c = Counter()
    for sid in sections:
        offs = PD.sentence_offsets(secs[sid])
        sent = {f"S{i + 1:03d}": ab for i, ab in enumerate(offs)}
        by_c = defaultdict(list)
        for m in gold[sid].mentions:
            by_c[m.concept_id].append(m.span)
        for r in gold[sid].relations:
            c["relations"] += 1
            c[
                f"evidence_sentences_{min(len(r.evidence), 3)}{'+' if len(r.evidence) >= 3 else ''}"
            ] += 1
            inside = lambda cid, ab, by_c=by_c: any(ab[0] <= s and e <= ab[1] for s, e in by_c[cid])
            same = any(
                inside(r.src_concept, sent[e]) and inside(r.tgt_concept, sent[e])
                for e in r.evidence
                if e in sent
            )
            c[
                "both_endpoints_in_one_cited_sentence"
                if same
                else "endpoints_not_in_one_cited_sentence"
            ] += 1
    return {"sheet": sheet, "sections": sections, **dict(c)}


# ---------------------------------------------------------------- Stage A: SciNLP held-out (frozen E0 runs)
def stage_a_scinlp() -> dict:
    ad = SciNLPAdapter()
    gold_all, sym = ad.gold("test"), ad.symmetric_relations()
    dmap = {d.doc_key: d for d in ad.load_documents("test", paragraph_every=SR.PARAGRAPH_EVERY)}
    res: dict = {v: {"per": {}, "codes": [], "edges": Counter()} for v in V.SC_VARIANTS}
    n0 = Counter()
    occ_stats = {}
    for dk in SC_DOCS:
        cp = PG.load_run(sc_run_id(dk))
        doc, g = dmap[dk], gold_all[dk]
        for v in V.SC_VARIANTS:
            r = V.sc_score(doc, g, cp, sym, v)
            res[v]["per"][dk] = r["scores"]
            res[v]["edges"].update(
                {k: n for k, n in r["edges"].items() if k != "unplaced_counted_as_fp"}
            )
            res[v]["codes"] += sc_attribution(doc, g, r["pred"], cp, sym)
            if v == "IDX-P1":
                occ_stats[dk] = {k: x for k, x in r["pred"]["stats"].items()}
                n0.update(
                    V.n0_split(
                        doc,
                        g,
                        sc_attribution(
                            doc, g, V.sc_score(doc, g, cp, sym, "FROZEN")["pred"], cp, sym
                        ),
                        r["pred"]["occurrences"],
                    )
                )
    out = {}
    for v, x in res.items():
        agg = {m: S.aggregate_documents(x["per"], m) for m in ("entity_strict", "rel")}
        codes = x["codes"]
        n_end = sum(1 for c in codes if c not in ("N0", "N1"))
        n_prop = sum(1 for c in codes if c not in ("N0", "N1", "P0"))
        out[v] = {
            "concept_f1_entity_strict": agg["entity_strict"]["micro"],
            "strict_relation": agg["rel"]["micro"],
            "strict_relation_per_document": agg["rel"]["per_document"],
            "pair_recall_analogue": {"reached": n_prop, "denominator": n_end, "recall": n_prop / n_end if n_end else None},
            "attribution": A.distribution(codes),
            "edges": {**{k: int(c) for k, c in x["edges"].items()}, "unplaced_counted_as_fp": v != "FROZEN"},
        }  # fmt: skip
    fz = json.loads(FROZEN_012.read_text())["scinlp"]["levels"]["E0"]["aggregates"]
    f = out["FROZEN"]
    out["frozen_check"] = {
        "strict_relation_micro_equal": all(abs(f["strict_relation"][k] - fz["rel"]["micro"][k]) < 1e-12 for k in ("precision", "recall", "f1")),
        "entity_strict_micro_equal": all(abs(f["concept_f1_entity_strict"][k] - fz["entity_strict"]["micro"][k]) < 1e-12 for k in ("precision", "recall", "f1")),
    }  # fmt: skip
    out["n0_split_of_frozen_codes"] = dict(n0)
    out["occurrence_index_stats"] = occ_stats
    return out


# ---------------------------------------------------------------- Stage A: P&D (frozen E0 runs, CR-017 five metrics)
def _pd_units(tag: str, indexed: bool):
    units, sym, _paths, _gold = R17.load_units(tag, "E0")
    if not indexed:
        return units, sym, {}
    _sheet, sections = R17.SHEETS[tag]
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    stats = {}
    for sid, rid in R17.run_ids(tag, "E0", sections).items():
        if sid not in units:
            continue
        cp = PG.load_run(rid)
        pg = V.pd_graph_indexed(cp, sid, secs[sid], PD.sentence_offsets(secs[sid]))
        u = units[sid]
        units[sid] = HL.UnitInput(u.gold, pg["nodes"], pg["edges"], u.proposed_pairs, u.classifier)
        stats[sid] = {k: v for k, v in pg["stats"].items() if k.startswith("index_")}
    return units, sym, stats


def _pd_codes(units, tag: str, sym) -> dict:
    codes = []
    for sid, u in units.items():
        cp = PG.load_run(R17.run_ids(tag, "E0", [sid])[sid])
        codes += [
            A.attribute(t)
            for t in A.build_traces(
                u.gold, u.nodes, u.edges, u.proposed_pairs, no_relation_pairs(cp, sid), sym
            )
        ]
    return A.distribution(codes)


def stage_a_pd() -> dict:
    out = {}
    fz = json.loads(FROZEN_017.read_text())["pd"]
    for tag in ("heldout", "pilot"):
        out[tag] = {}
        for name, indexed in (("FROZEN", False), ("IDX", True)):
            units, sym, stats = _pd_units(tag, indexed)
            ev = HL.evaluate(units, sym, boot=True)
            out[tag][name] = {
                "headline": ev["headline"],
                "attribution": _pd_codes(units, tag, sym),
                "occurrence_index_stats": stats,
            }
        f, z = out[tag]["FROZEN"]["headline"], fz[tag]["E0"]["headline"]
        out[tag]["frozen_check"] = {
            k: (f[k].get("f1", f[k].get("recall")) == z[k].get("f1", z[k].get("recall"))) for k in z
        }
    return out


# ---------------------------------------------------------------- report
def _f(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def markdown(r: dict) -> str:
    s0, sa, pd = r["stage0"], r["stage_a"]["scinlp"], r["stage_a"]["pd"]
    L = ["# CR-019 Stage 0 + Stage A — occurrence index and grounding-consistent evaluation", "",
         (f"Generated by `uv run python -m cumap.cr019.run`. $0, no model call. Source artefacts hashed before and after: identical = **{r['sources_unchanged']}**. "
         f"Frozen CR-012 / CR-017 numbers are reproduced by the `FROZEN` rows and are not replaced. Variants were pre-registered (DECISIONS.md 2026-10-15) from Stage 0 only."), "",
         "Datasets: SciNLP release in `data/raw/external/scinlp` (train/dev for Stage 0, the 3 test papers for Stage A); P&D-E2E sheets `data/gold/pd_e2e_pilot_blind.csv` (development) and `pd_e2e_test_blind.csv` (held-out); frozen E0 runs `cr012_*_E0`.", "",
         "## Stage 0 (no held-out data)", "", "| SciNLP split | relations | same sentence | median / p90 token gap | co-occurring annotated pair → annotated there |", "|---|---|---|---|---|"]  # fmt: skip
    for sp, x in s0["scinlp"].items():
        L.append(
            f"| {sp} | {x['relations']} | {x['endpoint_sentence_distance'].get('same_sentence', 0)} | {x['token_distance_median']} / {x['token_distance_p90']} | {x['of_which_annotated']} / {x['cooccurring_annotated_pair_sentences']} |"
        )
    L += [
        "",
        "Projection ceiling (perfect concept-level graph from the answer key, strict mention-level F1):",
        "",
        "| rule | train P / R / F1 | dev P / R / F1 |",
        "|---|---|---|",
    ]
    names = {
        "P1": "P1 one evidence sentence, all occurrences",
        "P2": "P2 every co-occurring sentence, all pairs",
        "P3": "P3 every co-occurring sentence, nearest pair",
        "P4": "P4 window ±1 sentence",
        "P5": "P5 window ±3 sentences",
    }
    for k, nm in names.items():
        t, d = (
            s0["scinlp"]["train"]["projection_ceiling"][k],
            s0["scinlp"]["dev"]["projection_ceiling"][k],
        )
        L.append(
            f"| {nm} | {_f(t['precision'])} / {_f(t['recall'])} / **{_f(t['f1'])}** | {_f(d['precision'])} / {_f(d['recall'])} / **{_f(d['f1'])}** |"
        )
    p = s0["pd"]
    L += ["", f"P&D development sheet ({', '.join(p['sections'])}): {p['relations']} gold relations; both endpoints inside one cited evidence sentence: **{p.get('both_endpoints_in_one_cited_sentence', 0)}**, not: {p.get('endpoints_not_in_one_cited_sentence', 0)}.", "",
          "## Stage A — SciNLP held-out (3 papers, frozen E0 runs)", "",
          "| variant | predicted edges | placed | unplaced (→ FP?) | strict relation P / R / F1 | concept F1 (entity strict) P / R / F1 | pair-recall analogue |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    for v in V.SC_VARIANTS:
        x = sa[v]
        e, rel, ent, pr = (
            x["edges"],
            x["strict_relation"],
            x["concept_f1_entity_strict"],
            x["pair_recall_analogue"],
        )
        tag = " (primary)" if v == V.PRIMARY else " (frozen)" if v == "FROZEN" else ""
        L.append(
            f"| `{v}`{tag} | {e['predicted']} | {e['placed']} | {e['unplaced']} ({'yes' if e['unplaced_counted_as_fp'] else 'no, excluded'}) | {_f(rel['precision'])} / {_f(rel['recall'])} / **{_f(rel['f1'])}** | {_f(ent['precision'])} / {_f(ent['recall'])} / {_f(ent['f1'])} | {pr['reached']} / {pr['denominator']} = {_f(pr['recall'])} |"
        )
    L += [
        "",
        f"Frozen check: {sa['frozen_check']}.",
        "",
        "Earliest-failure codes (counts):",
        "",
        "| variant | " + "N0 | N1 | P0 | R0 | R1 | R2 | recovered" + " |",
        "|---|" + "---|" * 7,
    ]
    for v in V.SC_VARIANTS:
        bc = sa[v]["attribution"]["by_code"]
        L.append(
            f"| `{v}` | "
            + " | ".join(str(bc.get(c, 0)) for c in ("N0", "N1", "P0", "R0", "R1", "R2"))
            + f" | {sa[v]['attribution'].get('recovered', 0)} |"
        )
    n = sa["n0_split_of_frozen_codes"]
    L += ["", f"Frozen N0 codes split: **N0-unrecorded {n.get('N0-unrecorded', 0)}** (a node owns both endpoint occurrences) · N0-absent {n.get('N0-absent', 0)}.", "",
          "## Stage A — P&D (CR-017 five metrics, frozen E0 runs)", "", "| set | variant | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 | Strict E2E Edge F1 (P / R) |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    for tag in ("heldout", "pilot"):
        for v in ("FROZEN", "IDX"):
            h = pd[tag][v]["headline"]
            se = h["strict_e2e_edge_f1"]
            L.append(
                f"| {tag} | `{v}` | {_f(h['concept_f1']['f1'])} | {_f(h['ancestor_hierarchy_f1'].get('f1'))} | {_f(h['pair_recall']['recall'])} | {_f(h['relation_macro_f1']['f1'])} | {_f(se['f1'])} ({_f(se['precision'])} / {_f(se['recall'])}) |"
            )
        L.append(f"| {tag} | frozen check | {pd[tag]['frozen_check']} | | | | |")
    L += [
        "",
        "P&D earliest-failure codes:",
        "",
        "| set | variant | N0 | N1 | C0 | C1 | P0 | R0 | R1 | recovered |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for tag in ("heldout", "pilot"):
        for v in ("FROZEN", "IDX"):
            a = pd[tag][v]["attribution"]
            L.append(
                f"| {tag} | `{v}` | "
                + " | ".join(
                    str(a["by_code"].get(c, 0)) for c in ("N0", "N1", "C0", "C1", "P0", "R0", "R1")
                )
                + f" | {a.get('recovered', 0)} |"
            )
    return "\n".join(L) + "\n"


def main() -> None:
    files = source_files()
    before = {str(f.relative_to(REPO_ROOT)): sha(f) for f in files}
    r = {
        "stage0": {"scinlp": stage0_scinlp(), "pd": stage0_pd()},
        "stage_a": {"scinlp": stage_a_scinlp(), "pd": stage_a_pd()},
    }
    after = {str(f.relative_to(REPO_ROOT)): sha(f) for f in files}
    r["source_hashes"] = before
    r["sources_unchanged"] = before == after
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage_a.json").write_text(json.dumps(r, indent=1, default=str))
    (OUT / "stage_a.md").write_text(markdown(r))
    print("wrote", OUT / "stage_a.md")


if __name__ == "__main__":
    main()
