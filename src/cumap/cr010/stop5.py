"""CR-010 STOP 5: held-out architecture evaluation (`current`, `erst_direct`, `dual`) and the full-replacement gate table.
Definitions are fixed in docs/cr010/STOP5_PREREGISTRATION.md. This module reports; it never selects an architecture.

    uv run python -m cumap.cr010.stop5 mapping   --annotator-sheet <annotator 1 sheet>     # $0: metrics, freezes the recovery table
    uv run python -m cumap.cr010.stop5 direct    --dry-run | --limit 20 | (full)          # erst_direct on the 120 held-out items
    uv run python -m cumap.cr010.stop5 report    --annotator-sheet <annotator 1 sheet>     # $0: gate table and the report
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

import numpy as np
import yaml
from pydantic import ConfigDict, create_model

from cumap.concepts_v4.schema import _Strict
from cumap.config import REPO_ROOT, get_settings
from cumap.eval.stats import wilson_ci
from cumap.gold.validate import verify_quote

CHECKS = REPO_ROOT / "data/interim/checks"
OUT = REPO_ROOT / "data/interim/stop5"
NO_ERST = "NO_ERST_RELATION"
LOSS_COLUMNS = [
    "loss_taxonomy",
    "loss_part_whole_composition",
    "loss_mechanism",
    "loss_network_topology",
    "loss_identifier_semantics",
    "loss_encapsulation_payload_semantics",
    "loss_causal_sign_direction",
    "loss_technical_dependency",
    "loss_tradeoff_semantics",
    "loss_pedagogical_prerequisite",
    "loss_principle_instance_organisation",
]
PEDAGOGICAL_RELATIONS = frozenset({"prerequisite_of"})
RUN_ID = "cr010_stop5_direct"
GATES = {
    "erst_expressibility_min": 0.90,
    "semantic_preservation_min": 0.90,
    "mapping_loss_rate_max": 0.10,
    "critical_loss_wilson95_upper_max": 0.15,
    "reverse_mapping_macro_f1_min": 0.90,
    "represented_relation_recall_min": 0.75,
    "erst_direct_edge_f1_diff_min": -0.05,
    "erst_direct_precision_diff_min": -0.05,
    "mapping_kappa_min": 0.67,
}


# ---------------------------------------------------------------- items
def registry_relations() -> list[str]:
    reg = yaml.safe_load((REPO_ROOT / get_settings().relation_registry).read_text())
    return [r["name"] for r in reg["relations"]]


def load_items(annotator_sheet: Path) -> list[dict]:
    """Manifest key joined to annotator 1's sheet. The key's model fields are used only for the `current` arm and for example
    display; the metrics read the annotator's columns."""
    with (CHECKS / "cr010_relmap180_MANIFEST_KEY_DO_NOT_SHARE.csv").open(encoding="utf-8") as f:
        key = {r["item_id"]: r for r in csv.DictReader(f)}
    with annotator_sheet.open(encoding="utf-8-sig") as f:
        ann = {r["item_id"]: r for r in csv.DictReader(f)}
    assert set(key) == set(ann), "annotator sheet and manifest differ"
    return [{**key[i], **{f"a_{k}": v for k, v in ann[i].items()}} for i in sorted(key)]


def judgement(it: dict) -> str:
    return it["a_current_semantic_relation_judgement"].strip()


def is_valid_relation(it: dict, relations: set[str]) -> bool:
    return judgement(it) in relations


def expressible(it: dict) -> bool:
    return it["a_erst_applies_yes_no"].strip() == "yes"


def survives(it: dict) -> bool:
    return it["a_machine_useful_meaning_survives_yes_no"].strip() == "yes"


def flagged_losses(it: dict) -> list[str]:
    return [c for c in LOSS_COLUMNS if it[f"a_{c}"].strip() == "yes"]


def rep_key(it: dict) -> tuple[str, ...] | None:
    if not expressible(it):
        return None
    g = lambda c: it[f"a_{c}"].strip()
    return (
        g("erst_relation_1"),
        g("erst_relation_2_optional"),
        g("direction_judgement"),
        g("nuclearity_judgement_if_relevant"),
    )


