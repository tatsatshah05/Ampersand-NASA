// The "Three tools" screen (?tools=1): its address, the loading of its three data files
// (/lab/reflex.json, /lab/colourwalk.json, /lab/transits.json, written by scripts/export_lab.py
// and shipped with the frontend build), and the pure functions that turn their fields into the
// numbers, ranges, chips and verdict sentences on the screen. Nothing here is typed in as a
// result: every number comes from a file, and every sentence comes from toolsWording.ts, chosen
// by the rules of the build spec (section 11) and the final checked results.
//
// A value that is missing (absent, or null with a `why`) never reaches the page as "undefined",
// "NaN" or a placeholder: the sentence that needs it is left out (see `fill`).
import { useEffect, useState } from 'react'
import { addressOf, readAddress, type Selection } from './address'
import { NATIVE_PIXEL_ARCSEC } from './api'
import { realSkyAddress } from './training'
import { PAGE, SCI, T1, T2, T3 } from './toolsWording'

// ---------------------------------------------------------------------------------- address

export const isToolsAddress = (search: string) => new URLSearchParams(search).has('tools')

/**
 * The screen's address, carrying the whole view the visitor came from (its place, name, motion,
 * detector, field and mode), so the way back shows that same view: one of our candidates held
 * still at its place in its own detector, not the brightest spot near it.
 */
export function toolsAddress(s: Selection): string {
  return `?tools=1&${addressOf({ ...s, train: null }).slice(1)}`
}

/** Back to the sky viewer: to the place the visitor came from, when the address carries one. */
export function toolsBackAddress(search: string): string {
  const p = new URLSearchParams(search)
  if (!p.has('ra') || !p.has('dec')) return '/'
  return realSkyAddress(readAddress(search).selection)
}

// ---------------------------------------------------------------------------------- the files

type Num = number | null | undefined
type Pair = [number, number | null] | null | undefined
/** Any object in a file may say why one of its values is missing: `why: {field: reason}`. */
interface Whys {
  why?: Record<string, string> | null
}

export interface ReflexStop extends Whys {
  inv_d: number
  distance_au?: Num
  snr?: Num
  /** The dot's path (arcsec east and north of the reference place) and the straight, steady path. */
  track_east?: number[] | null
  track_north?: number[] | null
  linear_east?: number[] | null
  linear_north?: number[] | null
}

/** One paragraph: sentences that run on in one block. */
export type Para = string[]

export interface ReflexFile extends Whys {
  fixture?: boolean
  final?: boolean
  /** The analysis choices were made after an earlier look had found the answer (docs/reflex.md). */
  development_object?: boolean | null
  checks?: Record<string, unknown> | null
  pixel_arcsec?: Num
  visit?: { n_used?: Num; duration_days?: Num; mjd_first?: Num; mjd_last?: Num; mjd_t0?: Num; distance_leverage_arcsec_per_inv_au?: number[] | null } & Whys
  field?: { ra?: Num; dec?: Num; size_deg?: Num; centred_on_known?: boolean | null } & Whys
  n_trials?: Num
  candidate?: {
    separation_arcsec?: Num
    distance_au?: Num
    /** About 95%: the epoch-bootstrap 95% range [low, high], high null when unbounded. */
    range_95_au?: Pair
    range_68_au?: Pair
    interval_2sigma_au_statistical_only?: Pair
    snr?: Num
    snr_at_infinity?: Num
    delta_s2_infinite?: Num
    leave_one_epoch_out_min_delta_s2?: Num
    n_epochs?: Num
    n_bootstrap?: Num
    reversed_earth_snr_mirror_distance?: Num
    reversed_best_away?: Num
    drift_arcsec_day?: number[] | null
    mean_flux_mjy?: Num
    /** The review's measurement of the earliest day (docs/reflex.md): its share of the bend, and its bright neighbour. */
    first_day?: { info_share?: Num; n_exposures?: Num; neighbour_arcsec?: Num; neighbour_as_bright?: boolean | null; available?: boolean | null } | null
  } & Whys
  jpl?: { observer_distance_au?: Num; helio_distance_au?: Num; linear_drift?: number[] | null; linear_drift_arcsec_day?: number[] | null; mid?: { ra?: Num; dec?: Num } | null } & Whys
  shifted?: { distance_au?: Num; range_95_au?: Pair; range_68_au?: Pair; separation_arcsec?: Num; snr?: Num; edge_reversed_peak?: Num; checks?: Record<string, unknown> | null } & Whys
  still_there?: { mjd_first: number; mjd_last: number; flux_mjy?: Num; error_mjy?: Num }[] | null
  limit?: {
    faintest_mean_flux_mjy?: Num
    searched_area_deg2?: Num
    distance_range_au?: (number | string)[] | null
    min_visit_days?: Num
    injection_tested?: boolean | null
    /** Farthest distance that still gets a distance: a number (for a body as bright as Eris), or the export's object. */
    ranging_limit_au?: Num | { eris_bright_au?: Num; at_threshold_au?: Num; available?: boolean | null }
    ranging_limit_at_threshold_au?: Num
    v_eris_coloured?: Num
    v_sedna_coloured?: Num
  } & Whys
  null_runs?: { n_field_visits?: Num; area_deg2?: Num; vetted_false?: Num } & Whys
  foldout?: {
    n_trials?: Num
    leverage_arcsec_per_inv_au?: number[] | null
    next_source_snr?: Num
    reversed_best_away_snr?: Num
    blank_field_raw_peaks?: { n_field_visits?: Num } | null
  } | null
  sedna?: { found_blind?: boolean | null; forced_snr?: Num; threshold?: Num } & Whys
  demo?: {
    crop_px?: Num
    pixel_arcsec?: Num
    uses_difference_images?: boolean | null
    /** "difference_images" when a star trail crosses Eris's place, so the stars were removed first. */
    made_from?: string | null
    single?: { png?: string | null; mjd?: Num } | null
    plain_mean?: { png?: string | null } | null
    slid?: { png?: string | null } | null
    /** Pixels with no data, or blanked by the search's own mask (bright fixed stars), drawn flat grey. */
    blank_pixels?: { single?: Num; plain_mean?: Num; slid?: Num } | null
    marks?: { tool_dot_px?: number[] | null; nasa_single_px?: number[] | null; nasa_mid_px?: number[] | null; nasa_path_px?: number[][] | null } | null
  } & Whys
  stops?: ReflexStop[] | null
  wrong_way?: ReflexStop | null
  sketch_exaggeration?: Num
}

export interface ColourGroup extends Whys {
  name: string
  lo_um?: Num
  hi_um?: Num
  png?: string | null
  /** Centre of this group's light, arcsec east and north (the screen subtracts the Bluer group). */
  east?: Num
  north?: Num
  /** This group's own 1σ, measured floor included; the inset's ring adds the Bluer group's in quadrature. */
  err_east?: Num
  err_north?: Num
}

export interface ColourFile extends Whys {
  fixture?: boolean
  final?: boolean
  pixel_arcsec?: Num
  development_object_note?: string | null
  verdict?: string | null
  rule_sigma?: Num
  known?: { sep_arcsec?: Num; pa_deg?: Num } & Whys
  n_exposures?: Num
  n_clean_fits?: Num
  walk?: {
    all?: { east?: Num; north?: Num; pa?: Num; size?: Num; sigma?: Num; p_false?: Num; pa_error_deg?: Num; err_east?: Num; err_north?: Num } & Whys
    sigma_guessed_floor?: Num
    detector_fixed_arcsec?: Num | { size?: Num; x?: Num; y?: Num }
    per_detector?: Record<string, { pa?: Num; size?: Num; sigma?: Num }> | null
  } & Whys
  visit_walks?: { sky_angle?: Num; detector_angle?: Num; size?: Num }[] | null
  acceptance?: { checks?: Record<string, boolean> | null; passed?: boolean | null } & Whys
  null?: {
    acceptance?: { checks?: Record<string, boolean> | null; passed?: boolean | null } | null
    scatter_east?: Num
    scatter_north?: Num
    n_within?: Num
    n_isolated?: Num
    /** Null-field stars whose centres walked over 4 times their usual error, with what may explain each. */
    walkers_over_4sigma?: { walk_arcsec?: Num; sigma?: Num; neighbour_kind?: string | null }[] | null
  } & Whys
  picture?: { crop_px?: Num; host_px?: number[] | null; pixel_arcsec?: Num } & Whys
  groups?: ColourGroup[] | null
  lone_star?: { available?: boolean | null; walk_size?: Num; gaia_id?: string | null; gmag?: Num; walk?: { sigma?: Num } | null; groups?: ColourGroup[] | null } | null
}

export interface TransitReading {
  bjd_tdb: number
  rel_flux: number
  err?: Num
}

export interface TransitStop {
  period_d: number
  known?: boolean | null
  depth?: Num
  /** The module's formal error at this period; the screen scales it by d5.noise_factor. */
  err?: Num
  n_in?: Num
  why?: string | Record<string, string> | null
}

export interface TransitFile extends Whys {
  fixture?: boolean
  final?: boolean
  development_object?: boolean | null
  planet?: { period_d?: Num; t0_bjd_tdb?: Num; t14_h?: Num; rprs?: Num; expected_depth?: Num; ra?: Num; dec?: Num; published_depth_range_pct?: number[] | { available?: boolean | null } | null } & Whys
  coverage?: { exposures?: Num; per_detector?: Record<string, Num> | null } & Whys
  /** SPHEREx's detectors, each one band of colours. */
  detectors?: Record<string, unknown> | null
  /** Radius of the measuring circle, in squares (the module's APERTURE_PX). */
  aperture_px?: Num
  d5?: {
    n?: Num
    n_in?: Num
    n_transits?: Num
    n_cutouts?: Num
    depth?: Num
    formal_err?: Num
    empirical_err?: Num
    empirical_sigma?: Num
    noise_factor?: Num
    n_fake?: Num
    fake_share_as_deep?: Num
    scatter?: Num
    slide_peak_h?: Num
    jackknife_min?: Num
    jackknife_max?: Num
    wl_min?: Num
    wl_max?: Num
    years?: Record<string, { depth?: Num; formal_err?: Num }> | null
    n_fake_as_deep?: Num
    deepest_fake_depth?: Num
    /** The reviewer's count of independent fakes (they overlap), from docs/transits.md. */
    fakes_independent?: { share_of_pairs_sharing_a_reading?: Num; n_independent_about?: Num; p_below?: Num; available?: boolean | null } | null
    sign_test?: { n_transits?: Num; n_below_baseline?: Num; p_value?: Num } | null
    choices?: Record<string, Num> | null
  } & Whys
  halo?: { depth?: Num; empirical_err?: Num; empirical_sigma?: Num; n_in?: Num } & Whys
  acceptance?: { A1?: boolean | { passed?: boolean | null } | null; A2?: boolean | { passed?: boolean | null } | null } & Whys
  aperture_radius_px?: Record<string, Num> | null
  min_in_transit?: Num
  window_h?: Num
  comparison?: { gmag?: Num; distance_arcsec?: Num; depth?: Num; err?: Num } & Whys
  wasp100?: {
    expected_depth?: Num
    combined?: { depth?: Num; error?: Num; detectors?: number[] | null } | null
    per_detector?: Record<string, { depth?: Num; empirical_err?: Num; empirical_sigma?: Num; excluded?: string | null }> | null
    n_clear?: Num
  } & Whys
  readings?: TransitReading[] | null
  stops?: TransitStop[] | null
  picture?: { png?: string | null; crop_px?: Num; star_px?: number[] | null } & Whys
  fallback_png?: string | null
}

