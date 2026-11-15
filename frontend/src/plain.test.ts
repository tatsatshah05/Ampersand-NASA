// Beginner's words in the six tool panels, checked on real saved answers of the server for four
// objects (src/fixtures/tools, saved 14 Nov 2026 from the requests the page makes; the larger
// answers keep every field of every entry, but drop entries the words do not use: brightness
// points with no value to compare beyond three overexposed ones per band, and most spectrum
// points without a clean measurement. Verdicts, counts and numbers are those of the full answers.)
import { describe, expect, it } from 'vitest'
import type { FramesReady } from './api'
import { summarise, type LightcurveResponse } from './lightcurve'
import type { SpectrumResponse } from './spectrum'
import type { SearchResult } from './search'
import type { DistantResult } from './distant'
import type { SmallBodiesResponse } from './smallbodies'
import {
  BRIGHTNESS_INTRO,
  BRIGHTNESS_LOADING,
  CONTEXT_INTRO,
  CONTEXT_TITLE,
  DISTANT_ELSEWHERE,
  DISTANT_INTRO,
  DISTANT_WAITING,
  OVEREXPOSED_MEANS,
  SCIENCE_FOLD,
  SCIENCE_WORDS,
  SEARCH_INTRO,
  SEARCH_WAITING,
  SMALLBODIES_INTRO,
  SMALLBODIES_LOADING,
  SPECTRUM_INTRO,
  SPECTRUM_LOADING,
  SPECTRUM_SPOT_ASK,
  SURVEY_WORDS,
  bandCaption,
  bandVerdicts,
  brightnessAxis,
  brightnessResult,
  brighterWords,
  colourWords,
  contextResult,
  crossingWords,
  distantResult,
  faintWords,
  fainterWords,
  photosOfIt,
  measureCautions,
  plainMeasure,
  searchItem,
  searchResult,
  shareWords,
  smallBodiesResult,
  spectrumResult,
  thenAndNow,
} from './plain'
import barnardLc from './fixtures/tools/barnard_lightcurve.json'
import rwaurLc from './fixtures/tools/rwaur_lightcurve.json'
import wiseLc from './fixtures/tools/wise0855_lightcurve.json'
import serpLc from './fixtures/tools/serpsouth_lightcurve.json'
import barnardSp from './fixtures/tools/barnard_spectrum.json'
import rwaurSp from './fixtures/tools/rwaur_spectrum.json'
import wiseSp from './fixtures/tools/wise0855_spectrum.json'
import serpSp from './fixtures/tools/serpsouth_spectrum.json'
import barnardSe from './fixtures/tools/barnard_search.json'
import rwaurSe from './fixtures/tools/rwaur_search.json'
import wiseSe from './fixtures/tools/wise0855_search.json'
import serpSe from './fixtures/tools/serpsouth_search.json'
import barnardDi from './fixtures/tools/barnard_distant.json'
import rwaurDi from './fixtures/tools/rwaur_distant.json'
import wiseDi from './fixtures/tools/wise0855_distant.json'
import serpDi from './fixtures/tools/serpsouth_distant.json'
import barnardSb from './fixtures/tools/barnard_smallbodies.json'
import rwaurSb from './fixtures/tools/rwaur_smallbodies.json'
import wiseSb from './fixtures/tools/wise0855_smallbodies.json'
import serpSb from './fixtures/tools/serpsouth_smallbodies.json'
// Three more brightness answers (saved 15 Nov 2026, trimmed the same way): the two novae, whose
// bands compared different visits and changed in opposite directions, and R Draconis, every
// photo of which is overexposed.
import v462Lc from './fixtures/tools/v462lup_lightcurve.json'
import barnardFrames from './fixtures/frames/barnard_d5.json'
import barnardRequestFrames from './fixtures/frames/barnard_request_d5.json'
import rwaurFrames from './fixtures/frames/rwaur_request_d5.json'
import v572Lc from './fixtures/tools/v572vel_lightcurve.json'
import rdraLc from './fixtures/tools/rdra_lightcurve.json'