def ratio(k: int, n: int) -> dict:
    w = wilson_ci(k, n)
    return {
        "k": k,
        "n": n,
        "rate": (k / n) if n else None,
        "wilson95": [w.low, w.high] if n else None,
    }


# ---------------------------------------------------------------- mapping metrics
def mapping_metrics(items: list[dict], relations: set[str]) -> dict:
    v = [it for it in items if is_valid_relation(it, relations)]
    n = len(v)
    expr = sum(expressible(it) for it in v)
    surv = sum(survives(it) for it in v)
    crit = [it for it in v if not survives(it) and flagged_losses(it)]
    silent = [it for it in v if not survives(it) and not flagged_losses(it)]
    keys = defaultdict(set)
    for it in v:
        if rep_key(it):
            keys[rep_key(it)].add(judgement(it))
    collide = sum(1 for it in v if rep_key(it) and len(keys[rep_key(it)]) > 1)
    ped = [it for it in v if judgement(it) in PEDAGOGICAL_RELATIONS]
    return {
        "valid_relation_items": n,
        "other_relation_items_outside_gates": sum(judgement(it) == "other" for it in items),
        "none_items": sum(judgement(it) == "none" for it in items),
        "erst_expressibility": ratio(expr, n),
        "semantic_preservation": ratio(surv, n),
        "mapping_loss_rate": ratio(n - surv, n),
        "critical_loss": ratio(len(crit), n),
        "silent_loss_survives_no_without_category": ratio(len(silent), n),
        "relation_collision_rate_among_expressible": ratio(collide, expr),
        "pedagogical_items": len(ped),
        "pedagogical_silent_losses": sum(1 for it in ped if it in silent),
        "pedagogical_flags": sum(
            1
            for it in v
            if it["a_loss_pedagogical_prerequisite"].strip() == "yes"
            or it["a_loss_principle_instance_organisation"].strip() == "yes"
        ),
    }


def loss_by_category(items: list[dict], relations: set[str]) -> list[dict]:
    v = [it for it in items if is_valid_relation(it, relations)]
    rows = []
    for c in LOSS_COLUMNS:
        hit = [it for it in v if it[f"a_{c}"].strip() == "yes"]
        rows.append(
            {
                "category": c.removeprefix("loss_"),
                "count": len(hit),
                "rate": (len(hit) / len(v)) if v else None,
                "examples": [
                    f"{it['item_id']}: {judgement(it)} ({it['name_x']} / {it['name_y']})"
                    for it in hit[:2]
                ],
            }
        )
    return rows


# ---------------------------------------------------------------- reverse recoverability
def _majority(c: Counter) -> str:
    return min(c.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def fit_recovery(dev: list[dict], relations: set[str]) -> dict:
    """Frozen from DEV valid-relation items only. Levels: full key, (erst1, nuclearity), erst1, NO_ERST, global."""
    v = [it for it in dev if is_valid_relation(it, relations)]
    lv: dict[str, dict[str, Counter]] = {
        k: defaultdict(Counter) for k in ("full", "erst1_nuc", "erst1")
    }
    no_erst, glob = Counter(), Counter()
    for it in v:
        glob[judgement(it)] += 1
        k = rep_key(it)
        if k is None:
            no_erst[judgement(it)] += 1
            continue
        lv["full"]["|".join(k)][judgement(it)] += 1
        lv["erst1_nuc"][f"{k[0]}|{k[3]}"][judgement(it)] += 1
        lv["erst1"][k[0]][judgement(it)] += 1
    return {
        "fitted_on": "dev valid-relation items only",
        "n_dev_items": len(v),
        "full": {k: _majority(c) for k, c in lv["full"].items()},
        "erst1_nuc": {k: _majority(c) for k, c in lv["erst1_nuc"].items()},
        "erst1": {k: _majority(c) for k, c in lv["erst1"].items()},
        "NO_ERST": _majority(no_erst) if no_erst else None,
        "global": _majority(glob),
    }


def recover(it: dict, model: dict) -> str:
    k = rep_key(it)
    if k is None:
        return model["NO_ERST"] or model["global"]
    for level, key in (("full", "|".join(k)), ("erst1_nuc", f"{k[0]}|{k[3]}"), ("erst1", k[0])):
        if key in model[level]:
            return model[level][key]
    return model["global"]


def macro_f1(gold: list[str], pred: list[str]) -> tuple[float, dict]:
    labels = sorted(set(gold))
    per = {}
    for lab in labels:
        tp = sum(g == lab and p == lab for g, p in zip(gold, pred, strict=True))
        fp = sum(g != lab and p == lab for g, p in zip(gold, pred, strict=True))
        fn = sum(g == lab and p != lab for g, p in zip(gold, pred, strict=True))
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        per[lab] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "f1": (2 * pr * rc / (pr + rc)) if pr + rc else 0.0,
        }
    return float(np.mean([p["f1"] for p in per.values()])) if per else 0.0, per


