// Types and the fetch for GET /api/spectrum: the brightness of one object in every
// SPHEREx exposure. Each exposure sees the object at a different wavelength, so the
// measurements together are its spectrum. Field names are the backend's.

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
  return (await r.json()) as SpectrumResponse
}
