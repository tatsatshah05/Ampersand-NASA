// The watchlist screen: types for GET /api/watchlist (backend/watchlist.py), fetching, voting and
// the plain wording that is new here. Everything on the list is a CANDIDATE, never a discovery or
// a "new object", and a vote is an opinion, never a confirmation. The sentences about what the
// machine saw and what the catalogues say are src/search.ts's: they are reused, not repeated.
import { addressOf, DEFAULT_SELECTION } from './address'
import { nearFindAt, type CatalogueStatus, type Evidence, type NearFind, type RejectedObject, type SearchObject } from './search'

export type Group = 'eyes' | 'known' | 'artefact'
export const GROUPS: readonly Group[] = ['eyes', 'known', 'artefact']
export type Answer = 'real' | 'artefact' | 'unsure'
export const ANSWERS: readonly Answer[] = ['real', 'artefact', 'unsure']
export const NOTE_MAX = 280

export interface Votes {
  real: number
  artefact: number
  unsure: number
  total: number
}

export interface NeowiseBand {
  micrometres: number
  n_visits: number
  faintest_mjy: number
  brightest_mjy: number
  factor: number | null
  saturated_share_max: number
}

export type Neowise =
  | { state: 'waiting' }
  | { state: 'error'; message: string }
  | {
      state: 'ok'
      reading: 'changed' | 'steady' | 'cannot_say'
      n_visits: number
      sentence: string
      w1: NeowiseBand | null
      w2: NeowiseBand | null
    }

/** One row of the list. Objects carry the search's own fields; artefacts carry `reasons`, `detector`, `sigma`. */
export interface WatchRow {
  id: string
  group: Group
  kind: 'mover' | 'changer'
  ra: number
  dec: number
  rank_in_group: number
  best_detector: number | null
  first_seen: string
  last_seen: string
  patches: unknown[]
  votes: Votes
  my_vote: Answer | null
  notes: string[]
  neowise?: Neowise
  flags: string[]
  // Objects only:
  verdict?: 'clean' | 'caution'
  sigma_best?: number
  sigma_combined?: number
  found_by?: string
  detectors_at_5_sigma?: number[]
  catalogue_status?: CatalogueStatus
  evidence?: Evidence
  // Set aside only:
  detector?: number
  sigma?: number
  reasons?: string[]
  /** Set on the page (markNearFind), never by the server: the candidate of our sweep this row is at, or is next to. */
  near_find?: NearFind
}

/**
 * Rows at or near one of the sweep's candidates (finds.ts). EVERY row within 5 arcsec of one, whatever
 * its group or kind, is marked as at that candidate's place, so that a card the patch search set aside
 * there (at B, a "mover" whose centre shifted differently in each colour: a blend, the search says) is never read as the app throwing the
 * candidate out. A brightness change within 25 arcsec gets the same caution and words as in the patch
 * search (search.ts, markFinds): near B, the patch search had flagged the steady star 10 arcsec away,
 * whose circle holds B's light, as an unexplained change.
 */
export function markNearFind(r: WatchRow): WatchRow {
  const near_find = nearFindAt(r.ra, r.dec)
  if (!near_find) return r
  if (near_find.at) return r.group === 'artefact' ? { ...r, near_find } : { ...r, verdict: 'caution', near_find }
  if (r.group === 'artefact' || r.kind !== 'changer') return r
  return { ...r, verdict: 'caution', near_find }
}

export interface WatchPage {
  counts: Record<Group, number>
  total: number
  patches_searched: number
  rows: WatchRow[]
  about: string
}

/** The row as the search's own object, for the helpers of search.ts; null for a set-aside row. */
export function asObject(r: WatchRow): SearchObject | null {
  if (r.group === 'artefact' || !r.catalogue_status || !r.evidence || !r.verdict) return null
  return r as unknown as SearchObject
}

/** The row as the search's rejected entry, for `rejectedHeadline`; null for anything else. */
export function asRejected(r: WatchRow): RejectedObject | null {
  if (r.group !== 'artefact' || r.sigma === undefined || r.detector === undefined) return null
  return { detector: r.detector, id: r.id, kind: r.kind, sigma: r.sigma, ra: r.ra, dec: r.dec, reasons: r.reasons ?? [], flags: r.flags }
}

