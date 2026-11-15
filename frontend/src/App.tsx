// The page: which patch of sky to show and how (kept in the page address), the frames
// for it, and the player around them. Issues #5 (player), #7 (selectors) and #8 (motion
// markers). The Gaia overlay and field stars (#10), frame details, flags and sky context
// (#12), spectrum (#11) and brightness chart (#9) are components of their own that only
// need the frames and the frame on screen.
//
// The layout is a blink comparator: the picture (the "plate") on the left with the player
// and the strip of visits under it, and on the right an "inspector" that says what is on
// the plate. Together they fill the window and never move: text that changes with the
// visit sits in a block of fixed height, and while a new view loads the old pictures stay
// on the plate, dimmed. Expert's tool panels open below, and the page scrolls to them.
import { useCallback, useEffect, useRef, useState } from 'react'
import { addressOf, DEFAULT_SELECTION, readAddress, readStoredLevel, storeLevel, toFramesQuery, withTarget, writeAddress, type Selection, type UiLevel } from './address'
import { framesUrl, NATIVE_PIXEL_ARCSEC } from './api'
import { BrightnessPanel } from './components/BrightnessPanel'
import { ContextView } from './components/ContextView'
import { FieldStars } from './components/FieldStars'
import { DetectionReadout } from './components/DetectionReadout'
import { isMarginal } from './detection'
import { FrameDetails } from './components/FrameDetails'
import { GaiaOverlay, GaiaReadout } from './components/GaiaOverlay'
import { InfoButton } from './components/InfoButton'
import { LevelSwitch, StepGuide } from './components/LevelSwitch'
import { ApertureMark, MotionLayer, MotionLegend } from './components/MotionLayer'
import { SearchField, SkySearch, TargetButtons, type SearchTarget } from './components/SearchBar'
import { DistantMarkers, DistantPanel } from './components/DistantPanel'
import { SearchMarkers, SearchPanel } from './components/SearchPanel'
import { Selectors } from './components/Selectors'
import { SmallBodiesPanel } from './components/SmallBodiesPanel'
import { SpectrumPanel } from './components/SpectrumPanel'
import { Stage } from './components/Stage'
import { TrainingView } from './components/TrainingView'
import { Transport, VisitStrip, type Visit } from './components/Transport'
import { WatchlistView } from './components/WatchlistView'
import { isWatchlistAddress, WATCHLIST_ADDRESS } from './watchlist'
import { PlateLoading, PlateMessage } from './components/StatusCard'
import { keyBelongsToControl, releaseFocusAfterPointer } from './focus'
import { infoFor, INFO_NAMES, NO_PROGRESS, PICTURE_INFO_ID, type InfoKey, type Progress } from './guide'
import { measuredPath, overallShift, SMALL_SHIFT_ARCSEC, startCentroid, toPicture } from './motion'
import { skyToPixel, type Grid } from './projection'
import type { Candidate } from './distant'
import type { SearchObject, SearchQuery } from './search'
import { targetMotion, type SpectrumRequest } from './spectrum'
import { fetchStars, fieldStarsSummary, type StarsResponse } from './stars'
import { newSeed, trainingAddress } from './training'
import { useFrames } from './useFrames'
import { usePlayer } from './usePlayer'
import { failuresSentence, frameLabel, modeSentence, motionSentence, saturationSentence, visitCaption } from './wording'
import { startBox, type Point, type ZoomBox } from './zoom'
import './App.css'

/** The circle /api/spectrum adds up: 2.5 SPHEREx pixels in radius (backend/photometry.py). */
const SPECTRUM_APERTURE_ARCSEC = 2.5 * NATIVE_PIXEL_ARCSEC

/** The tool panels that open below the picture, by the id of the slot each opens in ("tool-<name>"). */
type Tool = 'spectrum' | 'brightness' | 'search' | 'distant' | 'smallbodies'

const prefersStillness = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true

// Practice mode (?train=<seed>) is a separate screen: none of the viewer below is mounted for it.
export default function App() {
  if (isWatchlistAddress(window.location.search)) return <WatchlistView />
  return readAddress(window.location.search).selection.train !== null ? <TrainingView /> : <Viewer />
}

