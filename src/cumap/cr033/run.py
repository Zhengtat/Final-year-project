"""CR-033 ($0, no model call): SciNLP concept-level fact F1 `FACT-C1-SURF-R1`, beside the frozen strict relation F1.

    uv run python -m cumap.cr033.run --split dev      # validation first
    uv run python -m cumap.cr033.run --split test     # after the pre-registration is committed (DECISIONS.md); determinism gate first

Writes only `reports/cr033/`. Source checkpoints are hashed before and after. Every figure names its grounding variant and identity rule."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.types import PRF
from cumap.cr019 import stage_b as SB
from cumap.cr019.run import SC_DOCS, sc_run_id
from cumap.cr022 import run as R22
from cumap.cr022 import scoring as C22
from cumap.cr032 import scinlp_t1 as ST
from cumap.cr033 import fact_f1 as F
from cumap.expert_kg.alias_rules import AliasConfig

OUT = REPO_ROOT / "reports/cr033"


def prf_d(x: PRF) -> dict:
    return {
        "tp": x.tp,
        "fp": x.fp,
        "fn": x.fn,
        "precision": x.precision,
        "recall": x.recall,
        "f1": x.f1,
    }


def _level_rid(level: str):
    return lambda d: sc_run_id(d, level)


def sets_for(split: str) -> list[tuple[str, object, list[str], tuple[str, ...]]]:
    """(label, run-id function, documents, variants)."""
    if split == "test":
        s = R22.SETS
        oracle = [
            (f"frozen CR-012 oracle {lab} (token matching)", _level_rid(lv), SC_DOCS, ("FROZEN", "IDX-P1"))
            for lv, lab in (("E1", "E1"), ("E3", "E3-M"), ("E4", "E4-M"))
        ]  # fmt: skip
        return [
            (
                "frozen CR-012 STOP 4 E0 (token matching)",
                s[0][2],
                SC_DOCS,
                ("FROZEN", "IDX-P1", "IDX-P3"),
            ),
            (
                "CR-021 rebuild `cr021test` E0 (r1key matching)",
                s[1][2],
                SC_DOCS,
                ("FROZEN", "IDX-P1", "IDXR1-P1"),
            ),
            *oracle,
        ]
    s = R22.SETS
    return [
        (
            "CR-019 dev runs `cr019dev` E0 (token matching)",
            s[2][2],
            SB.SC_DEV,
            ("FROZEN", "IDX-P1"),
        ),
        (
            "CR-021 dev rebuild `cr021dev` E0 (r1key matching)",
            s[3][2],
            SB.SC_DEV,
            ("FROZEN", "IDX-P1", "IDXR1-P1"),
        ),
    ]


def score_set(split: str, rid, docs: list[str], variants, ad, sym, acfg) -> dict:
    gold = ad.gold(split)
    dmap = {d.doc_key: d for d in ad.load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)}
    present = [d for d in docs if (PG.run_path(rid(d)) / "checkpoint.json").exists()]
    out: dict = {"documents": present, "variants": {}}
    for v in variants:
        units, strict = {}, []
        for d in present:
            cp = json.loads((PG.run_path(rid(d)) / "checkpoint.json").read_text())
            doc, g = dmap[d], gold[d]
            p = C22.place(doc, cp, v)
            ident, _ = ST.r1_identity(doc, acfg)
            units[d] = F.fact_score(g, p.rels, sum(p.unplaced_by_label.values()), v, ident, sym)
            strict.append(C22.direct_relation_prf(g, p, sym, v, None))
        pooled = F.pool(units)
        out["variants"][v] = {
            "FACT_C1_SURF_R1": {**pooled, "prf": prf_d(pooled["prf"])},
            "strict_relation_mention_level_beside": prf_d(R22.pool(strict)),
        }
    return out


def internal_gate(split: str, ad, sym) -> dict:
    """Dev gate: the placed-relation path used here reproduces the frozen strict scorer (`cr019.variants.sc_score`) per document."""
    from cumap.cr019 import variants as V

    _label, rid, docs, _v = sets_for(split)[0]
    gold = ad.gold(split)
    dmap = {d.doc_key: d for d in ad.load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)}
    ok = True
    for d in docs:
        if not (PG.run_path(rid(d)) / "checkpoint.json").exists():
            continue
        cp = PG.load_run(rid(d))
        for v in ("FROZEN", "IDX-P1"):
            a = V.sc_score(dmap[d], gold[d], cp, sym, v)["scores"]["rel"]
            b = C22.direct_relation_prf(gold[d], C22.place(dmap[d], cp, v), sym, v, None)
            ok &= (a.tp, a.fp, a.fn) == (b.tp, b.fp, b.fn)
    return {"checks": {"placed_path_equals_cr019_sc_score_per_document": ok}, "passed": ok}


def markdown(r: dict) -> str:

    def f(x) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    L = [
        f"# CR-033 SciNLP concept-level fact F1 (`FACT-C1-SURF-R1`), {r['split']} split ($0, no model call)",
        "",
        "Definition pre-registered in `docs/DECISIONS.md` (2026-10-23, CR-033) before any test figure. **`FACT-C1-SURF-R1` infers concept identity from strings (R1 name key plus acronym <-> long form within a paper).** It is a labelled companion score, not a headline candidate; `IDX-P1` strict relation F1 stays the headline and `IDX-P3` the upper bound.",
        "",
        "## Determinism gate",
        "",
        "| check | result |",
        "|---|---|",
        *[f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in r["gate"]["checks"].items()],
        "",
        f"**Gate: {'PASSED' if r['gate']['passed'] else 'FAILED'}.** Source hashes identical before and after: **{r['hashes_unchanged']}** ({r['n_hashed']} files).",
        "",
    ]
    if not r["gate"]["passed"]:
        return "\n".join(L)
    for lab, s in r["sets"].items():
        L += [f"## {lab}", "", f"Documents ({len(s['documents'])}): {', '.join(s['documents'])}.", "",
              "| variant | fact P / R / F1 | gold facts (mention-level relations) | predicted facts (synthetic concept) | unplaced as FP | TP facts whose own quote also matches a gold mention relation | strict mention-level relation F1 (beside) |",
              "|---|---|---|---|---|---|---|"]  # fmt: skip
        for v, e in s["variants"].items():
            x = e["FACT_C1_SURF_R1"]
            p = x["prf"]
            sr = e["strict_relation_mention_level_beside"]
            share = x["evidence_match_share"]
            L.append(
                f"| `{v}` | {f(p['precision'])} / {f(p['recall'])} / **{f(p['f1'])}** (tp {p['tp']}, fp {p['fp']}, fn {p['fn']}) | {x['gold_facts']} ({x['gold_mention_relations']}) | {x['pred_facts']} ({x['pred_facts_with_synthetic_concept']}) | {x['unplaced_counted_as_fp']} | {x['tp_facts_with_strict_evidence_match']} of {x['tp_facts']} ({f(share)}) | {f(sr['f1'])} (tp {sr['tp']}, fp {sr['fp']}, fn {sr['fn']}) |"
            )
        L.append("")
    L += [
        "## Limits",
        "",
        "- Identity is inferred from strings: two different concepts with one R1 key collapse; one concept written two ways that R1 / acronym rules miss stays two nodes. Only the `SURF-R1` version exists (no identity sheet, owner decision).",
        "- Predicted facts come from the placed mention-level relations, so an edge whose evidence quote cannot be placed is a false positive (rule 35) except in `FROZEN`.",
        "- Dev has 6 and test 3 documents; no confidence interval is attempted. Dev and test are never pooled.",
        "- The explorer scorecard and the presentation's metric definitions are not updated in this change.",
    ]
    return "\n".join(L) + "\n"


def main(split: str) -> dict:
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    acfg = AliasConfig.load()
    OUT.mkdir(parents=True, exist_ok=True)
    sets = sets_for(split)
    files = [PG.run_path(rid(d)) / "checkpoint.json" for _l, rid, docs, _v in sets for d in docs]
    files = [p for p in files if p.exists()]

    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    before = {str(p): sha(p) for p in files}
    gate = R22.gate(ad, sym) if split == "test" else internal_gate(split, ad, sym)
    res: dict = {"split": split, "gate": gate, "sets": {}}
    if gate["passed"]:
        for label, rid, docs, variants in sets:
            res["sets"][label] = score_set(split, rid, docs, variants, ad, sym, acfg)
    res["hashes_unchanged"] = before == {str(p): sha(p) for p in files}
    res["n_hashed"] = len(before)
    (OUT / f"fact_f1_{split}.json").write_text(
        json.dumps(res, indent=1, default=str), encoding="utf-8"
    )
    (OUT / f"fact_f1_{split}.md").write_text(markdown(res), encoding="utf-8")
    print(split, "gate", gate["passed"], "hashes unchanged", res["hashes_unchanged"])
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    main(ap.parse_args().split)
