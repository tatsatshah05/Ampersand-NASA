"""Small chart and image-panel helpers for the verify scripts, drawn with Pillow only.

matplotlib is not among the project's dependencies, so these few functions stand in for it.
"""
from __future__ import annotations

import numpy as np
from astropy.time import Time
from PIL import Image, ImageDraw, ImageFont

BLACK, GREY, LIGHT = (20, 20, 20), (120, 120, 120), (225, 225, 225)
RED, BLUE, GREEN = (214, 69, 65), (52, 110, 200), (40, 150, 90)
ORANGE, PURPLE, TEAL, BROWN = (230, 140, 30), (140, 80, 190), (30, 160, 170), (140, 90, 50)


def font(size: int = 13):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                       # very old Pillow: fixed-size bitmap font
        return ImageFont.load_default()


def _nice_ticks(lo: float, hi: float, n: int = 6) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / n
    mag = 10 ** np.floor(np.log10(raw))
    step = min((s for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=10) * mag
    first = np.ceil(lo / step) * step
    return [float(v) for v in np.arange(first, hi + step * 1e-9, step)]


def _log_ticks(lo: float, hi: float) -> list[float]:
    """Tick positions (as log10 values) at 1, 2, 5 times powers of ten between 10**lo and 10**hi."""
    out = []
    for decade in range(int(np.floor(lo)), int(np.ceil(hi)) + 1):
        for m in (1, 2, 5) if hi - lo < 2.5 else (1,):
            v = decade + np.log10(m)
            if lo - 1e-9 <= v <= hi + 1e-9:
                out.append(float(v))
    return out


def _fmt(v: float) -> str:
    if abs(v) < 1e-12:
        return "0"
    if abs(v) >= 1000:
        return f"{v:.0f}" if abs(v - round(v)) < 1e-6 * abs(v) else f"{v:.1f}"
    if abs(v) < 0.01:
        return f"{v:.2g}"
    return f"{v:.3g}" if abs(v) < 10 else f"{v:.4g}"


class Chart:
    """One scatter/line chart. Add series, then call render()."""

    def __init__(self, title: str = "", xlabel: str = "", ylabel: str = "", width: int = 1100, height: int = 460,
                 logy: bool = False, logx: bool = False, xdate: bool = False, legend_width: int = 250,
                 xlim: tuple[float, float] | None = None, ylim: tuple[float, float] | None = None,
                 invert_y: bool = False):
        self.title, self.xlabel, self.ylabel = title, xlabel, ylabel
        self.w, self.h, self.logy, self.logx, self.xdate = width, height, logy, logx, xdate
        self.legend_width, self.xlim, self.ylim, self.invert_y = legend_width, xlim, ylim, invert_y
        self.series: list[dict] = []
        self.hlines: list[tuple[float, tuple, str | None]] = []
        self.vlines: list[tuple[float, tuple, str | None]] = []
        self.spans: list[tuple[float, float, tuple]] = []
        self.notes: list[tuple[float, float, str, tuple]] = []

    def scatter(self, x, y, yerr=None, color=BLUE, label: str | None = None, marker: str = "o",
                hollow: bool = False, size: int = 4, xerr=None) -> None:
        self.series.append({"kind": "scatter", "x": np.asarray(x, float), "y": np.asarray(y, float),
                            "yerr": None if yerr is None else np.asarray(yerr, float),
                            "xerr": None if xerr is None else np.asarray(xerr, float), "color": color,
                            "label": label, "marker": marker, "hollow": hollow, "size": size})

    def line(self, x, y, color=BLACK, label: str | None = None, width: int = 2) -> None:
        self.series.append({"kind": "line", "x": np.asarray(x, float), "y": np.asarray(y, float), "color": color,
                            "label": label, "width": width})

    def hline(self, y: float, color=GREY, label: str | None = None) -> None:
        self.hlines.append((y, color, label))

    def vline(self, x: float, color=GREY, label: str | None = None) -> None:
        self.vlines.append((x, color, label))

    def span(self, x0: float, x1: float, color=(240, 240, 225)) -> None:
        self.spans.append((x0, x1, color))

    def note(self, x: float, y: float, text: str, color=BLACK) -> None:
        self.notes.append((x, y, text, color))

    def _range(self):
        xs = [s["x"][np.isfinite(s["x"])] for s in self.series if len(s["x"])]
        ys = []
        for s in self.series:
            y = s["y"][np.isfinite(s["y"])]
            if self.logy:
                y = y[y > 0]
            ys.append(y)
        ys += [np.array([v]) for v, _, _ in self.hlines if not self.logy or v > 0]
        x = np.concatenate(xs) if xs else np.array([0.0, 1.0])
        y = np.concatenate(ys) if ys else np.array([0.1, 1.0])
        tx = np.log10(x[x > 0]) if self.logx else x
        ty = np.log10(y) if self.logy else y
        x0, x1 = (tx.min(), tx.max()) if self.xlim is None else (
            (np.log10(self.xlim[0]), np.log10(self.xlim[1])) if self.logx else self.xlim)
        y0, y1 = (ty.min(), ty.max()) if self.ylim is None else (
            (np.log10(self.ylim[0]), np.log10(self.ylim[1])) if self.logy else self.ylim)
        if self.xlim is None:
            pad = 0.04 * ((x1 - x0) or 1.0)
            x0, x1 = x0 - pad, x1 + pad
        if self.ylim is None:
            pad = 0.08 * ((y1 - y0) or 1.0)
            y0, y1 = y0 - pad, y1 + pad
        return x0, x1, y0, y1

    def render(self) -> Image.Image:
        left, right, top, bottom = 78, self.legend_width, 34, 52
        x0, x1, y0, y1 = self._range()
        pw, ph = self.w - left - right, self.h - top - bottom

        def px(x):
            v = np.log10(np.maximum(x, 1e-300)) if self.logx else x
            return left + (v - x0) / (x1 - x0) * pw

        def py(y):
            v = np.log10(np.maximum(y, 1e-300)) if self.logy else y
            frac = (v - y0) / (y1 - y0)
            return top + frac * ph if self.invert_y else top + ph - frac * ph

        im = Image.new("RGB", (self.w, self.h), (255, 255, 255))
        d = ImageDraw.Draw(im)
        f, fs, fb = font(13), font(12), font(14)
        for a, b, col in self.spans:
            d.rectangle([max(px(a), left), top, min(px(b), left + pw), top + ph], fill=col)
        # grid and ticks
        if self.xdate:
            t0, t1 = Time(x0, format="mjd").datetime, Time(x1, format="mjd").datetime
            months = []
            y_, m_ = t0.year, t0.month
            while (y_, m_) <= (t1.year, t1.month):
                months.append((y_, m_))
                m_ += 1
                if m_ == 13:
                    y_, m_ = y_ + 1, 1
            every = max(1, int(np.ceil(len(months) / 9)))
            for i, (yy, mm) in enumerate(months):
                mjd = Time(f"{yy}-{mm:02d}-01").mjd
                if not x0 <= mjd <= x1:
                    continue
                xx = px(mjd)
                d.line([xx, top, xx, top + ph], fill=LIGHT)
                if i % every == 0:
                    d.line([xx, top + ph, xx, top + ph + 5], fill=BLACK)
                    d.text((xx - 24, top + ph + 8), f"{yy}-{mm:02d}", fill=BLACK, font=fs)
        else:
            ticks = _log_ticks(x0, x1) if self.logx else _nice_ticks(x0, x1, 8)
            for v in ticks:
                xx = left + (v - x0) / (x1 - x0) * pw
                label = _fmt(10 ** v if self.logx else v)
                d.line([xx, top, xx, top + ph], fill=LIGHT)
                d.line([xx, top + ph, xx, top + ph + 5], fill=BLACK)
                d.text((xx - 3.3 * len(label), top + ph + 8), label, fill=BLACK, font=fs)
        for v in (_log_ticks(y0, y1) if self.logy else _nice_ticks(y0, y1, 6)):
            frac = (v - y0) / (y1 - y0)
            yy = top + frac * ph if self.invert_y else top + ph - frac * ph
            d.line([left, yy, left + pw, yy], fill=LIGHT)
            d.line([left - 5, yy, left, yy], fill=BLACK)
            d.text((6, yy - 7), _fmt(10 ** v if self.logy else v), fill=BLACK, font=fs)
        d.rectangle([left, top, left + pw, top + ph], outline=BLACK)
        d.text((left, 8), self.title, fill=BLACK, font=fb)
        d.text((left + pw // 2 - 4 * len(self.xlabel), self.h - 22), self.xlabel, fill=BLACK, font=f)
        if self.ylabel:
            tmp = Image.new("RGBA", (max(8 * len(self.ylabel), 10), 18), (255, 255, 255, 0))
            ImageDraw.Draw(tmp).text((0, 0), self.ylabel, fill=BLACK, font=f)
            rot = tmp.rotate(90, expand=True)
            im.paste(rot, (56, top + ph // 2 - rot.height // 2), rot)

        legend = []
        for y, col, label in self.hlines:
            yy = float(py(y))
            if top <= yy <= top + ph:
                for xs in range(left, left + pw, 10):
                    d.line([xs, yy, xs + 5, yy], fill=col)
            if label:
                legend.append(("dash", col, label, False))
        for x, col, label in self.vlines:
            xx = float(px(x))
            if left <= xx <= left + pw:
                for ys in range(top, top + ph, 10):
                    d.line([xx, ys, xx, ys + 5], fill=col)
            if label:
                legend.append(("dash", col, label, False))
        for s in self.series:
            col = s["color"]
            if s["kind"] == "line":
                pts = [(float(px(a)), float(py(b))) for a, b in zip(s["x"], s["y"], strict=True)
                       if np.isfinite(a) and np.isfinite(b)]
                pts = [p for p in pts if left - 1 <= p[0] <= left + pw + 1]
                if len(pts) > 1:
                    d.line(pts, fill=col, width=s["width"])
                if s["label"]:
                    legend.append(("line", col, s["label"], False))
                continue
            r = s["size"]
            for i, (a, b) in enumerate(zip(s["x"], s["y"], strict=True)):
                if not (np.isfinite(a) and np.isfinite(b)) or (self.logy and b <= 0):
                    continue
                xx, yy = float(px(a)), float(py(b))
                if not (left - 1 <= xx <= left + pw + 1 and top - 1 <= yy <= top + ph + 1):
                    continue
                if s["yerr"] is not None and np.isfinite(s["yerr"][i]):
                    lo, hi = b - s["yerr"][i], b + s["yerr"][i]
                    if not self.logy or lo > 0:
                        ya, yb = float(py(lo)), float(py(hi))
                        d.line([xx, max(min(ya, yb), top), xx, min(max(ya, yb), top + ph)], fill=col)
                if s["xerr"] is not None and np.isfinite(s["xerr"][i]) and not self.logx:
                    xa, xb = float(px(a - s["xerr"][i])), float(px(a + s["xerr"][i]))
                    d.line([max(min(xa, xb), left), yy, min(max(xa, xb), left + pw), yy], fill=col)
                _marker(d, xx, yy, r, col, s["marker"], s["hollow"])
            if s["label"]:
                legend.append((s["marker"], col, s["label"], s["hollow"]))
        for x, y, text, col in self.notes:
            d.text((float(px(x)), float(py(y))), text, fill=col, font=fs)
        ly = top + 4
        for kind, col, label, hollow in legend:
            lx = left + pw + 12
            if kind == "line":
                d.line([lx, ly + 7, lx + 16, ly + 7], fill=col, width=2)
            elif kind == "dash":
                d.line([lx, ly + 7, lx + 6, ly + 7], fill=col)
                d.line([lx + 10, ly + 7, lx + 16, ly + 7], fill=col)
            else:
                _marker(d, lx + 8, ly + 7, 4, col, kind, hollow)
            for k, part in enumerate(_wrap(label, max(10, (self.legend_width - 40) // 7))):
                d.text((lx + 22, ly + 15 * k), part, fill=BLACK, font=fs)
                last = k
            ly += 15 * (last + 1) + 6
        return im


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur] if cur else lines or [""]


def _marker(d: ImageDraw.ImageDraw, x: float, y: float, r: int, col, kind: str, hollow: bool) -> None:
    box = [x - r, y - r, x + r, y + r]
    if kind == "s":
        d.rectangle(box, outline=col, fill=None if hollow else col)
    elif kind == "x":
        d.line([x - r, y - r, x + r, y + r], fill=col, width=2)
        d.line([x - r, y + r, x + r, y - r], fill=col, width=2)
    elif kind == "^":
        d.polygon([(x, y - r), (x - r, y + r), (x + r, y + r)], outline=col, fill=None if hollow else col)
    else:
        d.ellipse(box, outline=col, fill=None if hollow else col)


def stack_vertical(images: list[Image.Image], pad: int = 6) -> Image.Image:
    w = max(im.width for im in images)
    out = Image.new("RGB", (w, sum(im.height for im in images) + pad * (len(images) - 1)), (255, 255, 255))
    y = 0
    for im in images:
        out.paste(im, (0, y))
        y += im.height + pad
    return out


def stack_horizontal(images: list[Image.Image], pad: int = 6, bg=(255, 255, 255)) -> Image.Image:
    h = max(im.height for im in images)
    out = Image.new("RGB", (sum(im.width for im in images) + pad * (len(images) - 1), h), bg)
    x = 0
    for im in images:
        out.paste(im, (x, 0))
        x += im.width + pad
    return out


def image_panel(arr: np.ndarray, vmin: float, vmax: float, scale: int = 6, title: str = "",
                marks: list[dict] | None = None, diverging: bool = False, caption: str = "") -> Image.Image:
    """Greyscale panel of a sky image whose row 0 is south (it is flipped so north is up).

    marks: dicts with x, y (array pixel coordinates), kind ("circle", "cross", "plus", "box"), color,
    r (radius in array pixels) and optional label. No-data pixels are drawn dark purple.
    """
    a = np.asarray(arr, float)
    norm = np.clip((a - vmin) / (vmax - vmin), 0, 1)
    ny, nx = a.shape
    if diverging:                                   # blue (negative) - white (zero) - red (positive)
        rgb = np.zeros((ny, nx, 3))
        lo, hi = norm < 0.5, norm >= 0.5
        rgb[lo] = np.stack([2 * norm[lo], 2 * norm[lo], np.ones(lo.sum())], axis=-1)
        rgb[hi] = np.stack([np.ones(hi.sum()), 2 - 2 * norm[hi], 2 - 2 * norm[hi]], axis=-1)
    else:
        rgb = np.stack([norm] * 3, axis=-1)
    rgb[~np.isfinite(a)] = (0.25, 0.0, 0.3)
    im = Image.fromarray((rgb[::-1] * 255).astype("uint8"), "RGB").resize((nx * scale, ny * scale), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for m in marks or []:
        x, y = (m["x"] + 0.5) * scale, (ny - 1 - m["y"] + 0.5) * scale
        r, col = m.get("r", 3) * scale, m.get("color", (255, 230, 0))
        kind = m.get("kind", "circle")
        if kind == "circle":
            d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=2)
        elif kind == "box":
            d.rectangle([x - r, y - r, x + r, y + r], outline=col, width=2)
        elif kind == "plus":
            g = 0.45 * r
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                d.line([x + dx * g, y + dy * g, x + dx * r, y + dy * r], fill=col, width=2)
        else:
            d.line([x - r, y - r, x + r, y + r], fill=col, width=2)
            d.line([x - r, y + r, x + r, y - r], fill=col, width=2)
        if m.get("label"):
            d.text((x + r + 3, y - 8), m["label"], fill=col, font=font(12))
    head = 20 if title else 0
    foot = 18 if caption else 0
    out = Image.new("RGB", (im.width, im.height + head + foot), (255, 255, 255))
    out.paste(im, (0, head))
    dd = ImageDraw.Draw(out)
    if title:
        dd.text((2, 2), title, fill=BLACK, font=font(13))
    if caption:
        dd.text((2, im.height + head + 2), caption, fill=BLACK, font=font(12))
    return out


def caption_block(width: int, lines: list[str], size: int = 12) -> Image.Image:
    """White strip with a few lines of explanatory text, to put under a figure."""
    out = Image.new("RGB", (width, 5 + (size + 5) * len(lines)), (255, 255, 255))
    d = ImageDraw.Draw(out)
    for k, text in enumerate(lines):
        d.text((4, 2 + (size + 5) * k), text, fill=BLACK, font=font(size))
    return out


def save(im: Image.Image, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, optimize=True)
    print(f"  wrote {path} ({path.stat().st_size // 1024} kB, {im.width}x{im.height})")
