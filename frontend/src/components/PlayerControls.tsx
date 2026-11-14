// Issue #5: the player's controls. Play or pause, step back and forward, a scrubber,
// the speed, and a blink between the first and last frame.
// There are usually only three frames (SPHEREx comes back to a patch of sky about every
// six months), so going round and stepping to and fro matter more than a long timeline.
import { releaseFocusAfterPointer } from '../focus'
import { SPEEDS, type Playback } from '../usePlayer'

interface Props {
  /** For each frame: its full label, and a short name to print under the scrubber. */
  frames: { label: string; tick: string }[]
  /** What the short names are numbers of, printed before them ("Visit"). */
  tickTitle: string
  current: number
  playback: Playback
  speedMs: number
  onTogglePlay: () => void
  onToggleBlink: () => void
  onStep: (by: number) => void
  onShow: (index: number) => void
  onSpeed: (ms: number) => void
}

export function PlayerControls({ frames, tickTitle, current, playback, speedMs, onTogglePlay, onToggleBlink, onStep, onShow, onSpeed }: Props) {
  const count = frames.length
  const several = count > 1
  const moving = playback !== 'paused'

  return (
    <div className="player-controls" role="group" aria-label="Player">
      <div className="controls">
        <button
          type="button"
          className="icon"
          aria-label="Previous frame"
          title="Previous frame (left arrow key)"
          disabled={!several}
          onClick={(e) => {
            onStep(-1)
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path d="M3 2.5v11M13 2.5L5.5 8l7.5 5.5z" fill="currentColor" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          </svg>
        </button>
        <button
          type="button"
          className="play"
          title="Play or pause (space bar)"
          disabled={!several}
          onClick={(e) => {
            onTogglePlay()
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          {moving && several ? 'Pause' : 'Play'}
        </button>
        <button
          type="button"
          className="icon"
          aria-label="Next frame"
          title="Next frame (right arrow key)"
          disabled={!several}
          onClick={(e) => {
            onStep(1)
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path d="M13 2.5v11M3 2.5L10.5 8 3 13.5z" fill="currentColor" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          </svg>
        </button>
        <button
          type="button"
          className="toggle"
          aria-pressed={playback === 'blinking'}
          title="Flip between the first and the last frame, which shows a small shift best"
          disabled={!several}
          onClick={(e) => {
            onToggleBlink()
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          Blink first and last
        </button>
        <label className="field">
          Speed
          <select
            value={speedMs}
            disabled={!several}
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
      </div>

      {several && (
        <div className="scrubber">
          <input
            type="range"
            min={0}
            max={count - 1}
            step={1}
            value={current}
            aria-label="Frame"
            aria-valuetext={frames[current]?.label}
            onChange={(e) => onShow(Number(e.target.value))}
            onPointerUp={(e) => e.currentTarget.blur()}
          />
          {/* The frames by name, each under its place on the scrubber. The slider says the same aloud. */}
          <span className="ticks-title" aria-hidden="true">
            {tickTitle}
          </span>
          <div className="ticks" aria-hidden="true">
            {frames.map((f, i) => (
              <span key={f.label} className={i === current ? 'tick on' : 'tick'}>
                {f.tick}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
