"""Minimal, dependency-free SVG chart generator in the project's Electric-Blue theme.
GitHub-safe: presentation attributes only (no <style>, no scripts, no external fonts)."""

from __future__ import annotations

INK = "#0F172A"
MUTED = "#64748B"
LINE = "#E2E8F0"
ACCENT = "#0052FF"
ACCENT2 = "#4D7CFF"
GREEN = "#16A34A"
RED = "#DC2626"
AMBER = "#B45309"
FONT = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"


def _defs() -> str:
    return (
        '<defs>'
        f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT2}"/>'
        f'</linearGradient>'
        f'<linearGradient id="gv" x1="0" y1="1" x2="0" y2="0">'
        f'<stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT2}"/>'
        f'</linearGradient>'
        '</defs>'
    )


def _text(x, y, s, size=13, color=INK, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{s}</text>'
    )


def hbar_chart(title, items, *, unit="%", max_value=100.0, width=680, subtitle="",
               value_fmt=None) -> str:
    """Horizontal bars. items = [(label, value), ...]. value_fmt overrides the label."""
    pad_l, pad_r, pad_t = 200, 70, 64 if subtitle else 48
    row_h, gap = 30, 12
    h = pad_t + len(items) * (row_h + gap) + 24
    bar_w = width - pad_l - pad_r
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {h}" width="{width}" '
        f'height="{h}"><rect width="{width}" height="{h}" fill="#FFFFFF" rx="14"/>',
        _defs(),
        _text(24, 30, title, 17, INK, 700),
    ]
    if subtitle:
        parts.append(_text(24, 50, subtitle, 12.5, MUTED))
    for i, (label, value) in enumerate(items):
        y = pad_t + i * (row_h + gap)
        w = max(2, bar_w * (float(value) / max_value)) if max_value else 2
        parts.append(_text(pad_l - 12, y + row_h / 2 + 4, label, 13, INK, 500, "end"))
        track = f'<rect x="{pad_l}" y="{y}" width="{bar_w}" height="{row_h}" rx="6" fill="{LINE}"/>'
        parts.append(track)
        parts.append(
            f'<rect x="{pad_l}" y="{y}" width="{w:.1f}" height="{row_h}" rx="6" fill="url(#g)"/>'
        )
        vlabel = value_fmt.format(value) if value_fmt else f"{value:g}{unit}"
        parts.append(_text(pad_l + w + 8, y + row_h / 2 + 4, vlabel, 12.5, INK, 600))
    parts.append("</svg>")
    return "".join(parts)


def grouped_bar_chart(title, groups, series, *, unit="", width=680, max_value=None,
                      subtitle="", value_fmt="{:g}") -> str:
    """Vertical grouped bars. groups=['A','B'], series=[(name,color,[v_A,v_B]), ...]."""
    pad_l, pad_r, pad_t, pad_b = 56, 24, 66 if subtitle else 52, 56
    h = 380
    plot_w = width - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    if max_value is None:
        max_value = max((v for _, _, vs in series for v in vs), default=1) * 1.18 or 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {h}" width="{width}" '
        f'height="{h}"><rect width="{width}" height="{h}" fill="#FFFFFF" rx="14"/>',
        _defs(),
        _text(24, 30, title, 17, INK, 700),
    ]
    if subtitle:
        parts.append(_text(24, 50, subtitle, 12.5, MUTED))
    # gridlines
    for k in range(5):
        gy = pad_t + plot_h * k / 4
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width-pad_r}" y2="{gy:.1f}" '
                     f'stroke="{LINE}" stroke-width="1"/>')
        parts.append(_text(pad_l - 8, gy + 4, value_fmt.format(max_value * (4 - k) / 4), 11,
                           MUTED, 400, "end"))
    n_groups = len(groups)
    gwidth = plot_w / n_groups
    nser = len(series)
    bw = min(46, (gwidth * 0.62) / max(1, nser))
    for gi, gname in enumerate(groups):
        gx0 = pad_l + gi * gwidth
        cluster_w = bw * nser + (nser - 1) * 6
        start = gx0 + (gwidth - cluster_w) / 2
        for si, (_name, color, vals) in enumerate(series):
            v = vals[gi]
            bh = plot_h * (float(v) / max_value)
            x = start + si * (bw + 6)
            y = pad_t + plot_h - bh
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                         f'rx="5" fill="{color}"/>')
            lbl = value_fmt.format(v) + unit
            parts.append(_text(x + bw / 2, y - 6, lbl, 11, INK, 600, "middle"))
        parts.append(_text(gx0 + gwidth / 2, h - 30, gname, 12.5, INK, 600, "middle"))
    # legend
    lx = pad_l
    for _name, color, _vals in series:
        parts.append(f'<rect x="{lx}" y="{h-16}" width="11" height="11" rx="3" fill="{color}"/>')
        parts.append(_text(lx + 16, h - 6, _name, 11.5, MUTED, 500))
        lx += 26 + len(_name) * 7
    parts.append("</svg>")
    return "".join(parts)
