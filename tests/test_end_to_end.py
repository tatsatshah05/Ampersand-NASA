"""Barnard's Star from request to picture, on real SPHEREx data and without the network.

The data are in tests/data/cache: files copied unchanged from backend/cache (listed in
conftest.py). They carry the names the backend gave them, so these tests also notice when
a cache key changes, which would leave the cache warmed for the demo unused.

Only nine of the 62 detector 5 cutouts are in the repository: the first three exposures
of each of the three visits (August 2025, March 2026, August 2026). The numbers therefore
differ a little from scripts/check_barnard.py, which uses all 62. Each limit below is
followed by what was measured with these nine cutouts on 2026-11-14 (pipeline.VERSION 2).
The limits are loose enough to survive a change of method (other subsets of three
exposures per visit put the star up to 3.4 arcsec from Gaia's position) and tight enough
to catch a slip of one grid pixel (2 arcsec) in the fixed stars or of half a SPHEREx
pixel (3 arcsec) in the moving one.
"""
from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from fastapi.testclient import TestClient
from PIL import Image

from backend import astrometry, pipeline, spherex

NATIVE_PIXEL = 6.15      # arcsec
HALF_A_PIXEL = 3.0       # arcsec: the limit for the moving star
ONE_GRID_PIXEL = 1.0     # output pixels (2 arcsec): the limit for the fixed stars


def offset(start: dict, end: dict) -> tuple[float, float]:
    """(east, north) in arcsec from one position to another (dicts with ra and dec), by astropy."""
    east, north = (SkyCoord(start["ra"] * u.deg, start["dec"] * u.deg)
                   .spherical_offsets_to(SkyCoord(end["ra"] * u.deg, end["dec"] * u.deg)))
    return float(east.arcsec), float(north.arcsec)


def distance(start: dict, end: dict) -> float:
    return float(np.hypot(*offset(start, end)))


def picture(meta: dict, frame: dict) -> np.ndarray:
    """A frame's PNG as rows of RGBA from the top, read from the folder the server serves /frames from."""
    assert frame["image"].startswith(f"/frames/{meta['key']}/")
    return np.asarray(Image.open(pipeline.FRAMES_DIR / meta["key"] / Path(frame["image"]).name))


def grey_at(image: np.ndarray, place: dict) -> int:
    """Grey level of the PNG pixel under a centroid or predicted position (x, y from the top-left)."""
    return int(image[int(round(place["y"])), int(round(place["x"])), 0])


def unreachable(*args: object, **kwargs: object) -> list[dict]:
    raise spherex.ArchiveError("Gaia did not answer (made to fail by a test)")


@pytest.fixture(scope="module")
def normal(barnard: SimpleNamespace, network_log: list[str]) -> SimpleNamespace:
    """build_frames with every default, as the page first asks for Barnard's Star.

    The exposure list is IRSA's complete one, so 53 cutouts that are not in the
    repository are asked for and refused: the result has three frames and 53 failures.
    """
    network_log.clear()
    meta = pipeline.build_frames(barnard.ra, barnard.dec)
    return SimpleNamespace(meta=meta, frames=meta["frames"], asked=list(network_log))


