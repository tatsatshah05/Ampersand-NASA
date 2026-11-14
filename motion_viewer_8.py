
"""
SPHEREx motion viewer: motion display features + detector / field-of-view / mode controls.

How it works (and why):
  * The page asks a backend API for frames whenever a control changes:
        GET <api>?ra=..&dec=..&detector=1..6&fov=0.02..0.5&mode=normal|difference|sum
    Assumed JSON reply (change only normalizeFrame() in the page if yours differs):
        {"frames": [{"url": <image URL or data URL>, "label": "...",
                     "centroid": [x, y], "saturated_pixels": 0}, ...]}
    "difference" and "sum" answer HTTP 501 until the backend supports them.
  * The selected options live in the page URL (?det=5&fov=0.1&mode=normal), so a reload
    or a shared link restores them.
  * Python (a) writes the single self-contained HTML page and (b) provides a small demo
    backend so the whole flow can be tried without the real API.

Usage:
    python spherex_motion_viewer.py                       # demo backend + page at http://localhost:8000
    python spherex_motion_viewer.py --api https://host/api/frames --out viewer.html
        (the real API must allow cross-origin requests if the page is opened from a file)
"""
import argparse
import base64
import functools
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
from PIL import Image

PIXEL_SCALE_ARCSEC = 2.0  # frames are already resampled to 2 arcsec per pixel
SAT_LEVEL = 400.0         # demo detector full-well level (pixels at this value are "saturated")
# Detector id -> wavelength range in microns; labels in the page are built from this.
DETECTORS = {1: (0.75, 1.12), 2: (1.10, 1.65), 3: (1.63, 2.43),
             4: (2.40, 3.85), 5: (3.81, 4.43), 6: (4.41, 5.01)}
BARNARD_RA, BARNARD_DEC = 269.452, 4.693  # default target, degrees


