/**
 * SPHEREx motion viewer (React): display features that make a 1-2 pixel motion obvious.
 *
 * Props of <MotionViewer>:
 *   frames          [{ src, label, centroid: [x, y] }]  src = image URL or data URL (2 arcsec/pixel);
 *                   centroid = measured position in image pixels (x right, y down)
 *   title           name shown in the plain-language headline (e.g. "Barnard's Star")
 *   arcsecPerPixel  pixel scale, default 2
 *   centroidOffset  added to centroids to reach the pixel's centre on screen. 0.5 if the
 *                   backend counts the CENTRE of the first pixel as 0 (numpy style); use 0 if
 *                   it counts the pixel's top-left corner as 0.
 *
 * The default export <App> adds the controls (detector, field of view, mode), keeps them in the
 * page URL (?ra=&dec=&fov=&det=&mode=), reloads the frames from the API when they change, and
 * falls back to synthetic demo frames so it can be tried without a backend.
 * Assumes north is up and east is left in the frames.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API = "/api/frames"; // GET ?ra=&dec=&fov=&detector=&mode=  ->  {frames:[{url,label,centroid,...}]}
const CANVAS_W = 760;
const CANVAS_H = 600;
const FRAME_MS = 450; // time per frame when playing, and per flip when blinking
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

// ---------------------------------------------------------------------------
// MotionViewer: the display. Everything the issue asks for lives in here.
// ---------------------------------------------------------------------------
export function MotionViewer({ frames, title = "This object", arcsecPerPixel = 2, centroidOffset = 0.5 }) {
  const canvasRef = useRef(null);
  const dragRef = useRef(null); // last pointer position while dragging (for pan)
  const [imgs, setImgs] = useState([]); // decoded images, one per frame
  const [playing, setPlaying] = useState(true);
  const [blink, setBlink] = useState(false); // first-vs-last flip
  const [trail, setTrail] = useState(true); // all centroids joined by a line
  const [pixels, setPixels] = useState(false); // hard pixels instead of smooth scaling
  const [frame, setFrame] = useState(0);
  const [tick, setTick] = useState(0); // counts timer beats; drives the blink
  const [view, setView] = useState({ zoom: 1, x: 0, y: 0 }); // zoom = canvas px per image px
  const N = imgs.length;

  // Centroids converted to image-pixel coordinates where pixel i spans [i, i+1].
  const cents = useMemo(
    () => frames.map((f) => [f.centroid[0] + centroidOffset, f.centroid[1] + centroidOffset]),
    [frames, centroidOffset]
  );

  // Which frame is on screen: blink alternates first/last, otherwise the selected frame.
  const idx = blink ? (tick % 2 ? N - 1 : 0) : frame;

  // Plain-language summary of the motion (first -> last), the thing a newcomer reads first.
  const motion = useMemo(() => {
    if (cents.length < 2) return null;
    const dx = cents[cents.length - 1][0] - cents[0][0];
    const dy = cents[cents.length - 1][1] - cents[0][1];
    const arc = Math.hypot(dx, dy) * arcsecPerPixel;
    const bearing = ((Math.atan2(-dx, -dy) * 180) / Math.PI + 360) % 360; // 0 = north, 90 = east
    const names = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];
    return { arc, bearing, dir: names[Math.round(bearing / 45) % 8], still: Math.hypot(dx, dy) < 0.3 };
  }, [cents, arcsecPerPixel]);

  // Decode every image once so drawing is instant. Restart if the frames change.
  useEffect(() => {
    let dead = false;
    Promise.all(
      frames.map((f) => {
        const im = new Image();
        im.src = f.src;
        return im.decode().then(() => im);
      })
    )
      .then((list) => {
        if (!dead) {
          setImgs(list);
          setFrame(0);
        }
      })
      .catch(() => {});
    return () => {
      dead = true;
    };
  }, [frames]);

  // Start zoomed in on the target (about 32 image pixels across), centred on its first
  // position, so a 1-2 pixel shift already spans tens of screen pixels.
  const resetView = useCallback(() => {
    if (!imgs.length) return;
    const fit = Math.min(CANVAS_W / imgs[0].naturalWidth, CANVAS_H / imgs[0].naturalHeight);
    const zoom = Math.max(fit, CANVAS_H / 32);
    setView({ zoom, x: CANVAS_W / 2 - cents[0][0] * zoom, y: CANVAS_H / 2 - cents[0][1] * zoom });
  }, [imgs, cents]);
  useEffect(resetView, [resetView]);

  // One timer drives both play and blink.
  useEffect(() => {
    if (N < 2) return undefined;
    const id = setInterval(() => {
      setTick((t) => t + 1);
      if (playing && !blink) setFrame((f) => (f + 1) % N);
    }, FRAME_MS);
    return () => clearInterval(id);
  }, [N, playing, blink]);

  // Zoom by factor k keeping the point under (mx, my) fixed.
  const zoomAt = useCallback((k, mx, my) => {
    setView((v) => {
      const zoom = clamp(v.zoom * k, 1, 120);
      const kk = zoom / v.zoom;
      return { zoom, x: mx - (mx - v.x) * kk, y: my - (my - v.y) * kk };
    });
  }, []);

  const step = useCallback(
    (d) => {
      if (!N) return;
      setPlaying(false);
      setBlink(false);
      setFrame((f) => (f + d + N) % N);
    },
    [N]
  );
  const togglePlay = useCallback(() => {
    setBlink(false);
    setPlaying((p) => !p);
  }, []);

  // Mouse wheel zoom. Added natively because React's onWheel is passive and cannot stop
  // the page from scrolling.
  useEffect(() => {
    const cv = canvasRef.current;
    const onWheel = (e) => {
      e.preventDefault();
      const r = cv.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? 1.2 : 1 / 1.2, ((e.clientX - r.left) * CANVAS_W) / r.width, ((e.clientY - r.top) * CANVAS_H) / r.height);
    };
    cv.addEventListener("wheel", onWheel, { passive: false });
    return () => cv.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  // Keyboard: space = play/pause, arrows = step (ignored while typing in a form field).
  useEffect(() => {
    const onKey = (e) => {
      if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        step(1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        step(-1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, step]);

  // Drag to pan. Pointer position is converted to canvas pixels (CSS may scale the canvas).
  const pointer = (e) => {
    const r = canvasRef.current.getBoundingClientRect();
    return [((e.clientX - r.left) * CANVAS_W) / r.width, ((e.clientY - r.top) * CANVAS_H) / r.height];
  };
  const onPointerDown = (e) => {
    dragRef.current = pointer(e);
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e) => {
    if (!dragRef.current) return;
    const [x, y] = pointer(e);
    const [px, py] = dragRef.current;
    dragRef.current = [x, y];
    setView((v) => ({ ...v, x: v.x + x - px, y: v.y + y - py }));
  };
  const onPointerUp = () => {
    dragRef.current = null;
  };

  // Draw: image, optional pixel grid, trail, fixed crosshair, marker, compass.
  useEffect(() => {
    if (!N) return;
    const ctx = canvasRef.current.getContext("2d");
    const toScreen = (x, y) => [x * view.zoom + view.x, y * view.zoom + view.y]; // overlays keep a constant size
    const w = imgs[0].naturalWidth;
    const h = imgs[0].naturalHeight;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

    // Smooth scaling by default; "show pixels" switches to hard-edged pixels.
    ctx.imageSmoothingEnabled = !pixels;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(imgs[idx], view.x, view.y, w * view.zoom, h * view.zoom);

    if (pixels && view.zoom >= 8) {
      // Pixel edges, once zoomed in far enough to see them.
      ctx.strokeStyle = "rgba(255,255,255,.18)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i <= w; i++) {
        const [x] = toScreen(i, 0);
        ctx.moveTo(x, view.y);
        ctx.lineTo(x, view.y + h * view.zoom);
      }
      for (let j = 0; j <= h; j++) {
        const [, y] = toScreen(0, j);
        ctx.moveTo(view.x, y);
        ctx.lineTo(view.x + w * view.zoom, y);
      }
      ctx.stroke();
    }

    if (trail && cents.length > 1) {
      // Every frame's centroid at once, joined by a line, with an arrow head at the end.
      ctx.strokeStyle = ctx.fillStyle = "#ffaa00";
      ctx.lineWidth = 2;
      ctx.beginPath();
      cents.forEach(([x, y], i) => {
        const [sx, sy] = toScreen(x, y);
        if (i) ctx.lineTo(sx, sy);
        else ctx.moveTo(sx, sy);
      });
      ctx.stroke();
      cents.forEach(([x, y]) => {
        const [sx, sy] = toScreen(x, y);
        ctx.beginPath();
        ctx.arc(sx, sy, 3, 0, 7);
        ctx.fill();
      });
      const a = toScreen(...cents[0]);
      const b = toScreen(...cents[cents.length - 1]);
      const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
      ctx.beginPath();
      ctx.moveTo(b[0], b[1]);
      ctx.lineTo(b[0] - 14 * Math.cos(ang - 0.4), b[1] - 14 * Math.sin(ang - 0.4));
      ctx.lineTo(b[0] - 14 * Math.cos(ang + 0.4), b[1] - 14 * Math.sin(ang + 0.4));
      ctx.closePath();
      ctx.fill();
    }

    // Fixed crosshair at the FIRST frame's centroid (gap in the middle keeps the star visible).
    const [cx, cy] = toScreen(...cents[0]);
    ctx.strokeStyle = "#00ffff";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx - 26, cy); ctx.lineTo(cx - 9, cy);
    ctx.moveTo(cx + 9, cy); ctx.lineTo(cx + 26, cy);
    ctx.moveTo(cx, cy - 26); ctx.lineTo(cx, cy - 9);
    ctx.moveTo(cx, cy + 9); ctx.lineTo(cx, cy + 26);
    ctx.stroke();

    // Marker ring on THIS frame's measured centroid.
    const [mx, my] = toScreen(...cents[idx]);
    ctx.strokeStyle = "#ff5500";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(mx, my, 12, 0, 7);
    ctx.stroke();

    // Compass: north up, east left.
    ctx.strokeStyle = ctx.fillStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.font = "14px system-ui, sans-serif";
    ctx.beginPath();
    ctx.moveTo(60, 60); ctx.lineTo(60, 22);
    ctx.moveTo(60, 60); ctx.lineTo(22, 60);
    ctx.stroke();
    ctx.fillText("N", 55, 16);
    ctx.fillText("E", 6, 65);
  }, [imgs, idx, view, trail, pixels, cents, N]);

  // Readout for the frame on screen: how far it has moved since the first frame.
  const f0 = cents[0];
  const cur = cents[idx] || f0;
  const dx = cur && f0 ? cur[0] - f0[0] : 0;
  const dy = cur && f0 ? cur[1] - f0[1] : 0;
  const label = blink ? (idx ? "LAST frame" : "FIRST frame") : frames[idx]?.label;
  const s = arcsecPerPixel;

  const btn = (on) => ({ ...styles.btn, ...(on ? styles.btnOn : null) });
  return (
    <div style={styles.wrap}>
      {/* Headline: answers "does it move, and which way?" in plain words. */}
      <p style={styles.headline} aria-live="polite">
        {motion &&
          (motion.still ? (
            <>{title} shows no measurable motion here.</>
          ) : (
            <>
              <span style={{ display: "inline-block", transform: `rotate(${-motion.bearing}deg)` }}>↑</span>{" "}
              {title} moves {motion.arc.toFixed(1)}″ toward the {motion.dir} between the first and last frame.
            </>
          ))}
      </p>
      <canvas
        ref={canvasRef}
        width={CANVAS_W}
        height={CANVAS_H}
        style={styles.canvas}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        aria-label="Sky images over time with markers showing the object's measured position"
      />
      <div style={styles.info}>
        {N ? `${label} (${idx + 1}/${N}) — moved ${(Math.hypot(dx, dy) * s).toFixed(1)}″ from start: ${Math.abs(dy * s).toFixed(1)}″ ${dy < 0 ? "N" : "S"}, ${Math.abs(dx * s).toFixed(1)}″ ${dx < 0 ? "E" : "W"}` : "Loading frames…"}
      </div>
      <div>
        <button style={btn(false)} onClick={togglePlay}>{playing && !blink ? "Pause (space)" : "Play (space)"}</button>
        <button style={btn(blink)} onClick={() => setBlink((b) => !b)}>Blink first/last</button>
        <button style={btn(trail)} onClick={() => setTrail((t) => !t)}>Trail</button>
        <button style={btn(pixels)} onClick={() => setPixels((p) => !p)}>Show pixels</button>
        <button style={btn(false)} onClick={() => step(-1)} aria-label="Previous frame">←</button>
        <button style={btn(false)} onClick={() => step(1)} aria-label="Next frame">→</button>
        <button style={btn(false)} onClick={() => zoomAt(1.5, CANVAS_W / 2, CANVAS_H / 2)}>Zoom +</button>
        <button style={btn(false)} onClick={() => zoomAt(1 / 1.5, CANVAS_W / 2, CANVAS_H / 2)}>Zoom −</button>
        <button style={btn(false)} onClick={resetView}>Reset view</button>
      </div>
      <small style={styles.hint}>
        Cyan cross = where it started. Orange ring = where it is in this frame. Orange line = its path.
        Scroll to zoom, drag to pan, space = play/pause, arrow keys = step. North is up, east is left.
      </small>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Data: load frames from the API, or fall back to synthetic demo frames.
