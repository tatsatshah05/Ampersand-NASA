// The page: which patch of sky to show and how (kept in the page address), the frames
// for it, and the player around them. Issues #5 (player), #7 (selectors) and #8 (motion
// markers). The Gaia overlay (#10), frame details (#12) and spectrum (#11) are
// components of their own that only need the frames and the frame on screen.
import { useCallback, useEffect, useRef, useState } from 'react'
import { addressOf, DEFAULT_SELECTION, readAddress, toFramesQuery, withTarget, writeAddress, type SearchTarget, type Selection } from './address'
import { framesUrl, NATIVE_PIXEL_ARCSEC } from './api'
import { FrameDetails } from './components/FrameDetails'
import { GaiaOverlay, GaiaReadout } from './components/GaiaOverlay'
import { ApertureMark, MotionLayer, MotionLegend } from './components/MotionLayer'
import { PlayerControls } from './components/PlayerControls'
import { Selectors } from './components/Selectors'
import { SpectrumPanel } from './components/SpectrumPanel'
import { Stage } from './components/Stage'
import { LoadingCard, StatusCard } from './components/StatusCard'
import { keyBelongsToControl, releaseFocusAfterPointer } from './focus'
import { measuredPath, overallShift, SMALL_SHIFT_ARCSEC, startCentroid, toPicture } from './motion'
import { skyToPixel, type Grid } from './projection'
import { targetMotion, type SpectrumRequest } from './spectrum'
import { useFrames } from './useFrames'
import { usePlayer } from './usePlayer'
import { failuresSentence, frameLabel, frameTick, modeSentence, motionSentence, saturationSentence } from './wording'
import { startBox, type Point, type ZoomBox } from './zoom'
import './App.css'

/** The circle /api/spectrum adds up: 2.5 SPHEREx pixels in radius (backend/photometry.py). */
const SPECTRUM_APERTURE_ARCSEC = 2.5 * NATIVE_PIXEL_ARCSEC

