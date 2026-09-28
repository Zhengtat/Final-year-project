"""Section schema — matches the fields produced by textbook/parse.py (BUILD_PLAN M1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    emphasized_terms: list[str]
    word_count: int
