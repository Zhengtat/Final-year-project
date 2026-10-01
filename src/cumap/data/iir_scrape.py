"""CR-007 §3.1: IIR test-split scraper, promoted from the CR-005 scratch script.

FACE's section text is not published for chapters beyond 3, so it is rebuilt from the book's
public HTML edition (nlp.stanford.edu/IR-book, local research use only; the text is (c) Cambridge
University Press and is never committed). The rules were validated against FACE's own dev text
(chapters 1-3, 5-word-shingle coverage) before being applied to any test chapter:

- **Sections come from the page tree (the "Table of Child-Links"), not the Next chain.**
- **An annotated section covers its own page plus every descendant page that is not itself an
  annotated section** (FACE's iir_N_M is the whole subtree of book section N.M).
- **Intro-to-N.1 rule:** where a chapter has no bare `iir-N` annotation, its first annotated section
  also carries the chapter intro. Variant B generalises this to the own pages of all un-annotated
  ancestors; it is used only if variant A fails the gate and B passes.
- **Gold-presence gate:** a section whose text contains fewer than 90% of its gold concepts
  (majority vote, name or alias, case- and whitespace-insensitive) is EXCLUDED and listed, never
  scored silently. Gold terms are used here only as a data-validity test of the scrape, never to tune
  a prompt.

Network access goes through an injectable `fetch(slug) -> html`, so tests use local fixtures.
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

BASE = "https://nlp.stanford.edu/IR-book/html/htmledition/"
HEADERS = {"User-Agent": "Mozilla/5.0 (academic research; non-redistributed use)"}
GATE = 0.90
_TAG = re.compile(r"<[^>]+>")
_ENT = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&copy;": "(c)"}
_SKIP_TITLES = ("references and further reading", "exercises")

Fetch = Callable[[str], str]


def make_fetcher(cache_dir: Path, *, delay: float = 0.4) -> Fetch:
    """Disk-cached, polite fetcher for the book's HTML pages."""
    cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(slug: str) -> str:
        slug = slug.split("#")[0]
        path = cache_dir / hashlib.md5(slug.encode()).hexdigest()
        if path.exists():
            return path.read_text(encoding="utf-8")
        time.sleep(delay)
        req = urllib.request.Request(BASE + slug, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="replace")
        path.write_text(html, encoding="utf-8")
        return html

    return fetch


def own_body(html: str) -> str:
    """The page's own text: after the navigation panel, before its child-links table."""
    marker = "<!--End of Navigation Panel-->"
    start = html.index(marker) + len(marker)
    ends = [len(html)]
    for stop in ("<!--Table of Child-Links-->", "<!--Navigation Panel-->"):
        i = html.find(stop, start)
        if i != -1:
            ends.append(i)
    text = _TAG.sub(" ", html[start : min(ends)])
    for k, v in _ENT.items():
        text = text.replace(k, v)
    return re.sub(r"\s+", " ", text).strip()


def child_tree(html: str) -> list[tuple[int, str, str]]:
    """Flat (depth, href, title) list from the nested <UL> child-links table (depth 1 = children)."""
    m = re.search(
        r"<!--Table of Child-Links-->(.*?)<!--End of Table of Child-Links-->", html, re.DOTALL
    )
    if not m:
        return []
    out, depth = [], 0
    pattern = r"<(/?)UL>|<LI><A[^>]*HREF=\"([^\"]+)\"[^>]*>(.*?)</A>"
    for tok in re.finditer(pattern, m.group(1), re.DOTALL | re.IGNORECASE):
        head = tok.group(0).upper()
        if head.startswith("<UL"):
            depth += 1
        elif head.startswith("</UL"):
            depth -= 1
        else:
            out.append((depth, tok.group(2), _TAG.sub("", tok.group(3)).strip()))
    return out


def parse_toc(html: str, n_chapters: int = 21) -> dict[int, str]:
    """Chapter number -> first page slug, from the book's front page (irbook.html)."""
    links = re.findall(r'<LI><A[^>]*HREF="([^"]+)"[^>]*>', html, re.IGNORECASE)
    return {i + 1: slug for i, slug in enumerate(links[:n_chapters])}


@dataclass
class Node:
    path: tuple[int, ...]  # (chapter, section, subsection, ...)
    title: str
    href: str
    own_text: str
    parent: tuple[int, ...] | None = None