export type LabName = 'reflex' | 'colourwalk' | 'transits'
export type Load<T> = { state: 'loading' } | { state: 'missing' } | { state: 'ready'; data: T }

export const labUrl = (file: string) => `/lab/${file.replace(/^\/+/, '')}`

/** Fetch one of the three data files; `attempt` changes to try again. */
export function useLab<T>(name: LabName, attempt: number): Load<T> {
  const [load, setLoad] = useState<{ key: string; value: Load<T> }>({ key: '', value: { state: 'loading' } })
  const key = `${name}|${attempt}`
  useEffect(() => {
    let live = true
    fetch(labUrl(`${name}.json`))
      .then((r) => (r.ok ? (r.json() as Promise<T>) : Promise.reject(new Error(String(r.status)))))
      .then((data) => live && setLoad({ key, value: data && typeof data === 'object' ? { state: 'ready', data } : { state: 'missing' } }))
      .catch(() => live && setLoad({ key, value: { state: 'missing' } }))
    return () => {
      live = false
    }
  }, [name, key])
  return load.key === key ? load.value : { state: 'loading' }
}

// ---------------------------------------------------------------------------------- helpers

const ok = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x)

/** Why a value is missing, if its file says: `why: {key: reason}` or `<key>_why: reason`. */
export function whyOf(obj: unknown, key: string): string | null {
  if (!obj || typeof obj !== 'object') return null
  const o = obj as Record<string, unknown>
  const map = o.why
  if (typeof map === 'string' && map) return map
  if (map && typeof map === 'object' && typeof (map as Record<string, unknown>)[key] === 'string') return (map as Record<string, string>)[key]
  const flat = o[`${key}_why`]
  return typeof flat === 'string' ? flat : null
}

class MissingSlot extends Error {}

/**
 * Fill a sentence from a record of formatted values. If the sentence asks for a value the record
 * lacks, the sentence is left out (null): a missing number hides its block, never shows "undefined".
 */
export function fill<V extends Record<string, string>>(fn: (v: V) => string, values: Partial<V>): string | null {
  const strict = new Proxy(values, {
    get(target, k) {
      if (typeof k !== 'string') return undefined
      const v = (target as Record<string, unknown>)[k]
      if (typeof v !== 'string' || v === '') throw new MissingSlot(k)
      return v
    },
  }) as V
  try {
    return fn(strict)
  } catch (e) {
    if (e instanceof MissingSlot) return null
    throw e
  }
}

const MINUS = '−'
/** A number to `d` decimals, with a true minus sign; `trim` drops a trailing ".0". */
export function fmt(x: Num, d = 0, trim = false): string | undefined {
  if (!ok(x)) return undefined
  const r = Math.round(x * 10 ** d) / 10 ** d
  let s = Math.abs(r).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d })
  if (trim && d > 0) s = s.replace(/\.0+$/, '')
  return r < 0 && Number(s.replace(/,/g, '')) !== 0 ? `${MINUS}${s}` : s
}
const fmtInt = (x: Num) => fmt(x, 0)
/** A lower bound, rounded down, so that "more than {x}" never claims more than the data. */
export const fmtDown = (x: Num, d = 0) => (ok(x) ? fmt(Math.floor(x * 10 ** d + 1e-9) / 10 ** d, d) : undefined)

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const mjdDate = (mjd: number) => new Date((mjd - 40587) * 86_400_000)

/** "July 2025", "July and August 2025", or "December 2025 and January 2026". */
export function monthsOf(first: Num, last: Num): string | undefined {
  if (!ok(first) || !ok(last)) return undefined
  const a = mjdDate(first)
  const b = mjdDate(last)
  const [ma, ya, mb, yb] = [a.getUTCMonth(), a.getUTCFullYear(), b.getUTCMonth(), b.getUTCFullYear()]
  if (ma === mb && ya === yb) return `${MONTHS[ma]} ${ya}`
  if (ya === yb) return `${MONTHS[ma]} and ${MONTHS[mb]} ${ya}`
  return `${MONTHS[ma]} ${ya} and ${MONTHS[mb]} ${yb}`
}

/** "10 July". */
export const dayMonth = (mjd: Num) => (ok(mjd) ? `${mjdDate(mjd).getUTCDate()} ${MONTHS[mjdDate(mjd).getUTCMonth()]}` : undefined)
const isoDate = (mjd: Num) => (ok(mjd) ? mjdDate(mjd).toISOString().slice(0, 10) : undefined)

const nonEmpty = (xs: (string | null | undefined)[]) => xs.filter((x): x is string => typeof x === 'string' && x.length > 0)
/** Paragraphs from groups of sentences: missing sentences dropped, then empty paragraphs. */
const paras = (...groups: (string | null | undefined)[][]): Para[] => groups.map(nonEmpty).filter((p) => p.length > 0)

/** A fold-out's entries: each one filled, those missing a value left out, empty paragraphs dropped. */
function sciParagraphs(paras: ((v: Record<string, string>) => string)[][], values: Record<string, string | undefined>): string[] {
  const clean: Record<string, string> = {}
  for (const [k, v] of Object.entries(values)) if (typeof v === 'string') clean[k] = v
  return paras.map((p) => nonEmpty(p.map((fn) => fill(fn, clean))).join(' ')).filter((p) => p.length > 0)
}

// ---------------------------------------------------------------------------------- ranges

export interface Range {
  lo: number
  hi: number | null
}

const asRange = (p: Pair): Range | null => (p && ok(p[0]) && (p[1] === null || ok(p[1])) ? { lo: p[0], hi: p[1] } : null)
const inside = (x: number, r: Range) => x >= r.lo && (r.hi === null || x <= r.hi)

/** The one range sentence (about 95%), with tools 1 and 3 feeding it the same way. */
export function rangeSentence(r: Range, d = 0): string {
  return r.hi === null ? PAGE.rangeAbove(fmtDown(r.lo, d) as string) : PAGE.rangeBetween(fmt(r.lo, d) as string, fmt(r.hi, d) as string)
}

// ---------------------------------------------------------------------------------- tool 1

export interface StopView {
  inv_d: number
  /** Written above the track and spoken as the slider's value. */
  label: string
  spoken: string
  delta: number | null
  line: string | null
  sketch: { track: [number, number][]; linear: [number, number][] } | null
  meterText: string | null
}

/** The number that matters, beside the verdict at the top of a tool: our value, and the known one. */
export interface Glance {
  ours: string
  known: string | null
  unit: string | null
}

export interface ReflexView {
  fixture: boolean
  final: boolean
  chip: string | null
  glance: Glance | null
  headline: string | null
  /** The test's text before the numbers row, as paragraphs. */
  test: Para[]
  numbers: { ours: string; range: string[]; nasa: string | null } | null
  ruler: { max: number; best: number; range: Range; r: number | null; summary: string | null } | null
  /** The sunlight line and the verdict sentences, as paragraphs. */
  after: Para[]
  howSure: Para[]
  appear: {
    count: string | null
    captions: [string, string | null, string]
    differenceImages: boolean
    pictures: ({ src: string } | { why: string })[]
    /** Whether each picture holds flat grey patches where bright stars were blanked out. */
    blanks: [boolean, boolean, boolean]
    cropPx: number | null
    marks: { tool: number[] | null; nasaSingle: number[] | null; nasaMid: number[] | null; nasaPath: number[][] | null }
  }
  distance: {
    stops: StopView[]
    wrong: StopView | null
    bestIndex: number
    nasaTick: number | null
    meter: { min: number; max: number } | null
    exaggeration: string | null
    startLabel: string | null
    endLabel: string | null
  } | null
  answerLine: string | null
  answers: { something: string; nothing: string | null; cannot: string | null; near: string | null; far: string | null; fainter: string | null }
  sedna: boolean
  sci: string[]
}

/** {half}: the search's limit against Eris's own brightness, as a fraction word. */
export function halfWord(limit: Num, eris: Num): string | 'as' | undefined {
  if (!ok(limit) || !ok(eris) || eris <= 0) return undefined
  const f = limit / eris
  if (f <= 0.4) return T1.half.third
  if (f <= 0.6) return T1.half.half
  return 'as'
}

/** {about half a year later, and again a year later}: the other visits, from the search visit's middle. */
export function otherVisitsPhrase(visitFirst: Num, visitLast: Num, others: { mjd_first: number; mjd_last: number }[] | null | undefined): string | undefined {
  if (!ok(visitFirst) || !ok(visitLast) || !others || others.length === 0) return undefined
  const mid = (visitFirst + visitLast) / 2
  const phrases = others.map((o) => {
    const dt = (o.mjd_first + o.mjd_last) / 2 - mid
    const months = Math.abs(dt) / 30.44
    const span = months >= 5 && months <= 7 ? T1.when.halfYear : months >= 11 && months <= 13 ? T1.when.year : T1.when.months(String(Math.round(months)))
    return dt >= 0 ? T1.when.later(span) : T1.when.earlier(span)
  })
  return phrases.length === 1 ? phrases[0] : T1.when.andAgain(phrases[0], phrases.slice(1).join(', and again '))
}

const sq = (x: number) => x * x

