"""Sphere figures and payload (CR-006 §10) on the synthetic organisation run."""

import json
import re
from pathlib import Path

import pytest
from test_org_pipeline import REPO, _run, cfg_fast, world  # noqa: F401  (fixture import)

from cumap.organisation.inputs import load_inputs
from cumap.report import sphere as S
from cumap.report.provenance import LABEL_SOURCES, Provenance
from cumap.report.svg import hbar_svg
from cumap.schemas.relations import RelationRegistry

PROV = Provenance(
    run_id="kg_fixture",
    prompt_versions={"organise": "org_x"},
    model_tier="none",
    model="graph",
    date="2026-01-01",
)
TAG_TEXT = "Structural metric (no human labels)"


@pytest.fixture
def scene(world):  # noqa: F811
    run_dir, sections, _ = world
    org_run = _run(world)
    reg = RelationRegistry.from_yaml(REPO / "configs/relations_v1.yaml")
    cfg = cfg_fast()
    inp = load_inputs(run_dir, sections, reg, cfg)
    return S.load_org(org_run.org_dir), inp, cfg


def test_new_label_tags_are_allowed_and_missing_or_unknown_still_raise():
    assert LABEL_SOURCES["structural_metric"] == TAG_TEXT
    assert LABEL_SOURCES["owner_importance_check"] == "Owner importance check (n=40)"
    assert TAG_TEXT in hbar_svg(
        "t", [("a", 1.0, 0)], provenance=PROV, label_source="structural_metric"
    )
    with pytest.raises(TypeError):
        hbar_svg("t", [("a", 1.0, 0)], provenance=PROV)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        hbar_svg("t", [("a", 1.0, 0)], provenance=PROV, label_source="structural")


def test_every_sphere_figure_carries_provenance_and_the_structural_tag(scene):
    org, inp, cfg = scene
    figs = {
        "sphere0": S.sphere_svg(org, inp, 0, cfg, PROV),
        "sphere2": S.sphere_svg(org, inp, 2, cfg, PROV),
        "sphere3": S.sphere_svg(org, inp, 3, cfg, PROV),
        "top3": S.topk_svg(org, 3, PROV),
        "rings": S.ring_composition_svg(org, 3, PROV),
        "stab": S.stability_svg(org, PROV),
        "cp": S.cp_fit_svg(org, PROV),
        "events": S.events_svg(org, PROV),
        "traj": S.trajectory_svg(org, ["H", "a1", "b1"], PROV),
    }
    for name, svg in figs.items():
        assert svg and TAG_TEXT in svg and "run kg_fixture" in svg, name
        assert "http://" not in svg.replace("http://www.w3.org/2000/svg", ""), name


def test_start_view_is_the_book_only_and_states_the_unlinked_count(scene):
    org, inp, cfg = scene
    start = S.sphere_svg(org, inp, 0, cfg, PROV)
    assert S.BOOK in start and "a virtual centre label, not a knowledge-graph node" in start
    assert "<title>H " not in start  # no concept nodes at the start
    s3 = org.summary(3)
    assert (
        S.unlinked_text(org, 3)
        == f"{s3['n_unlinked']} of {s3['n_nodes']} concepts have no typed edge yet: see relation recall."
    )
    assert S.unlinked_text(org, 3) in S.sphere_svg(org, inp, 3, cfg, PROV)


def test_no_clear_core_banner_is_drawn_when_the_null_check_fails(scene):
    org, inp, cfg = scene
    org.manifest["chapters"]["3"]["core_periphery"]["banner"] = (
        "No clear core at this chapter: ring positions are weakly supported."
    )
    assert "No clear core at this chapter" in S.sphere_svg(org, inp, 3, cfg, PROV)
    org.manifest["chapters"]["3"]["core_periphery"]["banner"] = None
    assert "No clear core" not in S.sphere_svg(org, inp, 3, cfg, PROV)


def test_cp_chart_draws_the_ba_reference_range_without_changing_the_threshold(scene):
    org, _, _ = scene
    svg = S.cp_fit_svg(org, PROV)
    assert "hub-heavy random graph (Δρ 0.08 to 0.14)" in svg and "Δρ ≥ 0.10 = present" in svg
    assert S.BA_REFERENCE_DELTA_RHO == (0.08, 0.14)


def test_payload_is_compact_json_with_events_that_name_their_edges(scene):
    org, inp, cfg = scene
    p = S.sphere_payload(org, inp, cfg)
    json.dumps(p)
    assert p["chapters"] == [0, 2, 3] and p["book"] == S.BOOK and p["tag"] == TAG_TEXT
    assert set(p["sph"]["H"]) == {"2", "3"} and len(p["sph"]["H"]["3"]) == 15
    assert p["counts"]["3"]["unlinked_text"] == S.unlinked_text(org, 3)
    moved = [
        e
        for evs in p["why"].get("3", {}).values()
        for e in evs
        if e["type"] in ("ring_in", "ring_out")
    ]
    assert all(e["edges"] for e in moved if e["type"] == "ring_in") or not moved
    assert re.match(
        r"^\d+ of \d+ concepts have no typed edge yet", p["counts"]["3"]["unlinked_text"]
    )
    assert isinstance(p["edge_chapter"]["E11"], int) and "late_note" in p and Path(REPO).exists()


def _page(scene, with_sphere=True):
    from cumap.report.graph3d import growth3d_page
    from cumap.report.svg import theme_css

    org, inp, cfg = scene
    data = {
        "radius": 100.0,
        "topn": 100,
        "labelTop": 30,
        "nodes": [],
        "edges": [],
        "concepts": {},
        "steps": [{"caption": "2.1 A", "chapter": 2, "mentioned": [], "merges": 0}],
        "secCaption": {},
        "families": [],
        "chapters": [{"ch": 2, "slot": 0}, {"ch": 3, "slot": 1}],
    }
    if with_sphere:
        data["sphere"] = S.sphere_payload(org, inp, cfg)
    return growth3d_page(data, css=theme_css(":root"), banner="b", footer="f · g", top_n=100)


def test_interactive_page_has_a_sphere_mode_with_the_required_controls_and_labels(scene):
    html = _page(scene)
    for needle in (
        'id="v4"',
        'id="chbar"',
        'id="rawrad"',
        'id="showouter"',
        'id="showband"',
        'id="crossonly"',
        'id="unl"',
        'id="cpbanner"',
        'id="tip"',
        TAG_TEXT,
        "not tiers",
        "CR-007",
    ):
        assert needle in html, needle
    assert not re.search(r'(?:src|href)\s*=\s*["\']?(?:https?:)?//', html)
    assert re.findall(r"<script[^>]*>", html) == [
        '<script type="application/json" id="d3d">',
        "<script>",
    ]
    payload = json.loads(re.search(r'id="d3d">(.*?)</script>', html, re.DOTALL).group(1))
    assert payload["sphere"]["visible_rings"] == [
        "centre",
        "inner",
        "middle",
    ]  # default view = the rings


def test_page_without_an_organisation_run_has_no_sphere_button(scene):
    html = _page(scene, with_sphere=False)
    assert 'id="v4"' not in html and 'id="chbar"' not in html and "--segs:2" in html
