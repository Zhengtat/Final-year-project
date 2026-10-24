"""CR-050 measurement: identity judge v1 (`J1`) vs the rejected-link adjudicator v2 (`ADJ`) on the owner's fresh sheet
(`data/gold/cr050_identity_sheet_marked.csv`, read only), luna profile, rule pre-registered in docs/DECISIONS.md.

    uv run python -m cumap.cr050.measure --dry-run | --limit 20 | (all)
    uv run python -m cumap.cr050.measure --score         # reports/cr050/judge_v1.{json,md}
Inputs are built the same way for both arms (the full sentence holding the evidence, the target node's aliases and description).
SciNLP rows come from train / dev papers only (rule 9)."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from functools import cache

from cumap.concepts_v4.rejected_links import AdjudicationLLM
from cumap.config import REPO_ROOT, get_settings
from cumap.cr021 import adjudicator as A
from cumap.expert_kg import identity_judge as IJ
from cumap.gold.validate import verify_quote

GOLD = REPO_ROOT / "data/gold/cr050_identity_sheet_marked.csv"
OUT = REPO_ROOT / "reports" / "cr050"
RESULTS = OUT / "results.jsonl"
RUN_ID = "cr050_identity_judge"
CAP_USD = 1.0
ARMS = ("ADJ", "J1")
DOMAIN = {
    "pd_production": "computer networking",
    "scinlp_dev_train": "natural language processing research",
}
TO_LABEL = {"same": "same_as_target", "narrower": "new_concept", "broader": "new_concept", "new": "new_concept", "not_a_concept": "not_a_concept"}  # fmt: skip


def load_rows() -> list[dict]:
    rows = list(csv.DictReader(GOLD.open(encoding="utf-8-sig")))
    for r in rows:
        r["gold"] = A.gold_label(r)
        r["key"] = f"cr050-{r['row']}"
        r["split"] = "fresh"
    return rows


@cache
def _scinlp_texts() -> dict[str, str]:
    from cumap.cr012.adapters import SciNLPAdapter

    ad = SciNLPAdapter()
    return {d.doc_key: d.text for sp in ("train", "dev") for d in ad.load_documents(sp)}


def sentence_for(r: dict) -> str:
    from cumap.expert_kg.relations import split_sentences

    ev = " ".join(r["evidence"].split())
    sec = r["section_id"].split("#")[0]
    text = (
        A._texts("pd_production").get(sec, "")
        if r["dataset"] == "pd_production"
        else _scinlp_texts().get(sec, "")
    )
    for s in split_sentences(text):
        if ev and ev in " ".join(s.split()):
            return " ".join(s.split())
    return r["evidence"]


def render_inputs(r: dict) -> dict:
    n = A._nodes(r["run_id"]).get(r["rejected_target"], {})
    return {"domain": DOMAIN[r["dataset"]], "surface": r["surface"], "target_name": r["rejected_target"],
            "target_aliases": ", ".join(n.get("aliases", [])) or "none", "target_type": r["target_type"],
            "target_gloss": n.get("definition") or n.get("gloss") or "none", "evidence": sentence_for(r)}  # fmt: skip


def judge(client, arm: str, r: dict, prompts: dict) -> dict:
    inp = render_inputs(r)
    if arm == "ADJ":
        res = client.parse(task="rejected_link_adjudicator", prompt_version=prompts["ADJ"].version,
                           messages=[{"role": "user", "content": prompts["ADJ"].render(**inp)}], schema=AdjudicationLLM, model_tier="strong")  # fmt: skip
        o = res.output
        dec = o.decision if verify_quote(o.evidence_quote, inp["evidence"]) else "no_decision"
        return {
            "arm": arm,
            "key": r["key"],
            "decision": dec,
            "raw": o.decision,
            "reason": o.reason,
            "input_hash": res.input_hash,
        }
    j = IJ.judge_pair(client, prompts["J1"], domain=inp["domain"], surface=inp["surface"], target_name=inp["target_name"],
                      target_aliases=[a for a in inp["target_aliases"].split(", ") if a and a != "none"], target_type=inp["target_type"],
                      target_gloss=None if inp["target_gloss"] == "none" else inp["target_gloss"], sentence=inp["evidence"])  # fmt: skip
    return {"arm": arm, "key": r["key"], "decision": TO_LABEL.get(j.decision, "no_decision"), "raw": j.raw_decision, "judge_decision": j.decision, "reason": j.reason, "input_hash": j.input_hash}  # fmt: skip


def load_results() -> dict[tuple[str, str], dict]:
    if not RESULTS.exists():
        return {}
    return {(x["arm"], x["key"]): x for x in map(json.loads, RESULTS.read_text().splitlines())}


def run(*, dry_run: bool, limit: int | None) -> dict:
    from cumap.llm.client import LLMClient
    from cumap.llm.cost import spend_from_log
    from cumap.llm.prompts import load_prompt

    items = load_rows()[:limit] if limit else load_rows()
    done = load_results()
    todo = [(a, r) for r in items for a in ARMS if (a, r["key"]) not in done]
    if dry_run:
        return {
            "dry_run": True,
            "rows": len(items),
            "calls": len(todo),
            "est_usd_luna": round(len(todo) * 0.0004, 3),
        }
    st = get_settings()
    if spend_from_log(st, RUN_ID) >= CAP_USD:
        raise SystemExit(f"CR-050 cap reached: ${CAP_USD}")
    client = LLMClient(st, run_id=RUN_ID)
    ps = {
        "ADJ": load_prompt(REPO_ROOT / "prompts", "rejected_link_adjudicator", "v2"),
        "J1": IJ.load_judge_prompt("v1"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        for a, r in todo:
            f.write(json.dumps(judge(client, a, r, ps)) + "\n")
    return {
        "calls": len(todo),
        "spend_usd": round(client.spent_usd, 4),
        "total_usd": round(spend_from_log(st, RUN_ID), 4),
    }


def score() -> dict:
    from cumap.llm.cost import spend_from_log

    rows, res = load_rows(), load_results()
    out: dict = {"rows": len(rows), "gold": dict(Counter(r["gold"] for r in rows)), "arms": {}}
    for arm in ARMS:
        got = {k: x for (a, k), x in res.items() if a == arm}
        if not all(r["key"] in got for r in rows):
            continue
        sc = A.score(rows, got, "fresh")
        sc["accuracy"] = sum(r["gold"] == got[r["key"]]["decision"] for r in rows) / len(rows)
        sc["by_dataset"] = {ds: sum(r["gold"] == got[r["key"]]["decision"] for r in rows if r["dataset"] == ds) / max(1, sum(r["dataset"] == ds for r in rows)) for ds in DOMAIN}  # fmt: skip
        if arm == "J1":
            sc["judge_answers"] = dict(Counter(got[r["key"]].get("judge_decision") for r in rows))
        out["arms"][arm] = sc
    if set(ARMS) <= out["arms"].keys():
        j, a = out["arms"]["J1"], out["arms"]["ADJ"]
        srn = j["same_rows_decided_new"]
        share = srn["count"] / srn["of"] if srn["of"] else 0.0
        ok = (j["precision_same_as_target"]["wilson_lb"] or 0) >= 0.70 and (j["precision_new_concept"]["wilson_lb"] or 0) >= 0.70 and share <= 0.20 and j["accuracy"] >= a["accuracy"]  # fmt: skip
        out["decision"] = {"status": "J1_REPLACES_ADJ" if ok else "KEEP_ADJ", "j1_same_wilson_lb": j["precision_same_as_target"]["wilson_lb"],
                           "j1_new_wilson_lb": j["precision_new_concept"]["wilson_lb"], "j1_same_rows_decided_new_share": share,
                           "j1_accuracy": j["accuracy"], "adj_accuracy": a["accuracy"],
                           "rule": "J1 same and new_concept Wilson LB >= 0.70, <= 20% of gold same rows decided new_concept, J1 accuracy >= ADJ accuracy"}  # fmt: skip
    out["spend_usd"] = round(spend_from_log(get_settings(), RUN_ID), 4)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "judge_v1.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    (OUT / "judge_v1.md").write_text(markdown(out), encoding="utf-8")
    return out.get("decision", {})


def _f(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def markdown(r: dict) -> str:
    L = ["# CR-050: identity judge v1 vs the rejected-link adjudicator v2 on a fresh owner sheet", "",
         (f"Generated by `cumap.cr050.measure --score` ($0). Gold `data/gold/cr050_identity_sheet_marked.csv` (owner-marked, blind, {r['rows']} rows: "
          f"{r['gold']}); luna profile; each row judged once (no tuning on this sheet)."), ""]  # fmt: skip
    d = r.get("decision")
    if d:
        L += [(f"**Decision ({d['rule']}): {d['status']}.** J1 accuracy {_f(d['j1_accuracy'])} vs ADJ {_f(d['adj_accuracy'])}; J1 Wilson LB same {_f(d['j1_same_wilson_lb'])}, "
               f"new {_f(d['j1_new_wilson_lb'])}; gold same rows decided new {d['j1_same_rows_decided_new_share']:.3f}."), ""]  # fmt: skip
    L += [
        "| arm | accuracy (P&D / SciNLP) | new_concept P (LB) | same P (LB) | not_a_concept P | same rows decided new |",
        "|---|---|---|---|---|---|",
    ]
    for arm, s in r["arms"].items():
        pn, ps, pc = (
            s["precision_new_concept"],
            s["precision_same_as_target"],
            s["precision_not_a_concept"],
        )
        L.append(f"| {arm} | {_f(s['accuracy'])} ({_f(s['by_dataset']['pd_production'])} / {_f(s['by_dataset']['scinlp_dev_train'])}) | {pn['correct']}/{pn['decided']} = {_f(pn['precision'])} ({_f(pn['wilson_lb'])}) | {ps['correct']}/{ps['decided']} = {_f(ps['precision'])} ({_f(ps['wilson_lb'])}) | {pc['correct']}/{pc['decided']} | {s['same_rows_decided_new']['count']}/{s['same_rows_decided_new']['of']} |")  # fmt: skip
    L += [""] + [
        f"- {arm} confusion: {s['confusion']}"
        + (f"; judge answers {s['judge_answers']}" if "judge_answers" in s else "")
        for arm, s in r["arms"].items()
    ]
    L += ["", f"Spend: ${r['spend_usd']} of ${CAP_USD}.", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    print(
        json.dumps(
            score() if a.score else run(dry_run=a.dry_run, limit=a.limit), indent=1, default=str
        )
    )


if __name__ == "__main__":
    main()
