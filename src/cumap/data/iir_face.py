"""CR-003 §3 / CR-005: loader for the FACE/IIR concept-extraction dataset (`iir_face`
only — the other CR-003 external sources are out of scope for now).

Source: github.com/PAWSLabUniversityOfPittsburgh/Concept-Extraction. Pinned commit and
licence notes in data/raw/external/iir_face/SOURCE.md and docs/DECISIONS.md. Only
chapters 1-3 have section text in this repo (13 sections) — that's what fixes CR-005's
"B1 dev chapters" choice, not a default we picked.
"""

from __future__ import annotations

import ast
import csv
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REPO_URL = "https://github.com/PAWSLabUniversityOfPittsburgh/Concept-Extraction.git"

# The repo's own text-with-labels chapter titles (confirmed from its own data: the
# first subsection record of chapters 2 and 3 carries the chapter's own title, since
# there's no separate "iir_2"/"iir_3" chapter-level record in book_section_samples).
CHAPTER_TITLES = {
    1: "Boolean retrieval",
    2: "The term vocabulary and postings lists",
    3: "Dictionaries and tolerant retrieval",
}

_SECTION_ID_RE = re.compile(r"^iir_(\d+)((?:_\d+)*)$")


@dataclass
class Section:
    """Same field set as cumap.schemas.textbook.Section (kept as a plain dataclass
    here, matching cumap.textbook.parse.Section's pattern, since CR-005's pipeline
    consumes P&D and IIR sections through the same code path).
    """

    section_id: str
    chapter_num: int | None
    chapter_title: str
    section_title: str
    heading_path: list[str]
    order_index: int
    source_file: str
    line_start: int
    line_end: int
    text: str
    emphasized_terms: list[str] = field(default_factory=list)
    word_count: int = 0


def fetch_iir_face(dest_dir: Path) -> str:
    """Shallow-clones the FACE/IIR repo if not already present. Returns the commit hash.
    Removes the nested .git afterward (this project only needs a pinned snapshot, and a
    live nested git repo breaks the SOURCE.md gitignore exception — see .gitignore).
    """
    if not (dest_dir / "IIR-dataset").exists():
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(dest_dir)], check=True)
    git_dir = dest_dir / ".git"
    if git_dir.exists():
        result = subprocess.run(
            ["git", "-C", str(dest_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()
        import shutil

        shutil.rmtree(git_dir)
        return commit
    return "9f03208fd995fc4e92c14fa1d371c185629ead56"  # already fetched; matches SOURCE.md


def parse_iir_sections(tsv_path: Path) -> list[Section]:
    """Parses IIR-dataset/book_section_samples/iir.sections.txt: tab-separated
    section_id, title, keywords, content. Only 13 rows exist (chapters 1-3).
    """
    with tsv_path.open(encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t", quotechar='"'))

    sections = []
    for i, row in enumerate(rows):
        section_id, title, _keywords, content = row[0], row[1], row[2], row[3]
        match = _SECTION_ID_RE.match(section_id)
        if not match:
            raise ValueError(f"Unrecognised IIR section_id format: {section_id!r}")
        chapter_num = int(match.group(1))
        chapter_title = CHAPTER_TITLES.get(chapter_num, f"Chapter {chapter_num}")

        sections.append(
            Section(
                section_id=section_id,
                chapter_num=chapter_num,
                chapter_title=chapter_title,
                section_title=title,
                heading_path=[chapter_title, title],
                order_index=i,
                source_file=str(tsv_path.name),
                line_start=i,
                line_end=i,
                text=content,
                emphasized_terms=[],
                word_count=len(content.split()),
            )
        )
    return sections


def _annotation_filename(section_id: str) -> str:
    """ "iir_1" -> "iir-1.csv"; "iir_1_1" -> "iir-1.1.csv"; "iir_12_1_1" -> "iir-12.1.1.csv"."""
    match = _SECTION_ID_RE.match(section_id)
    if not match:
        raise ValueError(f"Unrecognised IIR section_id format: {section_id!r}")
    chapter, rest = match.group(1), match.group(2)
    return f"iir-{chapter}{rest.replace('_', '.')}.csv"


def _parse_concept_list(raw: str) -> list[str]:
    """Most rows are a valid Python-list-repr string. A handful in the real dataset
    (chapters beyond the dev split; confirmed exactly 1 of 86 files as of the commit
    pinned in SOURCE.md) have an unescaped apostrophe inside a single-quoted item,
    e.g. "['nonrelevant document's vector']", which breaks ast.literal_eval. Falls
    back to treating the whole bracket content as one alias string in that case --
    correct for the confirmed single-item case; a multi-item row with the same defect
    would be mis-split, but none exist in the data as fetched.
    """
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        inner = raw.strip().removeprefix("[").removesuffix("]").strip()
        return [inner.strip("'\"")]


def parse_gold_concepts(
    annotation_dir: Path, section_ids: list[str], *, min_annotators_agree: int = 2
) -> pd.DataFrame:
    """Reads one annotation CSV per section_id. Each row: a Python-list-repr string of
    concept surface forms (aliases) + 3 annotator 0/1 columns. Gold = majority vote
    (>= min_annotators_agree of 3 say "yes"). Returns one row per (section_id, concept),
    concept = the first-listed surface form, aliases = the rest.
    """
    rows = []
    for section_id in section_ids:
        path = annotation_dir / _annotation_filename(section_id)
        if not path.exists():
            raise FileNotFoundError(f"No annotation file for {section_id!r} at {path}")

        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for record in reader:
                aliases = _parse_concept_list(record["Concepts"])
                votes = [
                    int(float(record[col]))  # some rows use "1.0" rather than "1"
                    for col in ("Annotator 1", "Annotator 2", "Annotator 3")
                    if col in record and record[col] not in (None, "")
                ]
                n_yes = sum(votes)
                rows.append(
                    {
                        "section_id": section_id,
                        "concept": aliases[0],
                        "aliases": aliases[1:],
                        "n_annotators_yes": n_yes,
                        "n_annotators_total": len(votes),
                        "is_gold": n_yes >= min_annotators_agree,
                    }
                )
    return pd.DataFrame(rows)


def load_iir_face(raw_dir: Path) -> tuple[list[Section], pd.DataFrame]:
    """raw_dir is the cloned repo root (e.g. data/raw/external/iir_face)."""
    sections = parse_iir_sections(
        raw_dir / "IIR-dataset" / "book_section_samples" / "iir.sections.txt"
    )
    gold = parse_gold_concepts(
        raw_dir / "IIR-dataset" / "annotation", [s.section_id for s in sections]
    )
    return sections, gold
