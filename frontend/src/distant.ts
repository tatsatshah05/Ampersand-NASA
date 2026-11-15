// Distant-world search: types for GET /api/distant, the polling fetch, and the plain wording.
// Field names are the backend's (backend/distant.py, backend/jobs.py); the saved answers in
// src/fixtures/distant are the contract. Whatever the search finds is a CANDIDATE: never a
// discovery. When it finds nothing, the answer is a limit, and the limit is shown as it came.
import { addressOf, DEFAULT_SELECTION, withTarget } from './address'
import { dateWords, POLL_MS } from './search'

export interface DistantQuery {
  ra: number
  dec: number
  fov: number
  /** Detector numbers as the API takes them, e.g. "56". */
  detectors?: string
  /** Practice: plant a made-up object of this level (a SIMULATION). */
  plant?: PlantLevel
  seed?: number
  plant_detector?: number
}

/** Which pass: every exposure of each visit, or only the densest few days of each visit. */
export type Exposures = 'all' | 'densest_days'

export type PlantLevel = 'easy' | 'medium' | 'hard'
export const PLANT_LEVELS: readonly PlantLevel[] = ['easy', 'medium', 'hard']

export interface CandidatePosition {
  epoch: number
  date: string
  ra: number
  dec: number
  x: number
  y: number
  times_noise: number
  flux_mjy: number
  misfit_arcsec: number
  width_ratio: number
}

export interface Support {
  detector: number
  visits: { epoch: number; times_noise: number | null }[]
  seen: boolean
}

export interface Follow {
  ra: number
  dec: number
  pmra: number
  pmdec: number
  parallax: number
  pm_epoch: number
}

export interface Candidate {
  detector: number
  distance_au: number
  /** [low, high]; high is null when the search can only say "at least". */
  distance_range_au: [number, number | null]
  parallax_arcsec: number
  jump_arcsec: number
  drift_arcsec_per_year: number
  circular_drift_arcsec_per_year: number
  chi2: number
  dof: number
  positions: CandidatePosition[]
  support: Support[]
  follow: Follow
  verdict: 'clean' | 'caution'
  cautions: string[]
  also_found_in_detectors?: number[]
  /** Simulation only. */
  is_planted_object?: boolean
  /** The pass that found it. Absent in a simulation, which has only the "all" pass. */
  exposures?: Exposures
}

export interface LimitRow {
  distance_au: number
  jump_arcsec: number
  share_of_picture: number
  faintest_mjy: number
  smear_arcsec: number
  /** Absent inside a detector's own list. */
  detector?: number
  /** The pass that gave the better limit at this distance. */
  exposures?: Exposures
}

export interface DistantVisit {
  epoch: number
  date: string
  date_start: string
  date_end: string
  n_exposures: number
  sources: number
  come_and_go: number
  faintest_mjy: number
  smear_per_arcsec_of_parallax: number
}

export interface PerDetector {
  detector: number
  /** There can be one entry per pass for the same detector. */
  exposures?: Exposures
  can_search: boolean
  visits: DistantVisit[]
  come_and_go: number
  set_aside_catalogued: number
  set_aside_not_point_like: number
  linked_from: number
  links: number
  chance_links: number
  clear_share: number
  limit: LimitRow[]
}

export interface Chance {
  links_with_earth_reversed: number
  note: string
}

export interface DistantCatalogue {
  name: string
  asked: boolean
  answered: boolean
  sources_in_field: number
  error: string | null
}

export interface Planted {
  distance_au: number
  drift_arcsec_per_year: number
  swing_arcsec: number
  level: PlantLevel
  seed: number
  detector: number
  peak_over_noise: number
  flux_mjy: number
  positions: { epoch: number; ra: number; dec: number; times_noise: number }[]
}

export interface DistantResult {
  simulation: boolean
  ra: number
  dec: number
  fov: number
  detectors: number[]
  status: 'nothing_found' | 'candidates' | 'cannot_search'
  /** One plain sentence written by the backend: the headline. */
  answer: string
  candidates: Candidate[]
  limit: LimitRow[]
  chance: Chance
  per_detector: PerDetector[]
  catalogue: DistantCatalogue
  failures: unknown[]
  limits: string
  method: string
  credit: string
  /** Only when `simulation` is true. */
  notice?: string
  planted?: Planted
}

export interface DistantStatus {
  status: 'queued' | 'running' | 'done' | 'failed'
  simulation: boolean
  ra: number
  dec: number
  fov: number
  detectors: number[]
  seconds: number
  detector_now: number | null
  detectors_done: number
  detectors_total: number
  result?: DistantResult
  error?: string
}

// ---- fetching ----------------------------------------------------------------------------