def build_tree(chapter: int, chapter_slug: str, fetch: Fetch) -> dict[tuple[int, ...], Node]:
    """All pages of a chapter as nodes keyed by their book path, from the child-links tree."""
    html = fetch(chapter_slug)
    nodes: dict[tuple[int, ...], Node] = {
        (chapter,): Node((chapter,), "", chapter_slug, own_body(html))
    }
    counters: list[int] = []
    skip_depth: int | None = None
    for depth, href, title in child_tree(html):
        if "bibliography" in href:
            continue
        if depth == 1 and title.lower().startswith(_SKIP_TITLES):
            skip_depth = 1
            continue
        if skip_depth is not None:
            if depth > skip_depth:
                continue
            skip_depth = None
        del counters[depth:]
        while len(counters) < depth:
            counters.append(0)
        counters[depth - 1] += 1
        path = (chapter, *counters[:depth])
        parent = path[:-1]
        nodes[path] = Node(path, title, href, own_body(fetch(href)), parent)
    return nodes


def annotated_path(annotation_id: str) -> tuple[int, ...]:
    """'iir-12.1.1' / 'iir_12_1_1' -> (12, 1, 1)."""
    return tuple(int(x) for x in re.findall(r"\d+", annotation_id))


def section_id(path: tuple[int, ...]) -> str:
    return "iir_" + "_".join(str(p) for p in path)


def _descendants(nodes: dict, path: tuple[int, ...]) -> list[tuple[int, ...]]:
    return sorted(p for p in nodes if len(p) > len(path) and p[: len(path)] == path)


def section_text(
    nodes: dict[tuple[int, ...], Node], path: tuple[int, ...], annotated: set[tuple[int, ...]]
) -> str:
    """Own page + every descendant page that is not itself (inside) an annotated section."""
    parts = [nodes[path].own_text]
    for d in _descendants(nodes, path):
        if any(d[: len(a)] == a for a in annotated if a != path and len(a) > len(path)):
            continue
        parts.append(nodes[d].own_text)
    return " ".join(p for p in parts if p)


def ancestors_text(nodes: dict, path: tuple[int, ...], annotated: set[tuple[int, ...]]) -> str:
    """Variant B prefix: own pages of the un-annotated ancestors, chapter intro first."""
    parts = []
    for k in range(1, len(path)):
        anc = path[:k]
        if anc in nodes and anc not in annotated:
            parts.append(nodes[anc].own_text)
    return " ".join(p for p in parts if p)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def gold_presence(text: str, gold: list[tuple[str, list[str]]]) -> float | None:
    """Share of gold concepts (name or any alias) present verbatim in `text`. None if no gold."""
    if not gold:
        return None
    t = norm(text)
    hit = sum(
        1 for name, aliases in gold if any(norm(n) and norm(n) in t for n in [name, *aliases])
    )
    return hit / len(gold)


@dataclass
class Scraped:
    section_id: str
    path: tuple[int, ...]
    title: str
    text: str
    variant: str  # "A" | "B"
    presence: float | None
    n_pages: int
    n_gold: int
    words: int = 0
    excluded_reason: str | None = None
    presence_a: float | None = None
    presence_b: float | None = None
    extra: dict = field(default_factory=dict)


def scrape_chapter(
    chapter: int,
    chapter_slug: str,
    annotation_ids: list[str],
    gold_by_section: dict[str, list[tuple[str, list[str]]]],
    fetch: Fetch,
    *,
    gate: float = GATE,
) -> list[Scraped]:
    """One Scraped per annotated section of the chapter, with the gate applied."""
    nodes = build_tree(chapter, chapter_slug, fetch)
    annotated = {annotated_path(a) for a in annotation_ids}
    bare = (chapter,) in annotated
    first = min((p for p in annotated if len(p) > 1), default=None)
    out: list[Scraped] = []
    for path in sorted(annotated):
        if path not in nodes:
            out.append(
                Scraped(
                    section_id(path),
                    path,
                    "",
                    "",
                    "A",
                    None,
                    0,
                    0,
                    excluded_reason="no page in the chapter's child-links tree",
                )
            )
            continue
        sid = section_id(path)
        gold = gold_by_section.get(sid, [])
        base = section_text(nodes, path, annotated)
        text_a = (nodes[(chapter,)].own_text + " " + base) if (not bare and path == first) else base
        prefix = ancestors_text(nodes, path, annotated) if path[0:1] == (chapter,) else ""
        text_b = (prefix + " " + base).strip()
        pa, pb = gold_presence(text_a, gold), gold_presence(text_b, gold)
        variant, text, pres = "A", text_a, pa
        if (pa is None or pa < gate) and pb is not None and pb >= gate:
            variant, text, pres = "B", text_b, pb
        pages = 1 + len(
            [
                d
                for d in _descendants(nodes, path)
                if not any(d[: len(a)] == a for a in annotated if a != path and len(a) > len(path))
            ]
        )
        reason = None
        if pres is None:
            reason = "no gold concepts to check the text against"
        elif pres < gate:
            reason = f"gold presence {pres:.1%} below the {gate:.0%} gate"
        out.append(
            Scraped(
                sid,
                path,
                nodes[path].title,
                text,
                variant,
                pres,
                pages,
                len(gold),
                words=len(text.split()),
                excluded_reason=reason,
                presence_a=pa,
                presence_b=pb,
            )
        )
    return out


