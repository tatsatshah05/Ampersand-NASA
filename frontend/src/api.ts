// Types for the backend's GET /api/frames response, copied from what the real server returns
// (see backend/pipeline.py). Pixel x, y are 0-based pixel centres, counted from the top-left
// of the PNG. In the PNG, north is up and east is left.

export interface SkyPixel {
  ra: number
  dec: number
  x: number
  y: number
}

export interface Centroid extends SkyPixel {
  /** The position's uncertainty. When `saturated_core` is true it is 1 or 2 arcseconds, not the fit's own error. */
  err_arcsec: number | null
  /** The fit's own error, which is far too small when the core is saturated. */
  err_arcsec_fit?: number | null
  /** The bright core is overexposed, so the fitted position is only about as good as err_arcsec says. */
  saturated_core?: boolean
  /** True when a Gaia star close by shares the light, so the marker is pulled toward it. Null when not looked for. */
  blended?: boolean | null
  /** Kept by the backend for compatibility; it is not how strongly the target is detected. */
  snr: number | null
  fwhm_arcsec: number
}

/** What the fit found near the predicted place when it is too far away to be the target. */
export interface NearestSource extends SkyPixel {
  offset_arcsec?: { east: number; north: number; total: number } | null
  detection_sigma?: number | null
  detection?: Detection | null
}

/** How strongly the target is detected in one frame. "unknown": too few empty places to measure the noise. */
export type Detection = 'clear' | 'marginal' | 'none' | 'saturated' | 'unknown'

/** A Gaia star close enough to the target to share its light in one frame. */
export interface BlendStar {
  source_id: string
  gmag: number
  distance_arcsec: number
  east_arcsec?: number
  north_arcsec?: number
  flux_mjy?: number | null
  /** Its part of the light fitted at the target and the blended stars together (0 to 1); null when too close to separate. */
  light_share: number | null
}

/** normal: one picture per visit. difference: each visit minus a reference. sum: every visit in one picture. */
export type Mode = 'normal' | 'difference' | 'sum'
/** Difference mode: subtract the first visit, or the average of all visits. */
export type Reference = 'first' | 'mean'
/** Sum mode: line the exposures up on the sky, or on the target as it moves. */
export type Track = 'sky' | 'target'

export interface Frame {
  /** Visit number, counted over all six detectors. Null in sum mode: that one frame holds every visit. */
  epoch: number | null
  date_start: string
  date_end: string
  date_mean: string
  mjd_mean: number
  image: string
  /** Normal and sum modes: an overlay PNG, blue where there is no data and red where saturated. */
  flags_image?: string
  n_exposures: number
  /** Null when no exposure recorded a wavelength at the centre of the request. */
  wavelength_um: [number, number] | null
  flagged_fraction: number
  saturated_pixels: number
  /** In how many of this frame's exposures the target's core is saturated for measuring brightness. */
  photometry_saturated_exposures?: number
  rejected_readings: number
  /** Measured position of the source nearest the target; null when nothing could be measured. */
  centroid: Centroid | null
  /** Why `centroid` is null, in the backend's own words; null when there is a centroid. */
  centroid_reason?: string | null
  /** When the target is not found: the source the fit found instead, if anything. */
  nearest_source?: NearestSource | null
  /** Times the background scatter that the target is detected at its predicted position; null when not measured. */
  detection_sigma?: number | null
  detection?: Detection | null
  detection_measure?: Record<string, unknown> | null
  /** Gaia stars close enough to share the target's light in this frame. */
  blend?: BlendStar[]
  /** Where the target should be on this frame's mean date; null when no target is known. */
  predicted: SkyPixel | null
  /** Sum mode only: the visits that were added together. */
  epochs_combined?: number[]
  /** Difference mode only: the visit that was subtracted, or null when the average of all visits was. */
  reference_epoch?: number | null
  /** Difference mode only: the share of pixels present in both pictures. */
  difference_valid_fraction?: number
}

/** The details of the subtracted first visit in difference mode: a frame without a picture. */
export type ReferenceFrame = Omit<Frame, 'image'>

/**
 * The object whose expected position is drawn. Either the Gaia star nearest the centre
 * ("gaia_nearest"), or the object at the centre with the motion the request gave
 * ("request"), which has no Gaia identifier and no magnitude. Gaia lists some stars
 * without a motion or parallax, so those can be null too.
 */
