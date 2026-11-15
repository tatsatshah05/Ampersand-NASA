// Issue #8: markers that make a one-to-two pixel motion easy to see. Drawn over the
// picture in the picture's own pixels (pixel i spans i to i+1):
//   - a ring on the position measured in the frame on screen,
//   - a fixed cross at the first measured position, with a gap so the star stays visible,
//   - a trail through every measured position, with an arrowhead at the last one.
// The cross, the dots and the arrowhead keep their size on screen at every zoom (their
// sizes are divided by `scale`). The ring is the Gaia overlay's circle (4 picture
// pixels), so the two layers draw one ring between them, but never smaller than 9
// screen pixels. Every mark has a dark edge so it shows on a white star as well as on
// black sky. Ported from the earlier viewer (public/viewer.html).
import type { Point } from '../zoom'

const RING_PICTURE_PX = 4 // the radius GaiaOverlay draws its measured circle with
const RING_MIN_SCREEN_PX = 9
const CROSS_GAP_SCREEN_PX = 9
const CROSS_ARM_SCREEN_PX = 26
const DOT_SCREEN_PX = 3
const ARROW_SCREEN_PX = 14

interface Props {
  sizePx: number
  /** Screen pixels per picture pixel. */
  scale: number
  /** The first measured position, or null when there is nothing to compare with. */
  start: Point | null
  /** Every measured position in time order. */
  path: Point[]
  /** The measured position in the frame on screen, or null when none could be measured. */
  here: Point | null
  /** The target is only marginally detected here: its ring is dashed. */
  hereMarginal?: boolean
  /** Put an arrowhead on the end of the path. Off when the shift is too small to be real. */
  arrow: boolean
  /**
   * One of our candidates' fixed place (finds.ts), marked in every visit with the same gapped cross
   * as a start, so the eye knows where to look in the visit where nothing is there yet.
   */
  place?: Point | null
}

export function MotionLayer({ sizePx, scale, start, path, here, hereMarginal, arrow, place }: Props) {
  const gap = CROSS_GAP_SCREEN_PX / scale
  const arm = CROSS_ARM_SCREEN_PX / scale

  // The arrowhead points along the whole move, first position to last, and is left out
  // when the path is too short on screen to carry one.
  let head: string | null = null
  if (arrow && path.length >= 2) {
    const a = path[0]
    const b = path[path.length - 1]
    const onScreen = Math.hypot(b.x - a.x, b.y - a.y) * scale
    if (onScreen >= 10) {
      const size = Math.min(ARROW_SCREEN_PX, onScreen * 0.7) / scale
      const angle = Math.atan2(b.y - a.y, b.x - a.x)
      const corner = (turn: number) => `${b.x - size * Math.cos(angle + turn)},${b.y - size * Math.sin(angle + turn)}`
      head = `${b.x},${b.y} ${corner(-0.4)} ${corner(0.4)}`
    }
  }

  // Drawn in this order: the cross (a fixed reference) underneath, the path over it,
  // the ring on top.
  const cross = (at: Point) =>
    `M${at.x - arm} ${at.y}H${at.x - gap}M${at.x + gap} ${at.y}H${at.x + arm}` + `M${at.x} ${at.y - arm}V${at.y - gap}M${at.x} ${at.y + gap}V${at.y + arm}`
  const marks = (
    <>
      {start && <path className="mark-line mark-start" d={cross(start)} />}
      {place && <path className="mark-line mark-start mark-place" d={cross(place)} />}
      {path.length >= 2 && (
        <>
          <polyline className="mark-line mark-measured" points={path.map((p) => `${p.x},${p.y}`).join(' ')} />
          {path.map((p, i) => (
            // The path never reorders, so a dot's place in the list identifies it.
            <circle key={i} className="mark-solid mark-measured" cx={p.x} cy={p.y} r={DOT_SCREEN_PX / scale} />
          ))}
          {head && <polygon className="mark-solid mark-measured" points={head} />}
        </>
      )}
      {here && (
        <circle
          className={`mark-line mark-measured mark-ring${hereMarginal ? ' mark-marginal' : ''}`}
          cx={here.x}
          cy={here.y}
          r={Math.max(RING_PICTURE_PX, RING_MIN_SCREEN_PX / scale)}
        />
      )}
    </>
  )

  return (
    <svg className="overlay motion-layer" viewBox={`0 0 ${sizePx} ${sizePx}`} aria-hidden="true">
      <g className="mark-edge">{marks}</g>
      <g>{marks}</g>
    </svg>
  )
}

/**
 * What the marks mean, each beside a small drawing of itself, so colour is not the only
 * cue. `note` is one more line, without a drawing.
 */
export function MotionLegend({
  start,
  path,
  arrow,
  note,
  marginal,
}: {
  start: boolean
  path: boolean
  arrow: boolean
  note?: string
  /** Some frame has only a marginal detection, so explain the dashed ring. */
  marginal?: boolean
}) {
  return (
    <ul className="legend">
      {start && (
        <li>
          <svg viewBox="0 0 22 22" aria-hidden="true">
            <path className="mark-line mark-start" d="M1 11H7M15 11H21M11 1V7M11 15V21" />
          </svg>
          where it started
        </li>
      )}
      <li>
        <svg viewBox="0 0 22 22" aria-hidden="true">
          <circle className="mark-line mark-measured" cx="11" cy="11" r="7" />
        </svg>
        where it was measured in this frame
      </li>
      {marginal && (
        <li>
          <svg viewBox="0 0 22 22" aria-hidden="true">
            <circle className="mark-line mark-measured mark-marginal" cx="11" cy="11" r="7" />
          </svg>
          a dashed ring: only a marginal detection in that frame, so treat the position with care
        </li>
      )}
      {path && (
        <li>
          <svg viewBox="0 0 34 22" aria-hidden="true">
            <path className="mark-line mark-measured" d="M4 16L18 11L28 5" />
            <circle className="mark-solid mark-measured" cx="4" cy="16" r="2.5" />
            <circle className="mark-solid mark-measured" cx="18" cy="11" r="2.5" />
            {arrow ? (
              <polygon className="mark-solid mark-measured" points="31,3 24.5,3.5 27.5,9.5" />
            ) : (
              <circle className="mark-solid mark-measured" cx="28" cy="5" r="2.5" />
            )}
          </svg>
          its measured path, visit by visit
        </li>
      )}
      {note && <li className="legend-note">{note}</li>}
    </ul>
  )
}

/** The circle a spectrum is measured in: a dashed ring of the given radius. */
export function ApertureMark({ sizePx, at, radiusPx }: { sizePx: number; at: Point; radiusPx: number }) {
  return (
    <svg className="overlay" viewBox={`0 0 ${sizePx} ${sizePx}`} aria-hidden="true">
      <circle className="mark-line mark-edge" cx={at.x} cy={at.y} r={radiusPx} />
      <circle className="mark-line mark-aperture" cx={at.x} cy={at.y} r={radiusPx} />
    </svg>
  )
}
