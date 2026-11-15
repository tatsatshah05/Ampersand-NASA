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
    ch.line(prof["inv_d"], prof["snr"], color=BLUE)
    ch.vline(1.0 / jpl, color=BLACK, label=f"JPL: {jpl:.1f} AU")
    ch.vline(0.0, label="infinitely far")
    save(ch.render(), DOCS / "eris_profile.png")
    spec = Chart(
        "Eris, spectrum from the same exposures",
        "detector (D1 0.75-1.1, D2 1.1-1.6, D3 1.6-2.4 um)",
        "mean flux (mJy)",
        width=700,
        height=360,
    )
    dets = c["per_detector"]
    spec.scatter([1, 2, 3], [dets[f"D{i}"]["flux_mjy"] for i in (1, 2, 3)], color=BLUE)
    save(spec.render(), DOCS / "eris_spectrum.png")


if __name__ == "__main__":
    main()
