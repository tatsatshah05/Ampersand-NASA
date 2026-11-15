// Every word Beginner reads in the six tool panels, in one place. Each sentence about an object
// is a pure function of that tool's own answer (the same answer Expert shows), so every number
// in it comes from that answer; the few facts that do not (the Moon's width, the years of the
// other surveys, how bright WISE 0855 is) are verified ones, named where they are used.
//
// Rules for the words, as in guide.ts: reading age about 11, sentences of 20 words or fewer,
// everyday words. Outside the closed fold Beginner never meets "sigma", "flux", "epoch",
// "detector", "centroid", "mJy", "aperture", "photometry", "ephemeris" or "S/N", and nothing is
// ever a "discovery" or a "new planet": what no catalogue explains is a candidate, with what
// would confirm it. plain.test.ts checks all of it on real saved answers.
import { CHANGE_THRESHOLD, summarise, type DetectorSummary, type LightcurveResponse, type Measure } from './lightcurve'
import type { Measured, SpectrumResponse, StarsInCircle } from './spectrum'
import { isCandidate, noData, type SearchObject, type SearchResult } from './search'
import type { DistantResult } from './distant'
import { groupByBody, type SmallBodiesResponse, type SmallBodyCrossing } from './smallbodies'
import { dateSpan, monthYearLong } from './wording'

/** The summary of the one closed fold that holds everything else of a panel. */
export const SCIENCE_FOLD = 'More detail (for scientists)'

/** The scientist's words Beginner never meets outside that fold (what the checks look for, case-blind). */
export const SCIENCE_WORDS = /\b(sigma|flux|fluxes|epoch|epochs|detector|detectors|centroid|centroids|mJy|aperture|photometry|ephemeris|S\/N)\b|σ/i

const count = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`
const listAnd = (items: string[]) => (items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`)
/** "1.6", "4.5", "13": one decimal below 10, whole numbers from 10. */
const factor = (r: number) => (r >= 10 ? String(Math.round(r)) : String(Number(r.toFixed(1))))
const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

// ---- what was measured, and what could spoil it (brightness and colours) --------------------

/**
 * The cautions under a brightness or colour chart, from the same fields Expert shows: another
 * star inside the measuring circle (its light is in every number), a spot measured in place
 * because no catalogued star is there, and photos that could not be downloaded.
 */
export function measureCautions(data: { measured?: Measured; stars_in_circle?: StarsInCircle; failures?: unknown[] }): string[] {
  const out: string[] = []
  const circle = data.stars_in_circle
  const near = circle?.stars ?? []
  if (circle?.known === false) out.push('We could not check for other stars this close, so their light may be mixed in.')
  else if (near.length === 1) out.push('Another star is so close that its light is mixed into these numbers.')
  else if (near.length > 1) out.push(`${near.length} other stars are so close that their light is mixed into these numbers.`)
  // The lightcurve's own word for "no motion was given and no catalogued star is here".
  if (data.measured?.what === 'fixed_position') out.push('No catalogued star is listed exactly here, so we measured the same spot in every photo.')
  const failed = data.failures?.length ?? 0
  if (failed > 0) out.push(`${count(failed, 'photo', 'photos')} could not be downloaded, so ${failed === 1 ? 'it is' : 'they are'} missing.`)
  return out
}

// ---- Brightness (the light curve) ----------------------------------------------------------

export const BRIGHTNESS_TITLE = 'Brightness over time'
export const BRIGHTNESS_INTRO =
  'Each dot is one photo, and 1 means its usual brightness. We only compare each infrared colour with itself, visit to visit.'
export const BRIGHTNESS_LOADING = 'Measuring it in every photo. This takes a few seconds, or a few minutes the first time.'
export const BRIGHTNESS_ERROR = 'The brightness could not be measured:'
export const brightnessAxis = (m: Measure) =>
  m === 'flux' ? 'How bright, compared with usual (1 = usual)' : 'Light just around the star, compared with usual (1 = usual)'

/** SPHEREx's six bands of infrared colours, in three plain groups: 1 and 2, 3 and 4, 5 and 6. */
const GROUPS = ['shortest', 'middle', 'longest'] as const
const groupOf = (band: number) => GROUPS[Math.min(2, Math.max(0, Math.ceil(band / 2) - 1))]

