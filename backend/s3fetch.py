"""SPHEREx cutouts read straight from the public Amazon S3 copy of the archive.

IRSA's cutout service sends about 4 MB per cutout (a 3.9 MB table rides along) and
drops about one request in three. The same level-2 files are in a public S3 bucket,
where any byte range can be read over plain HTTPS with no account. This module reads
only the image rows a cutout needs and writes a file in exactly the format
`spherex.fetch_cutout` writes, so the rest of the backend cannot tell which route a
cutout took. It does not import `spherex`, so `spherex` can import it.

Confirmed against the live bucket on 2026-11-14 (`scripts/check_s3.py` repeats it):

- Address: `https://nasa-irsa-spherex.s3.amazonaws.com/<key>`; the key is the IRSA URL
  after `/ibe/data/spherex/`. One `Range` per request: a request naming two ranges is
  answered with the whole 65 MB file.
- Extensions, in this order: PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE.
  IMAGE, VARIANCE and ZODI are plain 2040 x 2040 float32 arrays, so image rows y0 to y1
  are one byte range. FLAGS is tile-compressed (Rice, one tile per image row); its size
  differs from file to file, so everything after it starts at a different byte in every
  file and the headers have to be read rather than assumed.
- IRSA's cutout changes only NAXIS1/NAXIS2 and the CRPIX values of the three coordinate
  systems in the header: the sky (TAN-SIP), "A" (position on the detector) and "W"
  (wavelength lookup table). SIP distortion and the lookup table are both defined
  relative to CRPIX, so moving CRPIX by the corner of the box is the whole change.
- Written this way, all 2,035 cutouts in the project's cache came out of S3 identical
  to IRSA's, byte for byte.
"""
from __future__ import annotations

import hashlib
import io
import os
import random
import re
import threading
import time
import warnings
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning, NoConvergence
from astropy.wcs.utils import proj_plane_pixel_scales
from requests.adapters import HTTPAdapter

warnings.simplefilter("ignore", FITSFixedWarning)

BUCKET_URL = "https://nasa-irsa-spherex.s3.amazonaws.com"
IRSA_DATA_PATH = "/ibe/data/spherex/"   # in an IRSA address, the S3 key is what follows this
USER_AGENT = "fits-range-reader/1.0"    # generic on purpose: says nothing about the project or its users
DEFAULT_CONCURRENCY = 16                # on a 300 Mbit/s line 16 at once carried 25 MB/s, 32 carried 33 MB/s

