"""The pure steps of backend/pipeline.py: epochs, the output grid, cleaning a cutout, stacking,
the source fit and the brightness stretch.

Inputs here are made up on purpose (a Gaussian, a flat sky with a few flagged pixels), because
only then is the right answer known in advance. The real observations are in test_end_to_end.py.
"""
from __future__ import annotations

from collections import Counter

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from PIL import Image

from backend import photometry, pipeline

# ---------------------------------------------------------------------- epochs


def exposures_at(*mjds: float) -> list[dict]:
    return [{"mjd": m} for m in mjds]


def test_a_gap_of_more_than_30_days_starts_a_new_epoch():
    assert pipeline.assign_epochs(exposures_at(100.0, 110.0, 139.0, 170.0, 171.0)) == [0, 0, 0, 1, 1]
    # Exactly 30 days is still the same visit; a little more is the next one.
    assert pipeline.assign_epochs(exposures_at(100.0, 130.0)) == [0, 0]
    assert pipeline.assign_epochs(exposures_at(100.0, 130.01)) == [0, 1]
    assert pipeline.assign_epochs(exposures_at(100.0)) == [0]
    assert pipeline.assign_epochs([]) == []


def test_barnards_star_was_visited_three_times(barnard_exposures: list[dict]):
    """The real exposure list: 364 exposures in three visits of 118, 122 and 124 (CLAUDE.md)."""
    epochs = pipeline.assign_epochs(barnard_exposures)
    assert Counter(epochs) == {0: 118, 1: 122, 2: 124}
    # Epoch numbers come from all detectors together, so every detector has the same three.
    for detector in range(1, 7):
        assert {ep for e, ep in zip(barnard_exposures, epochs, strict=True) if e["detector"] == detector} == {0, 1, 2}
    detector_5 = Counter(ep for e, ep in zip(barnard_exposures, epochs, strict=True) if e["detector"] == 5)
    assert detector_5 == {0: 18, 1: 19, 2: 25}


# ------------------------------------------------------------------------ grid

@pytest.mark.parametrize(("fov", "size"), [(0.1, 180), (0.05, 90), (0.5, 900)])
def test_grid_has_two_arcsecond_pixels(fov: float, size: int):
    assert pipeline.make_grid(269.446267, 4.768222, fov)[1] == size


@pytest.mark.parametrize(("ra", "dec"), [(269.446267, 4.768222), (248.167233, 66.755024), (0.001, -56.8)])
def test_grid_is_centred_north_up_east_left(ra: float, dec: float):
    grid, n = pipeline.make_grid(ra, dec, 0.1)
    middle = (n - 1) / 2.0
    assert grid.all_world2pix(ra, dec, 0) == pytest.approx((middle, middle), abs=1e-6)

    centre = SkyCoord(ra * u.deg, dec * u.deg)

    def offset_of(x: float, y: float) -> tuple[float, float]:
        """(east, north) of a pixel from the centre in arcsec, measured on the sphere by astropy."""
        pix_ra, pix_dec = grid.all_pix2world(x, y, 0)
        east, north = centre.spherical_offsets_to(SkyCoord(pix_ra * u.deg, pix_dec * u.deg))
        return float(east.arcsec), float(north.arcsec)

    # One pixel to the right is 2 arcsec west on the sky (not 2 arcsec of right ascension);
    # one pixel up is 2 arcsec north.
    assert offset_of(middle + 1, middle) == pytest.approx((-2.0, 0.0), abs=1e-3)
    assert offset_of(middle, middle + 1) == pytest.approx((0.0, 2.0), abs=1e-3)
    # The corners are half a field of view away in each direction, less half a pixel.
    half = 0.05 * 3600 - 1.0
    assert offset_of(0, 0) == pytest.approx((half, -half), abs=0.01)
    assert offset_of(n - 1, n - 1) == pytest.approx((-half, half), abs=0.01)


# ------------------------------------------------------------------ flag masks

