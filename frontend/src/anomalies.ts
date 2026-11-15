// The "Observe anomalies" screen (address ?watchlist=1, kept from the watchlist it grew out of, so old
// links still work): its own words, the sweep of the Milky Way's plane as exported for it
// (public/anomalies/sweep.json, written by scripts/export_anomalies.py from docs/sweep/), the regions
// a visitor can choose, and which two visits a candidate's card shows.
//
// Every sentence the screen says about Candidates A, B and C is finds.ts's (the referee's allowed
// sentence, the search for earlier reports, the status, "probably") or findsInfo.ts's plain version of
// "probably", or a number from finds.ts or the exported sweep data. Nothing here says "discovery",
// "never seen before", or "new" without "that we found in no catalogue or report we checked".
import { addressOf, DEFAULT_SELECTION, type Selection, type UiLevel } from './address'
import { framesUrl, skyOffsetArcsec, type Frame } from './api'
import { CANDIDATE_LINE, FIND_RADIUS_ARCSEC, findAt, FINDS, type Find } from './finds'
import type { Group, PatchRegion, PatchRegions } from './watchlist'

export const SCREEN_TITLE = 'Observe anomalies'

/** What an anomaly is, said first, at both levels: short sentences a reader of about 11 can follow. */
export const WHAT_IS_AN_ANOMALY: readonly string[] = [
  'An anomaly is something our searches saw change in SPHEREx’s pictures: it moved, got brighter or fainter, appeared or vanished.',
  'Most turn out to be known objects or measuring problems.',
  'A few are in no catalogue or report we could find, and those are candidates, not discoveries.',
]

/** The first group: the three candidates of the sweep. Never "never seen before": nobody can show that. */
export const FINDS_HEADING = 'Not reported anywhere we could find'

/** Where the sweep is written up, for scientists. */
export const WRITEUP_URL = 'https://github.com/tatsatshah05/Ampersand-NASA/blob/Dev/docs/sweep.md'

// ---- a candidate's card --------------------------------------------------------------------------

/** The two pictures of a card: the last visit it was not seen in, and the visit it was brightest in. */
export interface CardPair {
  before: number
  brightest: number
}

/** The fitted brightness the page's own measure gives a frame (mJy), or null. */
function fitted(frame: Frame): number | null {
  const flux = frame.detection_measure?.flux_mjy
  return typeof flux === 'number' && Number.isFinite(flux) ? flux : null
}

/**
 * Indices into `frames` of the visit where the candidate was brightest (clearly seen, the largest
 * fitted brightness; a saturated place counts as brighter than any number) and of the last visit
 * before it where it was not seen. Null when there is no such pair: then the card shows no pictures
 * rather than two that would not show the change.
 */
export function cardPair(frames: readonly Frame[]): CardPair | null {
  let brightest = -1
  let best = Number.NEGATIVE_INFINITY
  frames.forEach((f, i) => {
    if (f.detection !== 'clear' && f.detection !== 'saturated') return
    const value = f.detection === 'saturated' ? Number.POSITIVE_INFINITY : (fitted(f) ?? Number.NEGATIVE_INFINITY)
    if (brightest < 0 || value > best) {
      brightest = i
      best = value
    }
  })
  if (brightest < 0) return null
  for (let i = brightest - 1; i >= 0; i--) if (frames[i].detection === 'none') return { before: i, brightest }
  return null
}

/** The Viewer's selection for a candidate, exactly as its button asks for it (finds.ts, findTarget). */
export function findSelection(find: Find, level: UiLevel): Selection {
  return { ...DEFAULT_SELECTION, ui: level, ra: find.ra, dec: find.dec, name: find.name, pmra: 0, pmdec: 0, parallax: null, det: find.det }
}

/** The address that opens the Viewer on a candidate, at the level in use. */
export const findAddress = (find: Find, level: UiLevel): string => addressOf(findSelection(find, level))

/** The same /api/frames request the Viewer makes for a candidate: so the card shows the Viewer's own pictures. */
export const findFramesUrl = (find: Find): string =>
  framesUrl({ ra: find.ra, dec: find.dec, fov: DEFAULT_SELECTION.fov, detector: find.det, mode: 'normal', pmra: 0, pmdec: 0 })

