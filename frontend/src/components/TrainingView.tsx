// Practice mode: real SPHEREx frames with one made-up moving object added, so that a
// visitor can practise spotting a distant world by the way it moves between visits.
// A separate screen (address: ?train=<seed>): none of the ordinary view's panels
// appear here, and a banner says "simulation" the whole time. Nothing on it is called
// a detection or a discovery: the object is "made-up" or "planted".
import { useCallback, useEffect, useMemo, useState } from 'react'
import { LEVELS, readAddress, writeAddress, type Level, type Selection } from '../address'
import { keyBelongsToControl, releaseFocusAfterPointer } from '../focus'
import { toPicture } from '../motion'
import { skyToPixel, type Grid } from '../projection'
import {
  arcsecondsText,
  FALLBACK_NOTICE,
  hintSentence,
  judgeClick,
  MISSES_BEFORE_HINT,
  newSeed,
  realSkyAddress,
  trainingUrl,
  triesText,
  useTraining,
  type TrainingFrame,
} from '../training'
import { usePlayer } from '../usePlayer'
import { listVisits } from '../wording'
import { startBox, type ZoomBox } from '../zoom'
import { MotionLayer } from './MotionLayer'
import { PlayerControls } from './PlayerControls'
import { Stage } from './Stage'
import { LoadingCard, StatusCard } from './StatusCard'
import './TrainingView.css'

const LEVEL_LABELS: Record<Level, string> = {
  easy: 'Easy (bright)',
  medium: 'Medium',
  hard: 'Hard (faint)',
}

/** How the round stands. `round` says which round it belongs to, so a new round starts clean. */
interface Progress {
  round: string
  misses: number
  foundInTries: number | null
  revealed: boolean
  hintShown: boolean
  last: { ra: number; dec: number; distance: number } | null
}
const fresh = (round: string): Progress => ({ round, misses: 0, foundInTries: null, revealed: false, hintShown: false, last: null })

const frameLabel = (f: TrainingFrame, difference: boolean) =>
  `Visit ${f.epoch}, ${f.date_mean}${difference ? ' (minus the first visit)' : ''}`

/** All the visits at once, for the line that must not change while they play. */
const allVisitsLabel = (frames: TrainingFrame[], difference: boolean) => {
  const which = listVisits(frames.map((f) => f.epoch))
  const span = frames.length > 1 ? `, ${frames[0].date_mean} to ${frames[frames.length - 1].date_mean}` : `, ${frames[0]?.date_mean ?? ''}`
  return `${which.charAt(0).toUpperCase()}${which.slice(1)}${span}${difference ? ' (each minus the first visit)' : ''}`
}

