"""CR-013 STOP 4 report generator (evaluation side: it reads the evaluation payload). Writes `reports/cr013/stop4.md` from the frozen overlay data, the fixture run and the checks
run in this session.

    uv run python -m cumap.explain.eval_report /tmp/browser_eval_checks.json"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.explain.eval_adapter import build_eval_payload
from cumap.explain.why_not_eval import EVAL_TEXT, localise

BASE = {"endpoints": ("A", "B"), "span_status": ("exact", "exact"), "false_merge": (False, False), "split": (False, False), "pairs_proposed": (True,), "no_relation": (False,), "predicted_relations": ("uses",), "gold_relation": "uses",
        "symmetric": False, "reversed_only": False, "types_ok": True, "qualifiers_ok": True, "evidence_valid": True}  # fmt: skip
FIXTURES = [
    ("N0", {"span_status": ("absent", "exact")}, "source endpoint never extracted"), ("N1", {"span_status": ("exact", "partial")}, "target endpoint extracted with a wrong span"), ("C1", {"false_merge": (True, False)}, "source endpoint is a false merge"),
    ("C0", {"split": (True, False), "pairs_proposed": (False, False), "predicted_relations": ()}, "source concept split, pair lost"), ("P0", {"pairs_proposed": (False,), "predicted_relations": ()}, "endpoint pair never sent to the classifier"),
    ("R0", {"no_relation": (True,), "predicted_relations": ()}, "classifier answered no relation"), ("R1", {"predicted_relations": ("part_of",)}, "classifier chose another relation"), ("R2", {"reversed_only": True}, "right relation, wrong direction"),
    ("R3", {"types_ok": False}, "endpoint types fail the check"), ("E0", {"evidence_valid": False}, "evidence invalid"), (None, {}, "nothing lost (recovered)"),
]  # fmt: skip


def main() -> None:
    P = build_eval_payload()
    browser = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else {}
    summary = (
        subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "-q",
                "tests/test_cr013_eval.py",
                "tests/test_cr013_explorer.py",
                "tests/test_cr013_trace.py",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={**os.environ, "CUMAP_LLM_BACKEND": "mock"},
            check=False,
        )
        .stdout.strip()
        .splitlines()[-1]
    )
    L = ["# CR-013 STOP 4: evaluation overlay", "",
         "Scope (Research STOP-4 authorisation): strictly separated CR-012 / SciNLP evaluation overlays for gold comparison, earliest-failure explanation and an aggregate failure map linked to concrete examples. **$0, no model call, no prediction rerun, no gold reinterpretation:** the overlay reads only the frozen CR-012 outputs (tag `cr012-stop4-complete`, commit `4697acb`: `reports/cr012/stop4_heldout_results.json`, the retained E0 checkpoints, the benchmark gold and the frozen `cumap.cr012.attribution` functions). The codes are explained as observations of the frozen run; nothing here is a production decision rule.", "",
         "## 1. Design and separation", "",
         "- **A separate, opt-in mode.** A third top-level button, `CR-012 evaluation overlay`, styled as a warning, opens the overlay; the production P&D views never show it. A permanent banner reads *EVALUATION OVERLAY — EVALUATION OUTPUT, gold-derived. NOT the production Expert KG*, and the same page states that the codes are observations, not decision rules.",
         "- **A separate payload.** The overlay is its own gzip blob (`eval-gz`), decoded only when the user opens the mode (verified in a real browser: it stays undecoded through every production view). The production trace blob (`trace-gz`) contains no gold, scorer, `cr012` or SciNLP data, and the trace-layer JavaScript contains no reference to the overlay.",
         "- **A separate module.** `src/cumap/explain/eval_adapter.py` (and `why_not_eval.py`, `eval_report.py`) are the only explain modules that import `cumap.cr012` or read the gold; a test enforces this.",
         "- **Dataset scoped, never pooled.** SciNLP held-out (3 documents) and P&D held-out (7 sections, *not* the Chapters 1-3 graph) are separate datasets with separate headline numbers and separate failure maps; unit ids are disjoint and each list shows one dataset.", "",
         "## 2. What the overlay shows", "",
         "- **Failure map.** Per dataset: the frozen headline (F1, precision, recall, CI status), a stacked bar of the earliest failure of every missed gold relation, a document / section x code matrix (click a count to list those gold relations), a glossary of the ten codes with the frozen wording and one concrete example each, and the frozen oracle ladder as context.",
         "- **Gold relations.** A filterable list (code, strict-match status, unit, text search); selecting a relation opens its explanation in the detail panel.",
         "- **Explanation of one gold relation.** The source sentence with the gold endpoints highlighted, the frozen earliest-failure code with its plain meaning, the ordered stage checks with the decisive check marked and later stages shown as *not evaluated*, what the run retained for the endpoints (predicted nodes and relations), the selection context (budget, selected, eligible-pool size), and, for SciNLP, a link that opens the missed relation in the SciNLP evaluation graph.", "",
         "## 3. Frozen outputs, reproduced exactly", "",
         "Every per-relation code is the frozen `attribute()` applied to that relation's facts; the builder asserts that the pooled and per-unit counts equal `stop4_heldout_results.json`, and a test repeats the check. SciNLP codes are also checked relation by relation against the frozen `sc_attribution`.", ""]  # fmt: skip
    for d in P["datasets"].values():
        h = d["headline"]
        tot = Counter()
        for u in d["units"]:
            tot.update(u["counts"])
        L += [f"### {d['label']}", "", f"Headline (frozen): {h['metric']} F1 **{h['f1']:.3f}** (P {h['precision']:.3f} / R {h['recall']:.3f}); CI status {h['ci_status']}. {d['not_applicable_note']}", "",
              f"| {d['unit_word']} | gold | " + " | ".join(P["code_order"]) + " | none | F1 |", "|---|---|" + "---|" * (len(P["code_order"]) + 2)]  # fmt: skip
        for u in d["units"]:
            L.append(
                f"| {u['title']} | {u['gold_n']} | "
                + " | ".join(str(u["counts"][c]) for c in P["code_order"])
                + f" | {u['recovered']} | {u['f1']:.3f} |"
            )
        L += [
            f"| **pooled** | {sum(u['gold_n'] for u in d['units'])} | "
            + " | ".join(str(tot[c]) for c in P["code_order"])
            + f" | {sum(u['recovered'] for u in d['units'])} | |",
            "",
        ]
    L += [
        "## 4. Failure-localisation fixture results (frozen attribution order)",
        "",
        "| fixture | expected | localised | frozen wording shown |",
        "|---|---|---|---|",
    ]
    ok = 0
    for code, change, label in FIXTURES:
        out = localise({**BASE, **change})
        good = out["code"] == code
        ok += good
        L.append(
            f"| {label} | {code or 'none'} | {out['code'] or 'none'} {'OK' if good else 'FAIL'} | {(EVAL_TEXT[code] if code else out['text'])[:90]}… |"
        )
    L += ["", f"**{ok} / {len(FIXTURES)}** fixtures attributed to the intended stage (stage localisation accuracy {100 * ok / len(FIXTURES):.0f}%). On the real data, each relation's stage checks are also verified against its code (`test_each_relations_stage_checks_are_consistent_with_its_frozen_code`).", "",
          "## 5. Gold-isolation tests", "", f"pytest (trace model, explorer, overlay): **{summary}**.", "",
          "| test | what it proves |", "|---|---|",
          "| `test_only_the_evaluation_modules_read_gold_or_import_cr012` | only `eval_adapter`, `why_not_eval`, `eval_report` touch gold or `cumap.cr012` |",
          "| `test_production_payload_is_free_of_the_overlay_and_any_gold` | the production trace payload contains no gold, frozen-run or SciNLP data |",
          "| `test_the_overlay_has_its_own_payload_and_production_javascript_never_references_it` | the trace-layer JavaScript has no overlay symbol; page hooks to the overlay are guarded |",
          "| `test_the_two_payload_blobs_are_separate_and_the_overlay_blob_matches_python` | `trace-gz` and `eval-gz` are separate, and the embedded overlay equals the Python build |",
          "| `test_overlay_is_opt_in_not_decoded_before_and_never_leaks_into_production_views` | the overlay is undecoded until opened; production views and the page after leaving the mode contain no evaluation text |",
          "| `test_overlay_is_dataset_scoped_and_pooled_counts_equal_the_frozen_results` | 295 SciNLP and 432 P&D gold rows, disjoint units, counts equal to the frozen results |",
          "| `test_overlay_counts_equal_the_frozen_cr012_results_exactly`, `test_per_relation_codes_equal_the_frozen_scinlp_attribution` | no reinterpretation of the frozen attribution |", "",
          "Real-browser checks (headless Chromium, `tests/js/take_eval_screenshots.py`):", "", "```", json.dumps(browser, indent=1), "```", "",
          "## 6. Evaluation-mode screenshots (`reports/cr013/screenshots/`)", "", "| file | shows |", "|---|---|"]  # fmt: skip
    for f, d in [
        (
            "15_eval_pd_failure_map",
            "P&D held-out failure map: headline, stacked bar, section x code matrix, glossary",
        ),
        ("16_eval_pd_gold_relations_p0", "Gold relations filtered to P0 from a matrix cell"),
        ("17_eval_pd_detail_p0", "Explanation of one gold relation lost at P0"),
        (
            "18_eval_pd_detail_r1_example",
            "Explanation of a wrong-relation (R1) example opened from the glossary",
        ),
        ("19_eval_pd_narrow", "Narrow (390 px) layout"),
        ("20_eval_pd_dark", "Dark mode"),
        (
            "_eval_scinlp_failure_map / _eval_scinlp_detail",
            "SciNLP overlay (local only, gitignored: contains CC BY-NC text)",
        ),
    ]:
        L.append(f"| `{f}.png` | {d} |")
    L += [
        "",
        "## 7. What the overlay deliberately does not do",
        "",
        "- It does not turn failure codes into decision rules, thresholds or recommendations for the production pipeline; the page says so wherever codes appear.",
        "- It does not rerun any model, re-score, re-attribute or edit gold. The retained E0 predictions are only read.",
        "- It does not pool SciNLP and P&D, and it does not show any CR-011 pre/post panel (CR011 = NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION; S0 / S1 not applicable).",
        "- Oracle levels (E1-E4) appear only as the frozen F1 values with the caveat that they are conditional diagnostics, not an additive decomposition; no per-relation oracle traces are shown.",
        "- Limits: E0 only; P&D held-out gold has a single human annotator; SciNLP C0 / C1 are not applicable (no identity gold) and one SciNLP document has a single gold relation; the pair pool is retained as a count only for these runs, so P0 explanations state the budget and pool size, not a rank.",
        "",
    ]
    (REPO_ROOT / "reports/cr013/stop4.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote reports/cr013/stop4.md")


if __name__ == "__main__":
    main()
