"""`cumap gold validate`: validates every file under data/gold/ against the schemas
and the relation registry, and checks every Evidence.quote is a verified substring
of its source text (CLAUDE.md rule 3). Read-only: never writes to data/gold/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from cumap.schemas.edges import ExpertEdge
from cumap.schemas.labels import Proposition, SilverAnswerLabel
from cumap.schemas.misconceptions import Misconception
from cumap.schemas.relations import EdgeRef, RelationRegistry
from cumap.schemas.student import StudentEdge


def normalise_whitespace(text: str) -> str:
    return " ".join(text.split())


def verify_quote(quote: str, source_text: str) -> bool:
    """True iff `quote` is an exact substring of `source_text` after whitespace
    normalisation (runs of whitespace collapsed to a single space on both sides).
    Case-sensitive: an evidence quote must match the source's actual wording.
    """
    return normalise_whitespace(quote) in normalise_whitespace(source_text)


@dataclass
class ValidationIssue:
    file: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.message}"


def _load_yaml_list(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text())
    if data is None:
        return []
    if isinstance(data, dict):
        data = [data]
    return data


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _validate_expert_pilot_file(
    path: Path, sections_by_id: dict[str, str], registry: RelationRegistry
) -> list[ValidationIssue]:
    issues = []
    try:
        rows = _load_yaml_list(path)
    except yaml.YAMLError as e:
        return [ValidationIssue(str(path), f"invalid YAML: {e}")]

    for i, row in enumerate(rows):
        try:
            edge = ExpertEdge.model_validate(row)
        except ValidationError as e:
            issues.append(ValidationIssue(str(path), f"item {i} ({row.get('edge_id', '?')}): {e}"))
            continue

        if edge.relation not in registry:
            issues.append(
                ValidationIssue(str(path), f"{edge.edge_id}: unknown relation {edge.relation!r}")
            )
        else:
            type_errors = registry.check_types(
                EdgeRef(edge.source_id, edge.relation, edge.target_id), {}
            )
            for e in type_errors:
                issues.append(ValidationIssue(str(path), f"{edge.edge_id}: {e}"))

        for ev in edge.evidence:
            if ev.section_id is None:
                continue
            section_text = sections_by_id.get(ev.section_id)
            if section_text is None:
                issues.append(
                    ValidationIssue(str(path), f"{edge.edge_id}: unknown section_id {ev.section_id!r}")
                )
            elif not verify_quote(ev.quote, section_text):
                issues.append(
                    ValidationIssue(
                        str(path),
                        f"{edge.edge_id}: evidence quote not found in section {ev.section_id}: {ev.quote!r}",
                    )
                )
    return issues


def _validate_student_pilot_file(
    path: Path, answers_by_id: dict[str, str]
) -> list[ValidationIssue]:
    issues = []
    try:
        rows = _load_yaml_list(path)
    except yaml.YAMLError as e:
        return [ValidationIssue(str(path), f"invalid YAML: {e}")]

    for i, row in enumerate(rows):
        try:
            edge = StudentEdge.model_validate(row)
        except ValidationError as e:
            issues.append(ValidationIssue(str(path), f"item {i}: {e}"))
            continue

        answer_text = answers_by_id.get(edge.response_id)
        if answer_text is None:
            issues.append(
                ValidationIssue(str(path), f"{edge.response_id}: unknown answer_id")
            )
        elif not verify_quote(edge.evidence_span.text, answer_text):
            issues.append(
                ValidationIssue(
                    str(path),
                    f"{edge.response_id}: evidence_span text not found in answer: {edge.evidence_span.text!r}",
                )
            )
    return issues


def _validate_jsonl(path: Path, schema: type) -> list[ValidationIssue]:
    issues = []
    try:
        rows = _load_jsonl(path)
    except json.JSONDecodeError as e:
        return [ValidationIssue(str(path), f"invalid JSONL: {e}")]

    for i, row in enumerate(rows):
        try:
            schema.model_validate(row)
        except ValidationError as e:
            issues.append(ValidationIssue(str(path), f"line {i + 1}: {e}"))
    return issues


def _validate_misconceptions_file(path: Path) -> list[ValidationIssue]:
    issues = []
    try:
        rows = _load_yaml_list(path)
    except yaml.YAMLError as e:
        return [ValidationIssue(str(path), f"invalid YAML: {e}")]

    for i, row in enumerate(rows):
        try:
            Misconception.model_validate(row)
        except ValidationError as e:
            issues.append(ValidationIssue(str(path), f"item {i}: {e}"))
    return issues


def validate_gold_dir(
    gold_dir: Path,
    *,
    sections_by_id: dict[str, str] | None = None,
    answers_by_id: dict[str, str] | None = None,
    registry: RelationRegistry | None = None,
) -> list[ValidationIssue]:
    """Validates every recognised file under `gold_dir`. Files that don't match a known
    naming convention are skipped, not failed — this directory is human-owned and may
    contain things (like question_section_map.csv) with no pydantic schema.
    """
    sections_by_id = sections_by_id or {}
    answers_by_id = answers_by_id or {}
    registry = registry or RelationRegistry.from_yaml(
        Path(__file__).parents[3] / "configs" / "relations_v0.yaml"
    )

    issues: list[ValidationIssue] = []
    if not gold_dir.exists():
        return issues

    for path in sorted(gold_dir.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        rel = path.relative_to(gold_dir)
        parts = rel.parts

        if parts[0] == "expert_pilot" and path.suffix in (".yaml", ".yml"):
            issues += _validate_expert_pilot_file(path, sections_by_id, registry)
        elif parts[0] == "student_pilot" and path.suffix in (".yaml", ".yml"):
            issues += _validate_student_pilot_file(path, answers_by_id)
        elif path.name == "propositions.jsonl":
            issues += _validate_jsonl(path, Proposition)
        elif path.name == "verified_labels.jsonl":
            issues += _validate_jsonl(path, SilverAnswerLabel)
        elif path.name.startswith("misconceptions") and path.suffix in (".yaml", ".yml"):
            issues += _validate_misconceptions_file(path)
        # else: no schema mapping for this file yet — skipped, not failed.

    return issues