// ---------------------------------------------------------------------------

// The only place that knows the API's field names; adapt here if the API differs.
function normalizeFrame(f, i) {
  if (!f.centroid) throw new Error("API frame has no centroid");
  return { src: f.url || f.image, label: f.label || `Epoch ${i + 1}`, centroid: f.centroid, sat: f.saturated_pixels || 0 };
}

// Synthetic field: one star drifting ~2 px north-north-east over 8 frames, plus fixed stars.
// Centroids are the true positions (index convention: pixel centre = integer).
function makeDemoFrames(det = 5, n = 8, size = 64) {
  const fixedStars = [[12, 15, 70], [50, 10, 50], [8, 48, 90], [55, 52, 60], [40, 28, 45], [20, 38, 35]];
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647); // repeatable noise
  const out = [];
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    const sx = 30 - 0.5 * t; // moves 0.5 px east (left) ...
    const sy = 36 - 2.0 * t; // ... and 2 px north (up)
    const cv = document.createElement("canvas");
    cv.width = cv.height = size;
    const ctx = cv.getContext("2d");
    const im = ctx.createImageData(size, size);
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        let v = 10 + (rand() - 0.5) * 8;
        const g = (x0, y0, p) => p * Math.exp(-((x - x0) ** 2 + (y - y0) ** 2) / (2 * 1.4 * 1.4));
        v += g(sx, sy, 140);
        for (const [fx, fy, p] of fixedStars) v += g(fx, fy, p);
        const norm = Math.asinh(10 * Math.min(Math.max((v - 8) / 150, 0), 1)) / Math.asinh(10);
        const o = (y * size + x) * 4;
        im.data[o] = im.data[o + 1] = im.data[o + 2] = norm * 255;
        im.data[o + 3] = 255;
      }
    }
    ctx.putImageData(im, 0, 0);
    out.push({ src: cv.toDataURL("image/png"), label: `Epoch ${i + 1}`, centroid: [sx, sy], sat: det <= 4 ? 16 : 0 }); // demo: D1-D4 pretend to saturate
  }
  return out;
}

