// Search mode: types for GET /api/search, the polling fetch, and the plain-language wording.
// Field names are the backend's (backend/search.py `search()`, backend/jobs.py). The wording
// follows docs/search.md. Anything the search finds that no catalogue lists is a CANDIDATE:
// never a "discovery", never "new". Nothing here rounds a number up or fills in a missing one.

export interface SearchQuery {
  ra: number
  dec: number
  fov: number
  /** Detector numbers as the API takes them, e.g. "123456". */
  detectors?: string
}

/** One catalogue's entry for something near the object (only the fields used here). */
export interface CatalogueMatch {
  catalogue: string
  name: string
  type?: string
  variable?: boolean
  separation_arcsec?: number
  motion_agrees?: boolean
}

export interface CatalogueStatus {
  category: string
  meaning: string | null
  label: string
  summary: string | null
  answered: string[]
  /** Catalogue name to the reason it did not answer. */
  did_not_answer: Record<string, string>
  counterpart: CatalogueMatch | null
  nearest: CatalogueMatch[]
}

export interface Visit {
  epoch: number
  date_mean: string
  n_exposures: number
}

export interface Motion {
  speed: number
  speed_err: number
  direction_deg_east_of_north: number
  span_years: number
  shift_first_to_last: { east: number; north: number }
  shift_error_arcsec: number
}

export interface Change {
  /** The two visits compared: indexes into `evidence.visits`. */
  bins: [number, number]
  n_channels: number
  channels_up: number
  channels_down: number
  ratio: number | null
  sigma: number
}

export interface Evidence {
  detector: number
  kind: 'mover' | 'changer'
  visits?: Visit[]
  motion?: Motion
  /** "aperture" is an ordinary brightness; "ring" is the ring around a saturated star. */
  measure?: string
  change?: Change | null
  two_out?: { survives: boolean; sigma: number } | null
}

export interface SearchObject {
  id: string
  kind: 'mover' | 'changer'
  verdict: 'clean' | 'caution'
  flags: string[]
  ra: number
  dec: number
  sigma_best: number
  best_detector: number
  sigma_combined: number
  found_by: string
  detectors_at_5_sigma: number[]
  detectors_at_3_sigma: number[]
  catalogue_status: CatalogueStatus
  evidence: Evidence
}

export interface RejectedObject {
  detector: number
  id: string
  kind: 'mover' | 'changer'
  sigma: number
  ra: number
  dec: number
  reasons: string[]
  flags: string[]
}

export interface SearchSummary {
  n_objects: number
  n_rejected: number
  n_below_threshold: number
  sources_tested: number
  seconds: number
  catalogues_answered: string[]
  catalogues_failed: Record<string, string>
  messages: Record<string, string>
  exposures: Record<string, number>
}

export interface SearchResult {
  field: { ra: number; dec: number; fov: number; detectors: number[] }
  objects: SearchObject[]
  rejected: RejectedObject[]
  summary: SearchSummary
  limits: string
}

export interface SearchStatus {
  status: 'queued' | 'running' | 'done' | 'failed'
  seconds: number
  detector_now: number | null
  detectors_done: number
  detectors_total: number
  searches_ahead: number
  result?: SearchResult
  error?: string
}

// ---- fetching ----------------------------------------------------------------------------

export function searchUrl(q: SearchQuery): string {
  const params = new URLSearchParams({
    ra: String(q.ra),
    dec: String(q.dec),
    fov: String(q.fov),
    detectors: q.detectors ?? '123456',
  })
  return `/api/search?${params}`
}

/** Ask once how the search of this field stands. The first ask starts it. */
export async function fetchSearchStatus(q: SearchQuery, signal?: AbortSignal): Promise<SearchStatus> {
  const r = await fetch(searchUrl(q), { signal })
  if (!r.ok) {
    let detail = `the server answered ${r.status}`
    try {
      const body: unknown = await r.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') detail = body.detail
    } catch {
      // Not JSON: the status code is enough.
    }
    throw new Error(r.status === 404 ? 'this server does not offer the search yet.' : detail)
  }
  return (await r.json()) as SearchStatus
}

