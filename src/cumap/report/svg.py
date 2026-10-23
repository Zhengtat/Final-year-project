"""Minimal dependency-free SVG chart primitives (bars) used both inline in the HTML report
and as standalone files under reports/demo/figures/. Colours are CSS custom properties with
light/dark values from the dataviz reference palette; each <svg> carries its own <style> so
a standalone file themes itself from the OS setting.
"""

from __future__ import annotations

from html import escape

from cumap.report.provenance import Provenance

# categorical slots (light, dark) in fixed order -- see dataviz references/palette.md
SLOTS = [
    ("#2a78d6", "#3987e5"),
    ("#eb6834", "#d95926"),
    ("#1baf7a", "#199e70"),
    ("#eda100", "#c98500"),
    ("#e87ba4", "#d55181"),
    ("#008300", "#008300"),
    ("#4a3aa7", "#9085e9"),
    ("#e34948", "#e66767"),
]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}


def theme_css(selector: str = "svg.cv") -> str:
    light = "".join(f"--s{i + 1}:{l};" for i, (l, _) in enumerate(SLOTS))
    dark = "".join(f"--s{i + 1}:{d};" for i, (_, d) in enumerate(SLOTS))
    status = "".join(f"--{k}:{v};" for k, v in STATUS.items())
    return (
        f"{selector}{{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e3e2de;--ref:#8a8985;"
        f"{light}{status}}}"
        f"@media (prefers-color-scheme:dark){{{selector}{{--bg:#1a1a19;--ink:#ffffff;"
        f"--ink2:#c3c2b7;--grid:#383835;--ref:#8a897f;{dark}}}}}"
    )


_CSS = (
    theme_css() + "svg.cv{background:var(--bg);font-family:system-ui,sans-serif}"
    "svg.cv text{fill:var(--ink)}svg.cv .t2{fill:var(--ink2)}"
    "svg.cv .ttl{font-size:14px;font-weight:600}svg.cv .sm{font-size:11px}"
    "svg.cv .grid{stroke:var(--grid);stroke-width:1}svg.cv .ax{stroke:var(--ink2);stroke-width:1}"
)


def slot(i: int) -> str:
    return f"var(--s{i + 1})"


def wrap_svg(width: int, height: int, body: str, title: str, footer: str) -> str:
    """Adds title + provenance footer (two lines' worth of height are reserved by callers)."""
    return (
        f'<svg class="cv" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{escape(title)}">'
        f"<style>{_CSS}</style>"
        f'<text class="ttl" x="12" y="20">{escape(title)}</text>{body}'
        f"{_footer_lines(footer, height)}</svg>"
    )


def _footer_lines(footer: str, height: int) -> str:
    """Two lines (run/prompts/model, then date/labels) so it never runs off narrow charts."""
    parts = footer.split(" · ")
    first, second = " · ".join(parts[:3]), " · ".join(parts[3:])
    return (
        f'<text class="t2 sm" x="12" y="{height - 20}">{escape(first)}</text>'
        f'<text class="t2 sm" x="12" y="{height - 6}">{escape(second)}</text>'
    )


def _legend(names: list[str], x: int, y: int, colors: list[str]) -> str:
    out, cx = [], x
    for name, colour in zip(names, colors, strict=True):
        out.append(f'<rect x="{cx}" y="{y - 9}" width="10" height="10" rx="2" fill="{colour}"/>')
        out.append(f'<text class="sm" x="{cx + 14}" y="{y}">{escape(name)}</text>')
        cx += 24 + 6.2 * len(name)
    return "".join(out)


def grouped_bar_svg(
    title: str,
    categories: list[str],
    series: dict[str, list[float]],
    *,
    provenance: Provenance,
    label_source: str,
    ymax: float | None = None,
    value_fmt: str = "{:.2f}",
    width: int = 640,
    height: int = 320,
    series_colors: dict[str, int] | None = None,
) -> str:
    footer = provenance.footer(label_source)
    names = list(series)
    left, right, top, bottom = 44, 12, 52, 58
    pw, ph = width - left - right, height - top - bottom
    top_v = (
        ymax if ymax is not None else max((max(v) for v in series.values() if v), default=1) * 1.1
    )
    top_v = top_v or 1
    body = []
    for g in range(5):
        v = top_v * g / 4
        y = top + ph - ph * g / 4
        body.append(
            f'<line class="grid" x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}"/>'
        )
        body.append(
            f'<text class="t2 sm" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{v:.2g}</text>'
        )
    gw = pw / max(len(categories), 1)
    bw = min(28, (gw * 0.8) / max(len(names), 1))
    colors = [slot((series_colors or {}).get(n, i)) for i, n in enumerate(names)]
    for ci, cat in enumerate(categories):
        gx = left + gw * ci + gw / 2 - bw * len(names) / 2
        for si, name in enumerate(names):
            val = series[name][ci]
            h = ph * val / top_v
            x = gx + si * bw
            tip = escape(f"{name} · {cat}: {value_fmt.format(val)}")
            body.append(
                f'<g><title>{tip}</title><rect x="{x + 1:.1f}" y="{top + ph - h:.1f}" '
                f'width="{bw - 2:.1f}" height="{max(h, 0):.1f}" rx="3" fill="{colors[si]}"/>'
                f'<text class="sm" x="{x + bw / 2:.1f}" y="{top + ph - h - 4:.1f}" '
                f'text-anchor="middle">{value_fmt.format(val)}</text></g>'
            )
        body.append(
            f'<text class="t2 sm" x="{left + gw * ci + gw / 2:.1f}" y="{top + ph + 16}" '
            f'text-anchor="middle">{escape(cat)}</text>'
        )
    body.append(
        f'<line class="ax" x1="{left}" x2="{width - right}" y1="{top + ph}" y2="{top + ph}"/>'
    )
    if len(names) >= 2:
        body.append(_legend(names, left, 38, colors))
    return wrap_svg(width, height, "".join(body), title, footer)


