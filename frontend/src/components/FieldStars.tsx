// Issue #10: every Gaia DR3 star in the view, drawn on the frame. A small circle sits at
// each star's catalogue position for the date of the frame on screen, so a star that does
// not move stays inside its circle while the frames play, and a fast one steps along with
// it. Stars that move at least half a picture pixel in a year also get an arrow showing
// one year of their motion, true to scale; most stars move far less and get none.
// The view's target is left to GaiaOverlay, which already draws its arrow and positions.
import { MIN_ARROW_PX, speedArcsecPerYear, type FieldStar, type StarsResponse } from '../stars'

interface Props {
  data: StarsResponse
  current: number
  sizePx: number
  pixelArcsec: number
}

// Backend pixel positions are pixel centres; in the SVG, pixel i spans i..i+1.
const c = (v: number) => v + 0.5

function title(s: FieldStar) {
  const g = s.gmag == null ? '' : `, G = ${s.gmag.toFixed(1)}`
  const motion =
    s.pmra == null || s.pmdec == null
      ? 'no motion in Gaia'
      : `moves ${speedArcsecPerYear(s).toFixed(3)}″ per year (${s.pmra.toFixed(1)}, ${s.pmdec.toFixed(1)} mas/yr east, north)`
  return `Gaia DR3 ${s.source_id}${g}: ${motion}`
}

export function FieldStars({ data, current, sizePx, pixelArcsec }: Props) {
  const others = data.stars.filter((s) => !s.is_target && s.positions[current])
  return (
    <svg className="overlay field-stars" viewBox={`0 0 ${sizePx} ${sizePx}`} role="img" aria-label="Gaia stars in the view">
      <defs>
        <marker id="field-arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" className="gaia-fill" />
        </marker>
      </defs>
      {others.map((s) => {
        const p = s.positions[current]
        // One year of motion in PNG pixels: east is left (-x), north is up (-y).
        const dx = s.pmra == null ? 0 : -s.pmra / 1000 / pixelArcsec
        const dy = s.pmdec == null ? 0 : -s.pmdec / 1000 / pixelArcsec
        const arrow = Math.hypot(dx, dy) >= MIN_ARROW_PX
        return (
          <g key={s.source_id}>
            <title>{title(s)}</title>
            <circle
              cx={c(p.x)}
              cy={c(p.y)}
              r={3}
              className="field-star"
              vectorEffect="non-scaling-stroke"
            />
            {arrow && (
              <line
                x1={c(p.x)}
                y1={c(p.y)}
                x2={c(p.x) + dx}
                y2={c(p.y) + dy}
                className="gaia-stroke"
                strokeWidth={1.5}
                vectorEffect="non-scaling-stroke"
                markerEnd="url(#field-arrowhead)"
              />
            )}
          </g>
        )
      })}
    </svg>
  )
}
