"""CR-029: standing lexicon intake and the `same_concept` queue reader.

Read-only on a finished run. Collects the identity decisions where an owner mark changes something (handoff §9 table, mapped
to today's records), removes pairs the lexicon already covers and pairs already marked, and writes ONE blind owner sheet to
`data/interim/suggestions/` (names, types and quotes only) plus a key file with each row's source. Nothing here writes the
lexicon or `data/gold/`; an owner mark becomes an entry only through `lexicon_proposals.propose_from_marks`.
"""

from __future__ import annotations

import csv
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from cumap.expert_kg.alias_rules import AliasConfig, alias_statements, r1_key
from cumap.expert_kg.lexicon import Lexicon

# the sheet's row order (handoff §9 table): groups first, then book order
GROUPS = (
    "u4_weak_cue",
    "u5_same_merged",
    "u5_same_held",
    "u5_not_a_concept",
    "u5_sample_narrower_broader_new",
    "audit_deterministic_merge",
)
SAMPLE_SIZE = {"u5_sample_narrower_broader_new": 5, "audit_deterministic_merge": 10}
DETERMINISTIC_RULES = {"exact", "R0", "R1", "R2", "R3-strong"}
SHEET_COLUMNS = ["id", "section", "name_a", "name_b", "type_a", "type_b", "quote", "mark", "note"]
MARKS = {"same", "different", "neither"}
DEFAULT_CAP = 40
DEFAULT_SEED = 29


@dataclass
class Candidate:
    group: str
    a: str
    b: str
    a_type: str
    b_type: str
    section: str
    quote: str
    source: dict = field(default_factory=dict)

    def pair_key(self, cfg: AliasConfig) -> frozenset[str]:
        return frozenset((r1_key(self.a, cfg), r1_key(self.b, cfg)))


def section_sort_key(section_id: str) -> tuple:
    """Book order from a section id such as '1.3', '1.3#2' or '1-problem-building-a-network'."""
    nums = [int(x) for x in re.findall(r"\d+", section_id.split("#")[0].split("-")[0])]
    chunk = re.search(r"#(\d+)", section_id)
    return (tuple(nums) or (0,), int(chunk.group(1)) if chunk else 0, section_id)


# ---------------------------------------------------------------- readers (all read-only)
def same_concept_queue(cp: dict) -> list[dict]:
    """Every `same_concept` result of a run: pair, section, sentence, evidence quote (CR-029 §8 step 1 reader)."""
    names = {c["concept_id"]: c for c in cp.get("concepts", [])}
    out = []
    for r in cp.get("relation_results_v3", []):
        if r.get("outcome") != "same_concept":
            continue
        p = r["pair"]
        x, y = names.get(p["concept_x_id"], {}), names.get(p["concept_y_id"], {})
        out.append(
            {
                "pair_id": p["pair_id"],
                "section_id": p["section_id"],
                "x_id": p["concept_x_id"],
                "y_id": p["concept_y_id"],
                "x_name": x.get("canonical_name", p["concept_x_id"]),
                "y_name": y.get("canonical_name", p["concept_y_id"]),
                "x_type": x.get("node_type", ""),
                "y_type": y.get("node_type", ""),
                "sentence": p.get("sentence", ""),
                "evidence_quote": r.get("evidence_quote") or "",
                "statement": r.get("statement", ""),
            }
        )
    return out


def _mention_quote(concept: dict, section_id: str, alias: str) -> str:
    ms = [m for m in concept.get("mentions", []) if m.get("quote")]
    same = [m for m in ms if m.get("section_id") == section_id] or ms
    hit = [m for m in same if alias.lower() in m["quote"].lower()]
    return (hit or same or [{"quote": ""}])[0]["quote"]


