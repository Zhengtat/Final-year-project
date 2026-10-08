"""CR-010 P3: the eRST-compatible graph builder (windows, closed-label schema, code-side verification, resume, freeze).
No network, no key: the mock backend reads tests/fixtures/llm/erst_graph/."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from cumap.erst import graph as G
from cumap.erst.registry import ErstRegistry

REG = ErstRegistry.load()


def win(
    units=("Buffers overflow.", "Packets are lost because buffers overflow.", "Then we resend."),
    first=0,
):
    return G.Window("s@0", "s", "Heading", first, tuple(units))


def raw(**kw):
    base = {
        "label": "CAUSAL-CAUSE",
        "nucleus_units": ["U1"],
        "satellite_unit": "U0",
        "satellite_position": "before",
        "evidence": "Packets are lost because buffers overflow.",
        "signals": [{"kind": "discourse_marker", "subtype": None, "anchor_text": "because"}],
        "confidence": 0.9,
    }
    return {**base, **kw}


def test_windows_cover_every_sentence_with_overlap_and_stable_ids():
    secs = [
        SimpleNamespace(
            section_id="a", heading_path=["h"], text=" ".join(f"Sentence {i}." for i in range(70))
        )
    ]
    ws = G.make_windows(secs)
    assert ws[0].first == 0 and len(ws[0].units) == 30 and ws[1].first == 25
    assert {w.first + i for w in ws for i in range(len(w.units))} == set(range(70))
    assert ws[-1].last == 69 and [w.window_id for w in ws] == ["a@0", "a@25", "a@50"]


def test_schema_label_is_a_closed_enum_of_the_discourse_relations():
    schema = G.build_schema(REG)
    ok = {"edges": [raw()]}
    assert schema.model_validate(ok)
    with pytest.raises(ValidationError):
        schema.model_validate({"edges": [raw(label="SAME-UNIT")]})  # technical, not a choice
    with pytest.raises(ValidationError):
        schema.model_validate({"edges": [raw(label="MADE-UP")]})
    with pytest.raises(ValidationError):
        schema.model_validate({"edges": [{**raw(), "extra": 1}]})


def test_a_valid_edge_converts_and_keeps_its_signal():
    rec, why = G.convert(raw(), win(), REG)
    assert why is None and rec["edge"]["label"] == "CAUSAL-CAUSE"
    assert rec["edge"]["signals"][0]["anchor_text"] == "because" and rec["signals_dropped"] == 0


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"evidence": "Packets vanish because of overflow."}, "evidence_not_in_units"),
        ({"nucleus_units": ["U9"]}, "unit_not_in_window"),
        ({"satellite_position": "after"}, "position_mismatch"),
        ({"satellite_unit": "U1"}, "repeated_unit"),
        ({"label": "CONTRAST-X"}, None),
    ],
)
def test_bad_edges_are_rejected_with_a_reason(change, reason):
    rec, why = G.convert(raw(**change), win(), REG)
    if reason is None:
        return  # unknown labels never reach convert: the schema is closed (tested above)
    assert rec is None and why == reason


def test_nuclearity_rules_from_the_inventory_still_apply():
    multi = raw(
        label="ADVERSATIVE-CONTRAST",
        nucleus_units=["U0"],
        satellite_unit="U1",
        satellite_position="after",
        evidence="Buffers overflow. Packets are lost because buffers overflow.",
    )
    rec, why = G.convert(multi, win(), REG)  # multinuclear: no satellite allowed
    assert rec is None and why.startswith("schema:")


def test_a_signal_with_an_anchor_outside_the_text_is_dropped_not_the_edge():
    rec, _ = G.convert(
        raw(signals=[{"kind": "discourse_marker", "subtype": None, "anchor_text": "hence"}]),
        win(),
        REG,
    )
    assert rec["edge"]["signals"] == [] and rec["signals_dropped"] == 1


def test_unit_pairs_for_satellite_and_multinuclear_edges():
    assert G.unit_pairs({"nucleus_units": ["U1"], "satellite_unit": "U0"}) == [(1, 0)]
    assert G.unit_pairs({"nucleus_units": ["U1", "U2", "U3"], "satellite_unit": None}) == [
        (1, 2),
        (1, 3),
        (2, 3),
    ]


def test_the_prompt_lists_every_discourse_label_and_no_technical_one():
    from cumap.config import REPO_ROOT
    from cumap.llm.prompts import load_prompt

    text = G.render(load_prompt(REPO_ROOT / "prompts", "erst_graph", "v1"), REG, win())
    assert all(lab in text for lab in REG.discourse_labels) and "SAME-UNIT" not in text
    assert text.index("Relation inventory") < text.index(
        "[U0]"
    )  # static content first, window last