export const POLL_MS = 3000

/** The status a search ended with, or the one the visitor stopped it at. */
export interface RunOptions {
  signal?: AbortSignal
  onStatus?: (status: SearchStatus) => void
  /** Replaceable in tests. */
  fetchStatus?: (q: SearchQuery, signal?: AbortSignal) => Promise<SearchStatus>
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
export async function runSearch(q: SearchQuery, options: RunOptions = {}): Promise<SearchStatus> {
  const { signal, onStatus, fetchStatus = fetchSearchStatus, delayMs = POLL_MS } = options
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

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** "1", "1 and 2", "1, 2 and 3". */
export function listWords(items: (string | number)[]): string {
  const words = items.map(String)
  if (words.length <= 1) return words.join('')
  return `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`
}

/**
 * Progress while the search runs, in words that hold still: the stage only (waiting, searching,
 * checking the catalogues), never a count of seconds or detectors, so nothing on the page ticks
 * while the visits play (the words-hold-still rule). The answer replaces it when it comes.
 */
export function progressSentence(s: SearchStatus): string {
  if (s.status === 'queued') return 'Waiting for another search to finish before this one starts.'
  if (s.detectors_done >= s.detectors_total && s.detectors_total > 0) return 'Checking the catalogues.'
  return `Searching ${s.detectors_total > 0 ? plural(s.detectors_total, 'detector', 'detectors') : 'the detectors'} one after another.`
}

/** Compass point for a bearing in degrees east of north. */
export function compass(deg: number): string {
  const points = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west']
  return points[Math.round((((deg % 360) + 360) % 360) / 45) % 8]
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2025-09-03" as "3 Sep 2025"; anything else is returned as it came. */
export function dateWords(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return iso
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1]}`
}

/** A number to the precision it carries: speeds and ratios with at most two decimals, no trailing zeros. */
const num = (v: number, digits = 1) => String(Number(v.toFixed(digits)))

export function moveSentence(m: Motion): string {
  const where = `${compass(m.direction_deg_east_of_north)} (bearing ${Math.round(m.direction_deg_east_of_north)}°)`
  return `Moved ${num(m.speed)} arcseconds a year (give or take ${num(m.speed_err)}), heading ${where}.`
}

/** The dates of the two visits a brightness change compares, when the response gives them. */
export function changeDates(e: Evidence): [string, string] | null {
  const bins = e.change?.bins
  const visits = e.visits
  if (!bins || !visits) return null
  const a = visits[bins[0]]
  const b = visits[bins[1]]
  return a && b ? [dateWords(a.date_mean), dateWords(b.date_mean)] : null
}

export function changeSentence(e: Evidence): string {
  const c = e.change
  if (!c) return 'Changed brightness.'
  const dates = changeDates(e)
  const between = dates ? ` between ${dates[0]} and ${dates[1]}` : ''
  if (c.ratio === null || c.ratio === undefined) return `Changed brightness${between}.`
  const how = c.ratio >= 1 ? 'brighter' : 'fainter'
  return `Changed brightness${between}: ${how}, ${num(c.ratio, 2)} times as bright as before.`
}

/** The headline of an object card. */
export function headline(o: SearchObject): string {
  if (o.kind === 'mover') return o.evidence.motion ? moveSentence(o.evidence.motion) : 'Moved.'
  return changeSentence(o.evidence)
}

export function changeDetail(e: Evidence): string | null {
  const c = e.change
  if (!c) return null
  const parts: string[] = []
  const total = c.channels_up + c.channels_down
  if (total > 0) {
    const same = Math.max(c.channels_up, c.channels_down)
    parts.push(`${same} of the ${plural(c.n_channels, 'wavelength channel', 'wavelength channels')} compared moved the same way`)
  }
  if (e.two_out) {
    parts.push(
      e.two_out.survives
        ? `it still stands out at ${num(e.two_out.sigma)} times the noise with the two most helpful exposures left out`
        : `with the two most helpful exposures left out it falls to ${num(e.two_out.sigma)} times the noise`,
    )
  }
  if (e.measure === 'ring') parts.push('its brightness is read from the ring of pixels around the star, because the star itself is overloaded')
  return parts.length ? `${parts.join('; ')}.` : null
}

/** How strong, in plain words: how many times the noise of empty places in the same picture. */
export function strengthSentence(o: SearchObject): string {
  const first = `${num(o.sigma_best)} times the noise in detector ${o.best_detector}`
  const five = o.detectors_at_5_sigma
  const where = five.length
    ? `Reached 5 times the noise or more in ${five.length === 1 ? 'detector' : 'detectors'} ${listWords([...five].sort((a, b) => a - b))}.`
    : 'Reached 5 times the noise only when detectors are put together.'
  return `Strongest: ${first}; ${num(o.sigma_combined)} times the noise with the detectors put together. ${where}`
}

/** True for what the catalogues that answered do not account for: a candidate, nothing more. */
export const CANDIDATE_CATEGORIES = [
  'mover_motion_not_in_catalogues',
  'mover_no_counterpart',
  'changer_not_listed_as_variable',
  'changer_no_counterpart',
]

export const isCandidate = (o: SearchObject) => CANDIDATE_CATEGORIES.includes(o.catalogue_status.category)

export function answeredSentence(c: CatalogueStatus): string {
  const failed = Object.keys(c.did_not_answer)
  const answered = c.answered.length ? `Catalogues that answered: ${listWords(c.answered)}.` : 'No catalogue answered.'
  return failed.length ? `${answered} Did not answer: ${listWords(failed)}.` : answered
}

/** What the catalogues say about it. */
export function catalogueSentence(o: SearchObject): string {
  const c = o.catalogue_status
  const name = c.counterpart?.name
  const missing = Object.keys(c.did_not_answer)
  const caveat = missing.length ? ` Not checked in ${listWords(missing)}, which did not answer.` : ''
  switch (c.category) {
    case 'known_mover':
      return `Already known: ${name ?? 'a catalogued object'}, whose catalogued motion matches the measured one.`
    case 'known_variable':
      return `Already known as a variable star: ${name ?? 'a catalogued object'}.`
    case 'mover_motion_not_in_catalogues':
      return `Not matched: an object is catalogued here, but none in the catalogues that answered has this motion.${caveat}`
    case 'mover_no_counterpart':
      return `Not listed: nothing in the catalogues that answered is at the measured track.${caveat}`
    case 'changer_not_listed_as_variable':
      return `${name ? `${name} is catalogued here, but it is` : 'Nothing catalogued here is'} not listed as a variable in the catalogues that answered.${caveat}`
    case 'changer_no_counterpart':
      return `Not listed: nothing in the catalogues that answered is at this place.${caveat}`
    case 'not checked':
      return 'The catalogues were not consulted, so it is not known whether this is listed.'
    case 'mover_unresolved_group':
      return 'Several catalogued objects lie within one pixel; the search rejects this as the shifting centre of a group.'
    default:
      return c.meaning ?? `Catalogue result: ${c.category}.`
  }
}

/** The sentence a candidate must carry: it is only a candidate, and what would settle it. */
export function candidateSentence(o: SearchObject): string | null {
  if (!isCandidate(o)) return null
  const why =
    o.catalogue_status.category === 'changer_not_listed_as_variable'
      ? 'the catalogues that answered do not list it as a variable'
      : o.catalogue_status.category === 'mover_motion_not_in_catalogues'
        ? 'no catalogue that answered has an object with this motion here'
        : 'the catalogues that answered have nothing here'
  const confirm =
    o.kind === 'mover'
      ? "A picture of the same place from another telescope on other dates showing the same motion, or SPHEREx's next visits, would confirm it."
      : "A near- or mid-infrared brightness record of this object from another telescope for the same dates, or SPHEREx's next visits, would confirm it."
  return `A candidate, not a finding: ${why}, and the published papers were not searched. ${confirm}`
}

const FLAG_WORDS: Record<string, string> = {
  saturated: 'Very bright: it overloads the detector in some exposures, so its position is only good to about 1 to 2 arcseconds.',
  halo: 'Sits on the glow of a much brighter star, which can fake or hide a change.',
  blended: 'A neighbour of similar brightness is within 16 arcseconds, so its position or brightness may be pulled by that neighbour.',
  wide: 'Wider than the stars of this picture: it may be two sources seen as one, or a galaxy.',
  edge: 'Close to the edge of the picture, where measurements are less reliable.',
  few_exposures: 'At least one visit used here has fewer than 5 exposures, so it is less certain.',
  two_visits: 'Only two visits were used, and two visits cannot tell a steady drift from a step out and back.',
  follows_roll: "The change shows only between visits taken with the spacecraft turned the other way round, so it could be light from a neighbouring bright star rather than the object itself.",
  one_roll_only: 'It shows in visits taken with the spacecraft one way round and is missing in the others, which is what a reflection inside the telescope does.',
  uncalibrated: 'Too few ordinary stars in the picture to check the measuring errors, so the strength shown may not be trustworthy.',
}

/** A flag as a sentence. A flag this page does not know is shown by its own name, never hidden. */
export function flagSentence(flag: string): string {
  return FLAG_WORDS[flag] ?? `Flag from the search: ${flag}.`
}

export function verdictSentence(o: SearchObject): string {
  return o.verdict === 'clean'
    ? 'Passed every artefact test the search has, and none of its caution flags was raised.'
    : 'Passed the artefact tests, but it has flags a person should look at before believing it.'
}

/** The kind of change, as the card's label. */
export function kindLabel(kind: 'mover' | 'changer'): string {
  return kind === 'mover' ? 'Moved' : 'Changed brightness'
}

/** One line of counts for the whole search. */
export function summarySentence(s: SearchSummary): string {
  const found = plural(s.n_objects, 'object', 'objects')
  const rejected = `${s.n_rejected} set aside as ${s.n_rejected === 1 ? 'an artefact' : 'artefacts'}`
  return `${plural(s.sources_tested, 'source', 'sources')} tested in ${Math.round(s.seconds)} seconds: ${found} moved or changed, ${rejected}.`
}

/** The explanation for an empty result. */
export function emptySentence(s: SearchSummary): string {
  return `Nothing in this patch moved or changed enough to pass the tests. ${summarySentence(s)}`
}

/** True when SPHEREx has no usable pictures here in any detector searched. */
export function noData(s: SearchSummary): boolean {
  const counts = Object.values(s.exposures)
  return counts.length > 0 && counts.every((n) => n === 0)
}

export function messagesOf(s: SearchSummary): string[] {
  return Object.entries(s.messages).map(([d, text]) => `Detector ${d}: ${text}`)
}

export function catalogueFailureSentence(s: SearchSummary): string | null {
  const failed = Object.keys(s.catalogues_failed)
  return failed.length ? `These catalogues did not answer, so nothing was checked against them: ${listWords(failed)}.` : null
}

export function rejectedHeadline(r: RejectedObject): string {
  return `${r.kind === 'mover' ? 'Looked like a mover' : 'Looked like a brightness change'} in detector ${r.detector}, ${num(r.sigma)} times the noise, at RA ${r.ra.toFixed(5)}°, Dec ${r.dec.toFixed(5)}°.`
}

/**
 * For a candidate that no more than one detector put at 5 times the noise: the search's own
 * caution about single-detector changes (docs/search.md, "What the search cannot find").
 */
export function oneDetectorSentence(o: SearchObject): string | null {
  if (!isCandidate(o) || o.detectors_at_5_sigma.length >= 2) return null
  return 'Only one detector reached 5 times the noise on its own. In nebulous or crowded patches a change seen in one detector cannot be told from an artefact by this search, so treat it as unconfirmed.'
}

/** The backend's limits as sentences, with its statistics word replaced by the page's plain one. */
export function limitsSentences(limits: string): string[] {
  return limits
    .replace(/\b5 sigma\b/g, '5 times the noise')
    .replace(/\s*See docs\/search\.md\.\s*$/, '')
    .split(/(?<=\.)\s+(?=[A-Z])/)
    .map((t) => t.trim())
    .filter(Boolean)
}