def test_flag_masks_keep_sources_and_overflow():
    """SOURCE is set on almost every pixel of a crowded field, so it must never be a reason to reject."""
    display = pipeline.ALWAYS_BAD | pipeline.COSMIC_RAY
    for kept in ("SOURCE", "OUTLIER", "OVERFLOW", "BLOOM"):
        assert not display & pipeline._mask(kept), kept
    assert not pipeline.ALWAYS_BAD & pipeline.COSMIC_RAY
    # The two bit numbers CLAUDE.md quotes from Table 16 of the Explanatory Supplement.
    assert (pipeline.BIT["SOURCE"], pipeline.BIT["OVERFLOW"]) == (21, 1)
    assert pipeline._mask("TRANSIENT", "SUR_ERROR") == 0b101

    # The two lists of Sect. 3.3 of the Supplement, as recorded in CLAUDE.md.
    for_photometry = ("SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "NONLINEAR", "PERSIST", "BLOOM",
                      "SNOWBALL", "HALO", "SATELLITE_HALO")
    assert photometry.PHOTOMETRY_BAD == pipeline._mask(*for_photometry)
    assert photometry.SKY_BAD == pipeline._mask(*for_photometry, "OVERFLOW", "OUTLIER", "SOURCE", "TRANSIENT")


def test_impossible_pixels_are_far_below_zero():
    image = np.array([0.5, -0.2, -0.31, np.nan])
    variance = np.full(4, 9e-4)                       # sigma = 0.03, so the limit is -0.3
    assert pipeline.impossible_pixels(image, variance).tolist() == [False, False, True, False]


# Made-up cutout: flat sky of 0.16 MJy/sr under zodiacal light that rises from 1.5 to 2.5
# across the cutout, noise 0.03, and one pixel for each case below. Positions are (x, y)
# in the cutout, four pixels apart so that resampling does not mix them.
FLAG_CASES = {
    #  name                  (x, y)   flags                                 kept in the picture?
    "hot":                 ((20, 20), ("HOT",),                              False),
    "source only":         ((24, 20), ("SOURCE",),                           True),
    "outlier only":        ((28, 20), ("OUTLIER",),                          True),
    "cosmic ray":          ((32, 20), ("TRANSIENT",),                        False),
    "bloom next to star":  ((36, 20), ("TRANSIENT", "BLOOM"),                True),
    "bright star core":    ((40, 20), ("SUR_ERROR", "OVERFLOW", "BLOOM"),    True),
    "saturated, no value": ((20, 30), ("OVERFLOW",),                         False),
    "no value":            ((24, 30), (),                                    False),
    "far below zero":      ((28, 30), (),                                    False),
    "ramp error":          ((32, 30), ("SUR_ERROR",),                        False),
    "halo":                ((36, 30), ("HALO",),                             False),
    "overflow only":       ((40, 30), ("OVERFLOW",),                         True),
}


@pytest.fixture
def cleaned(write_cutout):
    """The made-up cutout above after prepare_cutout, with a way to look up a cutout pixel in the result."""
    rng = np.random.default_rng(7)
    zodi = np.tile(np.linspace(1.5, 2.5, 60), (60, 1))
    image = zodi + 0.16 + rng.normal(0.0, 0.03, (60, 60))
    flags = np.zeros((60, 60), dtype="int32")
    for (x, y), names, _ in FLAG_CASES.values():
        flags[y, x] = pipeline._mask(*names)
    image[30, 20] = image[30, 24] = np.nan
    image[30, 28] = -0.6                              # 20 sigma below zero, and not flagged
    path, wcs = write_cutout(image, flags=flags, zodi=zodi, variance=9e-4, wave=4.0, mjd=61000.0)
    grid, n = pipeline.make_grid(150.0, 20.0, 0.05)
    item = pipeline.prepare_cutout(path, grid, n, 150.0, 20.0)
    assert item is not None

    def at(x: int, y: int) -> tuple[int, int]:
        """Row and column in the resampled image nearest the centre of cutout pixel (x, y)."""
        col, row = grid.all_world2pix(*wcs.all_pix2world(x, y, 0), 0)
        return int(round(float(row))), int(round(float(col)))

    return item, at


@pytest.mark.parametrize("case", FLAG_CASES)
def test_cleaning_rejects_defects_and_keeps_sources(cleaned, case: str):
    item, at = cleaned
    (x, y), _, kept = FLAG_CASES[case]
    assert bool(np.isfinite(item["data"][at(x, y)])) is kept


