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
  err_arcsec: number | null
  snr: number | null
  fwhm_arcsec: number
}

export interface Frame {
  epoch: number
  date_start: string
  date_end: string
  date_mean: string
  mjd_mean: number
  image: string
  // Overlay PNG for the flags toggle: blue = no data, red = saturated. Missing from frames
  // cached by an older backend.
  flags_image?: string
  n_exposures: number
  wavelength_um: [number, number] | null
  flagged_fraction: number
  saturated_pixels: number
  rejected_readings: number
  centroid: Centroid | null
  predicted: SkyPixel | null
}

export interface GaiaStar {
  source_id: string
  ra: number
  dec: number
  pmra: number // milliarcseconds per year, eastward (already includes cos dec)
  pmdec: number // milliarcseconds per year, northward
  parallax: number // milliarcseconds
  gmag: number
}

export interface FramesResponse {
  key: string
  ra: number
  dec: number
  fov: number
  detector: number
  mode: string
  size_px?: number
  pixel_arcsec?: number
  target: GaiaStar | null
  gaia_error?: string | null
  failures: unknown[]
  frames: Frame[]
  message?: string
  credit?: string
}

export interface FramesQuery {
  ra: number
  dec: number
  fov: number
  detector: number
}

export async function fetchFrames(q: FramesQuery, signal?: AbortSignal): Promise<FramesResponse> {
  const params = new URLSearchParams({
    ra: String(q.ra),
    dec: String(q.dec),
    fov: String(q.fov),
    detector: String(q.detector),
    mode: 'normal',
  })
  const r = await fetch(`/api/frames?${params}`, { signal })
  if (!r.ok) {
    let detail = `HTTP ${r.status}`
    try {
      const body: unknown = await r.json()
      if (body && typeof body === 'object' && 'detail' in body) detail += `: ${String(body.detail)}`
    } catch {
      // The error body was not JSON; the status code is enough.
    }
    throw new Error(detail)
  }
  return (await r.json()) as FramesResponse
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
