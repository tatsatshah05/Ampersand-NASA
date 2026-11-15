"""One small picture strip for a watchlist candidate, built from cutouts already on disk.

The strip shows each visit side by side on one brightness scale, then the last visit minus
the first, about 80 arcseconds across, north up (east left), centred on the candidate, for
its best detector. It is made with the viewer's own steps (`pipeline.make_grid`,
`prepare_cutout`, `Stacker`, `to_png`, `to_difference_png`), so it shows what the viewer
would show. It never downloads: if the patch's cutouts are not on disk the answer is
`None`, and the page says there is no picture. Strips are cached on disk.
"""
from __future__ import annotations

import hashlib
import tempfile
import threading
from pathlib import Path
from typing import Any

import numpy as np
from astropy.time import Time
from PIL import Image, ImageDraw

from . import pipeline, s3fetch, search, spherex

SIZE_ARCSEC = 80.0
SCALE = 6                      # each 2 arcsec grid pixel is drawn this many screen pixels wide
MIN_VISITS = 2
VERSION = 1
_build_lock = threading.Lock()


def pictures_dir() -> Path:
    return spherex.CACHE / "watchlist" / "pictures"


def _cutout_on_disk(exp: dict[str, Any], ra: float, dec: float, size_deg: float) -> Path | None:
    """Where this cutout is if a search already has it (shared cache first, then the search's own folder)."""
    for path in (spherex._cutout_path(exp, ra, dec, size_deg),
                 s3fetch.cutout_path(search.SEARCH_DIR / "cutouts", exp, ra, dec, size_deg)):
        if path.exists():
            return path
    return None


def _label(draw: ImageDraw.ImageDraw, x: int, text: str) -> None:
    draw.text((x + 4, 3), text, fill=(255, 255, 0))


def build(cand_id: str, ra: float, dec: float, patch: dict[str, Any], detector: int) -> Path | None:
    """The strip's file, from the cache or newly made; None if the patch's cutouts are not on disk."""
    key = hashlib.sha1(f"v{VERSION},{cand_id},{patch['ra']:.5f},{patch['dec']:.5f},{patch['fov']:.4f},{detector},"
                       f"{ra:.5f},{dec:.5f}".encode()).hexdigest()[:16]
    out = pictures_dir() / f"{key}.png"
    if out.exists():
        return out
    with _build_lock:
        if out.exists():
            return out
        made = _make(ra, dec, patch, detector)
        if made is None:
            return None
        out.parent.mkdir(parents=True, exist_ok=True)
        made.save(out)
        return out


def _make(ra: float, dec: float, patch: dict[str, Any], detector: int) -> Image.Image | None:
    exposures = search._exposures(patch["ra"], patch["dec"], offline=True)
    if not exposures:
        return None
    epoch_of = pipeline.assign_epochs(exposures)
    cutout_deg = round(patch["fov"] * 1.5, 4)           # as the search and /api/frames ask for them
    found: list[tuple[Path, int]] = []
    for exp, ep in zip(exposures, epoch_of, strict=True):
        if exp["detector"] != detector:
            continue
        path = _cutout_on_disk(exp, patch["ra"], patch["dec"], cutout_deg)
        if path is not None:
            found.append((path, ep))
    if len({ep for _, ep in found}) < MIN_VISITS:
        return None

    grid, n = pipeline.make_grid(ra, dec, SIZE_ARCSEC / 3600.0)
    stackers: dict[int, pipeline.Stacker] = {}
    mjds: dict[int, list[float]] = {}
    for path, ep in found:
        item = pipeline.prepare_cutout(path, grid, n, ra, dec)
        if item is None:
            continue
        stackers.setdefault(ep, pipeline.Stacker(n)).add(item["data"], item["saturated"], item["weight"],
                                                         item["lost"])
        mjds.setdefault(ep, []).append(item["mjd"])
    visits = sorted(stackers)
    counts = {ep: len(mjds[ep]) for ep in visits}
    stacks = {ep: stackers[ep].result() for ep in visits}
    if len(visits) < MIN_VISITS or not all(np.isfinite(s["image"]).any() for s in stacks.values()):
        return None

    lim = pipeline.stretch_limits([s["image"] for s in stacks.values()])
    diff = stacks[visits[-1]]["image"] - stacks[visits[0]]["image"]
    dlim = pipeline.difference_limits([diff])
    panels: list[tuple[Image.Image, str]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for ep in visits:
            path = Path(tmp) / f"v{ep}.png"
            pipeline.to_png(stacks[ep], lim, path)
            date = str(Time(float(np.mean(mjds[ep])), format="mjd").iso[:10])
            panels.append((Image.open(path).convert("RGBA"), f"visit {ep + 1}  {date}  n={counts[ep]}"))
        if dlim is not None:
            path = Path(tmp) / "diff.png"
            pipeline.to_difference_png(diff, dlim, path)
            panels.append((Image.open(path).convert("RGBA"), f"visit {visits[-1] + 1} minus {visits[0] + 1}"))

    side = n * SCALE
    sheet = Image.new("RGB", (len(panels) * (side + 6) + 6, side + 6 + 20), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for k, (img, text) in enumerate(panels):
        x = 6 + k * (side + 6)
        big = img.resize((side, side), Image.Resampling.BICUBIC)
        back = Image.new("RGBA", big.size, (0, 0, 0, 255))
        sheet.paste(Image.alpha_composite(back, big).convert("RGB"), (x, 6))
        _label(draw, x, text)
        mid, gap, tick = side // 2, side // 12, side // 10      # four ticks around the centre, not on it
        for a, b in (((x + mid, 6 + mid - gap - tick), (x + mid, 6 + mid - gap)),
                     ((x + mid, 6 + mid + gap), (x + mid, 6 + mid + gap + tick)),
                     ((x + mid - gap - tick, 6 + mid), (x + mid - gap, 6 + mid)),
                     ((x + mid + gap, 6 + mid), (x + mid + gap + tick, 6 + mid))):
            draw.line([a, b], fill=(90, 200, 255), width=2)
    draw.text((6, side + 10), f"detector {detector}; {SIZE_ARCSEC:.0f} arcsec across, north up, east left; "
                              "ticks mark the candidate; white in the last panel is brighter later",
              fill=(200, 200, 200))
    return sheet
