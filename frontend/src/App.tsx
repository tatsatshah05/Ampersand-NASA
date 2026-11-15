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
// on the plate, dimmed. The bar at the top (FeatureBar) lists every feature: its tools open
// as panels below, at both levels (the level changes how they are written, not what they
// show), and the page scrolls to them. The Beginner | Expert switch is in a dock at the
// bottom right (LevelDock).
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  DEFAULT_SELECTION,
  readAddress,
  readStoredLevel,
  storeLevel,
  toFramesQuery,
  toolFrom,
  withTarget,
  withUi,
  writeAddress,
  writeTool,
  type Selection,
  type UiLevel,
} from './address'
import { framesUrl, NATIVE_PIXEL_ARCSEC } from './api'
import { BeforeAfter } from './components/BeforeAfter'
import { BrightnessPanel } from './components/BrightnessPanel'
import { ContextView } from './components/ContextView'
import { ObjectCard } from './components/ObjectCard'
import { FeatureBar, type FeatureLinks } from './components/FeatureBar'
import { FieldStars } from './components/FieldStars'
import { isMarginal } from './detection'
import { VisitDetails } from './components/VisitDetails'
import { VisitTable } from './components/VisitTable'
import { GaiaOverlay, GaiaReadout } from './components/GaiaOverlay'
import { InfoButton } from './components/InfoButton'
import { LevelDock } from './components/LevelDock'
import { StepGuide } from './components/LevelSwitch'
import { ApertureMark, MotionLayer, MotionLegend } from './components/MotionLayer'
import { SearchField, SkySearch, TargetButtons, type SearchTarget } from './components/SearchBar'
import { DistantMarkers, DistantPanel } from './components/DistantPanel'
import { SearchMarkers, SearchPanel } from './components/SearchPanel'
import { Selectors } from './components/Selectors'
import { SmallBodiesPanel } from './components/SmallBodiesPanel'
import { SpectrumPanel } from './components/SpectrumPanel'
import { Stage } from './components/Stage'
import { TrainingView } from './components/TrainingView'
import { ToolsView } from './components/ToolsView'
import { isToolsAddress, toolsAddress } from './tools'
import { Transport, VisitStrip, type Visit } from './components/Transport'
import { WatchlistView } from './components/WatchlistView'
import { isWatchlistAddress, WATCHLIST_ADDRESS } from './watchlist'
import { PlateLoading, PlateMessage } from './components/StatusCard'
import { keyBelongsToControl, releaseFocusAfterPointer } from './focus'
import type { FeatureKey, ToolKey } from './features'
import { brightLine, infoFor, INFO_NAMES, NO_PROGRESS, PICTURE_INFO_ID, type InfoKey, type Progress } from './guide'
import { isRealShift, measuredPath, overallEnds, startCentroid, toPicture } from './motion'
import { skyToPixel, type Grid } from './projection'
import type { Candidate } from './distant'
import type { SearchObject, SearchQuery } from './search'
import { targetMotion, type SpectrumRequest } from './spectrum'
import { fetchStars, fieldStarsSummary, type StarsResponse } from './stars'
import { newSeed, trainingAddress } from './training'
import { useFrames } from './useFrames'
import { usePlayer, useResting } from './usePlayer'
import { isHeldFind } from './finds'
import {
  beforeAfter,
  expertResult,
  expertVerdict,
  failuresSentence,
  flagsNote,
  frameLabel,
  modeSentence,
  motionSentence,
  overallResult,
  rowAnnouncement,
  saturationSentence,
  seenLine,
  tableNotes,
  visitCaption,
} from './wording'
import { startBox, type Point, type ZoomBox } from './zoom'
import './App.css'
import './inspector.css'

/** The circle /api/spectrum adds up: 2.5 SPHEREx pixels in radius (backend/photometry.py). */
const SPECTRUM_APERTURE_ARCSEC = 2.5 * NATIVE_PIXEL_ARCSEC

const prefersStillness = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true