BLOCK = 2880                            # FITS files are built from blocks of this many bytes
CARD = 80                               # and headers from lines of this many
FIRST_READ = 14 * BLOCK                 # PRIMARY (1 block) and IMAGE header (8 or 9 blocks seen), with room
TABLE_HEADER_READ = 14 * BLOCK          # FLAGS header (6 blocks) plus its table of row positions (16,320 bytes)
HEADER_READ = 6 * BLOCK                 # VARIANCE and ZODI headers (4 blocks each in every file seen)
TAIL_READ = 3 * BLOCK                   # WCS-WAVE is the last 2 blocks of every file seen
MAX_HEADER = 200 * BLOCK                # no real header is this long: stop looking for its end
_END_CARD = b"END" + b" " * (CARD - 3)
_EMPTY_PRIMARY = fits.PrimaryHDU().header.tostring().encode("ascii")
_PIXEL_TYPES = {8: "u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}
# Header keywords of a coordinate system; the last letter, if any, says which system.
_SYSTEM_KEY = re.compile(r"(?:WCSAXES|WCSNAME|(?:CRPIX|CRVAL|CDELT|CROTA|CUNIT|CTYPE|CNAME)\d+|(?:PC|CD|PV|PS)\d+_\d+"
                         r"|LONPOLE|LATPOLE|RADESYS|EQUINOX)([A-Z]?)")
_SIP_KEY = re.compile(r"[AB]P?_(?:ORDER|DMAX|\d+_\d+)")   # distortion of the sky system
_SIZE_KEYS = ("NAXIS", "NAXIS1", "NAXIS2")
# Header lengths of VARIANCE and ZODI in the file read last, used to guess where their
# pixels start in the next file. Only ever a guess: see _RemoteFile.
_header_guess = {"VARIANCE": 4 * BLOCK, "ZODI": 4 * BLOCK}


class S3Error(RuntimeError):
    """The cutout could not be read from S3. The same cutout can still be asked of IRSA."""


class S3KeyMissing(S3Error):
    """The bucket holds no file under this exposure's key."""


class S3Changed(S3Error):
    """The file was replaced in the bucket between two reads of it."""


class S3LayoutError(S3Error):
    """The file is not laid out the way this reader was checked against, so it refuses to guess."""


@dataclass
class _Chunk:
    start: int
    data: bytes
    total: int   # size of the whole object
    etag: str


class S3Reader:
    """Byte ranges from the bucket: one connection pool, a cap on simultaneous requests, timeouts, retries.

    `max_concurrent` is the cap. Every read goes through a pool of that many threads,
    so sharing one reader between several callers keeps the cap for all of them together.
    A request that fails is tried again, `tries` times in all, waiting 0.4 s, 0.8 s, ...
    (plus or minus half) in between. Once a request has failed every time, all requests
    fail at once for `cooloff_s` seconds, so a caller with IRSA to fall back on is not
    kept waiting by a bucket that is down. `bucket_url` is there so that tests can
    point the reader at a stand-in for the bucket.
    """

    def __init__(self, max_concurrent: int = DEFAULT_CONCURRENCY, timeout: tuple[float, float] = (5.0, 10.0),
                 tries: int = 4, cooloff_s: float = 30.0, bucket_url: str = BUCKET_URL) -> None:
        if max_concurrent < 1 or tries < 1:
            raise ValueError("max_concurrent and tries must be at least 1")
        self.max_concurrent = max_concurrent
        self.timeout = timeout          # seconds to connect, seconds of silence allowed while reading
        self.tries = tries
        self.cooloff_s = cooloff_s
        self.bucket_url = bucket_url.rstrip("/")
        self.requests = 0               # counters, for timing reports
        self.bytes_read = 0
        self.retries = 0
        self._count_lock = threading.Lock()
        self._down_until = 0.0
        self._down_reason = ""
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._session.headers["Accept-Encoding"] = "identity"   # byte ranges must mean bytes of the file itself
        for scheme in ("https://", "http://"):
            self._session.mount(scheme, HTTPAdapter(pool_connections=1, pool_maxsize=max_concurrent))
        self._pool = ThreadPoolExecutor(max_concurrent, thread_name_prefix="s3range")

    def url_of(self, exp: dict) -> str:
        """The address of an exposure's file in this reader's bucket."""
        return f"{self.bucket_url}/{quote(s3_key(exp))}"

    def __enter__(self) -> S3Reader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._pool.shutdown(wait=True)
        self._session.close()

    def read_many(self, url: str, ranges: Sequence[tuple[int, int]], etag: str | None = None) -> list[_Chunk]:
        """Read byte ranges [start, end) of one object, all at the same time."""
        futures = [self._pool.submit(self._read_one, url, start, end, etag) for start, end in ranges]
        return [f.result() for f in futures]

    def _read_one(self, url: str, start: int, end: int, etag: str | None) -> _Chunk:
        what = f"bytes {start}-{end - 1} of {url}"
        headers = {"Range": f"bytes={start}-{end - 1}"}
        if etag:
            headers["If-Match"] = etag   # S3 answers 412 if the file is no longer the one first read
        problem = "no attempt made"
        for attempt in range(self.tries):
            # After a run of failures, later requests fail at once for a while instead of each
            # waiting through its own retries. A caller with a fallback gets to it quickly.
            if time.monotonic() < self._down_until:
                raise S3Error(f"S3 did not answer a moment ago ({self._down_reason}); not asking again yet")
            if attempt:
                with self._count_lock:
                    self.retries += 1
                time.sleep(min(0.4 * 2 ** (attempt - 1), 5.0) * random.uniform(0.5, 1.5))
            try:
                with self._session.get(url, headers=headers, timeout=self.timeout, stream=True) as r:
                    status = r.status_code
                    if status == 206:
                        # In pieces of 1 MB: requests' own r.content takes 10 kB at a time, which
                        # costs more processor time than everything else in this module together.
                        body = b"".join(r.iter_content(1 << 20))
                        first, last, total = _content_range(r.headers.get("Content-Range", ""))
                        # S3 cuts a range short only where the file ends.
                        if first == start and len(body) == last - first + 1 and last == min(end, total) - 1:
                            with self._count_lock:
                                self.requests += 1
                                self.bytes_read += len(body)
                            return _Chunk(start, body, total, r.headers.get("ETag", ""))
                        problem = f"{len(body)} bytes with Content-Range {r.headers.get('Content-Range')!r}"
                        continue
                    if status in (429, 500, 502, 503, 504):   # 503 is how S3 says "slow down"
                        problem = f"HTTP {status}"
                        continue
            except requests.RequestException as e:   # no connection, timeout, answer cut off
                problem = type(e).__name__
                continue
            # Any other answer will be the same next time.
            if status == 404:
                raise S3KeyMissing(f"the bucket has no file {unquote(urlsplit(url).path).lstrip('/')}")
            if status == 412:
                raise S3Changed(f"the file changed in the bucket while it was being read: {url}")
            if status == 200:
                raise S3Error(f"the server ignored the Range header and offered the whole file, reading {what}")
            raise S3Error(f"HTTP {status} reading {what}")
        self._down_reason = problem
        self._down_until = time.monotonic() + self.cooloff_s
        raise S3Error(f"{problem} after {self.tries} tries, reading {what}")


_default_reader: S3Reader | None = None
_default_reader_lock = threading.Lock()


def default_reader() -> S3Reader:
    """The reader shared by every call that does not bring its own."""
    global _default_reader
    with _default_reader_lock:
        if _default_reader is None:
            _default_reader = S3Reader()
        return _default_reader


def _content_range(value: str) -> tuple[int, int, int]:
    """'bytes 0-99/64952640' -> (0, 99, 64952640); (-1, -1, -1) if it is anything else."""
    m = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", value.strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else (-1, -1, -1)


class _RemoteFile:
    """One S3 object seen as a row of bytes. Whatever has been read stays in memory.

    A read that an earlier one covers costs nothing. That lets `read_cutout` ask early
    for bytes it will probably need, before the headers that say so have arrived: a
    wrong guess wastes a request but cannot put a wrong byte anywhere, because every
    piece is kept under the offset it was read from.
    """

    def __init__(self, reader: S3Reader, url: str) -> None:
        self.reader = reader
        self.url = url
        self.size = 0    # not known until the first read
        self.etag = ""
        self._pieces: list[tuple[int, bytes]] = []

    def _held(self, start: int, end: int) -> memoryview | None:
        for first, data in self._pieces:
            if first <= start and end <= first + len(data):
                return memoryview(data)[start - first:end - first]
        return None

    def fetch(self, ranges: Sequence[tuple[int, int]]) -> None:
        """Read byte ranges [start, end) at the same time, skipping what is already held."""
        wanted: list[tuple[int, int]] = []
        for start, end in ranges:
            start = max(start, 0)
            if self.size:
                end = min(end, self.size)
            if start < end and self._held(start, end) is None and (start, end) not in wanted:
                wanted.append((start, end))
        if not wanted:
            return
        for chunk in self.reader.read_many(self.url, wanted, self.etag or None):
            if self.size and chunk.total != self.size:
                raise S3Changed(f"the file changed size in the bucket while it was being read: {self.url}")
            self.size = chunk.total
            self.etag = self.etag or chunk.etag
            self._pieces.append((chunk.start, chunk.data))

    def get(self, start: int, end: int) -> memoryview:
        """Bytes start to end-1, from memory if an earlier read covers them."""
        if self.size and end > self.size:
            raise S3LayoutError(f"the file ends at byte {self.size}, before byte {end}: {self.url}")
        held = self._held(start, end)
        if held is None:
            self.fetch([(start, end)])
            held = self._held(start, end)
            if held is None:
                raise S3LayoutError(f"the file ends at byte {self.size}, before byte {end}: {self.url}")
        return held

    def held_from(self, start: int) -> memoryview | None:
        """Whatever is in memory from this offset onwards, if anything."""
        best: memoryview | None = None
        for first, data in self._pieces:
            if first <= start < first + len(data) and (best is None or first + len(data) - start > len(best)):
                best = memoryview(data)[start - first:]
        return best


@dataclass
class _Hdu:
    """One extension of the remote file: its header and where its data sits."""

    header: fits.Header
    start: int
    header_size: int
    data_size: int   # without the padding to a whole block

    @property
    def name(self) -> str:
        return str(self.header.get("EXTNAME", "PRIMARY")).strip()

    @property
    def data_start(self) -> int:
        return self.start + self.header_size

    @property
    def end(self) -> int:
        return self.data_start + _padded(self.data_size)

    @property
    def compressed(self) -> bool:
        """A tile-compressed image: stored as a table with one row per tile."""
        return self.header.get("XTENSION") == "BINTABLE" and bool(self.header.get("ZIMAGE", False))

    @property
    def shape(self) -> tuple[int, int]:
        """(width, height) of the image in pixels."""
        z = "Z" if self.compressed else ""
        if self.header[z + "NAXIS"] != 2:
            raise S3LayoutError(f"the {self.name} extension is not a 2-D image")
        return int(self.header[z + "NAXIS1"]), int(self.header[z + "NAXIS2"])


def _padded(n: int) -> int:
    return -(-n // BLOCK) * BLOCK


def _parse_header(buf: memoryview) -> tuple[fits.Header, int] | None:
    """The FITS header at the start of buf and its length in bytes. None if buf stops before its END line."""
    data = bytes(buf[:MAX_HEADER])
    if len(data) < CARD:
        return None
    if data[:9] not in (b"SIMPLE  =", b"XTENSION="):
        raise S3LayoutError(f"expected a FITS header, found {data[:20]!r}")
    pos = data.find(_END_CARD)
    while pos != -1 and pos % CARD:
        pos = data.find(_END_CARD, pos + 1)
    if pos == -1:
        return None
    return fits.Header.fromstring(data[:pos + CARD].decode("ascii")), _padded(pos + CARD)


def _hdu_at(remote: _RemoteFile, offset: int, first_read: int = HEADER_READ) -> _Hdu:
    """The extension whose header starts at this byte. Reads more of the file if it has to."""
    buf = remote.held_from(offset)
    want = first_read
    while True:
        if buf is not None:
            parsed = _parse_header(buf)
            if parsed is not None:
                break
            if len(buf) >= MAX_HEADER or (remote.size and offset + len(buf) >= remote.size):
                raise S3LayoutError(f"no complete FITS header at byte {offset} of {remote.url}")
            want = max(want, 2 * len(buf))
        buf = remote.get(offset, min(offset + want, remote.size) if remote.size else offset + want)
    header, header_size = parsed
    naxis = int(header["NAXIS"])
    pixels = 1 if naxis else 0
    for i in range(1, naxis + 1):
        pixels *= int(header[f"NAXIS{i}"])
    data_size = abs(int(header["BITPIX"])) // 8 * int(header.get("GCOUNT", 1)) * (int(header.get("PCOUNT", 0)) + pixels)
    return _Hdu(header, offset, header_size, data_size)


def _expect(hdu: _Hdu, name: str) -> _Hdu:
    if hdu.name != name:
        raise S3LayoutError(f"expected the {name} extension at byte {hdu.start}, found {hdu.name}")
    return hdu


def s3_key(exp: dict) -> str:
    """Where an exposure's file sits in the bucket: its IRSA address after /ibe/data/spherex/.

    Each archive search row also gives the key in `cloud_access`; for all 364 rows at
    Barnard's Star it is this same string.
    """
    _, found, key = str(exp["url"]).partition(IRSA_DATA_PATH)
    if not found or not key:
        raise S3Error(f"cannot tell the S3 key from the address {exp['url']}")
    return key


def s3_url(exp: dict) -> str:
    return f"{BUCKET_URL}/{quote(s3_key(exp))}"


def cutout_path(root: Path, exp: dict, ra: float, dec: float, size_deg: float) -> Path:
    """The file name `spherex._cutout_path` would choose, under a folder of the caller's choice."""
    tag = hashlib.sha1(f"{ra:.5f},{dec:.5f},{size_deg:.4f}".encode()).hexdigest()[:10]
    return Path(root) / tag / f"{exp['obs_id']}_D{exp['detector']}.fits"


def cutout_box(header: fits.Header, ra: float, dec: float, size_deg: float, pad: int = 0) -> tuple[int, int, int, int]:
    """The pixels IRSA's cutout service returns for this centre and size: (x0, x1, y0, y1).

    0-based, on the full detector image, x1 and y1 exclusive. IRSA does not document
    its rule. This one was worked out from the 2,035 cutouts in the project's cache
    (sizes 0.15 and 0.3 degrees, five targets, 198 of them clipped by a detector edge)
    and reproduces every one of them:

    - the centre goes to a pixel position with the full WCS, SIP distortion included;
    - the size becomes a whole number of pixels per axis, size / pixel scale rounded,
      the scale being that of the linear part of the WCS along that axis;
    - the box starts at ceil(centre - n / 2) and is n pixels long, clipped to the image.

    That is where astropy's Cutout2D puts a box of nx by ny pixels. Cutout2D handed
    the angular size itself is NOT the same: it takes the height from the x scale and
    the width from the y scale, and lands one pixel off whenever the two round apart.

    `pad` adds that many pixels on every side, for a caller that wants a margin.
    """
    # spherex.fetch_cutout puts the centre in IRSA's URL with 6 decimals and the size with 5.
    ra, dec, size_deg = float(f"{ra:.6f}"), float(f"{dec:.6f}"), float(f"{size_deg:.5f}")
    kind = (header.get("CTYPE1"), header.get("CTYPE2"), header.get("CUNIT1"), header.get("CUNIT2"))
    if kind != ("RA---TAN-SIP", "DEC--TAN-SIP", "deg", "deg"):
        raise S3LayoutError(f"sky coordinates of a kind this reader was not checked on: {kind}")
    wcs = WCS(_wcs_lines(header, ""))
    try:
        x, y = (float(v) for v in wcs.all_world2pix(ra, dec, 0))
    except NoConvergence as e:
        raise S3Error(f"({ra}, {dec}) is too far from this image to place on it") from e
    scale_x, scale_y = proj_plane_pixel_scales(wcs)   # degrees per pixel
    nx, ny = int(np.round(size_deg / scale_x)), int(np.round(size_deg / scale_y))
    x0, y0 = int(np.ceil(x - nx / 2)), int(np.ceil(y - ny / 2))
    x0, x1 = max(x0 - pad, 0), min(x0 + nx + pad, int(header["NAXIS1"]))
    y0, y1 = max(y0 - pad, 0), min(y0 + ny + pad, int(header["NAXIS2"]))
    if x0 >= x1 or y0 >= y1:
        raise S3Error(f"a {size_deg} degree patch at ({ra}, {dec}) does not overlap this image")
    return x0, x1, y0, y1


def _wcs_lines(header: fits.Header, system: str) -> fits.Header:
    """Only the header lines of one coordinate system: "" for the sky, or its letter.

    astropy builds a WCS from the text of the whole header, more than once. With 276
    lines, most of them nothing to do with coordinates, that takes 13 ms of processor
    time per WCS. The lines of the one system give the same numbers to the last bit
    (the cutouts still come out byte for byte IRSA's) in 2 to 4 ms. The lines are
    shared with `header`, not copied: the result is for reading only.
    """
    out = fits.Header()
    for card in header.cards:
        m = _SYSTEM_KEY.fullmatch(card.keyword)
        if (m and m[1] == system) or (not system and _SIP_KEY.fullmatch(card.keyword)) or card.keyword in _SIZE_KEYS:
            out.append(card)
    return out


def _shift_crpix(header: fits.Header, x0: int, y0: int) -> None:
    """Move every CRPIX of a header by the corner of the box, in place.

    CRPIX1/2 is the sky WCS (SIP polynomials are in pixels from CRPIX, so they need no
    change), CRPIX1A/2A the detector position, CRPIX1W/2W the wavelength lookup.

    The arithmetic copies IRSA's to the last bit. The sky CRPIX is the old one minus
    the corner, rounded to 15 significant digits (what wcslib prints). The others
    move by the difference between the new and old sky CRPIX, and are written as
    decimals even where they are whole numbers. For the usual CRPIX of 1020.5 this is
    plain subtraction. About 1 exposure in 200 has another value (1023.8, 1135.6 or
    1017.2, 905.4 or 1020.5, 1031.5), and there the steps matter: 1135.6 - 458 gives
    677.5999999999999, IRSA writes 677.6, and its CRPIX2A and CRPIX2W become
    -456.9999999999999, not -457.
    """
    for axis, corner in (("1", x0), ("2", y0)):
        old = float(header["CRPIX" + axis])
        new = float(f"{old - corner:.15g}")
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            key = f"CRPIX{axis}{letter}"
            if key in header:
                header[key] = float(header[key]) + (new - old)
        header["CRPIX" + axis] = new


def _tiles(remote: _RemoteFile, hdu: _Hdu, y0: int, y1: int) -> tuple[int, int, int, int, np.ndarray]:
    """For image rows y0 to y1-1 of a tile-compressed image: where their compressed bytes are.

    Returns (byte offset in the file where they start, where they end, first tile row,
    one past the last tile row, table rows for those tiles with positions counted from
    the first of these bytes). Handles tiles that span the full image width and any
    number of image rows; in every file seen a tile is exactly one image row.
    """
    h = hdu.header
    width, height = hdu.shape
    tile_h = int(h.get("ZTILE2", 1))
    m = re.fullmatch(r"1?([PQ])B(\(\d+\))?", str(h.get("TFORM1", "")).strip())
    if int(h.get("ZTILE1", width)) != width or int(h["TFIELDS"]) != 1 or not m:
        raise S3LayoutError(f"the {hdu.name} extension is compressed in a way this reader does not handle")
    kind = ">i4" if m[1] == "P" else ">i8"   # each table row: (number of bytes, position in the heap)
    row_bytes, n_rows = int(h["NAXIS1"]), int(h["NAXIS2"])
    if row_bytes != 2 * np.dtype(kind).itemsize or n_rows != -(-height // tile_h):
        raise S3LayoutError(f"the {hdu.name} table of compressed tiles has an unexpected shape")
    t0, t1 = y0 // tile_h, -(-y1 // tile_h)
    table = remote.get(hdu.data_start, hdu.data_start + row_bytes * n_rows)
    rows = np.frombuffer(table, dtype=kind).reshape(n_rows, 2)[t0:t1].astype(np.int64)
    first, last = int(np.min(rows[:, 1])), int(np.max(rows[:, 0] + rows[:, 1]))
    if last - first > 4 * int(rows[:, 0].sum()) + 65536:
        raise S3LayoutError(f"the compressed tiles of {hdu.name} are not stored next to each other")
    heap = hdu.data_start + int(h.get("THEAP", row_bytes * n_rows))
    rows[:, 1] -= first
    return heap + first, heap + last, t0, t1, rows.astype(kind)


def _row_ranges(remote: _RemoteFile, hdu: _Hdu, y0: int, y1: int) -> list[tuple[int, int]]:
    """The byte range of the file that holds image rows y0 to y1-1 of an extension."""
    if hdu.compressed:
        start, end, *_ = _tiles(remote, hdu, y0, y1)
        return [(start, end)]
    width, _ = hdu.shape
    row = width * abs(int(hdu.header["BITPIX"])) // 8
    return [(hdu.data_start + y0 * row, hdu.data_start + y1 * row)]


def _pixels(remote: _RemoteFile, hdu: _Hdu, x0: int, x1: int, y0: int, y1: int) -> tuple[np.ndarray, fits.Header]:
    """Pixels [y0:y1, x0:x1] of an image extension, and its header as a plain image header."""
    h = hdu.header
    width, _ = hdu.shape
    if not hdu.compressed:
        kind = _PIXEL_TYPES.get(int(h["BITPIX"]))
        if h.get("XTENSION") != "IMAGE" or kind is None or h.get("BSCALE", 1) != 1 or h.get("BZERO", 0) != 0:
            raise S3LayoutError(f"the {hdu.name} extension is not a plain image array")
        (start, end), = _row_ranges(remote, hdu, y0, y1)
        rows = np.frombuffer(remote.get(start, end), dtype=kind).reshape(y1 - y0, width)
        return np.ascontiguousarray(rows[:, x0:x1]), h

    # Compressed: the tiles of these rows, with their table rows, are a complete small
    # compressed image. Put a header on them and let astropy decompress it.
    start, end, t0, t1, table = _tiles(remote, hdu, y0, y1)
    heap = remote.get(start, end)
    tile_h = int(h.get("ZTILE2", 1))
    small = h.copy()
    small["NAXIS2"] = t1 - t0
    small["ZNAXIS2"] = min(t1 * tile_h, hdu.shape[1]) - t0 * tile_h
    small["PCOUNT"] = len(heap)
    small.remove("THEAP", ignore_missing=True)
    body = table.tobytes() + bytes(heap)
    raw = _EMPTY_PRIMARY + small.tostring().encode("ascii") + body + b"\0" * (_padded(len(body)) - len(body))
    with fits.open(io.BytesIO(raw)) as hdul:
        rows = np.asarray(hdul[1].data)
        image_header = hdul[1].header
    return np.ascontiguousarray(rows[y0 - t0 * tile_h:y1 - t0 * tile_h, x0:x1]), image_header


def _wave_table(remote: _RemoteFile, after: int) -> bytes:
    """The WCS-WAVE extension (header and data) as bytes.

    It has been the last extension of every file seen, so the end of the file is read
    early. If it is not there, the extensions after ZODI are walked one at a time.
    """
    start = max(remote.size - TAIL_READ, after)
    tail = remote.get(start, remote.size)
    for off in range(-start % BLOCK, len(tail), BLOCK):
        if bytes(tail[off:off + 9]) != b"XTENSION=":
            continue
        parsed = _parse_header(tail[off:])
        if parsed is not None and str(parsed[0].get("EXTNAME", "")).strip() == "WCS-WAVE":
            hdu = _hdu_at(remote, start + off)
            if hdu.end == remote.size:
                return bytes(tail[off:])
    pos = after
    while pos < remote.size:
        hdu = _hdu_at(remote, pos)
        if hdu.name == "WCS-WAVE":
            return bytes(remote.get(hdu.start, hdu.end))
        pos = hdu.end
    raise S3LayoutError(f"no WCS-WAVE extension in {remote.url}")


def _wavelengths(header: fits.Header, table: bytes, nx: int, ny: int) -> tuple[np.ndarray, np.ndarray]:
    """Wavelength and bandwidth of every pixel in microns, computed the way spherex.fetch_cutout does."""
    if (header.get("CTYPE1W"), header.get("CTYPE2W")) != ("WAVE-TAB", "WAVE-TAB"):
        raise S3LayoutError("no wavelength lookup of the kind this reader was checked on (CTYPE1W, CTYPE2W)")
    with fits.open(io.BytesIO(_EMPTY_PRIMARY + table)) as hdul:
        # Alternate WCS "W" is a -TAB lookup into the WCS-WAVE extension: axis 1 is
        # the central wavelength, axis 2 the bandwidth.
        spectral = WCS(_wcs_lines(header, "W"), fobj=hdul, key="W")
        spectral.sip = None
        xx, yy = np.meshgrid(np.arange(nx), np.arange(ny))
        wave, band = spectral.wcs_pix2world(xx, yy, 0)
    return wave.astype("float32"), band.astype("float32")


def read_cutout(exp: dict, ra: float, dec: float, size_deg: float, *, reader: S3Reader | None = None,
                pad: int = 0) -> fits.HDUList:
    """One cutout read from S3, in memory: PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, WAVE, BANDWIDTH.

    `exp` is an exposure as `spherex.find_exposures` returns it (only `url` is used).
    Raises S3Error (S3KeyMissing, S3LayoutError, ...) with a reason; nothing is ever
    filled in or approximated.
    """
    reader = reader or default_reader()
    url = reader.url_of(exp)
    try:
        return _read_cutout(_RemoteFile(reader, url), ra, dec, size_deg, pad)
    except S3Error:
        raise
    except (KeyError, ValueError, IndexError, OSError) as e:   # a header or table unlike those this was checked on
        raise S3LayoutError(f"{type(e).__name__}: {e}, reading {url}") from e


def _read_cutout(remote: _RemoteFile, ra: float, dec: float, size_deg: float, pad: int) -> fits.HDUList:
    # Three rounds of requests. Each round asks for everything that can be located
    # with what the round before it brought back.

    # Round 1: the start of the file, which holds the PRIMARY and IMAGE headers.
    remote.fetch([(0, FIRST_READ)])
    primary = _hdu_at(remote, 0)
    image = _expect(_hdu_at(remote, primary.end), "IMAGE")
    x0, x1, y0, y1 = cutout_box(image.header, ra, dec, size_deg, pad)
    nx, ny = x1 - x0, y1 - y0

    # Round 2: the IMAGE rows; the FLAGS header and its table of row positions (FLAGS
    # starts where IMAGE ends); and the end of the file, where the wavelength table is.
    remote.fetch([*_row_ranges(remote, image, y0, y1), (image.end, image.end + TABLE_HEADER_READ),
                  (remote.size - TAIL_READ, remote.size)])
    flags = _expect(_hdu_at(remote, image.end), "FLAGS")

    # Round 3: the FLAGS rows, and the VARIANCE header, which starts where FLAGS ends.
    # That place differs from file to file and is only known now. VARIANCE and ZODI
    # headers have been the same length in every file, so on that guess the VARIANCE
    # rows, the ZODI header and the ZODI rows are asked for in this round too.
    width, _ = image.shape
    row = width * abs(int(image.header["BITPIX"])) // 8
    variance_data = flags.end + _header_guess["VARIANCE"]
    zodi_start = variance_data + _padded(image.data_size)
    zodi_data = zodi_start + _header_guess["ZODI"]
    remote.fetch([*_row_ranges(remote, flags, y0, y1), (flags.end, flags.end + HEADER_READ),
                  (variance_data + y0 * row, variance_data + y1 * row), (zodi_start, zodi_start + HEADER_READ),
                  (zodi_data + y0 * row, zodi_data + y1 * row)])
    variance = _expect(_hdu_at(remote, flags.end), "VARIANCE")
    zodi = _expect(_hdu_at(remote, variance.end), "ZODI")
    _header_guess.update(VARIANCE=variance.header_size, ZODI=zodi.header_size)
    # If a guess was wrong the rows are read now, from where the headers say they are.
    remote.fetch([*_row_ranges(remote, variance, y0, y1), *_row_ranges(remote, zodi, y0, y1)])

    out = fits.HDUList([fits.PrimaryHDU()])
    for hdu in (image, flags, variance, zodi):
        if hdu.shape != image.shape:
            raise S3LayoutError(f"{hdu.name} is {hdu.shape} pixels but IMAGE is {image.shape}")
        data, header = _pixels(remote, hdu, x0, x1, y0, y1)
        cut = fits.ImageHDU(data, header=header, name=hdu.name)   # copies the header and sets NAXIS1, NAXIS2
        _shift_crpix(cut.header, x0, y0)
        out.append(cut)
    wave, band = _wavelengths(out["IMAGE"].header, _wave_table(remote, zodi.end), nx, ny)
    out.append(fits.ImageHDU(wave, name="WAVE"))
    out.append(fits.ImageHDU(band, name="BANDWIDTH"))
    return out


def fetch_cutout(exp: dict, ra: float, dec: float, size_deg: float, path: Path, *, reader: S3Reader | None = None,
                 pad: int = 0, overwrite: bool = False) -> Path:
    """Read one cutout from S3 and write it to `path`, in the format of `spherex.fetch_cutout`.

    A file already at `path` is kept unless `overwrite` is set. The file is written
    under a temporary name and renamed, so no reader ever sees half of it. Raises
    S3Error with a reason if the cutout cannot be read; no file is left behind then.
    """
    path = Path(path)
    if path.exists() and not overwrite:
        return path
    try:
        hdul = read_cutout(exp, ra, dec, size_deg, reader=reader, pad=pad)
    except S3Changed:   # the archive replaced the file between two of our reads: start again, once
        hdul = read_cutout(exp, ra, dec, size_deg, reader=reader, pad=pad)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Process and thread in the name: two of them may fetch the same cutout at once.
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        # The header lines are the archive's own. Having astropy check each of the 800
        # again before writing takes 10 ms per cutout and changes no byte.
        hdul.writeto(tmp, overwrite=True, output_verify="ignore")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def fetch_cutouts(exposures: list[dict], ra: float, dec: float, size_deg: float, root: Path, *,
                  max_concurrent: int = DEFAULT_CONCURRENCY, reader: S3Reader | None = None,
                  progress: Callable[[int, int], None] | None = None, pad: int = 0,
                  overwrite: bool = False) -> list[tuple[dict, Path | None, str | None]]:
    """Fetch many cutouts from S3 into `root`, at most `max_concurrent` requests at a time.

    Files are named as `spherex._cutout_path` names them, under `root`. Returns
    (exposure, path, error) for each, in the order given, like `spherex.fetch_cutouts`:
    a cutout that could not be read has path None and a reason, and is never replaced
    with anything. Pass a `reader` to share one cap (the reader's own) and one set of
    connections between calls, as a server answering several people at once should.
    """
    def one(exp: dict) -> tuple[dict, Path | None, str | None]:
        try:
            path = cutout_path(root, exp, ra, dec, size_deg)
            return exp, fetch_cutout(exp, ra, dec, size_deg, path, reader=shared, pad=pad, overwrite=overwrite), None
        except Exception as e:  # noqa: BLE001 - report every failure to the caller
            return exp, None, f"{type(e).__name__}: {e}"

    shared = reader or S3Reader(max_concurrent)
    results = []
    try:
        # One exposure needs up to five ranges at once, so half as many exposures in hand
        # as the request cap keeps the requests flowing. More in hand gained 5 per cent
        # and holds more in memory: an exposure in hand is 3 MB at 0.15 degrees, 8 MB at 0.5.
        with ThreadPoolExecutor(max(1, (shared.max_concurrent + 1) // 2)) as pool:
            for n, res in enumerate(pool.map(one, exposures), 1):
                results.append(res)
                if progress:
                    progress(n, len(exposures))
    finally:
        if reader is None:
            shared.close()
    return results
