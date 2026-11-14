import { describe, expect, it } from 'vitest'
import {
  COORD_EXAMPLES,
  formatDecDeg,
  formatDecDms,
  formatRaDeg,
  formatRaHms,
  looksLikeCoords,
  parseCoords,
} from './coords'

/** The parsed position. Throws with the parser's reason, so a wrong rejection explains itself. */
function pos(input: string) {
  const r = parseCoords(input)
  if (!r.ok) throw new Error(`"${input}" was rejected: ${r.reason}`)
  return r
}

/** The reason an input was rejected. Throws if it was accepted. */
function why(input: string): string {
  const r = parseCoords(input)
  if (r.ok) throw new Error(`"${input}" was accepted as RA ${r.ra}, Dec ${r.dec}`)
  return r.reason
}

// Expected values are worked out here from the definition, not by the code under test.
const hms = (h: number, m: number, s: number) => (h + m / 60 + s / 3600) * 15
const dms = (d: number, m: number, s: number) => d + m / 60 + s / 3600

// Barnard's Star at J2000 as usually printed, and the challenge's text for WISE 0855.
const BARNARD = { ra: hms(17, 57, 48.5), dec: dms(4, 41, 36) }
const WISE = { ra: hms(8, 55, 10.831), dec: -dms(7, 14, 42.53) }

describe('decimal degrees', () => {
  it.each([
    '269.4463 4.7682',
    '269.4463, +4.7682',
    '269.4463,4.7682',
    '269.4463d +4.7682d',
    '269.4463° +4.7682°',
    '269.4463deg 4.7682deg',
    '269.4463 deg, 4.7682 deg',
    '269.4463 degrees 4.7682 degrees',
    '(269.4463, 4.7682)',
    '269.4463; 4.7682',
    'RA 269.4463, Dec 4.7682',
    'RA 269.4463°, Dec +4.7682°',
    'ra=269.4463 dec=4.7682',
    'ra=269.4463&dec=4.7682', // as in a page address
    'RA: 269.4463 Dec: 4.7682',
    '269.4463 4.7682 J2000',
    '269.4463 +4.7682 (ICRS)',
    '269.4463 | 4.7682',
    '269.4463/4.7682',
    '269.4463[2] 4.7682[note 1]', // footnote marks
    'R.A. 269.4463 Decl. 4.7682',
    'Right Ascension 269.4463, Declination 4.7682',
    'α = 269.4463°, δ = +4.7682°',
    '269,4463 4,7682', // decimal commas
    '269,4463; +4,7682',
  ])('reads %j', (input) => {
    const p = pos(input)
    expect(p.ra).toBeCloseTo(269.4463, 10)
    expect(p.dec).toBeCloseTo(4.7682, 10)
  })

  it('reads a bare pair of numbers as degrees, never hours', () => {
    expect(pos('12.5 45.25')).toMatchObject({ ra: 12.5, dec: 45.25 })
    expect(pos('12 45')).toMatchObject({ ra: 12, dec: 45 })
    expect(pos('.5 .25')).toMatchObject({ ra: 0.5, dec: 0.25 })
    expect(pos('5. 6.')).toMatchObject({ ra: 5, dec: 6 })
  })

  it('returns a decimal number exactly as typed, with no arithmetic done to it', () => {
    // These go into the page address and the backend's cache key, so 4.6933 must not
    // come back as 4.693300000000001.
    expect(pos('269.446267 4.768222')).toEqual({ ok: true, ra: 269.446267, dec: 4.768222 })
    expect(pos('133.759765 -7.242182')).toEqual({ ok: true, ra: 133.759765, dec: -7.242182 })
    expect(pos('331.096653, -56.800663')).toEqual({ ok: true, ra: 331.096653, dec: -56.800663 })
    expect(pos('76.956587d +30.401291d')).toEqual({ ok: true, ra: 76.956587, dec: 30.401291 })
    expect(pos('0.1 0.2')).toEqual({ ok: true, ra: 0.1, dec: 0.2 })
    expect(pos('17h57m48.5s +4.6933').dec).toBe(4.6933)
    // 248.167233 and 4.6933 are numbers that x * 3600 / 3600 does change.
    expect(pos('248.167233 66.755024')).toEqual({ ok: true, ra: 248.167233, dec: 66.755024 })
    expect(pos('4.6933 -4.6933')).toEqual({ ok: true, ra: 4.6933, dec: -4.6933 })
    expect(pos('4.6933d -4.6933d')).toEqual({ ok: true, ra: 4.6933, dec: -4.6933 })
  })

  it('reads a comma between two whole numbers as the separator', () => {
    expect(pos('10,20')).toMatchObject({ ra: 10, dec: 20 })
  })

  it('reads negative declinations, whatever the minus sign', () => {
    for (const minus of ['-', '\u2212', '\u2013', '\u2014', '\u2010', '\u2011', '\uff0d']) {
      const p = pos(`133.759765 ${minus}7.242182`)
      expect(p.ra).toBeCloseTo(133.759765, 10)
      expect(p.dec).toBeCloseTo(-7.242182, 10)
    }
    expect(pos('133.759765-7.242182').dec).toBeCloseTo(-7.242182, 10)
  })

  it('reads full-width digits', () => {
    const p = pos('２６９．４４６３\u3000＋４．７６８２')
    expect(p.ra).toBeCloseTo(269.4463, 10)
    expect(p.dec).toBeCloseTo(4.7682, 10)
  })
})

