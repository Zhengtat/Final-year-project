"""CR-010 STOP 2: the node-recall experiment on top of the frozen CR-009 pipeline (N0).

N1 (candidate-hint rescue), N3 (N1 without one-token hints) and N2 (selective independent resampling) are post-passes
over a finished N0 run: they read each section's cards and final output, add verified/de-duplicated/pruned items, and
leave the node store of the N0 run untouched (so later sections see the same cards in every arm). Scoring uses the
CR-009 FACE scorer; the selection rule is the pre-registered one in `configs/cr010_node.yaml`.

    uv run python -m cumap.cr010.nodes_exp dry-run --split dev
    uv run python -m cumap.cr010.nodes_exp n0-dev --max-usd 0.5
    uv run python -m cumap.cr010.nodes_exp arms --split dev --max-usd 2 [--limit N]
    uv run python -m cumap.cr010.nodes_exp report --split dev
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

import yaml

from cumap.concepts_v4 import experiments as X
from cumap.concepts_v4 import runner as R
from cumap.concepts_v4.bank import load as load_bank
from cumap.concepts_v4.cards import Card, split_paragraphs
from cumap.concepts_v4.loop import SectionRunner
from cumap.concepts_v4.pruner import norm
from cumap.concepts_v4.verifier import VerifyCtx
from cumap.cr010.candidates import residual_candidates
from cumap.cr010.rescue import merge_additions, run_rescue
from cumap.eval.stats import micro_f1, paired_bootstrap_delta
from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.face_eval import evaluate_mentions
from cumap.expert_kg.face_scorer import (
    GoldConcept,
    PredictedConcept,
    load_gold_concepts,
    match_predictions,
)
from cumap.expert_kg.partial_span import chunk_counts, noun_form_lexicon
from cumap.llm.prompts import load_prompt

ROOT = Path(".")
OUT = ROOT / "data/processed/cr010"
CFG_PATH = ROOT / "configs/cr010_node.yaml"
ARMS = ("N1", "N3", "N2")


def load_cfg() -> dict:
    return yaml.safe_load(CFG_PATH.read_text())


# ---------------------------------------------------------------- data
def split_data(split: str) -> tuple[list[dict], dict[str, set[str]], list[GoldConcept]]:
    from cumap.concepts_v4.arms_dev import load_split

    if split == "dev":
        secs, emph = X.load_dev()
        return secs, emph, load_gold_concepts(X.DEV_GOLD)
    secs, gold_path = load_split("test")
    return secs, {}, load_gold_concepts(gold_path)


def baseline_run(split: str, cfg: dict) -> R.RunOutput:
    path = cfg["baseline"]["dev_run" if split == "dev" else "test_run"]
    return X.load_run(ROOT / path)


def cards_for(out: R.RunOutput, sid: str, text: str) -> list[Card]:
    low = text.lower()
    ids = out.section_meta.get(sid, {}).get("cards_shown", [])
    return [
        Card(out.store.nodes[i], in_text=out.store.nodes[i].name.lower() in low)
        for i in ids
        if i in out.store.nodes
    ]


class SectionContext:
    """Everything the verifier needs for one section, built the way `ConceptRun` builds it."""

    def __init__(self, sections: list[dict], emph: dict[str, set[str]], nlp):
        by: dict[str, list[str]] = {}
        for s in sections:
            by.setdefault(str(s["chapter_num"]), []).append(s["text"])
        self.chap = {
            ch: (chunk_counts(ts, nlp), noun_form_lexicon(ts, nlp)) for ch, ts in by.items()
        }
        self.emph, self.nlp = emph, nlp

    def vctx(self, sec: dict, paras: dict[str, str], cards: list[Card], rho: float = 1.5):
        rec, forms = self.chap[str(sec["chapter_num"])]
        return VerifyCtx(
            section_text=" ".join(paras.values()),
            paragraphs=paras,
            cards=cards,
            lexicon=None,
            nlp=self.nlp,
            rho=rho,
            recurring=rec,
            noun_forms=forms,
            emphasised=self.emph.get(sec["section_id"], set()),
        )


def n_items(final: dict) -> int:
    return len(final["new_concepts"]) + len(final["existing_mentions"])


# ---------------------------------------------------------------- arms
@dataclasses.dataclass
class ArmRun:
    arm: str
    finals: dict[str, dict] = dataclasses.field(default_factory=dict)
    details: dict[str, dict] = dataclasses.field(default_factory=dict)
    calls: int = 0
    cost_usd: float = 0.0


def candidate_kwargs(cfg: dict) -> dict:
    c = cfg["candidates"]
    return {
        "chunk_min_count": c["chunk_min_count"],
        "max_tokens": c["max_tokens"],
        "cap_one_token": c["cap_one_token"],
        "cap_multi_token": c["cap_multi_token"],
        "head_min_chars": c["head_min_chars"],
    }


def run_rescue_arm(
    arm: str,
    out0: R.RunOutput,
    sections: list[dict],
    emph: dict[str, set[str]],
    *,
    client,
    nlp,
    cfg: dict,
    pruner_for,
    tau: float,
    domain: str,
    max_usd: float,
    fixture: str = "default",
    progress=print,
) -> ArmRun:
    """N1 (arm='N1') or N3 (arm='N3': one-token candidates are not shown)."""
    ctx = SectionContext(sections, emph, nlp)
    acfg = AliasConfig.load()
    prompt = load_prompt(ROOT / "prompts", *cfg["rescue"]["prompt"].split("/"))
    run = ArmRun(arm)
    spent0 = getattr(client, "spent_usd", 0.0)
    for sec in sections:
        sid = sec["section_id"]
        if sid not in out0.sections:
            continue
        final0 = out0.sections[sid].final
        paras = split_paragraphs(sec["text"])
        cards = cards_for(out0, sid, sec["text"])
        cands = residual_candidates(
            sec["text"],
            final0,
            nlp,
            heading=str(sec.get("heading") or ""),
            emphasised=emph.get(sid, set()),
            cfg=acfg,
            include_one_token=(arm != "N3"),
            **candidate_kwargs(cfg),
        )
        res = run_rescue(
            client,
            prompt,
            {**sec, "heading": sec.get("heading") or sid},
            paras,
            cards,
            final0,
            cands,
            domain=domain,
            model_tier=cfg["rescue"]["model_tier"],
            fixture=fixture,
        )
        pr = pruner_for(sec["chapter_num"]) if pruner_for else None
        merged, funnel = merge_additions(
            final0, res.out, ctx.vctx(sec, paras, cards), acfg, pr, tau
        )
        run.finals[sid] = merged
        run.calls += res.calls
        outcomes = {
            k: sum(d["decision"] == k for d in res.decisions) for k in cfg["rescue"]["outcomes"]
        }
        run.details[sid] = {
            "candidates": len(cands),
            "one_token_candidates": sum(c.one_token for c in cands),
            "outcomes": outcomes,
            "incomplete": res.incomplete,
            "error": res.error,
            "funnel": funnel,
            "decisions": res.decisions,
            "cand_list": res.candidates,
        }
        run.cost_usd = round(getattr(client, "spent_usd", 0.0) - spent0, 4)
        progress(
            f"{arm} {sid}: {len(cands)} candidates -> {outcomes} -> kept {funnel['kept']} (${run.cost_usd})"
        )
        if run.cost_usd > max_usd:
            raise SystemExit(f"stopped: ${run.cost_usd} exceeds --max-usd {max_usd}")
    return run


def sample2(
    out0: R.RunOutput,
    sections: list[dict],
    emph: dict[str, set[str]],
    *,
    client,
    nlp,
    cfg: dict,
    domain: str,
    only: set[str] | None,
    cache: dict[str, dict],
    max_usd: float,
    progress=print,
) -> dict[str, dict]:
    """An independent second G1 generation per section (it never sees N0's output): same prompt text, a distinct
    cache key, so the model is actually sampled again. `only` restricts to triggered sections."""
    ctx = SectionContext(sections, emph, nlp)
    base = load_prompt(ROOT / "prompts", "concept_generator", "v4")
    variant = dataclasses.replace(base, version=f"{base.version}-{cfg['n2']['sample_label']}")
    runner = SectionRunner(client, variant, load_bank(), X.loop_config("G1", 1), domain=domain)
    spent0 = prev = getattr(client, "spent_usd", 0.0)
    for sec in sections:
        sid = sec["section_id"]
        if sid in cache or sid not in out0.sections or (only is not None and sid not in only):
            continue
        paras = split_paragraphs(sec["text"])
        cards = cards_for(out0, sid, sec["text"])
        res = runner.run(
            {**sec, "heading": sec.get("heading") or sid},
            paras,
            cards,
            None,
            ctx.vctx(sec, paras, cards),
        )
        now = getattr(client, "spent_usd", 0.0)
        cache[sid] = {
            "final": res.final,
            "calls": res.calls,
            "error": res.error,
            "cost_usd": round(now - prev, 5),
        }
        prev = now
        spent = round(now - spent0, 4)
        progress(f"N2 sample {sid}: {n_items(res.final)} items, {res.calls} calls (${spent})")
        if spent > max_usd:
            raise SystemExit(f"stopped: ${spent} exceeds --max-usd {max_usd}")
    return cache


def triggered(final: dict, text: str, theta: float | None) -> bool:
    """The N2 recall-warning condition: fewer than `theta` items per 100 words in N0's final output
    (`theta=None` means always, a reference arm only)."""
    if theta is None:
        return True
    return n_items(final) / max(len(text.split()), 1) * 100 < theta


def replay_n2(
    out0: R.RunOutput,
    sections: list[dict],
    emph: dict[str, set[str]],
    samples: dict[str, dict],
    theta: float | None,
    *,
    nlp,
    pruner_for,
    tau: float,
) -> ArmRun:
    ctx = SectionContext(sections, emph, nlp)
    acfg = AliasConfig.load()
    run = ArmRun("N2")
    for sec in sections:
        sid = sec["section_id"]
        if sid not in out0.sections:
            continue
        final0 = out0.sections[sid].final
        paras = split_paragraphs(sec["text"])
        fire = triggered(final0, sec["text"], theta) and sid in samples
        merged, funnel = final0, {"proposed": 0, "kept": 0, "kept_names": []}
        if fire:
            cards = cards_for(out0, sid, sec["text"])
            pr = pruner_for(sec["chapter_num"]) if pruner_for else None
            merged, funnel = merge_additions(
                final0, samples[sid]["final"], ctx.vctx(sec, paras, cards), acfg, pr, tau
            )
            run.calls += samples[sid]["calls"]
        run.finals[sid] = merged
        run.details[sid] = {"triggered": fire, "funnel": funnel}
    return run


# ---------------------------------------------------------------- scoring
def exact_counts(preds: dict[str, list[dict]], gold: list[GoldConcept]):
    """Per-section exact (tp, fp, fn) and the match rows (used for the paired bootstrap and rescue precision)."""
    gold = [g for g in gold if g.section_id in preds]
    pc = [
        PredictedConcept(sid, m["canonical_name"], m["role"])
        for sid, ms in preds.items()
        for m in ms
    ]
    rows = match_predictions(pc, gold, lenient=False)
    counts = {sid: [0, 0, 0] for sid in preds}
    for r in rows:
        counts[r.predicted.section_id][0 if r.matched_gold is not None else 1] += 1
    n_gold: dict[str, int] = {}
    for g in gold:
        n_gold[g.section_id] = n_gold.get(g.section_id, 0) + 1
    for sid, c in counts.items():
        c[2] = n_gold.get(sid, 0) - c[0]
    return {sid: tuple(c) for sid, c in counts.items()}, rows


def score_arm(
    arm: ArmRun | None,
    out0: R.RunOutput,
    sections: list[dict],
    gold: list[GoldConcept],
    nlp,
    embed,
) -> dict:
    gnm = X.gold_names(gold)
    sec_ids = [s["section_id"] for s in sections if s["section_id"] in out0.sections]
    finals = None if arm is None else {sid: arm.finals[sid] for sid in sec_ids if sid in arm.finals}
    preds = R.predictions(out0, sections, gnm, finals=finals)
    ev = evaluate_mentions(
        preds, gold, {s["section_id"]: s["text"] for s in sections}, nlp=nlp, embed_fn=embed
    )
    m = ev["metrics"]
    counts, rows = exact_counts(preds, gold)
    added = {
        sid: {norm(n) for n in d["funnel"]["kept_names"]}
        for sid, d in (arm.details if arm else {}).items()
    }
    add_rows = [
        r
        for r in rows
        if norm(r.predicted.canonical_name) in added.get(r.predicted.section_id, set())
    ]
    one = lambda kind: m["recall_by_ngram"][kind].get("1", {"recall": float("nan")})["recall"]
    fp_causes = ev["cause_counts"]["false_positive"]
    return {
        "n_predicted": m["n_predicted"],
        "n_gold": m["n_gold"],
        "exact": m["exact"]["micro"],
        "lenient_micro_f1": m["lenient"]["micro"]["f1"],
        "exact_macro_f1": m["exact"]["macro"]["f1"],
        "recall_by_ngram_lenient": m["recall_by_ngram"]["lenient"],
        "one_token_recall_exact": one("exact"),
        "one_token_recall_lenient": one("lenient"),
        "partial_span_errors": {
            k: v for k, v in fp_causes.items() if k.startswith(("over-specific", "over-general"))
        },
        "added_items": len(add_rows),
        "added_exact_tp": sum(r.matched_gold is not None for r in add_rows),
        "sec_counts": counts,
        "micro_f1_check": micro_f1(list(counts.values())),
    }


# ---------------------------------------------------------------- selection (pre-registered)
def select_node_arm(rows: dict[str, dict], cfg: dict) -> tuple[str, dict[str, dict]]:
    """`rows[arm]` = {delta, lo95, precision_drop, f1}. Qualify: (delta >= min_gain or lo95 > 0) and precision drop
    <= max_precision_drop. Among qualifying arms within `tie_band` of the best F1, the simplest wins; if none
    qualifies the result is N0 (no change is allowed)."""
    sel = cfg["selection"]
    verdict = {}
    for arm, r in rows.items():
        gain = r["delta"] >= sel["min_gain"] - 1e-9 or r["lo95"] > 0
        prec = r["precision_drop"] <= sel["max_precision_drop"] + 1e-9
        verdict[arm] = {"gain_ok": gain, "precision_ok": prec, "qualifies": gain and prec}
    qual = [a for a, v in verdict.items() if v["qualifies"]]
    if not qual:
        return "N0", verdict
    best = max(rows[a]["f1"] for a in qual)
    near = [a for a in qual if best - rows[a]["f1"] <= sel["tie_band"] + 1e-9]
    order = sel["simplicity_order"]
    return min(near, key=lambda a: (order.index(a), -rows[a]["f1"])), verdict


def compare(base: dict, other: dict, cfg: dict) -> dict:
    b = cfg["bootstrap"]
    bs = paired_bootstrap_delta(base["sec_counts"], other["sec_counts"], n=b["n"], seed=b["seed"])
    return {
        **bs,
        "f1": other["exact"]["f1"],
        "base_f1": base["exact"]["f1"],
        "precision_drop": base["exact"]["precision"] - other["exact"]["precision"],
        "delta": other["exact"]["f1"] - base["exact"]["f1"],
    }


# ---------------------------------------------------------------- persistence
def save_arm(run: ArmRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataclasses.asdict(run), indent=1, default=str), encoding="utf-8")


def load_arm(path: Path) -> ArmRun:
    return ArmRun(**json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------- dry run ($0)
def dry_run(split: str, limit: int | None) -> dict:
    import spacy

    from cumap.config import get_settings

    cfg = load_cfg()
    settings = get_settings()
    nlp = spacy.load("en_core_web_sm")
    sections, emph, _gold = split_data(split)
    sections = sections[:limit] if limit else sections
    tier = settings.llm.tiers[cfg["rescue"]["model_tier"]]
    out0 = baseline_run(split, cfg) if (ROOT / cfg["baseline"][f"{split}_run"]).exists() else None
    acfg = AliasConfig.load()
    prompt = load_prompt(ROOT / "prompts", *cfg["rescue"]["prompt"].split("/"))
    stats = {"sections": len(sections), "N1": {}, "N3": {}}
    for arm in ("N1", "N3"):
        cands = calls = tin = 0
        one = 0
        for sec in sections:
            if out0 is None or sec["section_id"] not in out0.sections:
                continue
            final0 = out0.sections[sec["section_id"]].final
            cl = residual_candidates(
                sec["text"],
                final0,
                nlp,
                heading=str(sec.get("heading") or ""),
                emphasised=emph.get(sec["section_id"], set()),
                cfg=acfg,
                include_one_token=(arm != "N3"),
                **candidate_kwargs(cfg),
            )
            if not cl:
                continue
            paras = split_paragraphs(sec["text"])
            from cumap.cr010.rescue import render_rescue

            text = render_rescue(
                prompt,
                domain="information retrieval",
                heading=str(sec.get("heading")),
                cards=cards_for(out0, sec["section_id"], sec["text"]),
                final=final0,
                paras=paras,
                cands=cl,
            )
            calls += 1
            cands += len(cl)
            one += sum(c.one_token for c in cl)
            tin += len(text) // 4
        tout = calls * 1500 + cands * 80  # reasoning slack + ~80 tokens per decision
        usd = (tin * tier.usd_per_1m_input_tokens + tout * tier.usd_per_1m_output_tokens) / 1e6
        stats[arm] = {
            "calls": calls,
            "candidates": cands,
            "one_token_candidates": one,
            "est_input_tokens": tin,
            "est_output_tokens": tout,
            "est_usd": round(usd, 4),
        }
    pf = X.preflight(sections, "G1", 1)
    stats["N2_all_sections_sample"] = pf
    return stats


# ---------------------------------------------------------------- CLI
def _common():
    import spacy

    from cumap.config import get_settings

    settings = get_settings()
    nlp = spacy.load("en_core_web_sm")
    return settings, nlp, X.Embedder(settings.embeddings.model)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["dry-run", "n0-dev", "n0-test-replicate", "arms", "report"])
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--arms", nargs="+", default=list(ARMS))
    a = ap.parse_args()
    cfg = load_cfg()
    if a.phase == "dry-run":
        print(json.dumps(dry_run(a.split, a.limit), indent=1))
        return
    from cumap.llm.client import LLMClient

    settings, nlp, embed = _common()
    domain = "information retrieval"
    dev_secs, _dev_emph, _ = split_data("dev")
    pruners = X.loco_pruners(dev_secs, nlp, embed)
    pruner_for = lambda ch: pruners.get(str(ch), pruners["all"]).p_growing
    gv = yaml.safe_load((ROOT / "configs/concept_gvp.yaml").read_text())
    tau = gv["pruner"]["tau"]
    if a.phase == "n0-dev":
        client = LLMClient(settings, run_id="cr010_dev_N0")
        out, _s = X.run_live(
            "N0",
            out_dir=OUT / "dev",
            form=gv["generator"]["form"],
            max_iterations=gv["verifier"]["max_iterations"],
            tau=tau,
            limit=a.limit,
            client=client,
            embed_fn=embed,
            nlp=nlp,
            pruners=pruners,
        )
        print(f"N0 dev: {len(out.store.nodes)} nodes, spend ${out.cost_usd}")
        return
    if a.phase == "n0-test-replicate":
        # baseline-stability sensitivity check: ONE fresh N0 run on the test split, started from the dev N0 state;
        # never used to select anything (the frozen CR-009 test run stays the historical comparator)
        client = LLMClient(settings, run_id="cr010_test_N0rep")
        out, _s = X.run_test(
            "N0rep",
            out_dir=OUT / "test",
            dev_run=ROOT / cfg["baseline"]["dev_run"],
            form=gv["generator"]["form"],
            max_iterations=gv["verifier"]["max_iterations"],
            tau=tau,
            client=client,
        )
        print(f"N0rep test: {len(out.store.nodes)} nodes, spend ${out.cost_usd}")
        return
    sections, emph, gold = split_data(a.split)
    sections = sections[: a.limit] if a.limit else sections
    out0 = baseline_run(a.split, cfg)
    d = OUT / a.split
    if a.phase == "arms":
        client = LLMClient(settings, run_id=f"cr010_{a.split}_arms")
        for arm in [x for x in a.arms if x in ("N1", "N3")]:
            run = run_rescue_arm(
                arm,
                out0,
                sections,
                emph,
                client=client,
                nlp=nlp,
                cfg=cfg,
                pruner_for=pruner_for,
                tau=tau,
                domain=domain,
                max_usd=a.max_usd,
            )
            save_arm(run, d / f"{arm}.json")
        if "N2" in a.arms:
            sp = d / "N2_samples.json"
            cache = json.loads(sp.read_text()) if sp.exists() else {}
            theta = cfg["n2"]["trigger_frozen"] if a.split == "test" else None
            only = (
                {
                    s["section_id"]
                    for s in sections
                    if s["section_id"] in out0.sections
                    and triggered(out0.sections[s["section_id"]].final, s["text"], theta)
                }
                if a.split == "test"
                else None
            )
            if a.split == "test" and theta is None:
                raise SystemExit("N2 on test needs n2.trigger_frozen set on dev first")
            sample2(
                out0,
                sections,
                emph,
                client=client,
                nlp=nlp,
                cfg=cfg,
                domain=domain,
                only=only,
                cache=cache,
                max_usd=a.max_usd,
            )
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        print(f"spend ${round(client.spent_usd, 4)}")
        return
    from cumap.cr010.nodes_report import write_report

    print(write_report(a.split, cfg, out0, sections, emph, gold, nlp, embed, pruner_for, tau))


if __name__ == "__main__":
    main()