/** "SPHEREx's middle and longest infrared colours". */
export function colourWords(bands: number[]): string {
  return `SPHEREx's ${listAnd(GROUPS.filter((g) => bands.some((b) => groupOf(b) === g)))} infrared colours`
}

/** The caption of one small chart: "Band 5 of 6 (longest infrared colours)". */
export const bandCaption = (band: number) => `Band ${band} of 6 (${groupOf(band)} infrared colours)`

/** The words of a hovered dot. */
export const brightnessTip = (value: number, err: number | null) =>
  `${value.toFixed(2)}${err !== null ? ` ± ${err.toFixed(2)}` : ''} times its usual brightness`

/** One band's verdict, with the measure it was read from. */
export type BandVerdict = DetectorSummary & { measure: Measure }

/**
 * The brightness tool's own verdict for each band (lightcurve.ts `summarise`, the rule Expert
 * states: a median change of 5 per cent or more over at least 3 wavelength bins, three quarters
 * of them agreeing, each bin compared only with itself). Per band it is read from the measured
 * brightness where that rule could decide there, else from the light around an overexposed
 * star, which Expert offers as its second measure. No new statistic is made.
 */
export function bandVerdicts(data: LightcurveResponse): BandVerdict[] {
  const flux = summarise(data, 'flux')
  const wing = summarise(data, 'wing')
  const bands = [...new Set([...flux, ...wing].map((s) => s.detector))].sort((a, b) => a - b)
  const decided = (s: DetectorSummary | undefined) => s !== undefined && s.verdict !== 'too few bins'
  return bands.flatMap((band) => {
    const f = flux.find((s) => s.detector === band)
    const w = wing.find((s) => s.detector === band)
    const pick = decided(f) ? { s: f!, m: 'flux' as const } : decided(w) ? { s: w!, m: 'wing' as const } : f ? { s: f, m: 'flux' as const } : w ? { s: w, m: 'wing' as const } : null
    return pick ? [{ ...pick.s, measure: pick.m }] : []
  })
}

/**
 * Which of the tool's two measures the Beginner chart draws: the one the sentence is about.
 * The measured brightness when it decides anything (or nothing else does), else the light
 * around an overexposed star.
 */
export function plainMeasure(data: LightcurveResponse): Measure {
  const decided = bandVerdicts(data).filter((v) => v.verdict !== 'too few bins')
  return decided.length > 0 && decided.every((v) => v.measure === 'wing') ? 'wing' : 'flux'
}

/** The month of a visit: the middle date of its photos that have a value to compare, "September 2025". */
export function visitMonth(data: LightcurveResponse, epoch: number): string {
  const valued = (p: { relative_flux: number | null; relative_wing: number | null }) => p.relative_flux !== null || p.relative_wing !== null
  const dates = (data.bins ?? []).flatMap((b) => b.points.filter((p) => p.epoch === epoch && valued(p)).map((p) => p.date)).sort()
  return dates.length ? monthYearLong(dates[Math.floor((dates.length - 1) / 2)]) : `visit ${epoch}`
}

/** "about 1.6 times as bright", "about 20 per cent brighter", "about 4.5 to 13 times as bright". */
export function brighterWords(ratios: number[]): string {
  const lo = Math.min(...ratios)
  const hi = Math.max(...ratios)
  if (hi < 1.3) {
    const [a, b] = [Math.round((lo - 1) * 100), Math.round((hi - 1) * 100)]
    return a === b ? `about ${a} per cent brighter` : `about ${a} to ${b} per cent brighter`
  }
  if (factor(lo) === factor(hi)) return `about ${factor(hi)} times as bright`
  return lo < 1.3 ? `up to about ${factor(hi)} times as bright` : `about ${factor(lo)} to ${factor(hi)} times as bright`
}

const FRACTIONS = ['', '', 'half', 'a third', 'a quarter', 'a fifth', 'a sixth', 'a seventh', 'an eighth', 'a ninth', 'a tenth']

/** A ratio below 1 as a fraction of the earlier brightness, or null when "per cent fainter" says it better. */
function fraction(r: number): string | null {
  if (r > 0.72) return null
  if (r > 0.6) return 'two thirds'
  const n = Math.round(1 / r)
  return FRACTIONS[n] ?? 'less than a tenth'
}

