"""Pictures for docs/reflex.md from docs/reflex/results.json (written by check_reflex.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_plot import BLACK, BLUE, Chart, save  # noqa: E402

DOCS = Path(__file__).resolve().parents[1] / "docs" / "reflex"


def main() -> None:
    res = json.loads((DOCS / "results.json").read_text())
    c = res["eris"]["candidate"]
    prof = c["profile"]
    jpl = res["eris"]["scored_against_jpl"]["observer_distance_au"]
    ch = Chart(
        "Eris, one visit, no ephemeris: S/N against 1/distance",
        "1 / distance (1/AU); negative = the Earth's motion reversed (control)",
        "S/N",
        width=1000,
        height=420,
    )
    pts = [(x, y) for x, y in zip(prof["inv_d"], prof["snr"], strict=True) if y is not None]
    ch.line([p[0] for p in pts], [p[1] for p in pts], color=BLUE)
    ch.vline(1.0 / jpl, color=BLACK, label=f"JPL: {jpl:.1f} AU")
    ch.vline(0.0, label="infinitely far")
    save(ch.render(), DOCS / "eris_profile.png")
    # three band-averaged fluxes against wavelength (band centres of D1-D3), matched-filter scale, y axis from 0
    dets = c["per_detector"]
    centres = [0.92, 1.36, 2.02]
    half = [0.17, 0.26, 0.40]
    flux = [dets[f"D{i}"]["flux_mjy"] for i in (1, 2, 3)]
    err = [dets[f"D{i}"].get("flux_error_mjy", 0.0) for i in (1, 2, 3)]
    spec = Chart(
        "Eris: three band fluxes from the same exposures (matched-filter scale, uncalibrated)",
        "wavelength (micrometres): D1 0.75-1.09, D2 1.10-1.62, D3 1.63-2.42",
        "mean flux (mJy)",
        width=760,
        height=380,
        ylim=(0.0, max(flux) * 1.3),
        xlim=(0.6, 2.6),
    )
    spec.scatter(centres, flux, yerr=err, xerr=half, color=BLUE, label="Eris, blind track")
    # approximate solar-coloured reflector, scaled to D1 (about 1 : 0.95 : 0.72 from solar colours; reviewers' estimate)
    spec.scatter(
        centres, [flux[0] * f for f in (1.0, 0.95, 0.72)], color=BLACK, hollow=True, label="solar colours (approx.)"
    )
    save(spec.render(), DOCS / "eris_spectrum.png")


if __name__ == "__main__":
    main()
