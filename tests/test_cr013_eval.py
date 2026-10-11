"""CR-013 STOP 4: the evaluation overlay. It consumes the frozen CR-012 outputs (no model call, no regenerated prediction, no reinterpreted gold), stays strictly separate from the
production explainer, and localises failures with the frozen attribution. Skipped when the retained runs or the gold sheets are absent."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from cumap.cr012.attribution import CODES as FROZEN_CODES
from cumap.explain.why_not_eval import EVAL_TEXT, localise

NEEDED = [
    Path("reports/cr012/stop4_heldout_results.json"),
    Path("data/gold/pd_e2e_test_blind.csv"),
    Path("data/processed/kg/cr012_heldout_4_4_E0/checkpoint.json"),
    Path("data/processed/kg/cr012_scinlp_heldout_P17_1058_grobid_E0/checkpoint.json"),
]
pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in NEEDED), reason="frozen CR-012 outputs absent"
)


@pytest.fixture(scope="module")
def payload():
    from cumap.explain.eval_adapter import build_eval_payload

    return build_eval_payload()


def test_overlay_counts_equal_the_frozen_cr012_results_exactly(payload):
    fz = json.loads(Path("reports/cr012/stop4_heldout_results.json").read_text())
    for ds, frozen in (
        ("scinlp", fz["scinlp"]["levels"]["E0"]["attribution_pooled"]),
        ("pd", fz["pd"]["levels"]["E0"]["attribution_pooled"]),
    ):
        tot = Counter()
        for u in payload["datasets"][ds]["units"]:
            tot.update(u["counts"])
        assert {c: tot.get(c, 0) for c in payload["code_order"]} == frozen["by_code"]
        assert sum(u["recovered"] for u in payload["datasets"][ds]["units"]) == frozen["recovered"]
        assert payload["datasets"][ds]["frozen_attribution"] == frozen
    assert (
        sum(u["gold_n"] for u in payload["datasets"]["scinlp"]["units"]) == 295
        and sum(u["gold_n"] for u in payload["datasets"]["pd"]["units"]) == 432
    )


def test_headline_numbers_are_the_frozen_ones_and_datasets_are_never_pooled(payload):
    sc, pd_ = payload["datasets"]["scinlp"]["headline"], payload["datasets"]["pd"]["headline"]
    assert round(sc["f1"], 3) == 0.050 and sc["ci_status"] == "NOT_EVALUABLE_SMALL_N"
    assert round(pd_["f1"], 3) == 0.053 and "DESCRIPTIVE_SMALL_N" in pd_["ci_status"]
    assert (
        payload["meta"]["cr011"] == "NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION"
        and "pooled" not in json.dumps(payload["datasets"]).lower()
    )
    assert {u["id"] for u in payload["datasets"]["scinlp"]["units"]}.isdisjoint(
        {u["id"] for u in payload["datasets"]["pd"]["units"]}
    )


def test_per_relation_codes_equal_the_frozen_scinlp_attribution(payload):
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012.adapters import SciNLPAdapter
    from cumap.cr012.stop4_score import sc_attribution

    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    gold = ad.gold("test")
    for doc in ad.load_documents("test", paragraph_every=SR.PARAGRAPH_EVERY):
        rid = f"cr012_scinlp_heldout_{doc.doc_key.replace('.', '_').replace('-', '_')}_E0"
        cp = json.loads(Path(f"data/processed/kg/{rid}/checkpoint.json").read_text())
        expected = sc_attribution(doc, gold[doc.doc_key], SR.predict(doc, cp), cp, sym)
        unit = next(u for u in payload["datasets"]["scinlp"]["units"] if u["id"] == doc.doc_key)
        assert [r["code"] for r in unit["relations"]] == expected


FAIL = {
    "N0": ("ep_src", {"no"}),
    "N1": ("ep_src", {"partial span"}),
    "C1": ("merge", {"yes"}),
    "C0": ("split", {"yes"}),
    "P0": ("pair", {"no"}),
    "R0": ("classified", {"no relation"}),
    "R1": ("relation", {"no"}),
    "R2": ("direction", {"wrong"}),
    "R3": ("types", {"failed"}),
    "E0": ("evidence", {"invalid"}),
}


def test_each_relations_stage_checks_are_consistent_with_its_frozen_code(payload):
    for ds in payload["datasets"].values():
        for u in ds["units"]:
            for r in u["relations"]:
                ck = {k: v for k, v in r["checks"]}
                c = r["code"]
                if c is None:
                    assert (
                        ck["ep_src"] == ck["ep_tgt"] == "yes"
                        and ck["merge"] == "no"
                        and ck["pair"] == "yes"
                        and ck["classified"] != "no relation"
                        and ck["direction"] == "ok"
                        and ck["types"] == "ok"
                        and ck["evidence"] == "valid"
                    )
                    continue
                key, bad = FAIL[c]
                if c in ("N0", "N1"):
                    assert ck["ep_src"] in bad or ck["ep_tgt"] in bad
                else:
                    assert ck[key] in bad, (u["id"], r["i"], c, ck)
                    assert (
                        ck["ep_src"] == "yes" and ck["ep_tgt"] == "yes"
                    )  # no earlier node failure


def test_localisation_fixtures_attribute_to_the_intended_stage_and_have_frozen_wording():
    assert set(EVAL_TEXT) >= set(FROZEN_CODES)
    base = {"endpoints": ("A", "B"), "span_status": ("exact", "exact"), "false_merge": (False, False), "split": (False, False), "pairs_proposed": (True,), "no_relation": (False,), "predicted_relations": ("uses",), "gold_relation": "uses",
            "symmetric": False, "reversed_only": False, "types_ok": True, "qualifiers_ok": True, "evidence_valid": True}  # fmt: skip
    cases = {
        "N0": {"span_status": ("absent", "exact")}, "N1": {"span_status": ("exact", "partial")}, "C1": {"false_merge": (True, False)}, "C0": {"split": (True, False), "pairs_proposed": (False, False), "predicted_relations": ()},
        "P0": {"pairs_proposed": (False,), "predicted_relations": ()}, "R0": {"no_relation": (True,), "predicted_relations": ()}, "R1": {"predicted_relations": ("part_of",)}, "R2": {"reversed_only": True}, "R3": {"types_ok": False},
        "E0": {"evidence_valid": False}, None: {},
    }  # fmt: skip
    for code, change in cases.items():
        out = localise({**base, **change})
        assert out["code"] == code and "EVALUATION" in out["scope"]
        assert out["text"] == (
            EVAL_TEXT[code] if code else "The gold edge is present in the final graph."
        )


def test_only_the_evaluation_modules_read_gold_or_import_cr012():
    allowed = {"eval_adapter.py", "why_not_eval.py", "eval_report.py"}
    for f in Path("src/cumap/explain").glob("*.py"):
        src = f.read_text()
        touches = bool(
            re.search(
                r"^\s*(from|import)\s+cumap\.(cr012|explain\.why_not_eval|explain\.eval_adapter)|data/gold",
                src,
                flags=re.MULTILINE,
            )
        )
        assert touches == (f.name in allowed), f


def test_production_payload_is_free_of_the_overlay_and_any_gold():
    from cumap.explain.viewer_adapter import build_trace_payload

    text = json.dumps(build_trace_payload(), default=list).lower()
    for needle in (
        "gold",
        "frozen_commit",
        "cr012-stop4",
        "stop4_heldout",
        "earliest-failure",
        "strict_e2e",
        "scinlp",
    ):
        assert needle not in text, needle


def test_the_overlay_has_its_own_payload_and_production_javascript_never_references_it():
    trace_js = "\n".join(
        x
        for x in Path("src/cumap/report/kg_explorer_trace.js").read_text().splitlines()
        if not x.lstrip().startswith("//")
    )
    assert not re.search(r"\bEV\b|\bES\b|eval-gz|loadEval|evDetail|datasets\b", trace_js)
    page = Path("src/cumap/report/kg_explorer.html").read_text()
    uses = [
        m.start()
        for m in re.finditer(
            r"\b(evEnter|evSide|evBanner|renderEvalTab|evDetailHTML|wireEvDetail|EV_TABS|EV_PANES)\b",
            page,
        )
    ]
    assert uses and all(
        ("S.mode==='ev'" in page[max(0, i - 240) : i + 120])
        or ("m==='ev'" in page[max(0, i - 120) : i + 120])
        or ("EV_" in page[i : i + 8])
        or ("onclick" in page[max(0, i - 40) : i + 60])
        or ("EV_PANES.includes" in page[max(0, i - 40) : i + 60])
        for i in uses
    )