const lc = (f: unknown) => f as LightcurveResponse
const sp = (f: unknown) => f as SpectrumResponse
const se = (f: unknown) => (f as { result: SearchResult }).result
const di = (f: unknown) => (f as { result: DistantResult }).result
const sb = (f: unknown) => f as SmallBodiesResponse

const OBJECTS = {
  "Barnard's Star": { lc: lc(barnardLc), sp: sp(barnardSp), se: se(barnardSe), di: di(barnardDi), sb: sb(barnardSb) },
  'RW Aurigae': { lc: lc(rwaurLc), sp: sp(rwaurSp), se: se(rwaurSe), di: di(rwaurDi), sb: sb(rwaurSb) },
  'WISE 0855': { lc: lc(wiseLc), sp: sp(wiseSp), se: se(wiseSe), di: di(wiseDi), sb: sb(wiseSb) },
  'Serpens South': { lc: lc(serpLc), sp: sp(serpSp), se: se(serpSe), di: di(serpDi), sb: sb(serpSb) },
}

const NOVAE = { 'V462 Lupi': lc(v462Lc), 'V572 Velorum': lc(v572Lc), 'R Draconis': lc(rdraLc) }

/** Every Beginner sentence for one object, from every tool. */
const allWords = (o: (typeof OBJECTS)[keyof typeof OBJECTS]) => [
  ...brightnessResult(o.lc),
  ...measureCautions(o.lc),
  ...spectrumResult(o.sp),
  ...measureCautions(o.sp),
  ...searchResult(o.se),
  ...o.se.objects.map(searchItem),
  ...distantResult(o.di, 0.1),
  ...smallBodiesResult(o.sb),
  ...o.sb.bodies.map(crossingWords),
  ...Object.keys(SURVEY_WORDS).flatMap((id) => contextResult(id, 0.1)),
]
const FIXED = [
  BRIGHTNESS_INTRO,
  BRIGHTNESS_LOADING,
  SPECTRUM_INTRO,
  SPECTRUM_LOADING,
  SPECTRUM_SPOT_ASK,
  SEARCH_INTRO,
  SEARCH_WAITING,
  DISTANT_INTRO,
  DISTANT_WAITING,
  DISTANT_ELSEWHERE,
  SMALLBODIES_INTRO,
  SMALLBODIES_LOADING,
  CONTEXT_INTRO,
  CONTEXT_TITLE,
  SCIENCE_FOLD,
  brightnessAxis('flux'),
  brightnessAxis('wing'),
  ...[1, 2, 3, 4, 5, 6].map(bandCaption),
  ...Object.values(SURVEY_WORDS).flatMap((s) => [s.label, s.sentence]),
]

const BANNED = SCIENCE_WORDS
const sentences = (text: string[]) => text.flatMap((p) => p.split(/(?<=[.!?])\s+/)).filter(Boolean)
const words = (s: string) => s.split(/\s+/).filter(Boolean).length

describe('every Beginner sentence of the six tools', () => {
  for (const [name, o] of Object.entries(OBJECTS)) {
    it(`${name}: no scientist's word, no "discovery", no "new planet"`, () => {
      for (const t of allWords(o)) {
        expect(t).not.toMatch(BANNED)
        expect(t).not.toMatch(/discover|new planet|new find/i)
      }
    })
    it(`${name}: no sentence longer than 20 words`, () => {
      for (const s of sentences(allWords(o))) expect(words(s), s).toBeLessThanOrEqual(20)
    })
  }
  for (const [name, data] of Object.entries(NOVAE)) {
    it(`${name}: its brightness words, no scientist's word and no sentence over 20 words`, () => {
      for (const t of [...brightnessResult(data), ...measureCautions(data)]) {
        expect(t).not.toMatch(BANNED)
        expect(t).not.toMatch(/discover|new planet|new find/i)
      }
      for (const s of sentences(brightnessResult(data))) expect(words(s), s).toBeLessThanOrEqual(20)
    })
  }
  it('the fixed words too', () => {
    for (const t of FIXED) expect(t).not.toMatch(BANNED)
    for (const s of sentences(FIXED)) expect(words(s), s).toBeLessThanOrEqual(20)
  })
  it('every intro is at most two sentences', () => {
    for (const t of [BRIGHTNESS_INTRO, SPECTRUM_INTRO, SEARCH_INTRO, DISTANT_INTRO, SMALLBODIES_INTRO, CONTEXT_INTRO]) {
      expect(sentences([t]).length).toBeLessThanOrEqual(2)
    }
  })
})