function stopSketch(s: ReflexStop, k: number): StopView['sketch'] {
  const { track_east: te, track_north: tn, linear_east: le, linear_north: ln } = s
  if (!te || !tn || !le || !ln || te.length < 2 || te.length !== tn.length || le.length !== te.length || ln.length !== te.length) return null
  // Drawn on the sky: east to the left, north up. The bend is the track's departure from the line.
  const track = te.map((e, i): [number, number] => [-(le[i] + k * (e - le[i])), -(ln[i] + k * (tn[i] - ln[i]))])
  const linear = le.map((e, i): [number, number] => [-e, -ln[i]])
  return { track, linear }
}

/** A pass or fail from a file's `checks`, found by the check's name (A4, A5…), or null when absent. */
function checkPassed(checks: Record<string, unknown> | null | undefined, name: string): boolean | null {
  if (!checks) return null
  const k = Object.keys(checks).find((key) => key.startsWith(`${name} `))
  const v = k ? checks[k] : undefined
  return typeof v === 'boolean' ? v : null
}

/** Range words for the For scientists text: "100.0–142.9 AU", or "76.5 AU to unbounded". */
function rangeAu(p: Pair): string | undefined {
  const x = asRange(p)
  return x ? (x.hi === null ? `${fmt(x.lo, 1)} AU to unbounded` : `${fmt(x.lo, 1)}–${fmt(x.hi, 1)} AU`) : undefined
}