describe('sexagesimal', () => {
  it.each([
    '17h57m48.5s +04d41m36s',
    '17:57:48.5 +04:41:36',
    '17 57 48.5 +04 41 36',
    '17h57m48.5s+04d41m36s',
    '17h 57m 48.5s +04d 41m 36s',
    '17h57m48.5s, +04d41m36s',
    '17h57m48.5s +04°41′36″',
    '17h57m48.5s +04°41\'36"',
    "17h57m48.5s +04°41'36''",
    '17h57m48.5s +04°41\u201936\u201d', // curly quotes, as phones type them
    '17h 57m 48.5s, +04° 41′ 36″',
    '17ʰ57ᵐ48.5ˢ +04°41′36″',
    '17H57M48.5S +04D41M36S',
    '17:57:48.5, +04:41:36',
    '17:57:48.5 04:41:36',
    '17 57 48.5 04 41 36',
    '17 57 48.5, 04 41 36',
    '17h57m48.5s 04d41m36s',
    '17h 57 48.5 +04d 41 36',
    'RA 17h57m48.5s, Dec +04d41m36s',
    'RA: 17:57:48.5 Dec: +04:41:36',
    'Right ascension 17h 57m 48.5s Declination +04° 41′ 36″',
    '"17 57 48.5 +04 41 36"',
    'RA 17h 57m 48.5s | Dec +04° 41′ 36″', // as a web search shows it
    'Right ascension\t17h 57m 48.5s[1]\nDeclination\t+04° 41′ 36″[1]', // two rows copied from Wikipedia
    '17h57m48.5s / +04d41m36s',
    '17 57 48.5 +04 41 36 J2000',
    '17h57m48.5s +04d41m36s (J2000.0)',
    '17:57:48.5 +04:41:36 ICRS',
    '17 57 48.5 +04 41 36 (FK5)',
    '175748.5+044136',
    '175748.5 +044136',
    'J175748.5+044136',
  ])('reads %j', (input) => {
    const p = pos(input)
    expect(p.ra).toBeCloseTo(BARNARD.ra, 9)
    expect(p.dec).toBeCloseTo(BARNARD.dec, 9)
  })

  it.each([
    '08h55m10.831s -07d14m42.53s', // the challenge's own text
    '08h55m10.831s -7d14m42.53s', // one digit of degrees, as the challenge page prints it
    'Right Ascension 08h55m10.831s, declination -7d14m42.53s', // pasted whole from the challenge page
    'RA 08h55m10.831s, Dec -07d14m42.53s',
    '08h55m10.831s \u221207d14m42.53s',
    '08h55m10.831s \u201307d14m42.53s',
    '08:55:10.831 -07:14:42.53',
    '08 55 10.831 -07 14 42.53',
    '8 55 10.831 -7 14 42.53',
    '08h55m10.831s-07d14m42.53s',
    '08h 55m 10.831s \u221207° 14′ 42.53″',
    '085510.831-071442.53',
    'J085510.831-071442.53',
  ])('reads %j', (input) => {
    const p = pos(input)
    expect(p.ra).toBeCloseTo(WISE.ra, 9)
    expect(p.dec).toBeCloseTo(WISE.dec, 9)
  })

  it('gives the WISE 0855 text the values worked out by hand', () => {
    const p = pos('08h55m10.831s -07d14m42.53s')
    expect(p.ra).toBeCloseTo(133.795129, 6)
    expect(p.dec).toBeCloseTo(-7.245147, 6)
  })

  it('takes RA as hours when it has an h or is several numbers', () => {
    expect(pos('12h +45d')).toMatchObject({ ra: 180, dec: 45 })
    expect(pos('12h30m +45d')).toMatchObject({ ra: 187.5, dec: 45 })
    expect(pos('12 30 +45').ra).toBe(187.5)
    expect(pos('12:30 +45').ra).toBe(187.5)
    expect(pos('6h -30').ra).toBe(90)
  })

  it('takes RA as degrees when it has a d or a degree sign', () => {
    const p = pos('269d27m07.5s +04d41m36s')
    expect(p.ra).toBeCloseTo(dms(269, 27, 7.5), 9)
    expect(p.dec).toBeCloseTo(BARNARD.dec, 9)
    expect(pos('269°27′07.5″ +04°41′36″').ra).toBeCloseTo(dms(269, 27, 7.5), 9)
    expect(pos('12d30m +45d').ra).toBe(12.5)
  })

  it('reads minutes with a decimal part and no seconds', () => {
    for (const input of ['17h57.8m +04d41.6m', '17 57.8 +04 41.6', '17 57.8 04 41.6', '17:57.8 04:41.6']) {
      const p = pos(input)
      expect(p.ra).toBeCloseTo((17 + 57.8 / 60) * 15, 9)
      expect(p.dec).toBeCloseTo(4 + 41.6 / 60, 9)
    }
  })

  it('reads a sexagesimal RA with a decimal Dec, and the reverse', () => {
    expect(pos('17h57m48.5s +4.6933')).toMatchObject({ dec: 4.6933 })
    expect(pos('17h57m48.5s +4.6933').ra).toBeCloseTo(BARNARD.ra, 9)
    expect(pos('17 57 48.5 4.6933').ra).toBeCloseTo(BARNARD.ra, 9)
    expect(pos('269.4520833 +04 41 36')).toMatchObject({ ra: 269.4520833 })
    expect(pos('269.4520833 +04 41 36').dec).toBeCloseTo(BARNARD.dec, 9)
    expect(pos('269.4520833 4 41 36').dec).toBeCloseTo(BARNARD.dec, 9)
  })

  it('uses colons to tell where RA ends when there is no sign', () => {
    const p = pos('17:57 04:41:36')
    expect(p.ra).toBeCloseTo((17 + 57 / 60) * 15, 9)
    expect(p.dec).toBeCloseTo(BARNARD.dec, 9)
  })

  it('reads hours and seconds with the minutes left out', () => {
    expect(pos('17h48.5s +04d36s').ra).toBeCloseTo(hms(17, 0, 48.5), 9)
    expect(pos('17h48.5s +04d36s').dec).toBeCloseTo(dms(4, 0, 36), 9)
  })
})

