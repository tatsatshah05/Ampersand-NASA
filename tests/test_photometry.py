"""backend/photometry.py: what counts as saturated, the aperture sum and its units, the
wavelength bins, and how the light curve and spectrum are put together.

All inputs are made up so that the answers can be worked out by hand. Real cutouts are
measured in test_end_to_end.py.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import ncx2

from backend import photometry, pipeline

bits = pipeline._mask
# One 6.15 arcsec pixel in steradians, times 1e9: 1 MJy/sr over one pixel is 0.889 mJy.
PIXEL_MJY = (6.15 / 206264.806) ** 2 * 1e9


# ------------------------------------------------------------------ saturation

@pytest.mark.parametrize(("flags", "value", "lost"), [
    ((), 5.0, False),
    (("SOURCE",), 5.0, False),
    # Half of full well reached: the value comes from the earlier reads and is valid (Table 16).
    (("OVERFLOW",), 5.0, False),
    (("OVERFLOW",), np.nan, True),                 # overflowed and no value came out of it
    (("OVERFLOW", "SUR_ERROR"), 5.0, True),        # overflowed within the first five seconds
    (("BLOOM",), 5.0, True),                       # charge spilled in from a saturated neighbour
    (("NONLINEAR",), 5.0, True),
    (("SUR_ERROR",), 5.0, False),                  # a cosmic ray: flagged, but not saturation
])
def test_which_pixels_are_lost_to_saturation(flags: tuple[str, ...], value: float, lost: bool):
    result = photometry.saturated_pixels(np.array([bits(*flags)]), np.array([value]))
    assert result.tolist() == [lost]


# ------------------------------------------------------------ the aperture sum

def test_coverage_is_the_area_of_the_circle():
    yy, xx = np.mgrid[0:41, 0:41]
    circle = photometry._coverage(xx, yy, 20.3, 19.6, 0.0, 2.5)
    assert circle.sum() == pytest.approx(np.pi * 2.5 ** 2, rel=0.02)       # 19.6 pixels; measured 19.44
    assert circle[20, 20] == 1.0 and circle[30, 30] == 0.0
    assert ((circle >= 0) & (circle <= 1)).all()
    ring = photometry._coverage(xx, yy, 20.0, 20.0, 3.5, 6.5)
    assert ring.sum() == pytest.approx(np.pi * (6.5 ** 2 - 3.5 ** 2), rel=0.02)
    assert ring[20, 20] == 0.0                                             # a ring leaves the star out


def region(n: int = 4, value: float = 3.0) -> dict:
    """A region of n fully covered pixels, each at `value` MJy/sr with variance 0.04, no flags."""
    return {"weight": np.ones(n), "data": np.full(n, value), "variance": np.full(n, 0.04),
            "flags": np.zeros(n, dtype="int32")}


def test_sum_region_by_hand():
    r = region()
    r["weight"] = np.array([1.0, 1.0, 1.0, 0.5])                           # the last pixel is half inside
    out = photometry._sum_region(**r, sky=1.0, sky_var=1e-4, to_mjy=2.0)
    assert out["status"] == "ok"
    # (1 + 1 + 1 + 0.5) * (3 - 1) = 7 MJy/sr, times 2 mJy per MJy/sr.
    assert out["value"] == pytest.approx(14.0)
    # Variance: (1 + 1 + 1 + 0.25) * 0.04 from the pixels, plus 3.5^2 * 0.0001 from the sky level.
    assert out["error_stat"] == pytest.approx(2.0 * np.sqrt(0.13 + 0.001225))
    # 3 per cent of the flux is added in quadrature (Explanatory Supplement, Sect. 3.3 Note 1).
    assert out["error"] == pytest.approx(np.hypot(out["error_stat"], 0.03 * 14.0))
    assert out["clean_fraction"] == 1.0 and out["flags"] == []


def test_sum_region_gives_a_reason_instead_of_a_number():
    saturated = region()
    saturated["flags"][1] = bits("OVERFLOW", "SUR_ERROR", "SOURCE")
    out = photometry._sum_region(**saturated, sky=0.0, sky_var=0.0, to_mjy=1.0)
    assert (out["status"], out["value"], out["error"]) == ("saturated", None, None)
    assert out["flags"] == ["OVERFLOW", "SUR_ERROR"]                       # SOURCE is not worth reporting
    assert out["overflow_pixels"] == 1

    flagged = region()
    flagged["flags"][2] = bits("HOT")
    assert photometry._sum_region(**flagged, sky=0.0, sky_var=0.0, to_mjy=1.0)["status"] == "flagged"

    empty = region()
    empty["data"][0] = np.nan
    assert photometry._sum_region(**empty, sky=0.0, sky_var=0.0, to_mjy=1.0)["status"] == "no_data"

    # Half-well overflow alone is a valid value: measured, and counted.
    overflow = region()
    overflow["flags"][0] = bits("OVERFLOW")
    out = photometry._sum_region(**overflow, sky=0.0, sky_var=0.0, to_mjy=1.0)
    assert (out["status"], out["value"], out["overflow_pixels"]) == ("ok", pytest.approx(12.0), 1)


def test_wing_ring_tolerates_a_few_flagged_pixels_but_no_saturated_one():
    ring = region(n=20, value=2.0)
    ring["flags"][0] = bits("HOT")                                         # 5 per cent of the ring
    ring["data"][0] = 500.0                                                # and its value must not count
    out = photometry._sum_region(**ring, sky=0.0, sky_var=0.0, to_mjy=1.0, max_flagged=0.10)
    assert out["status"] == "ok"
    assert out["value"] == pytest.approx(40.0)                             # mean of the clean 19, times 20
    assert out["clean_fraction"] == pytest.approx(0.95)

    ring["flags"][1] = ring["flags"][2] = bits("HOT")                      # now 15 per cent
    assert photometry._sum_region(**ring, sky=0.0, sky_var=0.0, to_mjy=1.0, max_flagged=0.10)["status"] == "flagged"

    ring = region(n=20, value=2.0)
    ring["flags"][0] = bits("BLOOM")
    assert photometry._sum_region(**ring, sky=0.0, sky_var=0.0, to_mjy=1.0, max_flagged=0.10)["status"] == "saturated"


def points_with_rings(*usable: tuple[bool, bool, bool]) -> list[dict]:
    return [{"wings": [{"status": "ok" if ok else "saturated"} for ok in rings]} for rings in usable]


def test_one_wing_ring_is_chosen_per_detector():
    # The innermost ring that works in at least half of the exposures.
    assert photometry._choose_wing_ring(points_with_rings((True, True, True), (True, True, True))) == 0
    assert photometry._choose_wing_ring(points_with_rings((False, True, True), (True, True, True))) == 0
    assert photometry._choose_wing_ring(points_with_rings((False, True, True), (False, True, True),
                                                          (True, True, True))) == 1
    # None reaches half: the one that works most often.
    assert photometry._choose_wing_ring(points_with_rings((False, False, True), (False, False, False),
                                                          (False, False, False))) == 2
    assert photometry._choose_wing_ring(points_with_rings((False, False, False))) is None
    assert photometry._choose_wing_ring([{"wings": []}]) is None           # nothing was measured at all


# ---------------------------------------------------- measure() on a made-up star

@pytest.fixture
def block_star(write_cutout):
    """A made-up cutout: zodiacal light 1.5 and sky 0.2 MJy/sr, and a "star" of 10 MJy/sr filling
    the 3 x 3 pixels around (x=30, y=28). All nine lie fully inside the 2.5 pixel circle, so the
    aperture sum is exactly 90 MJy/sr x pixel."""
    def make(flags: np.ndarray | None = None, **kwargs):
        image = np.full((60, 60), 1.5 + 0.2)
        image[27:30, 29:32] += 10.0
        path, wcs = write_cutout(image, flags=flags, zodi=1.5, variance=9e-4, wave=4.21, bandwidth=0.037, **kwargs)
        ra, dec = (float(v) for v in wcs.all_pix2world(30, 28, 0))
        return path, wcs, ra, dec
    return make


def test_flux_of_a_made_up_star_in_millijansky(block_star):
    path, _, ra, dec = block_star()
    point = photometry.measure(path, ra, dec)
    assert point["status"] == "ok"
    assert point["flux_mjy"] == pytest.approx(90.0 * PIXEL_MJY, rel=1e-4)          # 80.01 mJy
    # Noise of the 9 to 19.6 pixels in the circle (sigma 0.03 each); the made-up sky has no scatter.
    assert 3 * 0.03 * PIXEL_MJY < point["flux_err_stat_mjy"] < np.sqrt(19.7) * 0.03 * PIXEL_MJY
    assert point["flux_err_mjy"] == pytest.approx(np.hypot(point["flux_err_stat_mjy"], 0.03 * point["flux_mjy"]))
    assert (point["wavelength_um"], point["bandwidth_um"]) == pytest.approx((4.21, 0.037), rel=1e-6)
    assert point["mjd"] == 61000.0 and point["date"].startswith("2025-11-21")
    # The rings further out hold no light of this star.
    assert [w["status"] for w in point["wings"]] == ["ok", "ok", "ok"]
    assert [w["value"] for w in point["wings"]] == pytest.approx([0.0, 0.0, 0.0], abs=1e-3)


def test_aperture_follows_the_position_it_is_given(write_cutout):
    """A made-up Gaussian star between pixel centres, measured on the star and two pixels off it."""
    yy, xx = np.mgrid[0:60, 0:60]
    sigma, x0, y0 = 1.3, 30.37, 28.21
    image = 0.2 + 50.0 * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * sigma ** 2))
    path, wcs = write_cutout(image)
    total = 50.0 * 2 * np.pi * sigma ** 2 * PIXEL_MJY                              # 472.0 mJy
    # Share of a round Gaussian inside a circle of 2.5 pixels: centred on it (the textbook
    # result, 0.843), and centred two pixels away (non-central chi-square, 0.529).
    on_star = 1 - np.exp(-2.5 ** 2 / (2 * sigma ** 2))
    two_off = float(ncx2.cdf((2.5 / sigma) ** 2, 2, (2.0 / sigma) ** 2))
    assert (on_star, two_off) == pytest.approx((0.843, 0.529), abs=1e-3)

    for offset, share in ((0.0, on_star), (2.0, two_off)):
        ra, dec = (float(v) for v in wcs.all_pix2world(x0 + offset, y0, 0))
        # Measured: 1.7 and 1.6 per cent low, from summing pixel values instead of integrating.
        assert photometry.measure(path, ra, dec)["flux_mjy"] == pytest.approx(share * total, rel=0.03)


def test_measure_reports_why_there_is_no_flux(block_star, write_cutout):
    core = np.zeros((60, 60), dtype="int32")
    core[28, 30] = bits("OVERFLOW", "SUR_ERROR", "BLOOM")
    path, _, ra, dec = block_star(flags=core, name="saturated.fits")
    point = photometry.measure(path, ra, dec)
    assert (point["status"], point["flux_mjy"], point["flux_err_mjy"]) == ("saturated", None, None)
    assert {"OVERFLOW", "SUR_ERROR", "BLOOM"} <= set(point["flags"])
    assert point["wings"][0]["status"] == "ok"                 # the ring outside the core is still usable

    hot = np.zeros((60, 60), dtype="int32")
    hot[29, 31] = bits("HOT")
    path, _, ra, dec = block_star(flags=hot, name="flagged.fits")
    assert photometry.measure(path, ra, dec)["status"] == "flagged"

    # Too close to the edge for the sky ring (14 to 20 pixels out).
    path, wcs, _, _ = block_star(name="edge.fits")
    ra, dec = (float(v) for v in wcs.all_pix2world(12, 28, 0))
    point = photometry.measure(path, ra, dec)
    assert (point["status"], point["wavelength_um"], point["wings"]) == ("off_image", None, [])

    # No wavelength for that pixel: the reading cannot be placed in a bin.
    image = np.full((60, 60), 1.0)
    path, wcs = write_cutout(image, wave=np.nan, name="no_wavelength.fits")
    ra, dec = (float(v) for v in wcs.all_pix2world(30, 28, 0))
    assert photometry.measure(path, ra, dec)["status"] == "no_data"


def test_crowded_field_still_gets_a_sky_level(block_star):
    """Nearly every pixel of a crowded field carries SOURCE. The sky ring then keeps those pixels."""
    path, _, ra, dec = block_star(flags=np.full((60, 60), bits("SOURCE"), dtype="int32"))
    point = photometry.measure(path, ra, dec)
    assert point["status"] == "ok"
    assert point["flux_mjy"] == pytest.approx(90.0 * PIXEL_MJY, rel=1e-4)


def test_no_sky_when_the_ring_is_all_defects(block_star):
    flags = np.full((60, 60), bits("HOT"), dtype="int32")
    flags[20:38, 20:40] = 0                                    # only the star's surroundings are clean
    path, _, ra, dec = block_star(flags=flags)
    assert photometry.measure(path, ra, dec)["status"] == "no_sky"


# ------------------------------------------------------------- wavelength bins

def test_channels_split_a_detector_into_17_equal_ratio_steps():
    edges = photometry.channel_edges(3.8113, 4.43)             # detector 5, as IRSA gives its range
    assert len(edges) == 18
    assert (edges[0], edges[-1]) == pytest.approx((3.8113, 4.43))
    assert edges[1:] / edges[:-1] == pytest.approx(np.full(17, (4.43 / 3.8113) ** (1 / 17)))
    assert edges[1] == pytest.approx(3.8452, abs=1e-4)         # 3.8113 * 1.008888


def point(detector: int, channel: int | None, mjd: float, wavelength: float | None, status: str = "ok",
          flux: float | None = None, wing: float | None = None, epoch: int = 1) -> dict:
    """One exposure's entry as measure_all returns it (only the fields the charts are built from)."""
    return {"detector": detector, "channel": channel, "mjd": mjd, "epoch": epoch, "wavelength_um": wavelength,
            "status": status, "flux_mjy": flux, "wing_mjy": wing, "wing_status": "ok" if wing is not None else "none",
            "wing_trusted": detector in photometry.WING_TRUSTED_DETECTORS}