export function reflexView(f: ReflexFile): ReflexView {
  const pix = ok(f.pixel_arcsec) ? f.pixel_arcsec : ok(f.demo?.pixel_arcsec) ? (f.demo?.pixel_arcsec as number) : NATIVE_PIXEL_ARCSEC
  const c = f.candidate ?? {}
  const sep = c.separation_arcsec
  const recovered = ok(sep) ? sep / pix < 2 : null
  const best = c.distance_au
  const range = asRange(c.range_95_au)
  const range68 = asRange(c.range_68_au)
  const r = f.jpl?.helio_distance_au
  const wide = range && ok(best) ? range.hi === null || (range.hi - range.lo) / best > 0.3 : null

  const chip = recovered === null ? null : !recovered ? T1.chipNotFound : wide === null ? null : wide ? T1.chipFoundRough : T1.chipFoundDistance
  const headline = recovered === null ? null : !recovered ? T1.headlineNotFound : wide === null ? null : wide ? T1.headlineRough : T1.headlineDistance

  // Centred on NASA's place: said by the file, or read from it (JPL's mid-visit place within one square of the centre).
  const mid = f.jpl?.mid
  const fieldRa = f.field?.ra
  const fieldDec = f.field?.dec
  const centred =
    typeof f.field?.centred_on_known === 'boolean'
      ? f.field.centred_on_known
      : mid && ok(mid.ra) && ok(mid.dec) && ok(fieldRa) && ok(fieldDec)
        ? Math.hypot((mid.ra - fieldRa) * Math.cos((fieldDec * Math.PI) / 180), mid.dec - fieldDec) * 3600 < pix
        : null
  const blindness = centred === true ? [...T1.centred, T1.notGiven] : centred === false ? T1.notCentred : []

  // Within 2 squares counts as found (the answer line's rule), so beyond that the place sentence says it missed.
  const place = !ok(sep) ? null : sep / pix < 0.5 ? T1.placeAlmost : sep / pix < 2 ? T1.placeVeryClose : T1.placeMissed
  const test = paras([T1.eris], blindness, f.development_object === true ? T1.practice : [], [T1.testWas, place, place ? T1.thenBend : null])

  const bestTxt = fmtInt(best)
  const numbers =
    bestTxt && range
      ? {
          ours: T1.ours(bestTxt),
          range: nonEmpty([rangeSentence(range), range.hi === null ? T1.rangeOpenNote : null]),
          nasa: ok(r) ? T1.nasa(fmt(r, 1) as string) : null,
        }
      : null
  const glance: Glance | null = bestTxt && recovered ? { ours: T1.glance.ours(bestTxt), known: ok(r) ? T1.glance.known(fmt(r, 1) as string) : null, unit: T1.glance.unit } : null

  let ruler: ReflexView['ruler'] = null
  if (ok(best) && range) {
    const top = range.hi ?? 1.5 * best
    const max = (Math.floor(top / 20) + 1) * 20
    const rangeWords = range.hi === null ? T1.rulerRangeAbove(fmtDown(range.lo) as string) : T1.rulerRangeBetween(fmtInt(range.lo) as string, fmtInt(range.hi) as string)
    ruler = { max, best, range, r: ok(r) ? r : null, summary: ok(r) ? T1.rulerSummary(bestTxt as string, rangeWords, fmt(r, 1) as string) : null }
  }

  const sunlight = ok(r) ? T1.sunlight(fmtInt((r * 499.0) / 3600) as string) : null

  // Verdicts. With no far end to the range, "inside" says little: the screen says the check is weak.
  const verdicts: string[] = []
  const sh = f.shifted ?? {}
  const shRange = asRange(sh.range_95_au)
  const firstInside = ok(r) && range ? inside(r, range) : null
  if (firstInside === true && range?.hi === null) verdicts.push(T1.insideOpen, ...T1.openWeak)
  else {
    if (firstInside !== null) verdicts.push(firstInside ? T1.inside : T1.outside)
    if (wide !== null) verdicts.push(wide ? T1.wide : T1.narrow)
  }
  const runs: string[] = []
  if (ok(r) && ok(best) && ok(sh.distance_au)) {
    if (best > r && sh.distance_au > r) runs.push(T1.twiceFar, T1.alwaysDoes)
    else if (best < r && sh.distance_au < r) runs.push(T1.twiceNear, T1.alwaysDoes)
    else runs.push(T1.eitherSide)
  }
  const after = paras([sunlight], verdicts, runs)

  // How sure are we?
  const hs = T1.howSure
  const secondRun: (string | null)[] = []
  if (ok(sh.distance_au)) {
    secondRun.push(hs.second, hs.again(fmtInt(sh.distance_au) as string))
    if (ok(r) && shRange) {
      const words = shRange.hi === null ? hs.rangeAbove(fmtDown(shRange.lo) as string) : hs.rangeBetween(fmtInt(shRange.lo) as string, fmtInt(shRange.hi) as string)
      secondRun.push(inside(r, shRange) ? (firstInside ? hs.insideToo(words) : hs.insideAlso(words)) : hs.outside(words))
    }
    secondRun.push(hs.notFresh, hs.wherever)
    if (ok(best)) {
      const a = fmtInt(best) as string
      const b = fmtInt(sh.distance_au) as string
      secondRun.push(Math.abs(sh.distance_au - best) >= 0.05 * best ? hs.moved(a, b) : hs.hardlyMoved(a, b))
    }
  }
  const earliest: (string | null)[] = []
  const minOut = c.leave_one_epoch_out_min_delta_s2
  const fd = c.first_day
  const neighbour = fd && fd.available !== false && fd.neighbour_as_bright === true && ok(fd.neighbour_arcsec) && fd.neighbour_arcsec < pix
  if (ok(minOut) && ok(c.delta_s2_infinite) && minOut < c.delta_s2_infinite / 2) earliest.push(hs.earliestDay, neighbour ? hs.neighbour : null, minOut >= 9 ? hs.withoutStill : hs.withoutNot)
  const later = otherVisitsPhrase(f.visit?.mjd_first, f.visit?.mjd_last, f.still_there)
  const howSure = paras(secondRun, earliest, later ? [hs.again2(later), hs.gone] : [], [hs.matters, hs.subtracts, hs.leftover, hs.months])

  // Try it: make Eris appear
  const v = f.visit ?? {}
  const n = fmtInt(v.n_used)
  const drift = c.drift_arcsec_day
  const squares = drift && drift.length === 2 && ok(drift[0]) && ok(drift[1]) && ok(v.duration_days) ? fmtInt((Math.hypot(drift[0], drift[1]) * v.duration_days) / pix) : undefined
  const diff = f.demo?.uses_difference_images === true || f.demo?.made_from === 'difference_images'
  const demo = f.demo ?? {}
  const picture = (key: 'single' | 'plain_mean' | 'slid') => {
    const png = demo[key]?.png
    if (typeof png === 'string' && png) return { src: labUrl(png) }
    return { why: whyOf(demo, key) ?? whyOf(demo[key], 'png') ?? PAGE.pictureNotReady }
  }
  const bl = demo.blank_pixels ?? {}
  const appear: ReflexView['appear'] = {
    count: n && ok(v.duration_days) && monthsOf(v.mjd_first, v.mjd_last) ? T1.appear.count(n, fmtInt(v.duration_days) as string, monthsOf(v.mjd_first, v.mjd_last) as string) : null,
    captions: [T1.appear.caption1, n && squares ? (diff ? T1.appear.caption2Diff(n, squares) : T1.appear.caption2(n, squares)) : null, diff ? T1.appear.caption3Diff : T1.appear.caption3],
    differenceImages: diff,
    pictures: [picture('single'), picture('plain_mean'), picture('slid')],
    blanks: [ok(bl.single) && bl.single > 0, ok(bl.plain_mean) && bl.plain_mean > 0, ok(bl.slid) && bl.slid > 0],
    cropPx: ok(demo.crop_px) ? demo.crop_px : null,
    marks: {
      tool: demo.marks?.tool_dot_px ?? null,
      nasaSingle: demo.marks?.nasa_single_px ?? null,
      nasaMid: demo.marks?.nasa_mid_px ?? null,
      nasaPath: demo.marks?.nasa_path_px ?? null,
    },
  }

  // Try it: find the distance
  let distance: ReflexView['distance'] = null
  const stops = f.stops
  const s0 = stops?.find((s) => s.inv_d === 0)
  if (stops && stops.length >= 2 && ok(best) && ok(c.snr)) {
    const k = ok(f.sketch_exaggeration) ? f.sketch_exaggeration : 1
    const bestInv = 1 / best
    const bestIndex = stops.reduce((bi, s, i) => (Math.abs(s.inv_d - bestInv) < Math.abs(stops[bi].inv_d - bestInv) ? i : bi), 0)
    const zero = s0 && ok(s0.snr) ? sq(s0.snr) : null
    const delta = (s: ReflexStop) => (zero !== null && ok(s.snr) ? sq(s.snr) - zero : null)
    const deltaBest = delta(stops[bestIndex])
    // "Nearly as sharp": a stop inside the bootstrap 68% range (the statistical-only interval is too narrow).
    const near = (d: number | null) => d !== null && range68 !== null && inside(d, range68)
    const stopDistance = (s: ReflexStop) => (s.inv_d === 0 ? null : ok(s.distance_au) ? s.distance_au : 1 / s.inv_d)
    const meterText = (d: number | null, i: number) => {
      if (d === null) return null
      if (d === 0) return T1.distance.meterSame
      if (d < 0) return T1.distance.meterBlurrier
      const how = i === bestIndex ? T1.distance.meterBest : near(stopDistance(stops[i])) ? T1.distance.meterNearly : T1.distance.meterLess
      return T1.distance.meterSharper(how)
    }
    const views: StopView[] = stops.map((s, i) => {
      const d = stopDistance(s)
      const label = d === null ? T1.distance.noBend : T1.distance.value(fmtInt(d) as string)
      const spoken = d === null ? T1.distance.noBendSpoken : label
      const dl = delta(s)
      let line: string | null = null
      if (i === bestIndex) line = T1.distance.sharpest(bestTxt as string)
      else if (near(d)) line = T1.distance.nearly
      else if (dl !== null) {
        const nearer = s.inv_d < stops[bestIndex].inv_d
        line = dl >= 0 ? (nearer ? T1.distance.lessNearer : T1.distance.lessFarther) : nearer ? T1.distance.blurrierNearer : T1.distance.blurrierFarther
      }
      return { inv_d: s.inv_d, label, spoken, delta: dl, line, sketch: stopSketch(s, k), meterText: meterText(dl, i) }
    })
    const w = f.wrong_way
    const wDelta = w ? delta(w) : null
    // Keep the wrong-way control only while it is true: blurrier than no bend, and the bend itself clear.
    const keepWrong = w && wDelta !== null && wDelta < 0 && deltaBest !== null && deltaBest >= 9
    const wrong: StopView | null = keepWrong
      ? { inv_d: w.inv_d, label: T1.distance.wrongSpoken, spoken: T1.distance.wrongSpoken, delta: wDelta, line: T1.distance.wrongLine, sketch: stopSketch(w, k), meterText: T1.distance.meterBlurrier }
      : null
    const deltas = [...views.map((x) => x.delta), wrong?.delta ?? null].filter(ok)
    const meter = deltas.length >= 2 && zero !== null ? { min: Math.min(0, ...deltas), max: Math.max(0, ...deltas) } : null
    // The cyan NASA tick: JPL's 1/r interpolated between the neighbouring stops.
    let nasaTick: number | null = null
    if (ok(r)) {
      const inv = 1 / r
      for (let i = 0; i + 1 < stops.length; i++) {
        const [a, b] = [stops[i].inv_d, stops[i + 1].inv_d]
        if (inv >= Math.min(a, b) && inv <= Math.max(a, b) && a !== b) nasaTick = i + (inv - a) / (b - a)
      }
    }
    distance = {
      stops: views,
      wrong,
      bestIndex,
      nasaTick,
      meter,
      exaggeration: ok(f.sketch_exaggeration) ? fmt(f.sketch_exaggeration, 1, true) ?? null : null,
      startLabel: dayMonth(v.mjd_first) ?? null,
      endLabel: dayMonth(v.mjd_last) ?? null,
    }
  }

  const half = halfWord(f.limit?.faintest_mean_flux_mjy, c.mean_flux_mjy)
  const lim = f.limit ?? {}
  const rl = lim.ranging_limit_au
  const rangingEris = ok(rl) ? rl : rl && typeof rl === 'object' && rl.available !== false && ok(rl.eris_bright_au) ? rl.eris_bright_au : null
  const rangingThr = ok(lim.ranging_limit_at_threshold_au) ? lim.ranging_limit_at_threshold_au : rl && typeof rl === 'object' && ok(rl.at_threshold_au) ? rl.at_threshold_au : null
  const nearAu = lim.distance_range_au && ok(lim.distance_range_au[0]) ? fmtInt(lim.distance_range_au[0] as number) : undefined
  const answers: ReflexView['answers'] = {
    something: T1.answers.something,
    nothing: lim.injection_tested === true || half === undefined ? null : half === 'as' ? T1.answers.nothingAs : T1.answers.nothing(half),
    cannot: ok(lim.min_visit_days) ? T1.answers.cannot(fmtInt(lim.min_visit_days) as string) : null,
    near: nearAu ? T1.answers.near(nearAu) : null,
    far: rangingEris !== null ? T1.answers.far(fmtInt(rangingEris) as string) : null,
    fainter: rangingEris !== null ? T1.answers.fainter : null,
  }

  const jd = f.jpl?.linear_drift ?? f.jpl?.linear_drift_arcsec_day
  const fo = f.foldout ?? {}
  const lev = v.distance_leverage_arcsec_per_inv_au ?? fo.leverage_arcsec_per_inv_au
  const nNull = f.null_runs?.n_field_visits ?? fo.blank_field_raw_peaks?.n_field_visits
  const st = f.still_there ?? []
  const a4 = checkPassed(f.checks, 'A4')
  const a4moved = checkPassed(sh.checks, 'A4')
  const a4Text =
    a4 === false && range68 && ok(r) && !inside(r, range68)
      ? `JPL's distance lies outside this run's bootstrap 68% range, so its check A4 fails${a4moved === true ? '; the moved run passes it' : ''}.`
      : undefined
  const blanks =
    [bl.single, bl.plain_mean, bl.slid].every(ok) && ok(demo.crop_px)
      ? `${fmtInt(bl.single)}, ${fmtInt(bl.plain_mean)} and ${fmtInt(bl.slid)} of ${fmtInt(demo.crop_px * demo.crop_px)} pixels in the three pictures`
      : undefined
  const sci = sciParagraphs(SCI.t1, {
    levE: lev && ok(lev[0]) ? fmtInt(lev[0]) : undefined,
    levN: lev && ok(lev[1]) ? fmtInt(lev[1]) : undefined,
    trials: fmtInt(f.n_trials ?? fo.n_trials),
    area: fmt(lim.searched_area_deg2, 4),
    first: isoDate(v.mjd_first),
    last: isoDate(v.mjd_last),
    dur: fmt(v.duration_days, 2),
    n,
    size: fmt(f.field?.size_deg, 2, true),
    sep: fmt(sep, 2),
    sepPx: ok(sep) ? fmt(sep / pix, 2) : undefined,
    snr: fmt(c.snr, 1),
    ve: drift && ok(drift[0]) ? fmt(drift[0], 2) : undefined,
    vn: drift && ok(drift[1]) ? fmt(drift[1], 2) : undefined,
    je: jd && ok(jd[0]) ? fmt(jd[0], 2) : undefined,
    jn: jd && ok(jd[1]) ? fmt(jd[1], 2) : undefined,
    best: bestTxt,
    delta: fmt(f.jpl?.observer_distance_au, 2),
    r: fmt(r, 2),
    nboot: fmtInt(c.n_bootstrap),
    b68: rangeAu(c.range_68_au),
    b95: rangeAu(c.range_95_au),
    a4: a4Text,
    p2: rangeAu(c.interval_2sigma_au_statistical_only),
    sinf: fmt(c.snr_at_infinity, 2),
    ds2: fmt(c.delta_s2_infinite, 1),
    nep: fmtInt(c.n_epochs),
    ds2min: fmt(minOut, 1),
    fdShare: fd && ok(fd.info_share) ? fmtInt(fd.info_share * 100) : undefined,
    fdN: fd && ok(fd.n_exposures) ? fmtInt(fd.n_exposures) : undefined,
    fdSep: fd && ok(fd.neighbour_arcsec) ? fmt(fd.neighbour_arcsec, 1) : undefined,
    a5: ok(minOut) ? (minOut < 25 ? 'check A5 (ΔS² ≥ 25) fails without that epoch, and A5b (ΔS² ≥ 9 with any epoch left out) passes' : 'check A5 (ΔS² ≥ 25) still passes without it') : undefined,
    mirror: fmt(c.reversed_earth_snr_mirror_distance, 2),
    wrongFree: fmt(f.wrong_way?.snr, 2),
    revAway: fmt(c.reversed_best_away ?? fo.reversed_best_away_snr, 1),
    nextSource: fmt(fo.next_source_snr, 1),
    st1: st[0] && ok(st[0].flux_mjy) ? `${fmt(st[0].flux_mjy, 4)}${ok(st[0].error_mjy) ? ` ± ${fmt(st[0].error_mjy, 4)}` : ''}` : undefined,
    st2: st[1] && ok(st[1].flux_mjy) ? `${fmt(st[1].flux_mjy, 4)}${ok(st[1].error_mjy) ? ` ± ${fmt(st[1].error_mjy, 4)}` : ''}` : undefined,
    sep2: fmt(sh.separation_arcsec, 2),
    snr2: fmt(sh.snr, 1),
    best2: fmtInt(sh.distance_au),
    s68: rangeAu(sh.range_68_au),
    s95: rangeAu(sh.range_95_au),
    edge: fmt(sh.edge_reversed_peak, 2),
    lim: fmt(lim.faintest_mean_flux_mjy, 4),
    erisFlux: fmt(c.mean_flux_mjy, 4),
    nNull: fmtInt(nNull),
    nullArea: ok(f.null_runs?.area_deg2) ? fmt(f.null_runs?.area_deg2, 2) : ok(nNull) && ok(lim.searched_area_deg2) ? fmt(nNull * lim.searched_area_deg2, 2) : undefined,
    vEris: fmt(lim.v_eris_coloured, 1),
    vSedna: fmt(lim.v_sedna_coloured, 1),
    sedna: fmt(f.sedna?.forced_snr, 1),
    thr: fmt(f.sedna?.threshold, 0),
    minDays: fmtInt(lim.min_visit_days),
    rangeThr: fmtInt(rangingThr),
    rangeEris: fmtInt(rangingEris),
    near: nearAu,
    hours: ok(r) ? fmtInt((r * 499) / 3600) : undefined,
    demoDiff: diff ? 'yes' : 'no',
    blanks,
  })

  return {
    fixture: f.fixture === true,
    final: f.final === true,
    chip,
    glance,
    headline,
    test,
    numbers,
    ruler,
    after,
    howSure,
    appear,
    distance,
    answerLine: recovered === null ? null : recovered ? T1.answerFound : T1.answerNotFound,
    answers,
    sedna: f.sedna?.found_blind === false,
    sci,
  }
}