describe('declinations between -1 and 0 degrees', () => {
  it.each([
    ['12 00 00 -00 30 00', -0.5],
    ['12:00:00 -00:30:00', -0.5],
    ['12h00m00s -00d30m00s', -0.5],
    ['12h00m00s \u221200°30′00″', -0.5],
    ['12 0 0 -0 30', -0.5],
    ['180 -0.5', -0.5],
    ['180, -00 30 00', -0.5],
    ['120000-003000', -0.5],
    ['12 00 00 -00 00 01', -1 / 3600],
    ['12 00 00 -00 00 00.5', -0.5 / 3600],
    ['12 00 00 +00 30 00', 0.5],
    ['12 00 00 00 30 00', 0.5],
  ])('%j has Dec %d', (input, dec) => {
    const p = pos(input)
    expect(p.ra).toBe(180)
    expect(p.dec).toBeCloseTo(dec, 12)
    expect(Math.sign(p.dec)).toBe(Math.sign(dec))
  })

  it('gives plain zero, not minus zero, for -00 00 00', () => {
    expect(Object.is(pos('12 00 00 -00 00 00').dec, 0)).toBe(true)
    expect(Object.is(pos('180 -0').dec, 0)).toBe(true)
    expect(Object.is(pos('180 -0.0').dec, 0)).toBe(true)
  })
})