export function TrainingView() {
  const [selection, setSelection] = useState<Selection>(() => readAddress(window.location.search).selection)
  const [attempt, setAttempt] = useState(0)
  const seed = selection.train ?? 0
  const round = `${seed}|${selection.level}`
  const [progressRaw, setProgress] = useState<Progress>(() => fresh(round))
  const progress = progressRaw.round === round ? progressRaw : fresh(round)
  const [showPixels, setShowPixels] = useState(false)
  const [zoomed, setZoomed] = useState<{ sky: string; box: ZoomBox } | null>(null)

  const url = trainingUrl(selection)
  const load = useTraining(url, attempt)
  const data = load.state === 'ready' ? load.data : null
  const player = usePlayer(data?.key ?? '', data?.frames.length ?? 0)
  const frame = data?.frames[player.current] ?? null
  const difference = selection.mode === 'difference'

  // The address holds the round, so that it can be shared; Back and Forward follow it.
  const change = useCallback((next: Selection, how: 'push' | 'replace') => {
    setSelection(next)
    writeAddress(next, how)
  }, [])
  useEffect(() => {
    const onPop = () => setSelection(readAddress(window.location.search).selection)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  useEffect(() => {
    document.title = 'Practice: find a made-up object (simulation)'
  }, [])

  const { togglePlay, step } = player
  const several = (data?.frames.length ?? 0) > 1
  useEffect(() => {
    if (!several) return
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
  }, [several, togglePlay, step])

  const grid: Grid | null = data && { ra: data.ra, dec: data.dec, sizePx: data.size_px, pixelArcsec: data.pixel_arcsec }
  const sky = data ? `${data.ra},${data.dec},${data.size_px}` : ''
  const home = data ? startBox(data.size_px, null) : null
  const box = home && (zoomed?.sky === sky ? zoomed.box : home)
  const changeBox = (fn: (box: ZoomBox) => ZoomBox) => {
    if (home) setZoomed((was) => ({ sky, box: fn(was?.sky === sky ? was.box : home) }))
  }

  const over = progress.foundInTries !== null || progress.revealed

  function pick(ra: number, dec: number) {
    if (!data || !frame || over) return
    const result = judgeClick({ ra, dec }, frame.planted, data.found_within_arcsec)
    const tries = progress.misses + 1
    player.show(player.current) // hold the frame that was clicked
    setProgress({
      ...progress,
      misses: result.found ? progress.misses : tries,
      foundInTries: result.found ? tries : null,
      last: { ra, dec, distance: result.distanceArcsec },
    })
  }

  /** A new round: another seed or level at the same position, as a new history entry. */
  function startRound(next: Partial<Selection>) {
    setZoomed(null)
    change({ ...selection, ...next }, 'push')
  }

  const rings = useMemo(() => data?.planted.positions.map(toPicture) ?? [], [data])
  const lastClick = progress.last && grid ? skyToPixel(progress.last.ra, progress.last.dec, grid) : null
  const banner = data?.notice ?? FALLBACK_NOTICE

  return (
    <>
      {/* Always on screen: sticky, with no way to close it. The backend's own notice text. */}
      <div className="sim-banner" role="note" aria-label="This is a simulation">
        <strong>SIMULATION.</strong> {banner}
      </div>
      <main className="training">
        <header>
          <h1>Practice: find a made-up object</h1>
          <p className="tagline">
            Real SPHEREx images of this patch of sky, with one made-up object added to them. Find it by the way it moves
            between visits.
          </p>
          <p className="how-to-look">
            <strong>How to look.</strong> A real distant planet would not sit still like the stars. It swings back and
            forth between visits, because the Earth moves round the Sun while it watches. So look for the dot that is in
            a different place in each frame, while everything around it stays put. Play the frames or blink the first and
            last, then click where you think it is in the frame on screen.
          </p>
          <div className="selectors training-controls" role="group" aria-label="Practice options">
            <label className="field">
              Difficulty
              <select
                value={selection.level}
                onChange={(e) => {
                  startRound({ level: e.target.value as Level })
                  releaseFocusAfterPointer(e.currentTarget)
                }}
              >
                {LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {LEVEL_LABELS[l]}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Frames
              <select
                value={difference ? 'difference' : 'normal'}
                onChange={(e) => {
                  setZoomed(null)
                  change({ ...selection, mode: e.target.value === 'difference' ? 'difference' : 'normal' }, 'replace')
                  releaseFocusAfterPointer(e.currentTarget)
                }}
              >
                <option value="normal">Ordinary frames</option>
                <option value="difference">Difference frames</option>
              </select>
            </label>
            <button type="button" onClick={() => startRound({ train: newSeed() })}>
              New round
            </button>
            <a className="button-link" href={realSkyAddress(selection)}>
              Back to the real sky
            </a>
          </div>
          <p className="mode-note">
            {difference
              ? 'Difference frames: each later visit minus the first, so the stars cancel out and anything that moved stands out. The made-up object shows as a bright dot, with a dark ghost where it was in the first visit.'
              : 'Ordinary frames: one picture per SPHEREx visit. Try the difference frames if you cannot see it: that is where a mover stands out.'}
          </p>
          {data && data.failures.length > 0 && (
            <p className="notice">Some exposures could not be fetched, so these frames may have less data.</p>
          )}
        </header>

        <div className="viewer">
          {load.state === 'loading' && <LoadingCard key={url} />}
          {load.state === 'error' && (
            <StatusCard title="This practice round could not be made" tone="error">
              <p>{load.message}</p>
              <div className="status-actions">
                <button type="button" onClick={() => setAttempt(attempt + 1)}>
                  Try again
                </button>
                <button type="button" onClick={() => startRound({ train: newSeed() })}>
                  New round
                </button>
                <a className="button-link" href={realSkyAddress(selection)}>
                  Back to the real sky
                </a>
              </div>
            </StatusCard>
          )}
          {data && grid && frame && box && (
            <>
              <Stage
                grid={grid}
                images={data.frames.map((f) => ({ key: f.image, src: f.image }))}
                current={player.current}
                alt={`${frameLabel(frame, difference)}. A practice picture with a made-up object in it.`}
                box={box}
                onBoxChange={changeBox}
                onReset={() => setZoomed(null)}
                showPixels={showPixels}
                onPick={pick}
                describedBy="stage-help"
              >
                {(scale) => (
                  <>
                    {over && (
                      <MotionLayer sizePx={grid.sizePx} scale={scale} start={null} path={rings} here={toPicture(frame.planted)} arrow />
                    )}
                    {lastClick && !over && (
                      <svg className="overlay" viewBox={`0 0 ${grid.sizePx} ${grid.sizePx}`} aria-hidden="true">
                        <g className="your-click" transform={`translate(${lastClick.x} ${lastClick.y})`}>
                          <path d={`M${-6 / scale} 0H${6 / scale}M0 ${-6 / scale}V${6 / scale}`} strokeWidth={2 / scale} />
                        </g>
                      </svg>
                    )}
                  </>
                )}
              </Stage>
              <p id="stage-help" className="hint">
                Click where you think the made-up object is. Scroll or pinch to zoom, drag to move. The space bar plays
                and pauses and the arrow keys step. North is up and east is left. The word SIMULATION in the corner of
                each picture is part of the picture.
              </p>
            </>
          )}
        </div>

        {data && frame && (
          <section className="now training-now" aria-label="The frame on screen and the game">
            {/* Every visit, said once: the words hold still while the visits play, and the ticks
                under the slider mark the one on screen. A screen reader hears the visit on screen
                only when paused (that is, after stepping or choosing one), never while playing. */}
            <p className="frame-label">{allVisitsLabel(data.frames, difference)}</p>
            <p className="sr-only" aria-live="polite">
              {player.playback === 'paused' ? frameLabel(frame, difference) : ''}
            </p>

            <PlayerControls
              frames={data.frames.map((f) => ({ label: frameLabel(f, difference), tick: `${f.epoch}` }))}
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
              <button
                type="button"
                className="toggle"
                aria-pressed={showPixels}
                onClick={(e) => {
                  setShowPixels(!showPixels)
                  releaseFocusAfterPointer(e.currentTarget)
                }}
              >
                Show pixels
              </button>
              <button
                type="button"
                disabled={over}
                onClick={(e) => {
                  setProgress({ ...progress, revealed: true })
                  releaseFocusAfterPointer(e.currentTarget)
                }}
              >
                Show me
              </button>
              {progress.misses >= MISSES_BEFORE_HINT && !over && !progress.hintShown && (
                <button type="button" onClick={() => setProgress({ ...progress, hintShown: true })}>
                  Give me a hint
                </button>
              )}
            </div>

            <div className="game-result" aria-live="polite">
              {progress.foundInTries !== null && (
                <p className="found">
                  Found it! You spotted the made-up object {triesText(progress.foundInTries)}. The rings show where it was in
                  each visit.
                </p>
              )}
              {progress.foundInTries === null && progress.revealed && (
                <p className="revealed">Here it is. The rings, joined by a line, show where the made-up object was in each visit.</p>
              )}
              {!over && progress.last && (
                <p className="missed">
                  Not quite: your click was {arcsecondsText(progress.last.distance)} from the made-up object in this frame. It
                  counts when you are within {arcsecondsText(data.found_within_arcsec)}. Try again.
                </p>
              )}
              {!over && !progress.last && <p className="hint">No clicks yet.</p>}
              {!over && progress.hintShown && <p className="hintline">{hintSentence(data.frames[0].planted, data.size_px)}</p>}
              {over && <p className="explanation">{data.planted.explanation}</p>}
            </div>
          </section>
        )}

        <footer>
          <p>
            Everything on this screen is practice. The pictures are real SPHEREx data with one made-up object added, and
            the object is not real.
          </p>
          Images: NASA/JPL-Caltech SPHEREx, served by NASA/IPAC Infrared Science Archive (IRSA).
        </footer>
      </main>
    </>
  )
}
