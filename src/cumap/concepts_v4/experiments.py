"""CR-009 §7: IIR dev experiments for the concept stage v4. Live arms (the loop with the real model), replays ($0:
loop depth, pruner tau, L0, iteration 0) and scoring with the existing FACE scorer (exact micro F1 is the selection
metric). `python -m cumap.concepts_v4.experiments live --arm G2 --dry-run` prints the preflight first."""

from __future__ import annotations

import argparse
import copy
import json
import re
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import yaml

from cumap.concepts_v4 import runner as R
from cumap.concepts_v4.bank import load as load_bank
from cumap.concepts_v4.cards import Node, NodeStore
from cumap.concepts_v4.loop import LoopConfig, SectionResult
from cumap.concepts_v4.pruner import P1Model, build_rows, dev_rows, norm
from cumap.concepts_v4.verifier import Flag, drop_flagged
from cumap.expert_kg.face_eval import evaluate_mentions
from cumap.llm.prompts import load_prompt

ROOT = Path(".")
DEV_SECTIONS = ROOT / "data/interim/external/iir_sections.jsonl"
DEV_GOLD = ROOT / "data/interim/external/iir_gold_concepts.csv"
OUT = ROOT / "data/processed/concepts_v4"
TAUS = [round(0.1 * i, 1) for i in range(1, 10)]


# ---------------------------------------------------------------- data and models
def load_dev() -> tuple[list[dict], dict[str, set[str]]]:
    secs = [json.loads(x) for x in DEV_SECTIONS.read_text(encoding="utf-8").splitlines() if x]
    for s in secs:
        s["order_index"] = int(s["order_index"])
        s["chapter_num"] = str(s["chapter_num"])
        hp = s.get("heading_path")
        s["heading"] = (
            " > ".join(eval(hp))
            if isinstance(hp, str) and hp.startswith("[")
            else str(hp or s["section_id"])
        )
    emph = {
        s["section_id"]: set(eval(s["emphasized_terms"]))
        if isinstance(s.get("emphasized_terms"), str)
        else set(s.get("emphasized_terms") or [])
        for s in secs
    }
    return sorted(secs, key=lambda s: s["order_index"]), emph


def gold_names(gold) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for g in gold:
        out.setdefault(g.section_id, set()).update(g.names())
    return out


