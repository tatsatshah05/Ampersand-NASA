// Types and fetch for GET /api/smallbodies: the known asteroids and comets that NASA/JPL
// predicts inside a view's field at the time of one of its exposures. Field names are the
// backend's (backend/smallbodies.py). Every position here is a prediction; `verdict` is
// what the exposure itself shows at that place.

export type Verdict = 'seen' | 'possible' | 'not_seen' | 'unmeasurable' | 'fixed_source'

export interface SmallBodyCrossing {
  id: string
  name: string
  designation: string | null
  kind: 'asteroid' | 'comet'
  exposure: {
    obs_id: string
    detector: number
    mjd: number
    time: string // ISO, UTC, ends in Z
    visit: number | null // as /api/frames numbers them
    wavelength_um: [number, number]
  }
  predicted: { ra: number; dec: number; x: number; y: number; observer: string }
  vmag: number | null
  rate_arcsec_per_hour: number
  measurement: { status: string; sigma: number | null; flux_mjy: number | null } | null
  verdict: Verdict | null
  summary: string | null
  nearby_gaia_star: { source_id: string; gmag: number | null; distance_arcsec: number } | null
  picture: string | null
}

export interface SmallBodiesResponse {
  n_exposures_checked: number
  observer: string
  observer_note: string
  limits: string
  credit: string
  problems: string[]
  bodies: SmallBodyCrossing[]
  message?: string
}

export interface SmallBodiesQuery {
  ra: number
  dec: number
  fov: number
  detector: number
}

export async function fetchSmallBodies(q: SmallBodiesQuery, signal?: AbortSignal): Promise<SmallBodiesResponse> {
  const params = new URLSearchParams({ ra: String(q.ra), dec: String(q.dec), fov: String(q.fov), detector: String(q.detector) })
  const r = await fetch(`/api/smallbodies?${params}`, { signal })
  if (r.status === 404) throw new Error('this server does not look up asteroids and comets yet')
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
  return (await r.json()) as SmallBodiesResponse
}

/** The crossings grouped by body, in the order the bodies first appear. */
export function groupByBody(bodies: SmallBodyCrossing[]): SmallBodyCrossing[][] {
  const groups = new Map<string, SmallBodyCrossing[]>()
  for (const b of bodies) {
    const list = groups.get(b.name)
    if (list) list.push(b)
    else groups.set(b.name, [b])
  }
  return [...groups.values()]
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "16 July 2026, 22:04 UTC" from the backend's ISO time. */
/**
 * The backend's sentence about one exposure, without the word "sigma": its number is the
 * measured brightness divided by the error of that measurement, which the page says in words.
 */
export function plainSummary(summary: string | null): string {
  return (summary ?? '').replace(/(\d+(?:\.\d+)?) sigma/g, '$1 times its measuring error')
}

export function whenInWords(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso)
  if (!m) return iso
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1]}, ${m[4]}:${m[5]} UTC`
}

/** The one sentence that says what the exposure shows for a whole body (all its exposures). */
export function bodyVerdict(group: SmallBodyCrossing[]): string {
  const seen = group.filter((c) => c.verdict === 'seen').length
  const possible = group.filter((c) => c.verdict === 'possible').length
  const fixed = group.filter((c) => c.verdict === 'fixed_source').length
  const n = group.length
  const exposures = n === 1 ? 'the 1 exposure' : `${n} exposures`
  if (seen > 0) return `A source is seen at the predicted place in ${seen} of ${exposures} it was predicted in.`
  if (possible > 0) return `A faint source may be at the predicted place in ${possible} of ${exposures}; nothing secure.`
  if (fixed > 0) return `The source at the predicted place is also there on other days, so it is a star or galaxy, not this body.`
  if (group.every((c) => c.verdict === 'unmeasurable')) return `Not measured in ${exposures}.`
  return `Nothing is seen at the predicted place in ${exposures}.`
}