describe('Brightness: the tool’s own same-colour comparison', () => {
  it("Barnard's Star: too bright to measure directly, and its outer light shows no clear change (the tool's own verdict)", () => {
    // 354 photos show it: the other 10 of the answer's 364 have it off the edge. The colour panel counts the same 354.
    expect(brightnessResult(OBJECTS["Barnard's Star"].lc)).toEqual([
      '350 of its 354 photos are overexposed: it is too bright there to measure directly.',
      OVEREXPOSED_MEANS,
      'So we measured the light just around it, which showed no clear change between its visits.',
    ])
    expect(plainMeasure(OBJECTS["Barnard's Star"].lc)).toBe('wing')
  })
  it('RW Aurigae: about 1.6 times as bright in the shortest colours and half as bright around it in the longest, September to September', () => {
    expect(brightnessResult(OBJECTS['RW Aurigae'].lc)).toEqual([
      '167 of its 326 photos are overexposed: it is too bright there to measure directly.',
      OVEREXPOSED_MEANS,
      'It changed between September 2025 and September 2026.',
      "In SPHEREx's shortest infrared colours it became about 1.6 times as bright.",
      "In SPHEREx's longest infrared colours the light just around it became about half as bright.",
      'Where it is overexposed, we measured the light in a ring just around it.',
    ])
    // The chart shows the measured brightness, as Expert does by default.
    expect(plainMeasure(OBJECTS['RW Aurigae'].lc)).toBe('flux')
  })
  it('Serpens South: brighter by about 4.5 to 13 times in the middle and longest colours, and the spot is measured in place', () => {
    expect(brightnessResult(OBJECTS['Serpens South'].lc)).toEqual([
      'It got brighter between September 2025 and September 2026.',
      "In SPHEREx's middle and longest infrared colours it became about 4.5 to 13 times as bright.",
    ])
    // Only what was checked: no Gaia star to follow within 3 arcseconds (G < 17). Other catalogues
    // do list an object here (the search panel names it), so "no catalogued star" would be false.
    expect(measureCautions(OBJECTS['Serpens South'].lc)).toContain('Gaia lists no star bright enough to follow within 3 arcseconds, so we measured one fixed spot.')
    expect(measureCautions(OBJECTS['Serpens South'].lc).join(' ')).not.toMatch(/no catalogued star/i)
  })
  it('WISE 0855: too few photos of the same colour in two visits, and the nearby star’s light is in the numbers', () => {
    expect(brightnessResult(OBJECTS['WISE 0855'].lc)).toEqual(['Too few photos caught the same infrared colour in two visits, so no change can be judged.'])
    expect(measureCautions(OBJECTS['WISE 0855'].lc)).toEqual(['Another star is so close that its light is mixed into these numbers.'])
  })
  it('RW Aurigae keeps its blend caution (its companion 1.6 arcseconds away)', () => {
    expect(measureCautions(OBJECTS['RW Aurigae'].lc)).toEqual(['Another star is so close that its light is mixed into these numbers.'])
  })
  it('every factor said is the median change of the tool’s own table, and only for a band the rule calls changed', () => {
    for (const o of Object.values(OBJECTS)) {
      const verdicts = bandVerdicts(o.lc)
      for (const v of verdicts) {
        const own = summarise(o.lc, v.measure).find((s) => s.detector === v.detector)
        expect(own?.medianChange).toBe(v.medianChange)
        expect(own?.verdict).toBe(v.verdict)
      }
    }
    // Serpens South: bands 3 to 6 brighter by 4.79, 13.35, 6.30 and 4.50 times; band 2 has two bins only, so it is not said.
    const serp = bandVerdicts(OBJECTS['Serpens South'].lc)
    expect(serp.filter((v) => v.verdict === 'brighter').map((v) => v.detector)).toEqual([3, 4, 5, 6])
    expect(serp.find((v) => v.detector === 2)?.verdict).toBe('too few bins')
  })
  it('V462 Lupi: the bands that compared other visits get their own months, and the fading is said in good English', () => {
    expect(brightnessResult(NOVAE['V462 Lupi'])).toEqual([
      'It got fainter between its visits.',
      "Between July 2025 and July 2026, the light just around it got fainter in SPHEREx's longest infrared colours.",
      'The light just around it became less than a tenth as bright there.',
      "Between February and July 2026, it got fainter in SPHEREx's shortest and middle infrared colours.",
      'It became about an eighth to a quarter as bright there.',
      'Where it is overexposed, we measured the light in a ring just around it.',
    ])
    expect(brightnessResult(NOVAE['V462 Lupi']).join(' ')).not.toMatch(/about less than/)
  })
  it('V572 Velorum: brighter and fainter are never said of one colour group without their own months, and no factor from near the noise', () => {
    const said = brightnessResult(NOVAE['V572 Velorum'])
    expect(said).toEqual([
      '241 of its 473 photos are overexposed: it is too bright there to measure directly.',
      OVEREXPOSED_MEANS,
      'It changed between its visits.',
      'Between June 2025 and June 2026, it got brighter in bands 2, 5 and 6.',
      'It became at least 14 times as bright there.',
      'Between December 2025 and June 2026, it got fainter in band 1.',
      'It became about a sixth as bright there.',
    ])
    // Bands 5 and 6 rose by 665 and 1408 times over a level near the noise: no such number is said.
    expect(said.join(' ')).not.toMatch(/\b(665|1408|1,408)\b/)
  })
  it('R Draconis: every photo overexposed, the same total as its colour panel', () => {
    expect(brightnessResult(NOVAE['R Draconis']).slice(0, 3)).toEqual([
      'All 496 of its photos are overexposed: it is too bright to measure directly.',
      OVEREXPOSED_MEANS,
      'It got fainter between June 2025 and May 2026.',
    ])
  })
  it('both panels count the same photos of an object', () => {
    for (const o of Object.values(OBJECTS)) expect(photosOfIt(o.lc)).toBe(o.sp.n_exposures)
  })
  it('how much, in words', () => {
    expect(brighterWords([1.64])).toBe('about 1.6 times as bright')
    expect(brighterWords([1.12])).toBe('about 12 per cent brighter')
    expect(brighterWords([4.5, 13.35])).toBe('about 4.5 to 13 times as bright')
    expect(brighterWords([1.1, 2])).toBe('up to about 2 times as bright')
    expect(fainterWords([0.52, 0.56])).toBe('about half as bright')
    expect(fainterWords([0.9])).toBe('about 10 per cent fainter')
    expect(fainterWords([0.3, 0.5])).toBe('about a third to half as bright')
    // Below a tenth: never "about less than a tenth".
    expect(fainterWords([0.02])).toBe('less than a tenth as bright')
    expect(fainterWords([0.04, 0.25])).toBe('less than a tenth to about a quarter as bright')
    // The nearest simple fraction: 0.6 is nearer two thirds than half, 0.4 nearer a third.
    expect(fainterWords([0.6])).toBe('about two thirds as bright')
    expect(fainterWords([0.4])).toBe('about a third as bright')
    // From 20 times up, no factor.
    expect(brighterWords([14.4, 665, 1408])).toBe('at least 14 times as bright')
    expect(brighterWords([30, 1408])).toBe('many times as bright')
    expect(colourWords([1])).toBe("SPHEREx's shortest infrared colours")
    expect(colourWords([3, 6])).toBe("SPHEREx's middle and longest infrared colours")
  })
})