def test_cleaning_reports_what_it_did(cleaned):
    item, at = cleaned
    assert item["data"].shape == (90, 90)
    assert item["masked_fraction"] == pytest.approx(7 / 3600)       # the seven rejected cases above
    # Only a pixel that overflowed AND has no value counts as saturated (drawn white).
    assert item["saturated"][at(20, 30)]
    assert not item["saturated"][at(24, 30)] and not item["saturated"][at(40, 30)]
    assert item["saturated"].sum() < 20                              # one cutout pixel is about 3 x 3 here
    # The zodiacal light (with its slope) and the sky level left after it are both removed:
    # what remains is flat noise. Left in, the slope alone would give a scatter of 0.15.
    assert abs(np.nanmedian(item["data"])) < 0.01
    assert np.nanstd(item["data"]) < 0.04                           # measured: 0.02
    # One weight for the whole exposure: 1 / median variance.
    assert item["weight"] == pytest.approx(1 / 9e-4, rel=1e-4)
    assert (item["mjd"], item["wave_at_target"]) == (61000.0, 4.0)


def test_cutout_with_nothing_usable_is_dropped(write_cutout):
    path, _ = write_cutout(np.ones((60, 60)), flags=np.full((60, 60), pipeline._mask("MISSING_DATA")))
    grid, n = pipeline.make_grid(150.0, 20.0, 0.05)
    assert pipeline.prepare_cutout(path, grid, n, 150.0, 20.0) is None


def test_cutout_that_misses_the_target_still_contributes(write_cutout):
    """Near a detector edge the cutout stops short of the target: no wavelength there, but pixels to use."""
    rng = np.random.default_rng(8)
    path, _ = write_cutout(1.0 + rng.normal(0.0, 0.03, (60, 60)))   # 369 arcsec wide, centred on RA 150
    ra = 150.0 + 200.0 / 3600 / np.cos(np.radians(20.0))            # ask for a spot 200 arcsec to the east
    grid, n = pipeline.make_grid(ra, 20.0, 0.05)
    item = pipeline.prepare_cutout(path, grid, n, ra, 20.0)
    assert item is not None
    assert item["wave_at_target"] is None
    assert 0.2 < np.isfinite(item["data"]).mean() < 0.6             # measured: 0.41 of the field is covered


# ----------------------------------------------------------------------- stack

def exposure(data: np.ndarray, weight: float = 1.0, saturated: np.ndarray | None = None) -> dict:
    data = np.asarray(data, dtype=float)
    return {"data": data, "weight": weight,
            "saturated": np.zeros(data.shape, dtype=bool) if saturated is None else saturated}


def test_stack_is_a_weighted_mean_with_one_weight_per_exposure():
    result = pipeline.stack([exposure(np.full((3, 3), 0.0), weight=1.0), exposure(np.full((3, 3), 4.0), weight=3.0)])
    assert result["image"] == pytest.approx(np.full((3, 3), 3.0))   # (1 * 0 + 3 * 4) / 4
    assert (result["n_valid"] == 2).all()
    assert result["rejected_readings"] == 0


def test_stack_ignores_missing_pixels_and_marks_saturation():
    first = np.array([[np.nan, 1.0], [np.nan, np.nan]])
    second = np.array([[5.0, 3.0], [np.nan, np.nan]])
    overflowed_in_first = np.array([[True, False], [True, False]])
    result = pipeline.stack([exposure(first, saturated=overflowed_in_first), exposure(second)])
    assert result["image"][0].tolist() == [5.0, 2.0]                # the one reading there is; the mean of two
    assert np.isnan(result["image"][1]).all()                       # no reading at all
    assert result["n_valid"].tolist() == [[1, 2], [0, 0]]
    # Saturated means: no usable value in ANY exposure, and at least one of them overflowed
    # there. The top-left pixel overflowed once but has a good reading, so it is not.
    assert result["saturated"].tolist() == [[False, False], [True, False]]


def test_stack_drops_a_glitch_the_flags_missed():
    """The case in stack()'s docstring: one reading of -7 MJy/sr among 22 near 0.01."""
    readings = [exposure(np.full((9, 9), 0.01), weight=1000.0) for _ in range(22)]
    readings[7]["data"][4, 4] = -7.0
    result = pipeline.stack(readings)
    assert result["rejected_readings"] == 1
    assert result["image"] == pytest.approx(np.full((9, 9), 0.01))  # without rejection the pixel would be -0.31
    assert result["n_valid"][4, 4] == 21