def hbar_svg(
    title: str,
    items: list[tuple[str, float, int | None]],
    *,
    provenance: Provenance,
    label_source: str,
    value_fmt: str = "{:.2f}",
    xmax: float | None = None,
    width: int = 640,
    label_w: int = 190,
    note: str | None = None,
) -> str:
    """items: (label, value, slot index | None for a neutral 'reference' bar)."""
    footer = provenance.footer(label_source)
    row_h, top = 26, 40
    height = top + row_h * len(items) + (44 if note else 28) + 14
    top_v = xmax or max((v for _, v, _ in items), default=1) * 1.12 or 1
    pw = width - label_w - 60
    body = []
    for i, (label, val, si) in enumerate(items):
        y = top + i * row_h
        w = pw * val / top_v
        fill = "var(--ref)" if si is None else slot(si)
        tip = escape(f"{label}: {value_fmt.format(val)}")
        body.append(
            f'<g><title>{tip}</title><text class="sm" x="{label_w - 8}" y="{y + 14}" '
            f'text-anchor="end">{escape(label)}</text>'
            f'<rect x="{label_w}" y="{y + 3}" width="{max(w, 0):.1f}" height="16" rx="3" fill="{fill}"/>'
            f'<text class="sm" x="{label_w + w + 6:.1f}" y="{y + 15}">{value_fmt.format(val)}</text></g>'
        )
    if note:
        body.append(f'<text class="t2 sm" x="12" y="{height - 38}">{escape(note)}</text>')
    return wrap_svg(width, height, "".join(body), title, footer)


def stacked_bar_svg(
    title: str,
    categories: list[str],
    series: dict[str, list[float]],
    *,
    provenance: Provenance,
    label_source: str,
    value_fmt: str = "{:.0f}",
    width: int = 660,
    height: int = 320,
    series_colors: dict[str, int] | None = None,
) -> str:
    """Vertical stacked bars, a 2px surface gap between segments, legend for >= 2 series."""
    footer = provenance.footer(label_source)
    names = list(series)
    left, right, top, bottom = 44, 12, 52, 58
    pw, ph = width - left - right, height - top - bottom
    totals = [sum(series[n][i] for n in names) for i in range(len(categories))]
    top_v = (max(totals) if totals else 1) * 1.1 or 1
    body = []
    for g in range(5):
        v = top_v * g / 4
        y = top + ph - ph * g / 4
        body.append(
            f'<line class="grid" x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}"/>'
        )
        body.append(
            f'<text class="t2 sm" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{v:.3g}</text>'
        )
    gw = pw / max(len(categories), 1)
    bw = min(56, gw * 0.6)
    colors = [slot((series_colors or {}).get(n, i)) for i, n in enumerate(names)]
    for ci, cat in enumerate(categories):
        x = left + gw * ci + (gw - bw) / 2
        y = top + ph
        for si, name in enumerate(names):
            val = series[name][ci]
            h = ph * val / top_v
            if val <= 0:
                continue
            tip = escape(f"{name} · {cat}: {value_fmt.format(val)}")
            body.append(
                f'<g><title>{tip}</title><rect x="{x:.1f}" y="{y - h + 1:.1f}" width="{bw:.1f}" '
                f'height="{max(h - 2, 0):.1f}" rx="3" fill="{colors[si]}"/></g>'
            )
            y -= h
        body.append(
            f'<text class="t2 sm" x="{left + gw * ci + gw / 2:.1f}" y="{top + ph + 16}" '
            f'text-anchor="middle">{escape(cat)}</text>'
        )
        body.append(
            f'<text class="sm" x="{left + gw * ci + gw / 2:.1f}" y="{y - 4:.1f}" '
            f'text-anchor="middle">{value_fmt.format(totals[ci])}</text>'
        )
    body.append(
        f'<line class="ax" x1="{left}" x2="{width - right}" y1="{top + ph}" y2="{top + ph}"/>'
    )
    if len(names) >= 2:
        body.append(_legend(names, left, 38, colors))
    return wrap_svg(width, height, "".join(body), title, footer)
