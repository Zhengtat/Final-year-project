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


def _rec(rb, k):
    v = rb.get(k) if isinstance(rb, dict) else None
    return "–" if v is None else f"{(v['recall'] if isinstance(v, dict) else v):.2f}"


def _prf(x):
    return (
        x if isinstance(x, dict) else {"precision": float("nan"), "recall": float("nan"), "f1": x}
    )


def _row(name: str, sc: dict, calls: str = "", note: str = "") -> str:
    e, ln, em = _prf(sc["exact_micro"]), _prf(sc["lenient_micro"]), _prf(sc["exact_macro"])
    r = " / ".join(_rec(sc["recall_by_ngram"], k) for k in "1234")
    return f"| {name} | {sc['n_predicted']} | {e['precision']:.3f} / {e['recall']:.3f} / **{e['f1']:.3f}** | {ln['f1']:.3f} | {em['f1']:.3f} | {r} | {calls} | {note} |"


HEAD = "| arm | predicted | exact P / R / F1 (micro) | lenient micro F1 | exact macro F1 | recall 1/2/3/4-gram (lenient) | calls | note |\n|---|---|---|---|---|---|---|---|"


def calls_of(out) -> int:
    return sum(r.calls for r in out.sections.values()) + len(
        [b for b in out.backfill if "error" not in b]
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="dev1")
    ap.add_argument("--out", default="reports/cr009_stop2_dev.md")
    ap.add_argument(
        "--arms", nargs="+", required=True, help="arm file stems in the run dir, in step order"
    )
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
    L = [
        "# CR-009 STOP 2 — IIR dev results (13 sections; exact micro F1 selects)",
        "",
        "Pre-registration: DECISIONS 2026-10-03. Scored with the existing FACE scorer; a mention is scored like a new concept.",
        "",
    ]
    scored: dict[str, dict] = {}
    for s, out in runs.items():
        scored[s] = X.score(
            X.finals_at_depth(out, extra[s]["max_iterations"], sections, gnm),
            gold,
            sections,
            nlp,
            embed,
        )
    b0 = json.loads((ROOT / "data/processed/ablation/abl_20de9701/E3.json").read_text())["scores"]
    L += ["## Live arms and the selection steps", "", HEAD]
    L.append(
        _row(
            "B0 = v3 (CR-007, E3)",
            {
                "n_predicted": b0["n_predicted"],
                "exact_micro": b0["exact_micro"],
                "lenient_micro": b0["lenient_micro"],
                "exact_macro": b0["exact_macro"],
                "recall_by_ngram": b0.get("recall_by_ngram", {}),
            },
            "1 / section",
            "reported, not selected",
        )
    )
    for s, sc in scored.items():
        L.append(
            _row(
                s,
                sc,
                str(calls_of(runs[s])),
                f"form {extra[s]['form']}, iterations <= {extra[s]['max_iterations']}, M4 {extra[s]['m4']}, M5 {extra[s]['m5']}, ${extra[s]['spend_usd']}",
            )
        )
    # replays on the first arm that is a step-1 candidate
    L += [
        "",
        "## Verifier statistics per arm",
        "",
        "| arm | sections Correct | stop reasons | flags per rule | hints added / rejected | restored | iterations histogram |",
        "|---|---|---|---|---|---|---|",
    ]
    for s, out in runs.items():
        rs = list(out.sections.values())
        stops = Counter(r.stop_reason for r in rs)
        fl = Counter()
        for r in rs:
            fl.update(r.flags_by_rule)
        hist = Counter(len(r.iterations) - 1 for r in rs)
        L.append(
            f"| {s} | {stops.get('correct', 0)} / {len(rs)} | {dict(stops)} | {dict(fl)} | {sum(r.hints_added for r in rs)} / {sum(r.hints_rejected for r in rs)} | {sum(r.restored for r in rs)} | {dict(sorted(hist.items()))} |"
        )
    # replays, reported rows, tau, comparison arms
    L += [
        "",
        "## Loop depth (replay of stored iterations; flagged items dropped, unresolved M1 not counted)",
        "",
        HEAD,
    ]
    for s_ in ("G1", "G2"):
        for k in (0, 1, 2, 3):
            L.append(
                _row(
                    f"{s_} depth {k}",
                    X.score(
                        X.finals_at_depth(runs[s_], k, sections, gnm), gold, sections, nlp, embed
                    ),
                    str(calls_of(runs[s_])),
                    "selected by the rule: depth 1 (G1)" if (s_, k) == ("G1", 1) else "",
                )
            )
    L += ["", "## Reported, not selected (final run FINAL = G1, depth 1, tau 0.1)", "", HEAD]
    fin = runs["FINAL"]
    L.append(
        _row(
            "B0 = v3 (E3)",
            {
                "n_predicted": b0["n_predicted"],
                "exact_micro": b0["exact_micro"],
                "lenient_micro": b0["lenient_micro"],
                "exact_macro": b0["exact_macro"],
                "recall_by_ngram": b0["recall_by_ngram"],
            },
            "1 / section",
            "the baseline",
        )
    )
    L.append(
        _row(
            "iteration 0, raw generator output",
            X.score(X.iteration0_raw(fin, sections, gnm), gold, sections, nlp, embed),
            "1 / section",
        )
    )
    L.append(
        _row(
            "L0 (iteration 0 + rules offline)",
            X.score(X.l0_finals(fin, sections, gnm), gold, sections, nlp, embed),
            "1 / section",
            "PiVe's offline correction",
        )
    )
    L.append(
        _row(
            "**v4 FINAL (live)**",
            X.score(X.R.predictions(fin, sections, gnm), gold, sections, nlp, embed),
            str(calls_of(fin)),
            "the reported dev number",
        )
    )
    tj = json.loads((d / "tau.json").read_text())
    L += [
        "",
        "## Pruner tau (replay; rule: highest exact micro F1 with recall drop <= 0.01)",
        "",
        "| tau | F1 | recall | precision | predicted | eligible |",
        "|---|---|---|---|---|---|",
        f"| none | {tj['base']['f1']:.3f} | {tj['base']['recall']:.3f} | {tj['base']['precision']:.3f} | {tj['base']['n']} | – |",
    ]
    for r in tj["table"]:
        L.append(
            f"| {r['tau']} | {r['f1']:.3f} | {r['recall']:.3f} | {r['precision']:.3f} | {r['n']} | {r['eligible']} |"
        )
    L.append(f"\n**Chosen tau = {tj['tau']}.**")
    aj = json.loads((d / "arms_dev_scores.json").read_text())
    L += [
        "",
        "## Comparison arms on dev (reported, never selected; `selection_eligible: false`)",
        "",
        HEAD,
    ]
    for k, sc in aj.items():
        L.append(
            _row(
                k,
                sc,
                str(sc["calls"]),
                {
                    "C-SAC": "pruner P1 at tau 0.5 (P2 not built)",
                    "C-ConExion": "one random dev example, their filter, our bulk model",
                }.get(k, ""),
            )
        )
    L += [
        "",
        "Caveats: C-SAC and C-PiVe are SAC-KG-style and PiVe-style re-implementations on our benchmark, not reproductions; C-ConExion uses our model, not Llama-3-70B. FACE's published supervised micro F1 is 0.76 (a different protocol).",
        "",
    ]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote", a.out)
    (d / "scores.json").write_text(json.dumps(scored, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