/** "about half as bright", "about 10 per cent fainter", "about a third to half as bright". */
export function fainterWords(ratios: number[]): string {
  const lo = Math.min(...ratios)
  const hi = Math.max(...ratios)
  const [fl, fh] = [fraction(lo), fraction(hi)]
  if (fl === null && fh === null) {
    const [a, b] = [Math.round((1 - hi) * 100), Math.round((1 - lo) * 100)]
    return a === b ? `about ${a} per cent fainter` : `about ${a} to ${b} per cent fainter`
  }
  if (fl === fh) return `about ${fl} as bright`
  return fh === null ? `down to about ${fl} as bright` : `about ${fl} to ${fh} as bright`
}

/** Whether most clean measurements are under 3 times their own error: the page's "not seen" bar (guide.ts). */
function mostlyTooFaint(data: LightcurveResponse): boolean {
  const ok = (data.bins ?? []).flatMap((b) => b.points.filter((p) => p.status === 'ok' && p.flux_mjy !== null && p.flux_err_mjy))
  return ok.length > 0 && ok.filter((p) => (p.flux_mjy as number) > 3 * (p.flux_err_mjy as number)).length < ok.length / 2
}

/**
 * What the brightness tool shows for this object, in a few short sentences.
 *
 * The rule: only the tool's own same-colour comparison is used (`bandVerdicts`), never the
 * brightness of each visit's picture, which samples different colours in every visit. When a
 * band got brighter or fainter by that rule: by about how much (the median change of its
 * wavelength bins, as Expert's table gives it), between which months (the first and last visit
 * compared), and in which of SPHEREx's colours. When the rule found no change: "no clear change",
 * the rule's own verdict (Expert: "does not show a clear change"); a change under its 5 per cent
 * bar, or one most bins do not agree on, is not called a change, so it is not said to be absent
 * either. When it could decide nothing: why (overexposed, too faint, one visit only, or too few
 * photos of the same colour in two visits).
 */
export function brightnessResult(data: LightcurveResponse): string[] {
  const total = data.n_exposures ?? 0
  const overexposed = data.status_counts?.saturated ?? 0
  const out: string[] = []
  // "Most photos overexposed" is said first, whatever follows.
  const tooBright = total > 0 && overexposed > total / 2
  if (tooBright) out.push(`It is too bright to measure directly: ${overexposed} of its ${total} photos are overexposed.`)

  const bands = bandVerdicts(data)
  const decided = bands.filter((v) => v.verdict !== 'too few bins')
  const changed = decided.filter((v) => v.verdict === 'brighter' || v.verdict === 'fainter')

  if (changed.length > 0) {
    // The months of the comparison: shared by every changed band, else those of the strongest change.
    const strongest = changed.reduce((a, b) => (Math.abs(Math.log(1 + b.medianChange)) > Math.abs(Math.log(1 + a.medianChange)) ? b : a))
    const same = changed.every((v) => v.firstEpoch === strongest.firstEpoch && v.lastEpoch === strongest.lastEpoch)
    const from = visitMonth(data, strongest.firstEpoch)
    const to = visitMonth(data, strongest.lastEpoch)
    const up = changed.filter((v) => v.verdict === 'brighter')
    const down = changed.filter((v) => v.verdict === 'fainter')
    const how = up.length && down.length ? 'It changed' : up.length ? 'It got brighter' : 'It got fainter'
    out.push(same ? `${how} between ${from} and ${to}.` : `${how} between visits, most between ${from} and ${to}.`)
    for (const [group, words] of [
      [up, brighterWords],
      [down, fainterWords],
    ] as const) {
      if (!group.length) continue
      const ratios = group.map((v) => 1 + v.medianChange)
      const what = group.every((v) => v.measure === 'wing') ? 'the light just around it' : 'it'
      out.push(`In ${colourWords(group.map((v) => v.detector))} ${what} became ${words(ratios)}.`)
    }
    if (changed.some((v) => v.measure === 'wing')) out.push('Where it is overexposed, we measured the light in a ring just around it.')
    return out
  }
  if (decided.length > 0) {
    const ring = decided.every((v) => v.measure === 'wing')
    out.push(
      ring
        ? 'So we measured the light just around it, which showed no clear change between its visits.'
        : 'It showed no clear change between its visits.',
    )
    return out
  }
  // Nothing could be decided: say why.
  const valued = (data.bins ?? []).flatMap((b) => b.points.filter((p) => p.relative_flux !== null || p.relative_wing !== null))
  const visits = new Set(valued.map((p) => p.epoch))
  if (tooBright) out.push('So too few photos are left to compare one visit with another.')
  else if (!valued.length) out.push('No photo gave a clean measurement of it, so nothing can be compared.')
  else if (visits.size < 2) out.push('It was measured in one visit only, so there is nothing to compare it with yet.')
  else if (mostlyTooFaint(data)) out.push('In most photos it is too faint to measure well, so no change can be judged.')
  else out.push('Too few photos caught the same infrared colour in two visits, so no change can be judged.')
  return out
}