// ---------------------------------------------------------------------------
// Options: detector, field of view, mode. They live in the page URL so a reload or a
// shared link restores them.
// ---------------------------------------------------------------------------
const DETECTORS = [[1, 0.75, 1.12], [2, 1.1, 1.65], [3, 1.63, 2.43], [4, 2.4, 3.85], [5, 3.81, 4.43], [6, 4.41, 5.01]]; // microns
const FOVS = [0.02, 0.05, 0.1, 0.2, 0.5]; // presets in degrees; the API accepts 0.02-0.5
const MODES = [["normal", "Normal"], ["difference", "Difference"], ["sum", "Sum"]];
const ENABLED_MODES = ["normal"]; // add "difference", "sum" once the backend supports them

// Read options from the URL; anything missing or invalid falls back to the default.
function readOptions() {
  const p = new URLSearchParams(window.location.search);
  const det = parseInt(p.get("det"), 10);
  const fov = parseFloat(p.get("fov"));
  return {
    ra: p.get("ra") ?? "269.446267", // default target: Barnard's Star
    dec: p.get("dec") ?? "4.768222",
    det: det >= 1 && det <= 6 ? det : 5, // default detector 5 (no saturation)
    fov: fov >= 0.02 && fov <= 0.5 ? fov : 0.1,
    mode: ENABLED_MODES.includes(p.get("mode")) ? p.get("mode") : "normal",
  };
}
// Keep the URL in sync with the options.
function writeOptions(o) {
  try {
    window.history.replaceState(null, "", `?${new URLSearchParams({ ra: o.ra, dec: o.dec, det: o.det, fov: o.fov, mode: o.mode })}`);
  } catch (e) {
    /* some sandboxes block history changes; the view still works */
  }
}

