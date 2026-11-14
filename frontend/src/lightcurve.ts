// Types, fetch and summary for GET /api/lightcurve (issue #9): the brightness of one object
// in every SPHEREx exposure, grouped into wavelength bins. Field names are the backend's
// (backend/photometry.py). Only points in the same bin can be compared over time: another
// bin is another colour of light.
import type { Motion, SpectrumRequest } from './spectrum'

export interface LightcurvePoint {
  obs_id: string
  detector: number
  epoch: number
  mjd: number
  date: string
  /** "ok" when measured; otherwise why not: "saturated", "flagged", "no_data", "no_sky", "off_image". */
  status: string
  wavelength_um: number | null
  flux_mjy: number | null
  flux_err_mjy: number | null
  wing_status?: string | null
  wing_mjy?: number | null
  wing_err_mjy?: number | null
  /** flux over this bin's median flux; only when status is "ok". */
  relative_flux: number | null
  /** wing value over this bin's median wing value; only where the wing is trusted (D5, D6). */
  relative_wing: number | null
}

export interface LightcurveBin {
  bin: number
  detector: number
  wavelength_um: [number, number]
  center_um: number
  n_points: number
  median_flux_mjy: number | null
  median_wing_mjy: number | null
  wing_trusted: boolean
  points: LightcurvePoint[]
}

export interface LightcurveResponse {
  ra: number
  dec: number
  target?: { origin?: string; source_id?: string | null } | null
  gaia_error?: string | null
  failures?: unknown[]
  message?: string
  n_exposures?: number
  status_counts?: Record<string, number>
  n_wing_trusted?: number
  detector_ranges_um?: Record<string, [number, number]>
  method?: { flux?: string; error?: string; rejection?: string; wing?: string; statuses?: Record<string, string> }
  bins?: LightcurveBin[]
}

/** Which number is plotted: the measured flux, or, for a star too bright to measure, the
 *  light in a ring around it (a relative brightness, not a flux). */
export type Measure = 'flux' | 'wing'

export function relValue(p: LightcurvePoint, m: Measure): number | null {
  return m === 'flux' ? p.relative_flux : p.relative_wing
}

/** One-sigma error of the relative value, from the point's error and the bin's median. */
export function relError(p: LightcurvePoint, b: LightcurveBin, m: Measure): number | null {
  const err = m === 'flux' ? p.flux_err_mjy : p.wing_err_mjy
  const med = m === 'flux' ? b.median_flux_mjy : b.median_wing_mjy
  return err != null && med != null && med > 0 ? err / med : null
}

// The outer-light measure only means something where the star overloads the detector. On
// a faint star it is noise: WISE 0855, which never saturates, came out "brighter in D5
// (+101%)". A detector qualifies when at least this many of its exposures are saturated.
export const MIN_SATURATED = 3

/** The detectors in which the outer-light measure may be used for this star. */
export function wingDetectors(data: LightcurveResponse): Set<number> {
  const saturated = new Map<number, number>()
  for (const b of data.bins ?? []) {
    for (const p of b.points) if (p.status === 'saturated') saturated.set(b.detector, (saturated.get(b.detector) ?? 0) + 1)
  }
  return new Set([...saturated].filter(([, n]) => n >= MIN_SATURATED).map(([detector]) => detector))
}

/** The bins a measure is read from: every bin for flux, the saturated detectors' bins for outer light. */
export function usableBins(data: LightcurveResponse, m: Measure): LightcurveBin[] {
  const bins = data.bins ?? []
  if (m === 'flux') return bins
  const allowed = wingDetectors(data)
  return bins.filter((b) => allowed.has(b.detector))
}

export function countValues(data: LightcurveResponse, m: Measure) {
  let n = 0
  for (const b of usableBins(data, m)) for (const p of b.points) if (relValue(p, m) !== null) n += 1
  return n
}

/** Flux where there is any, otherwise the trusted wing values, otherwise flux (empty). */
export function defaultMeasure(data: LightcurveResponse): Measure {
  if (countValues(data, 'flux') > 0) return 'flux'
  return countValues(data, 'wing') > 0 ? 'wing' : 'flux'
}

// A change is called real only when it is at least this big and most bins agree on its
// direction. 5 per cent is above the 3 per cent the backend adds for repeatability, and is
// what two wing values of an unchanged star agree to in D5 and D6.
export const CHANGE_THRESHOLD = 0.05
export const AGREEMENT = 0.75
// A detector with fewer bins than this compared gets no verdict: one or two bins could be
// a single bad exposure.
export const MIN_BINS = 3