// ---------------------------------------------------------------------------------- tool 2

export interface GroupView {
  name: string
  spoken: string
  /** Offset from the Bluer group, arcsec east and north, and its 1σ ring. */
  east: number | null
  north: number | null
  errEast: number | null
  errNorth: number | null
  picture: { src: string } | { why: string }
  caption: string | null
  insetText: string | null
}

export interface ColourView {
  fixture: boolean
  final: boolean
  chip: string | null
  glance: Glance | null
  result: string[]
  test: Para[]
  howSure: Para[]
  groups: GroupView[]
  magnification: number | null
  /** The pre-set rule, in usual errors: the inset's dashed ring. */
  rule: number | null
  partner: { east: number; north: number } | null
  partnerPa: number | null
  pixel: number
  cropPx: number | null
  hostPx: number[] | null
  lone: { line: string[]; groups: GroupView[] } | null
  answerLine: string | null
  sci: string[]
}

const GROUP_NAMES = ['Bluer', 'Middle', 'Redder']

/** A pre-set check's key as words: "ratio_0p75_1p4_consistent_with_0_within_0p01" → "ratio 0.75–1.4 consistent with 0 within 0.01". */
export function checkWords(key: string): string {
  return key
    .replace(/(\d)p(\d)/g, '$1.$2')
    .replace(/_/g, ' ')
    .replace(/(\d) (\d)/g, '$1–$2')
}

/**
 * The colour groups as the inset draws them: each group's centre minus the Bluer group's, a ring
 * of the two groups' 1σ added in quadrature (so the Redder ring is the walk's own error), and the
 * captions chosen from them. For the lone star there is no partner, so no partner captions.
 */
function groupViews(input: ColourGroup[] | null | undefined, o: { pa: number | null; sigma: Num; rule: Num; lone: boolean }): GroupView[] {
  const raw = GROUP_NAMES.map((name) => (input ?? []).find((g) => g.name === name)).filter((g): g is ColourGroup => g !== undefined)
  const blue = raw.find((g) => g.name === 'Bluer')
  const quad = (a: Num, b: Num) => (ok(a) ? Math.hypot(a, ok(b) ? b : 0) : null)
  return raw.map((g) => {
    const i = GROUP_NAMES.indexOf(g.name)
    const rel = (x: Num, b: Num) => (ok(x) && ok(b) ? x - b : null)
    const isBlue = g === blue
    const east = isBlue ? 0 : rel(g.east, blue?.east)
    const north = isBlue ? 0 : rel(g.north, blue?.north)
    const errEast = isBlue ? null : quad(g.err_east, blue?.err_east)
    const errNorth = isBlue ? null : quad(g.err_north, blue?.err_north)
    let caption: string | null = null
    let insetText: string | null = null
    const colourWords = T2.tryIt.insetColours[i]
    if (isBlue) {
      caption = o.lone ? null : T2.tryIt.captionBluer
      insetText = o.lone ? T2.tryIt.insetLoneStart : T2.tryIt.insetStart
    } else if (east !== null && north !== null) {
      const groupDir = screenDirection((Math.atan2(east, north) * 180) / Math.PI)
      // How many usual errors the centre moved (the same measure as the walk's "about 2 times").
      const r = errEast !== null && errNorth !== null ? Math.sqrt(sq(east / errEast) + sq(north / errNorth)) : null
      const far = r === null ? null : r < 1 ? T2.tryIt.insetLess : T2.tryIt.insetAbout(fmt(r, 0) as string)
      if (o.lone) {
        if (groupDir && far) insetText = T2.tryIt.insetLone(colourWords, groupDir, far)
      } else if (o.pa !== null) {
        const along = alongPa(east, north, o.pa)
        if (g.name === 'Middle') {
          const err = errEast !== null && errNorth !== null ? alongErr(errEast, errNorth, o.pa) : null
          caption = err === null ? null : T2.tryIt.captionMiddle(along > err ? T2.tryIt.middleMoved : T2.tryIt.middleHardly)
        } else {
          caption = ok(o.sigma) && ok(o.rule) ? T2.tryIt.captionRedder(along <= 0 ? T2.tryIt.redderHardly : o.sigma >= o.rule ? T2.tryIt.redderClearly : T2.tryIt.redderLittle) : null
        }
        if (groupDir && far) insetText = T2.tryIt.insetSummary(colourWords, groupDir, along > 0 ? T2.tryIt.insetToward : T2.tryIt.insetAway, far)
      }
    }
    const png = g.png
    return {
      name: T2.tryIt.stops[i],
      spoken: T2.tryIt.spoken[i],
      east,
      north,
      errEast,
      errNorth,
      picture: typeof png === 'string' && png ? { src: labUrl(png) } : { why: whyOf(g, 'png') ?? PAGE.pictureNotReady },
      caption,
      insetText,
    }
  })
}

/** {one and a third}: a distance in squares as a whole number and a common fraction, in words. */
export function fractionWords(x: Num): string | undefined {
  if (!ok(x) || x <= 0 || x >= 10) return undefined
  const parts: [number, string][] = [
    [0, ''],
    [0.25, T2.fractions.quarter],
    [1 / 3, T2.fractions.third],
    [0.5, T2.fractions.half],
    [2 / 3, T2.fractions.twoThirds],
    [0.75, T2.fractions.threeQuarters],
    [1, ''],
  ]
  let whole = Math.floor(x)
  let [frac, word] = parts.reduce((b, p) => (Math.abs(x - whole - p[0]) < Math.abs(x - whole - b[0]) ? p : b))
  if (frac === 1) {
    whole += 1
    word = ''
  }
  const w = T2.fractions.numbers[whole] ?? ''
  if (whole === 0) return word || undefined
  return word ? T2.fractions.and(w, word) : w
}

/** {lower right}: the screen direction of a position angle (north up, east left). */
export function screenDirection(pa: Num): string | undefined {
  if (!ok(pa)) return undefined
  const a = ((pa % 360) + 360) % 360
  if (a >= 180 && a < 270) return T2.direction.lr
  if (a >= 90 && a < 180) return T2.direction.ll
  if (a < 90) return T2.direction.ul
  return T2.direction.ur
}

const angleGap = (a: number, b: number) => Math.abs((((a - b) % 360) + 540) % 360 - 180)
const alongPa = (east: number, north: number, pa: number) => east * Math.sin((pa * Math.PI) / 180) + north * Math.cos((pa * Math.PI) / 180)
const alongErr = (ee: number, en: number, pa: number) => Math.hypot(ee * Math.sin((pa * Math.PI) / 180), en * Math.cos((pa * Math.PI) / 180))

/** Inset magnification: the smallest of 10, 20, 25, 40, 50 putting the redder dot 40 px from the cross. */
export function chooseMagnification(shiftArcsec: number, pxPerArcsec: number): number {
  for (const m of [10, 20, 25, 40, 50]) if (shiftArcsec * m * pxPerArcsec >= 40) return m
  return 50
}