/** The two pictures' labels. */
export const PICTURE_LABEL: Record<UiLevel, Record<keyof CardPair, string>> = {
  beginner: { before: 'Not seen', brightest: 'At its brightest' },
  expert: { before: 'Last visit not detected', brightest: 'Brightest visit' },
}

/** One line under the two pictures: what they are. The crop is the middle third of the Viewer's 0.1-degree picture. */
export const PICTURES_NOTE: Record<UiLevel, string> = {
  beginner: 'Both pictures show the same small patch of sky, made the same way. The white ticks mark the place. North is up.',
  expert: 'Detector 6 (4.4–5.0 micrometres), the Viewer’s stacked frames on one brightness scale, cropped to the central 2 arcminutes; north up, east left; ticks mark the corrected position.',
}

/** The words over the line on the search for earlier reports. */
export const REPORT_LABEL: Record<UiLevel, string> = {
  beginner: 'Has anyone reported it?',
  expert: 'Search for earlier reports',
}

export const WATCH_LINK = 'Watch it appear'

/** The text alternative of one of a card's pictures. */
export function pictureAlt(find: Find, which: keyof CardPair, when: string): string {
  const what = which === 'before' ? 'nothing is seen at the marked place' : 'the source at the marked place at its brightest'
  return `SPHEREx picture of ${find.name}'s place, ${when}: ${what}. North is up.`
}

// ---- the sweep of the plane, as exported ----------------------------------------------------------

export type SweepKind = 'candidate' | 'known_eruption' | 'known_variable' | 'set_aside'
export const SWEEP_KINDS: readonly SweepKind[] = ['candidate', 'known_eruption', 'known_variable', 'set_aside']

export interface SweepVisit {
  dates: string
  text: string
  low_mjy: number | null
  high_mjy: number | null
}

/** One survivor of the sweep (scripts/export_anomalies.py says where each field comes from). */
export interface SweepSurvivor {
  kind: SweepKind
  tile: string
  ra: number
  dec: number
  constellation: string
  direction: 'brightened' | 'faded'
  bright_mjy?: number
  // Candidates (the ruling, from docs/sweep/summary.json):
  label?: 'A' | 'B' | 'C'
  sexagesimal?: string
  position_error_arcsec?: number
  allowed_sentence?: string
  last_non_detection?: string
  first_detection?: string
  rise?: string
  visits_d6?: SweepVisit[]
  // Known eruptions (docs/sweep.md's table):
  known_as?: string
  bright_text?: string
  evidence?: string
  // Known variables and eruptions (the sweep's tile records):
  catalogue_name?: string
  catalogue?: string
  catalogue_text?: string
  catalogue_reasons?: string[]
  // Set aside (docs/sweep.md's table):
  why?: string
}

export interface SweepData {
  schema: number
  swept: string
  ruled: string
  area_sq_deg: number
  /** The area as the write-up rounds it ("472.6"). */
  area_text: string
  tiles_done: number
  sources_compared: number
  /** "August to September 2025, February to April 2026, August to September 2026" */
  visits: string
  counts: Record<SweepKind, number> & { total: number }
  survivors: SweepSurvivor[]
}

export const SWEEP_URL = '/anomalies/sweep.json'

export async function fetchSweep(signal?: AbortSignal): Promise<SweepData> {
  const r = await fetch(SWEEP_URL, { signal })
  if (!r.ok) throw new Error(`the sweep's list could not be loaded (the server answered ${r.status})`)
  return (await r.json()) as SweepData
}

/** The exported row of a candidate (A, B or C), or null. */
export const sweepRowOf = (sweep: SweepData | null, find: Find): SweepSurvivor | null =>
  sweep?.survivors.find((s) => s.kind === 'candidate' && s.label === find.key) ?? null

/** The candidate (finds.ts) a survivor is, or null. */
export const findOf = (s: SweepSurvivor): Find | null => (s.kind === 'candidate' ? (FINDS.find((f) => f.key === s.label) ?? null) : null)