// Practice mode (?train=<seed>) is a separate screen: none of the viewer below is mounted for it.
export default function App() {
  if (isWatchlistAddress(window.location.search)) return <WatchlistView />
  if (isToolsAddress(window.location.search)) return <ToolsView />
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
  // The tool last opened (from the bar, or a spot clicked for its spectrum): the bar's current
  // feature while its panel is open. Watch otherwise.
  const [focusTool, setFocusTool] = useState<ToolKey | null>(null)
  // The tool the address asks for (tool=<key>), opened once the first pictures are ready.
  const [addressedTool] = useState(() => toolFrom(window.location.search))
  const pendingTool = useRef<ToolKey | null>(addressedTool)
  // Counts the browser's Back and Forward, so the tool of the entry returned to is opened even when its view is already on screen.
  const [popped, setPopped] = useState(0)
  // The practice round the bar's Practise link starts: chosen once, so the link holds still.
  const [practiceSeed] = useState(newSeed)
  // Issue #10: the Gaia stars of the view, placed on every visit's frame, and the view they belong to.
  const [stars, setStars] = useState<{ view: string; data: StarsResponse } | { view: string; error: string } | null>(null)
  // The target button last pressed, and where it took the page, so the button can be shown as the one on screen.
  const [picked, setPicked] = useState<{ name: string; ra: number; dec: number } | null>(null)

  // Both levels have every tool; Beginner writes them in plain words and Expert as a scientist
  // would. Only Expert has the view settings (detector, field, mode, overlays): they wait
  // unchanged while Beginner is on.
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
  // The picture's box: while it is out of the window (or the tab is hidden) the player's timer rests.
  const plate = useRef<HTMLDivElement>(null)
  const resting = useResting(plate)
  // One of our sweep's candidates opens blinking between the visit without it and the first with it.
  const pair = data ? beforeAfter(data) : null
  const player = usePlayer(data?.key ?? '', data?.frames.length ?? 0, resting, pair && [pair.before, pair.after])
  const frame = data?.frames[player.current] ?? null
  // For screen readers: the row of the visit just stepped to or chosen, said once (D6). The
  // frames key it was said for; cleared by Play and Blink, and by another star.
  const [spokenFor, setSpokenFor] = useState<string | null>(null)
  const dataKey = data?.key ?? null

  // Beginner's step guide: what the visitor has actually done. Every view opens still
  // (usePlayer.ts), so the guide says to press Play or Blink, and only a press counts.
  const [progress, setProgress] = useState<Progress>(NO_PROGRESS)
  const mark = useCallback((what: keyof Progress) => setProgress((was) => (was[what] ? was : { ...was, [what]: true })), [])
  const { pause: pausePlayer, togglePlay: playerTogglePlay, toggleBlink: playerToggleBlink, step: playerStep, show: playerShow } = player
  const togglePlay = useCallback(() => {
    playerTogglePlay()
    setSpokenFor(null)
    mark('flipped')
  }, [playerTogglePlay, mark])
  const toggleBlink = useCallback(() => {
    playerToggleBlink()
    setSpokenFor(null)
    mark('flipped')
  }, [playerToggleBlink, mark])
  const step = useCallback(
    (by: number) => {
      playerStep(by)
      setSpokenFor(dataKey)
      mark('flipped')
    },
    [playerStep, mark, dataKey],
  )
  const showVisit = useCallback(
    (index: number) => {
      playerShow(index)
      setSpokenFor(dataKey)
      mark('flipped')
    },
    [playerShow, mark, dataKey],
  )
  // Stepping and choosing pause the player, so this is never said while the visits play.
  const voice = data && spokenFor === data.key && player.playback === 'paused' ? rowAnnouncement(data, player.current) : ''

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
    }
    // The two searches belong to the patch they searched: its place and its size. A search of
    // another patch must never be shown under this one (the bar and the address then fall back to Watch).
    if (!sameTarget || next.fov !== was.fov) {
      setSearch(null)
      setSearchFound([])
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
      // Every panel closes, and the tool this entry's address names opens again once its pictures are ready.
      setSpectrum(null)
      setBrightness(null)
      setSearch(null)
      setSearchFound([])
      setDistant(null)
      setShowSmallBodies(false)
      setShowContext(false)
      setFocusTool(null)
      pendingTool.current = toolFrom(window.location.search)
      setPopped((n) => n + 1)
      setSelection(read.selection)
      setNotes(read.notes)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [fromAddress])

  /**
   * Switch level without losing the place: same target, frame and zoom, and the same tools
   * open (each is then written for the new level). Beginner goes back to the normal view at
   * the usual size, which its words describe.
   */
  const changeLevel = (ui: UiLevel) => {
    storeLevel(ui)
    if (ui === 'expert') {
      show({ ...selection, ui }, 'replace')
      return
    }
    const wasChanged = selection.mode !== DEFAULT_SELECTION.mode || selection.fov !== DEFAULT_SELECTION.fov
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
  // Whether they are drawn on every visit of the view (not on a sum): said once, whichever visit is on screen.
  const starsOnVisits = starsData !== null && data !== null && data.frames.every((f) => f.epoch !== null && starsData.frames.some((s) => s.epoch === f.epoch))
  const hasFlags = data !== null && data.frames.every((f) => f.flags_image)

  // ---- what is drawn over the picture ------------------------------------------------------

  const grid: Grid | null = data && { ra: data.ra, dec: data.dec, sizePx: data.size_px, pixelArcsec: data.pixel_arcsec }
  const start = data ? startCentroid(data) : null
  const path = data ? measuredPath(data) : []
  const ends = data ? overallEnds(data) : null
  // An arrowhead says "it went this way", so it is drawn only for a shift large enough to be real,
  // and in Beginner only when a known object is listed at the centre (else the marker is just the brightest spot).
  const arrow = ends !== null && isRealShift(ends[0], ends[1]) && (expert || data?.target != null)

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

  // One of our sweep's candidates held at its corrected place (finds.ts): no motion was given or measured, so none is said.
  const heldFind = isHeldFind(selection)
  const givenMotion = selection.pmra !== null && selection.pmdec !== null && !heldFind ? Math.hypot(selection.pmra, selection.pmdec) / 1000 : null
  const motionKnown = givenMotion !== null || (data?.target?.pmra != null && data.target.pmdec != null)
  const saturation = data && saturationSentence(data)
  const failures = fresh && failuresSentence(fresh)

  // ---- the tool panels below the picture ---------------------------------------------------

  const shell = useRef<HTMLDivElement>(null)
  const bench = useRef<HTMLElement>(null)
  const scrollBehavior = (): ScrollBehavior => (prefersStillness() ? 'auto' : 'smooth')
  // The panel just opened, which the page then scrolls to. `n` makes pressing the same button again scroll again.
  // Opened from the keyboard, the focus goes to the panel's title, so the next Tab reaches its controls
  // (a title is not a control, so the space bar still plays).
  const [opened, setOpened] = useState<{ tool: ToolKey; n: number; focus: boolean } | null>(null)
  const openTool = (tool: ToolKey, focus = false) => {
    setOpened((was) => ({ tool, n: (was?.n ?? 0) + 1, focus }))
    setFocusTool(tool)
  }
  useEffect(() => {
    if (!opened) return
    const slot = document.getElementById(`tool-${opened.tool}`)
    slot?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
    if (opened.focus && slot) {
      const title = slot.querySelector<HTMLElement>('h2, h3') ?? slot
      if (!title.hasAttribute('tabindex')) title.setAttribute('tabindex', '-1')
      title.focus({ preventScroll: true })
    }
  }, [opened])
  /** Watch: the picture back in view, and the feature on screen. */
  const backToPicture = () => {
    setFocusTool(null)
    shell.current?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
    // The picture takes the focus, so the space bar and the arrow keys play and step again
    // (the button that was pressed goes away once the picture is in view).
    shell.current?.querySelector<HTMLElement>('.stage-surface')?.focus({ preventScroll: true })
  }
  // Whether the picture is in the window: when it is not and a panel is open, a button leads back to it.
  const [benchInView, setBenchInView] = useState(true)
  useEffect(() => {
    const el = bench.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const watch = new IntersectionObserver(([entry]) => setBenchInView(entry.intersectionRatio >= 0.2), { threshold: [0, 0.2, 0.5] })
    watch.observe(el)
    return () => watch.disconnect()
  }, [])
  /** Whether a tool's panel is open under the picture. */
  const isOpen = (tool: ToolKey): boolean => {
    switch (tool) {
      case 'spectrum':
        return spectrum !== null
      case 'brightness':
        return brightness !== null
      case 'search':
        return search !== null
      case 'distant':
        return distant !== null
      case 'smallbodies':
        return showSmallBodies && data !== null
      case 'context':
        return showContext
    }
  }
  const anyTool = spectrum !== null || brightness !== null || search !== null || distant !== null || showSmallBodies || showContext
  // The bar's current feature: the tool last opened while its panel is open (closing it, or a
  // new target closing it, makes Watch current again).
  const current: FeatureKey = focusTool && isOpen(focusTool) ? focusTool : 'watch'

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

  /**
   * What an item of the bar does on this screen: a tool opens its panel for the object on
   * screen (the same request its button in the side column used to make) and the page scrolls
   * to it; Watch brings the picture back. A panel already open for this object is only scrolled
   * to: pressing its item again never sends its request again (a first measurement takes minutes).
   */
  const openFeature = (key: 'watch' | ToolKey, how: 'keyboard' | 'pointer' = 'pointer') => {
    if (key === 'watch') {
      backToPicture()
      return
    }
    if (!ready) return
    const forTarget = (r: SpectrumRequest | null) => r !== null && r.kind === 'target' && r.ra === ready.ra && r.dec === ready.dec
    const forPatch = (q: { ra: number; dec: number; fov: number } | null) => q !== null && q.ra === ready.ra && q.dec === ready.dec && q.fov === selection.fov
    if (key === 'spectrum') {
      if (!forTarget(spectrum)) setSpectrum({ kind: 'target', ra: ready.ra, dec: ready.dec, motion: targetMotion(ready.target) })
    } else if (key === 'brightness') {
      if (!forTarget(brightness)) setBrightness({ kind: 'target', ra: ready.ra, dec: ready.dec, motion: targetMotion(ready.target) })
    } else if (key === 'search') {
      if (!forPatch(search)) {
        setSearchFound([])
        setSearch({ ra: ready.ra, dec: ready.dec, fov: selection.fov })
      }
    } else if (key === 'distant') {
      if (!forPatch(distant)) setDistant({ ra: ready.ra, dec: ready.dec, fov: selection.fov })
    } else if (key === 'smallbodies') setShowSmallBodies(true)
    else setShowContext(true)
    openTool(key, how === 'keyboard')
  }
  const closeSearch = () => {
    setSearch(null)
    setSearchFound([])
  }
  const openNow = useRef(openFeature)
  useEffect(() => {
    openNow.current = openFeature
  })

  // The address's tool, once the pictures of the view it names are ready (the tools need them):
  // on arrival, and after Back or Forward.
  const readyKey = fresh !== null && !busy ? fresh.key : null
  useEffect(() => {
    const tool = pendingTool.current
    if (!tool || readyKey === null) return
    pendingTool.current = null
    openNow.current(tool)
  }, [readyKey, popped])

  // The address says which tool is on screen (tool=<key>), in place; none while Watch is.
  // While the address's own tool waits for the pictures, it is left as it is.
  const addressTool = current === 'watch' ? null : (current as ToolKey)
  useEffect(() => {
    if (!pendingTool.current) writeTool(addressTool)
  }, [addressTool, selection])

  // The bar's links to the other screens, in the level in use.
  const links: FeatureLinks = {
    practise: withUi(trainingAddress(selection, practiceSeed), selection.ui),
    vote: withUi(WATCHLIST_ADDRESS, selection.ui),
    // The methods screen keeps the place the visitor came from, for its way back.
    tools: withUi(toolsAddress({ ra: selection.ra, dec: selection.dec, name: shownName ?? selection.name }), selection.ui),
  }

  const visits: Visit[] = data ? data.frames.map((f) => ({ src: f.image, label: frameLabel(f, data), ...visitCaption(f, data) })) : []

  // Beginner's small "i" buttons: what exactly is going on, in words computed from what is on screen (guide.ts). None in Expert.
  const infoButton = (key: InfoKey, className?: string, id?: string) =>
    !expert && (
      <InfoButton
        name={INFO_NAMES[key]}
        text={infoFor(key, data, starsData?.bright_nearby, shownName)}
        className={className}
        id={id}
        onOpen={() => {
          mark('read')
          // What is explained is on screen now: stop the film so the words and the picture stay the same.
          pausePlayer()
        }}
      />
    )

  // Beginner's sentence about the whole run (Expert's only for something that appeared or faded) and the clearness line; the notes under the table (both levels).
  const result = data ? (expert ? expertResult(data) : overallResult(data)) : null
  const seen = data && !expert ? seenLine(data) : null
  const underTable = data ? tableNotes(data, expert ? 'expert' : 'beginner') : []
  const verdict = data && expert ? expertVerdict(data) : null

  return (
    <div className="app">
      <div className="shell" ref={shell}>
        {/* Every feature, in the bar at the top. The tools wait for the first pictures. */}
        <header className="topbar">
          <h1 className="brand">SPHEREx sky-change viewer</h1>
          <FeatureBar level={selection.ui} current={current} links={links} onOpen={openFeature} ready={ready !== null} />
        </header>

        {/* Issue #6: what to look at, in one row: a name or coordinates, or a target button. What they find goes to applyTarget. */}
        <SkySearch onSelect={applyTarget}>
          {(skySearch) => (
            <nav className="targets" aria-label="Targets">
              <SearchField search={skySearch} />
              <TargetButtons search={skySearch} picked={pickedHere} shown={selection.name} />
            </nav>
          )}
        </SkySearch>

        <main className="bench" ref={bench}>
          <section className="stagecol" aria-label="The picture">
            <div className="plate-col">
              <div className={busy ? 'plate busy' : 'plate'} ref={plate}>
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
                        {(expert ? showMotion : true) && (
                          <MotionLayer
                            sizePx={grid.sizePx}
                            scale={scale}
                            start={expert && start && path.length > 1 ? toPicture(start) : null}
                            path={heldFind && !expert ? [] : path.map(toPicture)}
                            here={frame.centroid && toPicture(frame.centroid)}
                            hereMarginal={isMarginal(frame)}
                            arrow={arrow}
                            place={heldFind && !expert && frame.predicted ? toPicture(frame.predicted) : null}
                          />
                        )}
                        {expert && showGaia && (
                          <GaiaOverlay frames={gaiaFrames} current={gaiaCurrent} sizePx={data.size_px} pixelArcsec={data.pixel_arcsec} target={data.target} />
                        )}
                        {/* What the open tools mark on the picture, at both levels. */}
                        {search && searchFound.length > 0 && <SearchMarkers objects={searchFound} grid={grid} scale={scale} />}
                        {distant && distantFound.candidates.length > 0 && !distantFound.simulation && (
                          <DistantMarkers
                            candidates={distantFound.candidates}
                            grid={grid}
                            scale={scale}
                            epoch={frame.epoch}
                            simulation={distantFound.simulation}
                          />
                        )}
                        {aperture && <ApertureMark sizePx={grid.sizePx} at={aperture} radiusPx={SPECTRUM_APERTURE_ARCSEC / grid.pixelArcsec} />}
                      </>
                    )}
                  </Stage>
                ) : (
                  // Nothing to show yet: an empty plate of the same size, so nothing around it moves.
                  <div className="stage stage-empty" />
                )}
                {data && !busy && <BeforeAfter data={data} current={player.current} />}
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
                beforeAfter={pair !== null}
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
              {/* A long name ("Young star in Serpens South") is set a size smaller, so it stays on one line and the column below it does not move. */}
              {shownName && <h2 className={shownName.length > 20 ? 'object-name long-name' : 'object-name'}>{shownName}</h2>}
              {/* The sky position is a scientist's line: Beginner shows it only when it is all the name there is (a typed position). */}
              {(expert || !shownName) && (
                <p className={shownName ? 'object-where' : 'object-where object-name'}>
                  <abbr title="right ascension">RA</abbr> {`${selection.ra.toFixed(5)}°, `}
                  <abbr title="declination">Dec</abbr> {`${selection.dec >= 0 ? '+' : '-'}${Math.abs(selection.dec).toFixed(5)}°`}
                  {expert && givenMotion !== null && `; moving ${givenMotion.toFixed(2)}″ a year`}
                </p>
              )}
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

            {/* The table of every visit, with Beginner's sentence about the whole run over it, in a
                block whose height never changes. Nothing in it depends on the visit on screen: only
                the mark of that visit's row moves. While another star loads, the last one's table
                stays, dimmed. */}
            <div className={busy ? 'readout-block busy' : 'readout-block'} aria-busy={busy || undefined}>
              {data && result && (
                <>
                  <p className="result-sentence">
                    {result.sentence}
                    {infoButton('movement')}
                  </p>
                  {result.more.map((line) => (
                    <p key={line} className="result-more">
                      {line}
                    </p>
                  ))}
                </>
              )}
              {data && seen && (
                <p className="seen-line">
                  {seen}
                  {infoButton('detection')}
                </p>
              )}
              {/* Expert: the whole run against the catalogue in one line, in a scientist's units, over the table. */}
              {data && verdict && <p className="expert-verdict">{verdict}</p>}
              {data && <VisitTable data={data} current={player.current} expert={expert} disabled={busy} onShow={showVisit} follow={voice !== ''} />}
              {result?.after?.map((line) => (
                <p key={line} className="result-more result-after">
                  {line}
                </p>
              ))}
              {underTable.map((line) => (
                <p key={line} className="table-note">
                  {line}
                </p>
              ))}
              {expert && saturation && <p className="notice">{saturation}</p>}
              {/* Shown at both levels and whether or not the overlay is on: it warns about shapes in the picture itself. */}
              {starsData?.bright_note && (
                <p className="hint bright-star">
                  {expert ? starsData.bright_note : brightLine(starsData.bright_nearby)}
                  {infoButton('bright')}
                </p>
              )}
            </div>
            {/* For screen readers: the row of the visit just stepped to or chosen. Never while playing. */}
            <p className="sr-only" aria-live="polite">
              {voice}
            </p>

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
                  {/* How to read a difference or a sum; the normal view needs no note. */}
                  {data && data.mode !== 'normal' && <p className="mode-note">{modeSentence(data)}</p>}
                  {/* What is drawn on the picture: under the menus, in the same section, to save a heading's height. */}
                  <div className="chips on-picture" role="group" aria-label="On the picture">
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
                  {/* Shown only while their switch is on; the legend of the marks is in Catalogue notes. */}
                  {data && showFlags && hasFlags && (
                    <p className="readout">
                      <span className="key nodata">■</span> no data, <span className="key saturated">■</span> saturated
                      {flagsNote(data)}
                    </p>
                  )}
                  {data && showPixels && (
                    <p className="hint">
                      Each square is {data.pixel_arcsec} arcseconds across. The frames are drawn on a finer grid than
                      SPHEREx's own pixels, which are {NATIVE_PIXEL_ARCSEC} arcseconds across.
                    </p>
                  )}
                </section>

                {/* Only what does not depend on the visit: what the marks mean and the other Gaia
                    stars. The measured-against-predicted comparison of every visit is the table. */}
                <Fold title="Catalogue notes">
                  {data && showMotion && path.length > 0 && (
                    <MotionLegend
                      start={path.length > 1}
                      path={path.length > 1}
                      arrow={arrow}
                      marginal={data.frames.some(isMarginal)}
                      note={data.mode === 'difference' ? "The positions were measured in each visit's own image, not in the difference." : undefined}
                    />
                  )}
                  {/* With a single frame and a known motion there is nothing to compare, so one line says what the marks are. */}
                  {data &&
                    showGaia &&
                    (gaiaFrames.length > 1 || data.target?.pmra == null || data.target.pmdec == null ? (
                      <GaiaReadout target={data.target} gaiaError={data.gaia_error} pixelArcsec={data.pixel_arcsec} />
                    ) : (
                      <p className="readout">
                        <span className="key gaia">+</span> marks where the target's known motion puts it on the middle date
                        of this frame
                        {Math.hypot(data.target.pmra, data.target.pmdec) / 1000 >= data.pixel_arcsec
                          ? '; the arrow is one year of that motion.'
                          : '. It moves too little in a year to draw as an arrow.'}
                      </p>
                    ))}
                  {showGaia && starsData && starsOnVisits && data && <p className="readout">{fieldStarsSummary(starsData, data.pixel_arcsec)}</p>}
                  {showGaia && starsData && !starsOnVisits && (
                    <p className="hint">The other Gaia stars are drawn on single visits only, so not on a sum of all visits.</p>
                  )}
                  {showGaia && starsError && <p className="hint">The other Gaia stars could not be loaded: {starsError}.</p>}
                  {!showGaia && <p className="hint">Turn on the Gaia overlay to see the catalogue's places on the picture.</p>}
                </Fold>

                <Fold title="Visit details">
                  {data ? <VisitDetails data={data} /> : <p className="hint">No visits yet.</p>}
                </Fold>
              </>
            ) : (
              <StepGuide progress={progress} info={infoButton('steps')} />
            )}

            <footer className="credits">
              <p>
                Images: NASA/JPL-Caltech SPHEREx, from <abbr title="NASA/IPAC Infrared Science Archive">IRSA</abbr>. Stars:
                ESA Gaia DR3.
              </p>
            </footer>
          </aside>
        </main>
      </div>

      {/* The tool panels, full width under the picture, in the order they were added, at both
          levels: each is written for the level in use. Opened from the bar at the top. */}
      <div className="tool-panels">
        {spectrum && (
          <div className="tool-slot" id="tool-spectrum">
            <SpectrumPanel request={spectrum} onClose={() => setSpectrum(null)} level={selection.ui} />
          </div>
        )}
        {brightness && (
          <div className="tool-slot" id="tool-brightness">
            <BrightnessPanel request={brightness} onClose={() => setBrightness(null)} level={selection.ui} />
          </div>
        )}
        {search && (
          <div className="tool-slot" id="tool-search">
            <SearchPanel
              key={`${search.ra},${search.dec},${search.fov}`}
              query={search}
              onClose={closeSearch}
              onObjects={setSearchFound}
              onLook={lookAt}
              level={selection.ui}
            />
          </div>
        )}
        {distant && (
          <div className="tool-slot" id="tool-distant">
            <DistantPanel
              key={`${distant.ra},${distant.dec},${distant.fov}`}
              query={distant}
              onClose={() => setDistant(null)}
              onCandidates={onDistantCandidates}
              onLook={lookAt}
              level={selection.ui}
            />
          </div>
        )}
        {/* New tool panels go here: a .tool-slot with id "tool-<key>", its key and labels in features.ts, opened with openFeature('<key>'). */}
        {showSmallBodies && data && (
          <div className="tool-slot" id="tool-smallbodies">
            <SmallBodiesPanel
              query={{ ra: data.ra, dec: data.dec, fov: data.fov, detector: data.detector }}
              onClose={() => setShowSmallBodies(false)}
              level={selection.ui}
            />
          </div>
        )}
        {/* The same patch in other surveys, with its own Close beside its title like the other panels. */}
        {showContext && (
          <div className="tool-slot context-slot" id="tool-context">
            <ContextView
              ra={selection.ra}
              dec={selection.dec}
              fov={selection.fov}
              level={selection.ui}
              onClose={() => setShowContext(false)}
              target={data?.target ?? null}
              name={shownName}
            >
              {/* What the catalogues know about the object at the centre (Dev's ObjectCard), then the same patch in older surveys. */}
              <ObjectCard ra={selection.ra} dec={selection.dec} name={shownName ?? undefined} level={selection.ui} />
            </ContextView>
          </div>
        )}
      </div>

      {anyTool && !benchInView && (
        <button type="button" className="back-to-plate" onClick={backToPicture}>
          Back to the picture
        </button>
      )}

      {/* The Beginner | Expert switch, at the bottom right; the side column keeps room for it. */}
      <LevelDock
        level={selection.ui}
        onChange={changeLevel}
        onInfoOpen={() => {
          mark('read')
          pausePlayer()
        }}
      />
    </div>
  )
}

/**
 * A folded section of Expert's side column. What it holds is in the page only while it is
 * open, so a closed fold has nothing to read, count or lay out.
 */
function Fold({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <details className="fold" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>{title}</summary>
      {open && children}
    </details>
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
