"""CR-021 option 1: a measured LLM adjudicator for links the strict G-link check rejected (pre-registered in DECISIONS.md 2026-10-15).

    uv run python -m cumap.cr021.adjudicator --split dev --dry-run
    uv run python -m cumap.cr021.adjudicator --split dev --limit 20
    uv run python -m cumap.cr021.adjudicator --split dev
    uv run python -m cumap.cr021.adjudicator --split heldout          # once, with the version chosen on dev
    uv run python -m cumap.cr021.adjudicator --score                  # reports/cr021/adjudicator.{json,md}

All calls go through LLMClient (cache, log, run id `cr021_adjudicator`). The gold sheet is read only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from functools import cache

from cumap.concepts_v4.rejected_links import AdjudicationLLM
from cumap.config import REPO_ROOT, get_settings
from cumap.gold.validate import verify_quote

GOLD = REPO_ROOT / "data/gold/cr021_rejected_links_review_marked.csv"
OUT = REPO_ROOT / "reports/cr021"
RESULTS = OUT / "adjudicator_results.jsonl"
RUN_ID = "cr021_adjudicator"
CAP_USD = 3.0
VERSION = "v2"
LABELS = ("new_concept", "same_as_target", "not_a_concept")
DOMAIN = {"pd_production": "computer networking", "scinlp_dev": "natural language processing research", "scinlp_test": "natural language processing research"}  # fmt: skip
D, S = "MARK_distinct_concept (yes/no)", "MARK_same_as_target (yes/no)"


def gold_label(r: dict) -> str:
    d, s = r[D].strip().lower(), r[S].strip().lower()
    return "same_as_target" if s == "yes" else "new_concept" if d == "yes" else "not_a_concept"


def load_rows() -> list[dict]:
    rows = list(csv.DictReader(GOLD.open(encoding="utf-8-sig")))
    for r in rows:
        r["gold"] = gold_label(r)
        r["key"] = hashlib.sha256(
            f"cr021|{r['run_id']}|{r['section_id']}|{r['surface']}|{r['rejected_target']}".encode()
        ).hexdigest()
    by: dict[str, list[dict]] = {}
    for r in sorted(rows, key=lambda x: x["key"]):
        by.setdefault(r["gold"], []).append(r)
    for grp in by.values():  # stratified alternation (pre-registered)
        for i, r in enumerate(grp):
            r["split"] = "dev" if i % 2 == 0 else "heldout"
    first: dict[str, str] = {}
    for r in rows:  # an item listed twice in the sheet stays in ONE split (the first copy's); no other row moves
        r["split"] = first.setdefault(r["key"], r["split"])
    return rows


# ---------------------------------------------------------------- inputs (target node and the full sentence)
@cache
def _nodes(run_id: str) -> dict[str, dict]:
    v = json.loads((REPO_ROOT / "data/processed/kg" / run_id / "v4_concepts.json").read_text())
    nodes = v["nodes"] if isinstance(v["nodes"], list) else list(v["nodes"].values())
    return {n["name"]: n for n in nodes}


@cache
def _texts(dataset: str) -> dict[str, str]:
    if dataset == "pd_production":
        from cumap.cr012.pd_e2e import load_sections

        return {r["section_id"]: r["text"] for r in load_sections()}
    from cumap.cr012.adapters import SciNLPAdapter

    return {
        d.doc_key: d.text
        for d in SciNLPAdapter().load_documents("dev" if dataset == "scinlp_dev" else "test")
    }


def sentence_for(r: dict) -> str:
    from cumap.expert_kg.relations import split_sentences

    ev = " ".join(r["evidence"].split())
    text = _texts(r["dataset"]).get(r["section_id"].split("#")[0], "")
    for s in split_sentences(text):
        if ev and ev in " ".join(s.split()):
            return " ".join(s.split())
    return r["evidence"]


def render_inputs(r: dict) -> dict:
    n = _nodes(r["run_id"]).get(r["rejected_target"], {})
    return {
        "domain": DOMAIN[r["dataset"]], "surface": r["surface"], "target_name": r["rejected_target"],
        "target_aliases": ", ".join(n.get("aliases", [])) or "none", "target_type": r["target_type"],
        "target_gloss": n.get("definition") or n.get("gloss") or "none", "evidence": sentence_for(r),
    }  # fmt: skip


def adjudicate(client, prompt, r: dict) -> dict:
    inp = render_inputs(r)
    res = client.parse(
        task="rejected_link_adjudicator", prompt_version=prompt.version,
        messages=[{"role": "user", "content": prompt.render(**inp)}], schema=AdjudicationLLM, model_tier="strong",
    )  # fmt: skip
    o = res.output
    ok = verify_quote(o.evidence_quote, inp["evidence"])
    return {"key": r["key"], "split": r["split"], "version": prompt.version, "decision": o.decision if ok else "no_decision",
            "raw_decision": o.decision, "quote_verified": ok, "confidence": o.confidence, "reason": o.reason, "input_hash": res.input_hash}  # fmt: skip


# ---------------------------------------------------------------- scoring
def wilson(k: int, n: int, z: float = 1.96) -> float | None:
    if not n:
        return None
    p = k / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (
        1 + z * z / n
    )


def score(rows: list[dict], results: dict[str, dict], split: str) -> dict:
    sel = [(r, results[r["key"]]) for r in rows if r["split"] == split and r["key"] in results]
    conf = Counter((r["gold"], x["decision"]) for r, x in sel)
    out = {"n": len(sel), "confusion": {f"{g}->{p}": c for (g, p), c in sorted(conf.items())}}
    for lab in LABELS:
        dec = [r for r, x in sel if x["decision"] == lab]
        k = sum(r["gold"] == lab for r in dec)
        out[f"precision_{lab}"] = {
            "correct": k,
            "decided": len(dec),
            "precision": k / len(dec) if dec else None,
            "wilson_lb": wilson(k, len(dec)),
        }
    gs = [x for r, x in sel if r["gold"] == "same_as_target"]
    out["same_rows_decided_new"] = {
        "count": sum(x["decision"] == "new_concept" for x in gs),
        "of": len(gs),
        "rate": (sum(x["decision"] == "new_concept" for x in gs) / len(gs)) if gs else None,
    }
    out["accuracy"] = sum(r["gold"] == x["decision"] for r, x in sel) / len(sel) if sel else None
    pn, sr = out["precision_new_concept"], out["same_rows_decided_new"]
    out["adopt_promotion"] = bool(
        pn["wilson_lb"] is not None
        and pn["wilson_lb"] >= 0.70
        and sr["rate"] is not None
        and sr["rate"] <= 0.20
    )
    ps = out["precision_same_as_target"]
    out["adopt_aliasing"] = bool(ps["wilson_lb"] is not None and ps["wilson_lb"] >= 0.70)
    return out  # fmt: skip


def load_results() -> dict[str, dict]:
    if not RESULTS.exists():
        return {}
    return {
        x["key"]: x
        for x in map(json.loads, RESULTS.read_text().splitlines())
        if x.get("version") == VERSION
    }


def spend() -> float:
    from cumap.llm.cost import spend_from_log

    return round(spend_from_log(get_settings(), RUN_ID), 4)


def run(split: str, *, limit: int | None, dry_run: bool) -> dict:
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    rows = [r for r in load_rows() if r["split"] == split]
    done = load_results()
    todo = [r for r in rows if r["key"] not in done][: limit or None]
    if dry_run:
        return {
            "split": split,
            "rows": len(rows),
            "todo": len(todo),
            "est_usd_upper": round(len(todo) * 0.01, 3),
            "spent_usd": spend(),
        }
    if spend() + len(todo) * 0.01 > CAP_USD:
        raise SystemExit(
            f"CR-021 adjudicator cap ${CAP_USD}: spent ${spend()}, {len(todo)} calls left"
        )
    settings = get_settings()
    client = LLMClient(settings, run_id=RUN_ID)
    prompt = load_prompt(REPO_ROOT / "prompts", "rejected_link_adjudicator", VERSION)
    OUT.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a") as f:
        for r in todo:
            f.write(json.dumps(adjudicate(client, prompt, r)) + "\n")
    return {"split": split, "classified": len(todo), "spent_usd": spend()}


def report() -> dict:
    rows, res = load_rows(), load_results()
    out = {"version": VERSION, "gold": str(GOLD.relative_to(REPO_ROOT)), "gold_provenance": "model-assisted, checked by the owner",
           "spent_usd": spend(), "label_counts": {s: dict(Counter(r["gold"] for r in rows if r["split"] == s)) for s in ("dev", "heldout")},
           "dev": score(rows, res, "dev"), "heldout": score(rows, res, "heldout")}  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "adjudicator.json").write_text(json.dumps(out, indent=1))
    L = [f"# CR-021 rejected-link adjudicator ({VERSION})", "",
         f"Gold `{out['gold']}` ({out['gold_provenance']}); stratified 70/70 split; strong tier; spend ${out['spent_usd']:.2f} of ${CAP_USD:.0f}.", ""]  # fmt: skip
    for s in ("dev", "heldout"):
        x = out[s]
        if not x["n"]:
            continue
        L += [
            f"## {s} ({x['n']} rows, accuracy {x['accuracy']:.3f})",
            "",
            "| decision | correct / decided | precision | Wilson LB |",
            "|---|---|---|---|",
        ]
        for lab in LABELS:
            p = x[f"precision_{lab}"]
            L.append(
                f"| {lab} | {p['correct']} / {p['decided']} | {p['precision'] if p['precision'] is None else round(p['precision'], 3)} | {p['wilson_lb'] if p['wilson_lb'] is None else round(p['wilson_lb'], 3)} |"
            )
        sr = x["same_rows_decided_new"]
        L += ["", f"Gold same-as-target rows decided new_concept: {sr['count']} / {sr['of']}.", f"Confusion (gold->decision): {x['confusion']}",
              f"Adopt promotion: **{x['adopt_promotion']}** · adopt aliasing: **{x['adopt_aliasing']}** (pre-registered rule; binding on heldout only).", ""]  # fmt: skip
    (OUT / "adjudicator.md").write_text("\n".join(L) + "\n")
    return {k: out[k] for k in ("spent_usd", "label_counts")} | {
        s: {k: out[s].get(k) for k in ("n", "accuracy", "adopt_promotion", "adopt_aliasing")}
        for s in ("dev", "heldout")
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "heldout"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    print(
        json.dumps(
            report() if a.score else run(a.split, limit=a.limit, dry_run=a.dry_run),
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
