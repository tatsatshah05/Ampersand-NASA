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
import type { Target } from './api'
import { compassWord, dateSpan, monthYearLong } from './wording'

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
  // The lightcurve's own word for "no motion was given, and no Gaia star (G < 17) is within 3
  // arcseconds" (backend/photometry.py): only that was checked, so only that is said. Other
  // catalogues may well list the object (the search panel says so when they do).
  if (data.measured?.what === 'fixed_position') {
    out.push(
      /Gaia did not answer/.test(data.measured.description ?? '')
        ? 'Gaia, the star map we follow stars with, did not answer, so we measured one fixed spot.'
        : 'Gaia lists no star bright enough to follow within 3 arcseconds, so we measured one fixed spot.',
    )
  }
  const failed = data.failures?.length ?? 0
  if (failed > 0) out.push(`${count(failed, 'photo', 'photos')} could not be downloaded, so ${failed === 1 ? 'it is' : 'they are'} missing.`)
  return out
}

/** What "overexposed" means, said where the word first appears in a panel. */
export const OVEREXPOSED_MEANS = 'Overexposed means too bright for the camera: that part turns flat white, like a phone photo of a lamp.'

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

/** The words of a hovered dot: "1.02 times its usual brightness, give or take 0.03". */
export const brightnessTip = (value: number, err: number | null, m: Measure = 'flux') =>
  `${value.toFixed(2)} times ${m === 'wing' ? 'the usual light just around it' : 'its usual brightness'}${err !== null ? `, give or take ${err.toFixed(2)}` : ''}`

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
  const decided = (s: DetectorSummary) => s.verdict !== 'too few bins'
  return bands.flatMap((band): BandVerdict[] => {
    const f = flux.find((s) => s.detector === band)
    const w = wing.find((s) => s.detector === band)
    if (f && decided(f)) return [{ ...f, measure: 'flux' as const }]
    if (w && decided(w)) return [{ ...w, measure: 'wing' as const }]
    if (f) return [{ ...f, measure: 'flux' as const }]
    return w ? [{ ...w, measure: 'wing' as const }] : []
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

/**
 * The month of a visit: the middle date of its photos that have a value to compare, "September
 * 2025"; only those of the given bands when they are named (a visit lasts weeks, and each band is
 * photographed on its own days, so the month is that of the photos the sentence compares).
 */
export function visitMonth(data: LightcurveResponse, epoch: number, bands?: number[]): string {
  const valued = (p: { relative_flux: number | null; relative_wing: number | null }) => p.relative_flux !== null || p.relative_wing !== null
  const dates = (data.bins ?? [])
    .filter((b) => !bands || bands.includes(b.detector))
    .flatMap((b) => b.points.filter((p) => p.epoch === epoch && valued(p)).map((p) => p.date))
    .sort()
  return dates.length ? monthYearLong(dates[Math.floor((dates.length - 1) / 2)]) : `visit ${epoch}`
}

/** "between June 2025 and June 2026", "between February and July 2026". */
export function monthsBetween(from: string, to: string): string {
  const [fm, fy] = from.split(' ')
  const [, ty] = to.split(' ')
  return fy && ty && fy === ty && from !== to ? `between ${fm} and ${to}` : `between ${from} and ${to}`
}

/**
 * A brightening as a factor: "about 1.6 times as bright", "about 20 per cent brighter", "about
 * 4.5 to 13 times as bright". From 20 times up no factor is given ("many times as bright", or
 * "at least 14 times as bright"): it is measured against a level near the noise, where a small
 * error in the earlier reading makes a large change in the factor.
 */
export const MANY_TIMES = 20
export function brighterWords(ratios: number[]): string {
  const lo = Math.min(...ratios)
  const hi = Math.max(...ratios)
  if (hi < 1.3) {
    const [a, b] = [Math.round((lo - 1) * 100), Math.round((hi - 1) * 100)]
    return a === b ? `about ${a} per cent brighter` : `about ${a} to ${b} per cent brighter`
  }
  if (lo >= MANY_TIMES) return 'many times as bright'
  if (hi >= MANY_TIMES) return lo < 1.3 ? 'up to many times as bright' : `at least ${factor(lo)} times as bright`
  if (factor(lo) === factor(hi)) return `about ${factor(hi)} times as bright`
  return lo < 1.3 ? `up to about ${factor(hi)} times as bright` : `about ${factor(lo)} to ${factor(hi)} times as bright`
}

/** The simple fractions a fading is said in, nearest first. */
const FRACTIONS: [number, string][] = [
  [2 / 3, 'two thirds'],
  [1 / 2, 'half'],
  [1 / 3, 'a third'],
  [1 / 4, 'a quarter'],
  [1 / 5, 'a fifth'],
  [1 / 6, 'a sixth'],
  [1 / 8, 'an eighth'],
  [1 / 10, 'a tenth'],
]
const LESS_THAN_A_TENTH = 'less than a tenth'

/** A ratio below 1 as the nearest simple fraction of the earlier brightness, or null when "per cent fainter" says it better. */
export function fraction(r: number): string | null {
  if (r > 0.72) return null
  if (r < 0.075) return LESS_THAN_A_TENTH
  return FRACTIONS.reduce((a, b) => (Math.abs(b[0] - r) < Math.abs(a[0] - r) ? b : a))[1]
}

/** "about" before a fraction, never before "less than a tenth". */
const aboutFraction = (f: string) => (f === LESS_THAN_A_TENTH ? f : `about ${f}`)

/** "about half as bright", "about 10 per cent fainter", "about a third to half as bright", "less than a tenth to about a quarter as bright". */
export function fainterWords(ratios: number[]): string {
  const lo = Math.min(...ratios)
  const hi = Math.max(...ratios)
  const [fl, fh] = [fraction(lo), fraction(hi)]
  if (fl === null && fh === null) {
    const [a, b] = [Math.round((1 - hi) * 100), Math.round((1 - lo) * 100)]
    return a === b ? `about ${a} per cent fainter` : `about ${a} to ${b} per cent fainter`
  }
  if (fl === fh) return `${aboutFraction(fl as string)} as bright`
  if (fh === null) return `down to ${aboutFraction(fl as string)} as bright`
  return `${aboutFraction(fl as string)} to ${fl === LESS_THAN_A_TENTH ? `about ${fh}` : fh} as bright`
}

/** Whether most clean measurements are under 3 times their own error: the page's "not seen" bar (guide.ts). */
function mostlyTooFaint(data: LightcurveResponse): boolean {
  const ok = (data.bins ?? []).flatMap((b) => b.points.filter((p) => p.status === 'ok' && p.flux_mjy !== null && p.flux_err_mjy))
  return ok.length > 0 && ok.filter((p) => (p.flux_mjy as number) > 3 * (p.flux_err_mjy as number)).length < ok.length / 2
}

/**
 * How many photos show the object at all: every photo of the answer but those where it is off
 * the edge of the picture. The colour tool counts the same photos, so both panels give one total.
 */
export function photosOfIt(data: { n_exposures?: number; status_counts?: Record<string, number> }): number {
  return Math.max(0, (data.n_exposures ?? 0) - (data.status_counts?.off_image ?? 0))
}

/** Bands that changed the same way between the same two visits, read in the same measure. */
interface ChangeGroup {
  verdict: 'brighter' | 'fainter'
  measure: Measure
  firstEpoch: number
  lastEpoch: number
  bands: BandVerdict[]
}

function changeGroups(changed: BandVerdict[]): ChangeGroup[] {
  const groups: ChangeGroup[] = []
  for (const v of changed) {
    const verdict = v.verdict === 'brighter' ? 'brighter' : 'fainter'
    const g = groups.find((x) => x.verdict === verdict && x.measure === v.measure && x.firstEpoch === v.firstEpoch && x.lastEpoch === v.lastEpoch)
    if (g) g.bands.push(v)
    else groups.push({ verdict, measure: v.measure, firstEpoch: v.firstEpoch, lastEpoch: v.lastEpoch, bands: [v] })
  }
  return groups.sort((a, b) => a.firstEpoch - b.firstEpoch || a.lastEpoch - b.lastEpoch)
}

/** "bands 2, 5 and 6", "band 1". */
const bandWords = (bands: number[]) => (bands.length === 1 ? `band ${bands[0]}` : `bands ${listAnd(bands.map(String))}`)

/**
 * What the brightness tool shows for this object, in a few short sentences.
 *
 * The rule: only the tool's own same-colour comparison is used (`bandVerdicts`), never the
 * brightness of each visit's picture, which samples different colours in every visit. When a
 * band got brighter or fainter by that rule: by about how much (the median change of its
 * wavelength bins, as Expert's table gives it), between which months (the two visits that band
 * compared), and in which of SPHEREx's colours. Bands that compared different visits, or changed
 * in opposite directions, are said in sentences of their own, each with its own months; when one
 * colour group would then be named twice, the bands are named by number instead. When the rule
 * found no change: "no clear change", the rule's own verdict (Expert: "does not show a clear
 * change"); a change under its 5 per cent bar, or one most bins do not agree on, is not called a
 * change, so it is not said to be absent either. When it could decide nothing: why (overexposed,
 * too faint, one visit only, or too few photos of the same colour in two visits).
 */
export function brightnessResult(data: LightcurveResponse): string[] {
  const total = photosOfIt(data)
  const overexposed = data.status_counts?.saturated ?? 0
  const out: string[] = []
  // "Most photos overexposed" is said first, whatever follows, with what the word means.
  const tooBright = total > 0 && overexposed > total / 2
  if (tooBright) {
    out.push(
      overexposed === total
        ? `All ${total} of its photos are overexposed: it is too bright to measure directly.`
        : `${overexposed} of its ${total} photos are overexposed: it is too bright there to measure directly.`,
    )
    out.push(OVEREXPOSED_MEANS)
  }

  const bands = bandVerdicts(data)
  const decided = bands.filter((v) => v.verdict !== 'too few bins')
  const changed = decided.filter((v) => v.verdict === 'brighter' || v.verdict === 'fainter')

  if (changed.length > 0) {
    const groups = changeGroups(changed)
    const up = groups.some((g) => g.verdict === 'brighter')
    const down = groups.some((g) => g.verdict === 'fainter')
    const how = up && down ? 'It changed' : up ? 'It got brighter' : 'It got fainter'
    const words = (g: ChangeGroup) => (g.verdict === 'brighter' ? brighterWords : fainterWords)(g.bands.map((v) => 1 + v.medianChange))
    const what = (g: ChangeGroup) => (g.measure === 'wing' ? 'the light just around it' : 'it')
    const months = (g: ChangeGroup) => {
      const which = g.bands.map((v) => v.detector)
      return monthsBetween(visitMonth(data, g.firstEpoch, which), visitMonth(data, g.lastEpoch, which))
    }
    const sameVisits = groups.every((g) => g.firstEpoch === groups[0].firstEpoch && g.lastEpoch === groups[0].lastEpoch)
    if (sameVisits) {
      // One pair of visits for all: said once, then each change in its colours. The months are
      // those of every band compared, as before.
      const all = changed.map((v) => v.detector)
      out.push(`${how} ${monthsBetween(visitMonth(data, groups[0].firstEpoch, all), visitMonth(data, groups[0].lastEpoch, all))}.`)
      const named = groups.map((g) => colourWords(g.bands.map((v) => v.detector)))
      groups.forEach((g, i) => {
        const where = named.filter((n) => n === named[i]).length > 1 ? bandWords(g.bands.map((v) => v.detector)) : named[i]
        out.push(`In ${where} ${what(g)} became ${words(g)}.`)
      })
    } else {
      // Different visits compared: each change with its own months. A colour group named in two
      // of these sentences is named by its bands instead, so no group is said both to brighten and fade.
      const groupsOf = (g: ChangeGroup) => GROUPS.filter((c) => g.bands.some((v) => groupOf(v.detector) === c))
      const shared = (g: ChangeGroup) => groups.some((o) => o !== g && groupsOf(o).some((c) => groupsOf(g).includes(c)))
      out.push(`${how} between its visits.`)
      for (const g of groups) {
        const which = g.bands.map((v) => v.detector)
        const where = shared(g) ? bandWords(which) : colourWords(which)
        out.push(`${capital(months(g))}, ${what(g)} got ${g.verdict} in ${where}.`)
        out.push(`${capital(what(g))} became ${words(g)} there.`)
      }
    }
    if (changed.some((v) => v.measure === 'wing')) out.push('Where it is overexposed, we measured the light in a ring just around it.')
    return out
  }
  if (decided.length > 0) {
    const ring = decided.every((v) => v.measure === 'wing')
    out.push(
      ring
        ? tooBright
          ? 'So we measured the light just around it, which showed no clear change between its visits.'
          : 'We measured the light just around it, which showed no clear change between its visits.'
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
export const SPECTRUM_AXIS_Y = 'Higher is brighter'
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
 * pixel or another problem, from the answer's own counts. When most were overexposed, where on
 * the chart the few measured ones are; when most measured ones are under 3 times their own error
 * (the page's "not seen" bar), that it is too faint to see in most of them.
 */
export function spectrumResult(data: SpectrumResponse): string[] {
  const n = data.n_exposures ?? 0
  const counts = data.status_counts ?? {}
  const ok = counts.ok ?? 0
  const sat = counts.saturated ?? 0
  const rest = n - ok - sat
  if (n === 0) return ['SPHEREx has no photo of this spot yet.']
  if (ok === n) return [`All ${n} of its photos could be measured.`, ...faintNote(data)]
  if (ok === 0) {
    return sat === n
      ? [`It is too bright: all ${n} of its photos are overexposed, so none could be measured.`, OVEREXPOSED_MEANS]
      : [`None of its ${n} photos gave a clean measurement.`]
  }
  // Nearly all overexposed (three quarters or more): said that way, with where the few measured ones are.
  if (sat >= 0.75 * n) {
    const out = [`It is so bright that it dazzles SPHEREx's camera: ${sat} of its ${n} photos are overexposed.`, OVEREXPOSED_MEANS]
    const measured = (data.points ?? []).filter((p) => p.status === 'ok' && p.wavelength_um !== null).map((p) => p.wavelength_um as number)
    const right = measured.length > 0 && Math.min(...measured) >= 3
    out.push(`Only ${ok} could be measured${right ? ': the dots on the right, in its longest colours' : ''}.`)
    if (rest > 0) out.push(`${rest} had a bad pixel or another problem.`)
    return out
  }
  const out = [`${ok} of its ${n} photos could be measured.`]
  if (sat > 0) out.push(`${sat} ${sat === 1 ? 'was' : 'were'} overexposed, because it is too bright there.`)
  if (rest > 0) out.push(`${rest} had a bad pixel or another problem.`)
  if (sat > 0) out.push(OVEREXPOSED_MEANS)
  return [...out, ...faintNote(data)]
}

/** "In most of them it is too faint to see.": most clean readings under 3 times their own error. */
function faintNote(data: SpectrumResponse): string[] {
  const ok = (data.points ?? []).filter((p) => p.status === 'ok' && p.flux_mjy !== null && p.flux_err_mjy)
  const faint = ok.filter((p) => (p.flux_mjy as number) < 3 * (p.flux_err_mjy as number)).length
  return ok.length > 0 && faint > ok.length / 2 ? ['In most of them it is too faint to see.'] : []
}

// ---- Find changes (the blind search of a patch) --------------------------------------------

export const SEARCH_TITLE = 'Did anything here move or change?'
export const SEARCH_INTRO =
  'The computer compares every point of light in this patch between visits. Most things it finds are already known, or are false alarms.'
export const SEARCH_WAITING = 'Searching this patch. It takes under a minute if its photos are here already, or a few minutes if not.'
export const SEARCH_FAILED = 'The search could not finish:'
export const SEARCH_LOOK = 'Show it on the picture'

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
  // A change with warning signs (the tool's "caution") is said as one that may have happened.
  const changedSure = objects.filter((o) => !MOVED(o) && o.verdict !== 'caution').length
  const changedUnsure = objects.filter((o) => !MOVED(o) && o.verdict === 'caution').length
  const known = objects.filter((o) => KNOWN.includes(o.catalogue_status.category)).length
  const candidates = objects.filter(isCandidate)
  const out = [`It tested ${count(s.sources_tested, 'point', 'points')} of light in this patch.`]
  if (!objects.length) out.push('Nothing moved or changed enough to pass its tests.')
  else {
    const m = moved === 0 ? 'Nothing moved' : `${count(moved, 'thing', 'things')} moved`
    if (changedUnsure === 0) out.push(`${m}, and ${changedSure === 0 ? 'nothing changed brightness' : `${count(changedSure, 'thing', 'things')} changed brightness`}.`)
    else {
      out.push(`${m}.`)
      out.push(
        changedSure === 0
          ? `${count(changedUnsure, 'thing', 'things')} may have changed brightness, but ${changedUnsure === 1 ? 'it has' : 'they have'} warning signs.`
          : `${count(changedSure, 'thing', 'things')} changed brightness, and ${changedUnsure} more may have: ${changedUnsure === 1 ? 'it has' : 'they have'} warning signs.`,
      )
    }
  }
  if (known > 0) out.push(known === objects.length ? (known === 1 ? 'It is already known in star catalogues.' : 'All of them are already known in star catalogues.') : `${known} ${known === 1 ? 'is' : 'are'} already known in star catalogues.`)
  if (candidates.length > 0) {
    const how = candidates.every(MOVED) ? 'moving' : candidates.some(MOVED) ? 'moving or changing' : 'changing'
    const n = candidates.length
    out.push(`${n} ${n === 1 ? 'is' : 'are'} not listed as ${how} in any catalogue we asked, so ${n === 1 ? 'it is' : 'each is'} only a candidate.`)
    out.push(`Scientists may already have written about ${n === 1 ? 'it' : 'them'}: we did not search their papers.`)
    out.push(`Another telescope, or SPHEREx’s next visits, would be needed to confirm ${n === 1 ? 'it' : 'them'}.`)
  }
  const unchecked = objects.length - known - candidates.length
  if (unchecked > 0) out.push(`${unchecked} could not be checked against the catalogues.`)
  if (result.rejected.length > 0) out.push(result.rejected.length === 1 ? '1 more was set aside as a false alarm.' : `${count(result.rejected.length, 'more was', 'more were')} set aside as false alarms.`)
  if (Object.keys(s.catalogues_failed).length > 0) out.push('Some catalogues did not answer, so this check is not complete.')
  return out
}

/** Each warning sign of the search (search.ts FLAG_WORDS) in a short plain sentence. */
const PLAIN_FLAGS: Record<string, string> = {
  saturated: 'It is so bright that it overflows the camera, so its place is less exact.',
  halo: 'It sits in the glow of a much brighter star, which can fake a change.',
  blended: 'Another star right beside it may mix its light in.',
  wide: 'It looks wider than a star: it may be two things, or a galaxy.',
  edge: 'It is near the edge of the picture, where measuring is harder.',
  few_exposures: 'One of its visits has only a few photos.',
  two_visits: 'Only two visits could be used, which is too few to be sure.',
  follows_roll: 'The change may be light from a bright star nearby.',
  one_roll_only: 'It may be a reflection inside the telescope.',
  uncalibrated: 'The computer could not check how exact this measurement is.',
}

/** The warning signs of one object, in plain words; one sentence for any sign this page does not know. */
export function flagWords(flags: string[]): string[] {
  const known = flags.filter((f) => f in PLAIN_FLAGS).map((f) => PLAIN_FLAGS[f])
  return flags.some((f) => !(f in PLAIN_FLAGS)) ? [...known, 'The computer has another reason to be less sure.'] : known
}

/** One numbered line per object, matching the numbered rings on the picture. */
export function searchItem(o: SearchObject): string {
  const what = MOVED(o) ? 'Moved' : o.verdict === 'caution' ? 'May have changed brightness' : 'Changed brightness'
  const known = KNOWN.includes(o.catalogue_status.category) ? 'Already known' : isCandidate(o) ? 'Only a candidate' : 'Not checked against catalogues'
  const signs = o.verdict === 'caution' ? flagWords(o.flags) : []
  return [`${what}.`, `${known}.`, ...(o.verdict === 'caution' && !signs.length ? ['The computer is less sure about this one.'] : signs)].join(' ')
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
  if (q <= 0.6) return `${aboutFraction(fraction(q) ?? 'half')} as bright as WISE 0855`
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

/** "twice", "3 times": how many times as wide one patch is as another. */
const timesWide = (k: number) => (Math.abs(k - 2) < 0.05 ? 'twice' : `${factor(k)} times`)

/**
 * What the distant-world search found here. The rule: whether anything was found (the answer's
 * own status), how far away it can see one at all (the nearest distance of its table: a nearer
 * planet jumps further than the patch is wide, so it is not searched for), how faint it could
 * reach (its best limit: the row of its table with the faintest brightness, said against WISE
 * 0855, and the share of the patch that same row covered, so the two numbers always belong
 * together), and always that finding nothing here rules nothing out elsewhere. The share is of
 * the patch searched, which is wider than the picture when the picture is small (`viewFov`). A
 * link is a candidate and needs another telescope.
 */
export function distantResult(r: DistantResult, viewFov?: number): string[] {
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
    const au = r.limit.map((row) => row.distance_au)
    out.push(`It can only catch one between ${Math.min(...au).toLocaleString('en-US')} and ${Math.max(...au).toLocaleString('en-US')} times as far from the Sun as Earth.`)
    out.push('A nearer planet would jump right out of the patch between visits.')
    out.push(`The faintest planet it could catch is ${faintWords(best.faintest_mjy)}.`)
    const wider = viewFov !== undefined && r.fov > viewFov * 1.05
    out.push(`At best it could catch one that faint in about ${shareWords(best.share_of_picture)} of the patch it searched.`)
    if (wider && viewFov) out.push(`That patch is ${timesWide(r.fov / viewFov)} as wide as the picture.`)
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
  // When NASA did not answer every question, only the photos it answered for are spoken of.
  else if (!groups.length)
    out.push(
      data.problems.length > 0
        ? `No known asteroid or comet was in this patch in the photos NASA answered for.`
        : `No known asteroid or comet was in this patch during any of the ${data.n_exposures_checked} photos we checked.`,
    )
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

/**
 * The middle year of each survey's pictures, for the objects that move: AllWISE combines WISE's
 * photos of January 2010 to February 2011, and 2MASS observed from 1997 to 2001 (SURVEY_WORDS).
 * DSS has none: its plates span decades.
 */
export const SURVEY_YEAR: Record<string, number> = { wise: 2010.5, '2mass': 1999 }
/** SPHEREx's own visits, about when the page's positions are given for (resolve.ts: "moved to 2026"). */
const SPHEREX_YEAR = 2026

/** Where a target's catalogue motion puts it in `year`, in arcseconds east and north of `centre`. */
export function placeIn(target: Pick<Target, 'ra' | 'dec' | 'pmra' | 'pmdec' | 'ref_epoch'>, year: number, centre: { ra: number; dec: number }) {
  const dt = year - target.ref_epoch
  const dec = target.dec + (((target.pmdec ?? 0) / 1000) * dt) / 3600
  const ra = target.ra + (((target.pmra ?? 0) / 1000) * dt) / 3600 / Math.cos((target.dec * Math.PI) / 180)
  const dRa = ((ra - centre.ra + 540) % 360) - 180
  const east = dRa * Math.cos((centre.dec * Math.PI) / 180) * 3600
  const north = (dec - centre.dec) * 3600
  return { east, north, total: Math.hypot(east, north) }
}

/** An offset this large is plainly seen in the older picture (WISE's sharpness is about 6 arcseconds). */
const SEEN_APART_ARCSEC = 30

/**
 * Then and now, for an object that moves: where its catalogue motion puts it in the older picture
 * on screen, against the middle of the orange square (the centre of the view), and that it has
 * moved that far since. Said only when the motion is known, the survey has one year, and the
 * place differs by more than the older picture can blur; empty otherwise. Every number is the
 * catalogue motion's, from the answer's own target.
 */
export function thenAndNow(
  surveyId: string,
  target: Target | null,
  centre: { ra: number; dec: number },
  name: string | null,
  level: 'beginner' | 'expert',
): string[] {
  const year = SURVEY_YEAR[surveyId]
  if (year === undefined || !target || target.pmra == null || target.pmdec == null) return []
  const then = placeIn(target, year, centre)
  const now = placeIn(target, SPHEREX_YEAR, centre)
  const moved = Math.hypot(then.east - now.east, then.north - now.north)
  if (then.total < SEEN_APART_ARCSEC || moved < SEEN_APART_ARCSEC) return []
  const arcmin = (then.total / 60).toFixed(1)
  const nearMiddle = now.total < 15
  if (level === 'expert') {
    const pa = Math.round(((((Math.atan2(then.east, then.north) * 180) / Math.PI) % 360) + 360) % 360) % 360
    const pm = (Math.hypot(target.pmra, target.pmdec) / 1000).toFixed(2)
    return [
      `At ~${year} the catalogue motion (${pm}″/yr) puts the target ${arcmin}′ from the field centre at PA ${pa}°${nearMiddle ? `; at ${SPHEREX_YEAR}.0 it is at the centre` : ''}.`,
    ]
  }
  const who = name ?? 'the object'
  // The full Moon is about 31 arcminutes wide.
  const share = moved / 60 / 31
  const moon = share < 0.075 ? 'less than a tenth' : `about ${shareWords(share)}`
  return [
    // Where its motion puts it, not whether it shows: a faint one may not be seen in an older survey.
    `When this picture was taken, about ${Math.floor(year)}, ${who} was about ${arcmin} arcminutes ${compassWord(then)} of the square's middle.`,
    `It has moved ${nearMiddle ? 'that far' : `about ${(moved / 60).toFixed(1)} arcminutes`} since then: ${moon} of the full Moon's width.`,
    ...(nearMiddle ? ['SPHEREx sees it in the middle of the square.'] : []),
  ]
}