/** The sweep's four groups, in the screen's order, named at each level. */
export const SWEEP_GROUPS: readonly { kind: SweepKind; label: Record<UiLevel, string> }[] = [
  { kind: 'candidate', label: { beginner: 'Candidates', expert: 'Candidates' } },
  { kind: 'known_eruption', label: { beginner: 'Known novae', expert: 'Known eruptions (novae)' } },
  { kind: 'known_variable', label: { beginner: 'Known stars that change', expert: 'Known variable stars' } },
  { kind: 'set_aside', label: { beginner: 'Set aside after a closer look', expert: 'Set aside after a closer look' } },
]

/** What a survivor is called: its name, what the catalogues call it, or (set aside) where it is. */
export function survivorName(s: SweepSurvivor): string {
  const find = findOf(s)
  if (find) return find.name
  if (s.kind === 'known_eruption') return s.known_as ?? s.catalogue_name ?? 'A known nova'
  if (s.kind === 'known_variable') return s.catalogue_name ?? 'A catalogued star'
  return `A spot in ${s.constellation}`
}

/** "RA 267.49549°, Dec −27.56803°" */
export function placeWords(ra: number, dec: number, digits = 5): string {
  return `RA ${ra.toFixed(digits)}°, Dec ${dec < 0 ? '−' : '+'}${Math.abs(dec).toFixed(digits)}°`
}

/** "Sagittarius · RA 267.49549°, Dec −27.56803°", and in Expert the sweep's tile. */
export function survivorPlace(s: SweepSurvivor, level: UiLevel): string {
  const place = `${s.constellation} · ${placeWords(s.ra, s.dec)}`
  return level === 'expert' ? `${place} · tile ${s.tile}` : place
}

const capital = (t: string) => t.charAt(0).toUpperCase() + t.slice(1)
/** The text as one sentence: a full stop at its end unless it has one. */
const stop = (t: string) => (/[.!?]$/.test(t) ? t : `${t}.`)

/** What a survivor is, in the level's words. A candidate's words are on its card, so here it only points there. */
export function survivorLines(s: SweepSurvivor, level: UiLevel): string[] {
  if (s.kind === 'candidate') return ['Its card is at the top of this page.']
  if (level === 'beginner') {
    if (s.kind === 'known_eruption') return ['A known nova, already in the catalogues.', 'Our sweep found it without being told where to look.']
    if (s.kind === 'known_variable') return ['A star the catalogues already list.', 'Older pictures show it bright too, so it did not just appear.']
    return ['Looked at closely and set aside: the change did not hold up.']
  }
  const at = 'at 4.4–5.0 micrometres'
  if (s.kind === 'known_eruption') {
    return [
      ...(s.catalogue_text ? [stop(`Catalogued: ${s.catalogue_text}`)] : []),
      stop(`Brightness ${at}: ${s.bright_text ?? `${s.bright_mjy} mJy`}`),
      ...(s.evidence ? [stop(`Evidence: ${s.evidence}`)] : []),
    ]
  }
  if (s.kind === 'known_variable') {
    return [
      stop(`Known variable (catalogued and already bright)${s.catalogue_text ? `: ${s.catalogue_text}` : ''}`),
      `${capital(s.direction)}; ${s.bright_mjy} mJy ${at} in its brighter visit.`,
    ]
  }
  return [stop(`Set aside: ${s.why ?? 'looked at and not kept'}`)]
}

/** The address that opens the Viewer at a survivor, in detector 6 (the sweep's), at the level in use. */
export function survivorAddress(s: SweepSurvivor, level: UiLevel): string {
  const find = findOf(s)
  if (find) return findAddress(find, level)
  return addressOf({ ...DEFAULT_SELECTION, ui: level, ra: s.ra, dec: s.dec, name: null, det: 6 })
}

// ---- regions -----------------------------------------------------------------------------------

export const EVERYWHERE = 'everywhere'
export const PLANE = 'plane'

