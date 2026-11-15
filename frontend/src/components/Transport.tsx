// Under the picture: the transport bar (play, blink, step, speed) and the strip of visits,
// one small picture per visit, which is also how to jump to one. Like the plates in a
// blink comparator's rack. Both keep their size whatever is loaded, so nothing around
// them moves; while a view loads they stay in place with their buttons switched off.
// (The practice screen keeps the older PlayerControls, with its slider.)
import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { releaseFocusAfterPointer } from '../focus'
import { SPEEDS, type Playback } from '../usePlayer'

interface TransportProps {
  /** More than one frame: playing, blinking and stepping mean something. */
  several: boolean
  /** A view is loading: everything is shown but nothing can be pressed. */
  disabled: boolean
  playback: Playback
  speedMs: number
  onTogglePlay: () => void
  onToggleBlink: () => void
  onStep: (by: number) => void
  onSpeed: (ms: number) => void
  /** A small button at the end of the row (Beginner's "i"). */
  info?: ReactNode
  /** Blink flips between a before-and-after pair rather than the first and the last frame (one of our candidates). */
  beforeAfter?: boolean
}

export function Transport({ several, disabled, playback, speedMs, onTogglePlay, onToggleBlink, onStep, onSpeed, info, beforeAfter = false }: TransportProps) {
  const off = disabled || !several
  const moving = playback !== 'paused' && several
  return (
    <div className="transport" role="group" aria-label="Player">
      <button
        type="button"
        className="play-button"
        title="Play or pause (space bar)"
        disabled={off}
        onClick={(e) => {
          onTogglePlay()
          releaseFocusAfterPointer(e.currentTarget)
        }}
      >
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
          {moving ? <path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor" /> : <path d="M4 2.2v11.6L13.5 8z" fill="currentColor" />}
        </svg>
        {moving ? 'Pause' : 'Play'}
      </button>
      <button
        type="button"
        className="toggle blink-button"
        aria-pressed={playback === 'blinking'}
        title={
          beforeAfter
            ? 'Flip between the picture where nothing is seen at this place and the first one where it clearly is'
            : 'Flip between the first and the last frame, which shows a small shift best'
        }
        disabled={off}
        onClick={(e) => {
          onToggleBlink()
          releaseFocusAfterPointer(e.currentTarget)
        }}
      >
        {beforeAfter ? 'Blink before and after' : 'Blink first and last'}
      </button>
      <span className="transport-steps">
        <button
          type="button"
          className="icon-button"
          aria-label="Previous frame"
          title="Previous frame (left arrow key)"
          disabled={off}
          onClick={(e) => {
            onStep(-1)
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path d="M3.5 2.5v11M12.5 2.5L5.5 8l7 5.5z" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
        </button>
        <button
          type="button"
          className="icon-button"
          aria-label="Next frame"
          title="Next frame (right arrow key)"
          disabled={off}
          onClick={(e) => {
            onStep(1)
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path d="M12.5 2.5v11M3.5 2.5L10.5 8l-7 5.5z" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
        </button>
      </span>
      <label className="transport-speed">
        <span className="transport-speed-word">Speed</span>
        <select
          aria-label="Speed"
          value={speedMs}
          disabled={off}
          onChange={(e) => {
            onSpeed(Number(e.target.value))
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          {SPEEDS.map((s) => (
            <option key={s.ms} value={s.ms}>
              {s.label}
            </option>
          ))}
        </select>
      </label>
      {info}
    </div>
  )
}

export interface Visit {
  /** The frame's picture: the same one the plate shows, small. */
  src: string
  /** "Visit 2", or "All visits" for a sum. */
  name: string
  /** When, in short ("19 Jun 2025"). */
  when: string
  /** The frame's full label, as a tooltip. */
  label: string
}

interface StripProps {
  visits: Visit[]
  current: number
  disabled: boolean
  onShow: (index: number) => void
}

/** One button per visit, with its picture; the one on the plate is marked. Scrolls sideways when there are many. */
export function VisitStrip({ visits, current, disabled, onShow }: StripProps) {
  const strip = useRef<HTMLDivElement>(null)

  // Keep the visit on screen in view inside the strip, without scrolling the page. (The
  // strip is positioned, so its buttons' offsetLeft is measured from it.)
  useLayoutEffect(() => {
    const box = strip.current
    const on = box?.children[current] as HTMLElement | undefined
    if (!box || !on) return
    const left = on.offsetLeft
    if (left < box.scrollLeft) box.scrollLeft = left
    else if (left + on.offsetWidth > box.scrollLeft + box.clientWidth) box.scrollLeft = left + on.offsetWidth - box.clientWidth
  }, [current, visits.length])

  return (
    <div className="visit-strip" role="group" aria-label="Visits" ref={strip}>
      {visits.map((v, i) => (
        <button
          key={`${i} ${v.src}`}
          type="button"
          className="visit"
          aria-current={i === current ? 'true' : undefined}
          title={v.label}
          disabled={disabled}
          onClick={(e) => {
            onShow(i)
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          <img src={v.src} alt="" draggable={false} />
          <span className="visit-text">
            <span className="visit-name">{v.name}</span>
            <span className="visit-when">{v.when}</span>
          </span>
        </button>
      ))}
    </div>
  )
}