// ---- wording -----------------------------------------------------------------------------

export const TABS: Record<Group, { label: string; explain: string }> = {
  eyes: {
    label: 'Needs eyes',
    explain: 'Passed every artefact test the search has, and no catalogue that answered explains it. These are candidates.',
  },
  known: {
    label: 'Already known',
    explain:
      'A catalogued moving object or a listed variable star. Kept as examples of what real ones look like: voting on them shows how well people and the machine agree.',
  },
  artefact: {
    label: 'Set aside as artefacts',
    explain:
      'The search threw these out because they have the signature of something other than a real moving or changing object (a reflection, a blend, a patch of nebula). Kept as examples, with the reasons.',
  },
}

/** Beginner's words for the three groups: what each holds, in plain words (the groups are the machine's, as in TABS). */
export const PLAIN_TABS: Record<Group, { label: string; explain: string }> = {
  eyes: {
    label: 'Not listed as changing',
    explain: 'Catalogues list an object at each of these places, but none we asked lists it as changing. Each is only a candidate.',
  },
  known: {
    label: 'Already known',
    explain: 'Catalogues already list these as moving or changing. They show what real ones look like.',
  },
  artefact: {
    label: 'Set aside as false alarms',
    explain: 'The search threw these out: they look like a reflection, two stars blended, or glowing gas.',
  },
}

/** Beginner's opening: why the screen is here, and what a vote is (and is not). */
export const PLAIN_INTRO = [
  'Our computer search marked these spots because they moved or changed brightness between SPHEREx’s visits.',
  'None is confirmed. Your vote says what you think the pictures show. It does not change the list.',
]

export const ORDER_SENTENCE =
  'The order is the machine’s, and votes never change it: a clean result comes before one with caution flags, then the ones that reached 5 times the noise in more detectors, then the stronger ones.'

export const INTRO =
  'Everything here is a candidate: something a blind search of SPHEREx images found moving or changing brightness, checked against catalogues. None of them is confirmed. A vote is your opinion of what the pictures show, not a confirmation, and anyone can vote, so votes can be gamed. The machine’s group and order do not depend on them.'

export const NEOWISE_NOTE = 'NEOWISE ended in 2024, so it speaks to whether this object varies, not to this particular change.'

export function neowiseHeadline(n: Neowise): string {
  if (n.state === 'waiting') return 'Asking NEOWISE (a second telescope’s archive); this runs in the background.'
  if (n.state === 'error') return 'NEOWISE could not be asked just now; it will be tried again.'
  switch (n.reading) {
    case 'changed':
      return 'NEOWISE also saw this spot change'
    case 'steady':
      return 'NEOWISE saw it steady'
    default:
      return 'NEOWISE cannot say'
  }
}

