// The "What is it?" card's data: the /api/identify answer, how it is fetched, and every
// sentence the card says, as pure functions. Each sentence is built only from what the
// lookup returned; a value it did not return is said to be unknown, never guessed.
import {
  JUPITER_RADIUS_KM,
  NEAREST_STAR_LY,
  SMALL_RADIUS_RSUN,
  SUN_RADIUS_KM,
  SUN_TEFF_K,
  colourWord,
  glowsVisibly,
  type Portrait,
} from './portrait'
import type { UiLevel } from './address'

// ------------------------------------------------------------------ the answer

export interface QualityFlag {
  column: string
  value: string
  /** what the flag says, where Gaia documents it plainly (ESP-UCD's quality class) */
  meaning: string | null
  /** ESP-UCD's lowest quality class */
  lowest_quality: boolean
}

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
  flags: QualityFlag | null
  /** fitted by Gaia with a model of stars (its astrophysical parameters), not measured directly */
  model: boolean
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
  /** at the date asked for (the picture's) */
  position: Position
  /** at 2026.0, the date /api/resolve gives positions for */
  resolve_position: Position
  catalogue_position: Position
  possibly_spurious: boolean
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
  resolve_position: Position
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
  display_name: string
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
  astrometric_params_solved: number | null
  visibility_periods_used: number | null
  possibly_spurious: boolean
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
  nearest_catalogued: {
    catalogue: string
    name: string
    display_name: string
    simbad_name: string | null
    separation_arcsec: number
    g_mag: number | null
    bp_rp: number | null
    same_pixel: boolean
    possibly_spurious: boolean
  } | null
  searched_arcsec: number
  gaia: GaiaEntry | null
  simbad: SimbadEntry | null
  match: { same: boolean; how: 'identifier' | 'position' | 'different'; text: string } | null
  /** how the object was chosen among the sources at the place */
  choice: { how: 'named' | 'light' | 'simbad'; text: string } | null
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
    throw new Error('The server could not be reached, so nothing could be looked up.', { cause: e })
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
    if (r.status === 502 || r.status === 504) throw new Error(detail ?? 'The catalogues could not be reached.')
    if (r.status === 404) throw new Error('This server does not offer the lookup (it answered "not found" for /api/identify).')
    throw new Error(detail ?? `The lookup failed (error ${r.status}).`)
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
  return num(Number(v.toPrecision(3)), Math.min(digits, 3))
}

