# ruff: noqa: ISC004, UP031
"""CR-007 STOP 5 ($0, read-only): gate table (§5.1), precision with Wilson CIs, merge errors by
similarity bucket, misconception-layer counts, spend by stage.

Reads the owner-filled sheets from `sheets_dir` (data/gold/... once copied; the report labels the
provenance). Never writes under data/gold/. The gate rule is applied exactly as pre-registered:
keep iff instances >= 5 AND >= 80% of the sampled instances are marked correct.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from cumap.eval.stats import wilson_ci

MIN_INSTANCES = 5
MIN_CORRECT_SHARE = 0.80
REPORT_ONLY = ("acts_on", "connected_to")
BAND = 0.70


def gate_decision(instances: int, sampled: int, correct: int) -> str:
    """Pre-registered rule, applied as written (no exceptions)."""
    if instances < MIN_INSTANCES:
        return f"drop (instances {instances} < {MIN_INSTANCES})"
    if sampled == 0 or correct / sampled < MIN_CORRECT_SHARE:
        return f"drop (correct {correct}/{sampled} < {int(MIN_CORRECT_SHARE * 100)}%)"
    return "keep"


def fmt_ci(successes: int, n: int) -> str:
    if n == 0:
        return "n/a"
    w = wilson_ci(successes, n)
    return f"{100 * successes / n:.0f}% ({100 * w.low:.0f}-{100 * w.high:.0f}%)"


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _mark(row: dict, prefix: str) -> str:
    col = next(k for k in row if k.startswith(prefix))
    return (row[col] or "").strip().lower()


def load_filled(sheets_dir: Path) -> dict:
    e, ek = _rows(sheets_dir / "cr007_edge_sheet.csv"), _rows(sheets_dir / "cr007_edge_key.csv")
    m, mk = _rows(sheets_dir / "cr007_merge_sheet.csv"), _rows(sheets_dir / "cr007_merge_key.csv")
    return {
        "edges": [
            {"relation": k["relation"], "family": k["family"], "mark": _mark(r, "mark")}
            for r, k in zip(e, ek, strict=True)
        ],
        "merges": [
            {
                "source": k["source"],
                "mark": _mark(r, "mark"),
                "section": r["section"],
                "alias": r["name_A"],
                "name": r["name_B"],
            }
            for r, k in zip(m, mk, strict=True)
        ],
    }


def gate_table(edges: list[dict], instances: Counter, gated: list[str]) -> list[dict]:
    out = []
    for rel in list(gated) + list(REPORT_ONLY):
        marked = [x for x in edges if x["relation"] == rel and x["mark"]]
        correct = sum(x["mark"] == "correct" for x in marked)
        row = {
            "relation": rel,
            "instances": instances[rel],
            "sampled": len(marked),
            "correct": correct,
        }
        row["decision"] = (
            gate_decision(instances[rel], len(marked), correct) if rel in gated else "report only"
        )
        out.append(row)
    return out


def merge_errors_by_bucket(merges: list[dict], similarity: dict[tuple, float | None]) -> dict:
    """Wrong pipeline merges by similarity bucket. Band rows were NOT merged (similarity < BAND by
    construction), so a `same` mark there is a missed merge, not a wrong one."""
    out: Counter = Counter()
    for m in merges:
        sim = similarity.get((m["alias"], m["section"], m["name"]))
        if sim is None:
            out[("unknown similarity", m["source"], m["mark"] or "unmarked")] += 1
            continue
        bucket = f"<{BAND:.2f}" if sim < BAND else f">={BAND:.2f}"
        out[(bucket, m["source"], m["mark"] or "unmarked")] += 1
    return dict(out)


def spend_by_stage(
    log_path: Path, tiers: dict, since_ts: float, run_prefix: str
) -> dict[str, float]:
    from cumap.llm.client import TASK_TO_STAGE

    out: dict[str, float] = defaultdict(float)
    for line in log_path.read_text().splitlines():
        r = json.loads(line)
        if r["cache_hit"] or r["ts"] < since_ts or not r["run_id"].startswith(run_prefix):
            continue
        tier = tiers.get(r.get("model_tier"))
        if tier is None or tier.usd_per_1m_input_tokens is None:
            continue
        u = r["usage"]
        cost = u.get("input_tokens", 0) / 1e6 * tier.usd_per_1m_input_tokens
        cost += u.get("output_tokens", 0) / 1e6 * tier.usd_per_1m_output_tokens
        out[TASK_TO_STAGE.get(r["task"], r["task"])] += cost
    return dict(out)


def misconception_layer_rows(cp: dict) -> dict:
    """CR-008 item 2: the misconception layer is the only source of warning counts. The legacy
    per-pair `corrects_intuition` qualifier on old edges is ignored (never read, never reported)."""
    layer = cp.get("misconceptions") or {}
    return {
        "items": layer.get("items", []),
        "needs_correct_edge": layer.get("needs_correct_edge", []),
        "needs_review": layer.get("needs_review", []),
        "stats": layer.get("stats", {}),
    }


CI_READING = (
    "Reading (Claude, run slice3_a1; a human judgement, not a metric). Cause: the prompt/schema, "
    "not post-processing. `build_pair_registry` and the snapshot writer never read the flag, so "
    "nothing in our code sets it; the model sets it. Two things in `relation_qualifiers/v3.md` "
    'drive wrong flags: the cue list includes "note that ... does not", which fires on ordinary '
    "caveats; and the flag is asked about the *sentence* while the edge is about the *pair*, so a "
    "sentence that warns against a belief flags an unrelated edge. Of the flagged results, by my "
    "reading 3 are genuine warnings against a belief (the MTU note, the Central Offices/Head Ends "
    '"despite their names" sentence, "it is tempting to settle") and 1 is not (the piggybacking '
    "caveat, which restates a limitation). Of the 3 genuine ones, 1 sits on an edge the owner marked "
    "incorrect (application -[causes]-> network), and 1 is an unselected-sample result that is not "
    "in the graph. Counts are left out of the demo report until the owner decides."
)


def build_report(
    run_dir: Path,
    sheets_dir: Path,
    *,
    gated: list[str],
    tiers: dict,
    log_path: Path,
    out_md: Path,
    org_id: str | None = None,
    spend_since: float = 0.0,
    preflight: dict[str, float] | None = None,
) -> str:
    cp = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    filled = load_filled(sheets_dir)
    provisional = "data/gold" not in str(sheets_dir.resolve())
    instances = Counter(
        r["relation"]
        for r in cp["relation_results_v3"]
        if r["group"] == "selected" and r["outcome"] == "edge"
    )
    marked = [x for x in filled["edges"] if x["mark"]]
    correct = sum(x["mark"] == "correct" for x in marked)
    L = [
        f"# CR-007 STOP 5: gate table and precision (run `{cp['run_id']}`"
        + (f", org `{org_id}`" if org_id else "")
        + ")",
        "",
    ]
    L.append(
        f"Marks read from `{sheets_dir}`"
        + (" -- **PROVISIONAL: not yet from data/gold/**." if provisional else " (owner copies).")
        + " $0, read-only.\n"
    )

    L += [
        "## 1. Gate table (CR-007 §5.1; rule applied as written: >=5 instances AND >=80% of the sampled correct)",
        "",
        "| relation | instances in re-run | sampled (owner-marked) | correct | % correct | decision |",
        "|---|---|---|---|---|---|",
    ]
    for r in gate_table(filled["edges"], instances, gated):
        pct = f"{100 * r['correct'] / r['sampled']:.0f}%" if r["sampled"] else "n/a"
        L.append(
            f"| {r['relation']} | {r['instances']} | {r['sampled']} | {r['correct']} | {pct} | {r['decision']} |"
        )
    L.append("")

    L += [
        "## 2. Precision (Wilson 95%)",
        "",
        f"- Edges overall: {correct}/{len(marked)} = **{fmt_ci(correct, len(marked))}** (CR-005 spot-check: 23/30 = {fmt_ci(23, 30)}).",
        "",
    ]
    fam: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for x in marked:
        fam[x["family"]][0] += x["mark"] == "correct"
        fam[x["family"]][1] += 1
    L += ["| family | correct / sampled | Wilson |", "|---|---|---|"]
    for k, (s, n) in sorted(fam.items()):
        L.append(f"| {k} | {s}/{n} | {fmt_ci(s, n)} |")
    pm = [m for m in filled["merges"] if m["source"] == "merged" and m["mark"]]
    ok = sum(m["mark"] == "same" for m in pm)
    L += ["", f"- Pipeline merges: {ok}/{len(pm)} = **{fmt_ci(ok, len(pm))}** (CR-005: 41/43).", ""]

    sim = {
        (
            m["alias"],
            m["section_id"],
            next(
                (c["canonical_name"] for c in cp["concepts"] if c["concept_id"] == m["concept_id"]),
                None,
            ),
        ): m.get("similarity")
        for m in cp["merges"]
    }
    sim.update(
        {
            (r["alias"], r["section_id"], r["candidate_name"]): r["similarity"]
            for r in cp["merge_review"]
        }
    )
    by = merge_errors_by_bucket(filled["merges"], sim)
    L += [
        "## 3. Merge errors by similarity bucket (review band stays at 0.70, provisional)",
        "",
        "| bucket | source | owner mark | rows |",
        "|---|---|---|---|",
    ]
    for (b, s, mk), n in sorted(by.items()):
        L.append(f"| {b} | {s} | {mk} | {n} |")
    L += [
        "",
        "`merged` rows were merged by the pipeline (similarity >= 0.70 by construction, so wrong merges can "
        "only fall in the upper bucket); `band` rows were held back for review, so a `same` mark there is a "
        "missed merge, not a wrong one.",
        "",
    ]

    L += ["## 4. Misconception layer (CR-008 §5; replaces the `corrects_intuition` count)", ""]
    m = misconception_layer_rows(cp)
    st = m["stats"]
    if not st:
        L.append("The misconception stage has not run on this run (no layer stored).")
    else:
        L.append(
            f"{st.get('candidates', 0)} cue candidates -> {len(m['items'])} layer items, "
            f"{len(m['needs_correct_edge'])} `needs_correct_edge`, {len(m['needs_review'])} owner review, "
            f"{st.get('not_warning', 0)} dismissed as plain facts."
        )
        for it in m["items"]:
            L.append(
                f"- [{it['perturbation_type']}] {it['source_name']} -[{it['relation']}]-> "
                f"{it['target_name']} ({it['polarity']}): {it['intuition']}"
            )
    L += ["", CI_READING, ""]

    spent = spend_by_stage(log_path, tiers, spend_since, cp["run_id"])
    L += [
        "## 5. Spend by stage, this run (actual from the call log; cache hits cost nothing)",
        "",
        "| stage | actual | preflight |",
        "|---|---|---|",
    ]
    for stage, usd in sorted(spent.items()):
        pf = (preflight or {}).get(stage)
        L.append(f"| {stage} | ${usd:.2f} | {'$%.2f' % pf if pf is not None else '-'} |")
    L.append(f"| **run total** | **${sum(spent.values()):.2f}** | |")
    out_md.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(out_md)