export function Viewer() {
  // What the address asks for, and what in it could not be used.
  const [fromAddress] = useState(() => readAddress(window.location.search, readStoredLevel()))
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
  // Issue #9: whose brightness over time is shown, or null when that panel is closed.
  const [brightness, setBrightness] = useState<SpectrumRequest | null>(null)
  // Search mode: the patch being searched (null when the panel is closed), and what it found, to mark on the picture.
  const [search, setSearch] = useState<SearchQuery | null>(null)
  const [searchFound, setSearchFound] = useState<SearchObject[]>([])
  // Distant-world search: the patch being searched (null when closed), and the candidates on screen.
  const [distant, setDistant] = useState<{ ra: number; dec: number; fov: number } | null>(null)
  const [distantFound, setDistantFound] = useState<{ candidates: Candidate[]; simulation: boolean }>({ candidates: [], simulation: false })
  const onDistantCandidates = useCallback((candidates: Candidate[], simulation: boolean) => setDistantFound({ candidates, simulation }), [])
  // Known asteroids and comets (backend/smallbodies.py): open only when asked for, as the lookup is slow.
  const [showSmallBodies, setShowSmallBodies] = useState(false)
  // Issue #12: colour the pixels with no data and the saturated ones.
  const [showFlags, setShowFlags] = useState(false)
  // Issue #12: the same patch of sky in other surveys. Off until asked for: it loads a
  // large sky-atlas library and depends on servers in Strasbourg that are not always up.
  const [showContext, setShowContext] = useState(false)
  // Issue #10: the Gaia stars of the view, placed on every visit's frame, and the view they belong to.
  const [stars, setStars] = useState<{ view: string; data: StarsResponse } | { view: string; error: string } | null>(null)
  // The target button last pressed, and where it took the page, so the button can be shown as the one on screen.
  const [picked, setPicked] = useState<{ name: string; ra: number; dec: number } | null>(null)

  // Beginner shows the picture and what moved; Expert shows everything. Nothing is mounted for
  // Beginner that only Expert has, and the choices made in Expert (which overlays, which panels) wait unchanged.
  const expert = selection.ui === 'expert'

  const url = framesUrl(toFramesQuery(selection))
  const load = useFrames(url, attempt)
  // The view asked for, once it has arrived.
  const fresh = load.state === 'ready' ? load.data : null
  // What the picture shows: that view or, while a new one is on its way, the one before it.
  const data = fresh ?? (load.state === 'loading' ? load.previous : null)
  // Loading for longer than a moment (or with nothing to show meanwhile): the picture is
  // dimmed with a message over it, and the player waits.
  const busy = load.state === 'loading' && (load.slow || load.previous === null)
  const player = usePlayer(data?.key ?? '', data?.frames.length ?? 0)
  const frame = data?.frames[player.current] ?? null

  // Beginner's step guide: what the visitor has actually done. The player starts playing by
  // itself, so only a press of theirs counts as flipping through the visits.
  const [progress, setProgress] = useState<Progress>(NO_PROGRESS)
  const mark = useCallback((what: keyof Progress) => setProgress((was) => (was[what] ? was : { ...was, [what]: true })), [])
  const { togglePlay: playerTogglePlay, toggleBlink: playerToggleBlink, step: playerStep, show: playerShow } = player
  const togglePlay = useCallback(() => {
    playerTogglePlay()
    mark('flipped')
  }, [playerTogglePlay, mark])
  const toggleBlink = useCallback(() => {
    playerToggleBlink()
    mark('flipped')
  }, [playerToggleBlink, mark])
  const step = useCallback(
    (by: number) => {
      playerStep(by)
      mark('flipped')
    },
    [playerStep, mark],
  )
  const showVisit = useCallback(
    (index: number) => {
      playerShow(index)
      mark('flipped')
    },
    [playerShow, mark],
  )

  // ---- the page address -------------------------------------------------------------------

  const latest = useRef(selection)
  useEffect(() => {
    latest.current = selection
  })
  // The detector the visitor picked (or the address asked for). A target can suggest
  // another one; the next target that suggests none goes back to this.
  const usualDetector = useRef(fromAddress.selection.det)

  /** Show a selection: keep it, put it in the address, and let the frames reload. */
  const show = useCallback((next: Selection, how: 'push' | 'replace') => {
    const was = latest.current
    // An open spectrum belongs to the target it was asked for: its place and its motion.
    const sameTarget =
      next.ra === was.ra && next.dec === was.dec && next.pmra === was.pmra && next.pmdec === was.pmdec && next.parallax === was.parallax
    if (!sameTarget) {
      setSpectrum(null)
      setBrightness(null)
      setDistant(null)
    }
    setSelection(next)
    setNotes([])
    writeAddress(next, how)
  }, [])

  /**
   * Show a new target: what the search box calls with what it found (issue #6). It takes
   * a position and, when the search knows them, the object's name, its motion (pmra,
   * pmdec, parallax, as /api/resolve returns them) and a detector to switch to. A
   * target without a motion clears the one before it. The field of view and the mode
   * stay as they are. The address gets the new position, motion and detector as a new
   * history entry, so the link can be shared and Back returns to the previous target.
   * `button` is the target button's name when the target came from one.
   */
  const applyTarget = useCallback(
    (target: SearchTarget, button?: string) => {
      const next = withTarget(latest.current, target, usualDetector.current)
      if (next) {
        show(next, 'push')
        mark('chose')
        setPicked(button ? { name: button, ra: next.ra, dec: next.dec } : null)
      } else setNotes(['That position could not be used: a declination has to be between -90 and 90 degrees.'])
    },
    [show, mark],
  )
  const pickedHere = picked && picked.ra === selection.ra && picked.dec === selection.dec ? picked.name : null
  // The name to show: the target button's own ("Epsilon Indi B") when one was pressed for this, else the catalogue's.
  const shownName = pickedHere ?? selection.name

  // Tidy the address once (defaults filled in, `detector` renamed to `det`), and follow
  // the browser's Back and Forward buttons.
  useEffect(() => {
    writeAddress(fromAddress.selection, 'replace')
    const onPop = () => {
      const read = readAddress(window.location.search, readStoredLevel())
      setSpectrum(null)
      setBrightness(null)
      setDistant(null)
      setSelection(read.selection)
      setNotes(read.notes)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [fromAddress])

  /** Switch level without losing the place: same target, frame and zoom. Beginner closes the expert panels. */
  const changeLevel = (ui: UiLevel) => {
    storeLevel(ui)
    if (ui === 'expert') {
      show({ ...selection, ui }, 'replace')
      return
    }
    const wasChanged = selection.mode !== DEFAULT_SELECTION.mode || selection.fov !== DEFAULT_SELECTION.fov
    setSpectrum(null)
    setBrightness(null)
    setSearch(null)
    setSearchFound([])
    setDistant(null)
    setShowSmallBodies(false)
    setShowContext(false)
    show({ ...selection, ui, mode: DEFAULT_SELECTION.mode, fov: DEFAULT_SELECTION.fov }, 'replace')
    if (wasChanged) setNotes(['Beginner shows the normal view at the usual size, so the picture has gone back to that.'])
  }

  // The browser tab, and so the entries under the Back button, say which target this is.
  const whereInWords = shownName ?? `RA ${selection.ra.toFixed(4)}°, Dec ${selection.dec.toFixed(4)}°`
  useEffect(() => {
    document.title = `${whereInWords}: SPHEREx sky-change viewer`
  }, [whereInWords])

  // ---- keyboard: the space bar plays and pauses, the arrow keys step ---------------------

  const severalFrames = (data?.frames.length ?? 0) > 1 && !busy
  // Reaching the last visit, after flipping through them, counts as having read the changes.
  const atLast = severalFrames && player.current === (data?.frames.length ?? 0) - 1
  if (atLast && progress.flipped && !progress.read) setProgress({ ...progress, read: true })
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

  // ---- field stars (issue #10) ---------------------------------------------------------------

  // Asked for only once the frames have arrived: /api/stars needs the same exposures, and
  // asking for both at once would fetch a view that is not cached twice over.
  const { ra, dec, fov, det, pmra, pmdec, parallax } = selection
  const starsView = `${ra},${dec},${fov},${det},${pmra},${pmdec},${parallax}`
  const framesReady = fresh !== null
  useEffect(() => {
    if (!framesReady) return
    const ctrl = new AbortController()
    const motion = pmra !== null && pmdec !== null ? { pmra, pmdec, parallax } : undefined
    fetchStars({ ra, dec, fov, detector: det, motion }, ctrl.signal)
      .then((found) => setStars({ view: starsView, data: found }))
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setStars({ view: starsView, error: e instanceof Error ? e.message : String(e) })
      })
    return () => ctrl.abort()
  }, [framesReady, starsView, ra, dec, fov, det, pmra, pmdec, parallax])
  const starsData = stars && stars.view === starsView && 'data' in stars ? stars.data : null
  const starsError = stars && stars.view === starsView && 'error' in stars ? stars.error : null
  // The stars are placed on each visit's frame. Find the visit on screen among them: a
  // difference view leaves the first visit out, and a sum has no single visit at all.
  const starsFrame = starsData && frame && frame.epoch !== null ? starsData.frames.findIndex((f) => f.epoch === frame.epoch) : -1
  const hasFlags = data !== null && data.frames.every((f) => f.flags_image)

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
  const failures = fresh && failuresSentence(fresh)

  // ---- the tool panels below the picture ---------------------------------------------------

  const shell = useRef<HTMLDivElement>(null)
  const bench = useRef<HTMLElement>(null)
  const scrollBehavior = (): ScrollBehavior => (prefersStillness() ? 'auto' : 'smooth')
  // The panel just opened, which the page then scrolls to. `n` makes pressing the same button again scroll again.
  const [opened, setOpened] = useState<{ tool: Tool; n: number } | null>(null)
  const openTool = (tool: Tool) => setOpened((was) => ({ tool, n: (was?.n ?? 0) + 1 }))
  useEffect(() => {
    if (opened) document.getElementById(`tool-${opened.tool}`)?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
  }, [opened])
  const backToPicture = () => shell.current?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
  // Whether the picture is in the window: when it is not and a panel is open, a button leads back to it.
  const [benchInView, setBenchInView] = useState(true)
  useEffect(() => {
    const el = bench.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const watch = new IntersectionObserver(([entry]) => setBenchInView(entry.intersectionRatio >= 0.2), { threshold: [0, 0.2, 0.5] })
    watch.observe(el)
    return () => watch.disconnect()
  }, [])
  const anyTool = expert && (spectrum !== null || brightness !== null || search !== null || distant !== null || showSmallBodies)

  // Search mode's "Look at this one": zoom to the object if it is in this picture, else move the view to it.
  const lookAt = (ra: number, dec: number) => {
    if (!grid) return
    const p = skyToPixel(ra, dec, grid)
    if (p.x >= 0 && p.y >= 0 && p.x <= grid.sizePx && p.y <= grid.sizePx) changeBox(() => startBox(grid.sizePx, p))
    else applyTarget({ ra, dec })
    backToPicture()
  }
  const toggle = (on: boolean, set: (on: boolean) => void, text: string, title: string, disabled = false) => (
    <button
      type="button"
      className="toggle chip"
      aria-pressed={on}
      disabled={disabled}
      title={title}
      onClick={(e) => {
        set(!on)
        releaseFocusAfterPointer(e.currentTarget)
      }}
    >
      {text}
    </button>
  )
  // The tools need the view on screen; while a new one loads they wait.
  const ready = busy ? null : data

  const visits: Visit[] = data ? data.frames.map((f) => ({ src: f.image, label: frameLabel(f, data), ...visitCaption(f, data) })) : []

  // Beginner's small "i" buttons: what exactly is going on, in words computed from what is on screen (guide.ts). None in Expert.
  const infoButton = (key: InfoKey, className?: string, id?: string) =>
    !expert && (
      <InfoButton
        name={INFO_NAMES[key]}
        text={infoFor(key, data, frame, starsData?.bright_nearby)}
        className={className}
        id={id}
        onOpen={() => mark('read')}
      />
    )

  return (
    <div className="app">
      <div className="shell" ref={shell}>
        {/* Issue #6: a name or coordinates, or a target button. What they find goes to applyTarget. */}
        <SkySearch onSelect={applyTarget}>
          {(skySearch) => (
            <>
              <header className="topbar">
                <h1 className="brand">SPHEREx sky-change viewer</h1>
                <SearchField search={skySearch} />
                <LevelSwitch level={selection.ui} onChange={changeLevel} />
                {infoButton('level')}
              </header>

              <nav className="targets" aria-label="Targets">
                <TargetButtons search={skySearch} picked={pickedHere} shown={selection.name} />
                <div className="target-actions">
                  <button type="button" className="quiet" onClick={() => window.location.assign(trainingAddress(selection, newSeed()))}>
                    Practise: find a planted object
                  </button>
                  <a className="quiet" href={expert ? `${WATCHLIST_ADDRESS}&ui=expert` : WATCHLIST_ADDRESS}>
                    Help check what the search found
                  </a>
                </div>
              </nav>
            </>
          )}
        </SkySearch>

        <main className="bench" ref={bench}>
          <section className="stagecol" aria-label="The picture">
            <div className="plate-col">
              <div className={busy ? 'plate busy' : 'plate'}>
                {data && grid && frame && box ? (
                  <Stage
                    grid={grid}
                    images={data.frames.map((f) => ({ key: f.image, src: f.image }))}
                    current={player.current}
                    alt={`${frameLabel(frame, data)}. ${motionSentence(frame, data)}`}
                    box={box}
                    onBoxChange={changeBox}
                    onReset={() => setZoomed(null)}
                    showPixels={expert && showPixels}
                    onPick={
                      expert && !busy
                        ? (ra, dec) => {
                            setSpectrum({ kind: 'spot', ra: Number(ra.toFixed(5)), dec: Number(dec.toFixed(5)) })
                            openTool('spectrum')
                          }
                        : undefined
                    }
                    describedBy="stage-help"
                  >
                    {(scale) => (
                      <>
                        {expert && showFlags && frame.flags_image && <img className="flags" src={frame.flags_image} alt="" />}
                        {expert && showGaia && starsData && starsFrame >= 0 && (
                          <FieldStars data={starsData} current={starsFrame} sizePx={data.size_px} pixelArcsec={data.pixel_arcsec} />
                        )}
                        {expert && showMotion && (
                          <MotionLayer
                            sizePx={grid.sizePx}
                            scale={scale}
                            start={start && path.length > 1 ? toPicture(start) : null}
                            path={path.map(toPicture)}
                            here={frame.centroid && toPicture(frame.centroid)}
                            hereMarginal={isMarginal(frame)}
                            arrow={arrow}
                          />
                        )}
                        {expert && showGaia && (
                          <GaiaOverlay frames={gaiaFrames} current={gaiaCurrent} sizePx={data.size_px} pixelArcsec={data.pixel_arcsec} target={data.target} />
                        )}
                        {expert && search && searchFound.length > 0 && <SearchMarkers objects={searchFound} grid={grid} scale={scale} />}
                        {expert && distant && distantFound.candidates.length > 0 && !distantFound.simulation && (
                          <DistantMarkers
                            candidates={distantFound.candidates}
                            grid={grid}
                            scale={scale}
                            epoch={frame.epoch}
                            simulation={distantFound.simulation}
                          />
                        )}
                        {expert && aperture && <ApertureMark sizePx={grid.sizePx} at={aperture} radiusPx={SPECTRUM_APERTURE_ARCSEC / grid.pixelArcsec} />}
                      </>
                    )}
                  </Stage>
                ) : (
                  // Nothing to show yet: an empty plate of the same size, so nothing around it moves.
                  <div className="stage stage-empty" />
                )}
                {busy && <PlateLoading key={`${attempt} ${url}`} what={whereInWords} />}
                {load.state === 'error' && (
                  <PlateMessage title="The frames could not be loaded" tone="error">
                    <p>{load.message}</p>
                    <button type="button" onClick={() => setAttempt(attempt + 1)}>
                      Try again
                    </button>
                  </PlateMessage>
                )}
                {load.state === 'empty' && (
                  <PlateMessage title="No frames to show here">
                    <p>{load.message}</p>
                    <p>Another detector or another mode may have some.</p>
                    <button
                      type="button"
                      onClick={() => applyTarget({ ra: DEFAULT_SELECTION.ra, dec: DEFAULT_SELECTION.dec, name: DEFAULT_SELECTION.name ?? undefined, det: DEFAULT_SELECTION.det })}
                    >
                      Show the example, Barnard's Star
                    </button>
                  </PlateMessage>
                )}
                {/* Expert keeps the "?" with how to work the picture; Beginner has the "i", which also tells how the picture was made. */}
                {expert ? <PlateHelp expert /> : infoButton('picture', 'plate-info', PICTURE_INFO_ID)}
              </div>

              <Transport
                several={(data?.frames.length ?? 0) > 1}
                disabled={busy}
                playback={player.playback}
                speedMs={player.speedMs}
                onTogglePlay={togglePlay}
                onToggleBlink={toggleBlink}
                onStep={step}
                onSpeed={player.setSpeedMs}
                info={infoButton('player')}
              />
              {expert ? (
                <VisitStrip visits={visits} current={player.current} disabled={busy} onShow={showVisit} />
              ) : (
                <div className="strip-row">
                  <VisitStrip visits={visits} current={player.current} disabled={busy} onShow={showVisit} />
                  {infoButton('visits')}
                </div>
              )}
            </div>
          </section>

          <aside className={expert ? 'inspector' : 'inspector beginner'} aria-label="What is on the picture">
            <div className="object">
              {shownName && <h2 className="object-name">{shownName}</h2>}
              <p className={shownName ? 'object-where' : 'object-where object-name'}>
                <abbr title="right ascension">RA</abbr> {`${selection.ra.toFixed(5)}°, `}
                <abbr title="declination">Dec</abbr> {`${selection.dec >= 0 ? '+' : '-'}${Math.abs(selection.dec).toFixed(5)}°`}
                {expert && givenMotion !== null && `, followed with its known motion of ${givenMotion.toFixed(2)} arcseconds a year`}
              </p>
            </div>

            {/* Rare notes (about the address, the level, downloads that failed). They sit here, so the picture never moves for them. */}
            {(notes.length > 0 || failures) && (
              <div className="notices">
                {notes.map((note) => (
                  <p key={note} className="notice" role="status">
                    {note}
                  </p>
                ))}
                {failures && (
                  <p className="notice">
                    {failures}{' '}
                    <button type="button" onClick={() => setAttempt(attempt + 1)}>
                      Try again
                    </button>
                  </p>
                )}
              </div>
            )}

            {/* Everything that changes with the visit on screen, in a block whose height never changes. */}
            <div className={busy ? 'readout-block busy' : 'readout-block'} aria-busy={busy || undefined}>
              {data && frame && (
                // Read out when stepping, but not while playing: it would never stop talking.
                <div aria-live={player.playback === 'paused' ? 'polite' : 'off'}>
                  <p className="frame-label">
                    {player.playback === 'blinking' && <span className="tag">{player.current === 0 ? 'First' : 'Last'}</span>}
                    {frameLabel(frame, data)}
                  </p>
                  <p className="motion-readout">
                    {motionSentence(frame, data)}
                    {infoButton('movement')}
                  </p>
                  <DetectionReadout frame={frame} detectionOnly={!expert} info={infoButton('detection')} />
                </div>
              )}
              {expert && saturation && <p className="notice">{saturation}</p>}
              {/* Shown at both levels and whether or not the overlay is on: it warns about shapes in the picture itself. */}
              {starsData?.bright_note && (
                <p className="hint bright-star">
                  {starsData.bright_note}
                  {infoButton('bright')}
                </p>
              )}
            </div>

            {expert ? (
              <>
                <section className="ins-section" aria-labelledby="ins-view">
                  <h3 id="ins-view">View</h3>
                  <Selectors
                    selection={selection}
                    motionKnown={motionKnown}
                    onChange={(change) => {
                      if (change.det !== undefined) usualDetector.current = change.det
                      show({ ...selection, ...change }, 'replace')
                    }}
                  />
                  {data && <p className="mode-note">{modeSentence(data)}</p>}
                </section>

                <section className="ins-section" aria-labelledby="ins-picture">
                  <h3 id="ins-picture">On the picture</h3>
                  <div className="chips">
                    {toggle(showMotion, setShowMotion, 'Motion markers', 'Mark where the target was measured in each frame')}
                    {toggle(
                      showGaia,
                      setShowGaia,
                      data?.target?.origin === 'request' ? 'Predicted positions' : 'Gaia overlay',
                      'Mark where the target should be according to its catalogued motion',
                    )}
                    {toggle(showPixels, setShowPixels, 'Show pixels', 'Hard-edged pixels instead of smooth scaling, with their edges drawn when zoomed in')}
                    {toggle(
                      showFlags && hasFlags,
                      setShowFlags,
                      'Flags',
                      hasFlags
                        ? 'Colour the pixels with no data and the ones too bright to measure'
                        : 'A difference view has no flags layer: it is already blank wherever either visit has no data',
                      !hasFlags,
                    )}
                  </div>
                  {data && showMotion && path.length > 0 && (
                    <MotionLegend
                      start={path.length > 1}
                      path={path.length > 1}
                      arrow={arrow}
                      marginal={data.frames.some(isMarginal)}
                      note={data.mode === 'difference' ? "The positions were measured in each visit's own image, not in the difference." : undefined}
                    />
                  )}
                  {data && frame && showFlags && hasFlags && (
                    <p className="readout">
                      <span className="key nodata">■</span> no data, <span className="key saturated">■</span> saturated: no
                      value in any exposure of this frame
                      {frame.saturated_pixels === 0 && ' (none here)'}
                      {(frame.photometry_saturated_exposures ?? 0) > 0 &&
                        `. For measuring brightness the star's core is saturated in ${frame.photometry_saturated_exposures} of this frame's ${frame.n_exposures} exposures, even where the image looks fine.`}
                    </p>
                  )}
                  {data && showPixels && (
                    <p className="hint">
                      Each square is {data.pixel_arcsec} arcseconds across. The frames are drawn on a finer grid than
                      SPHEREx's own pixels, which are {NATIVE_PIXEL_ARCSEC} arcseconds across.
                    </p>
                  )}
                </section>

                <section className="ins-section" aria-labelledby="ins-measure">
                  <h3 id="ins-measure">Measure</h3>
                  <div className="tool-buttons">
                    <button
                      type="button"
                      disabled={!ready}
                      onClick={() => {
                        if (!ready) return
                        setSpectrum({ kind: 'target', ra: ready.ra, dec: ready.dec, motion: targetMotion(ready.target) })
                        openTool('spectrum')
                      }}
                    >
                      Spectrum of the target
                    </button>
                    <button
                      type="button"
                      disabled={!ready}
                      onClick={() => {
                        if (!ready) return
                        setBrightness({ kind: 'target', ra: ready.ra, dec: ready.dec, motion: targetMotion(ready.target) })
                        openTool('brightness')
                      }}
                    >
                      Brightness over time
                    </button>
                  </div>
                </section>

                <section className="ins-section" aria-labelledby="ins-search">
                  <h3 id="ins-search">Search this patch</h3>
                  <div className="tool-buttons">
                    <button
                      type="button"
                      aria-label="Search this patch for anything that moved or changed"
                      disabled={!ready}
                      onClick={() => {
                        if (!ready) return
                        setSearch({ ra: ready.ra, dec: ready.dec, fov: selection.fov })
                        openTool('search')
                      }}
                    >
                      Anything that moved or changed
                    </button>
                    <button
                      type="button"
                      aria-label="Search for a distant world (Planet X)"
                      disabled={!ready}
                      onClick={() => {
                        if (!ready) return
                        setDistant({ ra: ready.ra, dec: ready.dec, fov: selection.fov })
                        openTool('distant')
                      }}
                    >
                      A distant world (Planet X)
                    </button>
                    <button
                      type="button"
                      disabled={!ready}
                      onClick={() => {
                        setShowSmallBodies(true)
                        openTool('smallbodies')
                      }}
                    >
                      Asteroids and comets
                    </button>
                    {/* New Expert tools: add their button here (and their panel in .tool-panels below, after DistantPanel). */}
                  </div>
                </section>

                {/* Open from the start: measured against predicted is the check a judge looks for. The
                    inspector scrolls inside itself, so its length moves nothing. */}
                <details className="fold" open>
                  <summary>Catalogue notes</summary>
                  {/* The Gaia readout compares frames with the first one. With a single frame and a
                      known motion there is nothing to compare, so one line says what the marks are. */}
                  {data &&
                    showGaia &&
                    (gaiaFrames.length > 1 || data.target?.pmra == null || data.target.pmdec == null ? (
                      <GaiaReadout frames={gaiaFrames} current={gaiaCurrent} target={data.target} gaiaError={data.gaia_error} pixelArcsec={data.pixel_arcsec} />
                    ) : (
                      <p className="readout">
                        <span className="key gaia">+</span> marks where the target's known motion puts it on the middle date
                        of this frame
                        {Math.hypot(data.target.pmra, data.target.pmdec) / 1000 >= data.pixel_arcsec
                          ? '; the arrow is one year of that motion.'
                          : '. It moves too little in a year to draw as an arrow.'}
                      </p>
                    ))}
                  {showGaia && starsData && starsFrame >= 0 && data && <p className="readout">{fieldStarsSummary(starsData, data.pixel_arcsec)}</p>}
                  {showGaia && starsData && starsFrame < 0 && (
                    <p className="hint">The other Gaia stars are drawn on single visits only, so not on a sum of all visits.</p>
                  )}
                  {showGaia && starsError && <p className="hint">The other Gaia stars could not be loaded: {starsError}.</p>}
                  {!showGaia && <p className="hint">Turn on the Gaia overlay to compare the picture with the catalogue.</p>}
                </details>

                <details className="fold">
                  <summary>Frame details</summary>
                  {data && frame ? <FrameDetails frame={frame} detector={data.detector} /> : <p className="hint">No frame yet.</p>}
                </details>

                <details className="fold">
                  <summary>Sky context</summary>
                  {showContext ? (
                    <ContextView ra={selection.ra} dec={selection.dec} fov={selection.fov} />
                  ) : (
                    <>
                      <p className="hint">The same patch of sky in other surveys (WISE, 2MASS, optical), from the Aladin sky atlas.</p>
                      <button type="button" onClick={() => setShowContext(true)}>
                        Show other surveys
                      </button>
                    </>
                  )}
                </details>
              </>
            ) : (
              <StepGuide progress={progress} />
            )}

            <footer className="credits">
              <p>
                Images: NASA/JPL-Caltech SPHEREx, from <abbr title="NASA/IPAC Infrared Science Archive">IRSA</abbr>. Stars:
                ESA Gaia DR3.
              </p>
              {expert && (
                <p>
                  <a href={`viewer.html${addressOf(selection)}`}>Open this view in the earlier single-page viewer</a>
                </p>
              )}
            </footer>
          </aside>
        </main>
      </div>

      {/* Expert's tool panels, full width under the picture, in the order they were added. */}
      <div className="tool-panels">
        {expert && spectrum && (
          <div className="tool-slot" id="tool-spectrum">
            <SpectrumPanel request={spectrum} onClose={() => setSpectrum(null)} />
          </div>
        )}
        {expert && brightness && (
          <div className="tool-slot" id="tool-brightness">
            <BrightnessPanel request={brightness} onClose={() => setBrightness(null)} />
          </div>
        )}
        {expert && search && (
          <div className="tool-slot" id="tool-search">
            <SearchPanel
              key={`${search.ra},${search.dec},${search.fov}`}
              query={search}
              onClose={() => setSearch(null)}
              onObjects={setSearchFound}
              onLook={lookAt}
            />
          </div>
        )}
        {expert && distant && (
          <div className="tool-slot" id="tool-distant">
            <DistantPanel
              key={`${distant.ra},${distant.dec},${distant.fov}`}
              query={distant}
              onClose={() => setDistant(null)}
              onCandidates={onDistantCandidates}
              onLook={lookAt}
            />
          </div>
        )}
        {/* New tool panels go here, after DistantPanel: a .tool-slot with id "tool-<name>", opened with openTool('<name>'). */}
        {expert && showSmallBodies && data && (
          <div className="tool-slot" id="tool-smallbodies">
            <SmallBodiesPanel
              query={{ ra: data.ra, dec: data.dec, fov: data.fov, detector: data.detector }}
              onClose={() => setShowSmallBodies(false)}
            />
          </div>
        )}
      </div>

      {anyTool && !benchInView && (
        <button type="button" className="back-to-plate" onClick={backToPicture}>
          Back to the picture
        </button>
      )}
    </div>
  )
}

/**
 * How to work the picture, behind a small button in its corner. Also the picture's
 * description for screen readers (the stage points to it by id).
 */
function PlateHelp({ expert }: { expert: boolean }) {
  return (
    <>
      <button type="button" className="plate-help-button" popoverTarget="stage-help" aria-label="How to move and zoom the picture" title="How to move and zoom the picture">
        ?
      </button>
      <div id="stage-help" className="plate-help" popover="auto">
        <p>
          Scroll or pinch to zoom, drag to move{expert ? ', click a spot to measure its spectrum' : ''}. The space bar plays and
          pauses and the arrow keys step. With the image selected, + and - zoom and Shift with an arrow key moves it. North
          is up and east is left. A flat white patch is too bright to measure{expert ? '; hatching is sky with no data.' : '.'}
        </p>
      </div>
    </>
  )
}