def collect(
    cp: dict,
    v4: dict | None,
    lexicon: Lexicon,
    *,
    section_texts: dict[str, str] | None = None,
) -> list[Candidate]:
    """All candidate rows by group, uncapped and unsampled."""
    cfg = lexicon.cfg
    concepts = {c["concept_id"]: c for c in cp.get("concepts", [])}
    nodes = (v4 or {}).get("nodes", {})
    cands: list[Candidate] = []

    def cname(cid: str) -> tuple[str, str]:
        c = concepts.get(cid, {})
        return c.get("canonical_name", cid), c.get("node_type", "")

    # U4 weak cues ("sometimes called"): recomputed from the section texts, never auto-merged
    if section_texts:
        vocab = {}
        for c in concepts.values():
            for f in [c["canonical_name"], *c.get("aliases", [])]:
                vocab.setdefault(f.lower(), c["concept_id"])
        for sid, text in section_texts.items():
            for st in alias_statements(text, vocab, cfg):
                if st.strength != "weak":
                    continue
                (a, at), (b, bt) = cname(st.x_id), cname(st.y_id)
                cands.append(
                    Candidate(
                        "u4_weak_cue", a, b, at, bt, sid, st.quote,
                        {"kind": "r3_weak", "cue": st.rule, "x_id": st.x_id, "y_id": st.y_id},
                    )
                )  # fmt: skip

    # LLM canonicalisation merges (R4) -> "U5 same, merged"; deterministic merges -> audit sample
    for m in cp.get("merges", []):
        if m.get("stage") != "canonicalize_v4":
            continue
        c = concepts.get(m["concept_id"], {})
        name, typ = c.get("canonical_name", m["concept_id"]), c.get("node_type", "")
        quote = m.get("evidence_quote") or _mention_quote(c, m["section_id"], m["alias"])
        src = {
            "kind": "checkpoint.merges",
            "concept_id": m["concept_id"],
            "rule_id": m.get("rule_id"),
            "llm_called": m.get("llm_called"),
            "reason": m.get("reason"),
            "similarity": m.get("similarity"),
        }
        if m.get("llm_called") and not m.get("auto_merged"):
            cands.append(
                Candidate("u5_same_merged", m["alias"], name, typ, typ, m["section_id"], quote, src)
            )
        elif m.get("rule_id") in DETERMINISTIC_RULES:
            cands.append(Candidate("audit_deterministic_merge", m["alias"], name, typ, typ, m["section_id"], quote, src))  # fmt: skip

    # the 0.70 review band -> "U5 same, held back"
    for r in cp.get("merge_review", []):
        name, typ = cname(r["concept_id"])
        cands.append(
            Candidate(
                "u5_same_held", name, r["candidate_name"], typ, r.get("candidate_type") or "",
                r["section_id"], r.get("quote") or "",
                {"kind": "merge_review", "concept_id": r["concept_id"], "candidate_id": r["candidate_id"],
                 "alias": r.get("alias"), "reason": r.get("llm_reason"), "similarity": r.get("similarity")},
            )
        )  # fmt: skip

    # the `same_concept` queue (lane C) -> "U5 same" rows
    for q in same_concept_queue(cp):
        cands.append(
            Candidate(
                "u5_same_held", q["x_name"], q["y_name"], q["x_type"], q["y_type"], q["section_id"],
                q["evidence_quote"] or q["sentence"],
                {"kind": "same_concept_queue", "pair_id": q["pair_id"], "statement": q["statement"]},
            )
        )  # fmt: skip

    # taxonomy decisions (narrower / broader): both nodes are kept, so a small sample
    for t in cp.get("taxonomy_candidates", []):
        (a, at), (b, bt) = cname(t["concept_id"]), cname(t["matched_concept_id"])
        c = concepts.get(t["concept_id"], {})
        cands.append(
            Candidate(
                "u5_sample_narrower_broader_new", a, b, at, bt, t["section_id"],
                _mention_quote(c, t["section_id"], a),
                {"kind": "taxonomy_candidates", "decision": t["decision"], "reason": t.get("reason")},
            )
        )  # fmt: skip

    # rejected-link adjudicator decisions (G-link-adjudicated) by decision type
    for m in (v4 or {}).get("merges", []):
        if m.get("rule_id") != "G-link-adjudicated":
            continue
        node = nodes.get(m["node_id"], {})
        nm, typ = node.get("name", m["node_id"]), node.get("node_type", "")
        src = {"kind": "G-link-adjudicated", "decision": m["decision"], "reason": m.get("reason"),
               "input_hash": m.get("input_hash")}  # fmt: skip
        grp = {
            "same_as_target": "u5_same_merged",
            "not_a_concept": "u5_not_a_concept",
            "new_concept": "u5_sample_narrower_broader_new",
        }.get(m["decision"])
        if grp:
            cands.append(
                Candidate(
                    grp, m["surface"], nm, typ, typ, m["section_id"], m.get("evidence") or "", src
                )
            )
    return cands


def marked_pairs(gold_dir: Path, cfg: AliasConfig) -> set[frozenset[str]]:
    """Pairs the owner already marked on an earlier intake sheet (read-only scan of data/gold/lexicon_intake_*.csv)."""
    out: set[frozenset[str]] = set()
    for p in sorted(gold_dir.glob("lexicon_intake_*.csv")):
        with p.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("mark") or "").strip().lower() in MARKS:
                    out.add(frozenset((r1_key(r["name_a"], cfg), r1_key(r["name_b"], cfg))))
    return out