export default function App() {
  const [opts, setOpts] = useState(readOptions);
  const [frames, setFrames] = useState(null);
  const [version, setVersion] = useState(0); // new frames -> fresh viewer (resets zoom, frame, etc.)
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState(""); // data problems (demo fallback)
  const [modeNote, setModeNote] = useState(""); // "coming soon" message

  // Reload the frames whenever an option changes (also runs once at start-up).
  useEffect(() => {
    writeOptions(opts);
    setLoading(true);
    setNote("");
    let dead = false; // ignore replies that arrive after a newer choice
    const q = new URLSearchParams({ ra: opts.ra, dec: opts.dec, fov: opts.fov, detector: opts.det, mode: opts.mode });
    fetch(`${API}?${q}`)
      .then((r) => {
        if (dead) return null;
        if (r.status === 501 && opts.mode !== "normal") {
          // Backend not ready for this mode: say so and go back to Normal.
          setModeNote(`${MODES.find((m) => m[0] === opts.mode)[1]} mode is coming soon; showing Normal.`);
          setOpts((o) => ({ ...o, mode: "normal" }));
          return null;
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j) => {
        if (!j || dead) return;
        setFrames(j.frames.map(normalizeFrame));
        setVersion((v) => v + 1);
        setLoading(false);
      })
      .catch((e) => {
        if (dead) return;
        setNote(`Showing demo data (could not load frames: ${e.message}).`);
        setFrames(makeDemoFrames(opts.det));
        setVersion((v) => v + 1);
        setLoading(false);
      });
    return () => {
      dead = true;
    };
  }, [opts]);

  // A control changed: store the new value (the effect above reloads the frames).
  const change = (key) => (e) => {
    setModeNote("");
    const value = key === "mode" ? e.target.value : Number(e.target.value);
    setOpts((o) => ({ ...o, [key]: value }));
    e.target.blur(); // so space and arrow keys go back to the viewer
  };

  const fovs = FOVS.includes(opts.fov) ? FOVS : [...FOVS, opts.fov].sort((a, b) => a - b); // keep a custom value from the URL
  const saturated = frames ? frames.filter((f) => f.sat > 0).length : 0;
  const notes = [
    modeNote,
    saturated ? `Saturated pixels in ${saturated} of ${frames.length} frames (bright star). Try detector 5 or 6.` : "",
    note,
    loading && frames ? "Loading new frames…" : "",
  ].filter(Boolean);

  return (
    <div style={styles.page}>
      <h2 style={{ margin: "12px 0 4px" }}>SPHEREx motion viewer</h2>
      <div style={styles.bar}>
        <label style={styles.label}>
          Detector
          <select style={styles.sel} value={opts.det} onChange={change("det")}>
            {DETECTORS.map(([d, lo, hi]) => (
              <option key={d} value={d}>{`D${d}  ${lo}-${hi} µm`}</option>
            ))}
          </select>
        </label>
        <label style={styles.label}>
          Field of view
          <select style={styles.sel} value={opts.fov} onChange={change("fov")}>
            {fovs.map((f) => (
              <option key={f} value={f}>{`${f}°${f === 0.1 ? " (default)" : ""}`}</option>
            ))}
          </select>
        </label>
        <label style={styles.label}>
          Mode
          <select style={styles.sel} value={opts.mode} onChange={change("mode")}>
            {MODES.map(([v, t]) => (
              <option key={v} value={v} disabled={!ENABLED_MODES.includes(v)}>
                {ENABLED_MODES.includes(v) ? t : `${t} (coming soon)`}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div style={styles.note}>{notes.join("  ")}</div>
      {frames ? <MotionViewer key={version} frames={frames} title="Barnard's Star" /> : <p>Loading frames…</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles: plain dark theme (astronomical images read best on dark).
// ---------------------------------------------------------------------------
const styles = {
  page: { background: "#111", color: "#eee", minHeight: "100vh", textAlign: "center", fontFamily: "system-ui, sans-serif" },
  wrap: { maxWidth: 780, margin: "0 auto", padding: "0 8px" },
  headline: { fontSize: "1.25em", margin: "8px 0", minHeight: "1.5em" },
  canvas: { width: "100%", background: "#000", cursor: "grab", touchAction: "none", display: "block" },
  info: { minHeight: "2.6em", fontSize: "1.05em", marginTop: 6 },
  btn: { background: "#2a2a2a", color: "#eee", border: "1px solid #555", borderRadius: 6, padding: "7px 12px", margin: 3, cursor: "pointer" },
  btnOn: { background: "#0a6", borderColor: "#0c8" },
  hint: { color: "#999", display: "block", margin: "6px 0 16px" },
  note: { color: "#fc6", margin: "4px 10px", minHeight: "1.4em", fontSize: ".95em" },
  bar: { margin: "6px 0" },
  label: { margin: "0 8px", fontSize: ".95em" },
  sel: { background: "#2a2a2a", color: "#eee", border: "1px solid #555", borderRadius: 6, padding: "7px 10px", margin: "0 0 0 6px" },
};