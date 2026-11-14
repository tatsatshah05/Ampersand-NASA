// What the page is showing (which patch of sky, and how), and the page address that
// holds it. Everything a view depends on is in the address, so that a reload or a
// shared link brings the same view back:
//     ?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal
// plus, when they apply: pmra, pmdec, parallax (the object's known motion, as
// /api/resolve returns it), reference (difference mode), track (sum mode) and name.
import type { FramesQuery, Mode, Reference, Track } from './api'
import type { SearchTarget } from './components/SearchBar'

/** The six SPHEREx detectors and the wavelengths each one sees, in micrometres. */
export const DETECTORS = [
  { number: 1, from: 0.75, to: 1.12 },
  { number: 2, from: 1.1, to: 1.65 },
  { number: 3, from: 1.63, to: 2.43 },
  { number: 4, from: 2.4, to: 3.85 },
  { number: 5, from: 3.81, to: 4.43 },
  { number: 6, from: 4.41, to: 5.01 },
] as const

/** Fields of view on offer, in degrees. The API takes more than FOV_ABOVE and at most FOV_MAX. */
export const FOV_PRESETS = [0.05, 0.1, 0.2, 0.5]
export const FOV_ABOVE = 0.02
export const FOV_MAX = 0.5

const MODES: readonly Mode[] = ['normal', 'difference', 'sum']
const REFERENCES: readonly Reference[] = ['first', 'mean']
const TRACKS: readonly Track[] = ['sky', 'target']

export interface Selection {
  ra: number // degrees, 0 up to 360
  dec: number // degrees, -90 to 90
  /** What the visitor called this place, when they looked it up by name. Display only. */
  name: string | null
  /** The object's own motion (mas per year, pmra including cos dec) and parallax (mas), when known. */
  pmra: number | null
  pmdec: number | null
  parallax: number | null
  fov: number
  det: number
  mode: Mode
  reference: Reference
  track: Track
}

// Barnard's Star where it is in 2026 (see CLAUDE.md), shown when the address gives no position.
export const DEFAULT_SELECTION: Selection = {
  ra: 269.446267,
  dec: 4.768222,
  name: "Barnard's Star",
  pmra: null,
  pmdec: null,
  parallax: null,
  fov: 0.1,
  det: 5,
  mode: 'normal',
  reference: 'first',
  track: 'sky',
}

const NUMBER = /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i

/** A plain decimal number from the address, or null if the text is missing or is not one. */
function numberFrom(raw: string | null): number | null {
  if (raw === null) return null
  const text = raw.trim()
  if (!NUMBER.test(text)) return null
  const value = Number(text)
  return Number.isFinite(value) ? value : null
}

/** Address text quoted back to the visitor: short, and on one line. */
const quote = (raw: string) => `"${raw.replace(/\s+/g, ' ').trim().slice(0, 24)}"`

const validRa = (v: number | null): v is number => v !== null && v >= 0 && v < 360
const validDec = (v: number | null): v is number => v !== null && v >= -90 && v <= 90
const validFov = (v: number | null): v is number => v !== null && v > FOV_ABOVE && v <= FOV_MAX
const validDetector = (v: number | null): v is number => v !== null && Number.isInteger(v) && v >= 1 && v <= 6
const validMotion = (v: number | null): v is number => v !== null && Math.abs(v) <= 1e5
const validParallax = (v: number | null): v is number => v !== null && Math.abs(v) <= 1e4

function cleanName(raw: string | null | undefined): string | null {
  if (!raw) return null
  // Control characters out, runs of spaces to one, and no longer than a name needs to be.
  const text = Array.from(raw, (ch) => (ch < ' ' || ch === '\u007f' ? ' ' : ch))
    .join('')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80)
  return text || null
}

function oneOf<T extends string>(raw: string | null, allowed: readonly T[]): T | null {
  return allowed.find((v) => v === raw) ?? null
}

/**
 * The selection an address asks for. A missing or unusable value falls back to its
 * default, and `notes` says so in plain words for each one that was given but could
 * not be used. Right ascension and declination are one position: if only one of them
 * is usable it is not paired with the default of the other.
 */
