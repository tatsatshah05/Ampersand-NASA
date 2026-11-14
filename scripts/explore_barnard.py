"""Scratch exploration: what does IRSA actually hold for Barnard's Star?

Run:  .venv/bin/python scripts/explore_barnard.py

Confirms, against the live service, every lead in CLAUDE.md: the SIA2 query, the
real column names, the cutout URL syntax, the FITS extensions, the header keys for
time and detector, and how to read the wavelength at the star's pixel.
Nothing here is used by the backend; it only prints.
"""
import io
import sys
import time
import warnings

import numpy as np
import requests
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.time import Time
from astropy.wcs import WCS, FITSFixedWarning

warnings.simplefilter("ignore", FITSFixedWarning)

SIA = "https://irsa.ipac.caltech.edu/SIA"
COLLECTIONS = ["spherex_dr1", "spherex_qr3"]
GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
BARNARD_GAIA_DR3 = 4472832130942575872
S = requests.Session()


def get(url, params=None, tries=12, timeout=120):
    """GET with retries. IRSA's proxy returns a fast 502 on roughly 1 request in 3."""
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            err = f"http {r.status_code}"
        except requests.RequestException as e:
            err = repr(e)[:100]
        print(f"    (retry {i + 1}: {err})")
        time.sleep(min(1.5 * (i + 1), 10))
    sys.exit(f"gave up on {url}")


