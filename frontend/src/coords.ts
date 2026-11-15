// Reading sky coordinates the way people type them (issue #6).
//
//   parseCoords('17h57m48.5s +04d41m36s')  ->  { ok: true, ra: 269.452083, dec: 4.693333 }
//   parseCoords('17 57 60 +04 41 36')      ->  { ok: false, reason: 'RA seconds must be less than 60.' }
//
// Positions come back in decimal degrees, RA first. Nothing is corrected or moved to
// another date: the answer is the position as typed.
//
// Accepted, RA first and then Dec:
//   decimal degrees   269.4463 4.7682    269.4463, +4.7682    269.4463d +4.7682d    269.4463° +4.7682°
//   sexagesimal       17h57m48.5s +04d41m36s    17:57:48.5 +04:41:36    17 57 48.5 +04 41 36
//                     17h 57m 48.5s, +04° 41′ 36″   (minutes and seconds can be left off)
//   a designation     085510.83-071442.5 or J085510.83-071442.5   (hhmmss.ss then ddmmss.s)
//   with labels       RA 08h55m10.831s, Dec -07d14m42.53s    ra=269.4463&dec=4.7682
//   with a frame      17 57 48.5 +04 41 36 (J2000)           (J2000, ICRS and FK5 are ignored)
//   as copied         RA 17h 57m 48s | Dec +4° 41′ 36″       (a web search result)
//                     Right ascension 17h 57m 48.5s[1] Declination +04° 41′ 36″[1]   (Wikipedia)
//
// How RA is read:
//   hours    if it carries an h, or is two or three numbers (17 57 48.5, 17:57:48.5);
//   degrees  if it carries a d or °, or is a single number (269.4463).
// Dec is always degrees. The sign is read from the text, so "-00 30 00" is south.
//
// Rejected rather than guessed: RA outside 0 to 360 degrees (0h to 24h, 24h itself
// included), Dec outside -90 to +90, minutes or seconds of 60 or more, an RA with a
// sign (probably a Dec typed first), a sign or a unit that does not touch its number,
// and five numbers with nothing to show where RA ends.

export type CoordsResult = { ok: true; ra: number; dec: number } | { ok: false; reason: string }

/**
 * Inputs shown to people as examples of what works. The tests check each one is accepted, and
 * that both are the same place: where Barnard's Star is in 2026, so that typing either one
 * shows the star in the middle of the picture. (Its catalogue position for the year 2000,
 * 17h57m48.5s +04d41m36s, is 4.5 arcminutes away: outside the picture the page opens with.)
 */
export const COORD_EXAMPLES = ['269.4463 4.7682', '17h57m47.1s +04d46m06s'] as const

/**
 * How to type a position, in the words shown beside every box that takes one. The only kind
 * read is equatorial: right ascension and declination as catalogues list them (J2000, ICRS).
 */
export const COORD_HOW = {
  /** The order, to follow "a position:" or "Coordinates are". */
  order: 'right ascension (RA) first, then declination (Dec)',
  degrees: 'Both in degrees',
  hours: 'RA in hours, Dec in degrees',
  note: 'Colons or spaces work in place of the letters. Use J2000 coordinates, the kind catalogues list. Other kinds, such as galactic, are not read.',
} as const

const WHY = {
  notCoordinates: 'This does not look like coordinates.',
  one: 'That gives only one value. A position needs two: RA first, then Dec.',
  tooMany: 'There are too many numbers here. RA and Dec take at most three each.',
  split: 'Could not tell where RA ends and Dec begins. Put a comma between them.',
  order: 'Write RA first, then Dec.',
  sign: 'Put a plus or minus sign right in front of its number, with no space.',
  unreadable: 'Could not read this as coordinates.',
  units: 'Could not read the units. Write RA like 17h57m48.5s and Dec like +04d41m36s.',
  decimal: 'Only the last number of RA, and the last number of Dec, can have a decimal point.',
  raSign: 'RA has no plus or minus sign: it runs from 0 up to 360 degrees (0h up to 24h). Write RA first, then Dec.',
  raHours: 'RA in hours must be less than 24. If you meant degrees, put a d after the first number, like 269d26m47s.',
  raDegrees: 'RA must be less than 360 degrees.',
  decHours: 'Dec is measured in degrees, not hours. Write it like +04d41m36s.',
  decRange: 'Dec must be between -90 and +90 degrees.',
} as const

