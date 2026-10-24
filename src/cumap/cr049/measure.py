"""CR-049 measurement of the identity judge v2 (GraphJudge elements), pre-registered in docs/DECISIONS.md before any call.

Rows: the owner-checked CR-021 sheet (`data/gold/cr021_rejected_links_review_marked.csv`, read only) with its fixed dev / held-out
split (`cumap.cr021.adjudicator.load_rows`); rows from SciNLP TEST papers are left out of every arm (rule 9). The held-out split was
used once before (CR-021 v2 adoption), so every held-out number here is a SECOND LOOK (owner, 2026-10-24).
Arms, same rows, same model profile (luna), all calls through LLMClient (run id `cr049_identity_judge`):
- `ADJ`: rejected_link_adjudicator v2 (today's production judge for input A), unchanged;
- `J1`:  identity_judge v1 (one sentence + description);
- `J2`:  identity_judge v2 (context packs for the term and the concept; claim-verification framing).
Judge answers map to the sheet labels: same -> same_as_target; narrower / broader / new -> new_concept; not_a_concept -> not_a_concept.
Stress set (reported, not deciding): the approved `different` entries of the production lexicon (v0.5) with a quote; any `same` is a false merge.

    uv run python -m cumap.cr049.measure --split dev --dry-run | --limit 20 | (all)
    uv run python -m cumap.cr049.measure --split heldout          # once
    uv run python -m cumap.cr049.measure --stress
    uv run python -m cumap.cr049.measure --score"""

from __future__ import annotations

import argparse
import json
from functools import cache

from cumap.config import REPO_ROOT, get_settings
from cumap.cr021 import adjudicator as A
from cumap.expert_kg import identity_judge as IJ

RUN_ID = "cr049_identity_judge"
CAP_USD = 3.0
OUT = REPO_ROOT / "reports" / "cr049"
RESULTS = OUT / "results.jsonl"
ARMS = ("ADJ", "J1", "J2")
TO_LABEL = {"same": "same_as_target", "narrower": "new_concept", "broader": "new_concept", "new": "new_concept", "not_a_concept": "not_a_concept"}  # fmt: skip


def rows(split: str) -> list[dict]:
    return [r for r in A.load_rows() if r["split"] == split and r["dataset"] != "scinlp_test"]


@cache
def _sentences(dataset: str) -> dict[str, list[str]]:
    from cumap.expert_kg.relations import split_sentences

    return {
        k: [" ".join(s.split()) for s in split_sentences(t)] for k, t in A._texts(dataset).items()
    }


def packs(r: dict, *, k: int = 3) -> tuple[list[str], list[str]]:
    """Term pack from the row's own section / paper (its sentence first); concept pack from the same section first, then the rest of the text."""
    sents = _sentences(r["dataset"])
    sec = r["section_id"].split("#")[0]
    own = sents.get(sec, [])
    rest = (
        [s for key, ss in sents.items() if key != sec for s in ss]
        if r["dataset"] == "pd_production"
        else []
    )
    sent = A.sentence_for(r)
    n = A._nodes(r["run_id"]).get(r["rejected_target"], {})
    names = [r["rejected_target"], *n.get("aliases", [])]
    term = IJ.context_pack(own, [r["surface"]], first=sent, k=k)
    concept = IJ.context_pack(own + rest, names, exclude=sent, k=k)
    return term, concept


def judge(client, arm: str, r: dict, prompts: dict) -> dict:
    if arm == "ADJ":
        x = A.adjudicate(client, prompts["ADJ"], r)
        return {"arm": arm, "key": r["key"], "split": r["split"], "decision": x["decision"], "raw": x["raw_decision"], "reason": x["reason"], "input_hash": x["input_hash"]}  # fmt: skip
    inp = A.render_inputs(r)
    term, concept = packs(r) if arm == "J2" else (None, None)
    j = IJ.judge_pair(
        client, prompts[arm], domain=inp["domain"], surface=inp["surface"], target_name=inp["target_name"],
        target_aliases=[a for a in inp["target_aliases"].split(", ") if a and a != "none"], target_type=inp["target_type"],
        target_gloss=None if inp["target_gloss"] == "none" else inp["target_gloss"], sentence=inp["evidence"],
        term_context=term, concept_context=concept,
    )  # fmt: skip
    dec = TO_LABEL.get(j.decision, "no_decision")
    return {"arm": arm, "key": r["key"], "split": r["split"], "decision": dec, "raw": j.raw_decision, "judge_decision": j.decision, "reason": j.reason, "input_hash": j.input_hash}  # fmt: skip


def stress_items() -> list[dict]:
    """Approved lexicon `different` pairs with a quote and a section (P&D): TERM = first form, CONCEPT = second form."""
    import yaml

    from cumap.expert_kg.lexicon import production_lexicon_path

    raw = yaml.safe_load(production_lexicon_path().read_text())
    out = []
    for e in raw.get("different", []):
        if (
            e.get("status") != "approved"
            or not e.get("quote")
            or not e.get("section")
            or len(e.get("forms", [])) != 2
        ):
            continue
        a, b = e["forms"]
        out.append({"key": e["id"], "split": "stress", "dataset": "pd_production", "run_id": "slice3_c2", "section_id": str(e["section"]),
                    "surface": a, "rejected_target": b, "target_type": A._nodes("slice3_c2").get(b, {}).get("type", "Concept"), "evidence": e["quote"], "gold": "new_concept"})  # fmt: skip
    return out


def prompts() -> dict:
    from cumap.llm.prompts import load_prompt

    return {"ADJ": load_prompt(REPO_ROOT / "prompts", "rejected_link_adjudicator", "v2"), "J1": IJ.load_judge_prompt("v1"), "J2": IJ.load_judge_prompt("v2")}  # fmt: skip


def load_results() -> dict[tuple[str, str], dict]:
    if not RESULTS.exists():
        return {}
    out = {}
    for line in RESULTS.read_text().splitlines():
        x = json.loads(line)
        out[(x["arm"], x["key"])] = x
    return out


def run(items: list[dict], *, dry_run: bool, limit: int | None) -> dict:
    from cumap.llm.client import LLMClient

    done = load_results()
    todo = [(a, r) for r in items for a in ARMS if (a, r["key"]) not in done]
    todo = todo[: limit * len(ARMS)] if limit else todo
    if dry_run:
        return {
            "dry_run": True,
            "items": len(items),
            "calls": len(todo),
            "est_usd_luna": round(len(todo) * 0.0004, 3),
        }
    from cumap.llm.cost import spend_from_log

    st = get_settings()
    if spend_from_log(st, RUN_ID) >= CAP_USD:
        raise SystemExit(f"CR-049 cap reached: ${CAP_USD}")
    client = LLMClient(st, run_id=RUN_ID)
    ps = prompts()
    OUT.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        for a, r in todo:
            f.write(json.dumps(judge(client, a, r, ps)) + "\n")
    return {
        "calls": len(todo),
        "spend_usd": round(client.spent_usd, 4),
        "total_usd": round(spend_from_log(st, RUN_ID), 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "heldout"])
    ap.add_argument("--stress", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.score:
        from cumap.cr049.score import main as score

        out = score()
    else:
        out = run(stress_items() if a.stress else rows(a.split), dry_run=a.dry_run, limit=a.limit)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
