// The card's wording, on the real answers saved by scripts/check_identify.py --save
// (fixtures/identify/*.json; tests/test_identify.py checks they are what the backend returns).
import { describe, expect, it } from 'vitest'
import { ANSWERS, PRESSES } from './fixtures/identify/answers'
import {
  NOTHING_HERE,
  NOTHING_TITLE,
  NO_NAME,
  TOO_COOL,
  arcsec,
  article,
  beginnerFacts,
  blurSentences,
  cardTitle,
  catalogueName,
  colourDrawn,
  disagreements,
  errorDecimals,
  expertGroups,
  fmtQuantity,
  identifyUrl,
  kindSentence,
  lightWords,
  lookTarget,
  notKnownLine,
  nothingFoundLines,
  orList,
  partOfSentence,
  pictureDescription,
  pictureNotes,
  readableName,
  roundTemperature,
  sig2,
  sig3,
  systemLine,
  temperatureForPicture,
  widthWords,
  withError,
  type IdentifyResult,
} from './identify'
import { portraitLayout } from './portrait'

const copy = (r: IdentifyResult): IdentifyResult => JSON.parse(JSON.stringify(r))

/** Every sentence a beginner reads, apart from the brief's own fixed phrase for a body too cool to glow. */
function beginnerSentences(r: IdentifyResult, name?: string): string[] {
  const found = r.gaia || r.simbad
  const texts = [
    cardTitle(r, name),
    systemLine(r, name),
    kindSentence(r),
    partOfSentence(r, name),
    ...blurSentences(r, 'beginner'),
    ...beginnerFacts(r).map((f) => f.text),
    // The card shows what is not known only about an object it found.
    found ? notKnownLine(r) : null,
    ...pictureNotes(r, 'beginner'),
    ...(r.nothing_catalogued ? [NOTHING_HERE] : []),
    ...(found ? [] : nothingFoundLines(r)),
  ].filter((t): t is string => !!t)
  return texts
    .flatMap((t) => t.split(/(?<=[.!?])\s+(?=[A-Z])/))
    .filter((s) => !s.toLowerCase().includes(TOO_COOL.slice(0, 30)))
}

describe('numbers in words', () => {
  it('rounds for reading', () => {
    expect([5.9629, 12.0505, 598.0, 2607.3, 6628.96].map(sig3)).toEqual(['5.96', '12.1', '598', '2,610', '6,630'])
    expect([36.45, 850.1, 135.04, 0.0311, 509.1, 12.05, 1.158].map(sig2)).toEqual(['36', '850', '140', '0.031', '510', '12', '1.2'])
    expect([3099.6, 1416.96, 4799.98, 285.3].map(roundTemperature)).toEqual(['3,100', '1,400', '4,800', '285'])
    expect([10.393, 4.684, 0.762, 0.0251, 0.00322].map(arcsec)).toEqual(['10.4', '4.7', '0.76', '0.025', '0.0032'])
  })
  it('rounds a value to its error by the Particle Data Group rule', () => {
    // 100 to 354: two significant figures; 355 to 949: one; 950 to 999: up to 1000, two.
    expect([0.0318, 0.0401, 0.000134, 0.000437, 0.006436, 1.437, 98.12, 0.0098].map(errorDecimals)).toEqual([3, 2, 5, 4, 3, 1, 0, 3])
    expect(withError(546.975939730948, 0.04011635482311249)).toEqual({ value: '546.98', error: '0.04' })
    expect(withError(-801.5509783684709, 0.0318208672106266)).toEqual({ value: '-801.551', error: '0.032' })
    expect(withError(90.0759, 0.006436)).toEqual({ value: '90.076', error: '0.006' })
    expect(withError(1416.964599609375, 98.1231918334961)).toEqual({ value: '1,417', error: '98' })
    expect(fmtQuantity({ value: 3099.633544921875, error: null, lower: 3098.75732421875, upper: 3101.6318359375 }, 'K')).toEqual({
      value: '3,099.6',
      uncertainty: '3,098.8 to 3,101.6',
    })
  })
  it('says sizes as fractions when they are close to one', () => {
    expect(widthWords(0.2022, 'the Sun')).toBe('about a fifth as wide as the Sun')
    expect(widthWords(0.5, 'the Sun')).toBe('about half as wide as the Sun')
    expect(widthWords(0.37, 'the Sun')).toBe('about 0.37 times as wide as the Sun')
    expect(widthWords(1.02, 'the Sun')).toBe('about as wide as the Sun')
    expect(widthWords(1.158, 'the Sun')).toBe('about 1.2 times as wide as the Sun')
    expect(widthWords(250, 'the Sun')).toBe('about 250 times as wide as the Sun')
  })
  it('chooses a or an as the word is said', () => {
    expect(['M dwarf', 'Orion variable', 'HII region', 'RR Lyrae variable', 'F-type star', 'X-ray source'].map(article)).toEqual(['an', 'an', 'an', 'an', 'an', 'an'])
    expect(['BY Draconis variable', 'Mira variable', 'T Tauri star', 'Y dwarf', 'brown dwarf', 'K dwarf'].map(article)).toEqual(['a', 'a', 'a', 'a', 'a', 'a'])
  })
  it('joins lists without a stray comma', () => {
    expect(orList(['its size'])).toBe('its size')
    expect(orList(['its size', 'its surface details'])).toBe('its size or its surface details')
    expect(orList(['a', 'b', 'c'])).toBe('a, b, or c')
  })
  it('builds the request, with the picture date when given', () => {
    expect(identifyUrl(269.446267, 4.768222)).toBe('/api/identify?ra=269.446267&dec=4.768222')
    expect(identifyUrl(1, -2, 6.15, 2025.7)).toBe('/api/identify?ra=1&dec=-2&radius=6.15&epoch=2025.7')
    expect(identifyUrl(269.446116, 4.770171, undefined, 2026.676)).toBe('/api/identify?ra=269.446116&dec=4.770171&epoch=2026.676')
  })
  it('says SIMBAD star names as they are spoken', () => {
    expect(['eps Ind B', 'RW Aur A', 'R Dra', '61 Cyg A', 'alf01 Cen', 'V1298 Tau', "Barnard's star", 'WISEA J085510.74-071442.5', 'Gaia DR3 5964332607636528768'].map(readableName)).toEqual([
      'Epsilon Indi B',
      'RW Aurigae A',
      'R Draconis',
      '61 Cygni A',
      'Alpha 1 Centauri',
      'V1298 Tauri',
      "Barnard's star",
      'WISEA J085510.74-071442.5',
      'Gaia DR3 5964332607636528768',
    ])
  })
  it('describes a source by its measured light only', () => {
    expect(lightWords(19.35, 3.6)).toBe('Gaia measures it as too faint to see without a telescope and much redder than the Sun.')
    expect(lightWords(5, 0.8)).toBe('Gaia measures it as close to the Sun in colour.')
    expect(lightWords(null, null)).toBeNull()
  })
})

