// The "What is it?" card's data: the /api/identify answer, how it is fetched, and every
// sentence the card says, as pure functions. Each sentence is built only from what the
// lookup returned; a value it did not return is said to be unknown, never guessed.
import { NEAREST_STAR_LY, colourWord, glowsVisibly, SMALL_RADIUS_RSUN, JUPITER_RADIUS_KM, SUN_RADIUS_KM, SUN_TEFF_K } from './portrait'

// ------------------------------------------------------------------ the answer

export interface Quantity {
  key: string
  label: string
  value: number | string
  error: number | null
  lower: number | null
  upper: number | null
  unit: string
  catalogue: 'Gaia DR3' | 'SIMBAD'
  column: string
  error_column: string | null
  range_columns: string[] | null
  reference: string | null
  note: string | null
}

export interface TypeWords {
  code: string
  label: string
  plain: string | null
  candidate: boolean
}

export interface SpectralWords {
  text: string
  class: string | null
  luminosity_class: string | null
  label: string | null
  plain: string | null
  pair: boolean
  parts: string[]
}

export interface Position {
  ra: number
  dec: number
  epoch: number | null
}

export interface GaiaEntry {
  source_id: string
  name: string
  separation_arcsec: number
  east_arcsec: number
  north_arcsec: number
  position: Position
  catalogue_position: Position
  values: Quantity[]
}

export interface Relative {
  oid: number
  name: string
  display_name: string
  type: TypeWords | null
  references: number | null
}

export interface SimbadEntry {
  oid: number
  main_id: string
  display_name: string
  separation_arcsec: number
  east_arcsec: number
  north_arcsec: number
  position: Position
  type: TypeWords | null
  spectral_type: SpectralWords | null
  spectral_type_reference: string | null
  references: number | null
  gaia_dr3_ids: string[]
  parents: Relative[] | null
  children: Relative[] | null
  planets: Relative[] | null
  temperatures: { n: number; median: number | null; min: number | null; max: number | null; column: string; references: string[] } | null
  values?: Quantity[]
}

export interface Neighbour {
  catalogue: 'Gaia DR3' | 'SIMBAD'
  name: string
  source_id?: string
  oid?: number
  simbad_name: string | null
  simbad_type: TypeWords | null
  separation_arcsec: number
  east_arcsec: number
  north_arcsec: number
  from_object_arcsec: number
  g_mag: number | null
  bp_rp: number | null
  parallax: number | null
  parallax_error: number | null
  same_pixel: boolean
}

export interface DistanceDerived {
  status: 'from_parallax' | 'parallax_too_uncertain' | 'negative_parallax' | 'parallax_has_no_error'
  pc: number | null
  pc_error: number | null
  ly: number | null
  ly_error: number | null
  parallax_over_error: number | null
  catalogue: string
  inputs: string[]
  formula: string
  reference: string | null
}

export interface Derived {
  from: string | null
  distance: DistanceDerived | null
  distance_estimate: {
    pc: number
    pc_lower: number | null
    pc_upper: number | null
    ly: number
    ly_lower: number | null
    ly_upper: number | null
    catalogue: string
    inputs: string[]
    note: string
  } | null
  motion: {
    mas_per_year: number
    mas_per_year_error: number | null
    arcsec_per_year: number
    arcsec_per_year_error: number | null
    pixels_per_year: number
    pixels_per_year_error: number | null
    years_per_pixel: number | null
    catalogue: string
    inputs: string[]
    formula: string
    reference: string | null
  } | null
  speed: { km_s: number; km_s_error: number | null; catalogue: string; inputs: string[]; formula: string } | null
}

export interface Service {
  name: string
  answered: boolean
  via: string | null
  error: string | null
  partial: string[]
}

