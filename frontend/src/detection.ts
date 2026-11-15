// Plain-language sentences about what was and was not detected, built from the fields the
// backend gives for honesty: `detection`, the saturated-core position error, `blend`,
// `measured` and `stars_in_circle`. Every number comes from the response. Every field is
// optional, so an older cached response gives null (nothing to say) rather than an error.
import type { BlendStar, Frame } from './api'
import type { Measured, StarsInCircle } from './spectrum'
import { listVisits } from './wording'

/** A number of times the background scatter: one decimal under 10, whole above. */
export const times = (n: number) => (n < 10 ? n.toFixed(1) : n >= 1000 ? 'over 1000' : String(Math.round(n)))

/** One line on how strongly the target is detected in this frame; null when the response does not say. */
export function detectionSentence(frame: Frame): string | null {
  const sigma = frame.detection_sigma
  switch (frame.detection) {
    case 'clear':
      return sigma != null ? `Detected clearly, ${times(sigma)} times the background scatter` : 'Detected clearly'
    case 'marginal':
      return sigma != null
        ? `Marginal detection, ${times(sigma)} times the background scatter: treat with care`
        : 'Marginal detection: treat with care'
    case 'none':
      if (sigma == null) return 'Not detected in this frame'
      // Below 1 (or negative) the measured value is just noise: say that, not "-0.8 times".
      return sigma < 1
        ? 'Not detected in this frame (nothing above the background scatter; at least 3 times it is needed)'
        : `Not detected in this frame (${times(sigma)} times the background scatter; at least 3 is needed)`
    case 'saturated':
      return 'Too bright to measure here (saturated)'
    case 'unknown':
      return 'How strongly it is detected could not be worked out for this frame'
    default:
      return null
  }
}

/** True when the target is detected, but only marginally: its marker is drawn dashed. */
export const isMarginal = (frame: Frame): boolean => frame.detection === 'marginal'

const arcsec = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1))

/**
 * How good the marked position is, said only where the fit's own error would mislead: a
 * saturated core. Null otherwise.
 */
export function positionSentence(frame: Frame): string | null {
  const c = frame.centroid
  if (!c?.saturated_core || c.err_arcsec == null) return null
  return `The core is overexposed, so the position is good to about ${arcsec(c.err_arcsec)}″, not the much smaller error of the fit.`
}

/** "About a quarter", "About 40 per cent" */
function shareWords(share: number): string {
  const friendly: [number, string][] = [
    [1 / 4, 'About a quarter'],
    [1 / 3, 'About a third'],
    [1 / 2, 'About half'],
    [2 / 3, 'About two thirds'],
    [3 / 4, 'About three quarters'],
  ]
  for (const [value, words] of friendly) if (Math.abs(share - value) <= 0.04) return words
  return `About ${Math.round(share * 100)} per cent`
}

function neighbour(s: BlendStar): string {
  return `Gaia G ${s.gmag.toFixed(1)}, ${s.distance_arcsec.toFixed(1)}″ away`
}

/** One sentence per neighbouring star that shares the light in this frame; empty when none. */
export function blendSentences(frame: Frame): string[] {
  return (frame.blend ?? []).map((s) => {
    if (s.light_share == null) {
      return `A star ${s.distance_arcsec.toFixed(1)}″ away (Gaia G ${s.gmag.toFixed(1)}) is too close to separate from the target, so the position and brightness here include its light.`
    }
    if (s.light_share < 0.05) {
      return `A neighbouring star (${neighbour(s)}) supplies under 5 per cent of the light here.`
    }
    if (s.light_share >= 0.95) return `Nearly all of the light here comes from a neighbouring star (${neighbour(s)}).`
    return `${shareWords(s.light_share)} of the light here comes from a neighbouring star (${neighbour(s)}).`
  })
}

/** What the measurement follows, in the backend's own words; null when it does not say. */
export function measuredSentence(measured: Measured | undefined): string | null {
  return measured?.description?.trim() || null
}

/**
 * Which Gaia stars are inside the measuring circle and that their light is included.
 * Null when there are none; a different line when Gaia did not answer.
 */
export function circleStarsSentence(circle: StarsInCircle | undefined): string | null {
  if (!circle) return null
  if (circle.known === false) {
    return 'Gaia did not answer, so it is not known whether other stars are inside the measuring circle. Their light would be included.'
  }
  const stars = circle.stars ?? []
  if (stars.length === 0) return null
  const radius = circle.radius_arcsec != null ? ` (radius ${circle.radius_arcsec.toFixed(1)}″)` : ''
  const each = stars.map((s) => {
    const where =
      s.nearest_arcsec === s.farthest_arcsec
        ? `${s.nearest_arcsec.toFixed(1)}″ from the object`
        : `${s.nearest_arcsec.toFixed(1)}″ to ${s.farthest_arcsec.toFixed(1)}″ from the object, depending on the visit`
    return `Gaia G ${s.gmag.toFixed(1)}, ${where} (${listVisits(s.epochs)})`
  })
  const light = stars.length === 1 ? "Its light is included in these numbers and nothing is subtracted, so they add the star's light to the object's." : "Their light is included in these numbers and nothing is subtracted, so they add those stars' light to the object's."
  return `Inside the measuring circle${radius}: ${each.join('; ')}. ${light} Stars Gaia does not list, or lists fainter than G 17, are not counted.`
}