/** The app's built-in targets: a searched patch centred on one is named after it. */
export const NAMED_PLACES: readonly { name: string; ra: number; dec: number }[] = [
  ...FINDS.map((f) => ({ name: f.name, ra: f.ra, dec: f.dec })),
  // The five challenge targets where /api/resolve puts them on 2026.0 (CLAUDE.md, "Positions at 2026.0").
  { name: "Barnard's Star", ra: 269.446267, dec: 4.768222 },
  { name: 'Epsilon Indi B', ra: 331.096653, dec: -56.800663 },
  { name: 'WISE 0855', ra: 133.759765, dec: -7.242182 },
  { name: 'RW Aurigae', ra: 76.956587, dec: 30.401291 },
  { name: 'R Draconis', ra: 248.167233, dec: 66.755024 },
  // The row's own looks, at the fixed positions of OWN_LOOKS in components/SearchBar.tsx (anomalies.test.ts
  // checks that they are the same).
  { name: 'Young star in Serpens South', ra: 277.50547, dec: -2.06198 },
  { name: 'Nova V462 Lupi', ra: 227.01362, dec: -40.14308 },
  { name: 'Nova V572 Velorum', ra: 156.30783, dec: -53.522 },
]

/** The built-in target a patch is centred on (within 5 arcseconds), or null. */
export function namedPlaceAt(ra: number, dec: number): string | null {
  const hit = NAMED_PLACES.find((p) => {
    const { east, north } = skyOffsetArcsec(p, { ra, dec })
    return Math.hypot(east, north) <= FIND_RADIUS_ARCSEC
  })
  return hit?.name ?? null
}

export interface RegionOption {
  key: string
  label: string
  /** How many anomalies the groups below list when it is chosen. */
  count: number
}

/** "Scorpius: Candidate B", or "Perseus, RA 52.27°, Dec +31.31°". */
export function patchName(p: Pick<PatchRegion, 'ra' | 'dec' | 'constellation'>): string {
  const name = namedPlaceAt(p.ra, p.dec)
  return name ? `${p.constellation}: ${name}` : `${p.constellation}, ${placeWords(p.ra, p.dec, 2)}`
}

export const PLANE_NAME = (sweep: Pick<SweepData, 'area_text'>) => `The Milky Way's plane (${sweep.area_text} square degrees swept)`

/** Every region, each with the count the groups below show for it: everywhere, the plane, then each patch. */
export function regionOptions(patches: PatchRegions | null, sweep: SweepData | null): RegionOption[] {
  const out: RegionOption[] = []
  const inPatches = patches?.total ?? 0
  const inSweep = sweep?.counts.total ?? 0
  out.push({ key: EVERYWHERE, label: 'Everywhere', count: inPatches + inSweep })
  if (sweep) out.push({ key: PLANE, label: PLANE_NAME(sweep), count: inSweep })
  for (const p of patches?.regions ?? []) out.push({ key: p.key, label: patchName(p), count: p.count })
  return out
}

/** The option's text in the list: its name and how many were found there. */
export const optionText = (o: RegionOption) => `${o.label} · ${o.count} found`

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "2026-11-15T10:11:15Z" or "2026-11-15" -> "15 November 2026" (the date as written, UTC for a time). */
export function longDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  const month = m ? MONTHS[Number(m[2]) - 1] : undefined
  return m && month ? `${Number(m[3])} ${month} ${m[1]}` : iso
}

/** "on 15 November 2026", or "from 14 to 15 November 2026" when the searches ran on several days. */
function onDays(first: string | null, last: string | null): string {
  if (!first || !last) return 'on dates not recorded'
  const a = longDate(first)
  const b = longDate(last)
  if (a === b) return `on ${a}`
  const [da, ...ra] = a.split(' ')
  const [db, ...rb] = b.split(' ')
  return ra.join(' ') === rb.join(' ') ? `from ${da} to ${db} ${rb.join(' ')}` : `from ${a} to ${b}`
}

const many = (n: number, one: string, more: string) => `${n.toLocaleString('en-GB')} ${n === 1 ? one : more}`