export function distantUrl(q: DistantQuery): string {
  const params = new URLSearchParams({
    ra: String(q.ra),
    dec: String(q.dec),
    fov: String(q.fov),
    detectors: q.detectors ?? '56',
  })
  if (q.plant) {
    params.set('plant', q.plant)
    params.set('seed', String(q.seed ?? 1))
    params.set('plant_detector', String(q.plant_detector ?? 5))
  }
  return `/api/distant?${params}`
}

/** Ask once how the search stands. The first ask starts it. */
export async function fetchDistantStatus(q: DistantQuery, signal?: AbortSignal): Promise<DistantStatus> {
  const r = await fetch(distantUrl(q), { signal })
  if (!r.ok) {
    let detail = `the server answered ${r.status}`
    try {
      const body: unknown = await r.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') detail = body.detail
    } catch {
      // Not JSON: the status code is enough.
    }
    throw new Error(r.status === 404 ? 'this server does not offer the distant-world search yet.' : detail)
  }
  return (await r.json()) as DistantStatus
}

export interface RunOptions {
  signal?: AbortSignal
  onStatus?: (status: DistantStatus) => void
  /** Replaceable in tests. */
  fetchStatus?: (q: DistantQuery, signal?: AbortSignal) => Promise<DistantStatus>
  delayMs?: number
}

const pause = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      resolve()
    })
  })

/** Ask every POLL_MS until the search is done or has failed. Resolves with that last answer. */
export async function runDistant(q: DistantQuery, options: RunOptions = {}): Promise<DistantStatus> {
  const { signal, onStatus, fetchStatus = fetchDistantStatus, delayMs = POLL_MS } = options
  for (;;) {
    const status = await fetchStatus(q, signal)
    if (signal?.aborted) throw new DOMException('stopped', 'AbortError')
    onStatus?.(status)
    if (status.status === 'done' || status.status === 'failed') return status
    await pause(delayMs, signal)
    if (signal?.aborted) throw new DOMException('stopped', 'AbortError')
  }
}

// ---- wording -----------------------------------------------------------------------------

const plural = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`
/** A whole number with thousands separators. */
export const whole = (v: number) => Math.round(v).toLocaleString('en-US')
/** A brightness in mJy to the precision the backend gave: at most three decimals, no trailing zeros. */
export const mjy = (v: number) => String(Number(v.toFixed(3)))
const percent = (share: number) => `${Math.round(share * 100)}%`

/** The width of the patch the search covers: at least 0.2 degrees, so a nearer object's jump fits. */
export const searchFov = (viewFov: number) => Math.min(0.5, Math.max(viewFov, 0.2))

/** What the panel searches, said before the answer comes. */
export function patchSentence(fov: number): string {
  return (
    `This searches a patch ${fov} degrees across in detectors 5 and 6. A wider patch holds the jump of a nearer object, ` +
    'and those two detectors see 3.8 to 5 micrometres, where a cold distant body would show.'
  )
}

export const FIRST_TIME_NOTE =
  "The first search of a new patch takes a few minutes, because the images are read from NASA's archive. A patch whose images are already here is much quicker."

/** Progress while the search runs. */
export function progressSentence(s: DistantStatus): string {
  if (s.status === 'queued') return 'Waiting for another search to finish before this one starts.'
  const seconds = Math.round(s.seconds)
  const taken = `${plural(seconds, 'second', 'seconds')} so far`
  if (s.detector_now !== null) return `Searching detector ${s.detector_now}: ${s.detectors_done} of ${s.detectors_total} done, ${taken}.`
  if (s.detectors_done >= s.detectors_total && s.detectors_total > 0) return `Checking the catalogue, ${taken}.`
  return `Starting, ${taken}.`
}

/** The pass, in words. */
export const passWords = (e: Exposures | undefined): string | null =>
  e === 'all' ? 'all exposures of each visit' : e === 'densest_days' ? 'the densest few days of each visit' : null

export const PASS_NOTE =
  'A near object moves while a visit lasts, so for near distances the search also uses only the densest few days of each visit.'

/** One row of the limit table as a sentence. */
export function limitSentence(r: LimitRow): string {
  const smear =
    r.smear_arcsec >= 6
      ? ` An object this near smears about ${whole(r.smear_arcsec)} arcseconds within a single visit, which is why the limit is weaker here.`
      : ''
  return (
    `At ${whole(r.distance_au)} times the Earth-Sun distance an object would jump ${whole(r.jump_arcsec)} arcseconds between visits. ` +
    `It would have been found if brighter than ${mjy(r.faintest_mjy)} mJy, in ${percent(r.share_of_picture)} of the picture.${smear}`
  )
}

/** "about 2,558 times the Earth-Sun distance (between 2,534 and 2,583)". */
export function distanceWords(c: Candidate): string {
  const [low, high] = c.distance_range_au ?? [null, null]
  const range =
    low === null || low === undefined
      ? ''
      : high === null || high === undefined
        ? ` (${whole(low)} or more)`
        : ` (between ${whole(low)} and ${whole(high)})`
  return `about ${whole(c.distance_au)} times the Earth-Sun distance${range}`
}

export function candidateHeadline(c: Candidate): string {
  return `Candidate: ${distanceWords(c)}`
}

/** What the same search with the Earth's motion reversed made by chance. */
export function chanceSentence(c: Chance): string {
  const n = c.links_with_earth_reversed
  if (n === 0) {
    return "The same search with the Earth's motion reversed, which nothing real can follow, found nothing either: chance made no links in this picture."
  }
  return `The same search with the Earth's motion reversed, which nothing real can follow, made ${plural(n, 'link', 'links')} by chance in this picture, so a link here could be chance.`
}