describe('the edges of the range', () => {
  it('accepts RA 0', () => {
    for (const input of ['0 0', '0.0 0.0', '0h0m0s +0d0m0s', '00 00 00 +00 00 00', '00:00:00 00:00:00', '0d 0d']) {
      expect(pos(input)).toMatchObject({ ra: 0, dec: 0 })
    }
  })

  it('accepts RA just under 360 degrees', () => {
    expect(pos('359.99 0').ra).toBe(359.99)
    expect(pos('359.999999 -89.999999')).toMatchObject({ ra: 359.999999, dec: -89.999999 })
    expect(pos('23h59m59.99s +0d').ra).toBeCloseTo(hms(23, 59, 59.99), 9)
    expect(pos('23 59 59.999 0 0 0').ra).toBeLessThan(360)
    expect(pos('359d59m59.9s 0d').ra).toBeCloseTo(dms(359, 59, 59.9), 9)
  })

  it('rejects RA of 24h or 360 degrees and beyond', () => {
    expect(why('24h00m00s +00d00m00s')).toMatch(/less than 24/)
    expect(why('24 00 00 +00 00 00')).toMatch(/less than 24/)
    expect(why('24:00:00 00:00:00')).toMatch(/less than 24/)
    expect(why('24h 0d')).toMatch(/less than 24/)
    expect(why('25h 0d')).toMatch(/less than 24/)
    expect(why('360 0')).toMatch(/less than 360/)
    expect(why('360.0 0')).toMatch(/less than 360/)
    expect(why('400 10')).toMatch(/less than 360/)
    expect(why('360d00m00s 0d')).toMatch(/less than 360/)
  })

  it('says how to give degrees when a sexagesimal RA is too big for hours', () => {
    const reason = why('269 26 46.7 +04 46 05.6')
    expect(reason).toMatch(/less than 24/)
    expect(reason).toMatch(/degrees/)
  })

  it('rejects a negative RA', () => {
    expect(why('-10 20')).toMatch(/RA has no plus or minus sign/)
    expect(why('-1h 20d')).toMatch(/RA has no plus or minus sign/)
    expect(why('-0 0')).toMatch(/RA has no plus or minus sign/)
  })

  it('rejects a plus sign on RA too, because it usually means Dec was typed first', () => {
    // Read as RA then Dec these would be valid positions, in the wrong part of the sky.
    expect(why('+04 41 36 17 57 48.5')).toMatch(/Write RA first, then Dec/)
    expect(why('+4.7682 269.4463')).toMatch(/Write RA first, then Dec/)
    expect(why('+30.401291 76.956587')).toMatch(/Write RA first, then Dec/)
    expect(why('+269.4463 +4.7682')).toMatch(/RA has no plus or minus sign/)
  })

  it('accepts Dec at the poles and rejects anything past them', () => {
    expect(pos('10 90')).toMatchObject({ ra: 10, dec: 90 })
    expect(pos('10 -90')).toMatchObject({ ra: 10, dec: -90 })
    expect(pos('10 +90 00 00').dec).toBe(90)
    expect(pos('10 -90:00:00').dec).toBe(-90)
    expect(why('10 90.0001')).toMatch(/between -90 and \+90/)
    expect(why('10 -90.0001')).toMatch(/between -90 and \+90/)
    expect(why('10 +90 00 01')).toMatch(/between -90 and \+90/)
    expect(why('10 -91')).toMatch(/between -90 and \+90/)
    expect(why('4.7682 269.4463')).toMatch(/between -90 and \+90/) // Dec and RA swapped
  })

  it('rejects seconds of 60 or more', () => {
    expect(why('17 57 60 +04 41 36')).toBe('RA seconds must be less than 60.')
    expect(why('17h57m60s +04d41m36s')).toBe('RA seconds must be less than 60.')
    expect(why('17:57:60.0 +04:41:36')).toBe('RA seconds must be less than 60.')
    expect(why('17 57 48.5 +04 41 60')).toBe('Dec seconds must be less than 60.')
    expect(why('17 57 48.5 +04 41 61.2')).toBe('Dec seconds must be less than 60.')
    expect(why('175760+044136')).toBe('RA seconds must be less than 60.')
  })

  it('rejects minutes of 60 or more', () => {
    expect(why('17 60 00 +04 41 36')).toBe('RA minutes must be less than 60.')
    expect(why('17 57 48.5 +04 60 00')).toBe('Dec minutes must be less than 60.')
    expect(why('17h75m +04d')).toBe('RA minutes must be less than 60.')
  })

  it('accepts seconds and minutes just under 60', () => {
    const p = pos('17 59 59.999 +04 59 59.999')
    expect(p.ra).toBeCloseTo(hms(17, 59, 59.999), 9)
    expect(p.dec).toBeCloseTo(dms(4, 59, 59.999), 9)
  })

  it('rejects numbers too large to be anything', () => {
    expect(why(`${'9'.repeat(400)} 0`)).toMatch(/less than 360/)
    expect(why(`0 ${'9'.repeat(400)}`)).toMatch(/between -90 and \+90/)
  })
})

