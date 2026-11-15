"""Probe 7: distance of the blind Eris track from ONE visit, with sub-pixel tracks.

Starts from the strongest track of the blind coarse search (p5: peak 3 arcsec from JPL, v=(4.0,-3.5)
arcsec/day; JPL is used only at the end, to compare). Difference maps (visit minus the two nearest-in-
wavelength exposures of the other visits) on a 1.5-arcsec grid; for each trial 1/d the place and drift
are optimised (Nelder-Mead) on S = sum(w*D(track)) / sqrt(sum w), sampled bilinearly. The profile
S^2(1/d) gives the distance and its interval (S^2 within 1 of the best: profile likelihood, if S is in
noise units). S is put in noise units by the same track shape placed at 600 random places in the field."""
import json, sys
import numpy as np
from scipy.ndimage import map_coordinates, binary_dilation
from scipy.optimize import minimize
from backend import smallbodies, spherex, distant
import importlib.util

SP = sys.argv[1]
spec = importlib.util.spec_from_file_location("p5", f"{SP}/p5_reflex.py")
# re-use the map-making code of p5 without running its search: exec only the needed parts
src = open(f"{SP}/p5_reflex.py").read()
src = src.split("t_start = time.time()\nmaps = {}")[0]          # stop before the maps are made
src = src.replace("SIZE, GRID_AS = 0.16, 3.0", "SIZE, GRID_AS = 0.16, 1.5")
g = {"__name__": "p5part"}
sys.argv = [sys.argv[0], SP, "123"]
exec(compile(src, "p5part", "exec"), g)
mf_map, allexp, paths, lo, hi, DETS = g["mf_map"], g["allexp"], g["paths"], g["lo"], g["hi"], g["DETS"]
n, GRID_AS, gx, gy, t0, cra, cdec = g["n"], g["GRID_AS"], g["gx"], g["gy"], g["t0"], g["cra"], g["cdec"]
mids, east, north = g["mids"], g["east"], g["north"]

maps = {}
for e in allexp:
    if e["detector"] in DETS and (e["obs_id"], e["detector"]) in paths and paths[(e["obs_id"], e["detector"])]:
        maps[(e["obs_id"], e["detector"])] = (e, *mf_map(paths[(e["obs_id"], e["detector"])]))
inv = [k for k, m in maps.items() if lo <= m[0]["mjd"] <= hi]
oth = [k for k, m in maps.items() if not (lo <= m[0]["mjd"] <= hi)]
D, W, T = [], [], []
for k in inv:
    e, Fm, Vm, wl, mjd = maps[k]
    cands = sorted((abs(maps[o][3] - wl), o) for o in oth if maps[o][0]["detector"] == e["detector"])[:2]
    tmpl = np.nanmean([maps[o][1] for _, o in cands], axis=0)
    diff = Fm - tmpl
    diff[binary_dilation(np.nan_to_num(np.abs(tmpl)) > 0.5, iterations=4)] = np.nan
    s = 1.4826 * np.nanmedian(np.abs(diff - np.nanmedian(diff)))
    D.append(diff); W.append(1 / s ** 2); T.append(mjd)
D = np.array(D); W = np.array(W); T = np.array(T)
valid = np.isfinite(D).astype(float); D0 = np.nan_to_num(D)
dtt = T - t0
Fd = distant.parallax_factor(distant._earth(T), cra, cdec) * 206264.806
lin = np.column_stack([np.ones_like(dtt), dtt])
for k in range(2):
    c, *_ = np.linalg.lstsq(lin, Fd[:, k], rcond=None)
    Fd[:, k] -= lin @ c
idx = np.arange(len(D))

def S(params, invd):
    pe, pn, ve, vn = params
    oe = pe + ve * dtt + invd * Fd[:, 0]; on = pn + vn * dtt + invd * Fd[:, 1]
    x = oe / GRID_AS + n // 2; y = on / GRID_AS + n // 2
    val = map_coordinates(D0, [idx, y, x], order=1, mode="constant", cval=0.0)
    ok = map_coordinates(valid, [idx, y, x], order=1, mode="constant", cval=0.0) > 0.99
    w = W * ok
    if w.sum() < 0.75 * W.sum():
        return -1e9
    return float(np.sum(w * val) / np.sqrt(w.sum()))

start = np.array([-3.0, 0.0, 4.0, -3.5])
grid_invd = np.arange(-0.012, 0.0301, 0.0005)
prof = []
x0 = start.copy()
for invd in grid_invd:
    best = None
    for s0 in (x0, start):
        r = minimize(lambda p: -S(p, invd), s0, method="Nelder-Mead",
                     options={"xatol": 0.02, "fatol": 1e-4, "maxiter": 800, "initial_simplex": None})
        if best is None or r.fun < best.fun:
            best = r
    prof.append((invd, -best.fun, *best.x))
prof = np.array(prof)
ib = int(np.argmax(prof[:, 1]))
# noise units: the best track shape at random places
rng = np.random.default_rng(1)
rand = []
pe_b, pn_b, ve_b, vn_b = prof[ib, 2:]
for _ in range(600):
    pe, pn = rng.uniform(-180, 180, 2)
    if np.hypot(pe - pe_b, pn - pn_b) < 25:
        continue
    v = S([pe, pn, ve_b, vn_b], prof[ib, 0])
    if v > -1e8:
        rand.append(v)
rand = np.array(rand)
scale = 1.4826 * np.median(np.abs(rand - np.median(rand)))
snr = (prof[:, 1] - np.median(rand)) / scale
s2 = snr ** 2
inside = grid_invd[s2 >= s2[ib] - 1.0]
print(f"noise scale from {len(rand)} random places: {scale:.3f} (raw units), median {np.median(rand):.3f}")
print(f"best: 1/d = {grid_invd[ib]:.4f} -> d = {1/grid_invd[ib]:.1f} AU, S/N {snr[ib]:.2f}; place ({pe_b:.2f}, {pn_b:.2f}) arcsec, "
      f"drift ({ve_b:.3f}, {vn_b:.3f}) arcsec/day")
lo_i, hi_i = inside.min(), inside.max()
print(f"1-sigma interval in 1/d: {lo_i:.4f} .. {hi_i:.4f} -> d {1/hi_i:.0f} .. {('inf' if lo_i <= 0 else f'{1/lo_i:.0f}')} AU")
for invd, sn in zip(grid_invd[::4], snr[::4]):
    print(f"   1/d {invd:+.4f}  S/N {sn:.2f}")
i_inf = int(np.argmin(np.abs(grid_invd)))
print(f"S/N at d=inf {snr[i_inf]:.2f} (delta S^2 = {s2[ib]-s2[i_inf]:.1f}); reversed-Earth best {snr[grid_invd<0].max():.2f}")
# compare with JPL (only now)
jE = np.interp(t0, mids, east); jN = np.interp(t0, mids, north)
jv = np.polyfit(mids - t0, east, 1)[0], np.polyfit(mids - t0, north, 1)[0]
print(f"JPL at t0: ({jE:.2f}, {jN:.2f}) arcsec; offset of blind track {np.hypot(pe_b - jE, pn_b - jN):.2f} arcsec; "
      f"JPL apparent linear drift ({jv[0]:.3f}, {jv[1]:.3f}); JPL observer distance 95.51 AU")
json.dump({"invd": grid_invd.tolist(), "snr": snr.tolist(), "params": prof[:, 2:].tolist()}, open(f"{SP}/eris_profile.json", "w"))