/** Two significant figures: 36, 850, 0.031, 12, 510, 1.2. */
export function sig2(v: number): string {
  if (v === 0) return '0'
  const digits = Math.max(0, 1 - Math.floor(Math.log10(Math.abs(v))))
  return num(Number(v.toPrecision(2)), Math.min(digits, 3))
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
  return `about ${sig2(ratio)} times as wide as ${what}`
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

/** A list in words: "a", "a or b", "a, b, or c". */
export function orList(items: string[]): string {
  if (items.length <= 1) return items.join('')
  if (items.length === 2) return `${items[0]} or ${items[1]}`
  return `${items.slice(0, -1).join(', ')}, or ${items.at(-1)}`
}

/**
 * Decimal places for showing an error, by the Particle Data Group's rule (Review of Particle
 * Physics, "Rounding"): look at the error's first three digits; 100 to 354 keep two
 * significant figures, 355 to 949 keep one, 950 to 999 round up to 1000 and keep two. The
 * value is then given to the same decimal place. Never fewer than 0 decimals: a whole
 * number is not rounded further (1,417 ± 98 K, not 1,420 ± 100).
 */
export function errorDecimals(error: number): number {
  const e = Math.abs(error)
  if (!(e > 0) || !Number.isFinite(e)) return 0
  let exp = Math.floor(Math.log10(e))
  const lead = Math.round(e / 10 ** (exp - 2))
  let sig = 2
  if (lead >= 950) {
    exp += 1
  } else if (lead >= 355) {
    sig = 1
  }
  return Math.max(0, sig - 1 - exp)
}

/** A value and its error rounded together, as text. */
export function withError(value: number, error: number): { value: string; error: string } {
  const d = Math.min(errorDecimals(error), 10)
  return { value: num(value, d), error: num(error, d) }
}

// ------------------------------------------------------------------ names

const GREEK: Record<string, string> = {
  alf: 'Alpha', bet: 'Beta', gam: 'Gamma', del: 'Delta', eps: 'Epsilon', zet: 'Zeta', eta: 'Eta', tet: 'Theta',
  iot: 'Iota', kap: 'Kappa', lam: 'Lambda', 'mu.': 'Mu', 'nu.': 'Nu', ksi: 'Xi', omi: 'Omicron', 'pi.': 'Pi',
  rho: 'Rho', sig: 'Sigma', tau: 'Tau', ups: 'Upsilon', phi: 'Phi', chi: 'Chi', psi: 'Psi', ome: 'Omega',
}

/** The 88 IAU constellation abbreviations and the genitive used in star names. */
const CONSTELLATION_GENITIVE: Record<string, string> = {
  And: 'Andromedae', Ant: 'Antliae', Aps: 'Apodis', Aqr: 'Aquarii', Aql: 'Aquilae', Ara: 'Arae', Ari: 'Arietis',
  Aur: 'Aurigae', Boo: 'Bootis', Cae: 'Caeli', Cam: 'Camelopardalis', Cnc: 'Cancri', CVn: 'Canum Venaticorum',
  CMa: 'Canis Majoris', CMi: 'Canis Minoris', Cap: 'Capricorni', Car: 'Carinae', Cas: 'Cassiopeiae', Cen: 'Centauri',
  Cep: 'Cephei', Cet: 'Ceti', Cha: 'Chamaeleontis', Cir: 'Circini', Col: 'Columbae', Com: 'Comae Berenices',
  CrA: 'Coronae Australis', CrB: 'Coronae Borealis', Crv: 'Corvi', Crt: 'Crateris', Cru: 'Crucis', Cyg: 'Cygni',
  Del: 'Delphini', Dor: 'Doradus', Dra: 'Draconis', Equ: 'Equulei', Eri: 'Eridani', For: 'Fornacis',
  Gem: 'Geminorum', Gru: 'Gruis', Her: 'Herculis', Hor: 'Horologii', Hya: 'Hydrae', Hyi: 'Hydri', Ind: 'Indi',
  Lac: 'Lacertae', Leo: 'Leonis', LMi: 'Leonis Minoris', Lep: 'Leporis', Lib: 'Librae', Lup: 'Lupi', Lyn: 'Lyncis',
  Lyr: 'Lyrae', Men: 'Mensae', Mic: 'Microscopii', Mon: 'Monocerotis', Mus: 'Muscae', Nor: 'Normae',
  Oct: 'Octantis', Oph: 'Ophiuchi', Ori: 'Orionis', Pav: 'Pavonis', Peg: 'Pegasi', Per: 'Persei', Phe: 'Phoenicis',
  Pic: 'Pictoris', Psc: 'Piscium', PsA: 'Piscis Austrini', Pup: 'Puppis', Pyx: 'Pyxidis', Ret: 'Reticuli',
  Sge: 'Sagittae', Sgr: 'Sagittarii', Sco: 'Scorpii', Scl: 'Sculptoris', Sct: 'Scuti', Ser: 'Serpentis',
  Sex: 'Sextantis', Tau: 'Tauri', Tel: 'Telescopii', Tri: 'Trianguli', TrA: 'Trianguli Australis', Tuc: 'Tucanae',
  UMa: 'Ursae Majoris', UMi: 'Ursae Minoris', Vel: 'Velorum', Vir: 'Virginis', Vol: 'Volantis', Vul: 'Vulpeculae',
}

/**
 * A SIMBAD star name as it is said: "eps Ind B" is "Epsilon Indi B", "RW Aur A" "RW Aurigae
 * A", "R Dra" "R Draconis", "61 Cyg A" "61 Cygni A". Only names of that form (a Greek letter,
 * a variable-star letter or number, or a Flamsteed number, then a constellation, then an
 * optional component letter) are changed; every other name is returned as it is.
 */
export function readableName(name: string): string {
  const m = /^(\S+?)(\d{0,2})\s+([A-Z][A-Za-z]{2})(\s+[A-Z][a-z]?)?$/.exec(name.trim())
  if (!m) return name
  const [, lead, index, con, part = ''] = m
  const genitive = CONSTELLATION_GENITIVE[con]
  if (!genitive) return name
  const greek = GREEK[lead]
  if (greek) return `${greek}${index ? ` ${Number(index)}` : ''} ${genitive}${part}`
  const variable = /^([R-Z]|[R-Z][R-Z]|[A-Q][A-Z]|V\d{3,4})$/.test(lead + index)
  const flamsteed = /^\d{1,3}$/.test(lead + index)
  return variable || flamsteed ? `${lead}${index} ${genitive}${part}` : name
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')
const sameName = (a: string, b: string) => norm(a) === norm(b) || norm(readableName(a)) === norm(readableName(b))

// ------------------------------------------------------------------ what the card says

/** Generic SIMBAD types, where the spectral type says more about what the thing is. */
const GENERIC_TYPES = new Set(['*', 'PM*', 'LM*', 'MS*', 'BY*', 'V*', 'Ro*', 'Er*', '**', 'SB*', 'Em*', 'HV*'])
/** For a brown dwarf, an L, T or Y class says which kind. */
const BROWN_DWARF_CLASSES = new Set(['L', 'T', 'Y'])
/** Systems and groups SIMBAD lists a star as part of that are not a star system. */
const GROUP_TYPES = new Set(['As*', 'Cl*', 'St*', 'OpC', 'GlC', 'MGr', 'SFR'])

export const NO_NAME = 'An object with no name in the catalogues we asked'
export const NOTHING_TITLE = 'This place: nothing catalogued'
export const NOTHING_HERE = 'Nothing is listed here in Gaia or SIMBAD. What SPHEREx sees here is in the brightness and colours tools.'
export const ILLUSTRATION_LABEL = 'Illustration drawn from measurements. Not a photograph.'
export const PLATE_TAG = 'DRAWING, NOT A PHOTO'
export const TOO_COOL = 'too cool to glow in light our eyes can see: it shines in infrared, which is why SPHEREx can see it'
/** Gaia DR3 BP-RP of the Sun (Casagrande & VandenBerg 2018, MNRAS 479, L102): 0.82. */
export const SUN_BP_RP = 0.82

const found = (r: IdentifyResult) => r.gaia != null || r.simbad != null
const down = (r: IdentifyResult, service: 'Gaia DR3' | 'SIMBAD') => r.unreachable.includes(service)

/** The star system SIMBAD counts the object part of, when that system is the name the page asked about. */
export function namedSystem(r: IdentifyResult, name?: string): Relative | null {
  if (!name?.trim() || !r.simbad) return null
  if (sameName(name, r.simbad.display_name)) return null
  return (r.simbad.parents ?? []).find((p) => p.type && !GROUP_TYPES.has(p.type.code) && sameName(name, p.display_name)) ?? null
}

export function cardTitle(r: IdentifyResult, name?: string): string {
  if (r.simbad && namedSystem(r, name)) return readableName(r.simbad.display_name)
  if (name && name.trim()) return name.trim()
  if (r.simbad) return readableName(r.simbad.display_name)
  if (r.gaia) return down(r, 'SIMBAD') ? 'An object Gaia lists' : NO_NAME
  return r.nothing_catalogued === true ? NOTHING_TITLE : 'This place'
}

/** SIMBAD's own name for it, when the card's title is something else. */
export function catalogueName(r: IdentifyResult, name?: string): string | null {
  if (!r.simbad || !name || namedSystem(r, name)) return null
  return sameName(name, r.simbad.display_name) ? null : r.simbad.display_name
}

/** When the page asked about a system and the object is one of its stars: say so, with the system's study count. */
export function systemLine(r: IdentifyResult, name?: string): string | null {
  const sys = namedSystem(r, name)
  if (!sys) return null
  const refs = sys.references != null ? ` SIMBAD lists ${num(sys.references)} papers that mention the system.` : ''
  return `It is one of the stars of ${readableName(sys.display_name)}, the system you chose.${refs}`
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
  if (r.gaia) {
    if (down(r, 'SIMBAD')) return 'SIMBAD, which says what kind of object things are, did not answer just now.'
    return 'Gaia lists it, but no catalogue we asked says what kind of object it is.'
  }
  return null
}

/** The system SIMBAD counts it part of, when that is a star system (and not the one the page asked about). */
export function partOfSentence(r: IdentifyResult, name?: string): string | null {
  if (namedSystem(r, name)) return null
  const stellar = (r.simbad?.parents ?? []).find((p) => p.type && p.type.code.includes('*') && !GROUP_TYPES.has(p.type.code))
  return stellar ? `SIMBAD lists it as part of ${readableName(stellar.display_name)}.` : null
}

/** The light of the object in G (visible), for comparing with neighbours. */
function objectG(r: IdentifyResult): number | null {
  const g = r.gaia?.values.find((v) => v.key === 'phot_g_mean_mag')
  return g && typeof g.value === 'number' ? g.value : null
}

const ORDER = 'OBAFGKMLTY'
/** Of two spectral types, is the second cooler? From class letter, then subclass number. null when it cannot be told. */
function secondIsCooler(a: string, b: string): boolean | null {
  const parse = (s: string) => /^\s*([OBAFGKMLTY])(\d+(?:\.\d+)?)?/.exec(s)
  const pa = parse(a)
  const pb = parse(b)
  if (!pa || !pb) return null
  const ia = ORDER.indexOf(pa[1])
  const ib = ORDER.indexOf(pb[1])
  if (ia !== ib) return ib > ia
  if (pa[2] == null || pb[2] == null || pa[2] === pb[2]) return null
  return Number(pb[2]) > Number(pa[2])
}

function isPairOfBrownDwarfs(sp: SpectralWords): boolean {
  return sp.parts.length === 2 && sp.parts.every((p) => BROWN_DWARF_CLASSES.has(p.trim()[0]))
}

/** Do other catalogued sources share the blur? Short sentences, or none. */
export function blurSentences(r: IdentifyResult, level: UiLevel = 'beginner'): string[] {
  const out: string[] = []
  const sp = r.simbad?.spectral_type
  if (sp?.pair) {
    if (level === 'expert') out.push(`A pair: SIMBAD's spectral type, ${sp.text}, names two objects seen as one point.`)
    else if (isPairOfBrownDwarfs(sp)) out.push('It is really two brown dwarfs, so close together they look like one point.')
    else out.push('It is really two objects, so close together they look like one point.')
  }
  const same = r.neighbours.filter((n) => n.same_pixel)
  if (same.length === 0) return out
  const g0 = objectG(r)
  const real = same.filter((n) => !n.possibly_spurious)
  const spurious = same.filter((n) => n.possibly_spurious)
  const comparable = real.filter((n) => g0 == null || n.g_mag == null || n.g_mag - g0 <= 2.5)
  const faint = real.filter((n) => !comparable.includes(n))
  let said = false
  if (comparable.length) {
    const first = comparable[0]
    const who = first.simbad_name ? readableName(first.display_name) : 'another source'
    const brighter = g0 != null && first.g_mag != null ? (first.g_mag < g0 ? ', brighter,' : ', fainter,') : ''
    const stars = comparable.every((n) => n.simbad_type?.code.includes('*')) ? 'stars' : 'sources'
    const n = comparable.length + (found(r) ? 1 : 0)
    out.push(`This blur holds ${n} catalogued ${stars}, not one: ${who}${brighter} is ${num(first.from_object_arcsec, 1)} arcseconds away.`)
    said = true
  }
  if (faint.length) {
    const also = said ? ' also' : ''
    const ratio = g0 != null && faint[0].g_mag != null ? timesFainter(faint[0].g_mag - g0) : null
    out.push(
      faint.length === 1
        ? ratio
          ? `Gaia${also} lists one other source in the same SPHEREx pixel, about ${roundRatio(ratio)} times fainter in visible light.`
          : `Gaia${also} lists one other, fainter source in the same SPHEREx pixel.`
        : `Gaia${also} lists ${faint.length} other, much fainter sources in the same SPHEREx pixel.`,
    )
    said = true
  }
  if (spurious.length) {
    const also = said ? ' also' : ''
    const one = spurious.length === 1
    out.push(`Gaia${also} lists ${one ? 'a faint source' : `${spurious.length} faint sources`} in the same pixel.`)
    out.push(`${one ? 'It' : 'They'} may not be real: Gaia often lists false ones beside very bright stars.`)
  }
  return out
}

export interface Fact {
  text: string
  source: string
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

/** Is Gaia's fit for the object poor enough that its formal errors understate the truth? */
export function poorFit(r: IdentifyResult): boolean {
  const ruwe = gaiaRuwe(r)
  return r.derived.from === 'Gaia DR3' && ruwe != null && ruwe > RUWE_LIMIT
}

/** The distance in light-years as the card says it: two significant figures when Gaia's fit is poor. */
export function lightYearsWords(r: IdentifyResult, ly: number): string {
  return poorFit(r) ? sig2(ly) : sig3(ly)
}

function distanceFact(r: IdentifyResult): Fact | null {
  const d = r.derived.distance
  const source = r.derived.from === 'SIMBAD' ? 'SIMBAD' : 'Gaia'
  if (d && d.status === 'from_parallax' && d.ly != null) {
    const poor = poorFit(r)
    // With a poor fit the formal error understates the truth, so it is not given.
    const giveOrTake = !poor && d.ly_error != null && d.ly_error / d.ly > 0.03 ? `, give or take ${sig2(d.ly_error)}` : ''
    const said = lightYearsWords(r, d.ly)
    const years = d.ly < 10 ? num(Math.round(d.ly)) : said
    let text = `It is about ${said} light-years away${giveOrTake}. The light we see left it ${years} years ago.`
    if (poor) text += " Gaia's fit for it is poor (often a sign of a close pair), so this distance is less sure."
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

/** An ultracool dwarf: its visible light is so shaped by molecules and alkali metals that a blackbody colour would mislead. */
export function isUltracool(r: IdentifyResult): boolean {
  const t = r.portrait.temperature
  if (t?.key === 'teff_espucd') return true
  const s = r.simbad
  if (s?.type && (s.type.code === 'BD*' || s.type.code === 'BD?')) return true
  return BROWN_DWARF_CLASSES.has(s?.spectral_type?.class ?? '')
}

/**
 * How the object's colour is drawn: a blackbody at its temperature, dark (too cool to glow),
 * not drawn because a blackbody colour would mislead (an ultracool dwarf), or not at all
 * (no temperature).
 */
export type ColourDrawn = 'blackbody' | 'dark' | 'withheld' | 'none'

export function colourDrawn(r: IdentifyResult): ColourDrawn {
  const t = r.portrait.temperature
  if (!t || typeof t.value !== 'number') return 'none'
  if (!glowsVisibly(t.value)) return 'dark'
  return isUltracool(r) ? 'withheld' : 'blackbody'
}

/** The temperature the picture's layout is given: none when the colour is withheld. */
export function temperatureForPicture(r: IdentifyResult): number | null {
  const c = colourDrawn(r)
  const t = r.portrait.temperature
  return (c === 'blackbody' || c === 'dark') && t && typeof t.value === 'number' ? t.value : null
}

function temperatureWho(t: Quantity): string {
  if (t.catalogue === 'SIMBAD') return 'Published measurements in SIMBAD put'
  return t.flags?.lowest_quality ? "Gaia's rough estimate, from its colours and brightness, puts" : "Gaia's model, fitted to its colours and brightness, puts"
}

function temperatureFact(r: IdentifyResult): Fact | null {
  const t = r.portrait.temperature
  if (!t || typeof t.value !== 'number') return null
  const sources = [t.catalogue === 'SIMBAD' ? 'SIMBAD' : 'Gaia']
  const k = roundTemperature(t.value)
  const parts = [`${temperatureWho(t)} its surface at about ${k} kelvin (the Sun: ${num(SUN_TEFF_K)}).`]
  const listed = r.simbad?.temperatures
  if (t.catalogue !== 'SIMBAD' && listed && listed.n >= 10 && listed.median != null) {
    parts.push(`Published measurements in SIMBAD centre on about ${roundTemperature(listed.median)} kelvin.`)
    sources.push('SIMBAD')
  }
  const sp = r.simbad?.spectral_type
  if (sp?.pair) {
    parts.push('Gaia saw the two as one point, so this temperature is a blend, mostly from the brighter one.')
    // For two brown dwarfs the warmer is the brighter in Gaia's light, so "the other" is the cooler one.
    if (isPairOfBrownDwarfs(sp) && secondIsCooler(sp.parts[0], sp.parts[1]) != null) parts.push("By SIMBAD's classes, the other one is cooler.")
  }
  const c = colourDrawn(r)
  if (c === 'dark') parts.push(`That is ${TOO_COOL}.`)
  else if (c === 'withheld') parts.push('Its gases soak up much of its visible light, so its colour to our eyes is not known.')
  else parts.push(`A perfect glowing body this hot would look ${colourWord(t.value)}.`)
  return { text: parts.join(' '), source: sources.join(', ') }
}

function radiusValue(r: IdentifyResult, key: string): number | null {
  const q = r.gaia?.values.find((v) => v.key === key)
  return q && typeof q.value === 'number' ? q.value : null
}

/** Gaia's two radius models, when both exist and differ by more than a tenth. */
export function radiusSpread(r: IdentifyResult): [number, number] | null {
  const a = radiusValue(r, 'radius_flame')
  const b = radiusValue(r, 'radius_gspphot')
  if (a == null || b == null || Math.abs(a / b - 1) <= 0.1) return null
  return [Math.min(a, b), Math.max(a, b)]
}

function sizeFact(r: IdentifyResult): Fact | null {
  const rad = r.portrait.radius
  if (!rad || typeof rad.value !== 'number') return null
  const spread = radiusSpread(r)
  let text: string
  if (spread) {
    text = `Gaia's two models put its width at ${sig2(spread[0])} to ${sig2(spread[1])} times the Sun's. The picture uses ${sig2(rad.value)}.`
  } else {
    const words = widthWords(rad.value, 'the Sun')
    const exact = /times/.test(words) ? '' : ` (${num(rad.value, 2)} times)`
    text = `Gaia's model makes it ${words}${exact}.`
  }
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
  if (n === 0) return { text: 'No scientific paper in SIMBAD mentions it yet.', source: 'SIMBAD' }
  return { text: `SIMBAD lists ${num(n)} scientific ${n === 1 ? 'paper that mentions' : 'papers that mention'} it.`, source: 'SIMBAD' }
}

/** At most five short facts, each with where its number comes from. */
export function beginnerFacts(r: IdentifyResult): Fact[] {
  return [distanceFact(r), temperatureFact(r), sizeFact(r), motionFact(r), studiedFact(r)].filter((f): f is Fact => f != null).slice(0, 5)
}

/** For beginners: what Gaia and SIMBAD are, for the ones the card names. */
export function sourcesKey(r: IdentifyResult): string[] {
  const out: string[] = []
  if (r.gaia || r.derived.from === 'Gaia DR3' || r.neighbours.some((n) => n.catalogue === 'Gaia DR3')) {
    out.push('Gaia is a space telescope that measures where stars are, how they move and how bright they are.')
  }
  if (r.simbad || r.services.simbad.answered) out.push('SIMBAD is a library of what astronomers have published about objects in space.')
  return out
}

/** What is not known, in one or two lines: not in the catalogues, or not known right now because a service did not answer. */
export function notKnownLine(r: IdentifyResult): string {
  const gaiaDown = down(r, 'Gaia DR3')
  const anyDown = r.unreachable.length > 0
  const missing: string[] = []
  const notNow: string[] = []
  const put = (what: string, couldBeElsewhere: boolean) => (couldBeElsewhere ? notNow : missing).push(what)
  if (!r.portrait.temperature) put('its temperature', anyDown)
  if (!r.portrait.radius) put('its size', gaiaDown)
  const d = r.derived.distance
  if (!(d && d.status === 'from_parallax') && !r.derived.distance_estimate) put('its distance', anyDown)
  if (!r.derived.motion) put('its motion', anyDown)
  missing.push('its surface details')
  const lines = [`Not in the catalogues we asked: ${orList(missing)}.`]
  if (notNow.length) lines.push(`Not known right now, because ${r.unreachable.join(' and ')} did not answer: ${orList(notNow)}.`)
  const planets = r.simbad?.planets?.length ?? 0
  if (planets) {
    lines.push(`SIMBAD lists ${planets === 1 ? 'a planet' : `${planets} planets`} around it; ${planets === 1 ? 'its size is' : 'their sizes are'} not in the catalogues we asked.`)
  }
  return lines.join(' ')
}

/** Under the picture: what each drawn thing was computed from. Plain words for beginners, columns for experts. */
export function pictureNotes(r: IdentifyResult, level: UiLevel = 'beginner', layout?: Portrait): string[] {
  const out: string[] = []
  const expert = level === 'expert'
  const t = r.portrait.temperature
  const rad = r.portrait.radius
  const col = (q: Quantity) => `${q.catalogue} ${q.column.split('.').at(-1)}`
  const c = colourDrawn(r)
  const drawsDisc = layout ? layout.kind !== 'none' : temperatureForPicture(r) != null || rad != null
  if (t && typeof t.value === 'number') {
    const k = num(Math.round(t.value))
    if (c === 'blackbody') {
      out.push(
        expert
          ? `Colour: a blackbody at ${k} K (${col(t)}) as the eye sees it (CIE 1931). The star's real colour is changed by its atmosphere and is not measured.`
          : "Colour: that of a perfect glowing body at Gaia's temperature for it. Its real colour is changed by its gases and is not measured.",
      )
    } else if (c === 'dark') {
      out.push(expert ? `Dark disc: ${k} K (${col(t)}).` : 'Dark disc: its temperature is measured.')
      out.push(`${TOO_COOL[0].toUpperCase()}${TOO_COOL.slice(1)}.`)
    } else if (c === 'withheld') {
      out.push(
        expert
          ? `No colour drawn: at ${k} K (${col(t)}) an ultracool dwarf's visible light is shaped by molecular and alkali absorption, so a blackbody colour would mislead; its visible colour is not measured.`
          : 'No colour drawn: its gases soak up much of its light, so a perfect glowing body\'s colour would be wrong.',
      )
    }
  } else if (rad) {
    out.push(expert ? 'Outline only: no temperature, so no colour, is in the catalogues we asked.' : 'Outline only: its temperature, so its colour, is not measured.')
  }
  if (rad && typeof rad.value === 'number') {
    const planets = rad.value < SMALL_RADIUS_RSUN ? ', with Jupiter and the Earth as outlines' : ''
    out.push(
      expert
        ? `Size: ${num(rad.value, rad.value < 10 ? 3 : 1)} solar radii (${col(rad)}), beside the Sun to scale${planets}.`
        : `Size: from Gaia's model, to scale with the Sun${planets}.`,
    )
    for (const b of layout?.bodies ?? []) {
      if (b.dot) out.push(`${b.key === 'earth' ? 'The Earth' : b.label} is too small to draw to scale here, so it is shown as a dot.`)
    }
  } else if (t && drawsDisc) {
    out.push("Size not measured: the disc's size means nothing, and the Sun is not shown.")
  }
  if (c === 'blackbody') {
    out.push(expert ? 'Edge darkening: a standard approximation (linear law, u = 0.6), the same for every star.' : 'Edges drawn darker, as stars look; the amount is one standard value for all.')
  }
  if (drawsDisc) out.push('Brightness is not to scale. No spots, flares or other surface details are drawn: none are measured.')
  return out
}

/** The short label under the object's own disc. */
export function discLabel(r: IdentifyResult, name?: string): string {
  const t = cardTitle(r, name)
  return t.length <= 16 && t !== NO_NAME ? t : 'This object'
}

/** The picture in words, for a screen reader: what is drawn, in what colour, to what scale, and what is not drawn. */
export function pictureDescription(r: IdentifyResult, layout: Portrait): string {
  const parts = ['Illustration drawn from measurements, not a photograph.']
  const obj = layout.bodies.find((b) => b.key === 'object')
  const t = r.portrait.temperature
  if (obj) {
    const label = obj.label === 'This object' ? 'The object' : obj.label
    const colour =
      obj.fill === 'glow' && t && typeof t.value === 'number'
        ? `${article(colourWord(t.value) ?? 'a')} ${colourWord(t.value)} disc, the colour of a perfect glowing body at ${roundTemperature(t.value)} kelvin`
        : obj.fill === 'dark'
          ? 'a dark outlined disc: too cool to glow in visible light'
          : 'an outline only: its colour is not measured'
    const sun = layout.bodies.find((b) => b.key === 'sun')
    const size =
      obj.radiusRsun != null && sun
        ? `, ${sig2(obj.radiusRsun)} times the Sun's width, beside the Sun (${colourWord(SUN_TEFF_K)}) to scale${layout.bodies.some((b) => b.key === 'jupiter') ? ', with Jupiter and the Earth as outlines' : ''}`
        : ', size not measured'
    parts.push(`${label} as ${colour}${size}.`)
  }
  const notDrawn: string[] = []
  const planets = r.simbad?.planets?.length ?? 0
  if (planets) notDrawn.push(planets === 1 ? 'its planet' : `its ${planets} planets`)
  if (colourDrawn(r) === 'withheld') notDrawn.push('its colour')
  notDrawn.push('surface details')
  parts.push(`Not drawn: ${notDrawn.join(', ')}.`)
  return parts.join(' ')
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

export function distanceScaleCaption(r: IdentifyResult, d: { ly: number; estimate: boolean }, source: string): string {
  const what = d.estimate ? `How far, by Gaia's own estimate: ${sig3(d.ly)} light-years.` : `How far: ${lightYearsWords(r, d.ly)} light-years (${source}).`
  return `${what} The nearest star, Proxima Centauri, is ${NEAREST_STAR_LY} light-years away.`
}

// ------------------------------------------------------------------ nothing found

/** How far the lookup searched, in words a beginner can follow. */
export function searchedSentence(r: IdentifyResult): string {
  const radius = r.query.radius_arcsec
  const frac = radius / r.query.pixel_arcsec
  const pixel = Math.abs(frac - 2 / 3) < 0.05 ? 'two-thirds of a SPHEREx pixel' : `${num(frac, 1)} SPHEREx pixels`
  return `We looked within ${num(radius, radius % 1 ? 1 : 0)} arcseconds of the place: ${pixel}. An arcsecond is 1/3600 of a degree.`
}

/** A Gaia source's light in words: how faint, and its colour beside the Sun's. Only what G and BP-RP say. */
export function lightWords(g: number | null, bpRp: number | null): string | null {
  const bits: string[] = []
  // A star of G 7 or fainter is too faint for the eye (the eye's limit is about magnitude 6 on a dark night).
  if (g != null && g >= 7) bits.push('too faint to see without a telescope')
  if (bpRp != null) {
    if (bpRp < SUN_BP_RP - 0.3) bits.push('bluer than the Sun')
    else if (bpRp <= SUN_BP_RP + 0.3) bits.push('close to the Sun in colour')
    else if (bpRp < 2) bits.push('redder than the Sun')
    else bits.push('much redder than the Sun')
  }
  return bits.length ? `Gaia measures it as ${bits.join(' and ')}.` : null
}

/** The nothing-found lines after the fixed sentence (or in its place when a catalogue did not answer). */
export function nothingFoundLines(r: IdentifyResult): string[] {
  const out: string[] = []
  const radius = num(r.query.radius_arcsec, r.query.radius_arcsec % 1 ? 1 : 0)
  if (r.nothing_catalogued === true) {
    out.push(searchedSentence(r))
  } else if (r.unreachable.length === 2) {
    out.push(`It could not be checked whether anything is listed here, because ${r.unreachable.join(' and ')} did not answer.`)
  } else {
    const answered = r.services.gaia.answered ? 'Gaia' : 'SIMBAD'
    const missing = r.unreachable[0]
    out.push(`${answered} lists nothing within ${radius} arcseconds of the place. ${missing} did not answer, so whether it lists anything here is not known.`)
  }
  const n = r.nearest_catalogued
  if (n) {
    const pixel = n.same_pixel ? ', inside the same SPHEREx pixel' : ''
    out.push(`The nearest catalogued thing is ${readableName(n.display_name)}, ${num(n.separation_arcsec, 1)} arcseconds away${pixel}.`)
    const light = n.catalogue === 'Gaia DR3' ? lightWords(n.g_mag, n.bp_rp) : null
    if (light) out.push(light)
    if (n.possibly_spurious) out.push('It may not be a real source: Gaia often lists false ones beside very bright stars.')
  }
  return out
}

// ------------------------------------------------------------------ the expert table

export interface ExpertRow {
  quantity: string
  value: string
  uncertainty: string
  unit: string
  /** the catalogue and column the value is read from, or the formula it is derived by */
  source: string
  /** quality flags and notes, each a short line */
  notes: string[]
}

export interface ExpertGroup {
  title: string
  rows: ExpertRow[]
}

/** Shorter column names for the table: the gaiadr3 schema is said once, in the group title. */
function shortColumn(c: string): string {
  return c.replace(/^gaiadr3\./, '')
}

function fmtPlain(v: number | string, unit: string): string {
  if (typeof v === 'string') return v
  const a = Math.abs(v)
  if (unit === 'K' || unit === '%' || Number.isInteger(v)) return num(v, 0)
  if (a >= 1000) return num(v, 1)
  return v.toPrecision(4) // four significant figures, trailing zeros kept: RUWE 1.500
}

/** A quantity's value and uncertainty, rounded to each other. */
export function fmtQuantity(q: { value: number | string; error: number | null; lower: number | null; upper: number | null }, unit: string): { value: string; uncertainty: string } {
  if (typeof q.value === 'string') return { value: q.value, uncertainty: '' }
  if (q.error != null && q.error > 0) {
    const w = withError(q.value, q.error)
    return { value: w.value, uncertainty: `± ${w.error}` }
  }
  if (q.lower != null && q.upper != null && q.upper > q.lower) {
    const d = Math.min(errorDecimals((q.upper - q.lower) / 2), 10)
    return { value: num(q.value, d), uncertainty: `${num(q.lower, d)} to ${num(q.upper, d)}` }
  }
  return { value: fmtPlain(q.value, unit), uncertainty: '' }
}

/** Units as an astronomer writes them in a table. */
const UNIT_SYMBOL: Record<string, string> = { 'solar radii': 'R☉', 'solar luminosities': 'L☉' }

/**
 * One table row. The catalogue is named in the group's title, so the source line holds only
 * the column, its error column and its range columns (written short: "_lower/_upper"), and
 * the reference when SIMBAD gives one.
 */
function quantityRow(q: Quantity): ExpertRow {
  const f = fmtQuantity(q, q.unit)
  const notes: string[] = []
  if (q.flags) notes.push(`Quality flag ${q.flags.column.split('.').at(-1)} = ${q.flags.value}${q.flags.meaning ? `: ${q.flags.meaning}` : ''}`)
  if (q.note) notes.push(q.note)
  const own = q.column.split('.').at(-1) ?? ''
  const range = q.range_columns
    ? q.range_columns.every((c) => c.startsWith(`${own}_`))
      ? `range ${q.range_columns.map((c) => c.slice(own.length)).join('/')}`
      : `range: ${q.range_columns.join(', ')}`
    : null
  const source = [
    `${q.reference ? `(${q.reference}) ` : ''}${shortColumn(q.column)}`,
    q.error_column ? `error ${q.error_column}` : null,
    range,
  ]
    .filter(Boolean)
    .join('; ')
  return { quantity: q.label, value: f.value, uncertainty: f.uncertainty, unit: UNIT_SYMBOL[q.unit] ?? q.unit, source, notes }
}

/** Notes where Gaia's own estimates disagree with each other, or with SIMBAD's published values, or describe a blend. */
export function disagreements(r: IdentifyResult): string[] {
  const out: string[] = []
  const sp = r.simbad?.spectral_type
  if (sp?.pair && r.portrait.temperature && r.portrait.temperature.catalogue !== 'SIMBAD') {
    const cooler = sp.parts.length === 2 ? secondIsCooler(sp.parts[0], sp.parts[1]) : null
    const partner = cooler == null ? '' : ` The partner SIMBAD types ${cooler ? sp.parts[1] : sp.parts[0]} is the cooler one.`
    out.push(`Gaia measured the light of both together (${sp.text}), so its temperature is a blend dominated by the brighter one.${partner}`)
  }
  const v = (key: string) => {
    const q = r.gaia?.values.find((x) => x.key === key)
    return q && typeof q.value === 'number' ? q.value : null
  }
  const phot = v('teff_gspphot')
  const spec = v('teff_gspspec')
  if (phot != null && spec != null && Math.abs(spec / phot - 1) > 0.1) {
    out.push(
      `Gaia's temperature estimates disagree: GSP-Phot ${num(phot)} K, GSP-Spec ${num(spec)} K (GSP-Spec can be far off for cool dwarfs). The picture uses ${r.portrait.temperature?.key === 'teff_gspspec' ? 'GSP-Spec' : 'GSP-Phot'}.`,
    )
  }
  const spread = radiusSpread(r)
  if (spread) {
    out.push(
      `Gaia's radius estimates disagree by ${num((spread[1] / spread[0] - 1) * 100)}%: FLAME ${fmtPlain(v('radius_flame') ?? 0, '')}, GSP-Phot ${fmtPlain(v('radius_gspphot') ?? 0, '')} solar radii. The picture uses ${r.portrait.radius?.key === 'radius_flame' ? 'FLAME' : 'GSP-Phot'}.`,
    )
  }
  const t = r.portrait.temperature
  const listed = r.simbad?.temperatures
  if (t && typeof t.value === 'number' && t.catalogue !== 'SIMBAD' && listed && listed.n >= 10 && listed.median != null && Math.abs(listed.median / t.value - 1) > 0.03) {
    out.push(`SIMBAD's ${listed.n} published temperatures have a median of ${num(listed.median)} K, against Gaia's ${num(t.value)} K used for the picture.`)
  }
  return out
}

export function expertGroups(r: IdentifyResult): ExpertGroup[] {
  const groups: ExpertGroup[] = []
  const values = r.gaia?.values ?? r.simbad?.values ?? []
  const measured = values.filter((q) => !q.model).map(quantityRow)
  const poor = poorFit(r)
  if (poor) {
    measured.push({
      quantity: 'Caution: RUWE above 1.4',
      value: num(gaiaRuwe(r) ?? 0, 2),
      uncertainty: '',
      unit: '',
      source: 'gaia_source.ruwe',
      notes: ['The astrometry is disturbed, often by an unresolved companion: parallax, motion and what is derived from them are less sure than their errors say.'],
    })
  }
  if (measured.length) groups.push({ title: r.gaia ? 'Measured by Gaia DR3 (tables in the gaiadr3 schema)' : 'From SIMBAD (columns of its basic table)', rows: measured })
  const model = values.filter((q) => q.model).map(quantityRow)
  if (model.length) groups.push({ title: "Gaia DR3's model estimates, fitted to its light and parallax", rows: model })

  const d = r.derived
  const derived: ExpertRow[] = []
  if (d.distance) {
    if (d.distance.status === 'from_parallax' && d.distance.pc != null && d.distance.ly != null) {
      const pc = fmtQuantity({ value: d.distance.pc, error: d.distance.pc_error, lower: null, upper: null }, 'pc')
      const ly = fmtQuantity({ value: d.distance.ly, error: d.distance.ly_error, lower: null, upper: null }, 'ly')
      derived.push({
        quantity: 'Distance (1 / parallax)',
        value: pc.value,
        uncertainty: pc.uncertainty,
        unit: 'pc',
        source: `${d.distance.catalogue}: ${d.distance.formula}`,
        notes: [`= ${[ly.value, ly.uncertainty].filter(Boolean).join(' ')} light-years`],
      })
    } else {
      const why = d.distance.status === 'parallax_too_uncertain' ? `parallax only ${num(d.distance.parallax_over_error ?? 0, 1)} times its error (5 needed)` : d.distance.status.replace(/_/g, ' ')
      derived.push({ quantity: 'Distance (1 / parallax)', value: 'not given', uncertainty: why, unit: '', source: `${d.distance.catalogue}: ${d.distance.formula}`, notes: [] })
    }
  }
  if (d.distance_estimate) {
    const e = d.distance_estimate
    const f = fmtQuantity({ value: e.ly, error: null, lower: e.ly_lower, upper: e.ly_upper }, 'ly')
    derived.push({ quantity: "Distance, Gaia's estimate (GSP-Phot)", value: f.value, uncertainty: f.uncertainty, unit: 'light-years', source: `Gaia DR3: ${e.inputs.map(shortColumn).join(', ')}`, notes: [] })
  }
  if (d.motion) {
    const m = d.motion
    const mu = fmtQuantity({ value: m.mas_per_year, error: m.mas_per_year_error, lower: null, upper: null }, 'mas/yr')
    derived.push({
      quantity: 'Total proper motion',
      value: mu.value,
      uncertainty: mu.uncertainty,
      unit: 'mas/yr',
      source: `${m.catalogue}: ${m.formula}`,
      notes: [`= ${Number(m.pixels_per_year.toPrecision(3))} SPHEREx pixels (6.15 arcsec) a year, with the same relative error`],
    })
  }
  if (d.speed) {
    const v = fmtQuantity({ value: d.speed.km_s, error: d.speed.km_s_error, lower: null, upper: null }, 'km/s')
    derived.push({ quantity: 'Speed across the line of sight', value: v.value, uncertainty: v.uncertainty, unit: 'km/s', source: `${d.speed.catalogue}: ${d.speed.formula}`, notes: [] })
  }
  if (derived.length) groups.push({ title: 'Derived here from the values above', rows: derived })

  const s = r.simbad
  const simbad: ExpertRow[] = []
  if (s) {
    if (s.type) simbad.push({ quantity: 'Object type', value: s.type.code, uncertainty: '', unit: '', source: `basic.otype (${s.type.label})`, notes: [] })
    if (s.spectral_type) {
      simbad.push({ quantity: 'Spectral type', value: s.spectral_type.text, uncertainty: '', unit: '', source: `${s.spectral_type_reference ? `(${s.spectral_type_reference}) ` : ''}basic.sp_type`, notes: [] })
    }
    if (s.references != null) simbad.push({ quantity: 'References', value: num(s.references), uncertainty: '', unit: 'papers', source: 'basic.nbref', notes: [] })
    for (const p of s.parents ?? []) {
      if (p.references != null) simbad.push({ quantity: `Part of ${p.display_name}`, value: num(p.references), uncertainty: '', unit: 'papers', source: `h_link, basic.nbref (${p.type?.label ?? 'type not given'})`, notes: [] })
    }
    const t = s.temperatures
    if (t && t.n && t.median != null) {
      simbad.push({ quantity: `Temperatures listed (${t.n} values)`, value: `median ${num(t.median)}`, uncertainty: `${num(t.min ?? 0)} to ${num(t.max ?? 0)}`, unit: 'K', source: t.column, notes: [] })
    }
  }
  if (simbad.length) groups.push({ title: 'SIMBAD', rows: simbad })
  return groups
}

/** Which service gave the numbers, for the expert view. */
export function servicesLine(r: IdentifyResult): string {
  return [r.services.gaia, r.services.simbad]
    .map((s) => (s.answered ? `${s.name}: ${s.via}` : `${s.name}: did not answer`))
    .join('. ')
}

/** Where the lookup searched, for experts. */
export function searchLine(r: IdentifyResult): string {
  const q = r.query
  const sign = q.dec >= 0 ? '+' : ''
  return `Searched within ${num(q.radius_arcsec, q.radius_arcsec % 1 ? 2 : 0)} arcsec of RA ${q.ra.toFixed(6)}, Dec ${sign}${q.dec.toFixed(6)} at ${q.epoch.toFixed(3)}; neighbours within ${num(q.neighbour_radius_arcsec)} arcsec.`
}

/** "Gaia DR3 did not answer" sentences for the card. */
export function unreachableSentence(r: IdentifyResult): string | null {
  if (!r.unreachable.length) return null
  const names = r.unreachable.join(' and ')
  const have = r.unreachable.length === 2 ? 'nothing could be looked up' : `this card shows only what ${r.unreachable.includes('SIMBAD') ? 'Gaia' : 'SIMBAD'} has`
  return `${names} did not answer just now, so ${have}.`
}

/** For "Look at this one": the object's place at 2026.0 (the date /api/resolve uses), with its motion when known. */
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
  // At 2026.0 whatever date the card was asked for, so the page can centre on it as on a resolved name.
  const where = r.gaia?.resolve_position ?? r.simbad?.resolve_position ?? { ra: r.query.ra, dec: r.query.dec }
  return {
    ra: where.ra,
    dec: where.dec,
    pmra: value('pmra'),
    pmdec: value('pmdec'),
    parallax: value('parallax') ?? value('plx_value'),
    name: found(r) ? (namedSystem(r, name) ? cardTitle(r, name) : name ?? (r.simbad ? readableName(r.simbad.display_name) : null) ?? r.gaia?.name ?? null) : (name ?? null),
  }
}

// ---- for the page that mounts the card ----------------------------------------------------

/** The one line in the "What is it?" panel that says the picture can be pressed (both levels). */
export const PRESS_TO_ASK = 'Press any star in the picture to ask about it.'
