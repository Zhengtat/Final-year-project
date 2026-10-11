"""CR-013 STOP 3: the extended KG explorer. Builds the page into a temp file, runs its script in Node against a stubbed DOM and checks: text parity with the
Python renderer for every trace event, Why-not parity with the Python localiser, every new tab renders in Review and Debug, journeys, dataset switch, gold isolation,
offline resources and keyboard / reduced-motion support. Skipped when the derived trace, the node binary or the source runs are absent."""

import base64
import gzip
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from cumap.explain.trace import TraceStore
from cumap.explain.viewer_adapter import latest
from cumap.explain.why_not import pair_index, why_not

D = latest("slice3_c2")
pytestmark = pytest.mark.skipif(
    D is None
    or shutil.which("node") is None
    or not Path(
        "data/processed/kg/cr012_scinlp_heldout_P17_1058_grobid_E0/checkpoint.json"
    ).exists(),
    reason="derived trace, node or source runs absent",
)


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    from cumap.report.kg_explorer import build

    root = tmp_path_factory.mktemp("explorer")
    html = build(root / "index.html")
    store = TraceStore.from_jsonl(D / "trace_events.jsonl")
    idx = pair_index(store)
    payload_pairs = [tuple(sorted(k)) for k in list(idx)[::37]]
    finals = sorted(
        o
        for o in store.by_object
        if o.startswith("concept:")
        and any(e.action == "commit_node" for e in store.for_object(o, "graph_commit"))
    )
    probes = [(a, b) for a, b in payload_pairs[:150]]
    probes += [(finals[i], "concept:c_missing_concept") for i in range(20)]  # N0
    probes += [(finals[i], finals[i + 301]) for i in range(60)]  # mostly outside the eligible pool
    pairs_js = [[a[8:], b[8:]] for a, b in probes]
    pj = root / "pairs.json"
    pj.write_text(json.dumps(pairs_js))
    out = root / "out.json"
    subprocess.run(
        ["node", "tests/js/explorer_harness.js", str(html), str(pj), str(out)],
        check=True,
        timeout=600,
    )
    res = json.loads(out.read_text())
    return html, res, store, idx, probes


def test_explorer_script_runs_without_errors_and_every_new_tab_renders_in_both_views(page):
    _, res, *_ = page
    assert "fatal" not in res and res["errors"] == []
    for view in ("review", "debug"):
        for sid in ("3.3", "1.2", "2.6"):
            for tab in ("pipeline", "section", "why", "lost", "snap") + (
                ("trace",) if view == "debug" else ()
            ):
                assert res["ui"][f"{view}|{sid}|{tab}"] > 200, (view, sid, tab)
    assert (
        res["counts"]["events"] == 19522
        and res["counts"]["pool"] == 8604
        and res["counts"]["journeys"] == 1771
    )


def test_javascript_text_equals_the_python_renderer_for_every_trace_event(page):
    _, res, *_ = page
    expected = {}
    for line in (D / "explanation_index.jsonl").read_text().splitlines():
        r = json.loads(line)
        expected[r["event_id"]] = r["text"]
    assert set(expected) == set(res["texts"])
    bad = [k for k in expected if expected[k] != res["texts"][k]]
    assert not bad, (len(bad), bad[:3], expected[bad[0]][:200], res["texts"][bad[0]][:200])


def test_javascript_why_not_equals_the_python_localiser(page):
    _, res, store, idx, probes = page
    assert len(res["why"]) == len(probes)
    kinds = set()
    for js, (a, b) in zip(res["why"], probes, strict=True):
        py = why_not(store, a, b, idx)
        kinds.add(py["earliest_failure"])
        assert js["code"] == (py["earliest_failure"] or "") and js["status"] == py["status"], (a, b)
        assert js["sentences"] == py["sentences"], (a, b, js["sentences"], py["sentences"])
        assert [c[0] for c in js["checks"]] == [c["id"] for c in py["checks"]] and [
            c[1] for c in js["checks"]
        ] == [c["answer"] for c in py["checks"]]
    assert {"N0", "P0"} <= kinds


def test_journeys_show_stage_events_with_authority_and_replayed_labels(page):
    _, res, *_ = page
    j = res["journey_edge_review"]
    for needle in (
        "Pair ranking + budget",
        "Relation classification",
        "Validation",
        "Graph commit",
        "REPLAYED",
        "RULE",
        "MODEL",
        "Source evidence",
        "Not recorded for this run",
    ):
        assert needle in j, needle
    assert "trace fields" in res["journey_edge_debug"] and "trace fields" not in j
    assert "Concept generator" in res["journey_node_review"]


def test_dataset_switch_hides_trace_tabs_for_scinlp_and_restores_them_for_pd(page):
    _, res, *_ = page
    assert (
        res["sci_trace_available"] is False
        and "Pipeline" not in res["sci_tabs"]
        and "Document" in res["sci_tabs"]
    )
    assert "Pipeline" in res["pd_tabs_after"] and "Why not?" in res["pd_tabs_after"]


def test_production_payload_contains_no_gold_scorer_or_scinlp_data(page):
    html, *_ = page
    text = Path(html).read_text(encoding="utf-8")
    b64 = re.search(r'id="trace-gz">([^<]*)</script>', text).group(1)
    payload = gzip.decompress(base64.b64decode(b64)).decode()
    for needle in ("data/gold", "cr012", "stop4", "gold_", "scinlp", "STRICT_E2E"):
        assert needle.lower() not in payload.lower(), needle
    code_lines = [
        x
        for x in Path("src/cumap/report/kg_explorer_trace.js").read_text().splitlines()
        if not x.lstrip().startswith("//")
    ]
    assert not re.search(
        r"gold|cr012|stop4|scinlp", "\n".join(code_lines), flags=re.IGNORECASE
    )  # the trace layer code never touches evaluation data


def test_page_is_offline_keyboard_navigable_and_respects_reduced_motion(page):
    html, *_ = page
    text = Path(html).read_text(encoding="utf-8")
    assert not re.search(r'(src|href)="https?://', text)
    js = Path("src/cumap/report/kg_explorer_trace.js").read_text()
    assert 'role="tablist"' in js and js.count("ArrowRight") >= 2 and js.count("ArrowLeft") >= 2
    assert "prefers-reduced-motion" in text and "REDUCED" in text
    for marker in (
        'id="m-pd"',
        'id="m-sci"',
        'id="v-review"',
        'id="v-debug"',
        "f-q",
        "Fit to screen",
        "label every concept",
    ):
        assert marker in text


def test_existing_explorer_views_remain(page):
    html, *_ = page
    text = Path(html).read_text(encoding="utf-8")
    for marker in (
        "Guided views",
        "Sphere",
        "renderDoc",
        "renderTables",
        "function detNode",
        "function detEdge",
    ):
        assert marker in text or marker.lower() in text.lower()
