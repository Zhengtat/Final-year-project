"""CR-009 §7 dev report: score the live runs and the $0 replays, apply the pre-registered selection rule, write
`reports/cr009_stop2_dev.md`. Run: `uv run python -m cumap.concepts_v4.dev_report --run dev1 --g1 G1 --g2 G2 ...`."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import spacy

from cumap.concepts_v4 import experiments as X
from cumap.expert_kg.face_scorer import load_gold_concepts

ROOT = Path(".")


def _row(name: str, sc: dict, calls: str = "", note: str = "") -> str:
    rb = sc["recall_by_ngram"]
    r = " / ".join(f"{rb[k]:.2f}" if isinstance(rb, dict) and k in rb else "–" for k in ("1", "2", "3", "4"))
    return (f"| {name} | {sc['n_predicted']} | {sc['exact_micro']['precision']:.3f} / {sc['exact_micro']['recall']:.3f} / **{sc['exact_micro']['f1']:.3f}** | "
            f"{sc['lenient_micro']['f1']:.3f} | {sc['exact_macro']['f1']:.3f} | {r} | {calls} | {note} |")


HEAD = "| arm | predicted | exact P / R / F1 (micro) | lenient micro F1 | exact macro F1 | recall 1/2/3/4-gram (lenient) | calls | note |\n|---|---|---|---|---|---|---|---|"


def calls_of(out) -> int:
    return sum(r.calls for r in out.sections.values()) + len([b for b in out.backfill if "error" not in b])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="dev1")
    ap.add_argument("--out", default="reports/cr009_stop2_dev.md")
    ap.add_argument("--arms", nargs="+", required=True, help="arm file stems in the run dir, in step order")
    a = ap.parse_args()
    from cumap.config import get_settings

    nlp = spacy.load("en_core_web_sm")
    embed = X.Embedder(get_settings().embeddings.model)
    sections, _ = X.load_dev()
    gold = load_gold_concepts(X.DEV_GOLD)
    gnm = X.gold_names(gold)
    d = X.OUT / a.run
    runs = {s: X.load_run(d / f"{s}.json") for s in a.arms}
    extra = {s: json.loads((d / f"{s}.json").read_text())["extra"] for s in a.arms}
    L = ["# CR-009 STOP 2 — IIR dev results (13 sections; exact micro F1 selects)", "", "Pre-registration: DECISIONS 2026-10-03. Scored with the existing FACE scorer; a mention is scored like a new concept.", ""]
    scored: dict[str, dict] = {}
    for s, out in runs.items():
        scored[s] = X.score(X.finals_at_depth(out, extra[s]["max_iterations"], sections, gnm), gold, sections, nlp, embed)
    b0 = json.loads((ROOT / "data/processed/ablation/abl_20de9701/E3.json").read_text())["scores"]
    L += ["## Live arms and the selection steps", "", HEAD]
    L.append(_row("B0 = v3 (CR-007, E3)", {"n_predicted": b0["n_predicted"], "exact_micro": b0["exact_micro"], "lenient_micro": b0["lenient_micro"], "exact_macro": b0["exact_macro"], "recall_by_ngram": b0.get("recall_by_ngram", {})}, "1 / section", "reported, not selected"))
    for s, sc in scored.items():
        L.append(_row(s, sc, str(calls_of(runs[s])), f"form {extra[s]['form']}, iterations <= {extra[s]['max_iterations']}, M4 {extra[s]['m4']}, M5 {extra[s]['m5']}, ${extra[s]['spend_usd']}"))
    # replays on the first arm that is a step-1 candidate
    base = a.arms[0] if len(a.arms) == 1 else None
    L += ["", "## Verifier statistics per arm", "", "| arm | sections Correct | stop reasons | flags per rule | hints added / rejected | restored | iterations histogram |", "|---|---|---|---|---|---|---|"]
    for s, out in runs.items():
        rs = list(out.sections.values())
        stops = Counter(r.stop_reason for r in rs)
        fl = Counter()
        for r in rs:
            fl.update(r.flags_by_rule)
        hist = Counter(len(r.iterations) - 1 for r in rs)
        L.append(f"| {s} | {stops.get('correct', 0)} / {len(rs)} | {dict(stops)} | {dict(fl)} | {sum(r.hints_added for r in rs)} / {sum(r.hints_rejected for r in rs)} | {sum(r.restored for r in rs)} | {dict(sorted(hist.items()))} |")
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote", a.out)
    json.dump(scored, open(d / "scores.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