describe('Colours: only what the tool states', () => {
  it('counts of photos measured, overexposed and spoiled, from the answer’s own counts', () => {
    // Nearly all overexposed: said so, with what the word means and where the 4 measured dots are (all at 3 micrometres or more).
    expect(spectrumResult(OBJECTS["Barnard's Star"].sp)).toEqual([
      "It is so bright that it dazzles SPHEREx's camera: 350 of its 354 photos are overexposed.",
      OVEREXPOSED_MEANS,
      'Only 4 could be measured: the dots on the right, in its longest colours.',
    ])
    expect(spectrumResult(OBJECTS['RW Aurigae'].sp)).toEqual([
      '131 of its 326 photos could be measured.',
      '167 were overexposed, because it is too bright there.',
      '28 had a bad pixel or another problem.',
      OVEREXPOSED_MEANS,
    ])
    expect(spectrumResult(OBJECTS['WISE 0855'].sp)).toEqual(['196 of its 258 photos could be measured.', '62 had a bad pixel or another problem.'])
    expect(spectrumResult(OBJECTS['Serpens South'].sp)).toEqual([
      '286 of its 395 photos could be measured.',
      '11 were overexposed, because it is too bright there.',
      '98 had a bad pixel or another problem.',
      OVEREXPOSED_MEANS,
    ])
  })
  it('names no dip or bump: the tool names none', () => {
    for (const o of Object.values(OBJECTS)) expect(spectrumResult(o.sp).join(' ')).not.toMatch(/dip|bump|peak|line|ice|water|dust/i)
  })
})

