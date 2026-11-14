// A basic frame player around the issue #10 and #12 panels. The player itself belongs to
// issue #5 (Anu): extend or replace it freely; the panels only need `frames` and `current`.
import { useEffect, useState } from 'react'
import { fetchFrames, type FramesQuery, type FramesResponse } from './api'
import { ContextView } from './components/ContextView'
import { FrameDetails } from './components/FrameDetails'
import { GaiaOverlay, GaiaReadout } from './components/GaiaOverlay'
import { BrightnessPanel } from './components/BrightnessPanel'
import { SearchBar, type SearchTarget } from './components/SearchBar'
import { SpectrumPanel } from './components/SpectrumPanel'
import { targetMotion, type SpectrumRequest } from './spectrum'
import './App.css'

// Barnard's Star at 2026.0 (from CLAUDE.md), used when the URL gives no position.
const DEFAULTS: FramesQuery = { ra: 269.446267, dec: 4.768222, fov: 0.1, detector: 5 }

function queryFromUrl(): FramesQuery {
  const p = new URLSearchParams(window.location.search)
  const num = (key: string, fallback: number) => {
    const raw = p.get(key)
    if (raw === null || raw.trim() === '') return fallback
    const v = Number(raw)
    return Number.isFinite(v) ? v : fallback
  }
  const query: FramesQuery = {
    ra: num('ra', DEFAULTS.ra),
    dec: num('dec', DEFAULTS.dec),
    fov: num('fov', DEFAULTS.fov),
    detector: num('detector', DEFAULTS.detector),
  }
  // Optional motion (?pmra=&pmdec=&parallax=, as /api/resolve gives it). Both pmra and pmdec
  // are needed; the backend refuses one without the other.
  const pmra = num('pmra', NaN)
  const pmdec = num('pmdec', NaN)
  if (Number.isFinite(pmra) && Number.isFinite(pmdec)) {
    const parallax = num('parallax', NaN)
    query.motion = Number.isFinite(parallax) ? { pmra, pmdec, parallax } : { pmra, pmdec }
  }
  return query
}

// The earlier single-file viewer (public/viewer.html) has features this app does not
// have yet. It names the detector `det`.
function viewerHref(q: FramesQuery) {
  return `viewer.html?${new URLSearchParams({ ra: String(q.ra), dec: String(q.dec), fov: String(q.fov), det: String(q.detector) })}`
}

type Load =
  | { state: 'loading' }
  | { state: 'error'; message: string }
  | { state: 'ready'; data: FramesResponse }

// Temporary wiring for the search box (issue #6), to be replaced by the rebuilt App.
// A name search also gives the object's motion; /api/frames needs it to follow objects
// Gaia does not list (WISE 0855), and fetchFrames in api.ts does not pass it on.
type Shown = FramesQuery & Pick<SearchTarget, 'pmra' | 'pmdec' | 'parallax'>

async function loadFrames(q: Shown, signal: AbortSignal): Promise<FramesResponse> {
  if (q.pmra == null || q.pmdec == null) return fetchFrames(q, signal)
  const motion: Record<string, string> = { pmra: String(q.pmra), pmdec: String(q.pmdec) }
  if (q.parallax != null) motion.parallax = String(q.parallax)
  const position = { ra: String(q.ra), dec: String(q.dec), fov: String(q.fov), detector: String(q.detector) }
  const r = await fetch(`/api/frames?${new URLSearchParams({ ...position, mode: 'normal', ...motion })}`, { signal })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return (await r.json()) as FramesResponse
}