describe('spacing and decoration', () => {
  it.each([
    '   269.4463     4.7682   ',
    '269.4463\t4.7682',
    '\n269.4463\n4.7682\n',
    '269.4463\u00a04.7682', // no-break space
    '269.4463\u20094.7682', // thin space
    '269.4463 \u200b4.7682', // zero-width space
    '269.4463 ,  4.7682',
    '269.4463, 4.7682.',
    '269.4463 4.7682,',
    '[269.4463, 4.7682]',
  ])('reads %j', (input) => {
    expect(pos(input)).toMatchObject({ ra: 269.4463, dec: 4.7682 })
  })

  it('reads sexagesimal text copied with no-break spaces', () => {
    const p = pos('17h\u00a057m\u00a048.5s   +04°\u00a041′\u00a036″')
    expect(p.ra).toBeCloseTo(BARNARD.ra, 9)
    expect(p.dec).toBeCloseTo(BARNARD.dec, 9)
  })
})

describe('input that cannot be read', () => {
  it.each([
    '',
    '   ',
    'hello',
    "Barnard's Star",
    'WISE 0855-0714',
    'NaN NaN',
    'Infinity 0',
    '1e2 5',
    '0x10 5',
    '10 20 N',
    '07 14 42 S',
    '12 north',
    '17 57 48.5 +04 41 36 B1950', // an old reference frame: not the same place, so not accepted
    '17 h 57 m 48.5 s +04 d 41 m 36 s', // units must touch their numbers
    '?',
    '--',
    '+',
    ':',
    ',',
  ])('%j is not coordinates', (input) => {
    expect(why(input)).toBe('This does not look like coordinates.')
  })

  it('asks for the second value when there is only one', () => {
    const lone = ['269.4463', '17h57m48.5s', '17:57:48.5', '+04d41m36s', 'RA 269.4463', '12h', 'RA 17 57 48.5, Dec', '12:30']
    for (const input of lone) {
      expect(why(input)).toMatch(/only one value/)
    }
  })

  it('does not guess where RA ends', () => {
    expect(why('12 30 45')).toMatch(/where RA ends/)
    expect(why('17 57 48 04 41')).toMatch(/where RA ends/)
    expect(why('17 57 48 04 41 36 12')).toMatch(/too many numbers/)
    expect(why('1 2 3 4, 5')).toMatch(/too many numbers/)
    expect(why('17, 57, 48.5, +04, 41, 36')).toMatch(/where RA ends/)
    expect(why('17-57-48')).toMatch(/where RA ends/)
    expect(why('2026-11-14')).toMatch(/where RA ends/)
    expect(why('1:2:3:4')).toMatch(/where RA ends/)
  })

  it('reads five numbers when a decimal point or a comma shows where RA ends', () => {
    expect(pos('17 57 48.5 04 41').dec).toBeCloseTo(4 + 41 / 60, 9)
    expect(pos('17 57 48, 04 41').dec).toBeCloseTo(4 + 41 / 60, 9)
    expect(pos('17 57, 04 41 36').ra).toBeCloseTo((17 + 57 / 60) * 15, 9)
  })

  it('rejects a decimal point anywhere but the last number', () => {
    expect(why('17.5 30 00 +04 41 36')).toMatch(/decimal point/)
    expect(why('17h30.5m10s +04d')).toMatch(/decimal point/)
    expect(why('1.5 2.5 3.5')).toMatch(/decimal point/)
    expect(why('1.2.3 4')).toMatch(/decimal point/)
  })

  it('rejects a sign that floats free of its number', () => {
    expect(why('17 57 48.5 - 07 14 42')).toMatch(/right in front of its number/)
    expect(why('+ 5 5')).toMatch(/right in front of its number/)
    expect(why('5 +-5')).toMatch(/right in front of its number/)
  })

  it('rejects units in the wrong place', () => {
    expect(why('17h57m48.5s +04h41m36s')).toMatch(/Dec is measured in degrees/)
    expect(why('17h57s30m +04d')).toMatch(/units/)
    expect(why('17h57m48.5s +04d41m36"s')).toMatch(/units/)
    expect(why('17 57m 48s +04 41 36')).toMatch(/units/)
    expect(why('07 14 42s 07 14 42s')).toMatch(/units/)
    expect(why('17h, 57m')).toMatch(/units/)
  })

  it('rejects Dec written before RA', () => {
    expect(why('Dec +4.7682 RA 269.4463')).toBe('Write RA first, then Dec.')
    expect(why('269.4463 RA 4.7682')).toBe('Write RA first, then Dec.')
  })

  it('always gives a short reason in words', () => {
    const bad = ['', 'x', '1', '1 2 3', '400 1', '1 100', '17 57 60 1 1 1', '1.5 2.5 3', '5 - 5', '24h 0d', '-1 1', '1h 1h']
    for (const input of bad) {
      const reason = why(input)
      expect(reason.length).toBeGreaterThan(10)
      expect(reason.length).toBeLessThan(130)
      expect(reason).toMatch(/\.$/)
    }
  })
})