@pytest.fixture
def measured(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Replace the per-exposure measurements with a handful of made-up ones."""
    points = [
        # Detector 5, channel 3: three visits, given out of order; the middle one is saturated.
        point(5, 3, 61270.0, 3.93, flux=110.0, wing=11.0, epoch=3),
        point(5, 3, 60910.0, 3.92, flux=90.0, wing=9.0, epoch=1),
        point(5, 3, 61114.0, 3.94, status="saturated", wing=10.0, epoch=2),
        # Detector 2, channel 0: wing values exist but are not trusted there.
        point(2, 0, 60911.0, 1.11, flux=40.0, wing=4.0, epoch=1),
        point(2, 0, 61115.0, 1.12, flux=60.0, wing=6.0, epoch=2),
        # An exposure in which the object fell off the detector: no wavelength, so no bin.
        point(5, None, 61116.0, None, status="off_image", epoch=2),
    ]
    result = {"key": "made-up", "ra": 10.0, "dec": 20.0, "detector": None, "target": None, "gaia_error": None,
              "failures": [], "points": points,
              "detector_ranges_um": {"2": [1.10, 1.65], "5": [3.8113, 4.43]},
              "wing_ring_px": {"2": [3.5, 6.5], "5": [3.5, 6.5]}}
    monkeypatch.setattr(photometry, "measure_all", lambda *args, **kwargs: result)
    return points


def test_lightcurve_groups_points_by_wavelength_bin(measured):
    curve = photometry.lightcurve(10.0, 20.0)
    assert (curve["n_exposures"], curve["status_counts"]) == (6, {"ok": 4, "saturated": 1, "off_image": 1})

    by_bin = {b["bin"]: b for b in curve["bins"]}
    assert sorted(by_bin) == [17, 71]                          # (detector - 1) * 17 + channel
    d5 = by_bin[71]
    edges = photometry.channel_edges(3.8113, 4.43)
    assert d5["wavelength_um"] == pytest.approx([edges[3], edges[4]])
    assert all(d5["wavelength_um"][0] <= p["wavelength_um"] <= d5["wavelength_um"][1] for p in d5["points"])
    assert [p["mjd"] for p in d5["points"]] == [60910.0, 61114.0, 61270.0]         # in time order
    assert (d5["n_points"], d5["n_measured"], d5["n_wing"]) == (3, 2, 3)
    # Brightness relative to the bin's own median (100 mJy); no number where there was no flux.
    assert d5["median_flux_mjy"] == 100.0
    assert [p["relative_flux"] for p in d5["points"]] == [pytest.approx(0.9), None, pytest.approx(1.1)]
    assert [p["relative_wing"] for p in d5["points"]] == pytest.approx([0.9, 1.0, 1.1])

    d2 = by_bin[17]
    assert d2["wing_trusted"] is False and d5["wing_trusted"] is True
    assert [p["relative_flux"] for p in d2["points"]] == pytest.approx([0.8, 1.2])
    assert [p["relative_wing"] for p in d2["points"]] == [None, None]              # never offered in detectors 1 to 4


def test_spectrum_sorts_one_epoch_by_wavelength(measured):
    everything = photometry.spectrum(10.0, 20.0)
    assert [p["wavelength_um"] for p in everything["points"]] == [1.11, 1.12, 3.92, 3.93, 3.94]
    assert [(e["epoch"], e["n_exposures"]) for e in everything["epochs"]] == [(1, 2), (2, 3), (3, 1)]
    assert everything["epochs"][0]["date_start"] == "2025-08-23"                   # MJD 60910

    second = photometry.spectrum(10.0, 20.0, epoch=2)
    assert [p["wavelength_um"] for p in second["points"]] == [1.12, 3.94]
    assert second["status_counts"] == {"ok": 1, "saturated": 1}
