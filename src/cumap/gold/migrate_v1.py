"""`cumap gold migrate-v1`: proposes v1-migrated copies of every data/gold/ file
(CR-001 §6). Read-only towards data/gold/ — writes only to
data/interim/suggestions/migrations/v1/<same relative path> and reports/migration_v1.md.
The human reviews, edits and copies the results into data/gold/ themselves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

import yaml

from cumap.gold.validate import ValidationResult
from cumap.schemas.relations import RelationRegistry

_PURPOSE_CUES = ["in order to", "so that", "to ensure", "to avoid", "purpose", "used to"]
_COLLECTION_NAME_HINTS = ["network", "domain", "group", "collection", "set of"]


@dataclass
class Suggestion:
    file: str
    edge_id: str
    field: str
    current: str
    suggested: str
    reason: str


@dataclass
class FileMigration:
    source_path: Path
    out_path: Path
    data: dict  # the proposed v1 dict, ready to yaml.safe_dump
    n_automatic_changes: int
    suggestions: list[Suggestion] = field(default_factory=list)


def _looks_like_activity(name: str) -> bool:
    return name.strip().lower().endswith("ing") or bool(re.match(r"^(perform|execute|run|send|receive|forward|learn|compute)", name.strip().lower()))


def _part_type_suggestion(target_node_type: str | None, target_name: str) -> str:
    if target_node_type in ("Mechanism", "State"):
        return "phase"
    if any(hint in target_name.lower() for hint in _COLLECTION_NAME_HINTS):
        return "member"
    return "component"


def _guess_chain_link_type(text: str, registry: RelationRegistry) -> str:
    text_lower = text.lower()
    for link_type in registry.chain_link_types.values():
        for cue in link_type.cues:
            if cue in text_lower:
                return link_type.name
    return "sequence"


def migrate_expert_pilot_file(path: Path, out_path: Path, registry: RelationRegistry) -> FileMigration:
    data = yaml.safe_load(path.read_text()) or {}
    concepts = data.get("concepts", [])
    edges = data.get("edges", [])
    concept_types = {c["concept_id"]: c.get("node_type") for c in concepts}
    concept_names = {c["concept_id"]: c.get("canonical_name", "") for c in concepts}

    suggestions: list[Suggestion] = []
    n_automatic = 0

    for edge in edges:
        relation = edge.get("relation")
        if relation not in registry:
            continue

        # Automatic: derive relation_family.
        family = registry.family_of(relation)
        if edge.get("relation_family") != family:
            edge["relation_family"] = family
            n_automatic += 1

        # Suggested (flagged only, NOT applied to the real field — schemas are extra="forbid"
        # and part_type/relation stay valid/unset in the proposed file; a "_suggested_*"
        # sibling key carries the proposal so the human sees it without the file becoming
        # invalid YAML-as-data. The report table is the primary place these are reviewed.)
        if relation == "part_of" and not edge.get("part_type"):
            target_name = concept_names.get(edge["target_id"], edge["target_id"])
            suggested = _part_type_suggestion(concept_types.get(edge["target_id"]), target_name)
            suggestions.append(
                Suggestion(str(path), edge["edge_id"], "part_type", "(none)", suggested, f"target {target_name!r} -> {suggested}")
            )
            edge["_suggested_part_type"] = f"{suggested} — SUGGESTED: confirm"

        # Suggested: has_property/uses with purpose cues -> has_purpose.
        if relation in ("has_property", "uses"):
            statement_lower = edge.get("statement", "").lower()
            cue = next((c for c in _PURPOSE_CUES if c in statement_lower), None)
            if cue:
                suggestions.append(
                    Suggestion(str(path), edge["edge_id"], "relation", relation, "has_purpose", f"purpose cue {cue!r} in statement")
                )
                edge["_suggested_relation"] = f"has_purpose — SUGGESTED: confirm (cue: {cue!r})"

        # Suggested: uses -> performs, when the target looks like an activity.
        if relation == "uses":
            target_name = concept_names.get(edge["target_id"], "")
            if _looks_like_activity(target_name):
                suggestions.append(
                    Suggestion(str(path), edge["edge_id"], "relation", "uses", "performs", f"target {target_name!r} looks like an activity")
                )
                edge["_suggested_relation"] = f"performs — SUGGESTED: confirm (target {target_name!r} looks like an activity)"

    # Suggested: consecutive same-chain_id edges -> ChainLinks.
    by_chain: dict[str, list[dict]] = {}
    for edge in edges:
        if edge.get("chain_id"):
            by_chain.setdefault(edge["chain_id"], []).append(edge)
    proposed_chain_links = []
    for chain_id, chain_edges in by_chain.items():
        chain_edges = sorted(chain_edges, key=lambda e: e.get("chain_position") or 0)
        for a, b in pairwise(chain_edges):
            combined_text = f"{a.get('statement', '')} {b.get('statement', '')}"
            link_type = _guess_chain_link_type(combined_text, registry)
            link_id = f"CL-{chain_id}-{a['edge_id']}-{b['edge_id']}"
            proposed_chain_links.append(
                {
                    "link_id": link_id,
                    "from_edge_id": b["edge_id"],  # b is supported by a (a happened first)
                    "to_edge_id": a["edge_id"],
                    "type": link_type,  # a valid ChainLinkType value; SUGGESTED — see the report table
                    "statement": f"SUGGESTED: confirm the reasoning between {a['edge_id']} and {b['edge_id']}",
                    "origin": "textbook",
                }
            )
            suggestions.append(
                Suggestion(str(path), link_id, "chain_link", "(none)", link_type, f"consecutive edges in chain {chain_id!r}")
            )

    data["registry_version"] = 1
    if proposed_chain_links:
        data["chain_links"] = data.get("chain_links", []) + proposed_chain_links

    return FileMigration(path, out_path, data, n_automatic, suggestions)


def migrate_student_pilot_file(path: Path, out_path: Path, registry: RelationRegistry) -> FileMigration:
    data = yaml.safe_load(path.read_text()) or {}
    edges = data.get("edges", [])

    suggestions: list[Suggestion] = []
    n_automatic = 0

    for i, edge in enumerate(edges):
        relation = edge.get("relation")
        if relation in registry:
            family = registry.family_of(relation)
            if edge.get("relation_family") != family:
                edge["relation_family"] = family
                n_automatic += 1

        if not edge.get("surface_phrase"):
            # Automatic, safe: pre-fill from the evidence span text; mark for a human check
            # since this is the whole evidentiary quote, not just the connective words.
            span_text = edge.get("evidence_span", {}).get("text", "")
            edge["surface_phrase"] = f"{span_text}  # auto: check"
            n_automatic += 1

        if relation == "part_of" and not edge.get("part_type"):
            suggestions.append(
                Suggestion(str(path), f"item {i}", "part_type", "(none)", "component", "default guess; no concept-type context on the student side")
            )
            edge["_suggested_part_type"] = "component — SUGGESTED: confirm (default; no concept-type context on the student side)"

    data["registry_version"] = 1
    return FileMigration(path, out_path, data, n_automatic, suggestions)


def run_migration(gold_dir: Path, out_dir: Path, registry: RelationRegistry) -> list[FileMigration]:
    """Reads every expert_pilot/student_pilot file under `gold_dir` (read-only) and
    returns the proposed v1 migrations. Does not write anything itself — see
    write_migrations for that, kept separate so --dry-run can skip writing.
    """
    migrations: list[FileMigration] = []
    if not gold_dir.exists():
        return migrations

    for path in sorted(gold_dir.rglob("*.yaml")):
        rel = path.relative_to(gold_dir)
        out_path = out_dir / rel
        if rel.parts[0] == "expert_pilot":
            migrations.append(migrate_expert_pilot_file(path, out_path, registry))
        elif rel.parts[0] == "student_pilot":
            migrations.append(migrate_student_pilot_file(path, out_path, registry))

    return migrations


def write_migrations(migrations: list[FileMigration]) -> None:
    for m in migrations:
        m.out_path.parent.mkdir(parents=True, exist_ok=True)
        m.out_path.write_text(yaml.safe_dump(m.data, sort_keys=False, allow_unicode=True))


def write_migration_report(
    migrations: list[FileMigration],
    gold_validation_under_v1: ValidationResult,
    out_path: Path,
) -> Path:
    lines = ["# CR-001 gold migration report (v0 -> v1)\n"]
    lines.append(
        "Generated by `cumap gold migrate-v1`. Read-only towards `data/gold/` — proposed "
        "files are under `data/interim/suggestions/migrations/v1/`. Review, edit, and copy "
        "them into `data/gold/` yourself, then run `cumap gold validate --registry v1`.\n"
    )

    if not migrations:
        lines.append("No `data/gold/expert_pilot/` or `data/gold/student_pilot/` files found yet.\n")
    else:
        lines.append("## Automatic changes (applied in the proposed files)\n")
        lines.append("| file | automatic changes |")
        lines.append("|---|---|")
        for m in migrations:
            lines.append(f"| {m.source_path.name} | {m.n_automatic_changes} |")

        all_suggestions = [s for m in migrations for s in m.suggestions]
        lines.append("\n## Suggested changes (flagged only, NOT applied without confirmation)\n")
        if not all_suggestions:
            lines.append("None.\n")
        else:
            lines.append("| file | edge_id | field | current | suggested | reason |")
            lines.append("|---|---|---|---|---|---|")
            for s in all_suggestions:
                lines.append(f"| {Path(s.file).name} | {s.edge_id} | {s.field} | {s.current} | {s.suggested} | {s.reason} |")

    lines.append("\n## Files that would fail v1 validation as they are (before migration)\n")
    if not gold_validation_under_v1.issues:
        lines.append("None — every existing gold file already satisfies v1 rules, or there are no gold files yet.\n")
    else:
        by_file: dict[str, list[str]] = {}
        for issue in gold_validation_under_v1.issues:
            by_file.setdefault(issue.file, []).append(issue.message)
        for file, messages in by_file.items():
            lines.append(f"- `{file}`:")
            for msg in messages:
                lines.append(f"  - {msg}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
