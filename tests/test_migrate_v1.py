"""CR-001 §6 acceptance tests: gold migration tool."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
import yaml

from cumap.gold.migrate_v1 import (
    migrate_expert_pilot_file,
    migrate_student_pilot_file,
    run_migration,
    write_migration_report,
    write_migrations,
)
from cumap.gold.validate import ValidationResult
from cumap.schemas.relations import RelationRegistry

V1_PATH = Path(__file__).parents[1] / "configs" / "relations_v1.yaml"


@pytest.fixture(scope="module")
def registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(V1_PATH)


@pytest.fixture
def expert_gold_dir(tmp_path) -> Path:
    gold_dir = tmp_path / "gold"
    expert_dir = gold_dir / "expert_pilot"
    expert_dir.mkdir(parents=True)
    (expert_dir / "q_1.yaml").write_text(
        yaml.safe_dump(
            {
                "concepts": [
                    {"concept_id": "c_ext_header", "canonical_name": "extension header", "node_type": "Component", "aliases": [], "mentions": [], "status": "candidate", "confidence": 1.0, "validation": {}, "version": 1},
                    {"concept_id": "c_ipv6_packet", "canonical_name": "IPv6 packet", "node_type": "DataUnit", "aliases": [], "mentions": [], "status": "candidate", "confidence": 1.0, "validation": {}, "version": 1},
                    {"concept_id": "c_learning", "canonical_name": "backward learning", "node_type": "Mechanism", "aliases": [], "mentions": [], "status": "candidate", "confidence": 1.0, "validation": {}, "version": 1},
                    {"concept_id": "c_bridge", "canonical_name": "transparent bridge", "node_type": "Component", "aliases": [], "mentions": [], "status": "candidate", "confidence": 1.0, "validation": {}, "version": 1},
                    {"concept_id": "c_carrier_ext", "canonical_name": "carrier extension", "node_type": "Mechanism", "aliases": [], "mentions": [], "status": "candidate", "confidence": 1.0, "validation": {}, "version": 1},
                    {"concept_id": "c_reliability", "canonical_name": "reliable collision detection", "node_type": "Property", "aliases": [], "mentions": [], "status": "candidate", "confidence": 1.0, "validation": {}, "version": 1},
                ],
                "edges": [
                    {
                        "edge_id": "E-1", "source_id": "c_ext_header", "target_id": "c_ipv6_packet",
                        "relation": "part_of", "layer": "taxonomy", "statement": "x", "criticality": "core",
                        "evidence": [], "validation": {}, "origin": "textbook",
                    },
                    {
                        "edge_id": "E-2", "source_id": "c_bridge", "target_id": "c_learning",
                        "relation": "uses", "layer": "semantic", "statement": "the bridge uses backward learning",
                        "criticality": "core", "evidence": [], "validation": {}, "origin": "textbook",
                    },
                    {
                        "edge_id": "E-3", "source_id": "c_carrier_ext", "target_id": "c_reliability",
                        "relation": "has_property", "layer": "semantic",
                        "statement": "carrier extension exists in order to achieve reliable collision detection",
                        "criticality": "core", "evidence": [], "validation": {}, "origin": "textbook",
                    },
                    {
                        "edge_id": "E-4", "source_id": "c_bridge", "target_id": "c_learning",
                        "relation": "triggers", "layer": "semantic", "statement": "a timeout triggers learning",
                        "criticality": "core", "chain_id": "CH-1", "chain_position": 1,
                        "evidence": [], "validation": {}, "origin": "textbook",
                    },
                    {
                        "edge_id": "E-5", "source_id": "c_learning", "target_id": "c_bridge",
                        "relation": "causes", "layer": "semantic", "statement": "because the table is updated",
                        "criticality": "core", "chain_id": "CH-1", "chain_position": 2,
                        "evidence": [], "validation": {}, "origin": "textbook",
                    },
                ],
            }
        )
    )
    return gold_dir


def test_migrate_expert_file_adds_registry_version_and_relation_family(expert_gold_dir, tmp_path, registry):
    path = expert_gold_dir / "expert_pilot" / "q_1.yaml"
    migration = migrate_expert_pilot_file(path, tmp_path / "out.yaml", registry)

    assert migration.data["registry_version"] == 1
    for edge in migration.data["edges"]:
        assert edge["relation_family"] == registry.family_of(edge["relation"])
    assert migration.n_automatic_changes >= len(migration.data["edges"])  # at least one relation_family per edge


def test_migrate_expert_file_suggests_part_type_for_part_of(expert_gold_dir, tmp_path, registry):
    path = expert_gold_dir / "expert_pilot" / "q_1.yaml"
    migration = migrate_expert_pilot_file(path, tmp_path / "out.yaml", registry)

    part_type_suggestions = [s for s in migration.suggestions if s.field == "part_type"]
    assert len(part_type_suggestions) == 1
    assert part_type_suggestions[0].edge_id == "E-1"
    # target is a DataUnit, not Mechanism/State or collection-like -> component
    assert part_type_suggestions[0].suggested == "component"

    e1 = next(e for e in migration.data["edges"] if e["edge_id"] == "E-1")
    assert e1.get("part_type") is None  # NOT silently applied
    assert "component" in e1["_suggested_part_type"]


def test_migrate_expert_file_suggests_has_purpose(expert_gold_dir, tmp_path, registry):
    path = expert_gold_dir / "expert_pilot" / "q_1.yaml"
    migration = migrate_expert_pilot_file(path, tmp_path / "out.yaml", registry)

    relation_suggestions = {s.edge_id: s for s in migration.suggestions if s.field == "relation"}
    assert relation_suggestions["E-3"].suggested == "has_purpose"


def test_migrate_expert_file_suggests_performs(expert_gold_dir, tmp_path, registry):
    path = expert_gold_dir / "expert_pilot" / "q_1.yaml"
    migration = migrate_expert_pilot_file(path, tmp_path / "out.yaml", registry)

    relation_suggestions = {s.edge_id: s for s in migration.suggestions if s.field == "relation"}
    assert relation_suggestions["E-2"].suggested == "performs"  # target "backward learning" looks like an activity


def test_migrate_expert_file_suggests_chain_links(expert_gold_dir, tmp_path, registry):
    path = expert_gold_dir / "expert_pilot" / "q_1.yaml"
    migration = migrate_expert_pilot_file(path, tmp_path / "out.yaml", registry)

    chain_link_suggestions = [s for s in migration.suggestions if s.field == "chain_link"]
    assert len(chain_link_suggestions) == 1
    assert migration.data["chain_links"][0]["from_edge_id"] == "E-5"
    assert migration.data["chain_links"][0]["to_edge_id"] == "E-4"
    assert migration.data["chain_links"][0]["type"] == "cause"  # "because" cue in E-5's statement


def test_migrate_student_file_autofills_surface_phrase_and_relation_family(tmp_path, registry):
    gold_dir = tmp_path / "gold"
    student_dir = gold_dir / "student_pilot"
    student_dir.mkdir(parents=True)
    path = student_dir / "a_1.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "edges": [
                    {
                        "source_id": "c_a", "relation": "causes", "target_id": "c_b",
                        "response_id": "a_1", "question_id": "q_1",
                        "evidence_span": {"start": 0, "end": 10, "text": "A causes B"},
                        "extraction_confidence": 0.9, "link_confidence": 0.9,
                    }
                ]
            }
        )
    )
    migration = migrate_student_pilot_file(path, tmp_path / "out.yaml", registry)
    edge = migration.data["edges"][0]
    assert edge["relation_family"] == "cause_effect"
    assert "A causes B" in edge["surface_phrase"]
    assert "auto: check" in edge["surface_phrase"]
    assert migration.n_automatic_changes >= 2


def test_write_migrations_never_writes_to_gold_dir(expert_gold_dir, tmp_path, registry):
    """CR-001 §6.2: point gold at a read-only directory; migration must not attempt a write there."""
    out_dir = tmp_path / "suggestions_out"
    migrations = run_migration(expert_gold_dir, out_dir, registry)

    gold_expert_dir = expert_gold_dir / "expert_pilot"
    original_mode = gold_expert_dir.stat().st_mode
    os.chmod(gold_expert_dir, stat.S_IREAD | stat.S_IEXEC)
    try:
        write_migrations(migrations)  # must not raise PermissionError
    finally:
        os.chmod(gold_expert_dir, original_mode)

    assert list(gold_expert_dir.glob("*")) == [gold_expert_dir / "q_1.yaml"]  # nothing added
    assert (out_dir / "expert_pilot" / "q_1.yaml").exists()  # proposed file landed in data/interim, not data/gold


def test_migration_report_lists_suggestions_and_automatic_counts(expert_gold_dir, tmp_path, registry):
    migrations = run_migration(expert_gold_dir, tmp_path / "out", registry)
    empty_validation = ValidationResult(issues=[], hints=[])
    report_path = write_migration_report(migrations, empty_validation, tmp_path / "migration_v1.md")

    text = report_path.read_text()
    assert "q_1.yaml" in text
    assert "E-1" in text  # part_type suggestion
    assert "has_purpose" in text
    assert "performs" in text


def test_migration_report_handles_no_gold_files_yet(tmp_path, registry):
    migrations = run_migration(tmp_path / "empty_gold", tmp_path / "out", registry)
    empty_validation = ValidationResult(issues=[], hints=[])
    report_path = write_migration_report(migrations, empty_validation, tmp_path / "migration_v1.md")
    assert "No `data/gold/" in report_path.read_text()