def test_stack_cannot_reject_with_fewer_than_five_exposures():
    """Why prepare_cutout masks far-below-zero pixels itself: a short epoch has no majority to outvote them."""
    readings = [exposure(np.full((9, 9), 0.01), weight=1000.0) for _ in range(4)]
    readings[2]["data"][4, 4] = -7.0
    result = pipeline.stack(readings)
    assert result["rejected_readings"] == 0
    assert result["image"][4, 4] == pytest.approx((3 * 0.01 - 7.0) / 4)


def test_stack_keeps_a_star_whose_brightness_swings_between_exposures():
    """A star at a fixed sky position differs by a factor of a few from exposure to exposure
    (undersampled image, different wavelength each time); that must not be taken for a glitch.
    A cosmic ray of similar size on empty sky must be."""
    star_readings = [10.0, 30.0, 12.0, 25.0, 9.0, 28.0]
    readings = []
    for value in star_readings:
        data = np.zeros((21, 21))
        data[4, 4] = value
        readings.append(exposure(data, weight=1000.0))
    readings[3]["data"][15, 15] = 5.0                               # cosmic ray, far from the star
    result = pipeline.stack(readings)
    assert result["image"][4, 4] == pytest.approx(np.mean(star_readings))
    assert result["rejected_readings"] == 1
    assert result["image"][15, 15] == pytest.approx(0.0)


# ------------------------------------------------------------------ fit_source

def made_up_star(x0: float, y0: float, amplitude: float = 100.0, sigma: float = 2.5, seed: int = 1) -> np.ndarray:
    """An 81 x 81 image: a round Gaussian on a background of 1 with noise of 0.5."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:81, 0:81]
    star = amplitude * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * sigma ** 2))
    return 1.0 + star + rng.normal(0.0, 0.5, (81, 81))


def test_fit_finds_the_centre_of_a_made_up_star():
    fit = pipeline.fit_source(made_up_star(41.3, 38.6), 40.0, 40.0)   # start a pixel or two off
    assert fit is not None
    assert (fit["x"], fit["y"]) == pytest.approx((41.3, 38.6), abs=0.05)   # measured over five seeds: 0.007
    assert fit["sigma_px"] == pytest.approx(2.5, abs=0.05)
    assert fit["amplitude"] == pytest.approx(100.0, rel=0.02)
    assert fit["err_px"] < 0.02 and fit["snr"] > 100


def test_fit_locates_a_saturated_star_from_its_wings():
    image = made_up_star(41.3, 38.6)
    yy, xx = np.mgrid[0:81, 0:81]
    # 26 pixels around the peak have no value, and (as in real data) the hole is not centred
    # on the star. Counting them as zero would pull the fit 2 pixels away.
    image[np.hypot(xx - 42.5, yy - 38.0) < 3.0] = np.nan
    fit = pipeline.fit_source(image, 40.0, 40.0)
    assert fit is not None
    assert (fit["x"], fit["y"]) == pytest.approx((41.3, 38.6), abs=0.1)    # measured over five seeds: 0.011


def test_fit_stays_with_the_source_near_the_expected_place():
    image = made_up_star(40.4, 39.7, amplitude=50.0)
    yy, xx = np.mgrid[0:81, 0:81]
    image += 1000.0 * np.exp(-((xx - 62) ** 2 + (yy - 60) ** 2) / (2 * 2.5 ** 2))   # 20 times brighter, 30 px away
    fit = pipeline.fit_source(image, 40.0, 40.0)
    assert fit is not None
    assert (fit["x"], fit["y"]) == pytest.approx((40.4, 39.7), abs=0.05)


def test_fit_gives_nothing_rather_than_a_guess():
    assert pipeline.fit_source(np.full((81, 81), np.nan), 40.0, 40.0) is None   # no data
    assert pipeline.fit_source(np.ones((81, 81)), 40.0, 40.0) is None           # nothing brighter than the sky
    assert pipeline.fit_source(made_up_star(5.0, 5.0), 5.0, 5.0) is None        # too close to the edge


# ------------------------------------------------------------ detection_sigma

FWHM = 10.0                                        # arcsec, as in a detector 5 stack
SIGMA_PX = FWHM / 2.3548 / pipeline.GRID_ARCSEC    # 2.1 grid pixels


def sky_with(*sources: tuple[float, float, float], noise: float = 0.01, seed: int = 11) -> np.ndarray:
    """A made-up 180 x 180 stack: white noise and round Gaussians (x, y, total in MJy/sr x grid pixel)."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:180, 0:180]
    image = rng.normal(0.0, noise, (180, 180))
    for x, y, total in sources:
        image += total * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * SIGMA_PX ** 2)) / (2 * np.pi * SIGMA_PX ** 2)
    return image