describe('Find changes: counts, known, candidates', () => {
  it("Barnard's Star: one mover, already known", () => {
    expect(searchResult(OBJECTS["Barnard's Star"].se)).toEqual([
      'It tested 130 points of light in this patch.',
      '1 thing moved, and nothing changed brightness.',
      'It is already known in star catalogues.',
    ])
    // Its warning sign said as what it is, not as "take care".
    expect(OBJECTS["Barnard's Star"].se.objects.map(searchItem)).toEqual(['Moved. Already known. It is so bright that it overflows the camera, so its place is less exact.'])
  })
  it('Serpens South: four changed brightness, one known, three only candidates, with what would confirm them', () => {
    expect(searchResult(OBJECTS['Serpens South'].se)).toEqual([
      'It tested 106 points of light in this patch.',
      'Nothing moved.',
      // Two of the four have warning signs (one detector only, uncalibrated; one roll only): said as "may have".
      '2 things changed brightness, and 2 more may have: they have warning signs.',
      '1 is already known in star catalogues.',
      '3 are not listed as changing in any catalogue we asked, so each is only a candidate.',
      'Scientists may already have written about them: we did not search their papers.',
      'Another telescope, or SPHEREx’s next visits, would be needed to confirm them.',
    ])
    expect(OBJECTS['Serpens South'].se.objects.map(searchItem)).toEqual([
      'Changed brightness. Only a candidate.',
      'Changed brightness. Already known.',
      'May have changed brightness. Only a candidate. The computer could not check how exact this measurement is.',
      'May have changed brightness. Only a candidate. The computer could not check how exact this measurement is. It may be a reflection inside the telescope.',
    ])
  })
  it('RW Aurigae and WISE 0855: the known objects', () => {
    expect(searchResult(OBJECTS['RW Aurigae'].se)[1]).toBe('Nothing moved, and 1 thing changed brightness.')
    expect(searchResult(OBJECTS['WISE 0855'].se)[1]).toBe('1 thing moved, and nothing changed brightness.')
    expect(searchResult(OBJECTS['WISE 0855'].se)[2]).toBe('It is already known in star catalogues.')
  })
})