describe('what the card says about each test object', () => {
  it("Barnard's Star", () => {
    const r = ANSWERS.barnard
    expect(kindSentence(r)).toBe('SIMBAD lists it as an M dwarf: a small, cool star (astronomers call these red dwarfs).')
    expect(beginnerFacts(r)).toEqual([
      { text: 'It is about 5.96 light-years away. The light we see left it 6 years ago.', source: 'Gaia' },
      {
        text: "Gaia's model, fitted to its colours and brightness, puts its surface at about 3,100 kelvin (the Sun: 5,772). Published measurements in SIMBAD centre on about 3,200 kelvin. A perfect glowing body this hot would look orange.",
        source: 'Gaia, SIMBAD',
      },
      { text: "Gaia's model makes it about a fifth as wide as the Sun (0.20 times).", source: 'Gaia' },
      {
        text: 'Each year it drifts 1.7 SPHEREx pixels across our sky: 10.4 arcseconds, each 1/3600 of a degree. Across our view it moves 90 km every second.',
        source: 'Gaia',
      },
      { text: 'SIMBAD lists 924 scientific papers that mention it.', source: 'SIMBAD' },
    ])
    // The faint source beside it is not one of its artefacts: Barnard's Star was 100 arcsec away when Gaia looked.
    expect(blurSentences(r)).toEqual(['Gaia lists one other source in the same SPHEREx pixel, about 100,000 times fainter in visible light.'])
    expect(notKnownLine(r)).toBe(
      'Not in the catalogues we asked: its surface details. SIMBAD lists 4 planets around it; their sizes are not in the catalogues we asked.',
    )
    expect(colourDrawn(r)).toBe('blackbody')
    expect(pictureNotes(r, 'expert')[0]).toBe(
      "Colour: a blackbody at 3,100 K (Gaia DR3 teff_gspphot) as the eye sees it (CIE 1931). The star's real colour is changed by its atmosphere and is not measured.",
    )
    expect(pictureNotes(r, 'beginner').join(' ')).not.toMatch(/teff_|radius_flame|u = 0\.6/)
    expect(cardTitle(r)).toBe("Barnard's star")
    expect(catalogueName(r, "Barnard's Star")).toBeNull()
    expect(disagreements(r)).toEqual([
      "Gaia's temperature estimates disagree: GSP-Phot 3,100 K, GSP-Spec 4,250 K (GSP-Spec can be far off for cool dwarfs). The picture uses GSP-Phot.",
      "SIMBAD's 55 published temperatures have a median of 3,243 K, against Gaia's 3,100 K used for the picture.",
    ])
  })

  it("Barnard's Star pressed on a visit-3 picture is still Barnard's Star", () => {
    const r = PRESSES.barnard_visit3
    expect(r.query.epoch).toBe(2026.676)
    expect(r.nothing_catalogued).toBe(false)
    expect(cardTitle(r, "Barnard's Star")).toBe("Barnard's Star")
    expect(beginnerFacts(r)[0].text).toBe('It is about 5.96 light-years away. The light we see left it 6 years ago.')
    // "Look at this one" hands back the 2026.0 place, the same as from the 2026.0 lookup.
    expect(lookTarget(r)).toMatchObject({ ra: ANSWERS.barnard.gaia!.resolve_position.ra, dec: ANSWERS.barnard.gaia!.resolve_position.dec })
  })

  it('Epsilon Indi B: the pair, its own numbers only, and no colour drawn', () => {
    const r = ANSWERS.epsindib
    expect(cardTitle(r, 'Epsilon Indi B')).toBe('Epsilon Indi B')
    expect(cardTitle(r)).toBe('Epsilon Indi B')
    expect(kindSentence(r)).toBe('SIMBAD lists it as a brown dwarf: heavier than a planet, too light to burn hydrogen like a star.')
    expect(blurSentences(r)).toEqual(['It is really two brown dwarfs, so close together they look like one point.'])
    expect(blurSentences(r, 'expert')).toEqual(["A pair: SIMBAD's spectral type, T1V+T6V, names two objects seen as one point."])
    const facts = beginnerFacts(r).map((f) => f.text)
    // RUWE 4.3: two significant figures, no "give or take", and the poor fit said.
    expect(facts[0]).toBe(
      "It is about 12 light-years away. The light we see left it 12 years ago. Gaia's fit for it is poor (often a sign of a close pair), so this distance is less sure.",
    )
    expect(facts[1]).toBe(
      "Gaia's rough estimate, from its colours and brightness, puts its surface at about 1,400 kelvin (the Sun: 5,772). Gaia saw the two as one point, so this temperature is a blend, mostly from the brighter one. By SIMBAD's classes, the other one is cooler. Its gases soak up much of its visible light, so its colour to our eyes is not known.",
    )
    expect(facts.join(' ')).not.toMatch(/red-orange|looks to the eye|glows/)
    expect(colourDrawn(r)).toBe('withheld')
    expect(temperatureForPicture(r)).toBeNull()
    expect(pictureNotes(r, 'beginner')).toContain("No colour drawn: its gases soak up much of its light, so a perfect glowing body's colour would be wrong.")
    expect(disagreements(r)).toEqual([
      'Gaia measured the light of both together (T1V+T6V), so its temperature is a blend dominated by the brighter one. The partner SIMBAD types T6V is the cooler one.',
    ])
    const ucd = expertGroups(r)
      .flatMap((g) => g.rows)
      .find((row) => row.quantity.startsWith('Temperature, ESP-UCD'))!
    expect(ucd).toMatchObject({ value: '1,417', uncertainty: '± 98', unit: 'K' })
    expect(ucd.notes).toEqual(["Quality flag flags_espucd = 20: the lowest of ESP-UCD's three quality classes"])
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
    expect(catalogueName(r, 'WISE 0855-0714')).toBe('WISEA J085510.74-071442.5')
  })

  it('RW Aurigae: the brighter star of the pair, titled as itself, with the system named', () => {
    const r = ANSWERS.rwaur
    expect(r.gaia!.source_id).toBe('156430822114424576')
    expect(cardTitle(r, 'RW Aurigae')).toBe('RW Aurigae A')
    expect(catalogueName(r, 'RW Aurigae')).toBeNull()
    expect(systemLine(r, 'RW Aurigae')).toBe('It is one of the stars of RW Aurigae, the system you chose. SIMBAD lists 828 papers that mention the system.')
    expect(partOfSentence(r, 'RW Aurigae')).toBeNull()
    expect(partOfSentence(r)).toBe('SIMBAD lists it as part of RW Aurigae.')
    expect(kindSentence(r)).toBe('SIMBAD lists it as an Orion variable: a young star whose brightness changes unevenly.')
    expect(blurSentences(r)).toEqual(['This blur holds 2 catalogued stars, not one: RW Aurigae B, fainter, is 1.5 arcseconds away.'])
    // A's own parallax, RUWE 1.50: rounded to two figures, no "give or take", the poor fit said.
    expect(beginnerFacts(r)[0].text).toBe(
      "It is about 510 light-years away. The light we see left it 510 years ago. Gaia's fit for it is poor (often a sign of a close pair), so this distance is less sure.",
    )
    expect(beginnerFacts(r).at(-1)!.text).toBe('SIMBAD lists 45 scientific papers that mention it.')
    const rows = expertGroups(r).flatMap((g) => g.rows)
    expect(rows.some((row) => row.quantity === 'Caution: RUWE above 1.4' && row.value === '1.50')).toBe(true)
    expect(rows.find((row) => row.quantity === 'Part of RW Aur')).toMatchObject({ value: '828', unit: 'papers' })
    expect(lookTarget(r, 'RW Aurigae')).toMatchObject({ name: 'RW Aurigae A', ra: r.gaia!.resolve_position.ra })
  })

  it('R Draconis: no disc, and the two faint sources beside it may not be real', () => {
    const r = ANSWERS.rdra
    expect(cardTitle(r)).toBe('R Draconis')
    expect(kindSentence(r)).toBe('SIMBAD lists it as a Mira variable: a cool giant star that swells and shrinks over many months.')
    expect(r.portrait.temperature).toBeNull()
    expect(pictureNotes(r)).toEqual([])
    expect(blurSentences(r)).toEqual([
      'Gaia lists 2 faint sources in the same pixel.',
      'They may not be real: Gaia often lists false ones beside very bright stars.',
    ])
    expect(beginnerFacts(r).map((f) => f.source)).toEqual(['Gaia', 'Gaia', 'SIMBAD'])
    expect(beginnerFacts(r)[0].text).toBe('It is about 2,610 light-years away, give or take 140. The light we see left it 2,610 years ago.')
    const g = expertGroups(r)
      .flatMap((x) => x.rows)
      .find((row) => row.quantity.startsWith('G magnitude'))!
    expect(g.notes[0]).toMatch(/variable: this error comes from the spread of its single measurements/)
  })

  it('a press 2.6 arcsec off R Draconis is still R Draconis', () => {
    const r = PRESSES.rdra_offset
    expect(cardTitle(r)).toBe('R Draconis')
    expect(r.choice?.how).toBe('light')
    expect(blurSentences(r)[1]).toBe('They may not be real: Gaia often lists false ones beside very bright stars.')
  })

  it('an ordinary faint star with no name: Gaia’s two radius models, and the uncorrected parallax offset', () => {
    const r = ANSWERS.faint
    expect(cardTitle(r)).toBe(NO_NAME)
    expect(kindSentence(r)).toBe('Gaia lists it, but no catalogue we asked says what kind of object it is.')
    expect(beginnerFacts(r).map((f) => f.text)[2]).toBe("Gaia's two models put its width at 0.89 to 1.2 times the Sun's. The picture uses 1.2.")
    expect(beginnerFacts(r)).toHaveLength(4) // no SIMBAD entry, so nothing on how well studied
    expect(disagreements(r)).toEqual(["Gaia's radius estimates disagree by 30%: FLAME 1.158, GSP-Phot 0.8916 solar radii. The picture uses FLAME."])
    expect(r.notes.some((n) => n.includes('about 4% closer'))).toBe(true)
  })

  it('the candidate place: nothing listed, how far we looked, and what is nearest', () => {
    const r = ANSWERS.candidate
    expect(cardTitle(r)).toBe(NOTHING_TITLE)
    expect(kindSentence(r)).toBeNull()
    expect(beginnerFacts(r)).toEqual([])
    expect(pictureNotes(r)).toEqual([])
    expect(nothingFoundLines(r)).toEqual([
      'We looked within 4 arcseconds of the place: two-thirds of a SPHEREx pixel. An arcsecond is 1/3600 of a degree.',
      'The nearest catalogued thing is Gaia DR3 5964332607636528768, 4.9 arcseconds away, inside the same SPHEREx pixel.',
      'Gaia measures it as too faint to see without a telescope and much redder than the Sun.',
    ])
    expect(lookTarget(r)).toEqual({ ra: 253.18038, dec: -44.67697, pmra: null, pmdec: null, parallax: null, name: null })
  })

  it('"Look at this one" hands back the place at 2026.0 and the motion', () => {
    expect(lookTarget(ANSWERS.barnard, "Barnard's Star")).toMatchObject({
      ra: ANSWERS.barnard.gaia!.resolve_position.ra,
      dec: ANSWERS.barnard.gaia!.resolve_position.dec,
      pmra: -801.5509783684709,
      pmdec: 10362.394206546573,
      parallax: 546.975939730948,
      name: "Barnard's Star",
    })
    expect(lookTarget(ANSWERS.wise0855)).toMatchObject({ pmra: -8123.7, pmdec: 673.2, parallax: 439 })
  })
})