def reverse_eval(held: list[dict], model: dict, relations: set[str]) -> dict:
    v = [it for it in held if is_valid_relation(it, relations)]
    gold = [judgement(it) for it in v]
    pred = [recover(it, model) for it in v]
    f1, per = macro_f1(gold, pred)
    represented = {}
    for lab, c in Counter(gold).items():
        hit = sum(1 for g, p in zip(gold, pred, strict=True) if g == lab and p == lab)
        represented[lab] = {
            "n": c,
            "recovered": hit,
            "recall": hit / c,
            "status": "INSUFFICIENT_SUPPORT"
            if c < 5
            else ("PASS" if hit / c >= GATES["represented_relation_recall_min"] else "FAIL"),
        }
    return {"macro_f1": f1, "per_relation_f1": per, "represented": represented, "n": len(v)}


# ---------------------------------------------------------------- edge quality
def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": p,
        "recall": r,
        "f1": (2 * p * r / (p + r)) if p + r else 0.0,
    }


def edge_quality(held: list[dict], predicted_edge: dict[str, bool]) -> dict:
    tp = fp = fn = tn = 0
    for it in held:
        gold = judgement(it) != "none"
        pred = predicted_edge[it["item_id"]]
        tp += gold and pred
        fp += (not gold) and pred
        fn += gold and (not pred)
        tn += (not gold) and (not pred)
    return {**prf(tp, fp, fn), "tn": tn, "n": len(held)}


def current_predictions(held: list[dict]) -> dict[str, bool]:
    return {it["item_id"]: it["current_outcome"] == "edge" for it in held}


# ---------------------------------------------------------------- erst_direct arm
def erst_direct_schema(reg):
    labels = Literal[(*reg.discourse_labels, NO_ERST)]  # type: ignore[valid-type]
    second = Literal[tuple(reg.discourse_labels)] | None  # type: ignore[valid-type]
    signal = create_model(
        "ErstDirectSignalLLM",
        __base__=_Strict,
        kind=(
            Literal[
                "discourse_marker",
                "graphical",
                "lexical",
                "morphological",
                "numerical",
                "reference",
                "semantic",
                "syntactic",
            ],
            ...,
        ),
        subtype=(str | None, ...),
        anchor_text=(str | None, ...),
    )
    return create_model(
        "ErstDirectLLM",
        __config__=ConfigDict(extra="forbid"),
        label=(labels, ...),
        concurrent_label=(second, ...),
        nuclearity=(
            Literal["nucleus_a", "nucleus_b", "both_nuclei", "either", "not_applicable"],
            ...,
        ),
        evidence=(str | None, ...),
        signals=(list[signal], ...),  # type: ignore[valid-type]
        confidence=(float, ...),
    )


def direct_edge_predicted(out: dict, passage: str) -> tuple[bool, str]:
    """Edge iff a real label and a quote that is an exact substring (rule 3); otherwise no edge, with the reason."""
    if out["label"] == NO_ERST:
        return False, "no_erst_relation"
    if not out["evidence"] or not verify_quote(out["evidence"], passage):
        return False, "evidence_not_in_passage"
    return True, "edge"


