"""CR-040 DRAFT: the v1.4 wording review sheet is generated, complete, and changes no config."""

import hashlib
from pathlib import Path

import yaml

from cumap.config import get_settings
from cumap.cr040 import review_sheet as RS
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
SIX = {"subtask_of", "enhanced_by", "measured_by", "evaluated_by", "evaluated_on", "similar_to"}


def _load():
    return yaml.safe_load(RS.V14.read_text(encoding="utf-8")), yaml.safe_load(
        RS.PROPOSALS.read_text(encoding="utf-8")
    )


def test_proposals_cover_exactly_the_six_relations_and_every_change_has_a_reason():
    reg, prop = _load()
    assert set(prop["relations"]) == SIX == set(RS.ORDER)
    by = {r["name"]: r for r in reg["relations"]}
    for name, p in prop["relations"].items():
        for f in RS.FIELDS:
            assert f in p and p.get(f + "_reason"), (
                name,
                f,
            )  # a proposal and a reason for every field, even when unchanged
        assert p["examples"] and all(isinstance(e, str) for e in p["examples"])
        for nm in p["near_misses"]:
            assert nm["relation"] in by or nm["relation"] == "same_concept", (
                name,
                nm["relation"],
            )  # same_concept is a choice, not a relation
            assert nm["relation"] != name and nm["example"] and nm["why"]


def test_the_sheet_shows_the_current_v14_text_exactly_and_is_in_sync_with_the_committed_file():
    reg, prop = _load()
    sha = hashlib.sha256(RS.V14.read_bytes()).hexdigest()
    text = RS.render(reg, prop, sha)
    for r in reg["relations"]:
        if r["name"] in SIX:
            assert " ".join(r["definition"].split()) in text.replace("\\|", "|")
    assert text == RS.OUT.read_text(encoding="utf-8"), (
        "run: uv run python -m cumap.cr040.review_sheet"
    )
    assert "Nothing here is adopted" in text and text.count("Owner checklist") == 6


def test_generating_the_sheet_never_edits_registry_v14_and_v14_is_not_the_default():
    before = hashlib.sha256(RS.V14.read_bytes()).hexdigest()
    RS.main()
    assert hashlib.sha256(RS.V14.read_bytes()).hexdigest() == before
    assert RelationRegistry.from_yaml(RS.V14).version_label == "1.4"
    assert "relations_v1.4" not in str(get_settings().relation_registry)