describe('looksLikeCoords', () => {
  it.each([
    ...COORD_EXAMPLES,
    '269.4463, +4.7682',
    '17:57:48.5 +04:41:36',
    '17 57 48.5 +04 41 36',
    '08h55m10.831s -07d14m42.53s',
    'RA 08h55m10.831s, Dec -07d14m42.53s',
    'J085510.83-071442.5',
    // Attempts at coordinates that are wrong: still coordinates, so the person is told
    // what is wrong instead of "no object of that name".
    '269.4463',
    '400 10',
    '17 57 60 +04 41 36',
    '12 30 45',
    '0855-0714',
  ])('%j is treated as coordinates', (input) => {
    expect(looksLikeCoords(input)).toBe(true)
  })

  it.each([
    "Barnard's Star",
    'barnards star',
    'Epsilon Indi B',
    'eps Ind B',
    'WISE 0855',
    'WISE 0855-0714',
    'WISE J085510.83-071442.5',
    'WISEA J085510.74-071442.5',
    'J0855-0714',
    'RW Aurigae',
    'R Draconis',
    'M31',
    'M 31',
    'NGC 1234',
    '51 Peg',
    '61 Cygni',
    '47 Tuc',
    '3C 273',
    'HD 209458',
    'TRAPPIST-1',
    '2MASS J0415-0935',
    '2M 0415',
    '2S 0114+650',
    '1H 0707-495',
    '4U 1820-30',
    'S5 0014+81',
    'alpha Centauri',
    'α Centauri',
    'δ Cep',
    'tau Ceti',
    'Sirius',
    '',
    '   ',
  ])('%j is treated as a name', (input) => {
    expect(looksLikeCoords(input)).toBe(false)
  })
})

