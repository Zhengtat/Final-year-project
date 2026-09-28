"""Parses the Peterson & Davie RST source into plain-text Sections.

Chosen approach: heading-regex + block-stripping, not docutils (see DECISIONS.md,
2026-09-28 "textbook parser"). The book's own toctree nesting (root index.rst ->
chapter file -> chapter's own toctree of section files) already gives the section
granularity BUILD_PLAN M1 asks for ("one Section per lowest-level heading"): each
*leaf* file listed in a chapter's toctree becomes one Section, named after that
file's own top heading (e.g. "6.3 TCP Congestion Control" -> section_id "6.3").
Deeper in-file subheadings (e.g. "6.3.1 ...") are kept as plain-text paragraph
breaks within that Section's text, not split into their own Sections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_ADORNMENT_CHARS = set("=-~^\"'`#*+.,:;<>_!$%&()/\\[]{}|@")
_CHAPTER_HEADING_RE = re.compile(r"^Chapter\s+(\d+)\s*:\s*(.+)$")
_NUMBERED_SECTION_RE = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$")
_TOCTREE_ENTRY_RE = re.compile(r"^([\w/.\-]+\.rst)\s*$")
_ROLE_RE = re.compile(r":[\w][\w-]*:`([^`]*)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_INLINE_LITERAL_RE = re.compile(r"``(.+?)``")


def _is_adornment_line(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 3 and len(set(stripped)) == 1 and stripped[0] in _ADORNMENT_CHARS


@dataclass
class Heading:
    title: str
    line_index: int  # 0-based index of the title line in the file
    is_first: bool = False


def find_headings(lines: list[str]) -> list[Heading]:
    """Finds every `title` / `title\\nunderline` / `overline\\ntitle\\nunderline` heading."""
    headings: list[Heading] = []
    i = 0
    n = len(lines)
    first = True
    while i < n:
        line = lines[i]
        if not line.strip() or _is_adornment_line(line):
            i += 1
            continue
        # title + underline (a preceding overline, if any, was already skipped above as a
        # standalone adornment line, so `title + underline` also covers `overline + title + underline`)
        if i + 1 < n and _is_adornment_line(lines[i + 1]):
            headings.append(Heading(title=line.strip(), line_index=i, is_first=first))
            first = False
            i += 2
            continue
        i += 1
    return headings


def _strip_directive_and_literal_blocks(lines: list[str]) -> list[str]:
    """Removes `.. directive::` blocks and `::`-introduced literal blocks (incl. their indented body)."""
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        is_directive = stripped.startswith("..")
        is_literal_intro = stripped.endswith("::") and not is_directive
        if is_literal_intro:
            prose = stripped[:-2].rstrip()
            if prose:
                out.append(prose + ("." if not prose.endswith((".", ":", "!", "?")) else ""))
            i += 1
            while i < n and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                i += 1
            continue
        if is_directive:
            i += 1
            while i < n and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                i += 1
            continue
        out.append(line)
        i += 1
    return out


def _clean_inline_markup(text: str) -> tuple[str, list[str]]:
    emphasized: list[str] = []

    def _role_sub(m: re.Match) -> str:
        inner = m.group(1)
        inner = re.sub(r"\s*<[^>]*>\s*$", "", inner)  # drop explicit `<target>` suffix
        inner = inner.replace("%s", "").strip()
        return inner

    text = _ROLE_RE.sub(_role_sub, text)

    def _bold_sub(m: re.Match) -> str:
        emphasized.append(m.group(1))
        return m.group(1)

    text = _BOLD_RE.sub(_bold_sub, text)

    def _italic_sub(m: re.Match) -> str:
        emphasized.append(m.group(1))
        return m.group(1)

    text = _ITALIC_RE.sub(_italic_sub, text)
    text = _INLINE_LITERAL_RE.sub(lambda m: m.group(1), text)
    return text, emphasized


@dataclass
class Section:
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


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def parse_section_file(
    path: Path,
    *,
    chapter_num: int | None,
    chapter_title: str,
    order_index: int,
    repo_root: Path,
) -> Section:
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    headings = find_headings(raw_lines)
    if not headings:
        raise ValueError(f"{path}: no heading found")

    first = headings[0]
    numbered = _NUMBERED_SECTION_RE.match(first.title)
    if numbered:
        section_id, section_title = numbered.group(1), numbered.group(2)
    else:
        section_id = f"{chapter_num if chapter_num is not None else 'x'}-{_slugify(first.title)}"
        section_title = first.title

    body_start = first.line_index + 2  # skip title + underline
    body_lines = raw_lines[body_start:]

    emphasized_terms: list[str] = []
    for h in headings[1:]:
        cleaned, emph = _clean_inline_markup(h.title)
        h.title = cleaned
        emphasized_terms.extend(emph)

    # Drop this section's own adornment lines and any subheading adornment lines,
    # keeping subheading titles inline as plain paragraph text.
    kept_lines: list[str] = []
    heading_line_indices = {h.line_index for h in headings}
    i = 0
    n = len(body_lines)
    while i < n:
        abs_idx = body_start + i
        line = body_lines[i]
        if abs_idx in heading_line_indices:
            kept_lines.append(line)  # subheading title text, kept as a paragraph
            i += 1
            if i < n and _is_adornment_line(body_lines[i]):
                i += 1  # drop its underline
            continue
        if _is_adornment_line(line):
            i += 1
            continue
        kept_lines.append(line)
        i += 1

    kept_lines = _strip_directive_and_literal_blocks(kept_lines)

    paragraphs: list[str] = []
    current: list[str] = []
    for line in kept_lines:
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))

    cleaned_paragraphs = []
    for p in paragraphs:
        cleaned, emph = _clean_inline_markup(p)
        cleaned_paragraphs.append(cleaned)
        emphasized_terms.extend(emph)

    text = "\n\n".join(cleaned_paragraphs)

    return Section(
        section_id=section_id,
        chapter_num=chapter_num,
        chapter_title=chapter_title,
        section_title=section_title,
        heading_path=[chapter_title, section_title],
        order_index=order_index,
        source_file=str(path.relative_to(repo_root)),
        line_start=first.line_index + 1,
        line_end=len(raw_lines),
        text=text,
        emphasized_terms=sorted(set(emphasized_terms)),
        word_count=len(text.split()),
    )


def _extract_toctree_entries(lines: list[str]) -> list[str]:
    entries = []
    in_toctree = False
    for line in lines:
        if line.strip().startswith(".. toctree::"):
            in_toctree = True
            continue
        if in_toctree:
            if not line.strip():
                continue
            if line.startswith(("   :", "  :")):  # toctree option, e.g. :maxdepth:
                continue
            if not line.startswith((" ", "\t")):
                break  # dedent = toctree ended
            match = _TOCTREE_ENTRY_RE.match(line.strip())
            if match:
                entries.append(match.group(1))
    return entries


# Front/back matter files with no "Chapter N:" heading; kept in book order, chapter_num=None.
_NON_CHAPTER_FILES = {"README.rst", "latest.rst", "print.rst"}


def parse_textbook(repo_dir: Path) -> list[Section]:
    index_lines = (repo_dir / "index.rst").read_text(encoding="utf-8").splitlines()
    chapter_files = _extract_toctree_entries(index_lines)

    sections: list[Section] = []
    order_index = 0
    for chapter_file in chapter_files:
        if chapter_file in _NON_CHAPTER_FILES:
            continue
        chapter_path = repo_dir / chapter_file
        chapter_lines = chapter_path.read_text(encoding="utf-8").splitlines()
        chapter_headings = find_headings(chapter_lines)
        chapter_title_line = chapter_headings[0].title if chapter_headings else chapter_path.stem
        chapter_match = _CHAPTER_HEADING_RE.match(chapter_title_line)
        if chapter_match:
            chapter_num = int(chapter_match.group(1))
            chapter_title = chapter_match.group(2).strip()
        else:
            chapter_num = None
            chapter_title = chapter_title_line

        section_files = _extract_toctree_entries(chapter_lines)
        if not section_files:
            # No nested toctree: the chapter file itself is a single Section (e.g. foreword/preface).
            section_files = [chapter_file]

        for rel in section_files:
            section_path = repo_dir / rel
            if not section_path.exists():
                continue
            section = parse_section_file(
                section_path,
                chapter_num=chapter_num,
                chapter_title=chapter_title,
                order_index=order_index,
                repo_root=repo_dir,
            )
            sections.append(section)
            order_index += 1

    return sections