@pytest.fixture
def complete(barnard: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the archive list only those detector 5 exposures whose cutouts are on disk.

    Nothing is missing then, so the result is complete and gets cached like a real one.
    """
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: barnard.exposures_on_disk)


# ------------------------------------------------------------- the cache is found

def test_cached_files_are_found_under_the_names_the_backend_expects(barnard: SimpleNamespace, network: list[str]):
    assert len(spherex.find_exposures(barnard.ra, barnard.dec)) == 364
    stars = astrometry.gaia_cone(barnard.ra, barnard.dec, barnard.fov * 0.75 + 0.06)
    assert stars[0]["source_id"] == barnard.gaia_id           # brightest first, and that is Barnard's Star
    on_disk = [e for e in barnard.exposures if e["detector"] == 5 and e["obs_id"] in barnard.cutouts_on_disk]
    assert len(on_disk) == 9
    assert all(spherex._cutout_path(e, barnard.ra, barnard.dec, round(barnard.fov * 1.5, 4)).exists() for e in on_disk)
    assert network == []


# ------------------------------------------------------------------ normal mode

def test_three_frames_one_per_visit(normal: SimpleNamespace):
    meta, frames = normal.meta, normal.frames
    assert [f["epoch"] for f in frames] == [1, 2, 3]
    assert [f["date_mean"][:7] for f in frames] == ["2025-08", "2026-03", "2026-08"]
    assert [f["n_exposures"] for f in frames] == [3, 3, 3]
    assert (meta["size_px"], meta["pixel_arcsec"], meta["detector"], meta["fov"]) == (180, 2.0, 5, 0.1)
    assert meta["exposures_total_all_detectors"] == 364
    for f in frames:
        low, high = f["wavelength_um"]
        assert 3.8 < low <= high < 4.44                       # detector 5 covers 3.81 to 4.43 microns
        assert f["date_start"] <= f["date_mean"] <= f["date_end"]
        assert 0.0 < f["flagged_fraction"] < 0.05             # measured: 0.014 to 0.024
        assert f["saturated_pixels"] == 0                     # the star is clean in detector 5 (CLAUDE.md)


def test_missing_exposures_are_reported_and_nothing_stands_in_for_them(normal: SimpleNamespace,
                                                                       barnard: SimpleNamespace):
    missing = [e for e in barnard.exposures if e["detector"] == 5 and e["obs_id"] not in barnard.cutouts_on_disk]
    failures = normal.meta["failures"]
    assert len(failures) == len(missing) == 53
    assert all(any(e["obs_id"] in failure for failure in failures) for e in missing)   # each one is named
    # Only those cutouts were asked for. The exposure list and the Gaia stars came from the cache.
    assert sorted(normal.asked) == sorted(f"{e['url']}?center=269.446267,4.768222&size=0.15000" for e in missing)
    # An incomplete result is returned but not kept, so the next request tries again.
    assert not (pipeline.FRAMES_DIR / normal.meta["key"] / "frames.json").exists()


def test_the_star_is_where_gaia_says(normal: SimpleNamespace, barnard: SimpleNamespace):
    """CLAUDE.md: Barnard's Star is the ground truth, to within about a pixel."""
    assert normal.meta["target"]["source_id"] == barnard.gaia_id
    off_by = [distance(f["predicted"], f["centroid"]) for f in normal.frames]
    assert max(off_by) < HALF_A_PIXEL                         # measured: 1.14, 0.44, 0.29 arcsec
    for f in normal.frames:
        star = f["centroid"]
        assert star["snr"] > 15                               # measured: 43, 49, 41
        assert NATIVE_PIXEL < star["fwhm_arcsec"] < 16        # measured: 10.0, 10.6, 12.0 (the PSF itself is 7.4)
        assert star["err_arcsec"] < 0.5                       # measured: 0.05


def test_the_star_moves_north_as_gaia_predicts(normal: SimpleNamespace, barnard: SimpleNamespace):
    """About 5 arcsec north per half year: a little less than one SPHEREx pixel per visit."""
    frames = normal.frames
    for earlier, later in zip(frames, frames[1:], strict=False):
        years = (later["mjd_mean"] - earlier["mjd_mean"]) / 365.25
        assert 0.4 < years < 0.6                              # measured: 0.557 and 0.429
        east, north = offset(earlier["centroid"], later["centroid"])
        assert 3.5 < north / years / 2 < 7.0                  # measured: 5.5 and 4.6 arcsec per half year
        expected = offset(earlier["predicted"], later["predicted"])
        # Measured (-0.76, +6.14) against (+0.58, +5.62), then (-1.28, +3.99) against (-1.35, +4.62):
        # 1.44 and 0.64 arcsec apart.
        assert np.hypot(east - expected[0], north - expected[1]) < HALF_A_PIXEL

    # Over the whole year the parallax nearly cancels and what is left is the proper motion:
    # 10.36 arcsec north per year in Gaia DR3.
    years = (frames[-1]["mjd_mean"] - frames[0]["mjd_mean"]) / 365.25
    east, north = offset(frames[0]["centroid"], frames[-1]["centroid"])
    assert north / years == pytest.approx(barnard.motion["pmdec"] / 1000.0, abs=1.0)   # measured: 10.27
    assert abs(east) < 4.0                                    # measured: -2.04 (Gaia: -0.77)


def test_frames_are_pictures_of_the_star(normal: SimpleNamespace):
    """A blank or flipped frame is a bug even if the numbers look right."""
    meta = normal.meta
    middle, scale = (meta["size_px"] - 1) / 2.0, meta["pixel_arcsec"]
    for f in normal.frames:
        image = picture(meta, f)
        assert image.shape == (180, 180, 4)
        grey, alpha = image[..., 0], image[..., 3]
        assert (alpha == 0).mean() < 0.01                     # hardly any pixel without data; measured: 0.0002
        assert np.median(grey) < 60 < 200 < grey.max()        # dark sky (measured 16), bright star (244 to 255)
        # The brightest pixel is the star, at the centroid's x and y counted from the top-left corner.
        row, column = np.unravel_index(np.argmax(grey), grey.shape)
        assert abs(column - f["centroid"]["x"]) <= 1.5 and abs(row - f["centroid"]["y"]) <= 1.5
        assert grey_at(image, f["predicted"]) > 200
        # Where the page draws its markers: x grows to the west and y to the south, 2 arcsec per
        # pixel, from the top-left corner. Worked out here from each sky position by hand.
        for place in (f["centroid"], f["predicted"]):
            east, north = offset(meta, place)                 # meta holds the ra and dec of the centre
            by_hand = (middle - east / scale, middle - north / scale)
            assert (place["x"], place["y"]) == pytest.approx(by_hand, abs=0.02)

    # One brightness scale for all three frames (CLAUDE.md, step 7): only the frame holding the
    # brightest pixel of all reaches white. Scaled frame by frame, every one of them would.
    brightest = [int(picture(meta, f)[..., 0].max()) for f in normal.frames]
    assert brightest.count(255) == 1                          # measured: 255, 248, 244
    assert meta["stretch"]["kind"] == "asinh" and meta["stretch"]["vmin"] < meta["stretch"]["vmax"]


def test_field_stars_stay_put_and_north_is_up(normal: SimpleNamespace, barnard: SimpleNamespace):
    """CLAUDE.md: field stars must stay fixed between frames; if they jitter, reprojection is wrong.

    The brightest Gaia stars of the field are looked up in each PNG at the pixel worked out
    by hand from their catalogue positions: east is left, north is up, 2 arcsec per pixel.
    """
    n, scale = normal.meta["size_px"], normal.meta["pixel_arcsec"]
    middle = (n - 1) / 2.0
    centre = {"ra": barnard.ra, "dec": barnard.dec}
    greys = [picture(normal.meta, f)[..., 0].astype(float) for f in normal.frames]

    checked = 0
    for star in astrometry.gaia_cone(barnard.ra, barnard.dec, barnard.fov * 0.75 + 0.06):
        if star["source_id"] == barnard.gaia_id or star["gmag"] > 13.5:
            continue
        if np.hypot(star["pmra"] or 0.0, star["pmdec"] or 0.0) > 50:      # mas/yr: would move by itself
            continue
        found = []
        for f, grey in zip(normal.frames, greys, strict=True):
            ra, dec = astrometry.position_at(star, f["mjd_mean"])
            east, north = offset(centre, {"ra": ra, "dec": dec})
            x, y = middle - east / scale, middle - north / scale          # from the top-left of the PNG
            if not (14 <= x < n - 14 and 14 <= y < n - 14):
                break                                                     # too close to the edge to fit
            fit = pipeline.fit_source(grey, x, y, search=3)
            assert fit is not None, f"Gaia DR3 {star['source_id']} (G = {star['gmag']:.1f}) is missing from a frame"
            assert np.hypot(fit["x"] - x, fit["y"] - y) < ONE_GRID_PIXEL  # measured: at most 0.28 pixel
            found.append((fit["x"], fit["y"]))
        else:
            checked += 1
            jitter = max(np.hypot(a[0] - b[0], a[1] - b[1]) for a in found for b in found)
            assert jitter < ONE_GRID_PIXEL                                # measured: at most 0.43 pixel
    assert checked == 4                                                   # G = 11.9, 13.0, 13.4 and 13.5


def test_api_returns_the_frames_and_serves_their_pictures(client: TestClient, normal: SimpleNamespace,
                                                          barnard: SimpleNamespace):
    """The request the page makes for its default view: no fov, no detector, no mode."""
    response = client.get("/api/frames", params={"ra": barnard.ra, "dec": barnard.dec})
    assert response.status_code == 200, response.text
    answer = response.json()
    # Defaults are part of the cache key: a different default would miss the warmed cache.
    assert (answer["fov"], answer["detector"], answer["mode"], answer["key"]) == (0.1, 5, "normal", normal.meta["key"])
    for field in ("size_px", "pixel_arcsec", "stretch", "target", "failures", "frames"):
        assert field in answer, field
    assert len(answer["frames"]) == 3

    for frame, direct in zip(answer["frames"], normal.frames, strict=True):
        for field in ("epoch", "date_start", "date_end", "date_mean", "mjd_mean", "image", "n_exposures",
                      "wavelength_um", "flagged_fraction", "saturated_pixels", "rejected_readings", "centroid",
                      "predicted"):
            assert field in frame, field
        for place in ("centroid", "predicted"):
            assert {"ra", "dec", "x", "y"} <= set(frame[place])
        assert frame["centroid"] == direct["centroid"]
        served = client.get(frame["image"])
        assert served.status_code == 200 and served.headers["content-type"] == "image/png"
        assert Image.open(io.BytesIO(served.content)).size == (answer["size_px"], answer["size_px"])


def test_without_gaia_the_frames_still_come_back_but_are_not_cached(barnard: SimpleNamespace, normal: SimpleNamespace,
                                                                    monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(astrometry, "gaia_cone", unreachable)
    meta = pipeline.build_frames(barnard.ra, barnard.dec)
    assert meta["target"] is None
    assert "Gaia did not answer" in meta["gaia_error"]
    assert [f["predicted"] for f in meta["frames"]] == [None, None, None]
    assert [f["centroid"] for f in meta["frames"]] == [f["centroid"] for f in normal.frames]
    assert not (pipeline.FRAMES_DIR / meta["key"] / "frames.json").exists()


def test_a_motion_given_in_the_request_makes_the_request_the_target(client: TestClient, barnard: SimpleNamespace,
                                                                    normal: SimpleNamespace,
                                                                    monkeypatch: pytest.MonkeyPatch):
    """How an object Gaia does not list (WISE 0855) gets an expected position: the page passes on
    pmra, pmdec and parallax from /api/resolve, for an object that is at (ra, dec) in 2026.0."""
    monkeypatch.setattr(astrometry, "gaia_cone", unreachable)             # Gaia must not be needed
    response = client.get("/api/frames", params={"ra": barnard.ra, "dec": barnard.dec, **barnard.motion})
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["target"]["origin"] == "request" and answer["gaia_error"] is None
    for frame, by_gaia in zip(answer["frames"], normal.frames, strict=True):
        # Same star, started from 2026.0 instead of Gaia's 2016.0. The two predictions differ by the
        # radial velocity that only astrometry.propagate applies. Measured: 0.063 arcsec. Leaving
        # out the parallax would show here as 0.5 arcsec.
        assert distance(by_gaia["predicted"], frame["predicted"]) < 0.1
        assert distance(frame["predicted"], frame["centroid"]) < HALF_A_PIXEL


def test_a_view_with_no_usable_exposures_says_so(client: TestClient, barnard: SimpleNamespace, network: list[str]):
    """Detector 6 at half the field of view: none of those cutouts are in the repository, so every
    download is refused. The answer is an empty list of frames and a message, not an error."""
    response = client.get("/api/frames", params={"ra": barnard.ra, "dec": barnard.dec, "detector": 6, "fov": 0.05})
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["frames"] == [] and "detector 6" in answer["message"]
    detector_6 = [e for e in barnard.exposures if e["detector"] == 6]
    assert len(answer["failures"]) == len(detector_6) == 60
    # The detector and the field of view of the request are what the archive was asked for.
    assert sorted(network) == sorted(f"{e['url']}?center=269.446267,4.768222&size=0.07500" for e in detector_6)


# -------------------------------------------------- difference and sum modes

def test_difference_mode_shows_where_the_star_left_and_where_it_arrived(complete: None, barnard: SimpleNamespace,
                                                                        network: list[str],
                                                                        monkeypatch: pytest.MonkeyPatch):
    meta = pipeline.build_frames(barnard.ra, barnard.dec, mode="difference")
    assert meta["failures"] == [] and network == []
    assert [(f["epoch"], f["reference_epoch"]) for f in meta["frames"]] == [(2, 1), (3, 1)]
    stretch = meta["stretch"]
    assert stretch["kind"] == "asinh-symmetric" and stretch["vmin"] == -stretch["vmax"] < 0

    before = meta["reference_frame"]
    assert before["epoch"] == 1
    for f in meta["frames"]:
        image = picture(meta, f)
        grey = image[..., 0]
        assert abs(float(np.median(grey)) - 128) <= 4         # no change is mid-grey; measured: 126 and 127
        assert ((grey > 117) & (grey < 139)).mean() > 0.8     # and that is most of the field; measured: 0.90
        assert grey_at(image, f["centroid"]) > 220            # white where the star is now; measured: 247, 250
        assert grey_at(image, before["centroid"]) < 35        # black where it was in visit 1; measured: 4, 0
        assert f["centroid"]["y"] < before["centroid"]["y"]   # and "now" is above "then": north is up

    # A complete result is kept, and the next request is answered from it without any work.
    assert (pipeline.FRAMES_DIR / meta["key"] / "frames.json").exists()
    monkeypatch.setattr(pipeline, "prepare_cutout", lambda *args, **kwargs: pytest.fail("the cache was not used"))
    assert pipeline.build_frames(barnard.ra, barnard.dec, mode="difference") == meta


def test_difference_against_all_visits_has_a_frame_for_each(client: TestClient, complete: None,
                                                            barnard: SimpleNamespace):
    response = client.get("/api/frames", params={"ra": barnard.ra, "dec": barnard.dec, "mode": "difference",
                                                 "reference": "mean"})
    assert response.status_code == 200, response.text
    answer = response.json()
    assert [(f["epoch"], f["reference_epoch"]) for f in answer["frames"]] == [(1, None), (2, None), (3, None)]
    assert answer["stretch"]["kind"] == "asinh-symmetric"
    for f in answer["frames"]:
        served = client.get(f["image"])
        assert served.headers["content-type"] == "image/png"
        # In every visit, the first included, the star is brighter at its own place than in
        # the average of all three, where it is spread over 10 arcsec.
        image = np.asarray(Image.open(io.BytesIO(served.content)))
        assert grey_at(image, f["centroid"]) > 200            # measured: 252, 242, 245


def test_sum_mode_is_sharper_when_it_follows_the_star(complete: None, barnard: SimpleNamespace):
    on_sky = pipeline.build_frames(barnard.ra, barnard.dec, mode="sum")
    # The motion comes from the request here, as the page passes it on from /api/resolve.
    following = pipeline.build_frames(barnard.ra, barnard.dec, mode="sum", track="target", **barnard.motion)
    for meta, registration in ((on_sky, "sky"), (following, "target_motion")):
        (frame,) = meta["frames"]
        assert (frame["epoch"], frame["epochs_combined"], frame["n_exposures"]) == (None, [1, 2, 3], 9)
        assert meta["registration"] == registration
        assert picture(meta, frame).shape == (180, 180, 4)
    assert "smeared" in following["note"]                     # the page has to say what happened to the other stars

    # Lined up on the sky, the star is drawn out along the 10 arcsec it moved. Following
    # it, it is as sharp as in a single visit.
    smeared, sharp = on_sky["frames"][0]["centroid"], following["frames"][0]["centroid"]
    assert smeared["fwhm_arcsec"] - sharp["fwhm_arcsec"] > 1.5    # measured: 13.9 against 10.7 arcsec
    assert sharp["snr"] > smeared["snr"]                          # measured: 51 against 19


def test_following_a_target_without_a_known_motion_is_refused(client: TestClient, barnard: SimpleNamespace,
                                                              monkeypatch: pytest.MonkeyPatch):
    """CLAUDE.md: track=target answers 400 if no motion is known. Here: none given, and Gaia is down.

    This relies on no test caching a Gaia-based track=target sum for this position (the
    test above passes the motion in the request instead): a cached one would be served.
    """
    monkeypatch.setattr(astrometry, "gaia_cone", unreachable)
    response = client.get("/api/frames", params={"ra": barnard.ra, "dec": barnard.dec, "mode": "sum",
                                                 "track": "target"})
    assert response.status_code in (400, 422), response.text
    assert "proper motion" in response.json()["detail"]


# ---------------------------------------------------- light curve and spectrum

def test_lightcurve_and_spectrum_of_a_star_too_bright_to_measure(client: TestClient, barnard: SimpleNamespace):
    """Barnard's Star saturates in every exposure (CLAUDE.md), so there is no flux, only the wing
    brightness, which detector 5 is trusted for. The motion is given, so nothing depends on how
    the target is picked without one."""
    params = {"ra": barnard.ra, "dec": barnard.dec, "detector": 5, **barnard.motion}
    response = client.get("/api/lightcurve", params=params)
    assert response.status_code == 200, response.text
    curve = response.json()
    assert len(curve["failures"]) == 53 and "flux" in curve["method"]

    points = [p for b in curve["bins"] for p in b["points"]]
    assert len(points) == 9
    assert sorted(p["epoch"] for p in points) == [1, 1, 1, 2, 2, 2, 3, 3, 3]      # numbered as in /api/frames
    for p in points:
        assert (p["status"], p["flux_mjy"], p["relative_flux"]) == ("saturated", None, None)
        assert {"OVERFLOW", "SUR_ERROR", "BLOOM"} <= set(p["flags"])
        assert p["wing_trusted"] is True and 0.03 < p["bandwidth_um"] < 0.04
    for b in curve["bins"]:
        low, high = b["wavelength_um"]
        assert b["detector"] == 5 and 3.81 <= low < high <= 4.43
        assert all(low <= p["wavelength_um"] <= high for p in b["points"])        # each point is in its own bin
        assert [p["mjd"] for p in b["points"]] == sorted(p["mjd"] for p in b["points"])

    # The wing brightness exists for most exposures (measured: 7 of 9) ...
    wings = [p for p in points if p["wing_status"] == "ok"]
    assert len(wings) >= 5 and all(p["wing_mjy"] > 0 and p["wing_ring_px"] == [3.5, 6.5] for p in wings)
    # ... and repeats: one bin holds a value from March and one from August 2026, and this
    # star does not vary. Measured: 3.8 per cent apart (CLAUDE.md: 2 to 5 per cent in detector 5).
    pairs = [[p["wing_mjy"] for p in b["points"] if p["wing_status"] == "ok"] for b in curve["bins"]]
    (pair,) = [values for values in pairs if len(values) == 2]
    assert max(pair) / min(pair) < 1.15

    response = client.get("/api/spectrum", params={**params, "epoch": 2})
    assert response.status_code == 200, response.text
    spectrum = response.json()
    assert [(e["epoch"], e["n_exposures"]) for e in spectrum["epochs"]] == [(1, 3), (2, 3), (3, 3)]
    waves = [p["wavelength_um"] for p in spectrum["points"]]
    assert len(waves) == 3 and waves == sorted(waves) and all(p["epoch"] == 2 for p in spectrum["points"])
    assert waves == pytest.approx([4.223, 4.259, 4.296], abs=0.001)

    assert client.get("/api/spectrum", params={**params, "epoch": 4}).status_code in (400, 422)
