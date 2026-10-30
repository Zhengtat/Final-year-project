"""CR-058: SciNLP pipeline diagnostics page ($0, read-only, no model call).

    uv run python -m cumap.cr058.page            # reports/cr058/pipeline.html (gitignored: SciNLP text is CC BY-NC) + summary_v11.{json,md}
    uv run python -m cumap.cr058.page --profile v10  # superseded A-all: pipeline_v10.html + summary_v10.{json,md}
    uv run python -m cumap.cr058.page --profile v5   # the CR-058 page as merged: pipeline_v5.html + summary.{json,md}

CR-061: by default the development panel shows profile v11 = the v5 runs with the CR-060 span-identity step (variant A-name) applied in
memory at load (the step runs after relation classification, so this equals a v10 run; the source checkpoints are not written, and are
hashed before and after). Gates for v10: the pooled concept and relation counts must equal the CR-060 replay (`reports/cr060/part_a*.json`);
hierarchy, fact and macro F1 have no v10 reference and are not gated.

Two labelled panels, never pooled with each other:
- development: the 57 SciNLP train + dev papers with profile v5 (first set `cr055ballp`, the other 37 train papers `cr057rest`): the
  stage funnel, the downstream objectives and gold vs built graphs;
- held-out oracle: the 3 test papers, frozen CR-012 runs E0 / E1 / E3-M / E4-M (older pipeline), reporting only (rule 9).
Every score uses the frozen scorers under `IDXR1-P1` (rule 35). Gates: the pooled final-stage numbers must equal the CR-043 scorecards and
the CR-031 ladder; the source checkpoints are hashed before and after."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import sc_attribution
from cumap.cr019 import variants as V
from cumap.cr019.run import SC_DOCS, sc_run_id
from cumap.cr022 import scoring as C
from cumap.cr032 import scinlp_t1 as ST
from cumap.cr033 import fact_f1 as F
from cumap.cr043.papers import paper_set
from cumap.cr043.run import run_id
from cumap.cr054.recall import run_trace
from cumap.cr058 import funnel as FN
from cumap.cr058 import graphs as GR
from cumap.cr060 import span_identity as SI

OUT = REPO_ROOT / "reports" / "cr058"
TEMPLATE = Path(__file__).with_name("page.html")
PRIMARY = "IDXR1-P1"
H2 = C.HIER_SETS["H2 {subclassOf, subtaskOf}"]
DEV_SOURCES = (
    ("first", "cr055ballp", "cr055ballp.json"),
    ("rest", "cr057rest", "cr057rest_rest.json"),
)
LEVELS = (("E0", "E0"), ("E1", "E1"), ("E3", "E3-M"), ("E4", "E4-M"))
SPAN_IDENTITY: str | None = (
    "A-name"  # CR-061: profile v11 (A-name); None = profile v5 as merged in CR-058
)
PROFILE_LABEL = {"A-name": "v11", "A-all": "v10"}
V10_REFS = {"first": "part_a.json", "rest": "part_a_rest.json"}
DATASET = "SciNLP repository release SciNLP-repo-e78342be (registry relations_scinlp_v1.0.1)"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


def _prf(x) -> dict:
    return {"tp": x.tp, "fp": x.fp, "fn": x.fn}


def _docs(ad: SciNLPAdapter, splits: set[str]) -> tuple[dict, dict]:
    gold = {s: ad.gold(s) for s in splits}
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in splits
    }
    return docs, gold


def downstream(doc, g, cp: dict, sym: set[str]) -> tuple[dict, list[dict]]:
    """Per-paper hierarchy (direct H2), fact F1 (FACT-C1-SURF-R1) and the relation macro rows, exactly as `cr043.eval.score`."""
    p = C.place(doc, cp, PRIMARY)
    ident, _ = ST.r1_identity(doc)
    fact = F.fact_score(g, p.rels, sum(p.unplaced_by_label.values()), PRIMARY, ident, sym)
    p3 = V.sc_score(doc, g, cp, sym, "IDXR1-P3")["scores"]["rel"]
    return (
        {"hierarchy_H2": _prf(C.direct_relation_prf(g, p, sym, PRIMARY, H2)), "fact": _prf(fact["prf"]),
         "relation_P3": _prf(p3)},
        C.relation_rows(doc, g, p, sym),
    )  # fmt: skip


def paper_record(doc, g, cp: dict, v4: dict | None, sym: set[str], trace: dict | None) -> dict:
    rf = FN.relation_funnel(doc, g, cp, sym)
    rec = {
        "words": doc.word_count,
        "gold_mentions": len(g.mentions),
        "gold_relations": len(g.relations),
        "relation": {k: rf[k] for k in ("pairs", "checks", "gold_stages", "not_selected_split", "selection_stats", "edges")},
        "relation_strict": rf["relation_strict"],
        "concept_strict": rf["concept_strict"],
        "codes": {},
    }  # fmt: skip
    codes = sc_attribution(doc, g, rf["pred"], cp, sym)
    for c in codes:
        rec["codes"][c or "recovered"] = rec["codes"].get(c or "recovered", 0) + 1
    if v4 is not None:
        rec["concept"] = FN.concept_funnel(doc, g, cp, v4, sym)
    rec["graph"] = GR.build(doc, g, cp, rf["pred"], rf["lost_at"], sym, trace)
    return rec


def _load(rid: str) -> tuple[dict, dict | None, list[Path]]:
    p = PG.run_path(rid)
    cp = json.loads((p / "checkpoint.json").read_text())
    v4p = p / "v4_concepts.json"
    v4 = json.loads(v4p.read_text()) if v4p.exists() else None
    return cp, v4, [p / "checkpoint.json", v4p]


def build_dev(ad: SciNLPAdapter, sym: set[str]) -> tuple[dict, dict, list[Path]]:
    papers, sets, macro_rows, files = {}, {}, {}, []
    docs, gold = _docs(ad, {"train", "dev"})
    for set_name, tag, _card in DEV_SOURCES:
        sets[set_name] = []
        macro_rows[set_name] = []
        for split, d in paper_set(set_name):
            rid = run_id(d, tag)
            cp, v4, fs = _load(rid)
            files += fs
            doc, g = docs[split][d], gold[split][d]
            if SPAN_IDENTITY:  # CR-061: profile v11 (or v10), applied in memory
                cp, _rec = SI.apply(
                    cp, doc.text, SI.load_variant(SPAN_IDENTITY), symmetric=frozenset(sym)
                )
            rec = paper_record(doc, g, cp, v4, sym, run_trace(rid) if v4 else None)
            ds, rows = downstream(doc, g, cp, sym)
            rec |= {"split": split, "set": set_name, "run_id": rid, "downstream": ds}
            macro_rows[set_name] += rows
            papers[d] = rec
            sets[set_name].append(d)
    macro = {k: C.pooled_macro(v)["macro_f1"] for k, v in macro_rows.items()}
    macro["all"] = C.pooled_macro(macro_rows["first"] + macro_rows["rest"])["macro_f1"]
    return papers, {"sets": sets, "macro_f1": macro}, files


def build_test(ad: SciNLPAdapter, sym: set[str]) -> tuple[dict, list[Path]]:
    """Held-out oracle ladder: reporting only (rule 9); the frozen runs are read, never rerun."""
    docs, gold = _docs(ad, {"test"})
    out, files = {}, []
    for d in SC_DOCS:
        doc, g = docs["test"][d], gold["test"][d]
        out[d] = {}
        for lv, label in LEVELS:
            rid = sc_run_id(d, lv)
            cp, v4, fs = _load(rid)
            files += fs
            trace = run_trace(rid) if v4 is not None and lv == "E0" else None
            rec = paper_record(doc, g, cp, v4 if lv == "E0" else None, sym, trace)
            rec["run_id"] = rid
            out[d][label] = rec
    return out, files


def _sum(recs: list[dict], path: tuple[str, ...]) -> dict:
    tot = {"tp": 0, "fp": 0, "fn": 0}
    for r in recs:
        x = r
        for k in path:
            x = x[k]
        for k in tot:
            tot[k] += x[k]
    return tot


def gates(papers: dict, meta: dict, test: dict) -> dict:
    """Pooled final-stage numbers against the CR-043 scorecards (development) and the CR-031 ladder (held-out)."""
    out = {}
    for set_name, _tag, card in DEV_SOURCES:
        recs = [papers[d] for d in meta["sets"][set_name]]
        if SPAN_IDENTITY:  # CR-061: reference = the CR-060 replay (concept and relation only)
            ref = json.loads((REPO_ROOT / "reports/cr060" / V10_REFS[set_name]).read_text())[
                "arms"
            ][SPAN_IDENTITY]
            got_c = _sum(recs, ("concept", "stages", "consolidation"))
            got_r = _sum(recs, ("relation_strict",))
            out[f"{set_name}/concept"] = all(
                got_c[x] == ref["concept"][x] for x in ("tp", "fp", "fn")
            )
            out[f"{set_name}/relation"] = all(
                got_r[x] == ref["relation"][x] for x in ("tp", "fp", "fn")
            )
            out[f"{set_name}/concept_strict_equals_consolidation"] = got_c == _sum(
                recs, ("concept_strict",)
            )
            continue
        sc = json.loads((REPO_ROOT / "reports/cr043" / card).read_text())
        want = {
            "concept": sc["variants"][PRIMARY]["concept_entity_strict"],
            "relation": sc["variants"][PRIMARY]["relation_strict"],
            "hierarchy_H2": sc["hierarchy_direct_H2"],
            "fact": sc["fact_f1_surf_r1"]["prf"],
        }
        got = {
            "concept": _sum(recs, ("concept", "stages", "consolidation")),
            "relation": _sum(recs, ("relation_strict",)),
            "hierarchy_H2": _sum(recs, ("downstream", "hierarchy_H2")),
            "fact": _sum(recs, ("downstream", "fact")),
        }
        for k in want:
            out[f"{set_name}/{k}"] = all(got[k][x] == want[k][x] for x in ("tp", "fp", "fn"))
        out[f"{set_name}/concept_strict_equals_consolidation"] = got["concept"] == _sum(
            recs, ("concept_strict",)
        )
        out[f"{set_name}/macro_f1"] = (
            abs(meta["macro_f1"][set_name] - sc["relation_macro_f1"]["macro_f1"]) < 1e-9
        )
    lad = json.loads((REPO_ROOT / "reports/cr031/oracle_ladder.json").read_text())
    for lv, label in LEVELS:
        want = lad[f"{lv}/IDXR1-P1"]["rel"]
        got = _sum([test[d][label] for d in test], ("relation_strict",))
        out[f"test/{label}/relation"] = all(got[x] == want[x] for x in ("tp", "fp", "fn"))
    return out


def summary(papers: dict, meta: dict, test: dict, gate: dict, hashes_ok: bool) -> dict:
    """Numbers only (no SciNLP text): committed beside the gitignored page."""

    def pool(names: list[str]) -> dict:
        recs = [papers[d] for d in names]
        cs = {s: _sum(recs, ("concept", "stages", s)) for s in FN.CONCEPT_STAGES}
        gs = {s: sum(r["relation"]["gold_stages"][s] for r in recs) for s in FN.GOLD_REL_STAGES}
        return {"papers": len(recs), "concept_stages": cs, "gold_relation_stages": gs,
                "relation_strict": _sum(recs, ("relation_strict",))}  # fmt: skip

    sets = {k: pool(v) for k, v in meta["sets"].items()}
    sets["all"] = pool(meta["sets"]["first"] + meta["sets"]["rest"])
    return {
        "dataset": DATASET,
        "sources": {s: t for s, t, _ in DEV_SOURCES},
        "profile": f"{PROFILE_LABEL.get(SPAN_IDENTITY, 'replay')} (v5 runs + span identity {SPAN_IDENTITY})" if SPAN_IDENTITY else "v5",
        "gates": gate,
        "sources_unchanged": hashes_ok,
        "development": sets,
        "test_oracle": {d: {lv: {"relation_strict": r["relation_strict"], "concept_strict": r["concept_strict"],
                                 "codes": r["codes"]} for lv, r in x.items()} for d, x in test.items()},
    }  # fmt: skip


def _f1(x: dict) -> float:
    return 2 * x["tp"] / (2 * x["tp"] + x["fp"] + x["fn"]) if x["tp"] else 0.0


def _f2(x: dict) -> float:  # CR-062: concept headline, beta 2
    return 5 * x["tp"] / (5 * x["tp"] + 4 * x["fn"] + x["fp"]) if x["tp"] else 0.0


def summary_md(s: dict) -> str:
    L = ["# CR-058 SciNLP pipeline diagnostics (summary)", "",
         "Generated by `cumap.cr058.page` ($0, read-only). The page itself (`reports/cr058/pipeline.html`) is gitignored because it embeds "
         "SciNLP text (CC BY-NC). Grounding `IDXR1-P1` throughout (rule 35). Dataset: " + s["dataset"] + ".", "",
         (f"Gates (pooled final numbers = {'CR-060 replay' if s.get('profile', 'v5') != 'v5' else 'CR-043 scorecards'} and CR-031 ladder): **{all(s['gates'].values())}**; "
          f"source files unchanged: **{s['sources_unchanged']}**."), "",
         f"## Development (train + dev, profile {s.get('profile', 'v5')})", "",
         "| set | papers | concept F2 (F1): generator 1st pass | after verifier | after corrective round | after pruner | after consolidation | relation F1 |",
         "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for k, v in s["development"].items():
        cs = v["concept_stages"]
        L.append(f"| {k} | {v['papers']} | " + " | ".join(f"{_f2(cs[x]):.3f} ({_f1(cs[x]):.3f})" for x in FN.CONCEPT_STAGES)
                 + f" | {_f1(v['relation_strict']):.3f} |")  # fmt: skip
    L += [
        "",
        "## Gold relations reaching each stage (development, all papers)",
        "",
        "| stage | gold relations |",
        "|---|---|",
    ]
    for st, n in s["development"]["all"]["gold_relation_stages"].items():
        L.append(f"| {st} | {n} |")
    L += [
        "",
        "## Held-out oracle ladder (test, frozen runs, reporting only)",
        "",
        "| paper | E0 | E1 | E3-M | E4-M |",
        "|---|---|---|---|---|",
    ]
    for d, x in s["test_oracle"].items():
        L.append(
            f"| {d} | "
            + " | ".join(
                f"{_f1(x[lv]['relation_strict']):.3f}" for lv in ("E0", "E1", "E3-M", "E4-M")
            )
            + " |"
        )
    return "\n".join(L) + "\n"


def source_files() -> list[Path]:
    rids = [run_id(d, tag) for s, tag, _ in DEV_SOURCES for _sp, d in paper_set(s)]
    rids += [sc_run_id(d, lv) for d in SC_DOCS for lv, _ in LEVELS]
    return [PG.run_path(r) / f for r in rids for f in ("checkpoint.json", "v4_concepts.json")]


def main() -> dict:
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    files = source_files()
    before = {str(p): _sha(p) for p in files}
    papers, meta, _ = build_dev(ad, sym)
    test, _ = build_test(ad, sym)
    gate = gates(papers, meta, test)
    after = {str(p): _sha(p) for p in files}
    data = {
        "dataset": DATASET,
        "sources": {s: t for s, t, _ in DEV_SOURCES},
        "profile": f"{PROFILE_LABEL[SPAN_IDENTITY]} (v5 runs + span identity {SPAN_IDENTITY})"
        if SPAN_IDENTITY
        else "v5",
        "papers": papers,
        "meta": meta,
        "test": test,
        "levels": [lab for _, lab in LEVELS],
        "stage_labels": GR.STAGE_LABEL,
        "symmetric": sorted(sym),
        "relations": sorted(ad.relation_registry()),
        "gates": gate,
        "sources_unchanged": before == after,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    blob = base64.b64encode(
        gzip.compress(json.dumps(data, ensure_ascii=False).encode("utf-8"), mtime=0)
    ).decode()
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA_B64__*/", blob)
    page, summ = {None: ("pipeline_v5.html", "summary"), "A-all": ("pipeline_v10.html", "summary_v10"),
                  "A-name": ("pipeline.html", "summary_v11")}[SPAN_IDENTITY]  # fmt: skip
    (OUT / page).write_text(html, encoding="utf-8")
    s = summary(papers, meta, test, gate, before == after)
    s["profile"] = data["profile"]
    (OUT / f"{summ}.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    (OUT / f"{summ}.md").write_text(summary_md(s), encoding="utf-8")
    return s


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="v11", choices=["v11", "v10", "v5"])
    a = ap.parse_args()
    SPAN_IDENTITY = {"v5": None, "v10": "A-all", "v11": "A-name"}[a.profile]
    r = main()
    print(json.dumps({"gates": r["gates"], "sources_unchanged": r["sources_unchanged"]}, indent=1))