export default function App() {
  const [query, setQuery] = useState<Shown>(queryFromUrl)
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [current, setCurrent] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [showGaia, setShowGaia] = useState(true)
  // Issue #11: what the spectrum panel is showing, or null when it is closed.
  const [spectrum, setSpectrum] = useState<SpectrumRequest | null>(null)
  const [showFlags, setShowFlags] = useState(false)
  // Issue #9: whose brightness over time is shown, or null when that panel is closed.
  const [brightness, setBrightness] = useState<SpectrumRequest | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    loadFrames(query, ctrl.signal)
      .then((data) => {
        setCurrent(0) // the new target may have fewer frames than the one on screen
        setLoad({ state: 'ready', data })
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoad({ state: 'error', message: e instanceof Error ? e.message : String(e) })
      })
    return () => ctrl.abort()
  }, [query])

  const n = load.state === 'ready' ? load.data.frames.length : 0
  const hasFlags = load.state === 'ready' && load.data.frames.every((f) => f.flags_image)
  useEffect(() => {
    if (!playing || n < 2) return
    const t = window.setInterval(() => setCurrent((i) => (i + 1) % n), 700)
    return () => window.clearInterval(t)
  }, [playing, n])

  return (
    <main>
      <h1>SPHEREx sky-change viewer</h1>
      <SearchBar
        onSelect={(t) => {
          setLoad({ state: 'loading' })
          const motion = { pmra: t.pmra, pmdec: t.pmdec, parallax: t.parallax }
          // The detector a target asks for (WISE 0855: 6), else the one the page opened with.
          // `motion: undefined` drops a motion that came with the page URL: it belonged to the
          // object the page opened on, not to this one.
          setQuery((q) => ({ ...q, ra: t.ra, dec: t.dec, detector: t.det ?? queryFromUrl().detector, ...motion, motion: undefined }))
        }}
      />
      <p className="where">
        RA {query.ra.toFixed(5)}°, Dec {query.dec.toFixed(5)}°, field {query.fov}°, detector D{query.detector}
      </p>

      {load.state === 'loading' && (
        <p className="status">Loading frames… The first request for a new position can take about a minute.</p>
      )}
      {load.state === 'error' && <p className="status error">Could not load frames: {load.message}</p>}
      {load.state === 'ready' && n === 0 && (
        <p className="status">{load.data.message ?? 'SPHEREx has no usable images of this position.'}</p>
      )}

      {load.state === 'ready' && n > 0 && load.data.size_px && load.data.pixel_arcsec && (
        <>
          <div className="viewer">
            <div className="stage">
              <img src={load.data.frames[current].image} alt={`SPHEREx frame ${current + 1} of ${n}`} />
              {showFlags && load.data.frames[current].flags_image && (
                <img className="flags" src={load.data.frames[current].flags_image} alt="" />
              )}
              {showGaia && (
                <GaiaOverlay
                  frames={load.data.frames}
                  current={current}
                  sizePx={load.data.size_px}
                  pixelArcsec={load.data.pixel_arcsec}
                  target={load.data.target}
                />
              )}
              <span className="compass" aria-hidden="true">
                N ↑ · E ←
              </span>
            </div>

            <div className="controls">
              <button type="button" onClick={() => setPlaying(!playing)}>
                {playing ? 'Pause' : 'Play'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setPlaying(false)
                  setCurrent((current - 1 + n) % n)
                }}
              >
                ← Prev
              </button>
              <input
                type="range"
                min={0}
                max={n - 1}
                value={current}
                aria-label="Frame"
                onChange={(e) => {
                  setPlaying(false)
                  setCurrent(Number(e.target.value))
                }}
              />
              <button
                type="button"
                onClick={() => {
                  setPlaying(false)
                  setCurrent((current + 1) % n)
                }}
              >
                Next →
              </button>
              <span>
                Frame {current + 1} of {n} · {load.data.frames[current].date_mean}
              </span>
              <label>
                <input type="checkbox" checked={showGaia} onChange={(e) => setShowGaia(e.target.checked)} /> Gaia overlay
              </label>
              <button
                type="button"
                onClick={() =>
                  setSpectrum({ kind: 'target', ra: load.data.ra, dec: load.data.dec, motion: targetMotion(load.data.target) })
                }
              >
                Spectrum of the target
              </button>
              <button
                type="button"
                onClick={() =>
                  setBrightness({ kind: 'target', ra: load.data.ra, dec: load.data.dec, motion: targetMotion(load.data.target) })
                }
              >
                Brightness over time
              </button>
              <label>
                <input
                  type="checkbox"
                  checked={showFlags}
                  disabled={!hasFlags}
                  onChange={(e) => setShowFlags(e.target.checked)}
                />{' '}
                Flags
              </label>
            </div>

            {showFlags && (
              <p className="readout">
                <span className="key nodata">■</span> no data · <span className="key saturated">■</span> saturated (too
                bright to measure){' '}
                {load.data.frames[current].saturated_pixels === 0 && '· no saturated pixels in this frame'}
              </p>
            )}
            {!hasFlags && (
              <p className="hint">
                Flags are not available for these frames. Restart the backend if it is older than the flags
                change.
              </p>
            )}

            {showGaia && (
              <GaiaReadout
                frames={load.data.frames}
                current={current}
                target={load.data.target}
                gaiaError={load.data.gaia_error}
              />
            )}
          </div>

          <div className="side">
            <FrameDetails frame={load.data.frames[current]} detector={load.data.detector} />
            <ContextView ra={query.ra} dec={query.dec} fov={query.fov} />
          </div>
          {spectrum && <SpectrumPanel request={spectrum} onClose={() => setSpectrum(null)} />}
          {brightness && <BrightnessPanel request={brightness} onClose={() => setBrightness(null)} />}
        </>
      )}

      <footer>
        <p>
          <a href={viewerHref(query)}>Open this view in the detailed viewer</a>: zoom, blink, difference and sum views,
          and the spectrum of any spot you click.
        </p>
        Images: NASA/JPL-Caltech SPHEREx, served by NASA/IPAC Infrared Science Archive (IRSA). Star positions and
        motions: ESA Gaia DR3.
      </footer>
    </main>
  )
}