/** The size of change the rule needs, for the fold's readers ("5 per cent"); kept here so Beginner never guesses it. */
export const CHANGE_BAR_PERCENT = Math.round(CHANGE_THRESHOLD * 100)

// ---- Colours (the spectrum) ----------------------------------------------------------------

export const SPECTRUM_TITLE = 'How bright it is in each infrared colour'
export const SPECTRUM_SPOT_TITLE = 'Measure the colours of this spot?'
export const SPECTRUM_INTRO =
  'SPHEREx splits infrared light, which our eyes cannot see, into 102 colours. Each dot is one photo: further right is a longer colour, higher is brighter.'
export const SPECTRUM_LOADING = 'Measuring it in every photo. This takes a few seconds, or a few minutes the first time.'
export const SPECTRUM_SPOT_ASK = 'A new spot has to be read from NASA’s archive in every photo. That takes a few minutes.'
export const SPECTRUM_SPOT_BUTTON = 'Measure this spot'
export const SPECTRUM_ERROR = 'Its colours could not be measured:'
export const SPECTRUM_AXIS_X = 'Infrared colour (micrometres)'
export const SPECTRUM_AXIS_Y = 'Brightness'
/** The two rails over the chart (each label must fit the chart's left margin, as "too bright" does). */
export const SPECTRUM_RAILS: Record<string, string> = { saturated: 'too bright', 'no value': 'no reading' }
export const spectrumVisit = (epoch: number, start: string, end: string) => `Visit ${epoch}: ${dateSpan(start, end)}`
export const spectrumTip = (wavelength: number) => `Colour ${wavelength.toFixed(2)} micrometres`
export const spectrumTipValue = (status: string, value: number | null) =>
  status === 'ok' && value !== null ? 'Measured' : status === 'saturated' ? 'Too bright to measure' : 'Not measured'

/** The chart's own message when it has nothing to draw, in plain words. */
export function spectrumEmpty(data: SpectrumResponse, allHidden: boolean): string {
  const pts = (data.points ?? []).filter((p) => p.wavelength_um !== null)
  if (allHidden) return 'No visit is switched on.'
  if (pts.length && pts.every((p) => p.status === 'saturated')) return 'Too bright: every photo is overexposed here.'
  if (pts.length) return 'No photo gave a clean measurement here.'
  return 'SPHEREx has no photo of this spot.'
}

/**
 * What the colour chart shows for this object. The rule: the tool names no dips or bumps in a
 * spectrum, so neither does this. It says only what the tool states: how many of the photos
 * could be measured, how many were overexposed (too bright for SPHEREx), and how many had a bad
 * pixel or another problem, from the answer's own counts.
 */
export function spectrumResult(data: SpectrumResponse): string[] {
  const n = data.n_exposures ?? 0
  const counts = data.status_counts ?? {}
  const ok = counts.ok ?? 0
  const sat = counts.saturated ?? 0
  const rest = n - ok - sat
  if (n === 0) return ['SPHEREx has no photo of this spot yet.']
  if (ok === n) return [`All ${n} of its photos could be measured.`]
  if (ok === 0) return [sat === n ? `It is too bright: all ${n} of its photos are overexposed, so none could be measured.` : `None of its ${n} photos gave a clean measurement.`]
  const out = [`${ok} of its ${n} photos could be measured.`]
  if (sat > 0) out.push(`${sat} ${sat === 1 ? 'was' : 'were'} overexposed, because it is too bright there.`)
  if (rest > 0) out.push(`${rest} had a bad pixel or another problem.`)
  return out
}

// ---- Find changes (the blind search of a patch) --------------------------------------------

export const SEARCH_TITLE = 'Did anything here move or change?'
export const SEARCH_INTRO =
  'The computer compares every point of light in this patch between visits. Most things it finds are already known, or are false alarms.'