export interface Target {
  origin: 'gaia_nearest' | 'request'
  /** Julian year at which the object is at (ra, dec). */
  ref_epoch: number
  source_id: string | null
  ra: number
  dec: number
  pmra: number | null // milliarcseconds per year, eastward (already includes cos dec)
  pmdec: number | null // milliarcseconds per year, northward
  parallax: number | null // milliarcseconds
  gmag: number | null
  /**
   * Set by the page, never by the server: 'Gaia DR3' when the motion of a `request` target is the
   * one /api/resolve took from Gaia DR3 (the address's src=gaia). The server then knows no source_id.
   */
  motion_from?: 'Gaia DR3' | null
}

/** The earlier name of Target, still used by the Gaia overlay. */
export type GaiaStar = Target

export interface Stretch {
  /** "asinh", or "asinh-symmetric" for difference pictures (mid-grey is no change). */
  kind: string
  vmin: number
  vmax: number
  soft: number
  unit: string
}

/**
 * What /api/frames answers. When the archive has nothing for the position or detector,
 * only `key`, `frames` (empty), `message` and sometimes `failures` are present.
 */
export interface FramesResponse {
  key: string
  frames: Frame[]
  /** Why there are no frames. */
  message?: string
  /** Exposures that could not be downloaded; the frames were built without them. */
  failures?: string[]
  ra?: number
  dec?: number
  fov?: number
  detector?: number
  mode?: Mode
  size_px?: number
  pixel_arcsec?: number
  target?: Target | null
  /** Set when the Gaia catalogue did not answer, so no target could be looked up. */
  gaia_error?: string | null
  exposures_total_all_detectors?: number
  credit?: string
  /** What `detection` means, in the backend's words. */
  detection_note?: string
  /** What the position uncertainty means when the core is saturated. */
  error_note?: string
  /** What `blend` means. */
  blend_note?: string
  /** Null in a difference view that has no frames. */
  stretch?: Stretch | null
  /** Difference mode, and sum mode following the target: how to read the picture. */
  note?: string
  /** Difference mode: what was subtracted. */
  reference?: Reference
  reference_description?: string
  /** Difference mode against the first visit: that visit's own details. */
  reference_frame?: ReferenceFrame
  /** Sum mode: how the exposures were combined and lined up. */
  combine?: string
  registration?: 'sky' | 'target_motion'
}

/** A response with pictures in it. These fields are then always present. */
export interface FramesReady extends FramesResponse {
  ra: number
  dec: number
  fov: number
  detector: number
  mode: Mode
  size_px: number
  pixel_arcsec: number
  target: Target | null
}

export function hasFrames(r: FramesResponse): r is FramesReady {
  return (
    r.frames.length > 0 &&
    typeof r.ra === 'number' &&
    typeof r.dec === 'number' &&
    typeof r.fov === 'number' &&
    typeof r.detector === 'number' &&
    typeof r.mode === 'string' &&
    typeof r.size_px === 'number' &&
    typeof r.pixel_arcsec === 'number' &&
    r.target !== undefined
  )
}

export interface FramesQuery {
  ra: number
  dec: number
  fov: number
  detector: number
  mode: Mode
  /** Difference mode only. */
  reference?: Reference
  /** Sum mode only. */
  track?: Track
  /** The object's known motion, as /api/resolve returns it: both or neither. */
  pmra?: number
  pmdec?: number
  parallax?: number
}

/** The address of a frames request. Also serves as the request's identity. */
export function framesUrl(q: FramesQuery): string {
  const params = new URLSearchParams({
    ra: String(q.ra),
    dec: String(q.dec),
    fov: String(q.fov),
    detector: String(q.detector),
    mode: q.mode,
  })
  if (q.mode === 'difference' && q.reference) params.set('reference', q.reference)
  if (q.mode === 'sum' && q.track) params.set('track', q.track)
  if (q.pmra !== undefined && q.pmdec !== undefined) {
    params.set('pmra', String(q.pmra))
    params.set('pmdec', String(q.pmdec))
    if (q.parallax !== undefined) params.set('parallax', String(q.parallax))
  }
  return `/api/frames?${params}`
}