def test_detection_sigma_of_a_made_up_star_and_of_nothing():
    image = sky_with((90.3, 89.6, 1.5))
    known = np.array([[90.3, 89.6]])                         # the target, kept off the empty places
    noise = pipeline.noise_at_empty_places(image, FWHM, known)
    assert noise is not None and noise["n_places"] > 400      # a 12 arcsec grid over the picture
    # For white noise the scatter of a fitted flux can be worked out: noise x sqrt(4 pi s^2),
    # a little more because the sky level is fitted too. Measured: 1.21 times that.
    ideal = 0.01 * np.sqrt(4 * np.pi * SIGMA_PX ** 2) * pipeline.GRID_PIXEL_MJY
    assert 1.0 < noise["scatter_mjy"] / ideal < 1.5
    star = pipeline.detection(image, 90.3, 89.6, FWHM, np.zeros((0, 2)), noise)
    assert star["status"] == "measured"
    assert star["flux_mjy"] == pytest.approx(1.5 * pipeline.GRID_PIXEL_MJY, rel=0.1)
    assert 12 < star["sigma"] < 30                            # 1.5 / (1.21 x 0.075): about 16
    assert star["n_blank_as_strong"] == 0 and pipeline.detection_word(star) == "clear"
    nothing = pipeline.detection(image, 40.0, 130.0, FWHM, known, noise)
    assert abs(nothing["sigma"]) < 3 and pipeline.detection_word(nothing) == "none"


def test_a_known_neighbour_is_not_counted_as_the_target():
    """WISE 0855 in detectors 1 to 4: nothing at the predicted place, a star 4.4 arcsec away."""
    star = (92.2, 90.0, 3.0)                                   # 2.2 grid pixels = 4.4 arcsec east... of x = 90
    image = sky_with(star)
    neighbour = np.array([[star[0], star[1]]])
    noise = pipeline.noise_at_empty_places(image, FWHM, np.vstack([neighbour, [[90.0, 90.0]]]))
    fitted_with = pipeline.detection(image, 90.0, 90.0, FWHM, neighbour, noise)
    assert fitted_with["n_neighbours_fitted"] == 1 and abs(fitted_with["sigma"]) < 3
    # Left out, the star's light is taken for a detection.
    alone = pipeline.detection(image, 90.0, 90.0, FWHM, np.zeros((0, 2)), noise)
    assert alone["sigma"] > 10
    # Sharing the light with a close neighbour makes the target's value less certain.
    assert fitted_with["noise_mjy"] > 1.2 * noise["scatter_mjy"]


def test_sources_no_catalogue_lists_are_set_aside_from_the_empty_places():
    rng = np.random.default_rng(5)
    hidden = [(float(x), float(y), 2.0) for x, y in rng.uniform(20, 160, (25, 2))]
    plain = pipeline.noise_at_empty_places(sky_with(), FWHM, np.zeros((0, 2)))
    crowded = pipeline.noise_at_empty_places(sky_with(*hidden), FWHM, np.zeros((0, 2)))
    assert plain is not None and crowded is not None
    assert crowded["n_set_aside"] > plain["n_set_aside"] + 15
    # Places near (not on) a hidden source still catch some of its light, so the scatter
    # grows a little (measured: 1.25 times); without setting the sources aside it would
    # be several times larger (measured: 3.1 times).
    assert crowded["scatter_mjy"] < 1.5 * plain["scatter_mjy"]
    assert np.std(crowded["values"]) > 2.5 * plain["scatter_mjy"]


