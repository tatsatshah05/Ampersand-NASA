"""Probe 5: blind 'Earth-reflex' shift-and-stack of ONE SPHEREx visit, Eris field.

Model of a distant body inside one visit (tangent plane, arcsec, east/north):
    offset(t) = p0 + v * (t - t0) + (206265 / d) * F(t)
F(t) = parallax factor of the Earth's barycentric place (backend.distant.parallax_factor).
Only the part of F that is not a straight line in time can tell d; the straight part is absorbed by v.

(a) Arithmetic check on JPL's own track: least-squares fit of p0, v, 1/d to Horizons' places.
(b) Data: matched-filter flux maps of every visit-1 exposure (D1-D3) on a 3-arcsec sky grid, minus the
    same maps built from the other two visits' exposures nearest in wavelength (static sky removed).
    Grid search over v (east, north) and 1/d, including negative 1/d (Earth's motion reversed: the
    control, no real body follows it). Reports the strongest peaks and where they are relative to JPL.
"""
import json, sys, time
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_area
from astropy.stats import sigma_clipped_stats
from scipy.ndimage import convolve, map_coordinates
from backend import smallbodies, spherex, photometry, pipeline, distant

SP = sys.argv[1]
DETS = tuple(int(c) for c in (sys.argv[2] if len(sys.argv) > 2 else "123"))
name, number, lo, hi = "Eris", "136199", 60866.0, 60882.0
cov = json.load(open(f"{SP}/coverage.json"))
v1 = [e for e in cov[name] if lo <= e["mjd"] <= hi]
mids = np.array([smallbodies.exposure_mid_mjd(e) for e in v1])
eph = smallbodies.ephemeris(f"{number} {name}", list(mids))
era = np.array([p["ra"] for p in eph]); edec = np.array([p["dec"] for p in eph])
cra, cdec = float(np.median(era)), float(np.median(edec))
t0 = float(np.median(mids))
cosd = np.cos(np.radians(cdec))

# (a) arithmetic check on JPL's track
F = distant.parallax_factor(distant._earth(mids), cra, cdec)          # (n, 2) arcsec per arcsec of parallax
east = (era - cra) * cosd * 3600; north = (edec - cdec) * 3600
dt = mids - t0
A = np.zeros((2 * len(mids), 5))
A[0::2, 0] = 1; A[1::2, 1] = 1; A[0::2, 2] = dt; A[1::2, 3] = dt
A[0::2, 4] = F[:, 0] * 206264.806; A[1::2, 4] = F[:, 1] * 206264.806
b = np.empty(2 * len(mids)); b[0::2] = east; b[1::2] = north
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
resid = b - A @ sol
# what part of the parallax is not a straight line (the leverage on d), at the true distance
lin = np.column_stack([np.ones_like(dt), dt])
curv = []
for k in range(2):
    c, *_ = np.linalg.lstsq(lin, F[:, k], rcond=None)
    curv.append(F[:, k] - lin @ c)
curv = np.array(curv).T * 206264.806 * sol[4]
print(f"(a) JPL track, {len(mids)} exposures over {np.ptp(mids):.2f} d: fitted distance {1/sol[4]:.2f} AU, "
      f"drift ({sol[2]:.2f}, {sol[3]:.2f}) arcsec/day, rms residual {np.sqrt(np.mean(resid**2)):.3f} arcsec; "
      f"non-linear part of the parallax at that distance: peak-to-peak {np.ptp(curv[:,0]):.1f} E, {np.ptp(curv[:,1]):.1f} N arcsec")
# Horizons distance for comparison
import requests
hz = smallbodies._jpl_get(smallbodies.HORIZONS_URL, {"format": "json", "COMMAND": f"'{number};'", "CENTER": "'@-163182'",
     "EPHEM_TYPE": "OBSERVER", "TLIST": f"'{t0 + 2400000.5:.6f}'", "QUANTITIES": "'20'", "CSV_FORMAT": "YES", "OBJ_DATA": "NO"})
row = json.loads(hz)["result"].split("$$SOE")[1].split("$$EOE")[0].strip()
print("    Horizons observer distance (delta, AU) at the middle of the visit:", row)