describe('the examples shown to people', () => {
  it.each([...COORD_EXAMPLES])('%j is accepted', (example) => {
    expect(parseCoords(example).ok).toBe(true)
  })
})

describe('formatting', () => {
  it('writes RA as hours, minutes and seconds', () => {
    expect(formatRaHms(BARNARD.ra)).toBe('17h57m48.50s')
    expect(formatRaHms(WISE.ra, 3)).toBe('08h55m10.831s')
    expect(formatRaHms(0)).toBe('00h00m00.00s')
    expect(formatRaHms(180, 0)).toBe('12h00m00s')
  })

  it('writes Dec as degrees, arcminutes and arcseconds with its sign', () => {
    expect(formatDecDms(BARNARD.dec)).toBe('+04d41m36.0s')
    expect(formatDecDms(WISE.dec, 2)).toBe('-07d14m42.53s')
    expect(formatDecDms(-0.5)).toBe('-00d30m00.0s')
    expect(formatDecDms(0)).toBe('+00d00m00.0s')
    expect(formatDecDms(-90)).toBe('-90d00m00.0s')
  })

  it('carries a rounded-up 60 into the next minute, hour or day', () => {
    expect(formatRaHms(hms(17, 57, 59.999))).toBe('17h58m00.00s')
    expect(formatRaHms(hms(17, 59, 59.999))).toBe('18h00m00.00s')
    expect(formatRaHms(hms(23, 59, 59.999))).toBe('00h00m00.00s')
    expect(formatRaHms(359.9999999)).toBe('00h00m00.00s')
    expect(formatDecDms(dms(4, 41, 59.96))).toBe('+04d42m00.0s')
    expect(formatDecDms(-dms(4, 59, 59.96))).toBe('-05d00m00.0s')
  })

  it('never writes minus zero', () => {
    expect(formatDecDms(-0.000001)).toBe('+00d00m00.0s')
    expect(formatDecDms(-0)).toBe('+00d00m00.0s')
    expect(formatDecDeg(-0.0000001)).toBe('+0.00000')
    expect(formatDecDeg(-0)).toBe('+0.00000')
  })

  it('writes decimal degrees with a sign on Dec only', () => {
    expect(formatRaDeg(269.446267)).toBe('269.44627')
    expect(formatDecDeg(4.768222)).toBe('+4.76822')
    expect(formatRaDeg(133.759768)).toBe('133.75977')
    expect(formatRaDeg(133.759765, 6)).toBe('133.759765')
    expect(formatDecDeg(-7.242182)).toBe('-7.24218')
    expect(formatDecDeg(-7.242182, 6)).toBe('-7.242182')
    expect(formatRaDeg(359.9999999)).toBe('0.00000')
    expect(formatRaDeg(359.99)).toBe('359.99000')
  })
})

