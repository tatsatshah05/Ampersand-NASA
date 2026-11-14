// Types and fetch for GET /api/stars (issue #10): the Gaia DR3 stars in a view, placed on
// every frame of it. Field names are the backend's (backend/stars.py). positions[i] is the
// star's place in frames[i], in the pixel convention of `centroid` and `predicted`.
import type { SkyPixel } from './api'

export interface FieldStar {
  source_id: string
  gmag: number | null
  pmra: number | null // mas per year, eastward (includes cos dec)
  pmdec: number | null // mas per year, northward
  parallax: number | null
  is_target: boolean
  positions: SkyPixel[]
}

export interface StarsResponse {
  size_px?: number
  pixel_arcsec?: number
  frames: { epoch: number | null; mjd_mean: number; date_mean: string }[]
  stars: FieldStar[]
  n_in_field: number
  n_returned: number
  truncated: boolean
  selection?: string
  target_source_id?: string | null
  gaia_error?: string | null
  message?: string
}

export interface StarsQuery {
  ra: number
  dec: number
  fov: number
  detector: number
  motion?: { pmra: number; pmdec: number; parallax?: number | null }
}

export async function fetchStars(q: StarsQuery, signal?: AbortSignal): Promise<StarsResponse> {
  const params = new URLSearchParams({
    ra: String(q.ra),
    dec: String(q.dec),
    fov: String(q.fov),
    detector: String(q.detector),
    mode: 'normal',
  })
  if (q.motion) {
    params.set('pmra', String(q.motion.pmra))
    params.set('pmdec', String(q.motion.pmdec))
    if (q.motion.parallax != null) params.set('parallax', String(q.motion.parallax))
  }
  const r = await fetch(`/api/stars?${params}`, { signal })
  if (!r.ok) throw new Error(r.status === 404 ? 'this server does not list field stars yet' : `HTTP ${r.status}`)
  return (await r.json()) as StarsResponse
}

/** Total proper motion in arcseconds per year, or 0 when Gaia gives none. */
export function speedArcsecPerYear(s: FieldStar) {
  return s.pmra == null || s.pmdec == null ? 0 : Math.hypot(s.pmra, s.pmdec) / 1000
}

// A star gets an arrow when one year of its motion is at least half a pixel of the picture
// (1 arcsec on the 2 arcsec grid). Arrows are true to scale, so slower stars would draw as a dot.
export const MIN_ARROW_PX = 0.5

/** One line under the frame: how many stars are drawn and how many have arrows. */
export function fieldStarsSummary(data: StarsResponse, pixelArcsec: number) {
  if (data.gaia_error) return `Gaia did not answer (${data.gaia_error}), so field stars are not shown.`
  if (data.message) return data.message
  const others = data.stars.filter((s) => !s.is_target)
  const minArcsec = MIN_ARROW_PX * pixelArcsec
  const moving = others.filter((s) => speedArcsecPerYear(s) >= minArcsec).length
  const n = others.length
  let text = `${n} other Gaia ${n === 1 ? 'star' : 'stars'} in view, circled where Gaia puts ${n === 1 ? 'it' : 'them'} on this frame's date. `
  text +=
    moving === 0
      ? `None moves ${minArcsec}″ or more in a year, so none has an arrow: still stars should stay inside their circles.`
      : `${moving} ${moving === 1 ? 'moves' : 'move'} ${minArcsec}″ or more a year and ${moving === 1 ? 'has an arrow' : 'have arrows'} (one year, to scale).`
  if (data.truncated) text += ` The field has ${data.n_in_field}; the brightest ${data.n_returned} are shown.`
  return text
}
