// The card's wording, on the real answers saved by scripts/check_identify.py --save
// (fixtures/identify/*.json; tests/test_identify.py checks they are what the backend returns).
import { describe, expect, it } from 'vitest'
import { ANSWERS } from './fixtures/identify/answers'
import {
  NOTHING_HERE,
  NO_NAME,
  TOO_COOL,
  arcsec,
  article,
  beginnerFacts,
  blurSentences,
  cardTitle,
  catalogueName,
  expertRows,
  identifyUrl,
  kindSentence,
  lookTarget,
  notKnownLine,
  partOfSentence,
  pictureNotes,
  roundTemperature,
  sig2,
  sig3,
  widthWords,
  type IdentifyResult,
} from './identify'

/** Every sentence a beginner reads, apart from the brief's own fixed phrase for a body too cool to glow. */
function beginnerSentences(r: IdentifyResult): string[] {
  const texts = [
    kindSentence(r),
    partOfSentence(r),
    ...blurSentences(r),
    ...beginnerFacts(r).map((f) => f.text),
    // The card shows what is not known only about an object it found.
    r.gaia || r.simbad ? notKnownLine(r) : null,
    ...pictureNotes(r),
    ...(r.nothing_catalogued ? [NOTHING_HERE] : []),
  ].filter((t): t is string => !!t)
  return texts
    .flatMap((t) => t.split(/(?<=[.!?])\s+(?=[A-Z])/))
    .filter((s) => !s.toLowerCase().includes(TOO_COOL.slice(0, 30)))
}

describe('numbers in words', () => {
  it('rounds for reading', () => {
    expect([5.9629, 12.0505, 598.0, 2607.3, 6628.96].map(sig3)).toEqual(['5.96', '12.1', '598', '2,610', '6,630'])
    expect([36.45, 850.1, 135.04, 0.0311].map(sig2)).toEqual(['36', '850', '140', '0.031'])
    expect([3099.6, 1416.96, 4799.98, 285.3].map(roundTemperature)).toEqual(['3,100', '1,400', '4,800', '285'])
    expect([10.393, 4.684, 0.762, 0.0251, 0.00322].map(arcsec)).toEqual(['10.4', '4.7', '0.76', '0.025', '0.0032'])
  })
  it('says sizes as fractions when they are close to one', () => {
    expect(widthWords(0.2022, 'the Sun')).toBe('about a fifth as wide as the Sun')
    expect(widthWords(0.5, 'the Sun')).toBe('about half as wide as the Sun')
    expect(widthWords(0.37, 'the Sun')).toBe('about 0.37 times as wide as the Sun')
    expect(widthWords(1.02, 'the Sun')).toBe('about as wide as the Sun')
    expect(widthWords(1.158, 'the Sun')).toBe('about 1.16 times as wide as the Sun')
    expect(widthWords(250, 'the Sun')).toBe('about 250 times as wide as the Sun')
  })
  it('chooses a or an as the word is said', () => {
    expect(['M dwarf', 'Orion variable', 'HII region', 'RR Lyrae variable', 'F-type star', 'X-ray source'].map(article)).toEqual([
      'an',
      'an',
      'an',
      'an',
      'an',
      'an',
    ])
    expect(['BY Draconis variable', 'Mira variable', 'T Tauri star', 'Y dwarf', 'brown dwarf', 'K dwarf'].map(article)).toEqual([
      'a',
      'a',
      'a',
      'a',
      'a',
      'a',
    ])
  })
  it('builds the request', () => {
    expect(identifyUrl(269.446267, 4.768222)).toBe('/api/identify?ra=269.446267&dec=4.768222')
    expect(identifyUrl(1, -2, 6.15, 2025.7)).toBe('/api/identify?ra=1&dec=-2&radius=6.15&epoch=2025.7')
  })
})

