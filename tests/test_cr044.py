"""CR-044: term lexicon v0.5 = v0.4 + the owner's ruling on intake row 10 (no network, no key)."""

from pathlib import Path

import yaml

from cumap.expert_kg.lexicon import Lexicon, production_lexicon_path


def test_production_lexicon_is_v05_and_row10_is_same():
    p = production_lexicon_path()
    assert p.name == "term_lexicon_v0.5.yaml"
    lx = Lexicon.load(p)
    assert {"data link protocol", "link-level protocol", "link-layer protocol"} <= lx.same_forms(
        "data link protocol"
    )
    assert not lx.is_different("data link protocol", "link-level protocol")


def test_v05_only_adds_the_row10_entry_to_v04():
    v4 = yaml.safe_load(Path("configs/term_lexicon_v0.4.yaml").read_text())
    v5 = yaml.safe_load(Path("configs/term_lexicon_v0.5.yaml").read_text())
    assert v5["different"] == v4["different"]
    assert v5["same"][: len(v4["same"])] == v4["same"]
    assert [e["id"] for e in v5["same"][len(v4["same"]) :]] == ["S-lexicon_intake_slice3_c2-10"]