describe('the picture in words, for a screen reader', () => {
  it("Barnard's Star: colour, size beside the Sun, and what is not drawn", () => {
    const r = ANSWERS.barnard
    const layout = portraitLayout({ temperatureK: temperatureForPicture(r), radiusRsun: 0.2021641731262207, label: "Barnard's Star" })
    expect(pictureDescription(r, layout)).toBe(
      "Illustration drawn from measurements, not a photograph. Barnard's Star as an orange disc, the colour of a perfect glowing body at 3,100 kelvin, 0.20 times the Sun's width, beside the Sun (white with a warm tint) to scale. Not drawn: its 4 planets, surface details.",
    )
  })
})

describe('a catalogue that did not answer', () => {
  it('says what is not known right now, rather than "not in the catalogues"', () => {
    const r = copy(ANSWERS.barnard)
    r.gaia = null
    r.unreachable = ['Gaia DR3']
    r.services.gaia = { ...r.services.gaia, answered: false, via: null }
    r.portrait = { temperature: null, radius: null, luminosity: null }
    r.derived = { from: null, distance: null, distance_estimate: null, motion: null, speed: null }
    expect(notKnownLine(r)).toBe(
      'Not in the catalogues we asked: its surface details. Not known right now, because Gaia DR3 did not answer: its temperature, its size, its distance, or its motion. SIMBAD lists 4 planets around it; their sizes are not in the catalogues we asked.',
    )
  })
  it('SIMBAD down: says SIMBAD did not answer instead of "no catalogue says what kind"', () => {
    const r = copy(ANSWERS.faint)
    r.unreachable = ['SIMBAD']
    r.services.simbad = { ...r.services.simbad, answered: false, via: null }
    expect(kindSentence(r)).toBe('SIMBAD, which says what kind of object things are, did not answer just now.')
    expect(cardTitle(r)).toBe('An object Gaia lists')
  })
  it('SIMBAD down at the candidate place: what Gaia has is still shown', () => {
    const r = copy(ANSWERS.candidate)
    r.nothing_catalogued = null
    r.unreachable = ['SIMBAD']
    r.services.simbad = { ...r.services.simbad, answered: false, via: null }
    const lines = nothingFoundLines(r)
    expect(lines[0]).toBe('Gaia lists nothing within 4 arcseconds of the place. SIMBAD did not answer, so whether it lists anything here is not known.')
    expect(lines[1]).toContain('The nearest catalogued thing is Gaia DR3 5964332607636528768')
    expect(cardTitle(r)).toBe('This place')
  })
})