export default function App() {
  // What the address asks for, and what in it could not be used.
  const [fromAddress] = useState(() => readAddress(window.location.search))
  const [selection, setSelection] = useState(fromAddress.selection)
  const [notes, setNotes] = useState(fromAddress.notes)
  const [attempt, setAttempt] = useState(0)
  const [showMotion, setShowMotion] = useState(true)
  const [showGaia, setShowGaia] = useState(true)
  const [showPixels, setShowPixels] = useState(false)
  // Where the visitor has zoomed and panned to, and on which patch of sky. Null until they do.
  const [zoomed, setZoomed] = useState<{ sky: string; box: ZoomBox } | null>(null)
  // Issue #11: what the spectrum panel is showing, or null when it is closed.
  const [spectrum, setSpectrum] = useState<SpectrumRequest | null>(null)

  const url = framesUrl(toFramesQuery(selection))
  const load = useFrames(url, attempt)
  const data = load.state === 'ready' ? load.data : null
  const player = usePlayer(data?.key ?? '', data?.frames.length ?? 0)
  const frame = data?.frames[player.current] ?? null

  // ---- the page address -------------------------------------------------------------------

  const latest = useRef(selection)
  useEffect(() => {
    latest.current = selection
  })

  /** Show a selection: keep it, put it in the address, and let the frames reload. */
  const show = useCallback((next: Selection, how: 'push' | 'replace') => {
    const was = latest.current
    // An open spectrum belongs to the target it was asked for: its place and its motion.
    const sameTarget =
      next.ra === was.ra && next.dec === was.dec && next.pmra === was.pmra && next.pmdec === was.pmdec && next.parallax === was.parallax
    if (!sameTarget) setSpectrum(null)
    setSelection(next)
    setNotes([])
    writeAddress(next, how)
  }, [])

  /**
   * Show a new target. This is the one function the search box needs: give it a
   * position and, when the search knows them, the object's name, its motion (pmra,
   * pmdec, parallax, as /api/resolve returns them) and a detector worth starting with.
   * The field of view and the mode stay as they are. The address gets a new history
   * entry, so the browser's Back button returns to the previous target.
   */
  const applyTarget = useCallback(
    (target: SearchTarget) => {
      const next = withTarget(latest.current, target)
      if (next) show(next, 'push')
      else setNotes(['That position could not be used: a declination has to be between -90 and 90 degrees.'])
    },
    [show],
  )

  // Tidy the address once (defaults filled in, `detector` renamed to `det`), and follow
  // the browser's Back and Forward buttons.
  useEffect(() => {
    writeAddress(fromAddress.selection, 'replace')
    const onPop = () => {
      const read = readAddress(window.location.search)
      setSpectrum(null)
      setSelection(read.selection)
      setNotes(read.notes)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [fromAddress])

  // The browser tab, and so the entries under the Back button, say which target this is.
  const whereInWords = selection.name ?? `RA ${selection.ra.toFixed(4)}°, Dec ${selection.dec.toFixed(4)}°`
  useEffect(() => {
    document.title = `${whereInWords}: SPHEREx sky-change viewer`
  }, [whereInWords])

  // ---- keyboard: the space bar plays and pauses, the arrow keys step ---------------------

  const { togglePlay, step } = player
  const severalFrames = (data?.frames.length ?? 0) > 1
  useEffect(() => {
    if (!severalFrames) return
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || keyBelongsToControl(e)) return
      if (e.key === ' ') togglePlay()
      else if (e.key === 'ArrowRight') step(1)
      else if (e.key === 'ArrowLeft') step(-1)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [severalFrames, togglePlay, step])

  // ---- what is drawn over the picture ------------------------------------------------------

  const grid: Grid | null = data && { ra: data.ra, dec: data.dec, sizePx: data.size_px, pixelArcsec: data.pixel_arcsec }
  const start = data ? startCentroid(data) : null
  const path = data ? measuredPath(data) : []
  const overall = data ? overallShift(data) : null
  // An arrowhead says "it went this way", so it is drawn only for a shift large enough to be real.
  const arrow = overall !== null && overall.total >= SMALL_SHIFT_ARCSEC

  // The view starts on the target (on the whole picture if nothing was measured) and
  // goes back to that when the patch of sky changes. A change of detector or mode keeps
  // the visitor's own zoom, so the same spot can be compared.
  const sky = data ? `${data.ra},${data.dec},${data.size_px}` : ''
  const home = data ? startBox(data.size_px, start ? toPicture(start) : null) : null
  const box = home && (zoomed?.sky === sky ? zoomed.box : home)
  const changeBox = (change: (box: ZoomBox) => ZoomBox) => {
    if (home) setZoomed((was) => ({ sky, box: change(was?.sky === sky ? was.box : home) }))
  }

  // In a difference view against the first visit, that visit is not among the frames.
  // The Gaia overlay measures every frame against the first one it is given, so it gets
  // the subtracted visit's details in front (it never looks at the picture).
  const gaiaFrames = data?.reference_frame ? [{ ...data.reference_frame, image: '' }, ...data.frames] : (data?.frames ?? [])
  const gaiaCurrent = data?.reference_frame ? player.current + 1 : player.current

  // Where the open spectrum is measured: the target's expected place in this frame (the
  // centre of the picture if no motion is known), or the spot that was clicked.
  let aperture: Point | null = null
  if (spectrum && grid && frame) {
    if (spectrum.kind === 'spot') aperture = skyToPixel(spectrum.ra, spectrum.dec, grid)
    else aperture = frame.predicted ? toPicture(frame.predicted) : { x: grid.sizePx / 2, y: grid.sizePx / 2 }
  }

  const givenMotion = selection.pmra !== null && selection.pmdec !== null ? Math.hypot(selection.pmra, selection.pmdec) / 1000 : null
  const motionKnown = givenMotion !== null || (data?.target?.pmra != null && data.target.pmdec != null)
  const saturation = data && saturationSentence(data)
  const failures = data && failuresSentence(data)
  const toggle = (on: boolean, set: (on: boolean) => void, text: string, title: string) => (
    <button
      type="button"
      className="toggle"
      aria-pressed={on}
      title={title}
      onClick={(e) => {
        set(!on)
        releaseFocusAfterPointer(e.currentTarget)
      }}
    >
      {text}
    </button>
  )

  return (
    <main>
      <header>
        <h1>SPHEREx sky-change viewer</h1>
        <p className="tagline">
          Images of one patch of sky from NASA's SPHEREx space telescope, played like a short film, so that anything
          that moved or changed stands out.
        </p>

        {/* ==== THE SEARCH BOX GOES HERE ====================================================
            frontend/src/components/SearchBar.tsx (built separately) belongs inside this div.
            Hand it applyTarget, which takes a SearchTarget (ra, dec and, when known, name,
            pmra, pmdec, parallax, det; see address.ts):
                <SearchBar onSelect={applyTarget} />
            The div takes no room while it is empty.
            ================================================================================== */}
        <div className="search-slot"></div>

        <p className="where">
          {selection.name && <strong>{selection.name}: </strong>}
          <abbr title="right ascension">RA</abbr> {selection.ra.toFixed(5)}°, <abbr title="declination">Dec</abbr>{' '}
          {selection.dec >= 0 ? '+' : '-'}
          {Math.abs(selection.dec).toFixed(5)}°
          {givenMotion !== null && `, followed with its known motion of ${givenMotion.toFixed(2)} arcseconds a year`}
        </p>
        {notes.map((note) => (
          <p key={note} className="notice" role="status">
            {note}
          </p>
        ))}

        <Selectors selection={selection} motionKnown={motionKnown} onChange={(change) => show({ ...selection, ...change }, 'replace')} />
        {data && <p className="mode-note">{modeSentence(data)}</p>}
        {saturation && <p className="notice">{saturation}</p>}
        {failures && (
          <p className="notice">
            {failures}{' '}
            <button type="button" onClick={() => setAttempt(attempt + 1)}>
              Try again
            </button>
          </p>
        )}
      </header>

      <div className="viewer">
        {load.state === 'loading' && <LoadingCard key={url} />}
        {load.state === 'error' && (
          <StatusCard title="The frames could not be loaded" tone="error">
            <p>{load.message}</p>
            <button type="button" onClick={() => setAttempt(attempt + 1)}>
              Try again
            </button>
          </StatusCard>
        )}
        {load.state === 'empty' && (
          <StatusCard title="No frames to show here">
            <p>{load.message}</p>
            <p>Another detector or another mode may have some.</p>
            <button
              type="button"
              onClick={() => applyTarget({ ra: DEFAULT_SELECTION.ra, dec: DEFAULT_SELECTION.dec, name: DEFAULT_SELECTION.name ?? undefined, det: DEFAULT_SELECTION.det })}
            >
              Show the example, Barnard's Star
            </button>
          </StatusCard>
        )}
        {load.state === 'ready' && grid && frame && box && (
          <>
            <Stage
              grid={grid}
              images={load.data.frames.map((f) => ({ key: f.image, src: f.image }))}
              current={player.current}
              alt={`${frameLabel(frame, load.data)}. ${motionSentence(frame, load.data)}`}
              box={box}
              onBoxChange={changeBox}
              onReset={() => setZoomed(null)}
              showPixels={showPixels}
              onPick={(ra, dec) => setSpectrum({ kind: 'spot', ra: Number(ra.toFixed(5)), dec: Number(dec.toFixed(5)) })}
              describedBy="stage-help"
            >
              {(scale) => (
                <>
                  {showMotion && (
                    <MotionLayer
                      sizePx={grid.sizePx}
                      scale={scale}
                      start={start && path.length > 1 ? toPicture(start) : null}
                      path={path.map(toPicture)}
                      here={frame.centroid && toPicture(frame.centroid)}
                      arrow={arrow}
                    />
                  )}
                  {showGaia && (
                    <GaiaOverlay
                      frames={gaiaFrames}
                      current={gaiaCurrent}
                      sizePx={load.data.size_px}
                      pixelArcsec={load.data.pixel_arcsec}
                      target={load.data.target}
                    />
                  )}
                  {aperture && <ApertureMark sizePx={grid.sizePx} at={aperture} radiusPx={SPECTRUM_APERTURE_ARCSEC / grid.pixelArcsec} />}
                </>
              )}
            </Stage>
            <p id="stage-help" className="hint">
              Scroll or pinch to zoom, drag to move, click a spot to measure its spectrum. The space bar plays and
              pauses and the arrow keys step. With the image selected, + and - zoom and Shift with an arrow key
              moves it. North is up and east is left. A flat white patch is too bright to measure; hatching is sky
              with no data.
            </p>
          </>
        )}
      </div>

      {load.state === 'ready' && frame && (
        <>
          <section className="now" aria-label="The frame on screen">
            {/* Read out when stepping, but not while playing: it would never stop talking. */}
            <div aria-live={player.playback === 'paused' ? 'polite' : 'off'}>
              <p className="frame-label">
                {player.playback === 'blinking' && <span className="tag">{player.current === 0 ? 'First' : 'Last'}</span>}
                {frameLabel(frame, load.data)}
              </p>
              <p className="motion-readout">{motionSentence(frame, load.data)}</p>
            </div>

            <PlayerControls
              frames={load.data.frames.map((f) => ({ label: frameLabel(f, load.data), tick: frameTick(f, load.data) }))}
              tickTitle="Visit"
              current={player.current}
              playback={player.playback}
              speedMs={player.speedMs}
              onTogglePlay={player.togglePlay}
              onToggleBlink={player.toggleBlink}
              onStep={player.step}
              onShow={player.show}
              onSpeed={player.setSpeedMs}
            />

            <div className="controls">
              {toggle(showMotion, setShowMotion, 'Motion markers', 'Mark where the target was measured in each frame')}
              {toggle(
                showGaia,
                setShowGaia,
                load.data.target?.origin === 'request' ? 'Predicted positions' : 'Gaia overlay',
                'Mark where the target should be according to its catalogued motion',
              )}
              {toggle(showPixels, setShowPixels, 'Show pixels', 'Hard-edged pixels instead of smooth scaling, with their edges drawn when zoomed in')}
              <button
                type="button"
                onClick={() =>
                  setSpectrum({ kind: 'target', ra: load.data.ra, dec: load.data.dec, motion: targetMotion(load.data.target) })
                }
              >
                Spectrum of the target
              </button>
            </div>

            {showPixels && (
              <p className="hint">
                Each square is {load.data.pixel_arcsec} arcseconds across. The frames are drawn on a finer grid than
                SPHEREx's own pixels, which are {NATIVE_PIXEL_ARCSEC} arcseconds across.
              </p>
            )}
            {showMotion && path.length > 0 && (
              <MotionLegend
                start={path.length > 1}
                path={path.length > 1}
                arrow={arrow}
                note={load.data.mode === 'difference' ? "The positions were measured in each visit's own image, not in the difference." : undefined}
              />
            )}
            {/* The Gaia readout compares frames with the first one. With a single frame and a
                known motion there is nothing to compare, so one line says what the marks are. */}
            {showGaia &&
              (gaiaFrames.length > 1 || load.data.target?.pmra == null || load.data.target.pmdec == null ? (
                <GaiaReadout frames={gaiaFrames} current={gaiaCurrent} target={load.data.target} gaiaError={load.data.gaia_error} />
              ) : (
                <p className="readout">
                  <span className="key gaia">+</span> marks where the target's known motion puts it on the middle date of
                  this frame; the arrow is one year of that motion.
                </p>
              ))}
          </section>

          <FrameDetails frame={load.data.frames[player.current]} detector={load.data.detector} />
          {spectrum && <SpectrumPanel request={spectrum} onClose={() => setSpectrum(null)} />}
        </>
      )}

      <footer>
        <p>
          <a href={`viewer.html${addressOf(selection)}`}>Open this view in the earlier single-page viewer</a>, which this
          page grew out of.
        </p>
        Images: NASA/JPL-Caltech SPHEREx, served by NASA/IPAC Infrared Science Archive (IRSA). Star positions and
        motions: ESA Gaia DR3.
      </footer>
    </main>
  )
}