export const SEARCH_WAITING = 'Searching this patch. It takes under a minute if its photos are here already, or a few minutes if not.'
export const SEARCH_FAILED = 'The search could not finish:'
export const SEARCH_LOOK = 'Look at it'

const MOVED = (o: SearchObject) => o.kind === 'mover'
const KNOWN = ['known_mover', 'known_variable']

/**
 * What the search found in this patch. The rule: count what moved and what changed brightness
 * (the tool's own list, after its artefact tests), how many the catalogues already know, and
 * how many no catalogue that answered lists as moving or changing: each of those is a candidate,
 * with what would confirm it. Also how many were set aside as false alarms, and whether a
 * catalogue did not answer.
 */
export function searchResult(result: SearchResult): string[] {
  const s = result.summary
  if (noData(s)) return ['SPHEREx has no usable photos of this patch, so nothing could be searched.']
  const objects = result.objects
  const moved = objects.filter(MOVED).length
  const changed = objects.length - moved
  const known = objects.filter((o) => KNOWN.includes(o.catalogue_status.category)).length
  const candidates = objects.filter(isCandidate)
  const out = [`It tested ${count(s.sources_tested, 'point', 'points')} of light in this patch.`]
  if (!objects.length) out.push('Nothing moved or changed enough to pass its tests.')
  else {
    const m = moved === 0 ? 'Nothing moved' : `${count(moved, 'thing', 'things')} moved`
    const c = changed === 0 ? 'nothing changed brightness' : `${count(changed, 'thing', 'things')} changed brightness`
    out.push(`${m}, and ${c}.`)
  }
  if (known > 0) out.push(known === objects.length ? (known === 1 ? 'It is already known in star catalogues.' : 'All of them are already known in star catalogues.') : `${known} ${known === 1 ? 'is' : 'are'} already known in star catalogues.`)
  if (candidates.length > 0) {
    const how = candidates.every(MOVED) ? 'moving' : candidates.some(MOVED) ? 'moving or changing' : 'changing'
    const n = candidates.length
    out.push(`${n} ${n === 1 ? 'is' : 'are'} not listed as ${how} in any catalogue we asked, so ${n === 1 ? 'it is' : 'each is'} only a candidate.`)
    out.push(`Another telescope, or SPHEREx’s next visits, would be needed to confirm ${n === 1 ? 'it' : 'them'}.`)
  }
  const unchecked = objects.length - known - candidates.length
  if (unchecked > 0) out.push(`${unchecked} could not be checked against the catalogues.`)
  if (result.rejected.length > 0) out.push(`${count(result.rejected.length, 'more was', 'more were')} set aside as false alarms.`)
  if (Object.keys(s.catalogues_failed).length > 0) out.push('Some catalogues did not answer, so this check is not complete.')
  return out
}

/** One numbered line per object, matching the numbered rings on the picture. */
export function searchItem(o: SearchObject): string {
  const what = MOVED(o) ? 'Moved' : 'Changed brightness'
  const known = KNOWN.includes(o.catalogue_status.category) ? 'Already known' : isCandidate(o) ? 'Only a candidate' : 'Not checked against catalogues'
  return `${what}. ${known}.${o.verdict === 'caution' ? ' Has warning signs, so take care.' : ''}`
}

// ---- Far-off planet (the distant-world search) ---------------------------------------------

export const DISTANT_TITLE = 'Is a far-off planet here?'
export const DISTANT_INTRO =
  'A planet far beyond Neptune would seem to jump between visits, because Earth has moved around the Sun. This search looks for such jumps.'
export const DISTANT_WAITING = 'Searching this patch. The first search of a new patch takes a few minutes.'
export const DISTANT_FAILED = 'The search could not finish:'
export const DISTANT_ELSEWHERE = 'Finding nothing here does not rule out a planet somewhere else in the sky.'

/**
 * How bright WISE 0855, one of the stars on this page, is to this search: 0.39 to 0.47 mJy in
 * band 5 on the search's own scale, 0.43 from the brightness tool, about 0.5 at 4.4 to 5
 * micrometres (CLAUDE.md, "Distant-world search" and "WISE 0855"). A yardstick a visitor can
 * look at, instead of a unit.
 */
export const WISE_0855_MJY = 0.45