describe('Far-off planet: found or not, how faint, and nothing ruled out elsewhere', () => {
  it("Barnard's Star", () => {
    // The default picture is 0.1 degrees wide; the search covers 0.2 degrees, and only planets from 1,000 times the Earth-Sun distance.
    expect(distantResult(OBJECTS["Barnard's Star"].di, 0.1)).toEqual([
      'Nothing here jumps the way a far-off planet would.',
      'It can only catch one between 1,000 and 30,000 times as far from the Sun as Earth.',
      'A nearer planet would jump right out of the patch between visits.',
      'The faintest planet it could catch is about as bright as WISE 0855.',
      'At best it could catch one that faint in about half of the patch it searched.',
      'That patch is twice as wide as the picture.',
      DISTANT_ELSEWHERE,
    ])
    // A picture as wide as the patch: no second patch to speak of.
    expect(distantResult(OBJECTS["Barnard's Star"].di, 0.2)).not.toContain('That patch is twice as wide as the picture.')
  })
  it('WISE 0855: its own field reaches half its brightness, over two thirds of the picture', () => {
    expect(distantResult(OBJECTS['WISE 0855'].di, 0.1).slice(3, 5)).toEqual([
      'The faintest planet it could catch is about a third as bright as WISE 0855.',
      'At best it could catch one that faint in about two thirds of the patch it searched.',
    ])
  })
  it('Serpens South: a bright, nebulous field, so the limit is far brighter', () => {
    // 4.0 mJy at best: nebulous fields reach 0.5 to 4 mJy in one visit (CLAUDE.md, "Distant-world search").
    expect(distantResult(OBJECTS['Serpens South'].di)[3]).toBe('The faintest planet it could catch is about 9 times as bright as WISE 0855.')
  })
  it('the words of the limit', () => {
    // 0.183 mJy is 0.41 of WISE 0855's 0.45: nearer a third than half.
    expect(faintWords(0.183)).toBe('about a third as bright as WISE 0855')
    expect(faintWords(0.02)).toBe('less than a tenth as bright as WISE 0855')
    expect(faintWords(0.538)).toBe('about as bright as WISE 0855')
    expect(faintWords(1.7)).toBe('about 4 times as bright as WISE 0855')
    expect(shareWords(0.54)).toBe('half')
    expect(shareWords(0.64)).toBe('two thirds')
    expect(shareWords(0.18)).toBe('a fifth')
  })
  it('a candidate is never confirmed', () => {
    const r = { ...OBJECTS['WISE 0855'].di, status: 'candidates' as const, candidates: [{} as never] }
    expect(distantResult(r)).toEqual([
      'It found 1 candidate: something that jumps the way a far-off planet would.',
      'It is not confirmed: another telescope would have to see it in the same places.',
      'It can only catch one between 1,000 and 30,000 times as far from the Sun as Earth.',
      'A nearer planet would jump right out of the patch between visits.',
      'The faintest planet it could catch is about a third as bright as WISE 0855.',
      'At best it could catch one that faint in about two thirds of the patch it searched.',
    ])
  })
  it('the limit and the share of the picture always come from the same row of the table', () => {
    // A made-up table where the faintest limit and the widest cover are in different rows: the
    // share said is the faintest row's, never the widest row's.
    const base = OBJECTS["Barnard's Star"].di
    const row = base.limit[0]
    const r = { ...base, limit: [{ ...row, faintest_mjy: 0.2, share_of_picture: 0.2 }, { ...row, faintest_mjy: 0.9, share_of_picture: 0.75 }] }
    expect(distantResult(r).slice(3, 5)).toEqual([
      'The faintest planet it could catch is about half as bright as WISE 0855.',
      'At best it could catch one that faint in about a fifth of the patch it searched.',
    ])
  })
})

