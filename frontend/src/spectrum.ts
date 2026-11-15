// Types and the fetch for GET /api/spectrum: the brightness of one object in every
// SPHEREx exposure. Each exposure sees the object at a different wavelength, so the
// measurements together are its spectrum. Field names are the backend's.
import { FIND_EVIDENCE, findAt, findNear, inQuiet, nearFindSentence } from './finds'
import { NEIGHBOURS_LIGHT } from './lightcurve'

/** What was actually measured, as /api/spectrum and /api/lightcurve describe it. */
export interface Measured {
  what?: string
  source_id?: string | null
  gmag?: number | null
  offset_from_request_arcsec?: number | null
  epoch?: number | null
  nearest_gaia_not_followed?: {
    source_id?: string
    gmag?: number
    distance_arcsec?: number
    [key: string]: unknown
  } | null
  /** A plain-words sentence on what the measurement follows. */
  description?: string
}

/** A Gaia star inside the measuring circle in one visit. */
export interface CircleStar {
  source_id: string
  gmag: number
  distance_arcsec: number
}

/** A Gaia star inside the measuring circle over the whole run. */
export interface CircleStarOverall {
  source_id: string
  gmag: number
  nearest_arcsec: number
  farthest_arcsec: number
  epochs: number[]
}

/** The Gaia stars (G < 17) inside the measuring circle. Nothing is subtracted: their light is in the numbers. */
export interface StarsInCircle {
  radius_arcsec?: number
  g_limit?: number
  /** False when Gaia did not answer, so nothing can be said about stars in the circle. */
  known?: boolean
  by_epoch?: { epoch: number; date: string; stars: CircleStar[] }[]
  stars?: CircleStarOverall[]
  note?: string
}

/** Motion of the object, as /api/resolve returns it (mas per year, mas, Julian year). */
export interface Motion {
  pmra: number
  pmdec: number
  parallax?: number
  pm_epoch?: number
}

/** What to measure: the target of the view, or another spot picked on the image. */
export interface SpectrumRequest {
  kind: 'target' | 'spot'
  ra: number
  dec: number
  motion?: Motion
}

export interface SpectrumPoint {
  obs_id: string
  detector: number
  epoch: number
  mjd: number
  date: string
  /** "ok" when measured; otherwise why not: "saturated", "flagged", "no_data", "no_sky", "off_image". */
  status: string
  wavelength_um: number | null
  bandwidth_um: number | null
  flux_mjy: number | null
  flux_err_mjy: number | null
}

export interface SpectrumEpoch {
  epoch: number
  date_start: string
  date_end: string
  n_exposures: number
}

export interface SpectrumResponse {
  ra: number
  dec: number
  /** The object that was followed: a Gaia star, the motion given in the request, or null. */
  target?: { origin?: string; source_id?: string | null } | null
  measured?: Measured
  stars_in_circle?: StarsInCircle
  points?: SpectrumPoint[]
  epochs?: SpectrumEpoch[]
  n_exposures?: number
  status_counts?: Record<string, number>
  detector_ranges_um?: Record<string, [number, number]>
  failures?: unknown[]
  message?: string
  method?: { flux?: string; error?: string; rejection?: string }
}

/**
 * The motion to send with a spectrum of the view's target, from the `target` of the
 * /api/frames response. Only a motion that came in with the request is passed on: a
 * Gaia star is found again by the backend from the position alone.
 */
export function targetMotion(
  target: {
    origin?: string
    pmra?: number | null
    pmdec?: number | null
    parallax?: number | null
    ref_epoch?: number | null
  } | null,
): Motion | undefined {
  if (!target || target.origin !== 'request' || target.pmra == null || target.pmdec == null) return undefined
  const motion: Motion = { pmra: target.pmra, pmdec: target.pmdec }
  if (target.parallax != null) motion.parallax = target.parallax
  if (target.ref_epoch != null) motion.pm_epoch = target.ref_epoch
  return motion
}

export async function fetchSpectrum(req: SpectrumRequest, signal?: AbortSignal): Promise<SpectrumResponse> {
  const params = new URLSearchParams({ ra: String(req.ra), dec: String(req.dec) })
  if (req.motion) {
    for (const [name, value] of Object.entries(req.motion)) params.set(name, String(value))
  }
  const r = await fetch(`/api/spectrum?${params}`, { signal })
  if (r.status === 404) throw new Error('this server does not offer spectra yet.')
  if (!r.ok) {
    let detail = `the server answered ${r.status}`
    try {
      const body: unknown = await r.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') detail = body.detail
    } catch {
      // The error body was not JSON; the status code is enough.
    }
    throw new Error(detail)
  }
  return guardSpectrum(req, (await r.json()) as SpectrumResponse)
}

/**
 * The spectrum's side of lightcurve.ts's guardLightcurve: at one of our candidates (finds.ts),
 * the exposures whose measuring circle held its neighbours' light, not the candidate's, get no
 * value, and the summary says why; near a candidate, the summary says its light reaches here.
 */
export function guardSpectrum(req: { ra: number; dec: number }, data: SpectrumResponse): SpectrumResponse {
  const at = findAt(req.ra, req.dec)
  if (!at) {
    const near = findNear(req.ra, req.dec)
    return near ? { ...data, message: `${nearFindSentence(near.find, near.arcsec)} ${data.message ?? countSentence(data)}` } : data
  }
  const counts = { ...(data.status_counts ?? {}) }
  const points = (data.points ?? []).map((p) => {
    if (!inQuiet(at, p.date)) return p
    counts[p.status] = (counts[p.status] ?? 1) - 1
    counts[NEIGHBOURS_LIGHT] = (counts[NEIGHBOURS_LIGHT] ?? 0) + 1
    return { ...p, status: NEIGHBOURS_LIGHT, flux_mjy: null, flux_err_mjy: null }
  })
  const guarded = { ...data, points, status_counts: counts }
  return { ...guarded, message: `${at.circle} ${FIND_EVIDENCE} ${data.message ?? countSentence(guarded)}` }
}

/** The panel's own first sentence (SpectrumPanel's summary), for when a message goes in front of it. */
function countSentence(data: SpectrumResponse): string {
  const n = data.n_exposures ?? 0
  const ok = data.status_counts?.ok ?? 0
  return `${ok} of ${n} ${n === 1 ? 'exposure' : 'exposures'} gave a clean measurement.`
}