export interface IdentifyResult {
  query: { ra: number; dec: number; radius_arcsec: number; epoch: number; neighbour_radius_arcsec: number; pixel_arcsec: number }
  services: { gaia: Service; simbad: Service }
  unreachable: string[]
  nothing_catalogued: boolean | null
  nearest_catalogued: { catalogue: string; name: string; simbad_name: string | null; separation_arcsec: number; g_mag: number | null } | null
  searched_arcsec: number
  gaia: GaiaEntry | null
  simbad: SimbadEntry | null
  match: { same: boolean; how: 'identifier' | 'position' | 'different'; text: string } | null
  derived: Derived
  portrait: { temperature: Quantity | null; radius: Quantity | null; luminosity: Quantity | null }
  neighbours: Neighbour[]
  notes: string[]
  credit: string
}

// ------------------------------------------------------------------ fetching

export function identifyUrl(ra: number, dec: number, radiusArcsec?: number, epoch?: number): string {
  const p = new URLSearchParams({ ra: String(ra), dec: String(dec) })
  if (radiusArcsec != null) p.set('radius', String(radiusArcsec))
  if (epoch != null) p.set('epoch', String(epoch))
  return `/api/identify?${p.toString()}`
}

/** Ask the backend. Rejects with an Error whose message is a plain sentence for the visitor. */
export async function fetchIdentify(url: string, signal?: AbortSignal): Promise<IdentifyResult> {
  let r: Response
  try {
    r = await fetch(url, { signal })
  } catch (e) {
    if (signal?.aborted) throw e
    throw new Error('The server could not be reached, so nothing could be looked up. Try again in a moment.', { cause: e })
  }
  let body: unknown
  try {
    body = await r.json()
  } catch (e) {
    if (signal?.aborted) throw e
    body = undefined
  }
  if (!r.ok) {
    const detail = body && typeof body === 'object' && typeof (body as { detail?: unknown }).detail === 'string' ? (body as { detail: string }).detail : null
    if (r.status === 502 || r.status === 504) throw new Error(detail ?? 'The catalogues could not be reached. Try again in a moment.')
    if (r.status === 404) throw new Error('This server does not offer the lookup (it answered "not found" for /api/identify).')
    throw new Error(detail ?? `The lookup failed (error ${r.status}). Try again.`)
  }
  if (!body || typeof body !== 'object' || !('services' in body) || !('neighbours' in body)) {
    throw new Error('The server answered, but not with a lookup. It may be the wrong server.')
  }
  return body as IdentifyResult
}

// ------------------------------------------------------------------ numbers in words