/** "about half as bright as WISE 0855", "about as bright as WISE 0855", "about 3 times as bright as WISE 0855". */
export function faintWords(mjy: number): string {
  const q = mjy / WISE_0855_MJY
  if (q <= 0.6) {
    const f = FRACTIONS[Math.round(1 / q)] ?? 'less than a tenth'
    return `about ${f} as bright as WISE 0855`
  }
  if (q < 1.5) return 'about as bright as WISE 0855'
  if (q < 2.5) return 'about twice as bright as WISE 0855'
  return `about ${Math.round(q)} times as bright as WISE 0855`
}

const SHARES: [number, string][] = [
  [0.1, 'a tenth'],
  [0.2, 'a fifth'],
  [0.25, 'a quarter'],
  [1 / 3, 'a third'],
  [0.5, 'half'],
  [2 / 3, 'two thirds'],
  [0.75, 'three quarters'],
  [1, 'all'],
]
/** A share as the nearest simple fraction: 0.54 and 0.55 are "half", 0.64 "two thirds". */
export function shareWords(share: number): string {
  return SHARES.reduce((a, b) => (Math.abs(b[0] - share) < Math.abs(a[0] - share) ? b : a))[1]
}

/**
 * What the distant-world search found here. The rule: whether anything was found (the answer's
 * own status), how faint it could reach (its best limit: the row of its table with the faintest
 * brightness, said against WISE 0855, and the share of the picture that same row covered, so the
 * two numbers always belong together), and always that finding nothing here rules nothing out
 * elsewhere. A link is a candidate and needs another telescope.
 */
export function distantResult(r: DistantResult): string[] {
  const out: string[] = []
  if (r.status === 'cannot_search') out.push('There are too few visits of this patch to search it yet.')
  else if (r.candidates.length > 0) {
    const n = r.candidates.length
    out.push(`It found ${count(n, 'candidate', 'candidates')}: something that jumps the way a far-off planet would.`)
    out.push(n === 1 ? 'It is not confirmed: another telescope would have to see it in the same places.' : 'None is confirmed: another telescope would have to see them in the same places.')
  } else out.push('Nothing here jumps the way a far-off planet would.')
  if (r.limit.length > 0 && r.status !== 'cannot_search') {
    // The faintest row (of equal ones, the one covering most of the picture): its limit and its share.
    const best = r.limit.reduce((a, b) => (b.faintest_mjy < a.faintest_mjy || (b.faintest_mjy === a.faintest_mjy && b.share_of_picture > a.share_of_picture) ? b : a))
    out.push(`The faintest planet it could catch is ${faintWords(best.faintest_mjy)}.`)
    out.push(`At best it could catch one that faint in about ${shareWords(best.share_of_picture)} of this picture.`)
  }
  if (r.failures.length > 0) out.push('Some parts of the search failed, so this answer may be incomplete.')
  if (!(r.catalogue.asked && r.catalogue.answered)) out.push('The list of known infrared objects did not answer, so known ones were not ruled out.')
  if (r.candidates.length === 0) out.push(DISTANT_ELSEWHERE)
  return out
}

// ---- Asteroids (known small bodies) --------------------------------------------------------

export const SMALLBODIES_TITLE = 'Known asteroids and comets in this patch'
export const SMALLBODIES_INTRO =
  'Asteroids and comets move against the stars, so they can look like a change. NASA keeps a list of where known ones are.'
export const SMALLBODIES_LOADING = 'Asking NASA which known asteroids and comets were here. The first time for a patch takes a few minutes.'
export const SMALLBODIES_ERROR = 'The asteroids and comets could not be looked up:'
export const SMALLBODIES_NO_PICTURE = 'No picture'

/** "Asteroid 103643", "Comet 12P". */
export const bodyName = (c: SmallBodyCrossing) => `${capital(c.kind)} ${c.name}`

/** What one photo shows at the body's predicted place, from the backend's own verdict. */
export function crossingWords(c: SmallBodyCrossing): string {
  switch (c.verdict) {
    case 'seen':
      return 'Something is seen where it should be.'
    case 'possible':
      return 'Something faint may be there.'
    case 'fixed_source':
      return 'A star or galaxy sits there on other days too.'
    case 'unmeasurable':
      return 'This photo could not be measured there.'
    case 'not_seen':
      return 'Nothing is seen there: it is too faint, or a little off.'
    default:
      return 'Not measured.'
  }
}

/** The words a screen reader gives one small picture. */
export const crossingAlt = (c: SmallBodyCrossing) => `${bodyName(c)} in one SPHEREx photo, centred where NASA predicts it`