// How the request's parameters are called on the page, for error messages.
const PARAMETER_NAMES: Record<string, string> = {
  ra: 'the right ascension (ra)',
  dec: 'the declination (dec)',
  fov: 'the field of view (fov)',
  detector: 'the detector',
  mode: 'the mode',
  reference: 'what to compare with (reference)',
  track: 'what to line up on (track)',
  pmra: 'the motion (pmra)',
  pmdec: 'the motion (pmdec)',
  parallax: 'the parallax',
  pm_epoch: 'the date of the position (pm_epoch)',
}

/** FastAPI's list of rejected parameters ({loc, msg, input}) as one plain sentence. */
function rejectedParameters(detail: unknown[]): string {
  const parts = detail.map((item) => {
    if (!item || typeof item !== 'object') return String(item)
    const { loc, msg, input } = item as { loc?: unknown; msg?: unknown; input?: unknown }
    const field = Array.isArray(loc) && loc.length ? String(loc[loc.length - 1]) : ''
    const name = PARAMETER_NAMES[field] ?? (field || 'a value')
    let problem = typeof msg === 'string' && msg ? msg : 'was not accepted'
    if (problem === 'Field required') problem = 'is missing'
    else problem = problem.replace(/^Input /, '')
    problem = problem.charAt(0).toLowerCase() + problem.slice(1)
    const given = typeof input === 'string' || typeof input === 'number' ? ` (it was ${String(input).slice(0, 40)})` : ''
    return `${name} ${problem}${given}`
  })
  return parts.join('; ')
}

/** Why a request failed, in words a visitor can act on. */
function explainFailure(status: number, body: unknown): string {
  const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : undefined
  if (Array.isArray(detail) && detail.length) {
    return `The server did not accept this request: ${rejectedParameters(detail)}.`
  }
  const text = typeof detail === 'string' ? detail.trim() : ''
  if (status === 400 && text.startsWith('track=target')) {
    return 'Following the target needs to know how it moves, and no motion is known for this position. Choose "the sky" under "Lined up on", or look the object up by name so that its motion comes with it.'
  }
  if (text) {
    // 502 is the backend saying that NASA's archive did not answer it.
    const again = status === 502 ? ' This is usually temporary: try again in a minute.' : ''
    return `${/[.!?]$/.test(text) ? text : `${text}.`}${again}`
  }
  if (status === 404) return 'This server does not offer the frames (it answered "not found" for /api/frames).'
  if (status === 502 || status === 503 || status === 504) {
    return `The server could not be reached (error ${status}). Check that it is running, then try again.`
  }
  if (status >= 500) return `The server ran into a problem while making these frames (error ${status}). Try again.`
  return `The server answered with error ${status}.`
}

/**
 * Ask the backend for the frames. Rejects with an Error whose message is a plain
 * sentence for the visitor. A new position, detector or field of view takes about a
 * minute, so there is no time limit here; pass a signal to give up early.
 */
export async function fetchFrames(url: string, signal?: AbortSignal): Promise<FramesResponse> {
  let r: Response
  try {
    r = await fetch(url, { signal })
  } catch (e) {
    if (signal?.aborted) throw e
    throw new Error('The server could not be reached. Check your connection and that the server is running, then try again.', {
      cause: e,
    })
  }
  let body: unknown
  try {
    body = await r.json()
  } catch (e) {
    if (signal?.aborted) throw e
    body = undefined // not JSON: the status code has to do
  }
  if (!r.ok) throw new Error(explainFailure(r.status, body))
  if (!body || typeof body !== 'object' || !Array.isArray((body as { frames?: unknown }).frames)) {
    throw new Error('The server answered, but not with frames. It may be the wrong server, or still starting up.')
  }
  return body as FramesResponse
}

/** Offset on the sky from a to b in arcseconds, as (east, north). */
export function skyOffsetArcsec(a: { ra: number; dec: number }, b: { ra: number; dec: number }) {
  let dra = b.ra - a.ra
  if (dra > 180) dra -= 360 // positions either side of RA 0
  if (dra < -180) dra += 360
  const cosDec = Math.cos((((a.dec + b.dec) / 2) * Math.PI) / 180)
  return { east: dra * cosDec * 3600, north: (b.dec - a.dec) * 3600 }
}

/** Native SPHEREx pixel size, for saying how big an offset is in detector terms. */
export const NATIVE_PIXEL_ARCSEC = 6.15