describe('round trips', () => {
  /** Smallest angle between two RAs in degrees, so 359.99999 and 0 count as close. */
  const raGap = (a: number, b: number) => Math.abs(((a - b + 540) % 360) - 180)
  const ARCSEC = 1 / 3600

  // A fixed list of awkward places plus 2000 scattered ones (seeded, so every run is the same).
  const places: { ra: number; dec: number }[] = [
    { ra: 0, dec: 0 },
    { ra: 0, dec: 90 },
    { ra: 0, dec: -90 },
    { ra: 359.99, dec: 0 },
    { ra: 359.9999999, dec: -0.0000001 },
    { ra: 15, dec: -0.5 },
    { ra: 180, dec: -0.0001 },
    { ra: 269.446267, dec: 4.768222 }, // Barnard's Star in 2026
    { ra: 133.759765, dec: -7.242182 }, // WISE 0855 in 2026
    { ra: 331.096653, dec: -56.800663 },
    { ra: 76.956587, dec: 30.401291 },
    { ra: 248.167233, dec: 66.755024 },
    { ra: hms(17, 59, 59.999), dec: dms(4, 59, 59.96) },
    { ra: hms(23, 59, 59.996), dec: -dms(89, 59, 59.96) },
  ]
  let seed = 20261114
  const random = () => {
    // mulberry32
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  for (let i = 0; i < 2000; i++) places.push({ ra: random() * 360, dec: random() * 180 - 90 })

  it('decimal degrees survive being written and read back', () => {
    for (const p of places) {
      const back = pos(`${formatRaDeg(p.ra, 6)} ${formatDecDeg(p.dec, 6)}`)
      expect(raGap(back.ra, p.ra)).toBeLessThanOrEqual(0.5e-6 + 1e-12)
      expect(Math.abs(back.dec - p.dec)).toBeLessThanOrEqual(0.5e-6 + 1e-12)
    }
  })

  it('sexagesimal survives being written and read back, to half the last digit shown', () => {
    for (const p of places) {
      const text = `${formatRaHms(p.ra)} ${formatDecDms(p.dec)}`
      const back = pos(text)
      expect(raGap(back.ra, p.ra)).toBeLessThanOrEqual(0.005 * 15 * ARCSEC + 1e-9) // 0.005 s of time
      expect(Math.abs(back.dec - p.dec)).toBeLessThanOrEqual(0.05 * ARCSEC + 1e-9)
      expect(back.ra).toBeGreaterThanOrEqual(0)
      expect(back.ra).toBeLessThan(360)
    }
  })

  it('sexagesimal with more digits comes back closer', () => {
    for (const p of places) {
      const back = pos(`${formatRaHms(p.ra, 5)} ${formatDecDms(p.dec, 4)}`)
      expect(raGap(back.ra, p.ra)).toBeLessThanOrEqual(0.000005 * 15 * ARCSEC + 1e-9)
      expect(Math.abs(back.dec - p.dec)).toBeLessThanOrEqual(0.00005 * ARCSEC + 1e-9)
    }
  })

  it('writing what was read gives the same text again', () => {
    for (const p of places) {
      const text = `${formatRaHms(p.ra)} ${formatDecDms(p.dec)}`
      const back = pos(text)
      expect(`${formatRaHms(back.ra)} ${formatDecDms(back.dec)}`).toBe(text)
    }
  })

  it('the same position reads the same in every spelling', () => {
    for (const p of places.slice(0, 200)) {
      const ra = formatRaHms(p.ra) // 17h57m48.50s
      const dec = formatDecDms(p.dec) // +04d41m36.0s
      const want = pos(`${ra} ${dec}`)
      const colons = `${ra.replace(/[hm]/g, ':').replace('s', '')} ${dec.replace(/[dm]/g, ':').replace('s', '')}`
      const spaces = colons.replace(/:/g, ' ')
      const marks = `${ra} ${dec.replace('d', '°').replace('m', '′').replace('s', '″')}`
      const run = `${ra.replace(/[hms]/g, '')}${dec.replace(/[dms]/g, '')}`
      for (const spelling of [colons, spaces, marks, run, `RA ${ra}, Dec ${dec}`]) {
        const got = pos(spelling)
        expect(got.ra).toBeCloseTo(want.ra, 9)
        expect(got.dec).toBeCloseTo(want.dec, 9)
      }
    }
  })
})