export function readAddress(search: string): { selection: Selection; notes: string[] } {
  const p = new URLSearchParams(search)
  const notes: string[] = []
  const s: Selection = { ...DEFAULT_SELECTION }

  // Position: both or neither.
  const raRaw = p.get('ra')
  const decRaw = p.get('dec')
  const ra = numberFrom(raRaw)
  const dec = numberFrom(decRaw)
  const positionGiven = validRa(ra) && validDec(dec)
  if (positionGiven) {
    s.ra = ra
    s.dec = dec
    s.name = cleanName(p.get('name'))
  } else if (raRaw !== null || decRaw !== null) {
    const problems: string[] = []
    if (raRaw === null) problems.push('no right ascension (ra)')
    else if (!validRa(ra)) problems.push(`a right ascension (ra=${quote(raRaw)}) that is not a number from 0 up to 360`)
    if (decRaw === null) problems.push('no declination (dec)')
    else if (!validDec(dec)) problems.push(`a declination (dec=${quote(decRaw)}) that is not a number from -90 to 90`)
    const usable = validRa(ra) && raRaw !== null ? `ra=${quote(raRaw)}` : validDec(dec) && decRaw !== null ? `dec=${quote(decRaw)}` : null
    notes.push(
      `The address of this page has ${problems.join(' and ')}. A position needs both, so ` +
        `${usable ? `${usable} is not used on its own and ` : ''}the example, Barnard's Star, is shown instead.`,
    )
  }

  // The object's motion belongs to the position, so it is read only when that was usable.
  if (positionGiven) {
    const pmraRaw = p.get('pmra')
    const pmdecRaw = p.get('pmdec')
    const pmra = numberFrom(pmraRaw)
    const pmdec = numberFrom(pmdecRaw)
    if (validMotion(pmra) && validMotion(pmdec)) {
      s.pmra = pmra
      s.pmdec = pmdec
      const parallaxRaw = p.get('parallax')
      const parallax = numberFrom(parallaxRaw)
      if (validParallax(parallax)) s.parallax = parallax
      else if (parallaxRaw !== null) notes.push(`The parallax in the address (parallax=${quote(parallaxRaw)}) is not a usable number, so it is left out.`)
    } else if (pmraRaw !== null || pmdecRaw !== null) {
      notes.push(
        "The address gives the object's motion incompletely (pmra and pmdec must both be numbers), so the motion is not used. " +
          'A fast-moving object may then be marked in the wrong place.',
      )
    }
  }

  const fovRaw = p.get('fov')
  const fov = numberFrom(fovRaw)
  if (validFov(fov)) s.fov = fov
  else if (fovRaw !== null) {
    notes.push(
      `The address asks for a field of view of ${quote(fovRaw)}, but it has to be a number above ${FOV_ABOVE} and at most ${FOV_MAX} degrees, ` +
        `so ${DEFAULT_SELECTION.fov} is used.`,
    )
  }

  // `det` is the name the address uses; older links say `detector`.
  const detRaws = [p.get('det'), p.get('detector')].filter((raw): raw is string => raw !== null)
  const det = detRaws.map(numberFrom).find(validDetector)
  if (det !== undefined) s.det = det
  else if (detRaws.length) {
    notes.push(`The address asks for detector ${quote(detRaws[0])}, but SPHEREx has detectors 1 to 6, so detector ${DEFAULT_SELECTION.det} is used.`)
  }

  const modeRaw = p.get('mode')
  const mode = oneOf(modeRaw, MODES)
  if (mode) s.mode = mode
  else if (modeRaw !== null) notes.push(`The address asks for a mode called ${quote(modeRaw)}. The modes are normal, difference and sum, so normal is used.`)

  const referenceRaw = p.get('reference')
  const reference = oneOf(referenceRaw, REFERENCES)
  if (reference) s.reference = reference
  else if (referenceRaw !== null && s.mode === 'difference') {
    notes.push(`The address asks to compare with ${quote(referenceRaw)}. The choices are first and mean, so the first visit is used.`)
  }

  const trackRaw = p.get('track')
  const track = oneOf(trackRaw, TRACKS)
  if (track) s.track = track
  else if (trackRaw !== null && s.mode === 'sum') {
    notes.push(`The address asks to line the exposures up on ${quote(trackRaw)}. The choices are sky and target, so the sky is used.`)
  }

  return { selection: s, notes }
}

