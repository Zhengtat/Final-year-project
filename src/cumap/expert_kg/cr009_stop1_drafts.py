"""CR-009 STOP 1: the bank approval sheet, the prompt-diff summary and the STOP 2 preflight ($0)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from cumap.expert_kg.fewshot_bank import load_bank

ROOT = Path(".")
CHECKS = ROOT / "data" / "interim" / "checks"
PRICE = {
    "bulk": (0.10, 0.50),
    "strong": (2.0, 10.0),
}  # USD per 1M input / output tokens (configs/default.yaml)


def _plain(ex: dict) -> str:
    e = ex["expected"]
    lines = []
    for m in e["existing_mentions"]:
        lines.append(
            f'MENTION of known node {m["node_id"]} ({m["surface"]}), role {m["role"]}: "{m["evidence"]}"'
        )
    for n in e["not_mentions"]:
        lines.append(f"NOT a mention: {n['node_id']} ({n['reason']})")
    for c in e["new_concepts"]:
        a = (
            "; ".join(f"{x['anchor_type']} -> {x['node_id']}" for x in c["anchors"])
            or f"independent ({c['independence_check']})"
        )
        al = f" [aka {', '.join(c['aliases'])}]" if c["aliases"] else ""
        lines.append(
            f"NEW {c['node_type']} “{c['name']}”{al}, role {c['role']}, {a}{', found via anchor' if c['found_via_anchor'] else ''}"
        )
    if ex.get("hint_responses"):
        for r in ex["hint_responses"]:
            lines.append(f"HINT {r['hint_id']}: {r['decision']} ({r['reason']})")
    for n in ex.get("negatives", []):
        lines.append(f"NOT extracted: “{n['text']}” — {n['why']}")
    return "\n".join(lines)


def write_bank_sheet(bank: dict) -> int:
    CHECKS.mkdir(parents=True, exist_ok=True)
    with (CHECKS / "cr009_bank_approval_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "id",
                "domain",
                "what it teaches",
                "passage",
                "known nodes shown (cards)",
                "given items (corrective only)",
                "expected output (plain words)",
                "judgement (approve / edit / reject)",
                "note",
            ]
        )
        for ex in bank["examples"]:
            cards = (
                "\n".join(
                    f"{c['id']} {c['name']} ({c['type']}; {'in text' if c['in_text'] else 'not in text'})"
                    for c in ex["cards"]
                )
                or "(none: cold start)"
            )
            given = "\n".join(
                f"{g['hint_id']}: {g['type']} — {g['text']}" for g in ex.get("given_items", [])
            )
            w.writerow(
                [
                    ex["id"],
                    ex["domain"],
                    "; ".join(ex["covers"]),
                    " ".join(" ".join(v.split()) for v in ex["paragraphs"].values()),
                    cards,
                    given,
                    _plain(ex),
                    "",
                    "",
                ]
            )
    return len(bank["examples"])


def bank_tokens(bank: dict) -> int:
    chars = sum(
        len(json.dumps({k: ex[k] for k in ("paragraphs", "cards", "expected") if k in ex}))
        for ex in bank["examples"]
    )
    return int(chars / 4)


def preflight(nums: dict, bank: dict) -> list[str]:
    root = ROOT
    prompt_tokens = int(len(Path("prompts/concept_generator/v4.md").read_text().split()) * 1.3)
    btok = bank_tokens(bank)
    iir_dev = [
        json.loads(x)
        for x in (root / "data/interim/external/iir_sections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x
    ]
    iir_test = [
        json.loads(x)
        for x in (root / "data/interim/external/iir_test_sections_v3.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x
    ]
    dev_w = [len(s["text"].split()) for s in iir_dev]
    test_w = [len(s["text"].split()) for s in iir_test]
    cards_dev = 40  # IIR dev has fewer earlier sections: assume 40 cards (P&D median is 68; chapters 4-16 grow past it)
    cards_test = 90
    card_tok = lambda n: int(n * nums["card_tokens_median"] / max(nums["cards_median"], 1))

    def call_cost(tier: str, tin: int, tout: int) -> float:
        pi, po = PRICE[tier]
        return (tin * pi + tout * po) / 1e6

    def gen(
        words: float, cards: int, calls: float, reasoning: int = 400, out_items: int = 35
    ) -> float:
        tin = prompt_tokens + btok + card_tok(cards) + int(words * 1.3)
        tout = out_items * 75 + reasoning
        return calls * call_cost("bulk", tin, tout)

    sec_dev = sum(gen(w, cards_dev, 1) for w in dev_w)  # one generator call over all dev sections
    rows = []
    worst = 4  # iteration 0 + up to 3 corrective
    expected = 2.0
    g1 = (sec_dev * expected, sec_dev * worst)
    g2 = (
        sum(gen(w, cards_dev, 1, out_items=35) for w in dev_w) * (1 + expected - 1 + 0.6),
        sum(gen(w, cards_dev, 1) for w in dev_w) * (1 + worst),
    )
    m4 = (sec_dev * expected, sec_dev * worst)
    v2 = sum(call_cost("strong", 2500, 1200) for _ in dev_w)
    final_dev = (sec_dev * expected, sec_dev * worst)
    test = (
        sum(gen(w, cards_test, 1) for w in test_w) * expected,
        sum(gen(w, cards_test, 1) for w in test_w) * worst,
    )
    c_sac = (
        sum(gen(w, 0, 1) for w in dev_w + test_w) * 1.5,
        sum(gen(w, 0, 1) for w in dev_w + test_w) * 2,
    )
    c_pive = (
        sum(gen(w, 0, 1) for w in dev_w + test_w) * 2,
        sum(gen(w, 0, 1) for w in dev_w + test_w) * 4,
    )
    c_conex = sum(call_cost("bulk", 900 + int(w * 1.3), 300) for w in dev_w + test_w)
    ext_docs = 586  # Inspec test 486 + SemEval-2017 test 100 (abstracts, ~230 words)
    ext = 3 * ext_docs * call_cost("bulk", 700, 450)
    ext_v4_loop = ext_docs * call_cost("bulk", prompt_tokens + btok + 400, 600) * 2
    pd_gen = (
        gen(
            nums["pd_words"] / nums["pd_sections"],
            int(nums["cards_median"]),
            nums["pd_sections"] * expected,
        ),
        gen(
            nums["pd_words"] / nums["pd_sections"],
            int(nums["cards_median"]),
            nums["pd_sections"] * worst,
        ),
    )
    backfill = nums["backfill_calls"] * call_cost("bulk", 1800, 500)

    def row(name, lo, hi):
        rows.append((name, lo, hi))

    row("IIR dev, arm G1 (live, 13 sections)", *g1)
    row("IIR dev, arm G2 (live)", *g2)
    row("IIR dev, ± M4 (live)", *m4)
    row("IIR dev, ± V2 concept verifier (strong tier, 13 calls)", v2, v2)
    row("IIR dev, final end-to-end run of the chosen configuration", *final_dev)
    row("IIR test, v4 once (70 sections)", *test)
    row(
        "Comparison arms on dev + test: C-SAC, C-PiVe (C-PiVe-off is a replay)",
        c_sac[0] + c_pive[0],
        c_sac[1] + c_pive[1],
    )
    row("Comparison arm C-ConExion (dev + test, one call per section)", c_conex, c_conex)
    row(
        "External check: 3 systems on Inspec + SemEval-2017 test (586 abstracts)",
        ext + ext_v4_loop * 0.5,
        ext + ext_v4_loop,
    )
    row("P&D ch1-3 concepts (24 sections) + backfill", pd_gen[0] + backfill, pd_gen[1] + backfill)
    row(
        "P&D canonicalisation R4, relations + verifier + expansion, prerequisites, fusion (CR §13 estimate; cache hits for unchanged prompts)",
        4.4,
        10.5,
    )
    lo = sum(r[1] for r in rows)
    hi = sum(r[2] for r in rows)
    L = [
        "## (h) Preflight for STOP 2 (estimates from measured prompt sizes; bulk tier $0.10 / $0.50 per 1M tokens, strong $2 / $10)",
        "",
        (
            f"Measured: prompt skeleton ≈ {prompt_tokens} tokens, bank ≈ {btok} tokens, cards median ≈ {int(nums['card_tokens_median'])} tokens (P&D; 40 assumed on IIR dev, 90 on IIR test), "
            "output ≈ 35 items × 75 tokens + 400 reasoning. Iterations: expected 2 per section, worst case 4 (iteration 0 + 3 corrective)."
        ),
        "",
        "| item | expected | worst case |",
        "|---|---|---|",
    ]
    for n, a, b in rows:
        L.append(f"| {n} | ${a:.2f} | ${b:.2f} |")
    L.append(f"| **Total** | **${lo:.2f}** | **${hi:.2f}** |")
    L += [
        "",
        "CR-009 §13 estimated ≈ $7–16 with a hard cap of $18. The cache makes byte-identical prompts free, and every command supports `--dry-run`, `--limit 20` before the full run (CLAUDE.md rule 7).",
        "",
    ]
    return L


def main() -> None:
    bank = load_bank()
    nums = json.loads((ROOT / "reports" / "cr009_stop1_numbers.json").read_text())
    n = write_bank_sheet(bank)
    pf = preflight(nums, bank)
    Path(
        "/private/tmp/claude-501/-Users-wongzhengtat-Desktop-h420020-mapper/d29c4c62-c64b-43ea-9ca7-cfb50d9c6376/scratchpad/prompt_v4_vs_v3.diff"
    )
    cfg = yaml.safe_load(Path("configs/concept_gvp.yaml").read_text())
    L = [
        "",
        "## (f) Drafts for your approval",
        "",
        (
            "- **Prompt v4** (`prompts/concept_generator_v4.md`, ≈ 960 words before the bank): the fixed skeleton ROLE → TASK → DEFINITIONS → INPUTS → PROCEDURE → OUTPUT SCHEMA → EXAMPLES → FINAL CHECKLIST. "
            "Against v3 (`prompts/concept_extraction/v2.md` + propagation) it adds EXISTING NODES and LOOK-ALIKES, the six-step procedure, the complete-span rules and the strict “same” rule, numbered paragraphs and an anchor/independence output; "
            "it drops the noun-chunk candidate-term hints. v3's definition of a concept, the exclusion list and the “a term, never a clause” rule are carried over unchanged. The full diff is not committed; the old file is unchanged."
        ),
        f"- **Corrective-instruction table:** `configs/concept_gvp.yaml` → `verifier.corrective_instructions` ({len(cfg['verifier']['corrective_instructions'])} rules, one instruction each, wording in config), with the PiVe-style prefix “Extract the concepts again, and also review the given items…”.",
        (
            f"- **Few-shot bank:** `configs/fewshot/concepts_v4_draft.yaml`: 6 worked examples + 1 corrective-round example (operating systems, databases, computer architecture; networking and IR are absent), "
            f"all validated by code (F2–F6, C3, M1, M2 raise nothing; no 8-gram overlap with any P&D or IIR section). Approval sheet: `data/interim/checks/cr009_bank_approval_sheet.csv` ({n} rows, ~10 min)."
        ),
        "- **Configuration:** `configs/concept_gvp.yaml`: the rule repository (16 rules), retriever caps, verifier loop limits, pruner settings and the comparison arms (all `selection_eligible: false`).",
        "",
    ]
    L += [
        "## (g) Comparison set-up (ConExion, checked 2026-10-03)",
        "",
        "- **Repository:** `github.com/ISE-FIZKarlsruhe/concept_extraction` (MIT licence), cloned read-only into the scratchpad (not into the project). It contains the code (`conexion/models/prompts.py`, `conexion/evaluation/evaluator.py`, dataset loaders) and 38 aggregate result CSVs.",
        "- **Prompt/setup:** the paper describes “few-shot 1-Random”: one training example chosen at random per test document, base prompt “I have the following document: [DOCUMENT] Please give me the keyphrases that are present in this document and separate them with commas”, output split on commas/semicolons/newlines and **filtered to concepts present in the text by exact lexical match** (arXiv 2504.12915).",
        "- **Scorer:** `evaluate_p_r_f` is set-intersection P/R/F1 on the exact strings per document (stemming only for the @k scores); published F1: Inspec 0.451, SemEval-2017 0.311 (Llama-3-70B, few-shot 1-random). Test sets: Inspec 486 documents, SemEval-2017 100.",
        "- **Datasets:** the code loads `midas/inspec` (revision 9617780) and `midas/semeval2017` (revision d0e6006) from Hugging Face. **I could not confirm the dataset licences:** the pages I could read did not state one, so please check them before the data are downloaded; nothing has been downloaded, and the data will stay local and uncommitted.",
        (
            "- **Validity gate: cannot be run as specified.** The repository releases **no per-document predictions** and none for the 70B few-shot setup: only 38 aggregate CSVs for Llama-2-7B/13B and Llama-3-8B, all on Inspec, zero-shot. So their scorer cannot be re-run on released outputs to reproduce the published 0.451/0.311. "
            "Per §7.2 the fallback applies: re-run their prompt with our model and report like-for-like rows only (their published 70B numbers are shown as context, not as a comparison). The scorer code itself is 10 lines and exact-match, so I can port it with a fixture test."
        ),
        "",
    ]
    path = ROOT / "reports" / "cr009_stop1.md"
    txt = path.read_text(encoding="utf-8")
    marker = "## (e) Quantity floor"
    head, tail = txt.split(marker, 1)
    tail_e, _ = (tail.split("\n## (f)", 1) + [""])[:2]
    path.write_text(head + marker + tail_e + "\n".join(L) + "\n" + "\n".join(pf), encoding="utf-8")
    print("bank sheet rows:", n)


if __name__ == "__main__":
    main()