def build_sheet(
    cands: list[Candidate],
    lexicon: Lexicon,
    *,
    already_marked: set[frozenset[str]] = frozenset(),  # type: ignore[assignment]
    cap: int = DEFAULT_CAP,
    seed: int = DEFAULT_SEED,
) -> tuple[list[Candidate], dict]:
    """Filter, sample and cap. Returns (sheet rows in order, key-file info)."""
    cfg = lexicon.cfg
    skipped = {"lexicon_covered": 0, "already_marked": 0, "duplicate_pair": 0, "same_name": 0}
    seen: set[frozenset[str]] = set()
    kept: list[Candidate] = []
    for c in sorted(cands, key=lambda c: (GROUPS.index(c.group), section_sort_key(c.section))):
        pk = c.pair_key(cfg)
        if len(pk) < 2 or c.a.strip().lower() == c.b.strip().lower():
            skipped["same_name"] += 1
        elif lexicon.is_different(c.a, c.b) or lexicon.same_decision(c.a, c.b):
            skipped["lexicon_covered"] += 1
        elif pk in already_marked:
            skipped["already_marked"] += 1
        elif pk in seen:
            skipped["duplicate_pair"] += 1
        else:
            seen.add(pk)
            kept.append(c)
    rng = random.Random(seed)
    rows: list[Candidate] = []
    unsampled: list[Candidate] = []
    for g in GROUPS:
        gl = [c for c in kept if c.group == g]
        n = SAMPLE_SIZE.get(g)
        if n is not None and len(gl) > n:
            chosen = set(rng.sample(range(len(gl)), n))
            unsampled += [c for i, c in enumerate(gl) if i not in chosen]
            gl = [c for i, c in enumerate(gl) if i in chosen]
        rows += gl
    sheet, overflow = rows[:cap], rows[cap:]
    info = {
        "seed": seed,
        "cap": cap,
        "skipped": skipped,
        "candidates_by_group": {g: sum(1 for c in kept if c.group == g) for g in GROUPS},
        "overflow_for_next_sheet": [_key_row(i, c) for i, c in enumerate(overflow, len(sheet) + 1)],
        "unsampled_not_listed": len(unsampled),
    }
    return sheet, info


def _key_row(i: int, c: Candidate) -> dict:
    return {"id": i, "group": c.group, "a": c.a, "b": c.b, "section": c.section, "source": c.source}


def write_sheet(
    run_id: str, sheet: list[Candidate], info: dict, out_dir: Path
) -> tuple[Path, Path]:
    """Blind CSV (no decision, reason or similarity) plus a key file. Never overwrites; never writes data/gold/."""
    if "gold" in out_dir.parts:
        raise ValueError("code never writes under data/gold/ (rule 2)")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"lexicon_intake_{run_id}.csv"
    key_path = out_dir / f"lexicon_intake_{run_id}_key.json"
    if csv_path.exists() or key_path.exists():
        raise FileExistsError(f"{csv_path.name} already exists; every sheet is a new file")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(SHEET_COLUMNS)
        for i, c in enumerate(sheet, 1):
            w.writerow([i, c.section, c.a, c.b, c.a_type, c.b_type, c.quote, "", ""])
    key = {"run_id": run_id, "rows": [_key_row(i, c) for i, c in enumerate(sheet, 1)], **info}
    key_path.write_text(
        json.dumps(key, indent=1, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return csv_path, key_path


# ---------------------------------------------------------------- marks -> proposals (CR-008 learning loop, unchanged rules)
def marked_rows(sheet_csv: Path, sheet_name: str) -> tuple[list[dict], list[dict]]:
    """(rows for `propose_from_marks`, pairs marked `neither`). Reads the marked sheet only."""
    rows, neither = [], []
    with sheet_csv.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            mark = (r.get("mark") or "").strip().lower()
            if mark not in MARKS:
                continue
            base = {"sheet": sheet_name, "id": r["id"], "a": r["name_a"], "b": r["name_b"],
                    "section": r.get("section") or "", "quote": r.get("quote") or "", "note": r.get("note") or ""}  # fmt: skip
            if mark == "neither":
                neither.append(base)
            else:
                rows.append({**base, "same": mark == "same"})
    return rows, neither