/** One sentence per detector: what it saw and what was done with it. */
export function perDetectorSentence(d: PerDetector): string {
  const pass = passWords(d.exposures)
  const name = pass ? `Detector ${d.detector}, ${pass.replace(/^the /, '')}` : `Detector ${d.detector}`
  if (!d.can_search) return `${name} could not be searched: it has too few usable visits.`
  const counts = d.visits.map((v) => v.sources)
  const seen = counts.length
    ? `${plural(d.visits.length, 'visit', 'visits')} with ${whole(Math.min(...counts))} to ${whole(Math.max(...counts))} sources each`
    : 'no visits'
  return (
    `${name}: ${seen}; ${plural(d.come_and_go, 'source', 'sources')} come and go between visits; ` +
    `${whole(d.set_aside_catalogued)} set aside because a catalogued infrared source sits there; ` +
    `${plural(d.linked_from, 'source', 'sources')} tried for linking across visits.`
  )
}

export const perDetectorSentences = (r: DistantResult) => r.per_detector.map(perDetectorSentence)

export function catalogueSentence(c: DistantCatalogue): string {
  if (c.asked && c.answered) {
    return `${c.name} answered: ${whole(c.sources_in_field)} catalogued infrared sources lie in this patch, and anything that sits on one was set aside.`
  }
  const why = c.error ? ` (${c.error})` : ''
  return `${c.name} did not answer${why}, so known infrared sources could not be ruled out.`
}

/** Whether the other detector sees a candidate. */
export function supportSentence(c: Candidate): string[] {
  return c.support.map((s) =>
    s.seen
      ? `Detector ${s.detector} also sees it.`
      : `Detector ${s.detector} does not see it. A real object should show in the neighbouring detector.`,
  )
}

/** Simulation: the truth next to what the search said. */
export function simulationSentence(r: DistantResult): string {
  const hit = r.candidates.find((c) => c.is_planted_object)
  if (r.planted && hit) {
    return `Planted at ${whole(r.planted.distance_au)} times the Earth-Sun distance; the search says ${distanceWords(hit).replace(/^about /, '')}.`
  }
  return r.answer
}

export function plantedSentence(p: Planted): string {
  return `Planted: ${p.level} level, seed ${p.seed}, in detector ${p.detector}, ${whole(p.distance_au)} times the Earth-Sun distance, drifting ${p.drift_arcsec_per_year.toFixed(1)} arcseconds a year, ${mjy(p.flux_mjy)} mJy.`
}

export function positionDate(p: { date: string }): string {
  return dateWords(p.date)
}

// ---- the link that follows a candidate ---------------------------------------------------

/** The smallest field of view (0.1, 0.2 or 0.5 degrees) that holds 1.4 times the jump, else 0.5. */
export function followFov(jumpArcsec: number): number {
  const need = (1.4 * jumpArcsec) / 3600
  return [0.1, 0.2, 0.5].find((f) => f >= need) ?? 0.5
}

/**
 * The page address ("?ra=...") of the main viewer set to follow a candidate. The `follow`
 * numbers are for 2026.0, which is the date the viewer assumes.
 */
export function followAddress(c: Candidate): string | null {
  const base = { ...DEFAULT_SELECTION, ui: 'expert' as const, fov: followFov(c.jump_arcsec), det: c.detector }
  const s = withTarget(base, { ra: c.follow.ra, dec: c.follow.dec, pmra: c.follow.pmra, pmdec: c.follow.pmdec, parallax: c.follow.parallax, det: c.detector })
  return s ? addressOf(s) : null
}

/**
 * The practice screen showing the same planted object the search was run on: the same
 * patch, detector, level and seed give the same object there (backend/training.py).
 * Null for a real answer.
 */
export function practiceAddress(result: DistantResult): string | null {
  const planted = result.planted
  if (!result.simulation || !planted) return null
  return addressOf({
    ...DEFAULT_SELECTION,
    name: null, // the default selection is Barnard's Star by name; this patch is not it
    ui: 'expert',
    ra: result.ra,
    dec: result.dec,
    fov: result.fov,
    det: planted.detector,
    train: planted.seed,
    level: planted.level,
  })
}