class Embedder:
    """sentence-transformers wrapper with a cache; any callable str -> vector works in tests."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model, self.cache = SentenceTransformer(model_name), {}

    def __call__(self, text: str) -> np.ndarray:
        if text not in self.cache:
            self.cache[text] = np.asarray(
                self.model.encode(text, show_progress_bar=False), dtype=float
            )
        return self.cache[text]


def loco_pruners(sections: list[dict], nlp, embed_fn) -> dict[str, P1Model]:
    """One P1 model per held-out dev chapter (trained on the other chapters only) plus 'all' (trained on all dev)."""
    gold_rows = list(__import__("csv").DictReader(DEV_GOLD.open(encoding="utf-8")))
    gold, cand = dev_rows(gold_rows, sections, nlp)
    chapters = sorted({s["chapter_num"] for s in sections})
    models = {}
    for ch in [*chapters, "all"]:
        train = [s["section_id"] for s in sections if ch == "all" or s["chapter_num"] != ch]
        models[ch] = P1Model(embed_fn, nlp).fit(build_rows(gold, cand, train))
    return models


def loop_config(form: str, max_iterations: int = 3, **kw) -> LoopConfig:
    cfg = yaml.safe_load((ROOT / "configs/concept_gvp.yaml").read_text())
    v = cfg["verifier"]
    return LoopConfig(
        form=form,
        max_iterations=max_iterations,
        per_section_call_budget=v["per_section_call_budget"],
        drop_max=v["drop_without_reprompt_max_flagged"],
        instructions=v["corrective_instructions"],
        prefix=v["correction_prefix"],
        **kw,
    )


# ---------------------------------------------------------------- persistence
def save_run(out: R.RunOutput, path: Path, extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    d = {
        "nodes": {k: n.to_dict() for k, n in out.store.nodes.items()},
        "sections": {k: asdict(v) for k, v in out.sections.items()},
        "section_meta": out.section_meta,
        "pruned": out.pruned,
        "merges": out.merges,
        "backfill": out.backfill,
        "extra": extra or {},
    }
    path.write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")


def load_run(path: Path) -> R.RunOutput:
    d = json.loads(path.read_text(encoding="utf-8"))
    store = NodeStore()
    for k, n in d["nodes"].items():
        n = {x: y for x, y in n.items()}
        store.nodes[k] = Node(**n)
    out = R.RunOutput(store)
    out.sections = {k: SectionResult(**v) for k, v in d["sections"].items()}
    out.section_meta, out.pruned, out.merges, out.backfill = (
        d["section_meta"],
        d["pruned"],
        d["merges"],
        d["backfill"],
    )
    return out


# ---------------------------------------------------------------- scoring
def score(finals: dict[str, list[dict]], gold, sections: list[dict], nlp, embed_fn) -> dict:
    ev = evaluate_mentions(
        finals, gold, {s["section_id"]: s["text"] for s in sections}, nlp=nlp, embed_fn=embed_fn
    )
    m = ev["metrics"]
    return {
        "n_predicted": m["n_predicted"],
        "n_gold": m["n_gold"],
        "exact_micro": m["exact"]["micro"],
        "lenient_micro": m["lenient"]["micro"],
        "exact_macro": m["exact"]["macro"],
        "lenient_macro": m["lenient"]["macro"],
        "recall_by_ngram": m["recall_by_ngram"]["lenient"],
        "precision_by_role": m["precision_by_role"],
    }


def _flags(it: dict) -> list[Flag]:
    return [Flag(f["rule"], f["where"], f["idx"], f["detail"], f.get("sub")) for f in it["flags"]]


def finals_at_depth(
    out: R.RunOutput, k: int, sections: list[dict], gold_nm: dict, *, tau: float | None = None
) -> dict[str, list[dict]]:
    """Replay: iteration k's verified output with flagged items dropped (unresolved M1 are not counted).
    With `tau`, new concepts whose recorded p(growing) < tau are removed too (a replay of the pruner)."""
    finals = {}
    for s in sections:
        res = out.sections.get(s["section_id"])
        if res is None:
            continue
        it = res.iterations[min(k, len(res.iterations) - 1)]
        fin, _ = drop_flagged(it.get("verified", it["output"]), _flags(it))
        finals[s["section_id"]] = fin
    return R.predictions(out, sections, gold_nm, finals=finals, tau=tau, replay=True)


def iteration0_raw(out: R.RunOutput, sections: list[dict], gold_nm: dict) -> dict[str, list[dict]]:
    return R.predictions(
        out,
        sections,
        gold_nm,
        finals={sid: r.iterations[0]["output"] for sid, r in out.sections.items() if r.iterations},
        replay=True,
    )


_M2 = re.compile(r"item (['\"])(.+?)\1 may be the tail of (['\"])(.+?)\3")


def l0_finals(out: R.RunOutput, sections: list[dict], gold_nm: dict) -> dict[str, list[dict]]:
    """CR-009 §7 L0 = PiVe's 'iterative offline correction': iteration 0 with the rules applied OFFLINE: auto-fixes,
    flagged items dropped, M1 hints written as mentions, M2 spans replaced, no re-prompt."""
    finals = {}
    extra: dict[str, list[str]] = {}
    for s in sections:
        res = out.sections.get(s["section_id"])
        if res is None or not res.iterations:
            continue
        it = res.iterations[0]
        fin, _ = drop_flagged(it.get("verified", it["output"]), _flags(it))
        fin = copy.deepcopy(fin)
        for h in it["hints"]:
            if h["rule"] == "M2" and (m := _M2.search(h["detail"])):
                for c in fin["new_concepts"]:
                    if norm(c["name"]) == norm(m.group(2)):
                        c["name"] = m.group(4)
        extra[s["section_id"]] = [h["text"] for h in it["hints"] if h["rule"] == "M1"]
        finals[s["section_id"]] = fin
    pred = R.predictions(out, sections, gold_nm, finals=finals, replay=True)
    for sid, names in extra.items():
        for nm in names:
            pred.setdefault(sid, []).append(
                {
                    "canonical_name": nm,
                    "role": "mentioned",
                    "node_type": "Concept",
                    "evidence_quote": "",
                    "source": "l0",
                }
            )
    return pred


def pick_by_rule(scores: dict[str, float], simplicity: dict[str, tuple], tie: float = 0.02) -> str:
    best = max(scores.values())
    near = [k for k, v in scores.items() if best - v <= tie]
    return min(near, key=lambda k: (simplicity[k], -scores[k]))


# ---------------------------------------------------------------- preflight and live runs
def preflight(
    sections: list[dict],
    form: str,
    max_iterations: int,
    bank_tokens: int = 4500,
    prompt_tokens: int = 1500,
) -> dict:
    words = sum(len(s["text"].split()) for s in sections)
    per_in = prompt_tokens + bank_tokens + 40 * 35  # prompt + bank + ~40 cards
    calls_expected = len(sections) * ((2 if form == "G2" else 1) + max(0, max_iterations // 2))
    calls_worst = len(sections) * ((1 if form == "G2" else 0) + 1 + max_iterations)
    tin = lambda c: c * per_in + int(words * 1.3 * c / len(sections))
    cost = lambda c: (tin(c) * 0.10 + c * 3000 * 0.50) / 1e6
    return {
        "sections": len(sections),
        "calls_expected": calls_expected,
        "calls_worst": calls_worst,
        "usd_expected": round(cost(calls_expected), 3),
        "usd_worst": round(cost(calls_worst), 3),
    }


def run_live(
    arm: str,
    *,
    out_dir: Path,
    form: str,
    max_iterations: int = 3,
    m4: bool = False,
    m5: bool = False,
    tau: float = 0.0,
    loco: bool = True,
    limit: int | None = None,
    progress=print,
    client=None,
    embed_fn=None,
    nlp=None,
    pruners=None,
    backfill: bool = True,
) -> tuple[R.RunOutput, list[dict]]:
    import spacy

    from cumap.config import get_settings
    from cumap.llm.client import LLMClient

    settings = get_settings()
    nlp = nlp or spacy.load("en_core_web_sm")
    embed_fn = embed_fn or Embedder(settings.embeddings.model)
    sections, emph = load_dev()
    if limit:
        sections = sections[:limit]
    client = client or LLMClient(settings, run_id=f"cr009_dev_{arm}")
    pruners = (
        pruners
        if pruners is not None
        else (loco_pruners(load_dev()[0], nlp, embed_fn) if loco else None)
    )
    cfg = loop_config(form, max_iterations)
    run = R.ConceptRun(
        client,
        load_prompt(ROOT / "prompts", "concept_generator", "v4"),
        load_bank(),
        cfg,
        nlp=nlp,
        embed_fn=embed_fn,
        lexicon=None,
        domain="information retrieval",
        backfill_prompt=load_prompt(ROOT / "prompts", "concept_backfill", "v1"),
        pruner_for=(lambda ch: pruners.get(str(ch), pruners["all"]).p_growing) if pruners else None,
        tau=tau,
        rho=1.5,
        m4=m4,
        m5=m5,
        emphasised=emph,
        progress=progress,
    )
    t0 = time.time()
    out = run.run(sections, backfill=backfill)
    out.cost_usd = round(getattr(client, "spent_usd", 0.0), 4)
    save_run(
        out,
        out_dir / f"{arm}.json",
        {
            "arm": arm,
            "form": form,
            "max_iterations": max_iterations,
            "m4": m4,
            "m5": m5,
            "tau": tau,
            "seconds": round(time.time() - t0),
            "spend_usd": out.cost_usd,
        },
    )
    return out, sections


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["live"])
    ap.add_argument("--arm", required=True)
    ap.add_argument("--form", choices=["G1", "G2"], default="G2")
    ap.add_argument("--max-iterations", type=int, default=3)
    ap.add_argument("--m4", action="store_true")
    ap.add_argument("--m5", action="store_true")
    ap.add_argument("--tau", type=float, default=0.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--run-id", default="dev1")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    secs, _ = load_dev()
    secs = secs[: a.limit] if a.limit else secs
    pf = preflight(secs, a.form, a.max_iterations)
    print("preflight:", json.dumps(pf))
    if a.dry_run:
        return
    out, _sections = run_live(
        a.arm,
        out_dir=OUT / a.run_id,
        form=a.form,
        max_iterations=a.max_iterations,
        m4=a.m4,
        m5=a.m5,
        limit=a.limit,
    )
    print(
        f"done: {len(out.store.nodes)} nodes, {sum(r.calls for r in out.sections.values())} calls, spend ${out.cost_usd}"
    )


if __name__ == "__main__":
    main()


def run_test(
    arm: str,
    *,
    out_dir: Path,
    dev_run: Path,
    form: str = "G1",
    max_iterations: int = 1,
    tau: float = 0.1,
    progress=print,
):
    """The IIR test split, run ONCE (CR-009 §7): starts from the final dev run's state and processes the test sections
    in book order with the all-dev pruner (chapters 4+). Never used for selection."""
    import spacy

    from cumap.concepts_v4.arms_dev import load_split
    from cumap.config import get_settings
    from cumap.llm.client import LLMClient

    settings = get_settings()
    nlp = spacy.load("en_core_web_sm")
    embed_fn = Embedder(settings.embeddings.model)
    dev_secs, _emph = load_dev()
    test_secs, _gold = load_split("test")
    pruners = loco_pruners(dev_secs, nlp, embed_fn)
    prev = load_run(dev_run)
    client = LLMClient(settings, run_id=f"cr009_test_{arm}")
    run = R.ConceptRun(
        client,
        load_prompt(ROOT / "prompts", "concept_generator", "v4"),
        load_bank(),
        loop_config(form, max_iterations),
        nlp=nlp,
        embed_fn=embed_fn,
        lexicon=None,
        domain="information retrieval",
        backfill_prompt=load_prompt(ROOT / "prompts", "concept_backfill", "v1"),
        pruner_for=lambda ch: pruners.get(str(ch), pruners["all"]).p_growing,
        tau=tau,
        rho=1.5,
        progress=progress,
    )
    out = run.run(test_secs, store=prev.store, order_offset=len(dev_secs))
    out.cost_usd = round(client.spent_usd, 4)
    save_run(
        out,
        out_dir / f"{arm}.json",
        {
            "arm": arm,
            "split": "test",
            "form": form,
            "max_iterations": max_iterations,
            "tau": tau,
            "spend_usd": out.cost_usd,
        },
    )
    return out, test_secs