def make_demo_frames(detector, fov, n=8, seed=1):
    """Synthetic frames of a field with one bright star drifting ~2 px north.

    Why: lets controls be tested without data. The cutout size follows the field of
    view (fov degrees -> pixels at 2 arcsec/pixel). Detectors 1-4 saturate on a bright
    star (blocky white core, `saturated_pixels` > 0); 5 and 6 stay clean, like real data.
    """
    size = int(round(fov * 3600 / PIXEL_SCALE_ARCSEC))
    rng = np.random.default_rng(seed + size)          # repeatable field for a given size
    yy, xx = np.mgrid[0:size, 0:size]                 # pixel coordinate grids for the Gaussians

    def star(x0, y0, peak, sigma=1.4):
        # A Gaussian blob approximates the telescope's point-spread function.
        return peak * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * sigma ** 2))

    # Fixed background stars must NOT move: they give the eye a reference.
    fixed = [(rng.uniform(5, size - 5), rng.uniform(5, size - 5), rng.uniform(30, 90))
             for _ in range(max(8, size // 8))]
    peak = 1500 if detector <= 4 else 140             # very bright in D1-D4, clean in D5-D6
    frames, labels, sats = [], [], []
    for i in range(n):
        t = i / (n - 1)                               # 0 -> 1 across the series
        # Target starts just off the cutout centre and moves ~2 px up (north), 0.5 px left (east).
        img = star(size / 2 - 2 - 0.5 * t, size / 2 + 4 - 2.0 * t, peak)
        for fx, fy, p in fixed:
            img += star(fx, fy, p)
        img += rng.normal(0, 3, img.shape) + 10       # sky background + noise
        img = np.minimum(img, SAT_LEVEL)              # detector clips at full well
        frames.append(img)
        sats.append(int((img >= SAT_LEVEL).sum()))    # what the API reports as saturated_pixels
        labels.append(f"Epoch {i + 1}")
    return np.array(frames), labels, sats


def measure_centroid(img, seed=None, search=8, half=5):
    """Return the (x, y) intensity-weighted centroid of the target near `seed`.

    Why: the marker must show the *measured* sub-pixel position. Pixel centres sit at
    i + 0.5 to match canvas coordinates. The search is limited around `seed` (default
    frame centre) so a brighter neighbour is never mistaken for the target.
    (Used by the demo backend; the real API supplies `centroid` itself.)
    """
    h, w = img.shape
    img = np.nan_to_num(img, nan=float(np.nanmedian(img)))   # cutouts can contain NaNs
    clean = img - np.median(img)                             # remove the sky background level
    sx, sy = seed if seed is not None else (w / 2, h / 2)
    xa, xb = int(max(sx - search, 0)), int(min(sx + search + 1, w))   # clamp search box
    ya, yb = int(max(sy - search, 0)), int(min(sy + search + 1, h))
    sub = clean[ya:yb, xa:xb] if (xb > xa and yb > ya) else clean
    iy, ix = np.unravel_index(np.argmax(sub), sub.shape)     # brightest pixel in the box
    x0, y0 = (xa + ix, ya + iy) if sub is not clean else (ix, iy)
    xa, xb = max(x0 - half, 0), min(x0 + half + 1, w)        # clamped centroid window
    ya, yb = max(y0 - half, 0), min(y0 + half + 1, h)
    win = clean[ya:yb, xa:xb]
    sigma = 1.4826 * np.median(np.abs(clean))                # robust noise (MAD)
    wts = np.where(win > 3 * sigma, win, 0.0)                # ignore noise pixels
    if wts.sum() <= 0:
        wts = np.clip(win, 0, None)                          # faint target fallback
    if wts.sum() <= 0:
        return float(x0 + 0.5), float(y0 + 0.5)
    yy, xx = np.mgrid[ya:yb, xa:xb]
    return float((xx * wts).sum() / wts.sum() + 0.5), float((yy * wts).sum() / wts.sum() + 0.5)


def frame_to_data_url(img, lo, hi):
    """Stretch a frame to 8-bit and return it as a base64 PNG data URL.

    Why: one shared (lo, hi) range keeps brightness comparable across frames; the asinh
    stretch lifts faint stars.
    """
    img = np.nan_to_num(img, nan=lo)                 # blank (NaN) pixels show as black
    norm = np.clip((img - lo) / (hi - lo), 0, 1)
    norm = np.arcsinh(10 * norm) / np.arcsinh(10)
    buf = io.BytesIO()
    Image.fromarray((norm * 255).astype(np.uint8), "L").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@functools.lru_cache(maxsize=16)
def demo_api_response(detector, fov):
    """Build the demo backend's JSON reply for one (detector, fov); cached because
    generating large fields is slow and the page may re-request the same view."""
    frames, labels, sats = make_demo_frames(detector, fov)
    lo, hi = np.nanpercentile(frames, [5, 99.8])     # shared stretch for all frames
    hi = hi if hi > lo else lo + 1.0                 # guard: flat frames
    out, prev = [], None
    for img, lab, sat in zip(frames, labels, sats):
        # First frame: search the centre; later frames: follow from the previous centroid.
        cx, cy = measure_centroid(img) if prev is None else measure_centroid(img, prev, search=4)
        prev = (cx, cy)
        out.append({"url": frame_to_data_url(img, lo, hi), "label": lab,
                    "centroid": [cx, cy], "saturated_pixels": sat})
    return json.dumps({"frames": out}).encode()


# The page. __CONFIG__ is replaced by Python (a plain string, not an f-string, so the
# many { } in CSS/JS need no escaping).
PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  /* Dark theme: astronomical images are easier to judge on a dark background. */
  body{margin:0;background:#111;color:#eee;font-family:system-ui,sans-serif;text-align:center}
  canvas{width:100%;max-width:760px;background:#000;cursor:grab;touch-action:none}
  button,select{background:#2a2a2a;color:#eee;border:1px solid #555;border-radius:6px;padding:7px 10px;margin:3px}
  button{cursor:pointer} button.on{background:#0a6;border-color:#0c8}
  label{margin:0 8px;font-size:.95em}
  #info{min-height:2.6em;font-size:1.05em}
  #note{min-height:1.4em;color:#fc6;font-size:.95em;margin:4px 10px}
  small{color:#999}
</style></head><body>
<h2>__TITLE__</h2>
<div>
  <label>Detector <select id="selDet"></select></label>
  <label>Field of view <select id="selFov"></select></label>
  <label>Mode <select id="selMode"></select></label>
</div>
<div id="note"></div>
<canvas id="cv" width="760" height="600" tabindex="0"></canvas>
<div id="info"></div>
<div>
  <button id="bPlay">Pause (space)</button>
  <button id="bBlink">Blink first/last</button>
  <button id="bTrail">Trail</button>
  <button id="bPix">Show pixels</button>
  <button id="bPrev">&larr;</button><button id="bNext">&rarr;</button>
  <button id="bIn">Zoom +</button><button id="bOut">Zoom &minus;</button>
  <button id="bReset">Reset view</button>
</div>
<small>Scroll to zoom, drag to pan, space = play/pause, arrow keys = step.
Assumes north up, east left.</small>
<script>
const C = __CONFIG__;                     // {title, api, ra, dec, scale, detectors}
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const $ = id => document.getElementById(id);

// ---- options ---------------------------------------------------------------
const MODES = [['normal', 'Normal'], ['difference', 'Difference'], ['sum', 'Sum']];
const ENABLED_MODES = ['normal'];         // add 'difference', 'sum' once the backend supports them
const FOVS = [0.02, 0.05, 0.1, 0.2, 0.5]; // presets (degrees) around the 0.1 default
const Q = {det: 5, fov: 0.1, mode: 'normal', ra: C.ra, dec: C.dec};  // selected options

function readURL(){
  // Restore options from the page URL; anything missing/invalid falls back to a default.
  const p = new URLSearchParams(location.search);
  const det = parseInt(p.get('det')), fov = parseFloat(p.get('fov'));
  Q.det = det >= 1 && det <= 6 ? det : 5;               // default detector 5 (no saturation)
  Q.fov = fov >= 0.02 && fov <= 0.5 ? fov : 0.1;        // API range 0.02-0.5 degrees
  Q.mode = ENABLED_MODES.includes(p.get('mode')) ? p.get('mode') : 'normal';
  Q.ra = p.get('ra') ?? C.ra; Q.dec = p.get('dec') ?? C.dec;
}
function writeURL(){
  // Keep the URL in sync so reload and shared links restore the same view.
  try { history.replaceState(null, '', '?' + new URLSearchParams(
    {ra: Q.ra, dec: Q.dec, det: Q.det, fov: Q.fov, mode: Q.mode})); } catch (e) {}
}
function fill(sel, items, value){
  // Fill a <select> from [value, text, disabled] triples and select `value`.
  sel.innerHTML = '';
  items.forEach(([v, t, dis]) => { const o = new Option(t, v); o.disabled = !!dis; sel.add(o); });
  sel.value = String(value);
}
function buildControls(){
  fill($('selDet'), C.detectors.map(([d, lo, hi]) => [d, `D${d}  ${lo}-${hi} \u00b5m`]), Q.det);
  const fovs = FOVS.includes(Q.fov) ? FOVS : [...FOVS, Q.fov].sort((a, b) => a - b);  // keep a custom URL value
  fill($('selFov'), fovs.map(f => [f, `${f}\u00b0` + (f === 0.1 ? ' (default)' : '')]), Q.fov);
  fill($('selMode'), MODES.map(([v, t]) => ENABLED_MODES.includes(v) ? [v, t] : [v, t + ' (coming soon)', true]), Q.mode);
}

// ---- frames (reloaded whenever an option changes) -------------------------
let D = {w: 1, h: 1, frames: []}, imgs = [], N = 0, loading = false, loadId = 0;
const notes = {mode: '', sat: ''};
function showNotes(){ $('note').textContent = [notes.mode, notes.sat].filter(Boolean).join('  '); }

function normalizeFrame(f){
  // The ONLY place that knows the API's field names; adapt here if the API differs.
  if (!f.centroid) throw new Error('API frame has no centroid');
  return {src: f.url || f.image, label: f.label || '', cx: f.centroid[0], cy: f.centroid[1],
          sat: f.saturated_pixels || 0};
}

async function loadFrames(){
  const my = ++loadId;                                  // ignore replies that arrive out of order
  loading = true; notes.sat = ''; showNotes(); $('info').textContent = 'Loading frames\u2026';
  const url = C.api + '?' + new URLSearchParams(
    {ra: Q.ra, dec: Q.dec, detector: Q.det, fov: Q.fov, mode: Q.mode});
  try {
    const r = await fetch(url);
    if (my !== loadId) return;
    if (r.status === 501 && Q.mode !== 'normal'){       // backend not ready for this mode yet
      notes.mode = MODES.find(m => m[0] === Q.mode)[1] + ' mode is coming soon; showing Normal.';
      Q.mode = 'normal'; $('selMode').value = 'normal'; writeURL();
      return loadFrames();
    }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const fr = (await r.json()).frames.map(normalizeFrame);
    if (!fr.length) throw new Error('no frames returned');
    const im = fr.map(f => { const i = new Image(); i.src = f.src; return i; });
    await Promise.all(im.map(i => i.decode()));         // wait until every image is ready
    if (my !== loadId) return;
    imgs = im; N = fr.length;
    D = {w: im[0].naturalWidth, h: im[0].naturalHeight, frames: fr};
    const k = fr.filter(f => f.sat > 0).length;         // saturation note (detectors 1-4 on bright stars)
    notes.sat = k ? `Saturated pixels in ${k} of ${N} frames (bright star). Try detector 5 or 6.` : '';
    showNotes(); S.frame = 0; S.tick = 0; loading = false; resetView(); draw();
  } catch (e) {
    if (my !== loadId) return;
    N = 0; loading = false; ctx.clearRect(0, 0, cv.width, cv.height);
    $('info').textContent = 'Could not load frames: ' + e.message;
  }
}
function onChange(){ Q.det = +$('selDet').value; Q.fov = +$('selFov').value; Q.mode = $('selMode').value;
  notes.mode = ''; writeURL(); loadFrames(); document.activeElement.blur(); }
['selDet', 'selFov', 'selMode'].forEach(id => $(id).onchange = onChange);

// ---- view/state ----------------------------------------------------------
// zoom = canvas pixels per image pixel; panX/panY = canvas position of image corner.
const S = {zoom:1, panX:0, panY:0, frame:0, playing:true, blink:false,
           trail:true, pixels:false, tick:0};

function resetView(){
  // Start zoomed in on the target (~32 image pixels across), centred on its first
  // position, so a 1-2 pixel shift already spans tens of screen pixels. Never zoom
  // out further than 'fit whole frame'.
  const fit = Math.min(cv.width / D.w, cv.height / D.h);
  S.zoom = Math.max(fit, cv.height / 32);
  S.panX = cv.width  / 2 - D.frames[0].cx * S.zoom;
  S.panY = cv.height / 2 - D.frames[0].cy * S.zoom;
}
// Image -> canvas coordinates (overlays use this so markers keep a constant screen size).
const toScreen = (x, y) => [x * S.zoom + S.panX, y * S.zoom + S.panY];

function zoomAt(k, mx, my){
  // Zoom by factor k keeping the point under (mx, my) fixed.
  const z = Math.min(Math.max(S.zoom * k, 1), 120);
  k = z / S.zoom; S.zoom = z;
  S.panX = mx - (mx - S.panX) * k;
  S.panY = my - (my - S.panY) * k;
  draw();
}

// ---- drawing ---------------------------------------------------------------
function currentIndex(){ return S.blink ? (S.tick % 2 ? N - 1 : 0) : S.frame; }  // blink = first/last

function drawCrosshair(x, y){
  // Fixed reference at the FIRST frame's centroid, with a gap so the star stays visible.
  const [sx, sy] = toScreen(x, y), g = 9, L = 26;
  ctx.strokeStyle = '#0ff'; ctx.lineWidth = 1.5; ctx.beginPath();
  ctx.moveTo(sx - L, sy); ctx.lineTo(sx - g, sy); ctx.moveTo(sx + g, sy); ctx.lineTo(sx + L, sy);
  ctx.moveTo(sx, sy - L); ctx.lineTo(sx, sy - g); ctx.moveTo(sx, sy + g); ctx.lineTo(sx, sy + L);
  ctx.stroke();
}

function drawTrail(){
  // Every frame's centroid at once, joined by a line, with an arrow head at the end.
  ctx.strokeStyle = '#fa0'; ctx.fillStyle = '#fa0'; ctx.lineWidth = 2;
  ctx.beginPath();
  D.frames.forEach((f, i) => { const [x, y] = toScreen(f.cx, f.cy); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.stroke();
  D.frames.forEach(f => { const [x, y] = toScreen(f.cx, f.cy);
    ctx.beginPath(); ctx.arc(x, y, 3, 0, 7); ctx.fill(); });
  const a = toScreen(D.frames[0].cx, D.frames[0].cy), b = toScreen(D.frames[N-1].cx, D.frames[N-1].cy);
  const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
  ctx.beginPath(); ctx.moveTo(b[0], b[1]);
  ctx.lineTo(b[0] - 14 * Math.cos(ang - .4), b[1] - 14 * Math.sin(ang - .4));
  ctx.lineTo(b[0] - 14 * Math.cos(ang + .4), b[1] - 14 * Math.sin(ang + .4));
  ctx.closePath(); ctx.fill();
}

function drawPixelGrid(){
  // 'Show pixels' also draws pixel edges once zoomed in far enough to see them.
  if (S.zoom < 8) return;
  ctx.strokeStyle = 'rgba(255,255,255,.18)'; ctx.lineWidth = 1; ctx.beginPath();
  for (let i = 0; i <= D.w; i++){ const [x] = toScreen(i, 0); ctx.moveTo(x, S.panY); ctx.lineTo(x, S.panY + D.h * S.zoom); }
  for (let j = 0; j <= D.h; j++){ const [, y] = toScreen(0, j); ctx.moveTo(S.panX, y); ctx.lineTo(S.panX + D.w * S.zoom, y); }
  ctx.stroke();
}

function drawCompass(){
  // Small N/E arrows in the corner so 'which way' is answered at a glance.
  ctx.strokeStyle = ctx.fillStyle = '#fff'; ctx.lineWidth = 2; ctx.font = '14px sans-serif';
  ctx.beginPath(); ctx.moveTo(60, 60); ctx.lineTo(60, 22); ctx.moveTo(60, 60); ctx.lineTo(22, 60); ctx.stroke();
  ctx.fillText('N', 55, 16); ctx.fillText('E', 6, 65);   // north up, east left
}

function draw(){
  if (!N || loading) return;                           // nothing to show while (re)loading
  const i = currentIndex(), f = D.frames[i], f0 = D.frames[0];
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, cv.width, cv.height);
  // Smooth scaling by default; 'show pixels' switches to hard-edged pixels.
  ctx.imageSmoothingEnabled = !S.pixels; ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(imgs[i], S.panX, S.panY, D.w * S.zoom, D.h * S.zoom);
  if (S.pixels) drawPixelGrid();
  if (S.trail) drawTrail();
  drawCrosshair(f0.cx, f0.cy);                         // fixed reference, never moves
  const [mx, my] = toScreen(f.cx, f.cy);               // marker follows this frame's centroid
  ctx.strokeStyle = '#f50'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(mx, my, 12, 0, 7); ctx.stroke();
  drawCompass();
  // Readout: shift so far and direction (north = up = -y, east = left = -x).
  const dx = f.cx - f0.cx, dy = f.cy - f0.cy, arc = Math.hypot(dx, dy) * C.scale;
  const ns = dy < 0 ? 'N' : 'S', ew = dx < 0 ? 'E' : 'W';
  const lab = S.blink ? (i ? 'LAST' : 'FIRST') : f.label;
  $('info').textContent =
    `${lab} (${i + 1}/${N})  moved ${arc.toFixed(1)}\u2033 from start: ` +
    `${Math.abs(dy * C.scale).toFixed(1)}\u2033 ${ns}, ${Math.abs(dx * C.scale).toFixed(1)}\u2033 ${ew}`;
}

// ---- animation loop -----------------------------------------------------------
setInterval(() => {
  // One timer drives both play and blink.
  if (!N || loading) return;
  S.tick++;
  if (S.playing && !S.blink) S.frame = (S.frame + 1) % N;
  if (S.playing || S.blink) draw();
}, 450);

// ---- controls ----------------------------------------------------------------------
function setOn(id, on){ $(id).classList.toggle('on', on); }
function setPlaying(p){ S.playing = p; $('bPlay').textContent = p ? 'Pause (space)' : 'Play (space)'; }
function step(d){ if (!N) return; setPlaying(false); S.blink = false; setOn('bBlink', false); S.frame = (S.frame + d + N) % N; draw(); }
function bind(id, fn){ const b = $(id); b.onclick = () => { fn(); b.blur(); }; }

bind('bPlay',  () => { S.blink = false; setOn('bBlink', false); setPlaying(!S.playing); draw(); });
bind('bBlink', () => { S.blink = !S.blink; setOn('bBlink', S.blink); draw(); });
bind('bTrail', () => { S.trail = !S.trail; setOn('bTrail', S.trail); draw(); });
bind('bPix',   () => { S.pixels = !S.pixels; setOn('bPix', S.pixels); draw(); });
bind('bPrev',  () => step(-1));
bind('bNext',  () => step(1));
bind('bIn',    () => zoomAt(1.5, cv.width / 2, cv.height / 2));
bind('bOut',   () => zoomAt(1 / 1.5, cv.width / 2, cv.height / 2));
bind('bReset', () => { if (N){ resetView(); draw(); } });

// Mouse position in canvas pixels (the canvas is scaled by CSS, so correct for it).
function pos(e){ const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]; }
cv.addEventListener('wheel', e => { e.preventDefault(); if (!N) return; const [x, y] = pos(e); zoomAt(e.deltaY < 0 ? 1.2 : 1 / 1.2, x, y); }, {passive:false});
let drag = null;                                          // drag-to-pan
cv.addEventListener('pointerdown', e => { drag = pos(e); cv.setPointerCapture(e.pointerId); cv.style.cursor = 'grabbing'; });
cv.addEventListener('pointermove', e => { if (!drag) return; const [x, y] = pos(e); S.panX += x - drag[0]; S.panY += y - drag[1]; drag = [x, y]; draw(); });
cv.addEventListener('pointerup',   () => { drag = null; cv.style.cursor = 'grab'; });
window.addEventListener('keydown', e => {                 // keyboard: space and arrows
  if (e.target.tagName === 'SELECT') return;              // let the dropdowns use their own keys
  if (e.code === 'Space'){ e.preventDefault(); S.blink = false; setOn('bBlink', false); setPlaying(!S.playing); draw(); }
  else if (e.key === 'ArrowRight'){ e.preventDefault(); step(1); }
  else if (e.key === 'ArrowLeft'){ e.preventDefault(); step(-1); }
});

// ---- start-up -------------------------------------------------------------------------
readURL(); buildControls(); writeURL();                   // restore options, show them, normalise URL
setOn('bTrail', true);
loadFrames();                                             // first load uses the restored options
</script></body></html>
"""


def page_html(api, ra, dec, title):
    """Insert the page configuration into the template and return the HTML text."""
    cfg = {"title": title, "api": api, "ra": ra, "dec": dec, "scale": PIXEL_SCALE_ARCSEC,
           "detectors": [[d, lo, hi] for d, (lo, hi) in DETECTORS.items()]}
    return PAGE.replace("__TITLE__", title).replace("__CONFIG__", json.dumps(cfg))


class DemoHandler(BaseHTTPRequestHandler):
    """Tiny demo backend: serves the page at / and mimics the API at /api/frames."""
    cfg = {}

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u, q = urlparse(self.path), parse_qs(urlparse(self.path).query)
        if u.path == "/":
            c = self.cfg
            self._send(200, "text/html; charset=utf-8",
                       page_html("/api/frames", c["ra"], c["dec"], c["title"]).encode())
        elif u.path == "/api/frames":
            try:
                det, fov = int(q["detector"][0]), float(q["fov"][0])
                assert det in DETECTORS and 0.02 <= fov <= 0.5
            except Exception:
                return self._send(400, "application/json", b'{"error":"bad detector or fov"}')
            if q.get("mode", ["normal"])[0] != "normal":   # like the real backend for now
                return self._send(501, "application/json", b'{"error":"not implemented"}')
            self._send(200, "application/json", demo_api_response(det, round(fov, 4)))
        else:
            self._send(404, "text/plain", b"not found")


def main():
    """Command line: write a page for a real API (--api) or run the demo backend."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", help="URL of the real frames API; writes a page for it")
    ap.add_argument("--out", default="spherex_viewer.html", help="output file when --api is given")
    ap.add_argument("--ra", type=float, default=BARNARD_RA, help="default RA, degrees")
    ap.add_argument("--dec", type=float, default=BARNARD_DEC, help="default Dec, degrees")
    ap.add_argument("--title", default="SPHEREx motion viewer")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    if a.api:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(page_html(a.api, a.ra, a.dec, a.title))
        print(f"Wrote {a.out}")
    else:
        DemoHandler.cfg = {"ra": a.ra, "dec": a.dec, "title": a.title}
        print(f"Demo at http://localhost:{a.port}  (Ctrl+C to stop)")
        HTTPServer(("127.0.0.1", a.port), DemoHandler).serve_forever()


if __name__ == "__main__":
    main()