/** How large the chosen region is and when it was searched, and how many anomalies it holds. */
export function regionAbout(key: string, patches: PatchRegions | null, sweep: SweepData | null, level: UiLevel): string[] {
  if (key === PLANE && sweep) {
    const lines = [
      `${sweep.area_text} square degrees of the Milky Way's plane, swept on ${longDate(sweep.swept)}.`,
      `Its pictures from three visits were compared: ${sweep.visits}.`,
      `${many(sweep.counts.total, 'anomaly', 'anomalies')} passed every automatic check.`,
    ]
    if (level === 'expert') {
      lines.push(`${sweep.tiles_done} tiles and ${many(sweep.sources_compared, 'source', 'sources')} compared at 4.4–5.0 micrometres (detector 6).`)
    }
    return lines
  }
  if (key === EVERYWHERE) {
    const n = patches?.patches_searched ?? 0
    const lines = [
      `Every place searched so far: ${many(n, 'small patch', 'small patches')} of sky${sweep ? ` and ${sweep.area_text} square degrees of the Milky Way's plane` : ''}.`,
      `The patches were searched ${onDays(patches?.first_searched ?? null, patches?.last_searched ?? null)}${sweep ? `, and the plane was swept on ${longDate(sweep.swept)}` : ''}.`,
    ]
    const inPatches = patches?.total ?? 0
    const inSweep = sweep?.counts.total ?? 0
    lines.push(`${many(inPatches + inSweep, 'anomaly', 'anomalies')} in all: ${inPatches.toLocaleString('en-GB')} in the patches and ${inSweep} in the sweep.`)
    return lines
  }
  const p = patches?.regions.find((r) => r.key === key)
  if (!p) return []
  const when = p.last_searched ? longDate(p.last_searched) : null
  const size =
    level === 'expert'
      ? `A patch ${p.fov}° across (${p.area_sq_deg} square degrees), centred on ${placeWords(p.ra, p.dec)}${p.last_searched ? `; last searched ${p.last_searched.replace('T', ' ').replace(/:\d\dZ$/, ' UTC')}` : ''}.`
      : `A patch ${p.fov} degrees across, ${when ? `last searched on ${when}` : 'searched on a date not recorded'}.`
  return [size, `${many(p.count, 'anomaly', 'anomalies')} found here.`]
}

/** Whether the chosen region shows the patch searches' three groups, and the sweep's. */
export const showsPatches = (key: string) => key !== PLANE
export const showsSweep = (key: string) => key === PLANE || key === EVERYWHERE

/** The region key the patch list is asked for (null: the whole list). */
export const patchRegionParam = (key: string): string | null => (key === EVERYWHERE || key === PLANE ? null : key)

/** The heading over the patch searches' groups. */
export const PATCHES_HEADING: Record<UiLevel, string> = {
  beginner: 'Found by searching small patches',
  expert: 'Blind searches of small patches',
}

/** The heading over the sweep's groups. */
export const SWEEP_HEADING: Record<UiLevel, string> = {
  beginner: 'Found by the sweep of the Milky Way’s plane',
  expert: 'The sweep of the Milky Way’s plane',
}

// ---- the way in from the Viewer --------------------------------------------------------------------

/** The short link after a candidate's allowed sentence in the Viewer. */
export const ALL_THREE_LINK: Record<UiLevel, string> = {
  beginner: 'See all three in Observe anomalies',
  expert: 'All three in Anomalies',
}

/**
 * The candidate whose allowed sentence `line` gives, when the Viewer is at that candidate's place:
 * the sentence itself (Expert, under the headline) or Beginner's short CANDIDATE_LINE under the table,
 * whose "i" quotes it word for word. Else null. The link to all three follows that line.
 */
export function allThreeLineOf(line: string, ra: number, dec: number): Find | null {
  const find = findAt(ra, dec)
  return find && (find.allowed === line || line === CANDIDATE_LINE) ? find : null
}

/** The groups' counts add up to the region's: used by the screen's own check. */
export const groupTotal = (counts: Record<Group, number> | null) => (counts ? counts.eyes + counts.known + counts.artefact : 0)