export interface DetectorSummary {
  detector: number
  firstEpoch: number
  lastEpoch: number
  /** Bins with a value in both the first and the last visit of this detector. */
  nBins: number
  nBrighter: number
  nFainter: number
  /** Median over those bins of (mean in last visit / mean in first visit - 1). */
  medianChange: number
  verdict: 'brighter' | 'fainter' | 'no clear change' | 'too few bins'
}

const mean = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length

function median(v: number[]) {
  const s = [...v].sort((a, b) => a - b)
  const mid = s.length >> 1
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
}

/** How each detector's bins changed between its first and last visit with values. */
export function summarise(data: LightcurveResponse, m: Measure): DetectorSummary[] {
  const byDet = new Map<number, LightcurveBin[]>()
  for (const b of usableBins(data, m)) byDet.set(b.detector, [...(byDet.get(b.detector) ?? []), b])
  const out: DetectorSummary[] = []
  for (const [detector, bins] of [...byDet].sort((a, b) => a[0] - b[0])) {
    const epochs = bins.flatMap((b) => b.points.filter((p) => relValue(p, m) !== null).map((p) => p.epoch))
    if (!epochs.length) continue
    const firstEpoch = Math.min(...epochs)
    const lastEpoch = Math.max(...epochs)
    if (firstEpoch === lastEpoch) continue
    const changes: number[] = []
    for (const b of bins) {
      const at = (ep: number) =>
        b.points.filter((p) => p.epoch === ep).map((p) => relValue(p, m)).filter((v): v is number => v !== null)
      const first = at(firstEpoch)
      const last = at(lastEpoch)
      if (first.length && last.length) changes.push(mean(last) / mean(first) - 1)
    }
    if (!changes.length) continue
    const nBrighter = changes.filter((c) => c > 0).length
    const nFainter = changes.filter((c) => c < 0).length
    const medianChange = median(changes)
    let verdict: DetectorSummary['verdict'] = changes.length < MIN_BINS ? 'too few bins' : 'no clear change'
    if (changes.length >= MIN_BINS && Math.abs(medianChange) >= CHANGE_THRESHOLD) {
      const agreeing = medianChange > 0 ? nBrighter : nFainter
      if (agreeing >= AGREEMENT * changes.length) verdict = medianChange > 0 ? 'brighter' : 'fainter'
    }
    out.push({ detector, firstEpoch, lastEpoch, nBins: changes.length, nBrighter, nFainter, medianChange, verdict })
  }
  return out
}

/** Why the exposures without a plotted value were left out, as counts by reason. Counts
 *  every exposure, including those with no wavelength, which are in no bin at all. */
export function leftOut(data: LightcurveResponse, m: Measure) {
  const reasons: Record<string, number> = {}
  const add = (why: string, n = 1) => {
    if (n > 0) reasons[why] = (reasons[why] ?? 0) + n
  }
  let inBins = 0
  const allowed = m === 'wing' ? wingDetectors(data) : null
  for (const b of data.bins ?? []) {
    const usable = allowed === null || allowed.has(b.detector)
    for (const p of b.points) {
      inBins += 1
      if (usable && relValue(p, m) !== null) continue
      // A measured exposure whose bin has no typical value to divide by is not "ok" to the reader.
      if (m === 'flux') add(p.status === 'ok' ? 'no_value' : p.status)
      else if (!b.wing_trusted) add('untrusted_detector')
      else if (!usable) add('not_saturated')
      else add(p.wing_status && p.wing_status !== 'ok' ? `wing_${p.wing_status}` : 'no_wing')
    }
  }
  // Exposures not in any bin: the backend could not read a wavelength for them. Their
  // statuses are the part of status_counts that the bins do not account for.
  const outside = (data.n_exposures ?? inBins) - inBins
  if (outside > 0) {
    const seen: Record<string, number> = {}
    for (const b of data.bins ?? []) for (const p of b.points) seen[p.status] = (seen[p.status] ?? 0) + 1
    let explained = 0
    for (const [status, n] of Object.entries(data.status_counts ?? {})) {
      const extra = n - (seen[status] ?? 0)
      if (extra > 0) {
        add(status, extra)
        explained += extra
      }
    }
    add('no_wavelength', outside - explained)
  }
  const total = Object.values(reasons).reduce((a, b) => a + b, 0)
  return { total, reasons }
}

export async function fetchLightcurve(req: SpectrumRequest, signal?: AbortSignal): Promise<LightcurveResponse> {
  const params = new URLSearchParams({ ra: String(req.ra), dec: String(req.dec) })
  if (req.motion) {
    for (const [name, value] of Object.entries(req.motion as Motion)) params.set(name, String(value))
  }
  const r = await fetch(`/api/lightcurve?${params}`, { signal })
  if (r.status === 404) throw new Error('this server does not offer brightness over time yet.')
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
  return (await r.json()) as LightcurveResponse
}