def test_detection_without_enough_empty_places_is_unknown():
    image = sky_with((20.0, 20.0, 1.5))[:40, :40]             # a picture 80 arcsec across: 16 places at most
    assert pipeline.noise_at_empty_places(image, FWHM, np.array([[20.0, 20.0]])) is None
    found = pipeline.detection(image, 20.0, 20.0, FWHM, np.zeros((0, 2)), None)
    assert found["status"] == "no_noise_estimate" and found["sigma"] is None
    assert pipeline.detection_word(found) == "unknown"


def test_a_saturated_place_counts_as_detected():
    image = sky_with((90.0, 90.0, 50.0))
    yy, xx = np.mgrid[0:180, 0:180]
    core = np.hypot(xx - 90.0, yy - 90.0) < 6                # far more than half the fitted pixels
    image[core] = np.nan
    found = pipeline.detection(image, 90.0, 90.0, FWHM, np.zeros((0, 2)), None, saturated=core)
    assert found["status"] == "saturated" and pipeline.detection_word(found) == "saturated"


# --------------------------------------------------------------------- stretch

def test_one_stretch_covers_every_epoch():
    rng = np.random.default_rng(3)
    faint = rng.normal(1.0, 0.1, (50, 50))
    bright = rng.normal(1.0, 0.1, (50, 50))
    bright[25, 25] = 500.0
    bright[0, 0] = np.nan
    limits = pipeline.stretch_limits([faint, bright])
    assert limits == pipeline.stretch_limits([bright, faint])
    assert limits["vmax"] == 500.0                                  # the brightest pixel of any epoch
    assert limits["vmin"] == pytest.approx(1.0 - 2 * 0.1, abs=0.02)   # sky median minus two sigma
    assert limits["soft"] == pytest.approx(3 * 0.1, abs=0.03)


def test_difference_stretch_is_symmetric_about_zero():
    rng = np.random.default_rng(4)
    change = rng.normal(0.0, 0.1, (50, 50))
    change[10, 10], change[20, 20], change[0, 0] = 8.0, -12.0, np.nan
    limits = pipeline.difference_limits([change])
    assert limits is not None
    assert (limits["vmin"], limits["vmax"]) == (-12.0, 12.0)
    assert limits["soft"] == pytest.approx(0.3, abs=0.03)
    # Nothing to scale: frames that never overlap, or that are identical.
    assert pipeline.difference_limits([np.full((5, 5), np.nan)]) is None
    assert pipeline.difference_limits([np.zeros((5, 5))]) is None


def test_png_is_north_up_with_white_for_saturated_and_clear_for_no_data(tmp_path):
    stacked = {"image": np.array([[0.0, 10.0], [np.nan, np.nan]]),      # row 0 is the SOUTH edge
               "saturated": np.array([[False, False], [True, False]])}
    pipeline.to_png(stacked, {"vmin": 0.0, "vmax": 10.0, "soft": 1.0}, tmp_path / "frame.png")
    png = Image.open(tmp_path / "frame.png")
    assert (png.mode, png.size) == ("RGBA", (2, 2))
    rgba = np.asarray(png)
    assert rgba[1, 0].tolist() == [0, 0, 0, 255]                     # bottom left: the faint end, black
    assert rgba[1, 1].tolist() == [255, 255, 255, 255]               # bottom right: the bright end, white
    assert rgba[0, 0].tolist() == [255, 255, 255, 255]               # top left: saturated, white
    assert rgba[0, 1, 3] == 0                                        # top right: no data, transparent


def test_difference_png_is_mid_grey_where_nothing_changed(tmp_path):
    change = np.array([[0.0, 5.0], [-5.0, np.nan]])
    pipeline.to_difference_png(change, {"vmin": -5.0, "vmax": 5.0, "soft": 1.0}, tmp_path / "diff.png")
    rgba = np.asarray(Image.open(tmp_path / "diff.png"))
    assert rgba[1, 0].tolist() == [128, 128, 128, 255]               # no change
    assert rgba[1, 1].tolist() == [255, 255, 255, 255]               # brighter than the reference
    assert rgba[0, 0].tolist() == [0, 0, 0, 255]                     # fainter
    assert rgba[0, 1, 3] == 0                                        # missing in either image
