"""Section text viewers (CR-005 §4 tab 1): highlight spans over the original section text.
Spans are located by whitespace-tolerant search; overlapping spans keep the first (highest
priority) one. Output is escaped HTML -- span text is never interpreted as markup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    css: str
    tip: str = ""


def find_span(text: str, phrase: str, *, ignore_case: bool = True) -> tuple[int, int] | None:
    """First occurrence of `phrase` in `text`, any run of whitespace matching any run of
    whitespace (quotes were verified after whitespace normalisation, so the original text
    may have different line breaks). Whole-word at both ends when the phrase's ends are word
    characters, so 'net' does not match inside 'network'.
    """
    words = phrase.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    if re.match(r"\w", phrase.strip()[0]):
        pattern = r"(?<!\w)" + pattern
    if re.match(r"\w", phrase.strip()[-1]):
        pattern += r"(?!\w)"
    m = re.search(pattern, text, re.IGNORECASE if ignore_case else 0)
    return (m.start(), m.end()) if m else None


def highlight_html(text: str, spans: list[Span]) -> str:
    """`spans` in priority order; a span overlapping one already kept is dropped."""
    kept: list[Span] = []
    for span in spans:
        if span.end <= span.start:
            continue
        if any(span.start < k.end and k.start < span.end for k in kept):
            continue
        kept.append(span)
    kept.sort(key=lambda s: s.start)
    out, pos = [], 0
    for s in kept:
        out.append(escape(text[pos : s.start]))
        tip = f' title="{escape(s.tip, quote=True)}"' if s.tip else ""
        out.append(f'<mark class="{escape(s.css)}"{tip}>{escape(text[s.start : s.end])}</mark>')
        pos = s.end
    out.append(escape(text[pos:]))
    return "".join(out)