describe('reading level', () => {
  const BANNED = /\b(parallax|proper motion|effective temperature|magnitude|spectral type)\b/i
  const NAMES: Record<string, string | undefined> = { barnard: "Barnard's Star", rwaur: 'RW Aurigae', wise0855: 'WISE 0855-0714' }
  it.each(Object.keys({ ...ANSWERS, ...PRESSES }))('%s: sentences of 20 words or fewer, without unexplained jargon', (key) => {
    const r = { ...ANSWERS, ...PRESSES }[key]
    for (const s of beginnerSentences(r, NAMES[key])) {
      expect(s.split(/\s+/).filter(Boolean).length, s).toBeLessThanOrEqual(20)
      expect(s, s).not.toMatch(BANNED)
      expect(s, s).not.toMatch(/degrees \(kelvin\)|teff_|radius_flame|T1V|eps Ind/)
    }
  })
  it("the brief's own phrase for a body too cool to glow is kept word for word", () => {
    expect(TOO_COOL).toBe('too cool to glow in light our eyes can see: it shines in infrared, which is why SPHEREx can see it')
  })
  it('a body below 800 K: dark, with the brief\'s phrase', () => {
    const r = copy(ANSWERS.wise0855)
    r.portrait.temperature = {
      key: 'mesFe_h.teff', label: 'Temperature', value: 285, error: null, lower: null, upper: null, unit: 'K', catalogue: 'SIMBAD',
      column: 'mesFe_h.teff', error_column: null, range_columns: null, reference: null, note: null, flags: null, model: false,
    }
    expect(colourDrawn(r)).toBe('dark')
    expect(beginnerFacts(r)[1].text).toContain(`That is ${TOO_COOL}.`)
  })
})