# (b) data
SIZE, GRID_AS = 0.16, 3.0
allexp = spherex.find_exposures(cra, cdec)
paths = {(e["obs_id"], e["detector"]): p for e, p, err in spherex.fetch_cutouts(allexp, cra, cdec, SIZE)}
half = 0.065 * 3600
n = int(2 * half / GRID_AS) + 1
gx = (np.arange(n) - n // 2) * GRID_AS          # east offsets, arcsec
gy = (np.arange(n) - n // 2) * GRID_AS          # north offsets
GE, GN = np.meshgrid(gx, gy)
gra = cra + GE / 3600 / cosd; gdec = cdec + GN / 3600

def mf_map(path):
    with fits.open(path) as h:
        img = h["IMAGE"].data.astype(float); var = h["VARIANCE"].data.astype(float)
        fl = h["FLAGS"].data; z = h["ZODI"].data.astype(float); wave = h["WAVE"].data; hdr = h["IMAGE"].header
    d = img - z
    bad = ((fl & photometry.PHOTOMETRY_BAD) != 0) | ~np.isfinite(d) | ~np.isfinite(var) | pipeline.impossible_pixels(img, var)
    sky = ~bad & ((fl & photometry.SKY_BAD) == 0)
    _, med, _ = sigma_clipped_stats(d[sky] if sky.sum() > 200 else d[~bad], sigma=3, maxiters=5)
    d = np.where(bad, 0.0, d - med); v = np.where(bad, 0.0, var); good = (~bad).astype(float)
    sig = float(hdr.get("PSF_FWHM", 8.0)) / 6.15 / 2.3548
    r = np.arange(-4, 5)
    P = np.exp(-(r[None, :] ** 2 + r[:, None] ** 2) / (2 * sig ** 2)); P /= P.sum()
    num = convolve(d, P[::-1, ::-1], mode="constant"); den = convolve(good, (P ** 2)[::-1, ::-1], mode="constant")
    vv = convolve(v, (P ** 2)[::-1, ::-1], mode="constant")
    core = convolve(bad.astype(float), (P > 0.02).astype(float), mode="constant") > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        f = num / den; fv = vv / den ** 2
    f[core | (den <= 0)] = np.nan
    w = WCS(hdr); to = float(proj_plane_pixel_area(w)) * (np.pi / 180) ** 2 * 1e9
    x, y = w.all_world2pix(gra, gdec, 0)
    F_ = map_coordinates(f, [y, x], order=1, mode="constant", cval=np.nan) * to
    V_ = map_coordinates(fv, [y, x], order=1, mode="constant", cval=np.nan) * to ** 2
    wl = float(wave[wave.shape[0] // 2, wave.shape[1] // 2])
    return F_, V_, wl, float(hdr["MJD-AVG"])

t_start = time.time()
maps = {}
for e in allexp:
    if e["detector"] not in DETS:
        continue
    p = paths.get((e["obs_id"], e["detector"]))
    if p is None:
        continue
    maps[(e["obs_id"], e["detector"])] = (e, *mf_map(p))
print(f"matched-filter maps: {len(maps)} in {time.time()-t_start:.0f} s, grid {n}x{n} at {GRID_AS} arcsec")
inv = [k for k, m in maps.items() if lo <= m[0]["mjd"] <= hi]
oth = [k for k, m in maps.items() if not (lo <= m[0]["mjd"] <= hi)]
D, W, T, keys = [], [], [], []
for k in inv:
    e, Fm, Vm, wl, mjd = maps[k]
    cands = sorted((abs(maps[o][3] - wl), o) for o in oth if maps[o][0]["detector"] == e["detector"])[:2]
    tmpl = np.nanmean([maps[o][1] for _, o in cands], axis=0)
    tv = np.nanmean([maps[o][2] for _, o in cands], axis=0) / len(cands)
    diff = Fm - tmpl
    var = Vm + tv
    # bright static sources do not subtract cleanly (wavelength and sampling differ): leave them out
    from scipy.ndimage import binary_dilation
    brightstatic = binary_dilation(np.nan_to_num(np.abs(tmpl)) > 0.5, iterations=2)
    diff[brightstatic] = np.nan
    # empirical noise of this difference map (robust), used as the exposure's single weight
    s = 1.4826 * np.nanmedian(np.abs(diff - np.nanmedian(diff)))
    D.append(np.nan_to_num(diff)); W.append(np.isfinite(diff) / s ** 2); T.append(mjd); keys.append(k)
D = np.array(D); W = np.array(W); T = np.array(T)
print(f"{len(D)} visit-1 exposures used, detectors {DETS}")
Fd = distant.parallax_factor(distant._earth(T), cra, cdec) * 206264.806     # arcsec of shift per (1/AU)
dtt = T - t0
# keep only the part of the parallax that is not a straight line in time: the straight part is in v
_lin = np.column_stack([np.ones_like(dtt), dtt])
for _k in range(2):
    _c, *_ = np.linalg.lstsq(_lin, Fd[:, _k], rcond=None)
    Fd[:, _k] = Fd[:, _k] - _lin @ _c
print("non-linear parallax per (1/AU): peak-to-peak %.0f E, %.0f N arcsec" % (np.ptp(Fd[:, 0]), np.ptp(Fd[:, 1])))

def stack(ve, vn, invd):
    """Weighted mean flux map along the trial track (integer 3-arcsec shifts) and its S/N map."""
    oe = ve * dtt + invd * Fd[:, 0]; on = vn * dtt + invd * Fd[:, 1]
    ie = np.round(oe / GRID_AS).astype(int); jn = np.round(on / GRID_AS).astype(int)
    num = np.zeros((n, n)); den = np.zeros((n, n))
    for i in range(len(D)):
        # value at grid (y, x) of the stack = exposure i at (y + jn, x + ie)
        sx, sy = ie[i], jn[i]
        ys = slice(max(0, -sy), min(n, n - sy)); xs = slice(max(0, -sx), min(n, n - sx))
        ys2 = slice(max(0, sy), min(n, n + sy)); xs2 = slice(max(0, sx), min(n, n + sx))
        num[ys, xs] += (W[i] * D[i])[ys2, xs2]; den[ys, xs] += W[i][ys2, xs2]
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den, num / np.sqrt(den), den

# JPL truth in grid coordinates at t0
iE = np.interp(t0, mids, east); iN = np.interp(t0, mids, north)
print(f"JPL place at t0: east {iE:.1f} north {iN:.1f} arcsec from the centre")
VSTEP = 0.5
WSUM = np.array([np.max(w) for w in W]).sum()
vgrid = np.arange(-8, 8.01, VSTEP)
curv_scale = np.ptp(curv[:, 0]) * sol[4] if np.ptp(curv[:, 0]) > np.ptp(curv[:, 1]) else np.ptp(curv[:, 1]) * sol[4]
dinv = np.arange(-0.03, 0.0301, 0.0015)     # 1/AU; negative = Earth's motion reversed (control)
t_start = time.time()
best = []
at_jpl = {}
NEARJ = np.hypot(GE - iE, GN - iN) <= 6.0
nfull = 0
for invd in dinv:
    for ve in vgrid:
        for vn in vgrid:
            _, snr, den = stack(ve, vn, invd)
            ok = (den > 0.75 * WSUM) & np.isfinite(snr)
            vals = snr[ok]
            scale = 1.4826 * np.median(np.abs(vals - np.median(vals)))
            snr = (snr - np.median(vals)) / scale
            snr[~ok] = -np.inf
            j = np.nanargmax(snr)
            y, x = divmod(j, n)
            best.append((float(snr[y, x]), invd, ve, vn, gx[x], gy[y]))
            atj = float(np.max(np.where(NEARJ, snr, -np.inf)))
            if atj > at_jpl.get(round(invd, 5), (-1e9,))[0]:
                at_jpl[round(invd, 5)] = (atj, ve, vn)
            nfull += 1
print(f"{nfull} trial tracks in {time.time()-t_start:.0f} s")
best.sort(reverse=True)
json.dump(best[:20000], open(f"{SP}/eris_reflex_best.json", "w"))
print("top 8 trials (S/N, 1/d, v_east, v_north, east, north):")
for b_ in best[:8]:
    print("   %.1f  1/d=%.4f (d=%s)  v=(%.1f, %.1f)  at (%.0f, %.0f)  %.0f arcsec from JPL" % (
        b_[0], b_[1], "inf" if b_[1] == 0 else f"{1/b_[1]:.0f}", b_[2], b_[3], b_[4], b_[5], np.hypot(b_[4] - iE, b_[5] - iN)))
pos = [b_ for b_ in best if b_[1] > 1e-9]; neg = [b_ for b_ in best if b_[1] < -1e-9]; zero = [b_ for b_ in best if abs(b_[1]) <= 1e-9]
print("best with Earth's motion reversed (control):", neg[0], "\nbest with 1/d>0:", pos[0], "\nbest at d=inf:", zero[0] if zero else None)
near = [b_ for b_ in best if np.hypot(b_[4] - iE, b_[5] - iN) <= 8]
print("best trial peaking within 8 arcsec of JPL:", near[0] if near else None)
# S/N against 1/d for trials at Eris (best over drift), to read the distance
prof = {}
for b_ in near:
    prof[round(b_[1], 5)] = max(prof.get(round(b_[1], 5), -1e9), b_[0])
print("S/N within 6 arcsec of JPL's place, best over drift, against 1/d:")
for k in sorted(at_jpl):
    print("   1/d %+.4f  d %s  S/N %.1f  v=(%.1f, %.1f)" % (k, "inf" if abs(k) < 1e-9 else f"{1/k:.0f}", *at_jpl[k]))
json.dump({str(k): v for k, v in at_jpl.items()}, open(f"{SP}/eris_at_jpl.json", "w"))
far = [b_ for b_ in best if np.hypot(b_[4] - iE, b_[5] - iN) > 20]
print("best S/N of any trial peaking more than 20 arcsec from Eris:", far[0])
