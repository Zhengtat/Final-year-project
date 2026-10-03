"""CR-008 STOP 1: $0 backtest of R1-R3, lexicon seed, equivalence audit and cue scan.

Reads the CR-007 run checkpoint and both owner merge sheets (read-only); writes only
`reports/cr008_stop1.md` and the seed sheet under `data/interim/checks/`. No API call.
Run: `uv run python -m cumap.expert_kg.cr008_stop1`.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from cumap.expert_kg.alias_rules import (
    AliasConfig,
    acronym_collision,
    alias_statements,
    find_abbreviations,
    r1_key,
    split_embedded_acronym,
)
from cumap.expert_kg.mentions import build_vocab

RUN = Path("data/processed/kg/slice3_a1/checkpoint.json")
SECTIONS = Path("data/interim/textbook_sections.jsonl")
CR005_MARKS = Path("data/interim/review/canonical_merge_marks.csv")
CR007_SHEET = Path("data/gold/cr007_merge_sheet.csv")
CR007_KEY = Path("data/gold/cr007_merge_key.csv")
OVERRIDES = Path("configs/canonical_overrides.yaml")
CUES = Path("configs/misconception_cues.yaml")
REPORT = Path("reports/cr008_stop1.md")
SEED_SHEET = Path("data/interim/checks/cr008_seed_sheet.csv")
DISTINGUISH = re.compile(
    r"\b(unlike|whereas|differs?|different from|not the same|in contrast|distinct\w*|distinguish\w*|rather than)\b",
    re.IGNORECASE,
)
# strong-tier cost per call (configs/default.yaml): ~3.5k input + ~1.5k output incl. reasoning
USD_PER_STRUCTURING_CALL = (3500 * 2.0 + 1500 * 10.0) / 1e6


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n\s*\n", text) if s.strip()]


def load_sheet_rows() -> list[dict]:
    rows: list[dict] = []
    for r in csv.DictReader(CR005_MARKS.open(encoding="utf-8")):
        rows.append(
            {
                "sheet": "CR-005",
                "id": r["id"],
                "a": r["alias_merged"],
                "b": r["merged_into"],
                "same": r["mark (ok/wrong)"].strip().lower() == "ok",
                "section": r["section_id"],
                "quote": r["evidence_quote"],
                "note": "",
            }
        )
    keys = {r["id"]: r["source"] for r in csv.DictReader(CR007_KEY.open(encoding="utf-8"))}
    for r in csv.DictReader(CR007_SHEET.open(encoding="utf-8")):
        rows.append(
            {
                "sheet": "CR-007",
                "id": r["id"],
                "a": r["name_A"],
                "b": r["name_B"],
                "same": r["mark (same/different)"].strip().lower() == "same",
                "section": r["section"],
                "quote": r["evidence"],
                "note": r.get("note", ""),
                "origin": keys.get(r["id"], "?"),
            }
        )
    return rows


class RuleEngine:
    """R1-R3 over one slice of text; `classify(a, b)` -> the first rule that would merge a and b."""

    def __init__(self, cfg: AliasConfig, text: str, vocab: dict[str, str]):
        self.cfg = cfg
        self.abbrevs = find_abbreviations(text, cfg)
        self.abbrev_keys = {
            frozenset((r1_key(p.long_form, cfg), r1_key(p.short_form, cfg))) for p in self.abbrevs
        }
        self.statements = alias_statements(text, vocab, cfg)
        self.id_name = {cid: s for s, cid in vocab.items()}
        self.stmt_keys: dict[frozenset[str], list] = defaultdict(list)
        for st in self.statements:
            k = frozenset((r1_key(st.x_surface, cfg), r1_key(st.y_surface, cfg)))
            self.stmt_keys[k].append(st)

    def classify(self, a: str, b: str) -> str | None:
        cfg = self.cfg
        ka, kb = r1_key(a, cfg), r1_key(b, cfg)
        if ka and ka == kb:
            return "R1-blocked(acronym collision)" if acronym_collision(a, b, cfg) else "R1"
        for x, y, ky in ((a, b, kb), (b, a, ka)):
            sp = split_embedded_acronym(x, cfg)
            if sp and ky in (r1_key(sp[0], cfg), r1_key(sp[1], cfg)):
                return "R2"
        if frozenset((ka, kb)) in self.abbrev_keys:
            return "R2"
        if hits := self.stmt_keys.get(frozenset((ka, kb))):
            return "R3-strong" if any(h.strength == "strong" for h in hits) else "R3-weak"
        return None


def main() -> None:
    cfg = AliasConfig.load()
    cp = json.loads(RUN.read_text())
    concepts = cp["concepts"]
    by_id = {c["concept_id"]: c for c in concepts}
    rows_sec = [
        json.loads(x) for x in SECTIONS.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    sec_ids = set(cp["mentions_by_section"])
    sections = [r for r in rows_sec if r["section_id"] in sec_ids]
    text = "\n\n".join(r["text"] for r in sections)
    vocab = build_vocab(concepts)
    never = yaml.safe_load(OVERRIDES.read_text())["never_merge"]
    never_keys = {frozenset((r1_key(a, cfg), r1_key(b, cfg))) for a, b in never}
    out: list[str] = [
        "# CR-008 STOP 1 — plan and $0 backtest",
        "",
        (
            f"Run: `{cp['run_id']}` (P&D ch. 1–3, {len(concepts)} concepts, "
            f"{len(sections)} sections). No API calls made."
        ),
        "",
    ]

    # ---------------- (a) backtest against the two owner sheets
    rows = load_sheet_rows()
    RuleEngine(cfg, text, {})  # R1/R2 engine; R3 per-row below
    for r in rows:
        v = {r["a"].lower(): "A", r["b"].lower(): "B"}
        eng = RuleEngine(cfg, text, v)
        r["rule"] = eng.classify(r["a"], r["b"])
    out += ["## (a) Backtest of R1–R3 against both owner merge sheets", ""]
    for sheet in ("CR-005", "CR-007"):
        sub = [r for r in rows if r["sheet"] == sheet]
        out.append(
            f"**{sheet}**: {len(sub)} rows ({sum(r['same'] for r in sub)} same / "
            f"{sum(not r['same'] for r in sub)} different)."
        )
    out += ["", "| Rule | owner `same` | owner `different` (wrong) |", "|---|---|---|"]
    rules = ["R1", "R1-blocked(acronym collision)", "R2", "R3-strong", "R3-weak", None]
    for rule in rules:
        s = sum(1 for r in rows if r["rule"] == rule and r["same"])
        w = [r for r in rows if r["rule"] == rule and not r["same"]]
        out.append(f"| {rule or 'no rule (would go to R4)'} | {s} | {len(w)} |")
    out += ["", "Owner-marked **wrong/different** pairs, and what the rules do with each:", ""]
    for r in rows:
        if not r["same"]:
            out.append(
                f"- {r['sheet']} #{r['id']} “{r['a']}” / “{r['b']}” → rule: **{r['rule']}**"
                + (f" — {r['note']}" if r["note"] else "")
            )
    out += [
        "",
        (
            "Owner-marked **same** pairs that no auto rule (R1, R2, R3-strong) would merge "
            "(they stay R4 or review):"
        ),
        "",
    ]
    for r in rows:
        if r["same"] and r["rule"] not in ("R1", "R2", "R3-strong"):
            out.append(f"- {r['sheet']} #{r['id']} “{r['a']}” / “{r['b']}” → {r['rule'] or 'R4'}")
    # conflicts between sheets
    seen: dict[frozenset, dict] = {}
    conflicts = []
    for r in rows:
        k = frozenset((r["a"].lower(), r["b"].lower()))
        if k in seen and seen[k]["same"] != r["same"]:
            conflicts.append((seen[k], r))
        seen.setdefault(k, r)
    out += [
        "",
        (
            f"**Owner marks that disagree across the two sheets: {len(conflicts)}** "
            "(the lexicon validator refuses a pair in both lists, so these need your ruling):"
        ),
        "",
    ]
    for x, y in conflicts:
        out.append(
            f"- “{x['a']}” / “{x['b']}”: {x['sheet']} #{x['id']} = "
            f"{'same' if x['same'] else 'different'}, {y['sheet']} #{y['id']} = "
            f"{'same' if y['same'] else 'different'}"
        )

    # ---------------- (b) currently separate nodes in the CR-007 run
    eng = RuleEngine(cfg, text, vocab)
    forms = [
        (c["concept_id"], f) for c in concepts for f in [c["canonical_name"], *c.get("aliases", [])]
    ]
    pairs: dict[frozenset, tuple[str, str, str]] = {}
    by_key: dict[str, set[str]] = defaultdict(set)
    for cid, f in forms:
        by_key[r1_key(f, cfg)].add(cid)
    blocked: list[tuple[str, str]] = []
    for k, ids in by_key.items():
        ids = sorted(ids)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = by_id[ids[i]]["canonical_name"], by_id[ids[j]]["canonical_name"]
                if acronym_collision(a, b, cfg):
                    blocked.append((a, b))
                else:
                    pairs.setdefault(frozenset(ids[i : j + 1 : j - i]), ("R1", a, b))
    split_names = 0
    for c in concepts:
        sp = split_embedded_acronym(c["canonical_name"], cfg)
        if sp:
            split_names += 1
            for cid in by_key.get(r1_key(sp[0], cfg), set()) | by_key.get(
                r1_key(sp[1], cfg), set()
            ):
                if cid != c["concept_id"]:
                    pairs.setdefault(
                        frozenset((cid, c["concept_id"])),
                        ("R2", by_id[cid]["canonical_name"], c["canonical_name"]),
                    )
    shorts: dict[str, set[str]] = defaultdict(set)
    for p in eng.abbrevs:
        shorts[p.short_form].add(r1_key(p.long_form, cfg))
        ids_l, ids_s = (
            by_key.get(r1_key(p.long_form, cfg), set()),
            by_key.get(r1_key(p.short_form, cfg), set()),
        )
        for x in ids_l:
            for y in ids_s:
                if x != y:
                    pairs.setdefault(
                        frozenset((x, y)),
                        ("R2", by_id[x]["canonical_name"], by_id[y]["canonical_name"]),
                    )
    collisions = {s: sorted(v) for s, v in shorts.items() if len(v) >= 2}
    weak = []
    for st in eng.statements:
        if st.x_id == st.y_id:
            continue
        key = frozenset((st.x_id, st.y_id))
        if st.strength == "strong":
            pairs.setdefault(
                key,
                ("R3-strong", by_id[st.x_id]["canonical_name"], by_id[st.y_id]["canonical_name"]),
            )
        else:
            weak.append(st)
    guarded = {
        k
        for k, (_, a, b) in pairs.items()
        if frozenset((r1_key(a, cfg), r1_key(b, cfg))) in never_keys
    }
    for k in guarded:
        del pairs[k]
    per_rule: dict[str, list] = defaultdict(list)
    for rule, a, b in pairs.values():
        per_rule[rule].append((a, b))
    out += [
        "",
        "## (b) Currently separate nodes the rules would merge (CR-007 run)",
        "",
        "| Rule | pairs merged |",
        "|---|---|",
    ]
    for rule in ("R1", "R2", "R3-strong"):
        out.append(f"| {rule} | {len(per_rule[rule])} |")
    out.append(f"| R3-weak (review only) | {len({(s.x_id, s.y_id) for s in weak})} |")
    out += [
        "",
        (
            f"Pairs blocked by an existing `never_merge`: {len(guarded)}. "
            f"Concept names with an embedded acronym to split (R2): {split_names}. "
            f"R1 acronym collisions (sent to review): {len(blocked)} {blocked[:5]}. "
            f"Ambiguous acronyms (one short form, ≥ 2 long forms): {len(collisions)} "
            f"{dict(list(collisions.items())[:5])}."
        ),
        "",
    ]
    for rule in ("R1", "R2", "R3-strong"):
        out += [f"**{rule} — up to 10 examples**", ""]
        out += [f"- “{a}” + “{b}”" for a, b in per_rule[rule][:10]] or ["- (none)"]
        out.append("")
    out += ["**R3-weak items (evidence quotes)**", ""]
    seen_w = set()
    for st in weak:
        if (st.x_id, st.y_id) in seen_w:
            continue
        seen_w.add((st.x_id, st.y_id))
        out.append(f"- [{st.rule}] “{st.x_surface}” ~ “{st.y_surface}”: …{st.quote}…")
    out.append("")

    # ---------------- (c) R4 calls R1-R3 would have replaced
    llm_pairs: list[tuple[str, str, str]] = []
    for m in cp["merges"]:
        if m["llm_called"]:
            llm_pairs.append(
                (
                    "merge",
                    by_id.get(m["concept_id"], {}).get("canonical_name", m["concept_id"]),
                    m["alias"],
                )
            )
    for m in cp["merge_review"]:
        llm_pairs.append(("review", m["candidate_name"], m["alias"]))
    for m in cp["taxonomy_candidates"]:
        a = by_id.get(m["concept_id"], {}).get("canonical_name")
        b = by_id.get(m["matched_concept_id"], {}).get("canonical_name")
        if a and b:
            llm_pairs.append((f"taxonomy-{m['decision']}", a, b))
    replaced = Counter()
    for kind, a, b in llm_pairs:
        r = eng.classify(a, b)
        if r in ("R1", "R2", "R3-strong"):
            replaced[(kind.split("-")[0], r)] += 1
    n_total = len(llm_pairs)
    n_rep = sum(replaced.values())
    exact = sum(1 for m in cp["merges"] if m["auto_merged"])
    out += [
        "## (c) R4 (LLM) merge calls R1–R3 would have replaced",
        "",
        (
            f"CR-007 logged **{n_total}** LLM-decided candidate pairs "
            f"({sum(m['llm_called'] for m in cp['merges'])} merged, {len(cp['merge_review'])} review-band, "
            f"{len(cp['taxonomy_candidates'])} broader/narrower; “different” outcomes are not "
            f"stored, so this is a lower bound). R1–R3 would have replaced **{n_rep}** of them "
            f"({n_rep / max(n_total, 1):.0%}): {dict(replaced) or 'none'}. A further {exact} exact-string "
            "merges were already free. At ≈ $0.0031 per call this is a saving of "
            f"${n_rep * 0.0031:.3f} on this slice; the full-book saving scales roughly with the "
            "number of sections."
        ),
        "",
    ]

    # ---------------- (d) lexicon seed
    entries: list[dict] = []
    for r in rows:
        entries.append(
            {
                "list": "same" if r["same"] else "different",
                "a": r["a"],
                "b": r["b"],
                "source": f"{r['sheet']} sheet row {r['id']}",
                "section": r["section"],
                "origin": "owner mark (information only)",
                "quote": r["quote"],
            }
        )
    for a, b in never:
        entries.append(
            {
                "list": "different",
                "a": a,
                "b": b,
                "source": "configs/canonical_overrides.yaml never_merge",
                "section": "",
                "origin": "owner mark (information only)",
                "quote": "",
            }
        )
    sent_by_sec = {r["section_id"]: _sentences(r["text"]) for r in sections}
    n_quote = 0
    for e in entries:
        if e["list"] != "different":
            continue
        for sid, sents in sent_by_sec.items():
            for s in sents:
                sl = s.lower()
                if e["a"].lower() in sl and e["b"].lower() in sl:
                    e["distinguish_quote"] = " ".join(s.split())
                    e["distinguish_section"] = sid
                    e["distinguishes"] = bool(DISTINGUISH.search(s))
                    break
            if "distinguish_quote" in e:
                break
        n_quote += "distinguish_quote" in e
    SEED_SHEET.parent.mkdir(parents=True, exist_ok=True)
    with SEED_SHEET.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "id",
                "list",
                "form_a",
                "form_b",
                "kind (different only)",
                "why",
                "source",
                "textbook quote",
                "quote section",
                "judgement (approve/reject/edit)",
            ]
        )
        i, done = 0, set()
        for e in sorted(entries, key=lambda e: e["list"] != "different"):
            k = (e["list"], frozenset((e["a"].lower(), e["b"].lower())))
            if k in done:
                continue
            done.add(k)
            i += 1
            w.writerow(
                [
                    i,
                    e["list"],
                    e["a"],
                    e["b"],
                    "",
                    "",
                    e["source"] + " [information only: owner-derived]",
                    e.get("distinguish_quote", ""),
                    e.get("distinguish_section", ""),
                    "(no tick needed)",
                ]
            )
    dif = [e for e in entries if e["list"] == "different"]
    out += [
        "## (d) Lexicon seed",
        "",
        (
            f"- From owner marks: **{sum(e['list'] == 'same' for e in entries)} `same`** and "
            f"**{len(dif)} `different`** candidate entries (duplicates between the sheets and the "
            "`never_merge` list are collapsed on load)."
        ),
        (
            f"- `different` pairs with a sentence in the slice that contains both forms: {n_quote} "
            f"of {len(dif)}; of those, {sum(bool(e.get('distinguishes')) for e in dif)} contain a "
            "distinguishing cue (unlike / whereas / differs / …)."
        ),
        (
            "- **Research-chat seed confusables: not found.** `configs/term_lexicon.yaml` does not "
            "exist in the repo and no seed list is in `docs/`. I have not invented any. Please paste "
            "or drop the seed list; until then the seed approval sheet "
            f"(`{SEED_SHEET}`) has no research-chat rows."
        ),
        "",
    ]
    for e in dif:
        out.append(
            f"- different: “{e['a']}” / “{e['b']}” ({e['source']})"
            + (
                f" — §{e['distinguish_section']}: “{e['distinguish_quote'][:200]}”"
                if e.get("distinguish_quote")
                else " — no co-occurring sentence"
            )
        )

    # ---------------- (e) equivalence audit
    eq = [
        r
        for r in cp["relation_results_v3"]
        if r["outcome"] == "edge" and r["relation"] == "equivalent_to"
    ]
    out += [
        "",
        "## (e) Equivalence audit — `equivalent_to` edges",
        "",
        f"{len(eq)} edge(s) in the run:",
        "",
    ]
    for r in eq:
        x, y = (
            by_id[r["pair"]["concept_x_id"]]["canonical_name"],
            by_id[r["pair"]["concept_y_id"]]["canonical_name"],
        )
        rule = eng.classify(x, y)
        out.append(
            f"- “{x}” ≡ “{y}” (direction {r['direction']}): R0–R3 → **{rule or 'no rule → equivalence_migration item on the merge sheet'}**. "
            f"Quote: “{r['evidence_quote']}”"
        )

    # ---------------- (f) misconception cue scan
    cues = yaml.safe_load(CUES.read_text())["families"]
    hits: dict[str, list[tuple[str, str]]] = {f: [] for f in cues}
    for sid, sents in sent_by_sec.items():
        for s in sents:
            for fam, pats in cues.items():
                if any(re.search(p, s, re.IGNORECASE) for p in pats):
                    hits[fam].append((sid, " ".join(s.split())))
    ci = [
        r
        for r in cp["relation_results_v3"]
        if r["outcome"] == "edge" and r["qualifiers"].get("corrects_intuition")
    ]
    diff_sent = [
        (sid, " ".join(s.split()))
        for e in dif
        if e.get("distinguish_quote")
        for sid, s in [(e["distinguish_section"], e["distinguish_quote"])]
    ]
    uniq = (
        {s for fam in hits.values() for _, s in fam}
        | {r["evidence_quote"] for r in ci}
        | {s for _, s in diff_sent}
    )
    n_calls = len(uniq)
    out += [
        "",
        "## (f) Misconception cue scan ($0)",
        "",
        f"{sum(len(_sentences(r['text'])) for r in sections)} sentences scanned.",
        "",
        "| Family | hits |",
        "|---|---|",
    ]
    for fam, h in hits.items():
        out.append(f"| {fam} | {len(h)} |")
    out += [
        f"| existing: `corrects_intuition` edges | {len(ci)} |",
        f"| existing: `different` pairs co-mentioned | {len(diff_sent)} |",
        "",
    ]
    for fam, h in hits.items():
        out += [f"**{fam} — 5 examples**", ""]
        out += [f"- §{sid}: {s[:260]}" for sid, s in h[:5]] or ["- (none)"]
        out.append("")
    out += ["**`corrects_intuition` edges**", ""]
    out += [f"- {r['statement']} — “{r['evidence_quote']}”" for r in ci] or ["- (none)"]
    out += [
        "",
        (
            f"**Preflight for structuring (§5.3):** {n_calls} distinct candidate sentences ⇒ "
            f"{n_calls} strong-tier calls × ≈ ${USD_PER_STRUCTURING_CALL:.3f} (3.5k in / 1.5k out incl. "
            f"reasoning) ≈ **${n_calls * USD_PER_STRUCTURING_CALL:.2f}**; family 4 is noisy, so most "
            f"calls should end at `is_warning: no`. Verifying proposed correct edges is extra "
            "(≈ $0.1–0.3 in the CR). Cap stays $3."
        ),
        "",
    ]
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {REPORT} and {SEED_SHEET}")


if __name__ == "__main__":
    main()