def section(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ---------------------------------------------------------------- 1. Gaia
section("1. Gaia DR3 astrometry for Barnard's Star")
t = time.time()
q = ("SELECT source_id, ra, dec, pmra, pmdec, parallax, radial_velocity, ref_epoch, "
     f"phot_g_mean_mag FROM gaiadr3.gaia_source WHERE source_id = {BARNARD_GAIA_DR3}")
r = get(GAIA_TAP, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": q})
g = parse_single_table(io.BytesIO(r.content)).to_table(use_names_over_ids=True)[0]
print(f"Gaia TAP answered in {time.time() - t:.1f}s")
for k in g.colnames:
    print(f"  {k:18s} {g[k]}")
pm_total = float(np.hypot(g["pmra"], g["pmdec"]))
print(f"  total proper motion {pm_total / 1000:.3f} arcsec/yr")

star = SkyCoord(ra=g["ra"] * u.deg, dec=g["dec"] * u.deg,
                pm_ra_cosdec=g["pmra"] * u.mas / u.yr, pm_dec=g["pmdec"] * u.mas / u.yr,
                distance=(1000.0 / g["parallax"]) * u.pc,
                radial_velocity=g["radial_velocity"] * u.km / u.s,
                obstime=Time(g["ref_epoch"], format="jyear"))
j2000 = star.apply_space_motion(Time("J2000"))
now = star.apply_space_motion(Time("2026-01-01"))
print(f"  position J2000.0   {j2000.ra.deg:.6f} {j2000.dec.deg:.6f}")
print(f"  position 2026.0    {now.ra.deg:.6f} {now.dec.deg:.6f}")
print(f"  moved since J2000  {j2000.separation(now).arcmin:.2f} arcmin")

# ---------------------------------------------------------------- 2. SIA
section("2. SIA2 query: which SPHEREx images cover the star?")
tables = []
for coll in COLLECTIONS:
    t = time.time()
    r = get(SIA, {"COLLECTION": coll, "POS": f"circle {now.ra.deg} {now.dec.deg} 0.01"})
    tb = parse_single_table(io.BytesIO(r.content)).to_table(use_names_over_ids=True)
    print(f"{coll}: {len(tb)} rows, {len(r.content) / 1e6:.2f} MB, {time.time() - t:.1f}s")
    tables.append(tb)
print("\ncolumns:", ", ".join(tables[0].colnames))

rows = []
for tb in tables:
    for row in tb:
        rows.append(dict(url=str(row["access_url"]), det=int(str(row["energy_bandpassname"])[-1]),
                         mjd=float(row["t_min"]), exptime=float(row["t_exptime"]),
                         obs_id=str(row["obs_id"]), coll=str(row["obs_collection"]),
                         em_min=float(row["em_min"]) * 1e6, em_max=float(row["em_max"]) * 1e6,
                         size_kb=int(row["access_estsize"])))
rows.sort(key=lambda d: d["mjd"])
print(f"\ntotal exposures covering the star: {len(rows)}")
print(f"dates: {Time(rows[0]['mjd'], format='mjd').iso[:10]} to {Time(rows[-1]['mjd'], format='mjd').iso[:10]}")
print(f"exposure time: {np.median([d['exptime'] for d in rows]):.1f}s; "
      f"full file size: {np.median([d['size_kb'] for d in rows]) / 1000:.0f} MB")
print("detector wavelength ranges (um):")
for det in range(1, 7):
    d = [x for x in rows if x["det"] == det]
    print(f"  D{det}: {d[0]['em_min']:.2f} to {d[0]['em_max']:.2f}   ({len(d)} exposures)")

# ---------------------------------------------------------------- 3. epochs
section("3. How the exposures cluster in time (new epoch after a gap of > 30 days)")
epochs, cur = [], [rows[0]]
for d in rows[1:]:
    if d["mjd"] - cur[-1]["mjd"] > 30:
        epochs.append(cur)
        cur = [d]
    else:
        cur.append(d)
epochs.append(cur)
for i, ep in enumerate(epochs):
    m = np.array([d["mjd"] for d in ep])
    per_det = [sum(1 for d in ep if d["det"] == k) for k in range(1, 7)]
    nights = len(set(np.floor(m).astype(int)))
    print(f"epoch {i + 1}: {Time(m.min(), format='mjd').iso[:10]} to {Time(m.max(), format='mjd').iso[:10]}"
          f"  span {m.max() - m.min():5.1f} d  {len(ep):3d} exposures on {nights} days"
          f"  per detector D1..D6 = {per_det}  collections = {sorted(set(d['coll'] for d in ep))}")

# ---------------------------------------------------------------- 4. cutouts
section("4. Download three cutouts (one per epoch, detector 3) and look inside")
SIZE_DEG = 0.1
picks = []
for ep in epochs:
    cand = [d for d in ep if d["det"] == 3]
    if cand:
        picks.append(cand[len(cand) // 2])
for n, d in enumerate(picks[:3]):
    when = Time(d["mjd"], format="mjd")
    pos = star.apply_space_motion(when)
    url = f"{d['url']}?center={pos.ra.deg:.6f},{pos.dec.deg:.6f}&size={SIZE_DEG}"
    t = time.time()
    r = get(url)
    dt = time.time() - t
    print(f"\n--- cutout {n + 1}: {d['obs_id']} D{d['det']} {when.iso[:19]} ({d['coll']})")
    print(f"    {url}")
    print(f"    {len(r.content) / 1e6:.2f} MB in {dt:.1f}s")
    with fits.open(io.BytesIO(r.content)) as hdul:
        if n == 0:
            hdul.info()
        img = hdul["IMAGE"]
        h = img.header
        print("    extensions:", [x.name for x in hdul])
        keys = [k for k in h if any(s in k for s in ("DATE", "MJD", "TIME", "DETECT", "OBSID", "EXPID",
                                                       "BUNIT", "EXPTIME", "VERSION", "L2 "))]
        for k in keys:
            print(f"    IMAGE header {k:9s}= {h[k]!r}")
        for name in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
            if name in hdul:
                a = hdul[name].data
                print(f"    {name:9s} shape {a.shape} dtype {a.dtype} "
                      f"min {np.nanmin(a):.4g} median {np.nanmedian(a):.4g} max {np.nanmax(a):.4g} "
                      f"BUNIT={hdul[name].header.get('BUNIT')}")
        w = WCS(h)
        x, y = w.world_to_pixel(pos)
        print(f"    star lands at cutout pixel x={float(x):.2f} y={float(y):.2f}; "
              f"pixel scale {np.mean([q.to_value(u.arcsec) for q in w.proj_plane_pixel_scales()]):.3f} arcsec")
        # Wavelength: the IMAGE header carries an alternate WCS "W" (a -TAB lookup)
        # that points at the WCS-WAVE binary table extension.
        try:
            ww = WCS(h, fobj=hdul, key="W")
            ww.sip = None
            lam, dlam = ww.wcs_pix2world(float(x), float(y), 0)
            print(f"    wavelength at the star: {float(lam):.4f} um, bandwidth {float(dlam):.4f} um "
                  f"(R = {float(lam) / float(dlam):.0f})")
            c = ww.wcs_pix2world([[0, 0], [img.data.shape[1] - 1, img.data.shape[0] - 1]], 0)
            print(f"    wavelength across this cutout: {c[0][0]:.4f} to {c[1][0]:.4f} um")
        except Exception as e:  # report, do not hide
            print(f"    !! reading wavelength via WCS key 'W' failed: {e!r}")
            if "WCS-WAVE" in hdul:
                print("    WCS-WAVE columns:", hdul["WCS-WAVE"].columns)
        yy, xx = int(round(float(y))), int(round(float(x)))
        sub = (img.data - hdul["ZODI"].data)[yy - 2:yy + 3, xx - 2:xx + 3]
        print("    5x5 pixels at the star, IMAGE minus ZODI (MJy/sr):")
        for line in sub:
            print("      " + " ".join(f"{v:9.2f}" for v in line))
        print(f"    FLAGS at the star pixel: {hdul['FLAGS'].data[yy, xx]} "
              f"(binary {int(hdul['FLAGS'].data[yy, xx]):022b})")
        if n == 0:
            mp = {k: h[k] for k in h if k.startswith("MP_")}
            if mp:
                print("    flag bit names from header:", mp)