/** A number with thousands separators and the given decimals. */
export function num(v: number, decimals = 0): string {
  return v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

/** Three significant figures, written plainly: 5.96, 12.1, 598, 2,610, 6,630. */
export function sig3(v: number): string {
  if (v === 0) return '0'
  const digits = Math.max(0, 2 - Math.floor(Math.log10(Math.abs(v))))
  const rounded = Number(v.toPrecision(3))
  return num(rounded, Math.min(digits, 3))
}

/** Temperature rounded for reading: 3,100, 1,400, 285. */
export function roundTemperature(k: number): string {
  if (k >= 1000) return num(Math.round(k / 100) * 100)
  return num(Math.round(k / 5) * 5)
}

/** An angle per year in arcseconds, with sensible decimals: 10.4, 0.76, 0.025, 0.0032. */
export function arcsec(v: number): string {
  if (v >= 1) return num(v, 1)
  if (v >= 0.1) return num(v, 2)
  return Number(v.toPrecision(2)).toString()
}

const FRACTIONS: [number, string][] = [
  [1 / 2, 'half'],
  [1 / 3, 'a third'],
  [1 / 4, 'a quarter'],
  [1 / 5, 'a fifth'],
  [1 / 6, 'a sixth'],
  [1 / 8, 'an eighth'],
  [1 / 10, 'a tenth'],
]

/** How wide beside something else, in words: "about a fifth as wide as", "about 1.2 times as wide as". */
export function widthWords(ratio: number, what: string): string {
  if (ratio > 0.9 && ratio < 1.1) return `about as wide as ${what}`
  if (ratio < 1) {
    const close = FRACTIONS.find(([f]) => Math.abs(ratio / f - 1) < 0.08)
    if (close) return `about ${close[1]} as wide as ${what}`
    return `about ${num(ratio, 2)} times as wide as ${what}`
  }
  return `about ${sig3(ratio)} times as wide as ${what}`
}

/** Brightness ratio from a G-magnitude difference (visible light): 10^(0.4 dG). */
export function timesFainter(dG: number): number {
  return 10 ** (0.4 * dG)
}

function roundRatio(v: number): string {
  if (v < 10) return num(v, 0)
  const p = 10 ** Math.floor(Math.log10(v))
  return num(Math.round(v / p) * p)
}

/** "a" or "an" as the word is said: an M dwarf, an HII region, an RR Lyrae, a BY Draconis, a Mira. */
export function article(phrase: string): 'a' | 'an' {
  const first = phrase.split(/[ -]/)[0]
  if (/^[A-Z]{1,4}$/.test(first)) return 'AEFHILMNORSX'.includes(first[0]) ? 'an' : 'a'
  return /^[aeiou]/i.test(first) ? 'an' : 'a'
}

// ------------------------------------------------------------------ what the card says

/** Generic SIMBAD types, where the spectral type says more about what the thing is. */
const GENERIC_TYPES = new Set(['*', 'PM*', 'LM*', 'MS*', 'BY*', 'V*', 'Ro*', 'Er*', '**', 'SB*', 'Em*', 'HV*'])
/** For a brown dwarf, an L, T or Y class says which kind. */
const BROWN_DWARF_CLASSES = new Set(['L', 'T', 'Y'])

export const NO_NAME = 'An object with no name in the catalogues we asked'
export const NOTHING_HERE = 'Nothing is listed here in Gaia or SIMBAD. What SPHEREx sees here is in the brightness and colours tools.'
export const ILLUSTRATION_LABEL = 'Illustration drawn from measurements. Not a photograph.'
export const TOO_COOL = 'too cool to glow in light our eyes can see: it shines in infrared, which is why SPHEREx can see it'

export function cardTitle(r: IdentifyResult, name?: string): string {
  if (name && name.trim()) return name.trim()
  if (r.simbad) return r.simbad.display_name
  return NO_NAME
}

/** SIMBAD's own name for it, when the card's title is something else. */
export function catalogueName(r: IdentifyResult, name?: string): string | null {
  if (!r.simbad || !name) return null
  const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')
  return norm(name) === norm(r.simbad.display_name) ? null : r.simbad.display_name
}

/** One sentence: what kind of thing this is, as the catalogues class it. */
export function kindSentence(r: IdentifyResult): string | null {
  const s = r.simbad
  if (s) {
    const t = s.type
    const sp = s.spectral_type
    const refines = t?.code === 'BD*' && BROWN_DWARF_CLASSES.has(sp?.class ?? '')
    if (sp?.plain && sp.label && (!t?.plain || GENERIC_TYPES.has(t.code) || refines) && !sp.pair) {
      return `SIMBAD lists it as ${article(sp.label)} ${sp.label}: ${sp.plain}.`
    }
    if (t?.plain) return `SIMBAD lists it as ${article(t.label)} ${t.label}: ${t.plain}.`
    if (sp?.plain && sp.label) return `SIMBAD lists it as ${article(sp.label)} ${sp.label}: ${sp.plain}.`
    if (t) return `SIMBAD lists it under the type "${t.code}", which our table does not put into words.`
    return 'SIMBAD lists it, but does not say what kind of object it is.'
  }
  if (r.gaia) return 'Gaia lists it, but no catalogue we asked says what kind of object it is.'
  return null
}

/** The system or group SIMBAD counts it part of, when that is a star or a pair. */
export function partOfSentence(r: IdentifyResult): string | null {
  const groups = new Set(['As*', 'Cl*', 'St*'])
  const stellar = (r.simbad?.parents ?? []).find((p) => p.type && p.type.code.includes('*') && !groups.has(p.type.code))
  return stellar ? `SIMBAD lists it as part of ${stellar.display_name}.` : null
}

/** The light of the object in G (visible), for comparing with neighbours. */
function objectG(r: IdentifyResult): number | null {
  const g = r.gaia?.values.find((v) => v.key === 'phot_g_mean_mag')
  return g && typeof g.value === 'number' ? g.value : null
}

/** Do other catalogued stars share the blur? One or two short sentences, or null. */
export function blurSentences(r: IdentifyResult): string[] {
  const out: string[] = []
  const sp = r.simbad?.spectral_type
  if (sp?.pair) out.push(`It is a pair: SIMBAD's type, ${sp.text}, names two objects seen as one point.`)
  const same = r.neighbours.filter((n) => n.same_pixel)
  if (same.length === 0) return out
  const g0 = objectG(r)
  const comparable = same.filter((n) => g0 == null || n.g_mag == null || n.g_mag - g0 <= 2.5)
  const faint = same.filter((n) => !comparable.includes(n))
  if (comparable.length) {
    const first = comparable[0]
    const who = first.simbad_name ? first.simbad_name.replace(/^(V\*|\*\*|\*|NAME)\s+/, '') : 'another star'
    const brighter = g0 != null && first.g_mag != null ? (first.g_mag < g0 ? ', brighter,' : ', fainter,') : ''
    const n = comparable.length + (r.gaia || r.simbad ? 1 : 0)
    out.push(
      `This blur holds ${n} catalogued stars, not one: ${who}${brighter} is ${num(first.from_object_arcsec, 1)} arcseconds away.`,
    )
  }
  if (faint.length) {
    const ratio = g0 != null && faint[0].g_mag != null ? timesFainter(faint[0].g_mag - g0) : null
    const also = comparable.length ? ' also' : ''
    out.push(
      faint.length === 1
        ? ratio
          ? `Gaia${also} lists one other star in the same SPHEREx pixel, about ${roundRatio(ratio)} times fainter in visible light.`
          : `Gaia${also} lists one other, fainter star in the same SPHEREx pixel.`
        : `Gaia${also} lists ${faint.length} other, much fainter stars in the same SPHEREx pixel.`,
    )
  }
  return out
}

export interface Fact {
  text: string
  source: string
}

/** Two significant figures, for an uncertainty: 36, 850, 0.031. */
export function sig2(v: number): string {
  if (v === 0) return '0'
  const digits = Math.max(0, 1 - Math.floor(Math.log10(Math.abs(v))))
  return num(Number(v.toPrecision(2)), Math.min(digits, 3))
}

/**
 * Gaia's renormalised unit weight error. About 1 for a well-fitted single star; above 1.4
 * the astrometry is usually disturbed, most often by an unresolved companion (Lindegren,
 * Gaia technical note GAIA-C3-TN-LU-LL-124, 2018; the usual cut since).
 */
export const RUWE_LIMIT = 1.4

export function gaiaRuwe(r: IdentifyResult): number | null {
  const q = r.gaia?.values.find((v) => v.key === 'ruwe')
  return q && typeof q.value === 'number' ? q.value : null
}

function distanceFact(r: IdentifyResult): Fact | null {
  const d = r.derived.distance
  const source = r.derived.from === 'SIMBAD' ? 'SIMBAD' : 'Gaia'
  if (d && d.status === 'from_parallax' && d.ly != null) {
    const giveOrTake = d.ly_error != null && d.ly_error / d.ly > 0.03 ? `, give or take ${sig2(d.ly_error)}` : ''
    const years = d.ly < 10 ? num(Math.round(d.ly)) : sig3(d.ly)
    let text = `It is about ${sig3(d.ly)} light-years away${giveOrTake}. The light we see left it ${years} years ago.`
    const ruwe = gaiaRuwe(r)
    if (source === 'Gaia' && ruwe != null && ruwe > RUWE_LIMIT) {
      text += ' Gaia\'s fit for it is poor (often a sign of a close pair), so this distance is less sure.'
    }
    return { text, source }
  }
  const est = r.derived.distance_estimate
  if (est) {
    return {
      text: `Its distance is not measured well enough to say. Gaia's own estimate is about ${sig3(est.ly)} light-years.`,
      source: 'Gaia',
    }
  }
  if (d) return { text: 'Its distance is not measured well enough to say.', source }
  return null
}

function temperatureFact(r: IdentifyResult): Fact | null {
  const t = r.portrait.temperature
  if (!t || typeof t.value !== 'number') return null
  const source = t.catalogue === 'SIMBAD' ? 'SIMBAD' : 'Gaia'
  const k = roundTemperature(t.value)
  if (!glowsVisibly(t.value)) {
    return { text: `Its surface is about ${k} degrees (kelvin), far cooler than the Sun's ${num(SUN_TEFF_K)}.`, source }
  }
  const compare = t.value < SUN_TEFF_K * 0.95 ? `, cooler than the Sun's ${num(SUN_TEFF_K)}` : t.value > SUN_TEFF_K * 1.05 ? `, hotter than the Sun's ${num(SUN_TEFF_K)}` : ', like the Sun'
  return { text: `Its surface is about ${k} degrees (kelvin)${compare}, so it glows ${colourWord(t.value)}.`, source }
}

function sizeFact(r: IdentifyResult): Fact | null {
  const rad = r.portrait.radius
  if (!rad || typeof rad.value !== 'number') return null
  const words = widthWords(rad.value, 'the Sun')
  const exact = /times/.test(words) ? '' : ` (${num(rad.value, 2)} times)`
  let text = `It is ${words}${exact}.`
  if (rad.value < SMALL_RADIUS_RSUN) text += ` That is ${widthWords(rad.value / (JUPITER_RADIUS_KM / SUN_RADIUS_KM), 'Jupiter')}.`
  return { text, source: 'Gaia' }
}

function motionFact(r: IdentifyResult): Fact | null {
  const m = r.derived.motion
  if (!m) return null
  const source = m.catalogue === 'SIMBAD' ? 'SIMBAD' : 'Gaia'
  const parts: string[] = []
  if (m.pixels_per_year >= 0.1) {
    parts.push(
      `Each year it drifts ${num(m.pixels_per_year, 1)} SPHEREx pixels across our sky: ${arcsec(m.arcsec_per_year)} arcseconds, each 1/3600 of a degree.`,
    )
  } else {
    parts.push(`It drifts ${arcsec(m.arcsec_per_year)} arcseconds a year across our sky (an arcsecond is 1/3600 of a degree).`)
    if (m.years_per_pixel != null) parts.push(`It takes about ${sig3(m.years_per_pixel)} years to cross one SPHEREx pixel.`)
  }
  if (r.derived.speed) parts.push(`Across our view it moves ${num(r.derived.speed.km_s)} km every second.`)
  return { text: parts.join(' '), source }
}

function studiedFact(r: IdentifyResult): Fact | null {
  const n = r.simbad?.references
  if (n == null) return null
  if (n === 0) return { text: 'No scientific paper in SIMBAD is about it yet.', source: 'SIMBAD' }
  return { text: `SIMBAD lists ${num(n)} scientific ${n === 1 ? 'paper' : 'papers'} about it.`, source: 'SIMBAD' }
}

/** At most five short facts, each with where its number comes from. */
export function beginnerFacts(r: IdentifyResult): Fact[] {
  return [distanceFact(r), temperatureFact(r), sizeFact(r), motionFact(r), studiedFact(r)].filter((f): f is Fact => f != null).slice(0, 5)
}

/** What is not known, in one line. */
export function notKnownLine(r: IdentifyResult): string {
  const missing: string[] = []
  if (!r.portrait.temperature) missing.push('its temperature')
  if (!r.portrait.radius) missing.push('its size')
  const d = r.derived.distance
  if (!(d && d.status === 'from_parallax') && !r.derived.distance_estimate) missing.push('its distance')
  if (!r.derived.motion) missing.push('its motion')
  missing.push('its surface details')
  const list = missing.length === 1 ? missing[0] : `${missing.slice(0, -1).join(', ')}, or ${missing.at(-1)}`
  const planets = r.simbad?.planets?.length ?? 0
  const around =
    planets === 0
      ? ''
      : ` SIMBAD lists ${planets === 1 ? 'a planet' : `${planets} planets`} around it; ${planets === 1 ? 'its size is' : 'their sizes are'} not in the catalogues we asked.`
  return `Not in the catalogues we asked: ${list}.${around}`
}

/** Under the picture: what each drawn thing was computed from. */
export function pictureNotes(r: IdentifyResult): string[] {
  const out: string[] = []
  const t = r.portrait.temperature
  const rad = r.portrait.radius
  if (t && typeof t.value === 'number') {
    const col = t.column.split('.').at(-1)
    if (glowsVisibly(t.value)) {
      out.push(`Colour: how a ${num(Math.round(t.value))} K surface looks to the eye (${t.catalogue} ${col}).`)
    } else {
      out.push(`Dark disc: ${num(Math.round(t.value))} K (${t.catalogue} ${col}).`)
      out.push(`${TOO_COOL[0].toUpperCase()}${TOO_COOL.slice(1)}.`)
    }
    if (r.simbad?.spectral_type?.pair) out.push('Gaia measured the pair as one point: this is one temperature for both.')
  } else if (rad) {
    out.push('Outline only: its temperature, so its colour, is not measured.')
  }
  if (rad && typeof rad.value === 'number') {
    const col = rad.column.split('.').at(-1)
    const planets = rad.value < SMALL_RADIUS_RSUN ? ', with Jupiter and the Earth as outlines' : ''
    out.push(`Size: ${num(rad.value, rad.value < 10 ? 3 : 1)} times the Sun's radius (Gaia ${col}), beside the Sun to scale${planets}.`)
  } else if (t) {
    out.push("Size not measured: the disc's size means nothing, and the Sun is not shown.")
  }
  if (t && glowsVisibly(t.value as number)) out.push('Edge darkening: a standard approximation (linear law, u = 0.6), the same for every star.')
  if (t || rad) out.push('Brightness is not to scale. No spots, flares or other surface details are drawn: none are measured.')
  return out
}

/** The short label under the object's own disc. */
export function discLabel(r: IdentifyResult, name?: string): string {
  const t = cardTitle(r, name)
  return t.length <= 16 && t !== NO_NAME ? t : 'This object'
}

export function distanceForScale(r: IdentifyResult): { ly: number; low: number | null; high: number | null; estimate: boolean } | null {
  const d = r.derived.distance
  if (d && d.status === 'from_parallax' && d.ly != null) {
    const e = d.ly_error ?? 0
    return { ly: d.ly, low: e ? d.ly - e : null, high: e ? d.ly + e : null, estimate: false }
  }
  const est = r.derived.distance_estimate
  if (est) return { ly: est.ly, low: est.ly_lower, high: est.ly_upper, estimate: true }
  return null
}

export function distanceScaleCaption(d: { ly: number; estimate: boolean }, source: string): string {
  const what = d.estimate ? `How far, by Gaia's own estimate: ${sig3(d.ly)} light-years.` : `How far: ${sig3(d.ly)} light-years (${source}).`
  return `${what} The nearest star, Proxima Centauri, is ${NEAREST_STAR_LY} light-years away.`
}

// ------------------------------------------------------------------ the expert table

export interface ExpertRow {
  quantity: string
  value: string
  uncertainty: string
  unit: string
  catalogue: string
  column: string
}

function fmtValue(v: number | string, unit: string): string {
  if (typeof v === 'string') return v
  const a = Math.abs(v)
  if (unit === 'K') return num(v, 0)
  if (a === 0) return '0'
  if (a >= 1000) return num(v, 1)
  if (a >= 1) return v.toPrecision(Math.max(6, Math.floor(Math.log10(a)) + 4)).replace(/\.?0+$/, '')
  return v.toPrecision(4)
}

function fmtErr(q: { error: number | null; lower: number | null; upper: number | null }, unit: string): string {
  if (q.error != null) return `± ${fmtValue(q.error, unit === 'K' ? '' : unit)}`
  if (q.lower != null && q.upper != null) {
    const lo = fmtValue(q.lower, unit)
    const hi = fmtValue(q.upper, unit)
    // A range narrower than the digits shown (Gaia's FLAME luminosity of Barnard's Star,
    // 0.0033978 to 0.0033984) gets the digits it needs.
    return lo === hi ? `${q.lower.toPrecision(6)} to ${q.upper.toPrecision(6)}` : `${lo} to ${hi}`
  }
  return ''
}

export function expertRows(r: IdentifyResult): ExpertRow[] {
  const rows: ExpertRow[] = []
  const values = r.gaia?.values ?? r.simbad?.values ?? []
  for (const q of values) {
    rows.push({
      quantity: q.label,
      value: fmtValue(q.value, q.unit),
      uncertainty: fmtErr(q, q.unit),
      unit: q.unit,
      catalogue: q.catalogue + (q.reference ? ` (${q.reference})` : ''),
      column: q.column + (q.error_column ? `; error: ${q.error_column}` : '') + (q.range_columns ? `; range: ${q.range_columns.join(', ')}` : ''),
    })
  }
  const d = r.derived
  const ruwe = gaiaRuwe(r)
  if (ruwe != null && ruwe > RUWE_LIMIT) {
    rows.push({
      quantity: 'Caution: RUWE above 1.4',
      value: num(ruwe, 2),
      uncertainty: '',
      unit: '',
      catalogue: 'Gaia DR3',
      column: 'gaia_source.ruwe; the astrometry is disturbed, often by an unresolved companion: parallax, motion and what is derived from them are less sure than their errors say',
    })
  }
  if (d.distance) {
    if (d.distance.status === 'from_parallax' && d.distance.pc != null && d.distance.ly != null) {
      rows.push({ quantity: 'Distance (1 / parallax)', value: fmtValue(d.distance.pc, 'pc'), uncertainty: fmtErr({ error: d.distance.pc_error, lower: null, upper: null }, 'pc'), unit: 'pc', catalogue: `derived, ${d.distance.catalogue}`, column: d.distance.formula })
      rows.push({ quantity: 'Distance', value: fmtValue(d.distance.ly, 'ly'), uncertainty: fmtErr({ error: d.distance.ly_error, lower: null, upper: null }, 'ly'), unit: 'light-years', catalogue: `derived, ${d.distance.catalogue}`, column: 'pc x 3.26156' })
    } else {
      const why = d.distance.status === 'parallax_too_uncertain' ? `parallax only ${num(d.distance.parallax_over_error ?? 0, 1)} times its error (5 needed)` : d.distance.status.replace(/_/g, ' ')
      rows.push({ quantity: 'Distance (1 / parallax)', value: 'not given', uncertainty: why, unit: '', catalogue: `derived, ${d.distance.catalogue}`, column: d.distance.formula })
    }
  }
  if (d.distance_estimate) {
    const e = d.distance_estimate
    rows.push({ quantity: "Distance, Gaia's estimate (GSP-Phot)", value: fmtValue(e.ly, 'ly'), uncertainty: e.ly_lower != null && e.ly_upper != null ? `${fmtValue(e.ly_lower, 'ly')} to ${fmtValue(e.ly_upper, 'ly')}` : '', unit: 'light-years', catalogue: 'Gaia DR3', column: e.inputs.join(', ') })
  }
  if (d.motion) {
    const m = d.motion
    rows.push({ quantity: 'Total proper motion', value: fmtValue(m.arcsec_per_year, 'arcsec/yr'), uncertainty: fmtErr({ error: m.arcsec_per_year_error, lower: null, upper: null }, ''), unit: 'arcsec/yr', catalogue: `derived, ${m.catalogue}`, column: m.formula })
    rows.push({ quantity: 'Motion in SPHEREx pixels (6.15 arcsec)', value: fmtValue(m.pixels_per_year, 'px/yr'), uncertainty: fmtErr({ error: m.pixels_per_year_error, lower: null, upper: null }, ''), unit: 'pixels/yr', catalogue: `derived, ${m.catalogue}`, column: 'mu / 6.15' })
  }
  if (d.speed) {
    rows.push({ quantity: 'Speed across the line of sight', value: fmtValue(d.speed.km_s, 'km/s'), uncertainty: fmtErr({ error: d.speed.km_s_error, lower: null, upper: null }, 'km/s'), unit: 'km/s', catalogue: `derived, ${d.speed.catalogue}`, column: d.speed.formula })
  }
  const s = r.simbad
  if (s) {
    if (s.type) rows.push({ quantity: 'Object type', value: s.type.code, uncertainty: '', unit: '', catalogue: 'SIMBAD', column: `basic.otype (${s.type.label})` })
    if (s.spectral_type) rows.push({ quantity: 'Spectral type', value: s.spectral_type.text, uncertainty: '', unit: '', catalogue: `SIMBAD${s.spectral_type_reference ? ` (${s.spectral_type_reference})` : ''}`, column: 'basic.sp_type' })
    if (s.references != null) rows.push({ quantity: 'References', value: num(s.references), uncertainty: '', unit: 'papers', catalogue: 'SIMBAD', column: 'basic.nbref' })
    const t = s.temperatures
    if (t && t.n && t.median != null) {
      rows.push({ quantity: `Temperatures listed (${t.n} values)`, value: `median ${num(t.median)}`, uncertainty: `${num(t.min ?? 0)} to ${num(t.max ?? 0)}`, unit: 'K', catalogue: 'SIMBAD', column: t.column })
    }
  }
  return rows
}

/** Which service gave the numbers, for the expert view. */
export function servicesLine(r: IdentifyResult): string {
  return [r.services.gaia, r.services.simbad]
    .map((s) => (s.answered ? `${s.name}: ${s.via}` : `${s.name}: did not answer`))
    .join('. ')
}

/** "Gaia DR3 did not answer" sentences for the card. */
export function unreachableSentence(r: IdentifyResult): string | null {
  if (!r.unreachable.length) return null
  const names = r.unreachable.join(' and ')
  const have = r.unreachable.length === 2 ? 'nothing could be looked up' : `this card shows only what ${r.unreachable.includes('SIMBAD') ? 'Gaia' : 'SIMBAD'} has`
  return `${names} did not answer just now, so ${have}.`
}

/** For "Look at this one": the object's place at the date of the pictures, with its motion when known. */
export interface LookTarget {
  ra: number
  dec: number
  pmra: number | null
  pmdec: number | null
  parallax: number | null
  name: string | null
}

export function lookTarget(r: IdentifyResult, name?: string): LookTarget {
  const value = (key: string) => {
    const q = (r.gaia?.values ?? r.simbad?.values ?? []).find((v) => v.key === key)
    return q && typeof q.value === 'number' ? q.value : null
  }
  const where = r.gaia?.position ?? r.simbad?.position ?? { ra: r.query.ra, dec: r.query.dec }
  return {
    ra: where.ra,
    dec: where.dec,
    pmra: value('pmra'),
    pmdec: value('pmdec'),
    parallax: value('parallax') ?? value('plx_value'),
    name: name ?? r.simbad?.display_name ?? r.gaia?.name ?? null,
  }
}