// The parameters this module owns. Anything else in the address is left as it is.
const OWN_KEYS = ['ra', 'dec', 'fov', 'det', 'detector', 'mode', 'pmra', 'pmdec', 'parallax', 'reference', 'track', 'name']

/** The query string ("?ra=...") for a selection, keeping other parameters of `current`. */
export function addressOf(s: Selection, current = ''): string {
  const others = new URLSearchParams(current)
  for (const key of OWN_KEYS) others.delete(key)
  const p = new URLSearchParams({
    ra: String(s.ra),
    dec: String(s.dec),
    fov: String(s.fov),
    det: String(s.det),
    mode: s.mode,
  })
  if (s.pmra !== null && s.pmdec !== null) {
    p.set('pmra', String(s.pmra))
    p.set('pmdec', String(s.pmdec))
    if (s.parallax !== null) p.set('parallax', String(s.parallax))
  }
  if (s.mode === 'difference') p.set('reference', s.reference)
  if (s.mode === 'sum') p.set('track', s.track)
  if (s.name) p.set('name', s.name)
  for (const [key, value] of others) p.append(key, value)
  return `?${p}`
}

/** Put a selection in the browser's address bar, as a new history entry or in place. */
export function writeAddress(s: Selection, how: 'push' | 'replace') {
  const next = addressOf(s, window.location.search)
  if (next === window.location.search) return
  try {
    if (how === 'push') window.history.pushState(null, '', next)
    else window.history.replaceState(null, '', next)
  } catch {
    // Some places (a page opened as a local file) do not allow it; the view still works.
  }
}

/** The request to /api/frames that shows a selection. */
export function toFramesQuery(s: Selection): FramesQuery {
  const q: FramesQuery = { ra: s.ra, dec: s.dec, fov: s.fov, detector: s.det, mode: s.mode }
  if (s.mode === 'difference') q.reference = s.reference
  if (s.mode === 'sum') q.track = s.track
  if (s.pmra !== null && s.pmdec !== null) {
    q.pmra = s.pmra
    q.pmdec = s.pmdec
    if (s.parallax !== null) q.parallax = s.parallax
  }
  return q
}

/**
 * The selection after choosing a new target: its position, name and motion replace the
 * old ones (a target that comes without a motion has none: nothing is carried over);
 * the field of view and mode stay. The detector is the one the target suggests (WISE
 * 0855 only shows in detector 6), otherwise `usualDetector`, the one the visitor last
 * chose for themselves. Returns null when the position cannot be used.
 */
export function withTarget(s: Selection, target: SearchTarget, usualDetector = s.det): Selection | null {
  if (!Number.isFinite(target.ra) || !validDec(target.dec)) return null
  // A right ascension outside 0 to 360 is brought round into it; one inside is kept
  // digit for digit, because the backend's cache is keyed on the number it is sent.
  const ra = validRa(target.ra) ? target.ra : Number((((target.ra % 360) + 360) % 360).toFixed(9)) % 360
  const moving = validMotion(target.pmra ?? null) && validMotion(target.pmdec ?? null)
  return {
    ...s,
    ra,
    dec: target.dec,
    name: cleanName(target.name),
    pmra: moving ? (target.pmra ?? null) : null,
    pmdec: moving ? (target.pmdec ?? null) : null,
    parallax: moving && validParallax(target.parallax ?? null) ? (target.parallax ?? null) : null,
    det: validDetector(target.det ?? null) ? (target.det ?? usualDetector) : usualDetector,
    // Following the target only makes sense for the target it was chosen for.
    track: moving ? s.track : 'sky',
  }
}