def scrape_iir(
    annotation_ids_by_chapter: dict[int, list[str]],
    gold_by_section: dict[str, list[tuple[str, list[str]]]],
    fetch: Fetch,
    *,
    gate: float = GATE,
    toc_slug: str = "irbook.html",
) -> list[Scraped]:
    """Scrape every chapter in `annotation_ids_by_chapter` (chapter numbers from the book's TOC)."""
    toc = parse_toc(fetch(toc_slug))
    out: list[Scraped] = []
    for chapter in sorted(annotation_ids_by_chapter):
        out += scrape_chapter(
            chapter,
            toc[chapter],
            annotation_ids_by_chapter[chapter],
            gold_by_section,
            fetch,
            gate=gate,
        )
    return out


def build_test_split(
    raw_dir: Path,
    out_dir: Path,
    fetch: Fetch,
    *,
    dev_chapters: tuple[int, ...] = (1, 2, 3),
    gate: float = GATE,
) -> dict:
    """Scrape every annotated chapter outside the dev split, apply the gold-presence gate and write
    (all under out_dir, gitignored): iir_test_sections_v3.jsonl (sections that passed),
    iir_test_gold_concepts_v3.csv (gold of the sections that passed) and iir_scrape_report.json
    (per-section presence and variant, plus the excluded sections with reasons)."""
    import json

    from cumap.data.iir_face import _SECTION_ID_RE, parse_gold_concepts

    ann_dir = raw_dir / "IIR-dataset" / "annotation"
    ids_by_ch: dict[int, list[str]] = {}
    for f in sorted(ann_dir.glob("iir-*.csv")):
        sid = "iir_" + f.stem.removeprefix("iir-").replace(".", "_")
        m = _SECTION_ID_RE.match(sid)
        ch = int(m.group(1))
        if ch not in dev_chapters:
            ids_by_ch.setdefault(ch, []).append(sid)
    all_ids = [s for ids in ids_by_ch.values() for s in ids]
    gold_df = parse_gold_concepts(ann_dir, all_ids)
    gold_df = gold_df[gold_df["is_gold"]]
    gold_by_section: dict[str, list[tuple[str, list[str]]]] = {}
    for _, r in gold_df.iterrows():
        gold_by_section.setdefault(r["section_id"], []).append((r["concept"], list(r["aliases"])))

    toc_html = fetch("irbook.html")
    titles = dict(
        re.findall(r'<LI><A[^>]*HREF="([^"]+)"[^>]*>(.*?)</A>', toc_html, re.IGNORECASE | re.DOTALL)
    )
    toc = parse_toc(toc_html)
    scraped = scrape_iir(
        {
            c: [a.replace("_", "-", 1).replace("_", ".") for a in ids]
            for c, ids in ids_by_ch.items()
        },
        gold_by_section,
        fetch,
        gate=gate,
    )
    kept = [s for s in scraped if s.excluded_reason is None]
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "iir_test_sections_v3.jsonl").open("w", encoding="utf-8") as f:
        for i, s in enumerate(sorted(kept, key=lambda s: s.path)):
            ch = s.path[0]
            ct = _TAG.sub("", titles.get(toc[ch], f"Chapter {ch}")).strip()
            f.write(
                json.dumps(
                    {
                        "section_id": s.section_id,
                        "chapter_num": ch,
                        "chapter_title": ct,
                        "section_title": s.title or ct,
                        "heading_path": [ct] + ([s.title] if s.title else []),
                        "order_index": 1000 + i,
                        "text": s.text,
                        "n_pages": s.n_pages,
                        "variant": s.variant,
                    }
                )
                + "\n"
            )
    keep_ids = {s.section_id for s in kept}
    gold_df[gold_df["section_id"].isin(keep_ids)].to_csv(
        out_dir / "iir_test_gold_concepts_v3.csv", index=False
    )
    report = {
        "gate": gate,
        "n_sections": len(scraped),
        "n_kept": len(kept),
        "kept": [
            {
                "section_id": s.section_id,
                "words": s.words,
                "presence": s.presence,
                "variant": s.variant,
                "presence_a": s.presence_a,
                "presence_b": s.presence_b,
                "n_gold": s.n_gold,
                "pages": s.n_pages,
            }
            for s in scraped
            if s.excluded_reason is None
        ],
        "excluded": [
            {
                "section_id": s.section_id,
                "reason": s.excluded_reason,
                "presence_a": s.presence_a,
                "presence_b": s.presence_b,
                "n_gold": s.n_gold,
            }
            for s in scraped
            if s.excluded_reason
        ],
    }
    (out_dir / "iir_scrape_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