/** "15 Sep 2026" from the backend's ISO time. */
export const crossingDate = (c: SmallBodyCrossing) => dateSpan(c.exposure.time, c.exposure.time)

/**
 * What the asteroid lookup found. The rule: how many known asteroids and comets NASA/JPL puts
 * inside this patch during the photos checked, in how many photos, that every one of them is
 * already known (it is a lookup of known bodies), and whether the lookup was complete.
 */
export function smallBodiesResult(data: SmallBodiesResponse): string[] {
  const groups = groupByBody(data.bodies)
  const out: string[] = []
  if (data.message) out.push('This patch could not be checked for asteroids and comets.')
  else if (!groups.length) out.push(`No known asteroid or comet was in this patch during any of the ${data.n_exposures_checked} photos we checked.`)
  else {
    const asteroids = groups.filter((g) => g[0]?.kind !== 'comet').length
    const comets = groups.length - asteroids
    const who = listAnd([asteroids ? count(asteroids, 'known asteroid', 'known asteroids') : '', comets ? count(comets, 'known comet', 'known comets') : ''].filter(Boolean))
    out.push(`${capital(who)} crossed this patch, in ${count(data.bodies.length, 'photo', 'photos')}.`)
    const one = groups.length === 1
    out.push(one ? 'It is already known, and NASA predicts where it is.' : 'They are all already known, and NASA predicts where they are.')
    // What the photos show at the predicted places, from the backend's verdict for each photo.
    const seen = data.bodies.filter((b) => b.verdict === 'seen').length
    const maybe = data.bodies.filter((b) => b.verdict === 'possible').length
    if (seen) out.push(`${count(seen, 'photo shows', 'photos show')} something where ${one ? 'it' : 'one'} should be.`)
    else if (maybe) out.push(`${count(maybe, 'photo', 'photos')} may show something faint where ${one ? 'it' : 'one'} should be.`)
    else if (data.bodies.every((b) => b.verdict === 'not_seen'))
      out.push(`${one ? 'It does' : 'They do'} not show in these photos: too faint here, or a little off.`)
  }
  if (data.problems.length > 0) out.push('NASA did not answer every question, so this list may be incomplete.')
  return out
}

// ---- What is it? (for now: the same patch in other surveys) ------------------------------------

export const CONTEXT_TITLE = 'What is it?'
export const CONTEXT_INTRO = 'These are older pictures of the same sky, from other telescopes. The orange square is the patch SPHEREx shows.'
export const CONTEXT_PICK = 'Telescope'
export const CONTEXT_FAILED = 'The sky atlas could not start.'
export const CONTEXT_NO_IMAGE = 'This picture could not be loaded right now.'
export const CONTEXT_CREDIT = 'Pictures: the Aladin sky atlas (CDS, Strasbourg).'

/** The surveys, by the id ContextView uses, with their years (verified dates of each survey). */
export const SURVEY_WORDS: Record<string, { label: string; sentence: string }> = {
  wise: {
    label: 'WISE, infrared (2010 and 2011)',
    sentence: 'WISE took these in 2010 and 2011, long before SPHEREx, so they show what was here before.',
  },
  '2mass': {
    label: '2MASS, near infrared (1997 to 2001)',
    sentence: '2MASS took these from 1997 to 2001, so they show what was here long before SPHEREx.',
  },
  dss: {
    label: 'DSS, visible light (photos from decades ago)',
    sentence: 'These are scans of old photos on glass, taken decades ago, so they show what was here then.',
  },
}

/** The full Moon is about half a degree wide. */
const MOON_DEGREES = 0.5

/**
 * What the visitor is looking at. The rule: which survey is on screen and when it was taken (an
 * old picture shows what was there before SPHEREx looked), and how big the SPHEREx patch is,
 * from the view's own field of view, against the full Moon.
 */
export function contextResult(surveyId: string, fov: number): string[] {
  const survey = SURVEY_WORDS[surveyId]
  const moon = fov / MOON_DEGREES
  const size = moon > 1.15 ? `about ${factor(moon)} times the width of the full Moon` : moon >= 0.9 ? 'about the width of the full Moon' : `about ${shareWords(moon)} of the width of the full Moon`
  return [...(survey ? [survey.sentence] : []), `The orange square is ${fov} degrees across, ${size}.`]
}