type Unit = 'h' | 'd' | 'm' | 's'
type Sign = '+' | '-'

/** One number as typed, with what is attached to it. */
interface Field {
  sign: Sign | null
  /** The digits as typed ("07", "42.53"), kept as text so "-00" keeps its sign and "085510" its length. */
  text: string
  /** The mark written straight after the number: h, d or °, m or ′, s or ″. */
  unit: Unit | null
  /** A colon joins it to the number before. */
  tied: boolean
}

interface Reading {
  fields: Field[]
  /** Field indexes at which Dec must start: after a comma or a "Dec" label. */
  breaks: number[]
  /** Set when the text is made of coordinate characters but is put together wrongly. */
  problem: string | null
}

const UNITS = new Map<string, Unit>([
  ['h', 'h'],
  ['d', 'd'],
  ['°', 'd'],
  ['m', 'm'],
  ["'", 'm'],
  ['s', 's'],
  ['"', 's'],
])

/**
 * The input in lower case with look-alike characters made plain, decoration removed and
 * labels reduced to single marks, so that read() only has to know a few characters.
 */
function prepare(input: string): string {
  let s = input
    .replace(/[\u200b-\u200d\u2060\ufeff]/g, '') // zero-width characters that ride along in copied text
    .replace(/[\u00ba\u02da]/g, '°') // º and ˚ typed for the degree sign
    .replace(/[\u2010-\u2015\u2212]/g, '-') // hyphens, dashes and the true minus sign
    .replace(/[\u2033\u201c\u201d\u02ba]/g, '"') // ″ and curly double quotes
    .replace(/[\u2032\u2018\u2019\u02b9\u00b4`]/g, "'") // ′, curly single quotes and accents typed for ′
    .normalize('NFKC') // full-width digits, superscript ʰ ᵐ ˢ, no-break and thin spaces
    .toLowerCase()
    .replace(/''/g, '"') // two primes for arcseconds
    .replace(/\[(?:\d{1,3}|[a-z]|note \d+)\]/g, ' ') // footnote marks copied from Wikipedia: 48.49847s[1]
    .replace(/[()[\]{}]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  s = s.replace(/^(["'])(.*)\1$/, '$2') // the whole thing wrapped in quotes
  // "(J2000)" or "ICRS" after a position says which reference frame it is in. Those two
  // and FK5 agree to well under an arcsecond, so the word is dropped. B1950 does not
  // agree (it can be more than half a degree off) and is left in, which makes the
  // text a name that nothing will be found for.
  s = s.replace(/(^|[^a-z0-9.])(?:j2000(?:\.0)?|icrs|fk5)(?![a-z0-9.])/g, '$1 ').trim()
  s = s.replace(/[\s.,;]+$/, '') // "269.4463, 4.7682."
  s = s.replace(/^j(?=\d{6}(?:\.\d*)?[+-]\d{6})/, '') // J085510.83-071442.5
  s = s.replace(/(\d) ?(?:degrees|degree|degs|deg)(?![a-z])\.?/g, '$1°')
  // Labels become single marks: α in front of RA, δ in front of Dec.
  s = s.replace(/(^|[^a-z])(?:right ascension|r\. ?a\.|ra|α)(?![a-z]) ?[:=]?/g, '$1 α ')
  s = s.replace(/(^|[^a-z])(?:declination|decl|dec|δ)(?![a-z])\.? ?[:=]?/g, '$1 δ ')
  // "269,4463 4,7682": decimal commas, as written in much of Europe.
  const words = s.replace(/[αδ]/g, ' ').trim().split(/[ ;]+/)
  if (words.length === 2 && words.every((w) => /^[+-]?\d+,\d+[°d]?$/.test(w))) s = s.replace(/,/g, '.')
  return s.replace(/ +/g, ' ').trim()
}

const NUMBER = /\d+(?:\.\d*)?|\.\d+/y

/**
 * Split prepared text into numbers with their signs, units and separators.
 * Returns null when the text holds something that never appears in coordinates (most
 * letters), has no number at all, or starts with minutes or seconds ("2M 0415"): such
 * text is a name, not a position.
 */
function read(text: string): Reading | null {
  const fields: Field[] = []
  const breaks: number[] = []
  let problem: string | null = null
  let sign: Sign | null = null // a sign waiting for its number
  let tie = false // a colon waiting for its number
  let raLabelled = false
  const flag = (why: string) => {
    problem ??= why
  }

  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (ch === ' ') {
      if (sign) flag(WHY.sign) // "- 07": a minus sign, or a dash between RA and Dec?
      i += 1
    } else if (ch === '+' || ch === '-') {
      if (sign) flag(WHY.sign)
      sign = ch
      i += 1
    } else if (ch === ':') {
      const before = fields.at(-1)
      if (!before || before.unit || tie || sign) flag(WHY.unreadable)
      tie = true
      i += 1
    } else if (ch === ',' || ch === ';' || ch === '&' || ch === '|' || ch === '/') {
      // "&" so that the "ra=269.4463&dec=4.7682" of a page address can be pasted, and
      // "|" for the "RA 17h 57m 48s | Dec +4° 41′ 36″" that a web search shows.
      if (fields.length === 0 || tie || sign) flag(WHY.unreadable)
      else breaks.push(fields.length)
      i += 1
    } else if (ch === 'α') {
      if (fields.length > 0 || raLabelled || sign) flag(WHY.order)
      raLabelled = true
      i += 1
    } else if (ch === 'δ') {
      if (fields.length === 0) flag(WHY.order)
      else if (tie || sign) flag(WHY.unreadable)
      else breaks.push(fields.length)
      i += 1
    } else {
      NUMBER.lastIndex = i
      const number = NUMBER.exec(text)
      if (!number) return null
      i += number[0].length
      // A unit counts only when it touches its number: "42s" is seconds, "42 S" is not.
      const unit = UNITS.get(text[i]) ?? null
      if (unit) {
        i += 1
        if (UNITS.has(text[i])) {
          flag(WHY.units) // two marks on one number: 42″s
          i += 1
        }
      }
      fields.push({ sign, text: number[0], unit, tied: tie })
      sign = null
      tie = false
    }
  }
  if (sign || tie) flag(WHY.unreadable)
  if (fields.length === 0) return null
  if (fields[0].unit === 'm' || fields[0].unit === 's') return null
  return { fields, breaks, problem }
}

/** The index of the field where Dec starts, or the reason it cannot be told. */
function findSplit(fields: Field[], breaks: number[]): number | string {
  const n = fields.length
  const must = new Set(breaks)
  const never = new Set<number>()
  for (let i = 1; i < n; i++) {
    const f = fields[i]
    if (f.sign || f.unit === 'h' || f.unit === 'd') must.add(i) // a sign or a degree mark starts Dec
    if (f.tied || f.unit === 'm' || f.unit === 's') never.add(i) // minutes and seconds never start anything
  }
  if (must.size === 0) {
    // Nothing explicit. A number with a decimal point is the last one of its coordinate.
    for (let i = 0; i < n - 1; i++) if (fields[i].text.includes('.')) must.add(i + 1)
    if (must.size > 1) return WHY.decimal
  }
  if (must.size > 1) return WHY.split
  const fits = (k: number) => k >= 1 && k <= 3 && n - k >= 1 && n - k <= 3 && !never.has(k)
  if (must.size === 1) {
    const [k] = must
    if (fits(k)) return k
    if (k >= n) return WHY.one // "RA 10 20, Dec" with nothing after the label
    return never.has(k) ? WHY.units : WHY.tooMany
  }
  const candidates = [1, 2, 3].filter(fits)
  if (candidates.length === 1) return candidates[0]
  if (n % 2 === 0 && candidates.includes(n / 2)) return n / 2 // 17 57 48.5 04 41 36
  return candidates.length === 0 && n <= 3 ? WHY.one : WHY.split
}

type Angle = { ok: true; degrees: number } | { ok: false; reason: string } | 'name'

/**
 * One coordinate (the numbers of RA, or of Dec) to decimal degrees. findSplit has
 * already made sure that only the first number can carry a sign, an h or a d.
 */
function readAngle(group: Field[], which: 'RA' | 'Dec'): Angle {
  const fail = (reason: string): Angle => ({ ok: false, reason })
  const first = group[0]

  // The numbers as [hours or degrees, minutes, seconds].
  let parts: string[]
  if (group.length === 1 && !first.unit && /^\d{6}(?:\.\d*)?$/.test(first.text)) {
    // hhmmss.ss or ddmmss.s run together, as in survey names.
    parts = [first.text.slice(0, 2), first.text.slice(2, 4), first.text.slice(4)]
  } else {
    parts = [first.text]
    let place = 0 // 0 hours or degrees, 1 minutes, 2 seconds
    for (const f of group.slice(1)) {
      // Marks on minutes or seconds need a mark on the first number too. Otherwise
      // "07 14 42S" (meant as south) would be read as 42 seconds north.
      if (f.unit && !first.unit) return fail(WHY.units)
      const next = f.unit === 's' ? 2 : f.unit === 'm' ? 1 : place + 1
      if (next <= place || next > 2) return fail(WHY.units)
      while (parts.length < next) parts.push('0') // 17h 48.5s: no minutes given
      // Minutes and seconds have two digits at most. "1H 0707-495" is a name.
      if (/^\d{3,}/.test(f.text)) return 'name'
      parts.push(f.text)
      place = next
    }
  }
  if (parts.slice(0, -1).some((p) => p.includes('.'))) return fail(WHY.decimal)

  const sexagesimal = parts.length > 1
  const [top, minutes = 0, seconds = 0] = parts.map(Number)
  if (minutes >= 60) return fail(`${which} minutes must be less than 60.`)
  if (seconds >= 60) return fail(`${which} seconds must be less than 60.`)
  // A number on its own is kept exactly as typed (4.6933 stays 4.6933). Several numbers
  // are added up in seconds, of time or of arc, and divided once.
  const total = top * 3600 + minutes * 60 + seconds
  const within = (limit: number) => (sexagesimal ? total < limit * 3600 : top < limit)

  if (which === 'RA') {
    // A minus is out of range. A plus is refused too: nobody signs an RA, so a signed
    // first value is most likely a Dec typed first, and reading it as RA would put the
    // person somewhere else without a word.
    if (first.sign) return fail(WHY.raSign)
    if (first.unit === 'h' || (!first.unit && sexagesimal)) {
      if (!within(24)) return fail(WHY.raHours)
      return { ok: true, degrees: sexagesimal ? total / 240 : top * 15 }
    }
    if (!within(360)) return fail(WHY.raDegrees)
    return { ok: true, degrees: sexagesimal ? total / 3600 : top }
  }
  if (first.unit === 'h') return fail(WHY.decHours)
  const size = sexagesimal ? total / 3600 : top
  if (!(size <= 90)) return fail(WHY.decRange)
  return { ok: true, degrees: first.sign === '-' && size > 0 ? -size : size }
}

function analyse(input: string): CoordsResult | 'name' {
  const fail = (reason: string): CoordsResult => ({ ok: false, reason })
  const reading = read(prepare(input))
  if (!reading) return 'name'
  if (reading.problem) return fail(reading.problem)
  const { fields, breaks } = reading
  if (fields.length === 1) return fail(WHY.one)
  if (fields.length > 6) return fail(WHY.tooMany)
  const split = findSplit(fields, breaks)
  if (typeof split === 'string') return fail(split)
  const ra = readAngle(fields.slice(0, split), 'RA')
  const dec = readAngle(fields.slice(split), 'Dec')
  if (ra === 'name' || dec === 'name') return 'name'
  if (!ra.ok) return ra
  if (!dec.ok) return dec
  return { ok: true, ra: ra.degrees, dec: dec.degrees }
}

/**
 * Read a typed position. Returns the position in decimal degrees, or a short reason in
 * plain words for why it could not be read.
 */
export function parseCoords(input: string): CoordsResult {
  const result = analyse(input)
  return result === 'name' ? { ok: false, reason: WHY.notCoordinates } : result
}

/**
 * Whether the text is an attempt at coordinates (true) or should be looked up as a name
 * (false). True does not mean the coordinates are valid: "400 10" looks like
 * coordinates, and parseCoords says what is wrong with it.
 *
 * It is a name if it has no digit, or any character that coordinates never contain:
 * every letter except the unit marks h, d, m, s written straight after a number and the
 * labels RA and Dec. Two shapes made only of coordinate characters are names too,
 * because catalogues use them: a first number marked as minutes or seconds
 * ("2M 0415"), and minutes or seconds of three digits or more ("1H 0707-495").
 */
export function looksLikeCoords(input: string): boolean {
  return analyse(input) !== 'name'
}

const two = (n: number) => String(n).padStart(2, '0')

function secondsText(count: number, perSecond: number, decimals: number): string {
  const whole = two(Math.floor(count / perSecond))
  return decimals > 0 ? `${whole}.${String(count % perSecond).padStart(decimals, '0')}` : whole
}

/** RA in decimal degrees as hours, minutes and seconds of time: "17h57m48.50s". */
export function formatRaHms(raDeg: number, decimals = 2): string {
  // Counted in whole units of the last digit shown, so 59.999 s rounds up into the next
  // minute instead of printing as 60.00 s, and 23h59m59.999s wraps to 00h.
  const perSecond = 10 ** decimals
  const day = 24 * 3600 * perSecond
  const count = ((Math.round(raDeg * 240 * perSecond) % day) + day) % day
  const hours = Math.floor(count / (3600 * perSecond))
  const minutes = Math.floor(count / (60 * perSecond)) % 60
  return `${two(hours)}h${two(minutes)}m${secondsText(count % (60 * perSecond), perSecond, decimals)}s`
}

/** Dec in decimal degrees as degrees, arcminutes and arcseconds: "+04d41m36.0s". */
export function formatDecDms(decDeg: number, decimals = 1): string {
  const perSecond = 10 ** decimals
  const count = Math.round(Math.abs(decDeg) * 3600 * perSecond)
  const sign = decDeg < 0 && count > 0 ? '-' : '+'
  const degrees = Math.floor(count / (3600 * perSecond))
  const minutes = Math.floor(count / (60 * perSecond)) % 60
  return `${sign}${two(degrees)}d${two(minutes)}m${secondsText(count % (60 * perSecond), perSecond, decimals)}s`
}

/** RA in decimal degrees for display: "269.44627". Never prints 360. */
export function formatRaDeg(raDeg: number, decimals = 5): string {
  const text = raDeg.toFixed(decimals)
  return Number(text) >= 360 ? (0).toFixed(decimals) : text
}

/** Dec in decimal degrees for display, always with its sign: "+4.76822", "-7.24218". */
export function formatDecDeg(decDeg: number, decimals = 5): string {
  const text = Math.abs(decDeg).toFixed(decimals)
  return `${decDeg < 0 && Number(text) !== 0 ? '-' : '+'}${text}`
}
