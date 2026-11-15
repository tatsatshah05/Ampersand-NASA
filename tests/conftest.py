"""Shared set-up for every test. Run the suite with `pytest` from the project root.

Three things are arranged here so that no single test has to remember them.

1. The real cache is never touched. backend/spherex.py reads SPHEREX_CACHE_DIR once, when
   it is first imported, and creates folders there. pytest_configure() below runs before
   any test module is imported and points the variable at an empty folder inside pytest's
   own temporary directory, so a test file can `from backend import pipeline` at the top
   as usual. THIS file must not import the backend at the top.
2. Nothing reaches the network. Every reference to spherex.http_get is replaced by a
   function that notes the URL and raises ArchiveError at once, which is what the real one
   does (after its retries) when the archive cannot be reached. `requests` and astropy's
   downloader are switched off as well, so a new code path fails loudly instead of quietly
   depending on the internet.
3. Real observations come from tests/data/cache: files copied unchanged from
   backend/cache, with the same folder layout and names. The `barnard` fixture copies them
   into the test cache. Whatever a test makes up (see `write_cutout`) goes to a temporary
   folder and is never mixed with them.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
from fastapi.testclient import TestClient

# Real data for Barnard's Star, copied from backend/cache on 2026-11-14 and not edited:
#   queries/sia_59eeb054c4d4ab68.json      IRSA's list of all 364 exposures covering it
#   queries/gaia_72ebee125c690986.json     Gaia DR3 stars within 0.135 degrees
#   queries/resolve_a876015f370716f8.json  what /api/resolve answered for "Barnard's Star"
#   cutouts/01e6af5d45/*_D5.fits           the first three detector 5 exposures of each of
#                                          its three epochs (slim cutouts, 0.15 degrees)
DATA_CACHE = Path(__file__).parent / "data" / "cache"
# Gaia DR3 position of Barnard's Star moved to 2026.0: the centre those cutouts were fetched for.
BARNARD_RA, BARNARD_DEC = 269.446267, 4.768222
NATIVE_ARCSEC = 6.15   # size of a SPHEREx pixel, used for made-up cutouts

_CACHE_DIR = pytest.StashKey[Path]()


class NetworkBlocked(RuntimeError):
    """Something tried to open a connection during the tests."""


@pytest.hookimpl(trylast=True)   # after pytest has set up its own temporary-folder factory
def pytest_configure(config: pytest.Config) -> None:
    # config._tmp_path_factory is the object behind the tmp_path_factory fixture. A fixture
    # would come too late: test modules import the backend while they are being collected.
    factory = getattr(config, "_tmp_path_factory", None)
    if factory is not None:
        cache = factory.mktemp("spherex-cache", numbered=False)
    else:   # a pytest that no longer has that attribute: still never the real cache
        cache = Path(tempfile.mkdtemp(prefix="spherex-cache-"))
    config.stash[_CACHE_DIR] = cache
    os.environ["SPHEREX_CACHE_DIR"] = str(cache)
    # Cutouts normally come from the public S3 bucket first. The tests never touch the
    # network, so that route is switched off here; the fallback test turns it on with a
    # stand-in for the bucket.
    os.environ["SPHEREX_USE_S3"] = "0"


@pytest.fixture(scope="session")
def cache_dir(pytestconfig: pytest.Config) -> Path:
    """The folder the backend uses as its cache during the tests (empty at the start)."""
    return pytestconfig.stash[_CACHE_DIR]


@pytest.fixture(scope="session", autouse=True)
def network_log(cache_dir: Path) -> Iterator[list[str]]:
    """In force for the whole run: isolated cache, no network. Yields the list of URLs asked for.

    Tests should use `network` below, which starts empty. This one is for fixtures that
    outlive a single test and need to clear and read the list themselves.
    """
    import requests
    from astropy.utils import data as astropy_data
    from astropy.utils import iers

    import backend.app  # noqa: F401 - imports every backend module, so each one is patched below
    from backend import spherex

    # If this fails, the backend was imported before pytest_configure ran, or it no longer
    # reads SPHEREX_CACHE_DIR. Either way the tests would be reading and writing the real cache.
    assert spherex.CACHE == cache_dir, f"the backend's cache is {spherex.CACHE}, not the test folder {cache_dir}"

    attempts: list[str] = []
    real_http_get = spherex.http_get

    def blocked_http_get(url: str, params: dict | None = None, **_: object) -> bytes:
        attempts.append(url)   # called from the six download threads; list.append is safe there
        raise spherex.ArchiveError(f"the network is blocked in tests: {url}")

    def blocked_request(self: object, method: str, url: str, *_: object, **__: object) -> None:
        attempts.append(str(url))
        raise NetworkBlocked(f"{method} {url}: the network is blocked in tests (see tests/conftest.py)")

    with pytest.MonkeyPatch.context() as patch:
        # `from .spherex import http_get` gives a module its own name for the function, so
        # replace it wherever it is found, not only in spherex.
        for name, module in list(sys.modules.items()):
            if name.split(".")[0] == "backend":
                for attr, value in list(vars(module).items()):
                    if value is real_http_get:
                        patch.setattr(module, attr, blocked_http_get)
        patch.setattr(requests.Session, "request", blocked_request)
        with astropy_data.conf.set_temp("allow_internet", False), iers.conf.set_temp("auto_download", False):
            yield attempts


@pytest.fixture
def network(network_log: list[str]) -> list[str]:
    """URLs the code tried to fetch during this test. Every attempt fails; the list starts empty."""
    network_log.clear()
    return network_log


@pytest.fixture(autouse=True)
def gaia_archive_not_known_to_be_down(network_log: list[str]) -> None:
    """Each test starts with ESA's Gaia archive not marked as down.

    The backend leaves that archive alone for ten minutes after it fails (astrometry._gaia_archive),
    and in the tests the blocked network makes it fail all the time: without this, whether a test
    asks the archive would depend on which test ran before it.
    """
    from backend import astrometry

    astrometry._gaia_down_until = 0.0


@pytest.fixture(scope="session")
def client(network_log: list[str]) -> Iterator[TestClient]:
    """The FastAPI app, called in-process: no server and no port."""
    from backend.app import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def barnard_exposures() -> list[dict]:
    """IRSA's list of the 364 exposures covering Barnard's Star (all six detectors), oldest first."""
    return json.loads((DATA_CACHE / "queries" / "sia_59eeb054c4d4ab68.json").read_text())


@pytest.fixture(scope="session")
def barnard_resolved() -> dict:
    """What /api/resolve answered for "Barnard's Star": Gaia DR3 position, motion and radial velocity."""
    return json.loads((DATA_CACHE / "queries" / "resolve_a876015f370716f8.json").read_text())


@pytest.fixture(scope="session")
def barnard(cache_dir: Path, barnard_exposures: list[dict], barnard_resolved: dict) -> SimpleNamespace:
    """Barnard's Star with its real data in the test cache, ready for build_frames and the API.

    Only nine of the 62 detector 5 cutouts are there. The exposure list is complete, so the
    backend asks the (blocked) archive for the other 53 and reports them as failures.
    `exposures_on_disk` is the list without those 53, for tests that need a complete result.
    """
    # copyfile, not the default copy2: find_exposures ignores a cached list older than a
    # day, judged by the file's modification time, and copy2 would keep the old time.
    shutil.copytree(DATA_CACHE, cache_dir, dirs_exist_ok=True, copy_function=shutil.copyfile)
    on_disk = {p.name.removesuffix("_D5.fits") for p in (DATA_CACHE / "cutouts").rglob("*_D5.fits")}
    return SimpleNamespace(
        ra=BARNARD_RA, dec=BARNARD_DEC, fov=0.1, detector=5,
        gaia_id=barnard_resolved["gaia_source_id"],
        motion={k: barnard_resolved[k] for k in ("pmra", "pmdec", "parallax")},
        exposures=barnard_exposures,
        cutouts_on_disk=sorted(on_disk),
        exposures_on_disk=[e for e in barnard_exposures if e["detector"] != 5 or e["obs_id"] in on_disk],
    )


@pytest.fixture
def write_cutout(tmp_path: Path) -> Callable[..., tuple[Path, WCS]]:
    """Write a made-up cutout laid out like a cached one, and return its path and sky WCS.

    For unit tests of the cleaning and measuring steps, where the right answer has to be
    known in advance. North is up, east is left, 6.15 arcsec per pixel, centred on (ra, dec).
    The file goes to the test's temporary folder. It is not an observation.
    """
    def write(image: np.ndarray, *, flags: np.ndarray | None = None, variance: float | np.ndarray = 9e-4,
              zodi: float | np.ndarray = 0.0, wave: float | np.ndarray = 4.0,
              bandwidth: float | np.ndarray = 0.035, ra: float = 150.0, dec: float = 20.0,
              mjd: float = 61000.0, name: str = "made_up.fits") -> tuple[Path, WCS]:
        image = np.asarray(image, dtype="float32")
        ny, nx = image.shape
        wcs = WCS(naxis=2)
        wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        wcs.wcs.crval = [ra, dec]
        wcs.wcs.crpix = [(nx + 1) / 2.0, (ny + 1) / 2.0]
        wcs.wcs.cdelt = [-NATIVE_ARCSEC / 3600.0, NATIVE_ARCSEC / 3600.0]
        header = wcs.to_header()
        header["MJD-AVG"] = mjd

        def plane(value: float | np.ndarray, dtype: str) -> np.ndarray:
            return np.broadcast_to(np.asarray(value, dtype=dtype), image.shape).copy()

        hdus = fits.HDUList([
            fits.PrimaryHDU(),
            fits.ImageHDU(image, header=header, name="IMAGE"),
            fits.ImageHDU(plane(0 if flags is None else flags, "int32"), name="FLAGS"),
            fits.ImageHDU(plane(variance, "float32"), name="VARIANCE"),
            fits.ImageHDU(plane(zodi, "float32"), name="ZODI"),
            fits.ImageHDU(plane(wave, "float32"), name="WAVE"),
            fits.ImageHDU(plane(bandwidth, "float32"), name="BANDWIDTH"),
        ])
        path = tmp_path / name
        hdus.writeto(path)
        return path, wcs

    return write