describe('Asteroids: how many known ones crossed, and that they are known', () => {
  it("Barnard's Star, WISE 0855 and Serpens South: none", () => {
    expect(smallBodiesResult(OBJECTS["Barnard's Star"].sb)).toEqual(['No known asteroid or comet was in this patch during any of the 62 photos we checked.'])
    expect(smallBodiesResult(OBJECTS['WISE 0855'].sb)).toEqual(['No known asteroid or comet was in this patch during any of the 45 photos we checked.'])
    expect(smallBodiesResult(OBJECTS['Serpens South'].sb)).toEqual(['No known asteroid or comet was in this patch during any of the 67 photos we checked.'])
  })
  it('when NASA did not answer every question, only the photos it answered for are spoken of', () => {
    const partial = { ...OBJECTS["Barnard's Star"].sb, problems: [{ what: 'one question was not answered' }] } as unknown as SmallBodiesResponse
    expect(smallBodiesResult(partial)).toEqual([
      'No known asteroid or comet was in this patch in the photos NASA answered for.',
      'NASA did not answer every question, so this list may be incomplete.',
    ])
  })
  it('RW Aurigae: one known asteroid in three photos, too faint to show', () => {
    expect(smallBodiesResult(OBJECTS['RW Aurigae'].sb)).toEqual([
      '1 known asteroid crossed this patch, in 3 photos.',
      'It is already known, and NASA predicts where it is.',
      'It does not show in these photos: too faint here, or a little off.',
    ])
  })
})

describe('What is it? Then and now, for an object that moves', () => {
  const frames = (f: unknown) => f as FramesReady
  it("Barnard's Star in the WISE picture: 2.7 arcminutes south of the square's middle, from its Gaia motion", () => {
    // Gaia DR3 at 2016.0 moved to 2010.5 (AllWISE's middle year) against the view's centre, its 2026 place.
    const b = frames(barnardFrames)
    expect(thenAndNow('wise', b.target, { ra: b.ra, dec: b.dec }, "Barnard's Star", 'beginner')).toEqual([
      "When this picture was taken, about 2010, Barnard's Star was about 2.7 arcminutes south of the square's middle.",
      "It has moved that far since then: about a tenth of the full Moon's width.",
      'SPHEREx sees it in the middle of the square.',
    ])
    expect(thenAndNow('wise', b.target, { ra: b.ra, dec: b.dec }, "Barnard's Star", 'expert')).toEqual([
      'At ~2010.5 the catalogue motion (10.39″/yr) puts the target 2.7′ from the field centre at PA 176°; at 2026.0 it is at the centre.',
    ])
    // The same from the motion the name lookup gives (at 2026.0, at the centre).
    const r = frames(barnardRequestFrames)
    expect(thenAndNow('wise', r.target, { ra: r.ra, dec: r.dec }, "Barnard's Star", 'beginner')[0]).toBe(
      "When this picture was taken, about 2010, Barnard's Star was about 2.7 arcminutes south of the square's middle.",
    )
  })
  it('nothing for a survey with no single year, an object with no motion, or one that barely moves', () => {
    const b = frames(barnardFrames)
    expect(thenAndNow('dss', b.target, { ra: b.ra, dec: b.dec }, "Barnard's Star", 'beginner')).toEqual([])
    expect(thenAndNow('wise', null, { ra: b.ra, dec: b.dec }, null, 'beginner')).toEqual([])
    const rw = frames(rwaurFrames)
    expect(thenAndNow('wise', rw.target, { ra: rw.ra, dec: rw.dec }, 'RW Aurigae', 'beginner')).toEqual([])
  })
  it('plain words, short sentences', () => {
    for (const f of [barnardFrames, barnardRequestFrames]) {
      const d = frames(f)
      for (const s of ['wise', '2mass']) {
        const lines = thenAndNow(s, d.target, { ra: d.ra, dec: d.dec }, 'Epsilon Indi B', 'beginner')
        for (const line of lines) expect(line).not.toMatch(BANNED)
        for (const line of sentences(lines)) expect(words(line), line).toBeLessThanOrEqual(20)
      }
    }
  })
})

describe('What is it? (the same patch through other telescopes)', () => {
  it('says which survey and when, and the size of the patch against the Moon', () => {
    expect(contextResult('wise', 0.1)).toEqual([
      'WISE took these in 2010 and 2011, long before SPHEREx, so they show what was here before.',
      'The orange square is 0.1 degrees across, about a fifth of the width of the full Moon.',
    ])
    expect(contextResult('dss', 0.5)[1]).toBe('The orange square is 0.5 degrees across, about the width of the full Moon.')
  })
})
