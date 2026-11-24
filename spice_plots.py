"""Pure helpers that turn simulation series into inline SVG geometry.

No Flask, no file I/O, no ngspice here — only numbers in, strings out.
"""

from html import escape
import math

_DEFAULT_WIDTH = 720
_DEFAULT_HEIGHT = 380
_PAD = 8


def _validate_series(*series):
    if not series or any(len(s) == 0 for s in series):
        raise ValueError("series ต้องไม่ว่าง")
    for s in series:
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in s):
            raise ValueError("series ต้องเป็นจำนวนจริงที่จำกัด (finite)")
    if any(len(s) != len(series[0]) for s in series):
        raise ValueError("series ทุกช่องต้องมีความยาวเท่ากัน")


def polyline_points(xs, ys, width, height, pad, x_range, y_range):
    """Map (x, y) data into SVG user-space points, flipping the y axis."""
    _validate_series(xs, ys)
    x0, x1 = x_range
    y0, y1 = y_range
    x_span = x1 - x0
    y_span = y1 - y0
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    points = []
    for x, y in zip(xs, ys):
        fx = 0.5 if x_span == 0 else (x - x0) / x_span
        fy = 0.5 if y_span == 0 else (y - y0) / y_span
        px = pad + fx * inner_w
        py = height - pad - fy * inner_h
        points.append(f"{px:g},{py:g}")
    return " ".join(points)


def nice_range(values, pad_fraction=0.1):
    """Return a padded (min, max); equal values get a symmetric band."""
    _validate_series(values)
    lo, hi = min(values), max(values)
    if lo == hi:
        delta = max(abs(lo) * pad_fraction, 1.0)
        return lo - delta, hi + delta
    delta = (hi - lo) * pad_fraction
    return lo - delta, hi + delta


def _axis_ticks(lo, hi, count=5):
    step = (hi - lo) / (count - 1)
    return [lo + i * step for i in range(count)]


def _fmt(value):
    if abs(value) >= 1000 or (0 < abs(value) < 0.01):
        return f"{value:.2e}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _panel(xs, ys, x_range, y_range, x_label, y_label, color, box, log_x=False):
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    pad = 8
    # Shift geometry into the panel box by translating the polyline group.
    local = polyline_points(
        xs, ys, width, height, pad, x_range, y_range
    )
    parts = [
        f'<g transform="translate({left} {top})">',
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        'fill="#f8fafc" stroke="#cbd5e1"/>',
    ]
    for tick in _axis_ticks(*y_range, count=5):
        _, py = polyline_points(
            [y_range[0]], [tick], width, height, pad, y_range, y_range
        ).split()[0].split(",")
        parts.append(
            f'<line x1="0" y1="{py}" x2="{width}" y2="{py}" '
            'stroke="#e2e8f0"/>'
        )
        parts.append(
            f'<text x="2" y="{float(py) - 3:.2f}" font-size="9" fill="#475569">'
            f"{escape(_fmt(tick))}</text>"
        )
    for tick in _axis_ticks(*x_range, count=5):
        px, _ = polyline_points(
            [tick], [y_range[0]], width, height, pad, x_range, y_range
        ).split()[0].split(",")
        parts.append(
            f'<line x1="{px}" y1="{height}" x2="{px}" y2="0" '
            'stroke="#e2e8f0"/>'
        )
        label = f"1e{tick:.0f}" if log_x else _fmt(tick)
        parts.append(
            f'<text x="{float(px) - 8:.2f}" y="{height + 12}" font-size="9" '
            f'fill="#475569">{escape(label)}</text>'
        )
    parts.append(
        f'<polyline points="{local}" fill="none" stroke="{color}" '
        'stroke-width="2" stroke-linejoin="round"/>'
    )
    parts.append(f'<text x="2" y="-4" font-size="10" fill="#1e293b">{escape(y_label)}</text>')
    parts.append(
        f'<text x="{width}" y="{height + 24}" text-anchor="end" font-size="10" '
        f'fill="#1e293b">{escape(x_label)}</text>'
    )
    parts.append("</g>")
    return "\n".join(parts)


def bode_svg(freq, gain_db, phase_deg):
    """Full SVG with a gain panel (dB) and a phase panel (deg) vs log Hz."""
    _validate_series(freq, gain_db, phase_deg)
    if any(f <= 0 for f in freq):
        raise ValueError("freq ต้องมากกว่า 0 สำหรับแกน log")
    log_freq = [math.log10(f) for f in freq]
    fx0, fx1 = min(log_freq), max(log_freq)
    if fx0 == fx1:
        fx0, fx1 = fx0 - 0.5, fx1 + 0.5
    x_range = (fx0, fx1)
    gain_box = (62, 34, _DEFAULT_WIDTH - 16, 168)
    phase_box = (62, 232, _DEFAULT_WIDTH - 16, 348)
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_DEFAULT_WIDTH} '
            f'{_DEFAULT_HEIGHT}" role="img" aria-label="Bode plot">',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            _panel(
                log_freq, gain_db, x_range, nice_range(gain_db),
                "Frequency (Hz)", "Gain (dB)", "#2563eb", gain_box, log_x=True,
            ),
            _panel(
                log_freq, phase_deg, x_range, nice_range(phase_deg),
                "Frequency (Hz)", "Phase (deg)", "#dc2626", phase_box, log_x=True,
            ),
            "</svg>",
        ]
    )


def wave_svg(time, vin, vout):
    """Full SVG of Vin and Vout vs time; time is displayed in milliseconds."""
    _validate_series(time, vin, vout)
    time_ms = [t * 1000.0 for t in time]
    x_range = nice_range(time_ms)
    y_range = nice_range(list(vin) + list(vout))
    box = (62, 34, _DEFAULT_WIDTH - 16, 250)
    width = box[2] - box[0]
    height = box[3] - box[1]
    panel = _panel(
        time_ms, vin, x_range, y_range, "Time (ms)", "Voltage (V)",
        "#2563eb", box,
    )
    vout_points = polyline_points(
        time_ms, vout, width, height, 8, x_range, y_range
    )
    panel = panel.replace(
        "</g>",
        f'<polyline data-series="vout" points="{vout_points}" fill="none" '
        'stroke="#dc2626" stroke-width="2" stroke-linejoin="round"/></g>',
    ).replace(
        '<polyline points=', '<polyline data-series="vin" points=', 1
    )
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_DEFAULT_WIDTH} 300" '
            'role="img" aria-label="Transient waveform">',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            panel,
            '<text x="62" y="286" font-size="11" fill="#1e293b">'
            'Vin (blue) / Vout (red)</text>',
            "</svg>",
        ]
    )
