// Issue #10: Gaia overlay. Draws, on top of the frame image:
//   - an arrow showing which way and how far Gaia says the target moves in one year,
//   - a small "+" at the position Gaia predicts for each frame's date,
//   - a circle at the position the backend measured in the current frame.
// The readout below the image compares measured and predicted shifts since the first frame.
import { NATIVE_PIXEL_ARCSEC, skyOffsetArcsec, type Frame, type GaiaStar } from '../api'

interface OverlayProps {
  frames: Frame[]
  current: number
  sizePx: number
  pixelArcsec: number
  target: GaiaStar | null
}

// Backend pixel positions are pixel centres; in the SVG, pixel i spans i..i+1.
const c = (v: number) => v + 0.5

export function GaiaOverlay({ frames, current, sizePx, pixelArcsec, target }: OverlayProps) {
  const first = frames[0]?.predicted
  // One year of Gaia proper motion, in PNG pixels. East is left (-x) and north is up (-y).
  const arrow =
    target && target.pmra != null && target.pmdec != null && first
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
          className="measured-stroke"
          fill="none"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  )
}

function describe(east: number, north: number) {
  const ns = `${Math.abs(north).toFixed(1)}″ ${north >= 0 ? 'north' : 'south'}`
  const ew = `${Math.abs(east).toFixed(1)}″ ${east >= 0 ? 'east' : 'west'}`
  return `${ns}, ${ew}`
}

interface ReadoutProps {
  frames: Frame[]
  current: number
  target: GaiaStar | null
  gaiaError?: string | null
}

export function GaiaReadout({ frames, current, target, gaiaError }: ReadoutProps) {
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
  const who = target.source_id ? 'Gaia' : 'the motion given for this object'
  const f0 = frames[0]
  const f = frames[current]
  const header = (
    <p className="readout">
      <span className="key gaia">→</span> {target.source_id ? `Gaia DR3 ${target.source_id}` : 'The motion given for this object'}:
      moves {pmTotal.toFixed(2)}″ per year (arrow shows one year).
    </p>
  )
  if (current === 0) {
    return (
      <>
        {header}
        <p className="readout">This is the first frame. Step forward to compare the measured shift with {who}.</p>
      </>
    )
  }
  if (!f0?.centroid || !f?.centroid || !f0.predicted || !f.predicted) {
    return (
      <>
        {header}
        <p className="readout">The star could not be measured in frame 1 or this frame, so no comparison is shown.</p>
      </>
    )
  }
  const m = skyOffsetArcsec(f0.centroid, f.centroid)
  const p = skyOffsetArcsec(f0.predicted, f.predicted)
  const diff = Math.hypot(m.east - p.east, m.north - p.north)
  return (
    <>
      {header}
      <p className="readout">
        Since frame 1: <span className="key measured">○</span> measured shift {describe(m.east, m.north)}.{' '}
        <span className="key gaia">+</span> {who} predicts {describe(p.east, p.north)}.
      </p>
      <p className="readout">
        They differ by {diff.toFixed(1)}″, which is {(diff / NATIVE_PIXEL_ARCSEC).toFixed(2)} of a SPHEREx pixel.
      </p>
    </>
  )
}
