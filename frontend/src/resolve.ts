// The backend's name lookup: GET /api/resolve?name=  (see backend/astrometry.py, resolve_name).
// It asks SIMBAD which object a name means, takes position and motion from Gaia DR3 when
// SIMBAD lists a Gaia identifier (from SIMBAD itself otherwise), and moves the position
// to the year 2026. The first lookup of a name takes a few seconds; repeats are cached.

export interface ResolvedName {
  /** The catalogue's main name in SIMBAD's spelling: "NAME Barnard's star", "V* RW Aur". See plainName(). */
  name: string
  /** Degrees, ICRS, already moved from the catalogue date to 2026. */
  ra: number
  dec: number
  /** Milliarcseconds per year, eastward (cos dec included) and northward. Null when not known. */
  pmra: number | null
  pmdec: number | null
  /** Milliarcseconds. Null when not known. */
  parallax: number | null
  /** Where position and motion came from: "Gaia DR3" or "SIMBAD". Empty if the server did not say. */
  source: string
  /** How far the position above is from the object's place in the year 2000. Null if the server did not say. */
  moved_since_2000_arcsec: number | null
  /** Remarks from the server, such as "No proper motion known". */
  notes: string[]
}

export type ResolveFailure =
  /** 404: the name service knows no single object of that name. */
  | 'not_found'
  /** 502, 503, 504 or no answer in time: the name service is not answering. Coordinates still work. */
  | 'service_down'
  /** The request never reached our own server: it is stopped, or the visitor is offline. */
  | 'unreachable'
  /** 400 or 422: the server would not take the name as written. */
  | 'rejected'
  /** Anything else, including an answer that is not what /api/resolve sends. */
  | 'failed'

/** Why a lookup failed. `message` is a plain sentence that can be shown to a visitor as it is. */
export class ResolveError extends Error {
  readonly kind: ResolveFailure
  /** HTTP status, when the server answered. */
  readonly status: number | null
  /** The server's own explanation, when it gave one that is not already the message. */
  readonly detail: string | null

  constructor(kind: ResolveFailure, message: string, status: number | null = null, detail: string | null = null) {
    super(message)
    this.name = 'ResolveError'
    this.kind = kind
    this.status = status
    this.detail = detail
  }
}

/** How long to wait for an answer. The backend retries SIMBAD itself, so a slow answer is normal. */
export const RESOLVE_TIMEOUT_MS = 60_000

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const finite = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/**
 * The explanation in a FastAPI error body, as one line of text, or null.
 * HTTPException sends {"detail": "some words"}. A request that fails validation (422)
 * sends {"detail": [{"loc": ["query", "name"], "msg": "String should have ..."}, ...]}.
 */
export function errorDetail(body: unknown): string | null {
  if (!isRecord(body)) return null
  const detail = body.detail
  if (typeof detail === 'string') return detail.trim() || null
  if (!Array.isArray(detail)) return null
  const lines = detail.flatMap((item: unknown) => {
    if (!isRecord(item) || typeof item.msg !== 'string') return []
    // loc is ["query", "name"]: the last entry is the parameter at fault.
    const where = Array.isArray(item.loc) ? item.loc.at(-1) : undefined
    return [typeof where === 'string' || typeof where === 'number' ? `${where}: ${item.msg}` : item.msg]
  })
  return lines.length > 0 ? lines.join('; ') : null
}

/** A response body as JSON, or null if it is anything else (an HTML error page from a proxy, say). */
function jsonOrNull(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

/** Check a 200 answer field by field: the page goes on to fetch whatever patch of sky it names. */
function readAnswer(body: unknown, asked: string): ResolvedName | null {
  if (!isRecord(body)) return null
  const ra = finite(body.ra)
  const dec = finite(body.dec)
  if (ra === null || dec === null || ra < 0 || ra >= 360 || dec < -90 || dec > 90) return null
  return {
    name: typeof body.name === 'string' && body.name.trim() ? body.name : asked,
    ra,
    dec,
    pmra: finite(body.pmra),
    pmdec: finite(body.pmdec),
    parallax: finite(body.parallax),
    source: typeof body.source === 'string' ? body.source : '',
    moved_since_2000_arcsec: finite(body.moved_since_2000_arcsec),
    notes: Array.isArray(body.notes) ? body.notes.filter((n): n is string => typeof n === 'string') : [],
  }
}

/**
 * Look a name up. Resolves with where the object is, or rejects with a ResolveError.
 * If `signal` is aborted by the caller, rejects with the browser's own abort error
 * instead, so a search that was replaced by a newer one can be told apart and ignored.
 */
export async function resolveName(
  name: string,
  signal?: AbortSignal,
  timeoutMs: number = RESOLVE_TIMEOUT_MS,
): Promise<ResolvedName> {
  // One controller for both ways of giving up: the caller's signal and the timeout.
  const ctrl = new AbortController()
  const giveUp = () => ctrl.abort()
  if (signal?.aborted) ctrl.abort()
  signal?.addEventListener('abort', giveUp)
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    ctrl.abort()
  }, timeoutMs)

  let r: Response
  let text: string
  try {
    r = await fetch(`/api/resolve?${new URLSearchParams({ name })}`, {
      signal: ctrl.signal,
      headers: { Accept: 'application/json' },
    })
    text = await r.text() // inside the try: the body can be cut short too
  } catch (e) {
    if (signal?.aborted) throw e
    if (timedOut) throw new ResolveError('service_down', 'The name lookup is taking too long.')
    // fetch rejects without a status when nothing answered at all.
    throw new ResolveError('unreachable', 'Could not reach the server, so the name was not looked up.')
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', giveUp)
  }
  const body = jsonOrNull(text)

  if (r.ok) {
    const answer = readAnswer(body, name)
    if (answer) return answer
    throw new ResolveError('failed', 'The name lookup sent back an answer that could not be read.', r.status)
  }
  const detail = errorDetail(body)
  if (r.status === 404) {
    throw new ResolveError('not_found', detail ?? `No object called "${name}" was found.`, 404)
  }
  if (r.status === 502 || r.status === 503 || r.status === 504) {
    throw new ResolveError('service_down', 'The name lookup service is not answering right now.', r.status, detail)
  }
  if (r.status === 400 || r.status === 422) {
    throw new ResolveError('rejected', `The server did not accept that name${detail ? ` (${detail})` : ''}.`, r.status)
  }
  throw new ResolveError('failed', `The name lookup failed (HTTP ${r.status}).`, r.status, detail)
}

