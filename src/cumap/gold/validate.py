"""`cumap gold validate`: validates every file under data/gold/ against the schemas
and the relation registry, and checks every Evidence.quote is a verified substring
of its source text (CLAUDE.md rule 3). Read-only: never writes to data/gold/.

CR-001 §5 made this version-aware: a gold expert/student file is v0 or v1 depending
on a top-level `registry_version:` key (missing = v0). v0 files are validated under
v0 rules only (no qualifier/family/chain-link checks) and get a one-line informational
hint, not a failure, suggesting the migration tool. `--registry v1` (validate_gold_dir's
`force_version=1`) applies v1 rules to every file regardless of its own key, for use
after the human has migrated.

Note: relations_v1.yaml's 16 names are a strict superset of v0's 14 (CR-001 added
has_purpose/performs; nothing was renamed or removed), so relation-name/domain-range
checks use the v1 registry for both v0 and v1 files — a second, separately-loaded v0
registry instance isn't needed for that. Only the v1-only checks (required qualifiers,
relation_family match, chain-link references) are gated behind the detected version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from cumap.schemas.chain_links import ChainLink
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


@dataclass
class ValidationResult:
    issues: list[ValidationIssue]
    hints: list[str]  # informational only (e.g. "v0 file, consider migrating") — never fail validation

    def __bool__(self) -> bool:  # True iff clean (no issues) — lets `if not result:` read naturally
        return not self.issues


def _load_yaml_dict(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    return data or {}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _detect_version(data: dict, forced_version: int | None) -> int:
    if forced_version is not None:
        return forced_version
    return data.get("registry_version", 0)


def _validate_chain_links(
    path: Path,
    chain_link_rows: list[dict],
    known_edge_ids: set[str],
    sections_by_id: dict[str, str],
    answers_by_id: dict[str, str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for i, row in enumerate(chain_link_rows):
        try:
            link = ChainLink.model_validate(row)
        except ValidationError as e:
            issues.append(ValidationIssue(str(path), f"chain_links[{i}]: {e}"))
            continue

        if link.from_edge_id not in known_edge_ids:
            issues.append(ValidationIssue(str(path), f"{link.link_id}: from_edge_id {link.from_edge_id!r} not found in this file"))
        if link.to_edge_id not in known_edge_ids:
            issues.append(ValidationIssue(str(path), f"{link.link_id}: to_edge_id {link.to_edge_id!r} not found in this file"))

        for ev in link.evidence:
            source_text = sections_by_id.get(ev.section_id) if ev.section_id else answers_by_id.get(ev.answer_id)
            if source_text is None:
                issues.append(ValidationIssue(str(path), f"{link.link_id}: unknown evidence source ({ev.section_id or ev.answer_id!r})"))
            elif not verify_quote(ev.quote, source_text):
                issues.append(ValidationIssue(str(path), f"{link.link_id}: evidence quote not found: {ev.quote!r}"))
    return issues


def _validate_expert_pilot_file(
    path: Path,
    sections_by_id: dict[str, str],
    registry: RelationRegistry,
    forced_version: int | None,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    hints: list[str] = []
    try:
        data = _load_yaml_dict(path)
    except yaml.YAMLError as e:
        return [ValidationIssue(str(path), f"invalid YAML: {e}")], hints

    version = _detect_version(data, forced_version)
    edges = data.get("edges", [])
    chain_link_rows = data.get("chain_links", [])
    known_edge_ids: set[str] = set()

    for i, row in enumerate(edges):
        try:
            edge = ExpertEdge.model_validate(row)
        except ValidationError as e:
            issues.append(ValidationIssue(str(path), f"item {i} ({row.get('edge_id', '?')}): {e}"))
            continue
        known_edge_ids.add(edge.edge_id)

        if edge.relation not in registry:
            issues.append(ValidationIssue(str(path), f"{edge.edge_id}: unknown relation {edge.relation!r}"))
        else:
            for e in registry.check_types(EdgeRef(edge.source_id, edge.relation, edge.target_id), {}):
                issues.append(ValidationIssue(str(path), f"{edge.edge_id}: {e}"))

        for ev in edge.evidence:
            if ev.section_id is None:
                continue
            section_text = sections_by_id.get(ev.section_id)
            if section_text is None:
                issues.append(ValidationIssue(str(path), f"{edge.edge_id}: unknown section_id {ev.section_id!r}"))
            elif not verify_quote(ev.quote, section_text):
                issues.append(ValidationIssue(str(path), f"{edge.edge_id}: evidence quote not found in section {ev.section_id}: {ev.quote!r}"))

        if version >= 1 and edge.relation in registry:
            for qualifier in registry.required_qualifiers(edge.relation):
                if getattr(edge, qualifier, None) in (None, [], ""):
                    issues.append(ValidationIssue(str(path), f"{edge.edge_id}: missing required qualifier {qualifier!r} (v1)"))
            expected_family = registry.family_of(edge.relation)
            if edge.relation_family is not None and edge.relation_family != expected_family:
                issues.append(
                    ValidationIssue(str(path), f"{edge.edge_id}: relation_family {edge.relation_family!r} != registry's {expected_family!r}")
                )

    if version >= 1:
        issues += _validate_chain_links(path, chain_link_rows, known_edge_ids, sections_by_id, {})
    elif chain_link_rows:
        issues.append(ValidationIssue(str(path), "has chain_links but registry_version < 1 — add `registry_version: 1` to validate them"))

    if version == 0:
        hints.append(f"{path}: v0 file — run `cumap gold migrate-v1 --dry-run` to see a proposed v1 upgrade.")

    return issues, hints


def _validate_student_pilot_file(
    path: Path,
    answers_by_id: dict[str, str],
    forced_version: int | None,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    hints: list[str] = []
    try:
        data = _load_yaml_dict(path)
    except yaml.YAMLError as e:
        return [ValidationIssue(str(path), f"invalid YAML: {e}")], hints

    version = _detect_version(data, forced_version)
    edges = data.get("edges", [])
    chain_link_rows = data.get("chain_links", [])
    # Student edges have no stable id of their own; chain links address them positionally.
    synthetic_edge_ids = {f"SE-{i}" for i in range(len(edges))}

    for i, row in enumerate(edges):
        try:
            edge = StudentEdge.model_validate(row)
        except ValidationError as e:
            issues.append(ValidationIssue(str(path), f"item {i}: {e}"))
            continue

        answer_text = answers_by_id.get(edge.response_id)
        if answer_text is None:
            issues.append(ValidationIssue(str(path), f"{edge.response_id}: unknown answer_id"))
        elif not verify_quote(edge.evidence_span.text, answer_text):
            issues.append(
                ValidationIssue(str(path), f"{edge.response_id}: evidence_span text not found in answer: {edge.evidence_span.text!r}")
            )

        if version >= 1 and edge.surface_phrase in (None, ""):
            issues.append(ValidationIssue(str(path), f"item {i}: missing required surface_phrase (v1, required on every StudentEdge)"))

    if version >= 1:
        issues += _validate_chain_links(path, chain_link_rows, synthetic_edge_ids, {}, answers_by_id)
    elif chain_link_rows:
        issues.append(ValidationIssue(str(path), "has chain_links but registry_version < 1 — add `registry_version: 1` to validate them"))

    if version == 0:
        hints.append(f"{path}: v0 file — run `cumap gold migrate-v1 --dry-run` to see a proposed v1 upgrade.")

    return issues, hints


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
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        return [ValidationIssue(str(path), f"invalid YAML: {e}")]
    rows = data if isinstance(data, list) else ([data] if data else [])

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
    force_version: int | None = None,
) -> ValidationResult:
    """Validates every recognised file under `gold_dir`. Files that don't match a known
    naming convention are skipped, not failed — this directory is human-owned and may
    contain things (like question_section_map.csv) with no pydantic schema.

    `force_version`: None (default) detects each file's own version from its
    `registry_version:` key (missing = 0); pass 1 to force v1 rules on every file
    (CLAUDE-001 §5 `--registry v1`, used after the human has migrated).
    """
    sections_by_id = sections_by_id or {}
    answers_by_id = answers_by_id or {}
    if registry is None:
        from cumap.config import get_settings

        settings = get_settings()
        registry = RelationRegistry.from_yaml(settings.resolve(settings.relation_registry))

    issues: list[ValidationIssue] = []
    hints: list[str] = []
    if not gold_dir.exists():
        return ValidationResult(issues, hints)

    for path in sorted(gold_dir.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        rel = path.relative_to(gold_dir)
        parts = rel.parts

        if parts[0] == "expert_pilot" and path.suffix in (".yaml", ".yml"):
            file_issues, file_hints = _validate_expert_pilot_file(path, sections_by_id, registry, force_version)
            issues += file_issues
            hints += file_hints
        elif parts[0] == "student_pilot" and path.suffix in (".yaml", ".yml"):
            file_issues, file_hints = _validate_student_pilot_file(path, answers_by_id, force_version)
            issues += file_issues
            hints += file_hints
        elif path.name == "propositions.jsonl":
            issues += _validate_jsonl(path, Proposition)
        elif path.name == "verified_labels.jsonl":
            issues += _validate_jsonl(path, SilverAnswerLabel)
        elif path.name.startswith("misconceptions") and path.suffix in (".yaml", ".yml"):
            issues += _validate_misconceptions_file(path)
        # else: no schema mapping for this file yet — skipped, not failed.

    return ValidationResult(issues, hints)