describe('what the card says about each test object', () => {
  it("Barnard's Star", () => {
    const r = ANSWERS.barnard
    expect(kindSentence(r)).toBe('SIMBAD lists it as an M dwarf: a small, cool, red star.')
    expect(beginnerFacts(r)).toEqual([
      { text: 'It is about 5.96 light-years away. The light we see left it 6 years ago.', source: 'Gaia' },
      { text: "Its surface is about 3,100 degrees (kelvin), cooler than the Sun's 5,772, so it glows orange.", source: 'Gaia' },
      { text: 'It is about a fifth as wide as the Sun (0.20 times).', source: 'Gaia' },
      {
        text: 'Each year it drifts 1.7 SPHEREx pixels across our sky: 10.4 arcseconds, each 1/3600 of a degree. Across our view it moves 90 km every second.',
        source: 'Gaia',
      },
      { text: 'SIMBAD lists 924 scientific papers about it.', source: 'SIMBAD' },
    ])
    expect(blurSentences(r)).toEqual(['Gaia lists one other star in the same SPHEREx pixel, about 100,000 times fainter in visible light.'])
    expect(notKnownLine(r)).toBe(
      'Not in the catalogues we asked: its surface details. SIMBAD lists 4 planets around it; their sizes are not in the catalogues we asked.',
    )
    expect(pictureNotes(r)[0]).toBe('Colour: how a 3,100 K surface looks to the eye (Gaia DR3 teff_gspphot).')
    expect(pictureNotes(r)[1]).toBe("Size: 0.202 times the Sun's radius (Gaia radius_flame), beside the Sun to scale.")
    expect(cardTitle(r)).toBe("Barnard's star")
    expect(catalogueName(r, "Barnard's Star")).toBeNull()
  })

  it('Epsilon Indi B: the pair, with its own numbers only', () => {
    const r = ANSWERS.epsindib
    expect(kindSentence(r)).toBe('SIMBAD lists it as a brown dwarf: bigger than a planet, too small to shine like a star.')
    expect(blurSentences(r)).toEqual(["It is a pair: SIMBAD's type, T1V+T6V, names two objects seen as one point."])
    const facts = beginnerFacts(r).map((f) => f.text)
    expect(facts[0]).toContain('12.1 light-years')
    expect(facts[0]).toContain("Gaia's fit for it is poor") // RUWE 4.3
    expect(facts[1]).toBe("Its surface is about 1,400 degrees (kelvin), cooler than the Sun's 5,772, so it glows red-orange.")
    expect(pictureNotes(r)).toContain('Gaia measured the pair as one point: this is one temperature for both.')
    expect(pictureNotes(r)).toContain("Size not measured: the disc's size means nothing, and the Sun is not shown.")
    expect(JSON.stringify(r)).not.toContain('eps Ind A')
  })

  it('WISE 0855: SIMBAD only, and nothing about its temperature', () => {
    const r = ANSWERS.wise0855
    expect(kindSentence(r)).toBe('SIMBAD lists it as a Y dwarf: the coldest kind of brown dwarf known.')
    const facts = beginnerFacts(r)
    expect(facts.map((f) => f.source)).toEqual(['SIMBAD', 'SIMBAD', 'SIMBAD'])
    expect(facts[0].text).toBe('It is about 7.43 light-years away. The light we see left it 7 years ago.')
    const all = beginnerSentences(r).join(' ')
    expect(all).not.toMatch(/kelvin|too cool|glow/)
    expect(notKnownLine(r)).toBe('Not in the catalogues we asked: its temperature, its size, or its surface details.')
    expect(pictureNotes(r)).toEqual([])
  })

  it('RW Aurigae: the star nearest the place, its partner in the same blur, and the system', () => {
    const r = ANSWERS.rwaur
    expect(cardTitle(r, 'RW Aurigae')).toBe('RW Aurigae')
    expect(catalogueName(r, 'RW Aurigae')).toBe('RW Aur B')
    expect(kindSentence(r)).toBe('SIMBAD lists it as an Orion variable: a young star whose brightness changes unevenly.')
    expect(partOfSentence(r)).toBe('SIMBAD lists it as part of RW Aur.')
    expect(blurSentences(r)).toEqual(['This blur holds 2 catalogued stars, not one: RW Aur A, brighter, is 1.5 arcseconds away.'])
    expect(beginnerFacts(r)[0].text).toBe(
      "It is about 598 light-years away, give or take 36. The light we see left it 598 years ago. Gaia's fit for it is poor (often a sign of a close pair), so this distance is less sure.",
    )
    expect(expertRows(r)[0]).toMatchObject({ quantity: 'Parallax' })
    expect(expertRows(r).some((row) => row.quantity === 'Caution: RUWE above 1.4' && row.value === '16.42')).toBe(true)
  })

  it('R Draconis: no temperature or radius from Gaia, so no disc', () => {
    const r = ANSWERS.rdra
    expect(kindSentence(r)).toBe('SIMBAD lists it as a Mira variable: a cool giant star that swells and shrinks over many months.')
    expect(r.portrait.temperature).toBeNull()
    expect(pictureNotes(r)).toEqual([])
    expect(beginnerFacts(r).map((f) => f.source)).toEqual(['Gaia', 'Gaia', 'SIMBAD'])
    expect(beginnerFacts(r)[0].text).toBe('It is about 2,610 light-years away, give or take 140. The light we see left it 2,610 years ago.')
  })

  it('an ordinary faint star with no name', () => {
    const r = ANSWERS.faint
    expect(cardTitle(r)).toBe(NO_NAME)
    expect(kindSentence(r)).toBe('Gaia lists it, but no catalogue we asked says what kind of object it is.')
    expect(beginnerFacts(r).map((f) => f.text)[2]).toBe('It is about 1.16 times as wide as the Sun.')
    expect(beginnerFacts(r)).toHaveLength(4) // no SIMBAD entry, so nothing on how well studied
  })

  it('the candidate place: nothing to say about the object itself', () => {
    const r = ANSWERS.candidate
    expect(kindSentence(r)).toBeNull()
    expect(beginnerFacts(r)).toEqual([])
    expect(pictureNotes(r)).toEqual([])
    expect(lookTarget(r)).toEqual({ ra: 253.18038, dec: -44.67697, pmra: null, pmdec: null, parallax: null, name: null })
  })

  it('"Look at this one" hands back the place on the pictures and the motion', () => {
    expect(lookTarget(ANSWERS.barnard, "Barnard's Star")).toMatchObject({
      ra: ANSWERS.barnard.gaia!.position.ra,
      dec: ANSWERS.barnard.gaia!.position.dec,
      pmra: -801.5509783684709,
      pmdec: 10362.394206546573,
      parallax: 546.975939730948,
      name: "Barnard's Star",
    })
    expect(lookTarget(ANSWERS.wise0855)).toMatchObject({ pmra: -8123.7, pmdec: 673.2, parallax: 439 })
  })
})

describe('reading level', () => {
  const BANNED = /\b(parallax|proper motion|effective temperature|magnitude|spectral type)\b/i
  it.each(Object.keys(ANSWERS))('%s: sentences of 20 words or fewer, without unexplained jargon', (key) => {
    for (const s of beginnerSentences(ANSWERS[key])) {
      expect(s.split(/\s+/).filter(Boolean).length, s).toBeLessThanOrEqual(20)
      expect(s, s).not.toMatch(BANNED)
    }
  })
  it('the brief\'s own phrase for a body too cool to glow is kept word for word', () => {
    expect(TOO_COOL).toBe('too cool to glow in light our eyes can see: it shines in infrared, which is why SPHEREx can see it')
  })
})
