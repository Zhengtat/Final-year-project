"""CR-009 STOP 3: owner marks (read from data/gold, never written) -> precision with Wilson CIs, split by the hidden
keys in data/interim/checks. Appends the section to reports/cr009_stop3.md. `python -m cumap.concepts_v4.stop3_marks`."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from cumap.eval.stats import wilson_ci

ROOT = Path(".")
GOLD, CHECKS = ROOT / "data/gold", ROOT / "data/interim/checks"
RUN = "slice3_c1"


def _rows(p: Path) -> list[list[str]]:
    return list(csv.reader(p.open(encoding="utf-8")))[1:]


def ci(k: int, n: int) -> str:
    w = wilson_ci(k, n)
    return f"{k}/{n} = {k / max(n, 1):.0%} (Wilson 95% [{w.low:.2f}, {w.high:.2f}])"


def main() -> str:
    L = ["", "## Owner marks (STOP 3; read from `data/gold/`, split by the hidden keys)", ""]
    # concepts
    cs = _rows(GOLD / f"cr009_stop3_concepts_{RUN}.csv")
    key = {r[0]: r for r in _rows(CHECKS / f"cr009_stop3_concepts_key_{RUN}.csv")}
    j = {r[0]: r[5].strip().lower() for r in cs}
    ok = {i for i, v in j.items() if v == "valid complete"}
    L += [
        "### Concepts (40, stratified)",
        "",
        f"- **Valid complete concept: {ci(len(ok), len(j))}**; verdicts {dict(Counter(j.values()))}",
        "",
        "| stratum | n | valid complete |",
        "|---|---|---|",
    ]
    strata = {
        "independent": lambda k: k[1] == "independent" and k[2] != "True",
        "anchored": lambda k: k[1] == "anchored" and k[2] != "True",
        "found_via_anchor": lambda k: k[2] == "True",
    }
    for name, f in strata.items():
        ids = [i for i, k in key.items() if f(k)]
        L.append(f"| {name} | {len(ids)} | {ci(sum(i in ok for i in ids), len(ids))} |")
    aj = [
        (r[0], r[9].strip().lower())
        for r in cs
        if r[9].strip().lower() in {"correct", "wrong", "should be independent"}
    ]
    c = Counter(v for _, v in aj)
    L += [
        "",
        f"- **Anchor correct: {ci(c['correct'], len(aj))}** ({dict(c)}); by anchor type: "
        + "; ".join(
            f"{t} {sum(1 for i, v in aj if key[i][3] == t and v == 'correct')}/{sum(1 for i, _ in aj if key[i][3] == t)}"
            for t in sorted({key[i][3] for i, _ in aj})
        ),
        "",
    ]
    # g-links
    gl = [r[5].strip().lower() for r in _rows(GOLD / f"cr009_stop3_glinks_{RUN}.csv")]
    L += [
        "### Non-trivial generator links (G-link, 15)",
        "",
        f"- **Same sense: {ci(gl.count('same'), len(gl))}.** A wrong G-link merges a text form into a node as an alias; 11 of 15 sampled were wrong (e.g. network -> cloud, system -> device, link -> link capacity).",
        "",
    ]
    # pruned
    pk = {r[0]: r[1] for r in _rows(CHECKS / f"cr009_stop3_pruned_key_{RUN}.csv")}
    pr = [(r[0], r[4].strip().lower()) for r in _rows(GOLD / f"cr009_stop3_pruned_{RUN}.csv")]
    bad = [i for i, v in pr if v == "should be a node"]
    bd = [i for i in bad if pk.get(i) == "True"]
    L += [
        "### Pruned items (15)",
        "",
        f"- **False-prune rate (should have been a node): {ci(len(bad), len(pr))}**; of the `pruned_defined` ones sampled {sum(1 for i, _ in pr if pk.get(i) == 'True')}, wrongly pruned {len(bd)}. The pruner is trained on IIR dev only, so it is out of domain on P&D.",
        "",
    ]
    # rejections
    rk = {r[0]: r for r in _rows(CHECKS / f"cr009_stop3_rejections_key_{RUN}.csv")}
    rj = [(r[0], r[4].strip().lower()) for r in _rows(GOLD / f"cr009_stop3_rejections_{RUN}.csv")]
    wrong = [i for i, v in rj if v == "actually a mention"]
    L += [
        "### Not-mentions and backfill rejections (10)",
        "",
        f"- **Correct rejection: {ci(len(rj) - len(wrong), len(rj))}**; wrongly rejected by reason: {dict(Counter(rk[i][2] for i in wrong))}; by kind: {dict(Counter(rk[i][1] for i in wrong))}",
        "",
    ]
    # flags
    fk = {r[0]: r[1] for r in _rows(CHECKS / f"cr009_stop3_flags_key_{RUN}.csv")}
    fj = [(r[0], r[4].strip().lower()) for r in _rows(GOLD / f"cr009_stop3_flags_{RUN}.csv")]
    valid = [i for i, v in fj if v == "valid flag"]
    L += [
        "### Verifier flags (10, rules F3 and F2)",
        "",
        f"- **Valid flag: {ci(len(valid), len(fj))}**; false flags by rule: {dict(Counter(fk[i] for i, v in fj if v == 'false flag'))}",
        "",
    ]
    # stop 1 sheets
    pa = _rows(GOLD / "cr009_propagation_audit_sheet.csv")
    pkey = {r[0]: r[1] for r in _rows(CHECKS / "cr009_propagation_audit_key.csv")}
    same = [r[0] for r in pa if r[6].strip().lower() == "same sense"]
    L += [
        "### STOP 1 propagation audit (20)",
        "",
        f"- **Same sense: {ci(len(same), len(pa))}**; by direction: "
        + "; ".join(
            f"{d} {sum(1 for i in same if pkey[i] == d)}/{sum(1 for r in pa if pkey[r[0]] == d)}"
            for d in sorted(set(pkey.values()))
        ),
        f"- Bank approval sheet: {dict(Counter(r[7].strip().lower() for r in _rows(GOLD / 'cr009_bank_approval_sheet.csv')))}",
        "",
    ]
    out = ROOT / "reports" / "cr009_stop3.md"
    txt = out.read_text(encoding="utf-8")
    txt = txt.split("\n## Owner marks")[0].rstrip("\n") + "\n" + "\n".join(L) + "\n"
    out.write_text(txt, encoding="utf-8")
    return "\n".join(L)


if __name__ == "__main__":
    print(main())
