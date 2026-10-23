"""CR-010 STOP 3: the machine-readable eRST audit ($0, no model). Checks the inventory file against the primary paper
(Appendix A Table A.1, the nuclearity legend, Section 3.3 / Table 1) and against the project's own invariants.

    uv run python -m cumap.erst.audit            # writes reports/cr010_stop3_audit.json and .md
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT, get_settings
from cumap.erst import guards as G
from cumap.erst.edges import ErstEdge, ErstSignal
from cumap.erst.registry import (
    NO_RELATION,
    RELATIONS_PATH,
    SIGNALS_PATH,
    ErstRegistry,
    UnknownErstLabel,
)

PAPER_TXT = REPO_ROOT / "data/raw/external/erst_paper/arxiv_2403.13560v2.txt"
PAPER_TABLE = REPO_ROOT / "tests/fixtures/erst_table_a1_paper.json"
FIXTURES = REPO_ROOT / "tests/fixtures/cr010_erst_fixtures.yaml"
MAPPING = REPO_ROOT / "data/interim/checks/cr010_current_to_erst_mapping_NOT_GOLD.csv"
OUT_JSON = REPO_ROOT / "reports/cr010_stop3_audit.json"
OUT_MD = REPO_ROOT / "reports/cr010_stop3_audit.md"
_ROW = re.compile(r"\s*([A-Z]+)\s*-\s*([A-Z]+)\s+(→←|←|→|Λ)\s+(.*)")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _flag(cid: str, detail) -> dict:
    return {"id": cid, "status": "FLAG", "detail": detail, "kind": "flag"}


def _check(cid: str, ok: bool | None, detail, kind: str = "check") -> dict:
    return {
        "id": cid,
        "status": "skipped" if ok is None else ("pass" if ok else "FAIL"),
        "detail": detail,
        "kind": kind,
    }


def paper_rows(text: str) -> dict[str, tuple[str, str]]:
    i = text.index("relation name                 nuclearity   definition")
    j = text.index("Table A.1: Relation Labels in the GUM")
    out = {}
    for line in text[i:j].splitlines()[1:]:
        if m := _ROW.match(line):
            out[f"{m.group(1)}-{m.group(2)}"] = (m.group(3), m.group(4).strip())
    return out


def _tok(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", s.lower()) if len(t) > 2}


def _jaccard(a: str, b: str) -> float:
    x, y = _tok(a), _tok(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def run_audit(paper_text: str | None) -> dict:
    reg = ErstRegistry.load()
    fx = yaml.safe_load(FIXTURES.read_text())
    rt = fx["registry_tests"]
    res: list[dict] = []
    # ---- A. inventory counts and the exact label set
    labels, disc = reg.labels, reg.discourse_labels
    res.append(
        _check(
            "A1_counts",
            len(labels) == rt["expected_label_count"]
            and len(disc) == rt["expected_true_discourse_relation_count"]
            and set(labels) - set(disc) == set(rt["technical_labels"]),
            {
                "labels": len(labels),
                "true_discourse_relations": len(disc),
                "technical": sorted(set(labels) - set(disc)),
            },
        )
    )
    res.append(
        _check(
            "A2_label_set_equals_fixture",
            set(labels) == set(rt["must_include"]),
            {
                "missing": sorted(set(rt["must_include"]) - set(labels)),
                "extra": sorted(set(labels) - set(rt["must_include"])),
            },
        )
    )
    # ---- B/C. against the primary paper's Table A.1
    pt = json.loads(PAPER_TABLE.read_text())["rows"]
    pmap = {r["label"]: r["symbol"] for r in pt}
    res.append(
        _check(
            "B1_labels_equal_paper_table_A1",
            set(pmap) == set(labels),
            {
                "paper_rows": len(pmap),
                "missing_in_package": sorted(set(pmap) - set(labels)),
                "extra_in_package": sorted(set(labels) - set(pmap)),
            },
            "source",
        )
    )
    sym_bad = {
        r.label: [r.primary_nuclearity_symbol, pmap.get(r.label)]
        for r in reg.relations
        if pmap.get(r.label) != r.primary_nuclearity_symbol
    }
    res.append(
        _check("B2_nuclearity_symbols_equal_paper", not sym_bad, {"mismatches": sym_bad}, "source")
    )
    # ---- D. hierarchy
    hier = reg.hierarchy()
    res.append(
        _check(
            "D1_hierarchy_naming_rule",
            True,
            {
                "discourse_coarse_classes": len([c for c in hier if c != "technical"]),
                "per_class": {c: len(v) for c, v in hier.items()},
                "note": "SAME-UNIT sits in the package's 'technical' bucket, not a discourse coarse class (the paper: not a proper discourse relation, a device for discontinuous units); every other label obeys <coarse-class>-<fine-grained>, enforced at load",
            },
        )
    )
    # ---- E. nuclearity
    counts = Counter(r.primary_nuclearity_symbol for r in reg.relations)
    fixed = {
        r.label: r.primary_nuclearity_symbol
        for r in reg.relations
        if r.primary_nuclearity_symbol in {"←", "→"}
    }
    res.append(
        _check(
            "E1_nuclearity_distribution",
            dict(counts) == {"→←": 19, "Λ": 7, "←": 3, "→": 3},
            {"counts": dict(counts), "fixed_orientation_labels": fixed},
        )
    )
    res.append(
        _check(
            "E2_orientation_reading_flagged_for_research",
            True,
            {
                "reading": "the arrow points at the nucleus: '←' nucleus first, satellite after; '→' satellite first; '→←' either; 'Λ' multinuclear",
                "basis": "the paper's legend says '←' is for satellite relations that only go left-to-right; the reading is consistent with the definitions of all six fixed-orientation rows (elaboration, partial restatement follow their nucleus; heading, preparation, question precede it) but is an inference to be confirmed by Research",
                "enforced_in": "ErstEdge (primary edges only; secondary edges record a direction and never nuclearity)",
            },
            "flag",
        )
    )
    # ---- F/G/H/I. paper text cross-checks
    if paper_text is None:
        for cid in (
            "F1_definitions_vs_paper",
            "G1_legend_vs_paper",
            "H1_signal_types_vs_paper",
            "H2_signal_subtypes_in_paper_table1",
            "I1_secondary_edge_rule_vs_paper",
        ):
            res.append(_check(cid, None, "local paper text not present", "source"))
    else:
        rows = paper_rows(paper_text)
        low = sorted(
            (_jaccard(r.definition, rows[r.label][1]), r.label)
            for r in reg.relations
            if r.label in rows
        )
        res.append(
            _check(
                "F1_definitions_vs_paper",
                len(rows) == len(labels),
                {
                    "paper_rows_parsed": len(rows),
                    "method": "token-set Jaccard between the package definition and the paper definition (the package paraphrases the paper)",
                    "lowest_overlap_for_human_review": [
                        {"label": l, "jaccard": round(j, 2)} for j, l in low[:6]
                    ],
                    "median_jaccard": round(sorted(j for j, _ in low)[len(low) // 2], 2),
                },
                "source",
            )
        )
        legend_ok = all(s in paper_text for s in ("(for satel-", "multinu-", "→←")) and set(
            yaml.safe_load(RELATIONS_PATH.read_text())["nuclearity_legend"]
        ) == {"←", "→", "→←", "Λ"}
        res.append(
            _check(
                "G1_legend_vs_paper",
                legend_ok,
                "the package legend has the four symbols the paper's Appendix A defines",
                "source",
            )
        )
        sec = re.search(
            r"we divide non-DM signals\s+into seven types, corresponding to:\s*(.*?)\.\s",
            paper_text,
            re.DOTALL,
        )
        paper_types = (
            sorted(w for w in re.findall(r"[a-z]+", sec.group(1)) if w not in {"and", "features"})
            if sec
            else []
        )
        mine = sorted(k for k in reg.signals if k != "discourse_marker")
        res.append(
            _check(
                "H1_signal_types_vs_paper",
                paper_types == mine,
                {"paper": paper_types, "package": mine},
                "source",
            )
        )
        tbl = paper_text[
            paper_text.index(" signal type     subtypes") : paper_text.index(
                "Table 1: Non-DM signal types"
            )
        ].lower()
        miss = [
            f"{k}:{s}"
            for k in mine
            for s in reg.subtypes(k)
            if not all(part.strip() in tbl for part in re.split(r"/|,", s))
        ]
        res.append(
            _check("H2_signal_subtypes_in_paper_table1", not miss, {"not_found": miss}, "source")
        )
        compact = re.sub(r"\s+", " ", paper_text)
        res.append(
            _check(
                "I1_secondary_edge_rule_vs_paper",
                "secondary edges express only relations, and not overall prominence" in compact
                and "do not fabricate primary-tree nuclearity"
                in yaml.safe_load(RELATIONS_PATH.read_text())["secondary_edge_rule"],
                "the paper: secondary edges express only relations, not prominence; the package rule forbids a fabricated nuclearity on them",
                "source",
            )
        )
    # ---- J. semantic guards from the fixtures (run against the real registry)
    lex = _lexicon()
    cases = [
        (
            "same_unit_not_semantic",
            lambda: (
                not any(
                    G.check_kg_effect(reg, "SAME-UNIT", e).allowed
                    for e in (
                        G.PAIR_PRIORITY,
                        G.SAME_CONCEPT_CANDIDATE,
                        G.DOCUMENT_STRUCTURE,
                        G.DOMAIN_EDGE,
                    )
                )
                and NO_RELATION in reg.choice_set()
                and "SAME-UNIT" not in reg.choice_set()
            ),
        ),
        (
            "restatement_no_auto_merge",
            lambda: (
                G.check_kg_effect(reg, "RESTATEMENT-REPETITION", G.SAME_CONCEPT_CANDIDATE).allowed
                and not G.check_kg_effect(
                    reg,
                    "RESTATEMENT-REPETITION",
                    G.DOMAIN_EDGE,
                    relation="equivalent_to",
                    independent_domain_evidence=True,
                ).allowed
                and not G.check_kg_effect(
                    reg, "RESTATEMENT-REPETITION", G.DOMAIN_EDGE, independent_domain_evidence=True
                ).allowed
            ),
        ),
        (
            "list_not_contrast",
            lambda: (
                not any(
                    G.check_kg_effect(
                        reg,
                        "JOINT-LIST",
                        G.DOMAIN_EDGE,
                        relation=r,
                        independent_domain_evidence=True,
                    ).allowed
                    for r in G.CONTRAST_RELATIONS
                )
            ),
        ),
        (
            "attribution_not_domain_edge",
            lambda: (
                not G.check_kg_effect(
                    reg, "ATTRIBUTION-POSITIVE", G.DOMAIN_EDGE, relation="uses"
                ).allowed
                and G.check_kg_effect(
                    reg,
                    "ATTRIBUTION-POSITIVE",
                    G.DOMAIN_EDGE,
                    relation="uses",
                    independent_domain_evidence=True,
                ).allowed
            ),
        ),
        (
            "organization_not_domain_edge",
            lambda: (
                not G.check_kg_effect(
                    reg,
                    "ORGANIZATION-HEADING",
                    G.DOMAIN_EDGE,
                    relation="part_of",
                    independent_domain_evidence=True,
                ).allowed
                and G.check_kg_effect(reg, "ORGANIZATION-HEADING", G.DOCUMENT_STRUCTURE).allowed
            ),
        ),
        (
            "condition_not_prerequisite",
            lambda: (
                not G.check_kg_effect(
                    reg,
                    "CONTINGENCY-CONDITION",
                    G.DOMAIN_EDGE,
                    relation="prerequisite_of",
                    independent_domain_evidence=True,
                ).allowed
            ),
        ),
        (
            "contrast_dimension_guard",
            lambda: (
                not G.check_kg_effect(
                    reg,
                    "ADVERSATIVE-CONTRAST",
                    G.DOMAIN_EDGE,
                    relation="contrasts_with",
                    independent_domain_evidence=True,
                ).allowed
                and G.check_kg_effect(
                    reg,
                    "ADVERSATIVE-CONTRAST",
                    G.DOMAIN_EDGE,
                    relation="contrasts_with",
                    independent_domain_evidence=True,
                    grounded_dimension=True,
                ).allowed
            ),
        ),
    ]
    want = {g["id"] for g in fx["semantic_guards"]}
    out = {cid: bool(fn()) for cid, fn in cases}
    res.append(_check("J1_semantic_guards", set(out) == want and all(out.values()), out))
    # the lexicon stores some pairs under longer surface forms; try the fixture's forms and the lexicon's own entry forms
    reg_pairs, gaps = [], []
    own = {
        frozenset(map(str.lower, e.forms)): list(e.forms)
        for e in (lex.approved("different") if lex else [])
    }
    for c in fx["canonicalisation_regressions"]:
        fixture_form = lex is not None and lex.is_different(c["left"], c["right"])
        entry = next(
            (
                f
                for k, f in own.items()
                if any(c["left"].lower() in x for x in k)
                and any(c["right"].lower() in x for x in k)
            ),
            None,
        )
        entry_form = lex is not None and entry is not None and lex.is_different(entry[0], entry[1])
        gate = G.merge_gate(
            lex, *(entry if entry_form and not fixture_form else (c["left"], c["right"]))
        )
        reg_pairs.append(
            {
                "pair": [c["left"], c["right"]],
                "recognised_as_different_by_fixture_surface_forms": fixture_form,
                "lexicon_entry_forms": entry,
                "recognised_via_lexicon_entry_forms": entry_form,
                "merge_gate_allowed": gate.allowed,
            }
        )
        if not fixture_form:
            gaps.append(reg_pairs[-1])
    res.append(
        _check(
            "J2_no_cr008_equivalence_violation",
            lex is not None
            and all(not p["merge_gate_allowed"] for p in reg_pairs)
            and not any(G.signal_licenses_domain_relation(k, None, "part_of") for k in reg.signals),
            {
                "pairs": reg_pairs,
                "rule": "an eRST restatement/synonymy signal may only queue a same-concept candidate; an approved `different` pair is never merged",
            },
        )
    )
    if gaps:
        res.append(
            _flag(
                "J3_lexicon_surface_form_gap",
                {
                    "finding": "Lexicon.is_different matches only the exact surface forms of an entry: the fixture's bare forms are not recognised for these pairs, only the lexicon's own long forms are. This is the existing CR-008 guard, not an eRST behaviour; nothing was changed in CR-010.",
                    "pairs": gaps,
                    "options": [
                        "owner adds the bare forms to the approved `different` entry (data change in configs/term_lexicon.yaml)",
                        "CR-008 matching also compares the short form of an 'X (ABC)' entry (code change, stricter, needs a DECISIONS entry)",
                        "leave as is: node names carry the long form + acronym alias, so the merge guard sees the long form",
                    ],
                },
            )
        )
    # ---- K. no invented relations, equivalence retired
    settings = get_settings()
    dom = yaml.safe_load((REPO_ROOT / settings.relation_registry).read_text())
    dom_names = _domain_names(dom)
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower())
    clash = sorted(r for r in dom_names if norm(r) in {norm(x) for x in labels})
    allrows = list(csv.reader(MAPPING.open(encoding="utf-8")))
    hdr_i = next(i for i, r in enumerate(allrows) if r and r[0] == "current_relation")
    rows = [r for r in allrows[hdr_i + 1 :] if r]
    targets = {t for r in rows if len(r) > 2 and r[2] for t in r[2].split(";")}
    from cumap.expert_kg.checks import retired_relation_errors

    res.append(
        _check(
            "K1_mapping_targets_are_inventory_labels",
            targets <= set(labels),
            {"targets": len(targets), "not_in_inventory": sorted(targets - set(labels))},
        )
    )
    res.append(
        _check(
            "K2_no_label_equals_a_domain_relation_name",
            not clash,
            {"clashes": clash, "active_registry": str(settings.relation_registry)},
        )
    )
    res.append(
        _check(
            "K3_equivalent_to_stays_retired",
            "equivalent_to" not in dom_names and bool(retired_relation_errors(["equivalent_to"])),
            {
                "in_active_registry": "equivalent_to" in dom_names,
                "validator_rejects": bool(retired_relation_errors(["equivalent_to"])),
            },
        )
    )
    touching = [
        {"current": r[0], "layer": r[1], "erst_hypotheses": r[2]}
        for r in rows
        if r
        and r[0]
        in {
            "equivalent_to",
            "conflated_with",
            "identifies",
            "encapsulates",
            "trades_off_with",
            "instantiates",
        }
    ]
    res.append(
        _check(
            "K4_mapping_rows_for_retired_or_misconception_relations",
            True,
            {
                "rows": touching,
                "note": "hypotheses only (NOT GOLD); equivalent_to maps to RESTATEMENT-* strictly as canonicalisation evidence",
            },
            "flag",
        )
    )
    # ---- L/M. fail-closed
    bad_labels = [
        "CAUSAL-REASON",
        "causal-cause",
        "synonym_of",
        "same_as",
        "EQUIVALENT-TO",
        "",
        "SAME_UNIT",
    ]
    raised = []
    for b in bad_labels:
        try:
            reg.get(b)
            raised.append(False)
        except UnknownErstLabel:
            raised.append(True)
    edge = {
        "edge_kind": "primary",
        "evidence": "x",
        "nucleus_units": ["u1"],
        "satellite_unit": "u2",
        "satellite_position": "after",
        "from_unit": None,
        "to_unit": None,
        "signals": [],
        "concurrent_labels": [],
    }
    rejects = {}
    for lab in ("CAUSAL-REASON", "SAME-UNIT"):
        try:
            ErstEdge(**{**edge, "label": lab})
            rejects[lab] = False
        except ValueError:
            rejects[lab] = True
    res.append(
        _check(
            "L1_unknown_labels_fail_closed",
            all(raised) and all(rejects.values()) and rt["unknown_label_behavior"] == "fail_closed",
            {
                "registry_lookup": dict(zip(bad_labels, raised, strict=True)),
                "edge_construction_rejected": rejects,
            },
        )
    )
    sig_bad = []
    for kw in (
        {"kind": "semantic", "subtype": "synonym_of", "anchor_text": "x"},
        {"kind": "invented", "subtype": None, "anchor_text": "x"},
        {"kind": "discourse_marker", "subtype": None, "anchor_text": None},
    ):
        try:
            ErstSignal(**kw)
            sig_bad.append(False)
        except ValueError:
            sig_bad.append(True)
    res.append(_check("L2_unknown_or_unanchored_signals_rejected", all(sig_bad), sig_bad))
    # ---- N. provenance
    prov = {
        "erst_relations.yaml": _sha(RELATIONS_PATH),
        "erst_signals.yaml": _sha(SIGNALS_PATH),
        "fixtures": _sha(FIXTURES),
        "paper_table_fixture": _sha(PAPER_TABLE),
        "paper_text_present": paper_text is not None,
        "paper": "arXiv:2403.13560v2 (28 Aug 2024); journal version not compared",
        "registry_id": reg.meta["registry_id"],
    }
    n_fail = sum(r["status"] == "FAIL" for r in res)
    return {"stop": "CR-010 STOP 3", "failed_checks": n_fail, "checks": res, "provenance": prov}


def _domain_names(dom: dict) -> set[str]:
    rels = dom.get("relations", [])
    return {r["name"] if isinstance(r, dict) else str(r) for r in rels}


def _lexicon():
    from cumap.expert_kg.lexicon import Lexicon

    try:
        return Lexicon.load()
    except Exception:  # noqa: BLE001
        return None


def to_markdown(a: dict) -> str:
    L = [
        "# CR-010 STOP 3 — eRST inventory audit",
        "",
        f"Failed checks: **{a['failed_checks']}** of {len(a['checks'])}. Machine-readable: `reports/cr010_stop3_audit.json`. Generated by `uv run python -m cumap.erst.audit`.",
        "",
        "| check | kind | status |",
        "|---|---|---|",
    ]
    L += [f"| {c['id']} | {c['kind']} | {c['status']} |" for c in a["checks"]]
    L += [
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(a["provenance"], indent=1, ensure_ascii=False),
        "```",
        "",
    ]
    for c in a["checks"]:
        if c["kind"] == "flag" or c["status"] not in {"pass"}:
            L += [
                f"### {c['id']} ({c['status']})",
                "",
                "```json",
                json.dumps(c["detail"], indent=1, ensure_ascii=False),
                "```",
                "",
            ]
    return "\n".join(L)


def main() -> None:
    text = PAPER_TXT.read_text(encoding="utf-8", errors="replace") if PAPER_TXT.exists() else None
    a = run_audit(text)
    OUT_JSON.write_text(json.dumps(a, indent=1, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(to_markdown(a), encoding="utf-8")
    print(f"failed checks: {a['failed_checks']} of {len(a['checks'])}")
    sys.exit(1 if a["failed_checks"] else 0)


if __name__ == "__main__":
    main()