def run_direct(
    dry_run: bool, limit: int | None, max_usd: float, annotator_sheet: Path | None
) -> dict:
    from cumap.erst.graph import relation_options, signal_options
    from cumap.erst.registry import ErstRegistry
    from cumap.llm.client import BudgetExceededError, LLMClient
    from cumap.llm.prompts import load_prompt

    with (CHECKS / "cr010_relmap180_MANIFEST_KEY_DO_NOT_SHARE.csv").open(encoding="utf-8") as f:
        held = [r for r in csv.DictReader(f) if r["split"] == "test"]
    held.sort(key=lambda r: r["item_id"])
    path = OUT / "erst_direct_test.jsonl"
    done = (
        {json.loads(x)["item_id"] for x in path.read_text().splitlines()}
        if path.exists()
        else set()
    )
    todo = [r for r in held if r["item_id"] not in done]
    if limit:
        todo = todo[:limit]
    reg = ErstRegistry.load()
    prompt = load_prompt(REPO_ROOT / "prompts", "erst_direct", "v1")

    def msg(r: dict) -> str:
        return prompt.render(
            relation_options=relation_options(reg),
            signal_options=signal_options(reg),
            concept_a=r["concept_a"],
            concept_b=r["concept_b"],
            passage=r["sentence"],
        )

    tier = get_settings().llm.tiers["strong"]
    est = (
        sum(len(msg(r)) / 3.5 for r in todo) / 1e6 * tier.usd_per_1m_input_tokens
        + len(todo) * 1200 / 1e6 * tier.usd_per_1m_output_tokens
    )
    info = {
        "todo": len(todo),
        "already_done": len(done),
        "est_usd": round(est, 3),
        "cap_usd": max_usd,
    }
    if dry_run:
        return {"dry_run": True, **info}
    if est > max_usd:
        raise SystemExit(f"estimate {est:.2f} exceeds the cap {max_usd}")
    s = get_settings()
    s.llm.stage_budgets_usd["erst"] = max_usd
    client = LLMClient(s, run_id=RUN_ID)
    schema = erst_direct_schema(reg)
    OUT.mkdir(parents=True, exist_ok=True)
    stopped = None
    with path.open("a", encoding="utf-8") as f:
        for r in todo:
            try:
                res = client.parse(
                    task="erst_direct",
                    prompt_version="v1",
                    messages=[{"role": "user", "content": msg(r)}],
                    schema=schema,
                    model_tier="strong",
                    fixture_name="default",
                )
            except BudgetExceededError as e:
                stopped = str(e)
                break
            out = res.output.model_dump()
            edge, why = direct_edge_predicted(out, r["sentence"])
            f.write(
                json.dumps(
                    {
                        "item_id": r["item_id"],
                        "output": out,
                        "edge": edge,
                        "why": why,
                        "usage": res.usage,
                        "input_hash": res.input_hash,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            f.flush()
    return {**info, "spend_usd": round(client.spent_usd, 4), "stopped_by_budget": stopped}


def direct_results() -> dict[str, dict]:
    p = OUT / "erst_direct_test.jsonl"
    return (
        {json.loads(x)["item_id"]: json.loads(x) for x in p.read_text().splitlines()}
        if p.exists()
        else {}
    )


# ---------------------------------------------------------------- gate table
def gate_table(
    held_metrics: dict, rev: dict, cur: dict, direct: dict | None, kappa: float | None
) -> list[dict]:
    def row(name, thr, obs, ok, extra=""):
        return {
            "gate": name,
            "threshold": thr,
            "observed": obs,
            "status": "NOT_EVALUABLE" if ok is None else ("PASS" if ok else "FAIL"),
            "note": extra,
        }

    rep = [v for v in rev["represented"].values() if v["status"] != "INSUFFICIENT_SUPPORT"]
    min_rec = min((v["recall"] for v in rep), default=None)
    crit_up = (
        held_metrics["critical_loss"]["wilson95"][1]
        if held_metrics["critical_loss"]["wilson95"]
        else None
    )
    d_f1 = (direct["f1"] - cur["f1"]) if direct else None
    d_pr = (direct["precision"] - cur["precision"]) if direct else None
    ped_ok = (
        held_metrics["pedagogical_silent_losses"] == 0 and held_metrics["pedagogical_flags"] == 0
    )
    return [
        row(
            "eRST expressibility",
            ">= 0.90",
            held_metrics["erst_expressibility"]["rate"],
            held_metrics["erst_expressibility"]["rate"] >= GATES["erst_expressibility_min"],
        ),
        row(
            "Semantic preservation",
            ">= 0.90",
            held_metrics["semantic_preservation"]["rate"],
            held_metrics["semantic_preservation"]["rate"] >= GATES["semantic_preservation_min"],
        ),
        row(
            "Mapping-loss rate",
            "<= 0.10",
            held_metrics["mapping_loss_rate"]["rate"],
            held_metrics["mapping_loss_rate"]["rate"] <= GATES["mapping_loss_rate_max"],
        ),
        row(
            "Critical-loss Wilson 95% upper",
            "<= 0.15",
            crit_up,
            None if crit_up is None else crit_up <= GATES["critical_loss_wilson95_upper_max"],
        ),
        row(
            "Reverse-mapping macro F1",
            ">= 0.90",
            rev["macro_f1"],
            rev["macro_f1"] >= GATES["reverse_mapping_macro_f1_min"],
        ),
        row(
            "Represented-relation recall (min over n>=5 relations)",
            ">= 0.75",
            min_rec,
            None if min_rec is None else min_rec >= GATES["represented_relation_recall_min"],
            "per-relation numerators in the report",
        ),
        row(
            "eRST-direct edge-F1 difference",
            ">= -0.05",
            d_f1,
            None if d_f1 is None else d_f1 >= GATES["erst_direct_edge_f1_diff_min"],
        ),
        row(
            "eRST-direct precision difference",
            ">= -0.05",
            d_pr,
            None if d_pr is None else d_pr >= GATES["erst_direct_precision_diff_min"],
        ),
        row(
            "Mapping agreement kappa",
            ">= 0.67",
            kappa,
            None if kappa is None else kappa >= GATES["mapping_kappa_min"],
            "NOT_EVALUABLE: no second human annotator",
        ),
        row(
            "Organisation/pedagogical information (vacuous: REL-MAP-180 has no pedagogical item)",
            "no silent loss",
            {
                "silent": held_metrics["pedagogical_silent_losses"],
                "flags": held_metrics["pedagogical_flags"],
                "items": held_metrics["pedagogical_items"],
            },
            ped_ok,
        ),
    ]


# ---------------------------------------------------------------- main phases
def compute(annotator_sheet: Path) -> dict:
    relations = set(registry_relations())
    items = load_items(annotator_sheet)
    dev = [it for it in items if it["split"] == "dev"]
    held = [it for it in items if it["split"] == "test"]
    OUT.mkdir(parents=True, exist_ok=True)
    fz = OUT / "reverse_recovery_frozen.json"
    if fz.exists():
        model = json.loads(fz.read_text())
    else:
        model = fit_recovery(dev, relations)
        model["sha256_of_content"] = hashlib.sha256(
            json.dumps({k: v for k, v in model.items()}, sort_keys=True).encode()
        ).hexdigest()
        fz.write_text(json.dumps(model, indent=1, sort_keys=True), encoding="utf-8")
    res = {
        "mapping_dev": mapping_metrics(dev, relations),
        "mapping_heldout": mapping_metrics(held, relations),
        "loss_by_category_heldout": loss_by_category(held, relations),
        "loss_by_category_dev": loss_by_category(dev, relations),
        "reverse_recovery_frozen_sha256": model["sha256_of_content"],
        "reverse_heldout": reverse_eval(held, model, relations),
        "reverse_dev_resubstitution_NOT_A_RESULT": reverse_eval(dev, model, relations)["macro_f1"],
        "current": edge_quality(held, current_predictions(held)),
    }
    dr = direct_results()
    if len(dr) == len(held):
        pred = {it["item_id"]: bool(dr[it["item_id"]]["edge"]) for it in held}
        res["erst_direct"] = edge_quality(held, pred)
        res["erst_direct_reasons"] = dict(Counter(d["why"] for d in dr.values()))
        agree = [(it, dr[it["item_id"]]["output"]) for it in held]
        res["erst_direct_vs_annotator_descriptive"] = {
            "applicability_agreement": ratio(
                sum((o["label"] != NO_ERST) == expressible(it) for it, o in agree), len(agree)
            ),
            "label_agreement_when_both_apply": ratio(
                sum(
                    o["label"] == it["a_erst_relation_1"].strip()
                    for it, o in agree
                    if o["label"] != NO_ERST and expressible(it)
                ),
                sum(1 for it, o in agree if o["label"] != NO_ERST and expressible(it)),
            ),
        }
    res["gates"] = gate_table(
        res["mapping_heldout"], res["reverse_heldout"], res["current"], res.get("erst_direct"), None
    )
    res["gates_all_pass_mechanical"] = all(g["status"] == "PASS" for g in res["gates"])
    return res


def _pct(x) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def write_report(res: dict, cost: dict) -> Path:
    """reports/cr010_stop5.md: neutral evidence for Research (sections 4, 6, 7, 9 of the evaluation template)."""
    mh, md = res["mapping_heldout"], res["mapping_dev"]
    rv = res["reverse_heldout"]

    def line(name, key):
        a, b = md[key], mh[key]
        return f"| {name} | {a['k']}/{a['n']} = {_pct(a['rate'])} | {b['k']}/{b['n']} = {_pct(b['rate'])} |"

    L = [
        "# CR-010 STOP 5 - architecture evaluation (evidence for Research; no architecture is selected here)",
        "",
        (
            "Definitions: `docs/cr010/STOP5_PREREGISTRATION.md` (committed before any STOP-5 call). Single annotator (annotator 1); "
            "REL-MAP-180 is relation-balanced, so rates are not natural prevalence. Gates use the 120 held-out items; the dev column is for information."
        ),
        "",
        "## 1. eRST expressibility, 2. semantic preservation (separate blocks)",
        "",
        "| metric (valid-relation items) | dev | held-out |",
        "|---|---|---|",
        line("eRST expressibility", "erst_expressibility"),
        line("Semantic preservation", "semantic_preservation"),
        line("Mapping-loss rate", "mapping_loss_rate"),
        line("Critical-loss rate (survives = no and a loss category named)", "critical_loss"),
        f"| Critical-loss Wilson 95% upper | {_pct((md['critical_loss']['wilson95'] or [0, None])[1])} | {_pct((mh['critical_loss']['wilson95'] or [0, None])[1])} |",
        line(
            "Silent loss (survives = no, no category named)",
            "silent_loss_survives_no_without_category",
        ),
        line(
            "Relation-collision rate (among expressible)",
            "relation_collision_rate_among_expressible",
        ),
        "",
        f"Valid-relation items: dev {md['valid_relation_items']}, held-out {mh['valid_relation_items']}; `other` judgements outside the gates: dev {md['other_relation_items_outside_gates']}, held-out {mh['other_relation_items_outside_gates']}.",
        "",
        "### Loss by category (held-out valid-relation items)",
        "",
        "| category | count | rate | examples |",
        "|---|---|---|---|",
    ]
    for r in res["loss_by_category_heldout"]:
        L.append(
            f"| {r['category']} | {r['count']} | {_pct(r['rate'])} | {'; '.join(r['examples'])} |"
        )
    L += [
        "",
        "## 3. Reverse recoverability",
        "",
        f"Recovery table frozen from the 60 dev items (sha256 `{res['reverse_recovery_frozen_sha256'][:16]}...`) before use; applied once to held-out. **Macro F1 = {rv['macro_f1']:.3f}** over {rv['n']} valid-relation items.",
        "",
        "| relation | n | recovered | recall | status |",
        "|---|---|---|---|---|",
    ]
    for lab, v in sorted(rv["represented"].items(), key=lambda kv: -kv[1]["n"]):
        L.append(f"| {lab} | {v['n']} | {v['recovered']} | {_pct(v['recall'])} | {v['status']} |")
    L += [
        "",
        "## 4. Direct edge quality and architecture results (held-out 120 items)",
        "",
        "| architecture | precision | recall | F1 | TP/FP/FN | cost | notes |",
        "|---|---|---|---|---|---|---|",
    ]
    c = res["current"]
    L.append(
        f"| current | {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} | {c['tp']}/{c['fp']}/{c['fn']} | stored run ($0 now) | frozen CR-009 outcome |"
    )
    if "erst_direct" in res:
        d = res["erst_direct"]
        L.append(
            f"| erst_direct | {d['precision']:.3f} | {d['recall']:.3f} | {d['f1']:.3f} | {d['tp']}/{d['fp']}/{d['fn']} | ${cost.get('erst_direct', 0):.2f} | outcomes {res['erst_direct_reasons']} |"
        )
    L.append(
        "| dual | = current | = current | = current | = current | graph $3.13 + P3 sample $0.91 | concept layer unchanged by construction; discourse graph 2,024 edges (sha256 41cc5e7b...) |"
    )
    if "erst_direct" in res:
        a = res["erst_direct_vs_annotator_descriptive"]
        L.append(
            f"\nDescriptive: erst_direct agrees with annotator 1 on applicability for {a['applicability_agreement']['k']}/{a['applicability_agreement']['n']}; same label when both apply {a['label_agreement_when_both_apply']['k']}/{a['label_agreement_when_both_apply']['n']}."
        )
    L += [
        "",
        "## 5. P3 candidate-routing utility (separate; from `reports/cr010_p3.md`)",
        "",
        (
            "P3-extra 2,547 pairs, 63/150 = 42.0% human-true (CI 33.3-49.7), about 1,070 true edges; eRST-linked units are a useful candidate-discovery signal. "
            "The conditional classifier on those pairs (recall 23/63, precision 23/32) is a classifier finding, not a representation failure. Recall is within the enumerated candidate universe only."
        ),
        "",
        "## 6. Full-replacement gate table (section 9)",
        "",
        "| gate | threshold | observed | status |",
        "|---|---|---|---|",
    ]
    for g in res["gates"]:
        o = g["observed"]
        o = _pct(o) if isinstance(o, float) and abs(o) <= 1 else o
        L.append(
            f"| {g['gate']} | {g['threshold']} | {o} | {g['status']}{(' (' + g['note'] + ')') if g['note'] else ''} |"
        )
    L += [
        "",
        f"Mechanical eligibility under section 9 (all gates PASS): **{'ELIGIBLE' if res['gates_all_pass_mechanical'] else 'NOT ELIGIBLE'}**. IAA gate: NOT_EVALUABLE (no second human annotator); FULL_ERST_REPLACEMENT is ineligible regardless.",
        "",
        "## 7. Cost (this stage)",
        "",
        f"- erst_direct on 120 held-out items: ${cost.get('erst_direct', 0):.2f}. CR-010 totals: pair-recall sample $1.81, eRST graph $3.13, P3 classification $0.91.",
        "",
        "## 8. Limitations and ambiguities for Research",
        "",
        "- Single annotator; adjudicated = annotator 1; no kappa. The annotator marginals (applicability, survival) were seen before the metrics were defined; no per-split metric was.",
        "- 'Critical loss' was not defined by the CR; the pre-registered reading is survives = no plus a named loss category. Silent losses are reported alongside; treating them as critical would raise the critical-loss rate to the mapping-loss rate.",
        "- REL-MAP items are mostly single sentences; eRST relates discourse units, so low applicability is partly a property of the sampled evidence (same-sentence pairs from P0), not only of the inventory. P3 shows eRST structure is informative across sentences.",
        "- erst_direct is run once, prompt frozen; no retuning. The gate difference compares presence of a discourse relation with presence of a concept relation, as the CR specifies for a direct-replacement test.",
        "- Relations with n < 5 held-out valid instances are INSUFFICIENT_SUPPORT. 'other' judgements (relations the registry lacks) are outside every gate denominator.",
        "",
        "Decision form for Research: `reports/cr010_decision_report_template.md` (unselected).",
        "",
    ]
    out = REPO_ROOT / "reports/cr010_stop5.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["mapping", "direct", "report"])
    ap.add_argument("--annotator-sheet")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-usd", type=float, default=3.0)
    a = ap.parse_args()
    if a.phase == "direct":
        print(json.dumps(run_direct(a.dry_run, a.limit, a.max_usd, None), indent=1))
        return
    res = compute(Path(a.annotator_sheet))
    (OUT / "stop5_results.json").write_text(
        json.dumps(res, indent=1, default=str), encoding="utf-8"
    )
    if a.phase == "report":
        from cumap.llm.cost import spend_from_log

        cost = {"erst_direct": spend_from_log(get_settings(), RUN_ID)}
        print(write_report(res, cost))
        return
    keep = ("mapping_heldout", "reverse_heldout", "gates")
    print(json.dumps({k: v for k, v in res.items() if k in keep}, indent=1, default=str))


if __name__ == "__main__":
    main()
