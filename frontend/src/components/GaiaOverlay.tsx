// Issue #10: Gaia overlay. Draws, on top of the frame image:
//   - an arrow showing which way and how far Gaia says the target moves in one year,
//   - a small "+" at the position Gaia predicts for each frame's date,
//   - a circle at the position the backend measured in the current frame.
// The readout in the Catalogue notes says what those marks are; the table of visits compares
// measured and predicted shifts for every visit.
import { NATIVE_PIXEL_ARCSEC, type Frame, type GaiaStar } from '../api'

interface OverlayProps {
  frames: Frame[]
  current: number
  sizePx: number
  pixelArcsec: number
  target: GaiaStar | null
}

// Backend pixel positions are pixel centres; in the SVG, pixel i spans i..i+1.
const c = (v: number) => v + 0.5

// Below one image pixel of motion in a year the arrow would be an arrowhead with no shaft,
// which reads as visible motion, so it is not drawn.
const MIN_ARROW_IMAGE_PX = 1
const yearMotionPx = (t: GaiaStar, pixelArcsec: number) =>
  t.pmra == null || t.pmdec == null ? 0 : Math.hypot(t.pmra, t.pmdec) / 1000 / pixelArcsec

export function GaiaOverlay({ frames, current, sizePx, pixelArcsec, target }: OverlayProps) {
  const first = frames[0]?.predicted
  // One year of Gaia proper motion, in PNG pixels. East is left (-x) and north is up (-y).
  const arrow =
    target && target.pmra != null && target.pmdec != null && first && yearMotionPx(target, pixelArcsec) >= MIN_ARROW_IMAGE_PX
      ? {
          x1: c(first.x),
          y1: c(first.y),
          x2: c(first.x) - target.pmra / 1000 / pixelArcsec,
          y2: c(first.y) - target.pmdec / 1000 / pixelArcsec,
        }
      : null
  const cur = frames[current]

  return (
    <svg
      className="overlay"
      viewBox={`0 0 ${sizePx} ${sizePx}`}
      role="img"
      aria-label="Gaia positions and measured positions of the target"
    >
      <defs>
        <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" className="gaia-fill" />
        </marker>
      </defs>
      {arrow && (
        <line {...arrow} className="gaia-stroke" strokeWidth={2} vectorEffect="non-scaling-stroke" markerEnd="url(#arrowhead)" />
      )}
      {frames.map((f) =>
        f.predicted ? (
          <g key={`p${f.epoch}`} className="gaia-stroke" strokeWidth={1.5} vectorEffect="non-scaling-stroke">
            <line x1={c(f.predicted.x) - 1.5} x2={c(f.predicted.x) + 1.5} y1={c(f.predicted.y)} y2={c(f.predicted.y)} vectorEffect="non-scaling-stroke" />
            <line x1={c(f.predicted.x)} x2={c(f.predicted.x)} y1={c(f.predicted.y) - 1.5} y2={c(f.predicted.y) + 1.5} vectorEffect="non-scaling-stroke" />
          </g>
        ) : null,
      )}
      {cur?.centroid && (
        <circle
          cx={c(cur.centroid.x)}
          cy={c(cur.centroid.y)}
          r={4}
          className={cur.detection === 'marginal' ? 'measured-stroke mark-marginal' : 'measured-stroke'}
          fill="none"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  )
}

interface ReadoutProps {
  target: GaiaStar | null
  gaiaError?: string | null
  pixelArcsec?: number // the picture's pixel size; the SPHEREx pixel when not given
}

/**
 * What the Gaia marks on the picture are: whose motion and how fast, or why there is none.
 * The same for every visit (the measured-against-predicted comparison of each visit is in
 * the table of visits), so it never changes while the visits play.
 */
export function GaiaReadout({ target, gaiaError, pixelArcsec }: ReadoutProps) {
  if (!target) {
    return (
      <p className="readout">
        {gaiaError
          ? `Gaia catalogue did not answer (${gaiaError}), so there is no prediction to compare with.`
          : 'No Gaia star near the centre, so there is no predicted motion to compare with.'}
      </p>
    )
  }
  if (target.pmra == null || target.pmdec == null) {
    return (
      <p className="readout">
        Gaia DR3 {target.source_id} is near the centre, but Gaia lists no motion for it, so there is no predicted
        motion to compare with.
      </p>
    )
  }
  const pmTotal = Math.hypot(target.pmra, target.pmdec) / 1000
  // A target described by the request (a motion from /api/resolve) has no Gaia identifier.
  return (
    <>
      <p className="readout">
        <span className="key gaia">→</span> {target.source_id ? `Gaia DR3 ${target.source_id}` : 'The motion given for this object'}:
        moves {pmTotal.toFixed(2)}″ per year{' '}
        {yearMotionPx(target, pixelArcsec ?? NATIVE_PIXEL_ARCSEC) < MIN_ARROW_IMAGE_PX
          ? '(too small to draw as an arrow).'
          : '(arrow shows one year).'}
      </p>
      <p className="readout">
        <span className="key gaia">+</span> marks where that motion puts it on each visit's middle date; the table of
        visits compares those places with the measured ones.
      </p>
    </>
  )
}