/** The one sentence the card shows for NEOWISE. */
export function neowiseSentence(n: Neowise): string {
  return n.state === 'ok' ? n.sentence : neowiseHeadline(n)
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

export function tallySentence(v: Votes): string {
  if (v.total === 0) return 'No votes yet.'
  return `${plural(v.total, 'volunteer has', 'volunteers have')} voted: ${v.real} real, ${v.artefact} artefact, ${v.unsure} unsure. These are opinions, not confirmations.`
}

export const ANSWER_LABEL: Record<Answer, string> = {
  real: 'Looks real',
  artefact: 'Looks like an artefact',
  unsure: 'Not sure',
}

/** Beginner's one plain line on a card the search set aside (its own reasons are in the fold). */
export function plainSetAside(kind: WatchRow['kind']): string {
  return `The computer decided this ${kind === 'mover' ? 'movement' : 'change'} was a false alarm.`
}

/** Under a group with nothing in it: everywhere, the list is empty; under a chosen region, only that region's part is. */
export function emptyGroupSentence(everywhere: boolean): string {
  return everywhere ? 'Nothing is in this group yet: the list holds only what real searches have reported.' : 'Nothing from this region is in this group.'
}

/** The group a region opens on: the first that has rows (null when none does, or the counts are not known). */
export function firstGroupWithRows(counts: Record<Group, number> | null | undefined): Group | null {
  return counts ? (GROUPS.find((g) => counts[g] > 0) ?? null) : null
}

export function exampleSentence(g: Group): string | null {
  if (g === 'known') return 'Example: the catalogues already know this one.'
  if (g === 'artefact') return 'Example: the search set this aside as an artefact.'
  return null
}

/** The address that opens the normal viewer centred on the candidate, in its best detector. */
export function viewerAddress(r: Pick<WatchRow, 'ra' | 'dec' | 'best_detector'>): string {
  const det = r.best_detector && r.best_detector >= 1 && r.best_detector <= 6 ? r.best_detector : DEFAULT_SELECTION.det
  // Opened in Expert: someone checking a candidate needs the detectors, the difference view and the charts.
  return addressOf({ ...DEFAULT_SELECTION, ra: r.ra, dec: r.dec, name: null, fov: 0.1, det, mode: 'normal', ui: 'expert' })
}

export const WATCHLIST_ADDRESS = '?watchlist=1'
export const isWatchlistAddress = (search: string) => new URLSearchParams(search).has('watchlist')

export const pictureUrl = (id: string) => `/api/watchlist/${encodeURIComponent(id)}/picture.png`
export const EXPORT_CSV_URL = '/api/watchlist/export.csv'

// ---- the voter ---------------------------------------------------------------------------

const VOTER_KEY = 'spherex-watchlist-voter'

/** A random id the browser keeps. No name, no account. Falls back to a fresh one each visit if storage is blocked. */
export function voterId(): string {
  try {
    const kept = window.localStorage.getItem(VOTER_KEY)
    if (kept && /^[A-Za-z0-9_-]{16,64}$/.test(kept)) return kept
  } catch {
    // Storage blocked: carry on with an id for this visit only.
  }
  const fresh = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `v${Date.now()}${Math.random().toString(36).slice(2)}x`
  try {
    window.localStorage.setItem(VOTER_KEY, fresh)
  } catch {
    // As above.
  }
  return fresh
}

// ---- fetching ----------------------------------------------------------------------------

async function failure(r: Response): Promise<Error> {
  let detail = `the server answered ${r.status}`
  try {
    const body: unknown = await r.json()
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') detail = body.detail
  } catch {
    // Not JSON: the status code is enough.
  }
  return new Error(r.status === 404 ? 'this server does not offer the watchlist yet.' : detail)
}

export async function fetchWatchlist(
  group: Group,
  offset: number,
  limit: number,
  voter: string,
  signal?: AbortSignal,
  region: string | null = null,
): Promise<WatchPage> {
  const params = new URLSearchParams({ group, offset: String(offset), limit: String(limit) })
  if (region) params.set('region', region)
  const r = await fetch(`/api/watchlist?${params}`, { signal, headers: { 'X-Voter': voter } })
  if (!r.ok) throw await failure(r)
  const page = (await r.json()) as WatchPage
  return { ...page, rows: page.rows.map(markNearFind) }
}

/** One patch a blind search covered (GET /api/watchlist/regions, backend/watchlist.py `regions`). */
export interface PatchRegion {
  key: string
  ra: number
  dec: number
  /** The width of the patch, degrees. */
  fov: number
  area_sq_deg: number
  /** The constellation its centre lies in (astropy's boundaries, the IAU's spelling). */
  constellation: string
  /** When a search of it last reported (UTC, ISO), or null. */
  last_searched: string | null
  /** The rows its searches reported; a row seen from two patches counts in both. */
  count: number
  counts: Record<Group, number>
}

export interface PatchRegions {
  regions: PatchRegion[]
  /** Every row of the list, once. */
  total: number
  counts: Record<Group, number>
  patches_searched: number
  first_searched: string | null
  last_searched: string | null
}

export async function fetchRegions(signal?: AbortSignal): Promise<PatchRegions> {
  const r = await fetch('/api/watchlist/regions', { signal })
  if (!r.ok) throw await failure(r)
  return (await r.json()) as PatchRegions
}

export async function castVote(id: string, answer: Answer, note: string, voter: string): Promise<{ votes: Votes; my_vote: Answer }> {
  const r = await fetch(`/api/watchlist/${encodeURIComponent(id)}/vote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer, note: note.trim() || null, voter }),
  })
  if (!r.ok) throw await failure(r)
  return (await r.json()) as { votes: Votes; my_vote: Answer }
}