// Look-alike characters are given by number here, because several cannot be told from
// their plain twins on screen.
const chars = (...points: number[]) => String.fromCodePoint(...points)
// Curly and slanted marks typed or pasted for an apostrophe: ‘ ’ ‛ ʼ ′ ´ `
const APOSTROPHE_LIKE = new RegExp(`[${chars(0x2018, 0x2019, 0x201b, 0x02bc, 0x2032, 0x00b4, 0x0060)}]`, 'g')
// Every kind of hyphen and dash, and the true minus sign.
const DASH_LIKE = new RegExp(`[\\p{Pd}${chars(0x2212)}]`, 'gu')
// Straight or curly double quotes put around a name.
const WRAPPING_QUOTES = new RegExp(`^["${chars(0x201c, 0x201d)}]+|["${chars(0x201c, 0x201d)}]+$`, 'g')

const GREEK: Record<string, string> = {
  α: 'alpha', β: 'beta', γ: 'gamma', δ: 'delta', ε: 'epsilon', ζ: 'zeta', η: 'eta', θ: 'theta',
  ι: 'iota', κ: 'kappa', λ: 'lambda', μ: 'mu', ν: 'nu', ξ: 'xi', ο: 'omicron', π: 'pi',
  ρ: 'rho', σ: 'sigma', ς: 'sigma', τ: 'tau', υ: 'upsilon', φ: 'phi', χ: 'chi', ψ: 'psi', ω: 'omega',
}

/**
 * A typed or pasted name in the plain characters the name service knows names by.
 * Phones turn ' into a curly apostrophe; web pages write "WISE 0855−0714" with a true
 * minus sign, "ε Indi B" with a Greek letter and "Bételgeuse" with an accent. SIMBAD
 * lists none of those spellings, and the backend answers 502 for any character outside
 * plain ASCII, so they are put into plain form before the lookup.
 */
export function nameForLookup(typed: string): string {
  return typed
    .replace(APOSTROPHE_LIKE, "'") // before the accents go, or ´ would vanish with them
    .replace(DASH_LIKE, '-')
    .normalize('NFKD') // é becomes e plus an accent; full-width letters become plain
    .replace(/\p{M}/gu, '') // drop the accents
    .replace(/[α-ωΑ-Ω]/g, (letter, at: number, whole: string) => {
      // "εIndi" needs a space after the word; "π3 Ori" must stay "pi3 Ori".
      const before = at > 0 && /[\p{L}\p{N}]/u.test(whole[at - 1]) ? ' ' : ''
      const after = /\p{L}/u.test(whole[at + 1] ?? '') ? ' ' : ''
      return `${before}${GREEK[letter.toLowerCase()] ?? letter}${after}`
    })
    .replace(/\s+/g, ' ')
    .trim()
    .replace(WRAPPING_QUOTES, '')
    .trim()
}

/** Whether a name, once in plain form, still has a character the name service cannot take. */
export function hasUnusableCharacters(name: string): boolean {
  return /[^ -~]/.test(name) // anything outside printable ASCII
}

/**
 * SIMBAD's main name without its catalogue prefix, for showing to people:
 * "NAME Barnard's star" -> "Barnard's star", "V* RW Aur" -> "RW Aur", "* eps Ind B" -> "eps Ind B".
 * Names with no such prefix ("WISEA J085510.74-071442.5", "M  31") only lose doubled spaces.
 */
export function plainName(simbadName: string): string {
  return simbadName
    .replace(/^(?:NAME|V\*|\*\*|\*)\s+/, '')
    .replace(/\s+/g, ' ')
    .trim()
}