export function colourView(f: ColourFile, insetPx = 358): ColourView {
  const pix = ok(f.pixel_arcsec) ? f.pixel_arcsec : ok(f.picture?.pixel_arcsec) ? (f.picture?.pixel_arcsec as number) : NATIVE_PIXEL_ARCSEC
  const w = f.walk?.all ?? {}
  const knownPa = f.known?.pa_deg
  const knownSep = f.known?.sep_arcsec
  const rule = f.rule_sigma
  const pointed = ok(w.pa) && ok(knownPa) && ok(w.pa_error_deg) ? angleGap(w.pa, knownPa) < w.pa_error_deg : null

  const notProven = f.verdict === 'nothing_found' || f.acceptance?.passed === false || f.null?.acceptance?.passed === false
  const chip = f.verdict == null && f.acceptance?.passed == null ? null : notProven ? T2.chipNotProven : f.development_object_note ? T2.chipPractice : T2.chipPassed
  const glance: Glance | null = ok(w.sigma) ? { ours: T2.glance.shift(fmt(w.sigma, 1, true) as string), known: ok(rule) ? T2.glance.needed(fmtInt(rule) as string) : null, unit: null } : null

  // The verdict first, then what happened (newcomer review: the good news first read as a win).
  const small = ok(w.sigma) && ok(rule) ? w.sigma < rule : null
  const result = nonEmpty([
    chip === null ? null : notProven ? T2.resultNotProven : f.development_object_note ? T2.resultPractice : T2.resultPassed,
    pointed === null ? null : pointed ? T2.resultRight : T2.resultWrong,
    small === null ? null : small ? (pointed === false ? T2.resultSmallAnd : T2.resultSmall) : T2.resultBig,
  ])

  const parts = ok(knownSep) ? fractionWords(knownSep / pix) : undefined
  const dir = screenDirection(w.pa)
  const visits = f.visit_walks ?? []
  const fixedRaw = f.walk?.detector_fixed_arcsec
  const fixed = ok(fixedRaw) ? fixedRaw : fixedRaw && typeof fixedRaw === 'object' ? (ok(fixedRaw.size) ? fixedRaw.size : ok(fixedRaw.x) && ok(fixedRaw.y) ? Math.max(Math.abs(fixedRaw.x), Math.abs(fixedRaw.y)) : null) : null
  const turned = ok(w.pa) && visits.length > 0 && visits.every((x) => ok(x.sky_angle) && angleGap(x.sky_angle, w.pa as number) <= 45) && ok(fixed) && fixed < 0.05
  const nullFailed = f.null?.acceptance?.passed === false
  const checks = f.acceptance?.checks
  const nFailed = checks ? Object.values(checks).filter((x) => x === false).length : 0
  const test = paras(
    [T2.anyway],
    [T2.known, T2.squares, parts ? T2.sits(parts) : null, T2.blob],
    [
      dir ? T2.moved(dir) : null,
      ok(w.pa) && ok(knownPa) && ok(w.pa_error_deg) ? (pointed ? T2.liesThatWay : T2.liesAway(fmtInt(angleGap(w.pa, knownPa)) as string)) : null,
      ok(w.size) ? T2.tiny(fmtInt((w.size / pix) * 100) as string) : null,
    ],
    [T2.inexact, turned ? T2.turned : null],
    [T2.usualError, ok(w.sigma) ? T2.times(fmt(w.sigma, 1, true) as string) : null, ok(rule) ? T2.rule(fmtInt(rule) as string) : null],
    [
      checks && nFailed > 0 ? (nFailed === 1 ? T2.checksOne : nFailed === 2 ? T2.checksTwo : T2.checksMany(fmtInt(nFailed) as string)) : null,
      nullFailed || (checks && nFailed > 0) ? T2.notClean : null,
    ],
    [f.development_object_note ? T2.practice : null],
  )

  // Other stars measured the same way (the null field's walkers): as far as VHS 1256's centre, or farther.
  const walkers = (f.null?.walkers_over_4sigma ?? []).filter((x) => ok(x.walk_arcsec))
  const farthest = walkers.length ? Math.max(...walkers.map((x) => x.walk_arcsec as number)) : null
  const others = farthest !== null && ok(w.size) ? (farthest >= w.size ? T2.othersFar : farthest >= 0.7 * w.size ? T2.othersAbout : null) : null

  // How sure are we? (newcomer review: the counts and the review's story, folded, the verdict left in view)
  const guessed = ok(f.walk?.sigma_guessed_floor) && ok(w.sigma) && (f.walk?.sigma_guessed_floor as number) > w.sigma
  const howSure = paras(
    [ok(f.n_clean_fits) ? T2.measured(fmtInt(f.n_clean_fits) as string) : null, ok(w.p_false) && w.p_false > 0 ? T2.chance(fmtInt(1 / w.p_false) as string) : null],
    guessed
      ? [T2.guessed, T2.guessedNow(fmt(w.sigma, 1, true) as string, fmt(f.walk?.sigma_guessed_floor, 1, true) as string), ok(rule) ? T2.ruleKept(fmtInt(rule) as string) : null]
      : [],
    [nullFailed ? T2.nullFailed : null, others],
    [T2.mass, T2.border, T2.brownDwarf],
  )

  const pa = ok(knownPa) ? knownPa : null
  const groups = groupViews(f.groups, { pa, sigma: w.sigma, rule, lone: false })
  const cropPx = ok(f.picture?.crop_px) ? (f.picture?.crop_px as number) : null
  const shifts = groups.filter((g) => g.east !== null && g.north !== null).map((g) => Math.hypot(g.east as number, g.north as number))
  const magnification = cropPx && shifts.length > 1 ? chooseMagnification(Math.max(...shifts), insetPx / (cropPx * pix)) : null
  const partner =
    ok(knownSep) && ok(knownPa) ? { east: knownSep * Math.sin((knownPa * Math.PI) / 180), north: knownSep * Math.cos((knownPa * Math.PI) / 180) } : null

  // "Compare: a star on its own": only when the lone-star export exists, with all three groups.
  // Its one star's small walk is never left alone on the screen: other stars walked as far (truth review).
  let lone: ColourView['lone'] = null
  const ls = f.lone_star
  if (ls && ls.available !== false && ok(ls.walk_size) && ok(w.size)) {
    const lg = groupViews(ls.groups, { pa: null, sigma: null, rule: null, lone: true })
    if (lg.length === groups.length && lg.length > 1) lone = { line: nonEmpty([T2.tryIt.lone, ls.walk_size >= 0.7 * w.size ? T2.tryIt.loneFar : T2.tryIt.loneLittle, others, T2.tryIt.loneRule]), groups: lg }
  }

  const answerLine = f.verdict === 'nothing_found' ? T2.answerNothing : typeof f.verdict === 'string' && /found|shift|candidate/.test(f.verdict) ? T2.answerFound : null

  const per = f.walk?.per_detector ?? {}
  const dets = ['D4', 'D5', 'D6'].map((k) => per[k]).filter(Boolean)
  const list = (xs: (string | undefined)[]) => (xs.length > 0 && xs.every(Boolean) ? (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}` : xs[0]) : undefined)
  const failedNames = checks
    ? Object.entries(checks)
        .filter(([, v]) => v === false)
        .map(([k]) => checkWords(k))
    : []
  const nullChecks = f.null?.acceptance?.checks
  const farWalkers = walkers.filter((x) => ok(w.size) && (x.walk_arcsec as number) >= w.size).sort((a, b) => (b.walk_arcsec as number) - (a.walk_arcsec as number))
  const sci = sciParagraphs(SCI.t2, {
    floorE: fmt(f.null?.scatter_east, 3),
    floorN: fmt(f.null?.scatter_north, 3),
    sep: fmt(knownSep, 2),
    pa: fmt(knownPa, 1),
    nExp: fmtInt(f.n_exposures),
    nFit: fmtInt(f.n_clean_fits),
    size: fmt(w.size, 2),
    wpa: fmtInt(w.pa),
    paErr: fmtInt(w.pa_error_deg),
    sigma: fmt(w.sigma, 1),
    pFalse: fmt(w.p_false, 2),
    sigmaOld: fmt(f.walk?.sigma_guessed_floor, 1),
    rule: fmtInt(rule),
    pRule: ok(rule) ? powerOfTen(Math.exp(-(rule * rule) / 2)) : undefined,
    verdict: f.verdict ?? undefined,
    visitPas: list(visits.map((x) => (ok(x.sky_angle) ? `${fmtInt(x.sky_angle)}°` : undefined))),
    fixed: fmt(fixed, 3),
    detPas: list(dets.map((d) => (ok(d.pa) ? `${fmtInt(d.pa)}°` : undefined))),
    detSizes: list(dets.map((d) => (ok(d.size) ? `${fmt(d.size, 2)}″` : undefined))),
    detSigmas: dets.length ? `${fmt(Math.min(...dets.map((d) => d.sigma ?? NaN)), 1)}–${fmt(Math.max(...dets.map((d) => d.sigma ?? NaN)), 1)}` : undefined,
    passedChecks: checks ? fmtInt(Object.values(checks).filter((x) => x === true).length) : undefined,
    nChecks: checks ? fmtInt(Object.keys(checks).length) : undefined,
    failedChecks: failedNames.length ? failedNames.join('; ') : undefined,
    nWithin: fmtInt(f.null?.n_within),
    nIso: fmtInt(f.null?.n_isolated),
    nullPassed: nullChecks ? fmtInt(Object.values(nullChecks).filter((x) => x === true).length) : undefined,
    nullChecks: nullChecks ? fmtInt(Object.keys(nullChecks).length) : undefined,
    walkers:
      farWalkers.length && farWalkers.every((x) => x.neighbour_kind)
        ? list(farWalkers.map((x) => (ok(x.sigma) ? `${fmt(x.walk_arcsec, 2)}″ (${fmt(x.sigma, 1)}σ)` : undefined)))
        : undefined,
    loneId: ls?.gaia_id ?? undefined,
    loneG: fmt(ls?.gmag, 1),
    loneSize: fmt(ls?.walk_size, 3),
    loneSigma: fmt(ls?.walk?.sigma, 2),
    sepPx: ok(knownSep) ? fmt(knownSep / pix, 2) : undefined,
    sizePx: ok(w.size) ? fmt(w.size / pix, 2) : undefined,
    cm: ok(w.size) ? fmtInt((w.size / pix) * 100) : undefined,
    timesWord: fmt(w.sigma, 1, true),
    oneIn: ok(w.p_false) && w.p_false > 0 ? fmtInt(1 / w.p_false) : undefined,
  })

  return {
    fixture: f.fixture === true,
    final: f.final === true,
    chip,
    glance,
    result,
    test,
    howSure,
    groups,
    magnification,
    rule: ok(rule) ? rule : null,
    partner,
    partnerPa: ok(knownPa) ? knownPa : null,
    pixel: pix,
    cropPx,
    hostPx: f.picture?.host_px ?? null,
    lone,
    answerLine,
    sci,
  }
}

// ---------------------------------------------------------------------------------- tool 3

export interface FoldedPoint {
  h: number
  y: number
}
export interface Bin {
  h: number
  mean: number
  err: number | null
  n: number
}

/** Hours from the nearest predicted crossing, for readings within ±window hours. */
export function fold(readings: TransitReading[], periodD: number, t0: number, windowH = 9): FoldedPoint[] {
  const out: FoldedPoint[] = []
  for (const r of readings) {
    if (!ok(r.bjd_tdb) || !ok(r.rel_flux)) continue
    const dt = r.bjd_tdb - t0
    const h = (dt - Math.round(dt / periodD) * periodD) * 24
    if (Math.abs(h) <= windowH) out.push({ h, y: r.rel_flux * 100 })
  }
  return out
}

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b)
  const m = s.length >> 1
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/**
 * Means in 45-minute slots from −window to +window hours (slot centres −8.625 … +8.625 for 9 h),
 * by the module's own rule (scripts/check_transit.py bin_curve): a slot needs at least 5 readings,
 * and its error is the robust spread (1.4826 × the median absolute deviation) over √n. So on the
 * known timetable these are the module's folded averages (transits.json d5.folded).
 */
export const MIN_PER_SLOT = 5
export function binFolded(points: FoldedPoint[], widthH = 0.75, windowH = 9): Bin[] {
  const n = Math.round((2 * windowH) / widthH)
  const slots: number[][] = Array.from({ length: n }, () => [])
  for (const p of points) {
    const i = Math.floor((p.h + windowH) / widthH)
    if (i >= 0 && i < n) slots[i].push(p.y)
  }
  return slots.flatMap((ys, i) => {
    if (ys.length < MIN_PER_SLOT) return []
    const mean = ys.reduce((a, b) => a + b, 0) / ys.length
    const mid = median(ys)
    const robust = 1.4826 * median(ys.map((y) => Math.abs(y - mid)))
    return [{ h: -windowH + (i + 0.5) * widthH, mean, err: robust / Math.sqrt(ys.length), n: ys.length }]
  })
}

/** The chart's fixed y range: 1st–99th percentile at the known timetable, rounded out to whole numbers. */
export function yRange(points: FoldedPoint[]): [number, number] | null {
  if (points.length < 3) return null
  const ys = points.map((p) => p.y).sort((a, b) => a - b)
  const q = (f: number) => ys[Math.min(ys.length - 1, Math.max(0, Math.round(f * (ys.length - 1))))]
  return [Math.floor(q(0.01)), Math.ceil(q(0.99))]
}

/** The module's trapezoid: flat bottom T23 = T14 (1 − k) / (1 + k), linear ingress and egress. */
export function trapezoidDepth(hours: number, t14h: number, rprs: number): number {
  const t23 = (t14h * (1 - rprs)) / (1 + rprs)
  return Math.min(1, Math.max(0, (t14h / 2 - Math.abs(hours)) / ((t14h - t23) / 2)))
}

export interface DialStop {
  period: number
  label: string
  spoken: string
  known: boolean
  /** "Dip on this timetable: …", only where the module measured a dip. */
  readout: string | null
  /** In the readout's place where the module refuses to fit: too few readings in a crossing. */
  missing: string | null
  lines: string[]
  /** The dip and its about-95% give-or-take, in per cent, for the bar; null where nothing was measured. */
  bar: { depth: number; err: number } | null
  barSummary: string | null
}

export interface TransitView {
  fixture: boolean
  final: boolean
  chip: string | null
  glance: Glance | null
  headline: string | null
  asPublished: string | null
  /** Said at once after the result: one band of colours, and what a 1 per cent dip is. */
  lead: string[]
  picture: { src: string } | { why: string }
  /** The measuring circle on the picture, in picture squares. */
  ring: { crop: number; x: number; y: number; r: number } | null
  test: Para[]
  numbers: { ours: string; range: string; published: string | null; publishedRange: string | null } | null
  after: Para[]
  howSure: Para[]
  /** Under the dial: the wrong timetables tried on purpose. */
  dialNote: Para[]
  dial: {
    stops: DialStop[]
    knownIndex: number
    t0: number
    t14: number | null
    rprs: number | null
    expected: number | null
    measured: number | null
    expectedText: string | null
    /** The chart's two lines in words, with the published dip and ours with its give-or-take. */
    measuredText: string | null
    readings: TransitReading[]
    y: [number, number] | null
    window: number
    /** The dip bar's scale, in per cent, the same at every stop. */
    barRange: [number, number] | null
  } | null
  fallback: string | null
  answerLine: string | null
  sci: string[]
}

/** "2 × 10⁻⁷". */
export function powerOfTen(x: Num): string | undefined {
  if (!ok(x) || x <= 0) return undefined
  let e = Math.floor(Math.log10(x))
  let m = Math.round(x / 10 ** e)
  if (m === 10) {
    m = 1
    e += 1
  }
  const sup = String(Math.abs(e))
    .split('')
    .map((c) => '⁰¹²³⁴⁵⁶⁷⁸⁹'[Number(c)])
    .join('')
  return `${m} × 10${e < 0 ? '⁻' : ''}${sup}`
}

/** The spread of the depth over the module's other analysis choices, aperture radii and the HALO flag, in per cent. */
function choiceRange(choices: Record<string, Num> | null | undefined, apertures: Record<string, Num> | null | undefined, halo: Num): string | undefined {
  const xs = [...Object.values(choices ?? {}), ...Object.values(apertures ?? {}), halo].filter(ok)
  if (xs.length < 2) return undefined
  return `${fmt(Math.min(...xs) * 100, 2)}–${fmt(Math.max(...xs) * 100, 2)}`
}

export function transitView(f: TransitFile): TransitView {
  const d5 = f.d5 ?? {}
  const pl = f.planet ?? {}
  const A1 = f.acceptance?.A1
  const a1 = typeof A1 === 'boolean' ? A1 : (A1?.passed ?? undefined)
  const depth = d5.depth
  const emp = d5.empirical_err
  const exp = pl.expected_depth
  const range: Range | null = ok(depth) && ok(emp) ? { lo: Math.round((depth - 2 * emp) * 1000) / 10, hi: Math.round((depth + 2 * emp) * 1000) / 10 } : null
  const expPct = ok(exp) ? exp * 100 : null
  const pubInside = range && expPct !== null ? inside(Math.round(expPct * 100) / 100, range) : null

  // WASP-100 b: combined within 2 errors of the published depth; bands at 3 empirical sigma or more.
  const w100 = f.wasp100 ?? {}
  // Detectors the module left out (too bright for the camera) are not counted.
  const per = w100.per_detector ? Object.values(w100.per_detector).filter((d) => !d.excluded) : null
  const nClear = per ? per.filter((d) => ok(d.empirical_sigma) && d.empirical_sigma >= 3).length : ok(w100.n_clear) ? w100.n_clear : null
  const comb = w100.combined
  const combClose = comb && ok(comb.depth) && ok(comb.error) && ok(w100.expected_depth) ? Math.abs(comb.depth - w100.expected_depth) <= 2 * comb.error : null
  const allWithin =
    per && ok(w100.expected_depth) ? per.every((d) => ok(d.depth) && ok(d.empirical_err) && Math.abs((d.depth as number) - (w100.expected_depth as number)) <= 2 * (d.empirical_err as number)) : false

  const chip =
    a1 === true ? (nClear === null ? null : nClear === 1 ? T3.chipOneMixed : nClear === 0 ? T3.chipOneNot : allWithin ? T3.chipTwo : T3.chipOneMixed) : a1 === false ? T3.chipNone : null
  const headline = a1 === true ? T3.headline : a1 === false ? T3.headlineNot : null
  const asPublished = pubInside === null ? null : pubInside ? T3.asDeep : expPct !== null && range && expPct > (range.hi as number) ? T3.shallower : T3.deeper
  // The depth never without its give-or-take (docs/transits.md): 2 empirical errors, about 95%.
  const glance: Glance | null =
    ok(depth) && ok(emp) && a1 !== undefined
      ? { ours: T3.glance.ours(fmt(depth * 100, 1) as string, fmt(2 * emp * 100, 1) as string), known: expPct !== null ? T3.glance.known(fmt(expPct, 2) as string) : null, unit: T3.glance.unit }
      : null

  // One of SPHEREx's bands of colours (its detectors), said at once.
  const nBands = Object.keys(f.detectors ?? f.coverage?.per_detector ?? {}).length
  const bandsWord = T2.fractions.numbers[nBands]
  const lead = nonEmpty([ok(d5.n) && nBands > 1 && bandsWord ? T3.oneOfBands(bandsWord) : null, ok(depth) ? T3.bigPlanet : null])

  const period = pl.period_d
  const t14 = pl.t14_h
  const t14Words = ok(t14) ? (Math.abs(t14 - Math.round(t14)) <= 0.1 ? T3.about(fmtInt(t14) as string) : t14 - Math.floor(t14) >= 0.5 ? T3.almost(fmtInt(Math.ceil(t14)) as string) : T3.justOver(fmtInt(Math.floor(t14)) as string)) : undefined
  const scatterWords = ok(d5.scatter) && ok(depth) && depth > 0 ? (d5.scatter / depth >= 1.15 ? T3.moreThan : d5.scatter / depth >= 0.85 ? T3.aboutAs : T3.almostAs) : null
  const test = paras(
    [T3.giant, ok(period) && t14Words ? T3.goesRound(fmt(period, 1) as string, t14Words) : null],
    [T3.patches, ok(f.coverage?.exposures) ? T3.again(fmtInt(Math.round((f.coverage?.exposures as number) / 100) * 100) as string) : null],
    [
      T3.tooBright,
      ok(d5.n) ? T3.oneBand(fmtInt(d5.n) as string) : null,
      ok(d5.n_in) && ok(d5.n_transits) ? T3.during(fmtInt(d5.n_in) as string, fmtInt(d5.n_transits) as string) : null,
    ],
    [ok(d5.scatter) ? T3.typical(fmt(d5.scatter * 100, 1) as string) : null, scatterWords, T3.noSingle],
    [ok(depth) ? T3.linedUp(fmt(depth * 100, 1) as string) : null],
  )

  const pr = pl.published_depth_range_pct
  const pubRange = Array.isArray(pr) && pr.length === 2 && ok(pr[0]) && ok(pr[1]) ? T3.publishedRange(fmt(pr[0], 2) as string, fmt(pr[1], 2) as string) : null
  const numbers =
    ok(depth) && range ? { ours: T3.ours(fmt(depth * 100, 1) as string), range: rangeSentence(range, 1), published: expPct !== null ? T3.published(fmt(expPct, 2) as string) : null, publishedRange: pubRange } : null

  const after = paras(
    [pubInside === null ? null : pubInside ? T3.publishedInside : T3.publishedOutside],
    [f.development_object === true ? T3.practice : null],
    [
      comb ? T3.second : null,
      combClose === null ? null : combClose ? T3.secondClose : ok(comb?.depth) && ok(w100.expected_depth) && (comb?.depth as number) > (w100.expected_depth as number) ? T3.secondDeeper : T3.secondShallower,
      nClear === null ? null : nClear === 1 ? T3.secondOne : nClear === 0 ? T3.secondNone : allWithin ? T3.secondAll : T3.secondOne,
    ],
  )

  const years = d5.years ? Object.entries(d5.years).sort(([a], [b]) => a.localeCompare(b)) : []
  let yearLine: string | null = null
  if (years.length === 2 && ok(d5.noise_factor)) {
    const clear = years.every(([, y]) => ok(y.depth) && ok(y.formal_err) && (y.depth as number) > 3 * (y.formal_err as number) * (d5.noise_factor as number))
    yearLine = clear ? T3.howSure.years(years[0][0], years[1][0]) : T3.howSure.yearsTogether
  }
  const comp = f.comparison
  const howSure = paras([yearLine, comp && ok(comp.depth) && ok(comp.err) && Math.abs(comp.depth) <= 2 * comp.err ? T3.howSure.steady : null])
  const nDeep = ok(d5.n_fake_as_deep) ? d5.n_fake_as_deep : ok(d5.fake_share_as_deep) && ok(d5.n_fake) ? Math.round(d5.fake_share_as_deep * d5.n_fake) : null
  const dialNote = ok(d5.n_fake)
    ? paras([T3.howSure.wrong(fmtInt(d5.n_fake) as string), T3.howSure.wouldShow, nDeep === null ? null : nDeep === 0 ? T3.howSure.noneDid : T3.howSure.someDid(fmtInt(nDeep) as string)])
    : []

  // The dial: the file's own fit at each period, and the readings folded in the browser.
  let dial: TransitView['dial'] = null
  const readings = f.readings
  const stops = f.stops
  if (readings && readings.length > 0 && stops && stops.length >= 2 && ok(period) && ok(pl.t0_bjd_tdb)) {
    const flagged = stops.findIndex((s) => s.known === true)
    const knownIndex =
      flagged >= 0 ? flagged : stops.reduce((bi, s, i) => (Math.abs(s.period_d - (period as number)) < Math.abs(stops[bi].period_d - (period as number)) ? i : bi), 0)
    // The module's errors at each period are formal; its empirical factor makes them the same kind as
    // the range above, and 2 of them make the "give or take" about 95%, as every range on the page.
    const factor = ok(d5.noise_factor) ? d5.noise_factor : 1
    const chanceLimit = ok(d5.empirical_err) ? 2 * d5.empirical_err : null
    const views: DialStop[] = stops.map((s, i) => {
      const p = fmt(s.period_d, 2) as string
      const known = i === knownIndex
      const e2 = ok(s.err) ? 2 * s.err * factor : null
      const x = ok(s.depth) ? fmt(s.depth * 100, 1) : undefined
      const e = e2 !== null ? fmt(e2 * 100, 1) : undefined
      const readout: string | null = x && e ? T3.tryIt.readout(x, e) : null
      const lines = known ? [T3.tryIt.known] : readout ? [T3.tryIt.wrong] : [T3.tryIt.wrongFew]
      if (!known && readout && ok(s.depth) && Math.abs(s.depth) < (chanceLimit ?? (e2 ?? 0))) lines.push(T3.tryIt.chance)
      // No depth at this stop: say why in plain words (too few readings in a crossing, the module's
      // own limit), or that it is not available, never a number.
      const missing = readout ? null : ok(s.n_in) && ok(f.min_in_transit) && s.n_in < f.min_in_transit ? T3.tryIt.tooFew : T3.tryIt.noDip
      const bar = readout && ok(s.depth) && e2 !== null ? { depth: s.depth * 100, err: e2 * 100 } : null
      const barSummary = bar && x && e ? T3.tryIt.bar.summary(x, e) : null
      return { period: s.period_d, label: T3.tryIt.days(p), spoken: known ? T3.tryIt.spokenKnown(p) : T3.tryIt.spokenWrong(p), known, readout, missing, lines, bar, barSummary }
    })
    const bars = views.flatMap((v) => (v.bar ? [v.bar.depth - v.bar.err, v.bar.depth + v.bar.err] : []))
    const barRange: [number, number] | null = bars.length ? [Math.floor(Math.min(0, ...bars) * 2) / 2, Math.ceil(Math.max(0, ...bars, expPct ?? 0) * 2) / 2] : null
    dial = {
      stops: views,
      knownIndex,
      t0: pl.t0_bjd_tdb as number,
      t14: ok(t14) ? t14 : null,
      rprs: ok(pl.rprs) ? pl.rprs : null,
      expected: expPct,
      measured: ok(depth) ? depth * 100 : null,
      expectedText: expPct !== null ? (fmt(expPct, 2) as string) : null,
      measuredText: ok(depth) && ok(emp) && expPct !== null ? T3.tryIt.chartLines(fmt(expPct, 2) as string, fmt(depth * 100, 2) as string, fmt(2 * emp * 100, 2) as string) : null,
      readings,
      y: yRange(fold(readings, stops[knownIndex].period_d, pl.t0_bjd_tdb as number, ok(f.window_h) ? f.window_h : 9)),
      window: ok(f.window_h) ? f.window_h : 9,
      barRange,
    }
  }

  const png = f.picture?.png
  const fb = f.fallback_png
  const star = f.picture?.star_px
  const ring = ok(f.picture?.crop_px) && star && ok(star[0]) && ok(star[1]) && ok(f.aperture_px) ? { crop: f.picture?.crop_px as number, x: star[0], y: star[1], r: f.aperture_px } : null
  const factor = d5.noise_factor
  const yearsSci = years.length ? years.map(([y, v]) => `${y} ${fmt((v.depth ?? NaN) * 100, 2)} ± ${fmt((v.formal_err ?? NaN) * 100, 2)}%`).join(', ') : undefined
  const yearsEmp =
    years.length && ok(factor)
      ? `${years.map(([, v]) => `± ${fmt((v.formal_err ?? NaN) * factor * 100, 2)}`).join(' and ')} (${years.map(([, v]) => `${fmt((v.depth ?? NaN) / ((v.formal_err ?? NaN) * factor), 1)}σ`).join(' and ')})`
      : undefined
  const w100each = per
    ? Object.entries(w100.per_detector ?? {})
        .filter(([, d]) => !d.excluded)
        .map(([k, d]) => `D${k} ${fmt((d.depth ?? NaN) * 100, 2)} ± ${fmt((d.empirical_err ?? NaN) * 100, 2)}% (${fmt(d.empirical_sigma, 1)}σ)`)
        .join(', ')
    : undefined
  const w100match =
    per && ok(w100.expected_depth)
      ? Object.entries(w100.per_detector ?? {})
          .filter(([, d]) => !d.excluded && ok(d.depth) && ok(d.empirical_err))
          .map(([k, d]) => {
            const z = ((d.depth as number) - (w100.expected_depth as number)) / (d.empirical_err as number)
            return `D${k} ${fmt(Math.abs(z), 1)}σ ${z > 0 ? 'deeper' : 'shallower'}`
          })
          .join(', ')
      : undefined
  const fi = d5.fakes_independent
  const sci = sciParagraphs(SCI.t3, {
    period: ok(period) ? period.toFixed(8) : undefined,
    t0: ok(pl.t0_bjd_tdb) ? pl.t0_bjd_tdb.toFixed(6) : undefined,
    ra: ok(pl.ra) ? pl.ra.toFixed(5) : undefined,
    dec: ok(pl.dec) ? `${pl.dec < 0 ? MINUS : ''}${Math.abs(pl.dec).toFixed(5)}` : undefined,
    t14: fmt(t14, 2),
    rprs: fmt(pl.rprs, 4),
    expected: expPct !== null ? fmt(expPct, 2) : undefined,
    pubLo: Array.isArray(pr) && ok(pr[0]) ? fmt(pr[0], 2) : undefined,
    pubHi: Array.isArray(pr) && ok(pr[1]) ? fmt(pr[1], 2) : undefined,
    aperture: fmt(f.aperture_px, 1),
    nFake: fmtInt(d5.n_fake),
    factor: fmt(d5.noise_factor, 2),
    exposures: fmtInt(f.coverage?.exposures),
    wl: ok(d5.wl_min) && ok(d5.wl_max) ? `${fmt(d5.wl_min, 2)}–${fmt(d5.wl_max, 2)}` : undefined,
    cutouts: fmtInt(d5.n_cutouts),
    n: fmtInt(d5.n),
    nIn: fmtInt(d5.n_in),
    nTransits: fmtInt(d5.n_transits),
    depth: ok(depth) ? fmt(depth * 100, 2) : undefined,
    emp: ok(emp) ? fmt(emp * 100, 2) : undefined,
    formal: ok(d5.formal_err) ? fmt(d5.formal_err * 100, 2) : undefined,
    empSigma: fmt(d5.empirical_sigma, 1),
    halo: ok(f.halo?.depth) ? fmt((f.halo?.depth as number) * 100, 2) : undefined,
    haloErr: ok(f.halo?.empirical_err) ? fmt((f.halo?.empirical_err as number) * 100, 2) : undefined,
    haloN: fmtInt(f.halo?.n_in),
    haloSigma: fmt(f.halo?.empirical_sigma, 1),
    lo2: ok(depth) && ok(emp) ? fmt((depth - 2 * emp) * 100, 2) : undefined,
    hi2: ok(depth) && ok(emp) ? fmt((depth + 2 * emp) * 100, 2) : undefined,
    asDeep: nDeep !== null ? fmtInt(nDeep) : undefined,
    overlap: fi && ok(fi.share_of_pairs_sharing_a_reading) ? fmtInt(fi.share_of_pairs_sharing_a_reading * 100) : undefined,
    nInd: fi ? fmtInt(fi.n_independent_about) : undefined,
    pBelow: fi && ok(fi.p_below) ? fmt(fi.p_below * 100, 1) : undefined,
    deepestFake: ok(d5.deepest_fake_depth) ? fmt(d5.deepest_fake_depth * 100, 2) : undefined,
    signBelow: fmtInt(d5.sign_test?.n_below_baseline),
    signN: fmtInt(d5.sign_test?.n_transits),
    signP: powerOfTen(d5.sign_test?.p_value),
    choicesRange: choiceRange(d5.choices, f.aperture_radius_px, f.halo?.depth),
    slide: fmt(d5.slide_peak_h, 1),
    years: yearsSci && !yearsSci.includes('undefined') ? yearsSci : undefined,
    yearsEmp: yearsEmp && !/undefined|NaN/.test(yearsEmp) ? yearsEmp : undefined,
    jack: ok(d5.jackknife_min) && ok(d5.jackknife_max) ? `${fmt(d5.jackknife_min * 100, 2)}–${fmt(d5.jackknife_max * 100, 2)}` : undefined,
    compG: fmt(comp?.gmag, 1),
    compDist: fmtInt(comp?.distance_arcsec),
    compDepth: ok(comp?.depth) ? fmt((comp?.depth as number) * 100, 2) : undefined,
    compErr: ok(comp?.err) ? fmt((comp?.err as number) * 100, 2) : undefined,
    scatter: ok(d5.scatter) ? fmt(d5.scatter * 100, 2) : undefined,
    w100each: w100each && !w100each.includes('undefined') ? w100each : undefined,
    w100match: w100match && !/undefined|NaN/.test(w100match) ? w100match : undefined,
    w100dets: comb?.detectors?.length ? comb.detectors.join(', D') : undefined,
    w100comb: comb && ok(comb.depth) && ok(comb.error) ? `${fmt(comb.depth * 100, 2)} ± ${fmt(comb.error * 100, 2)}` : undefined,
    w100exp: ok(w100.expected_depth) ? fmt(w100.expected_depth * 100, 3) : undefined,
  })

  return {
    fixture: f.fixture === true,
    final: f.final === true,
    chip,
    glance,
    headline,
    asPublished,
    lead,
    picture: typeof png === 'string' && png ? { src: labUrl(png) } : { why: whyOf(f.picture, 'png') ?? whyOf(f, 'picture') ?? PAGE.pictureNotReady },
    ring,
    test,
    numbers,
    after,
    howSure,
    dialNote,
    dial,
    fallback: dial ? null : typeof fb === 'string' && fb ? labUrl(fb) : null,
    answerLine: a1 === true ? T3.answerFound : a1 === false ? T3.answerNot : null,
    sci,
  }
}
