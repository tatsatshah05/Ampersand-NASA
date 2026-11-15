// Beginner's words in the six tool panels, checked on real saved answers of the server for four
// objects (src/fixtures/tools, saved 14 Nov 2026 from the requests the page makes; the larger
// answers keep every field of every entry, but drop entries the words do not use: brightness
// points with no value to compare beyond three overexposed ones per band, and most spectrum
// points without a clean measurement. Verdicts, counts and numbers are those of the full answers.)
import { describe, expect, it } from 'vitest'
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
  measureCautions,
  plainMeasure,
  searchItem,
  searchResult,
  shareWords,
  smallBodiesResult,
  spectrumResult,
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

/** Every Beginner sentence for one object, from every tool. */
const allWords = (o: (typeof OBJECTS)[keyof typeof OBJECTS]) => [
  ...brightnessResult(o.lc),
  ...measureCautions(o.lc),
  ...spectrumResult(o.sp),
  ...measureCautions(o.sp),
  ...searchResult(o.se),
  ...o.se.objects.map(searchItem),
  ...distantResult(o.di),
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
  it("Barnard's Star: too bright to measure directly, and its outer light did not change beyond the error", () => {
    expect(brightnessResult(OBJECTS["Barnard's Star"].lc)).toEqual([
      'It is too bright to measure directly: 350 of its 364 photos are overexposed.',
      'So we measured the light just around it, which showed no change bigger than the measuring error.',
    ])
    expect(plainMeasure(OBJECTS["Barnard's Star"].lc)).toBe('wing')
  })
  it('RW Aurigae: about 1.6 times as bright in the shortest colours and half as bright around it in the longest, September to September', () => {
    expect(brightnessResult(OBJECTS['RW Aurigae'].lc)).toEqual([
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
    expect(measureCautions(OBJECTS['Serpens South'].lc)).toContain('No catalogued star is listed exactly here, so we measured the same spot in every photo.')
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
  it('how much, in words', () => {
    expect(brighterWords([1.64])).toBe('about 1.6 times as bright')
    expect(brighterWords([1.12])).toBe('about 12 per cent brighter')
    expect(brighterWords([4.5, 13.35])).toBe('about 4.5 to 13 times as bright')
    expect(brighterWords([1.1, 2])).toBe('up to about 2 times as bright')
    expect(fainterWords([0.52, 0.56])).toBe('about half as bright')
    expect(fainterWords([0.9])).toBe('about 10 per cent fainter')
    expect(fainterWords([0.3, 0.5])).toBe('about a third to half as bright')
    expect(colourWords([1])).toBe("SPHEREx's shortest infrared colours")
    expect(colourWords([3, 6])).toBe("SPHEREx's middle and longest infrared colours")
  })
})

describe('Colours: only what the tool states', () => {
  it('counts of photos measured, overexposed and spoiled, from the answer’s own counts', () => {
    expect(spectrumResult(OBJECTS["Barnard's Star"].sp)).toEqual(['4 of its 354 photos could be measured.', '350 were overexposed, because it is too bright there.'])
    expect(spectrumResult(OBJECTS['RW Aurigae'].sp)).toEqual([
      '131 of its 326 photos could be measured.',
      '167 were overexposed, because it is too bright there.',
      '28 had a bad pixel or another problem.',
    ])
    expect(spectrumResult(OBJECTS['WISE 0855'].sp)).toEqual(['196 of its 258 photos could be measured.', '62 had a bad pixel or another problem.'])
    expect(spectrumResult(OBJECTS['Serpens South'].sp)).toEqual([
      '286 of its 395 photos could be measured.',
      '11 were overexposed, because it is too bright there.',
      '98 had a bad pixel or another problem.',
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
    expect(OBJECTS["Barnard's Star"].se.objects.map(searchItem)).toEqual(['Moved. Already known. Has warning signs, so take care.'])
  })
  it('Serpens South: four changed brightness, one known, three only candidates, with what would confirm them', () => {
    expect(searchResult(OBJECTS['Serpens South'].se)).toEqual([
      'It tested 106 points of light in this patch.',
      'Nothing moved, and 4 things changed brightness.',
      '1 is already known in star catalogues.',
      '3 are not listed as changing in any catalogue we asked, so each is only a candidate.',
      'Another telescope, or SPHEREx’s next visits, would be needed to confirm them.',
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
    expect(distantResult(OBJECTS["Barnard's Star"].di)).toEqual([
      'Nothing here jumps the way a far-off planet would.',
      'The faintest planet it could catch is about as bright as WISE 0855.',
      'At best it could catch one that faint in about half of this picture.',
      DISTANT_ELSEWHERE,
    ])
  })
  it('WISE 0855: its own field reaches half its brightness, over two thirds of the picture', () => {
    expect(distantResult(OBJECTS['WISE 0855'].di).slice(1, 3)).toEqual([
      'The faintest planet it could catch is only half as bright as WISE 0855.',
      'At best it could catch one that faint in about two thirds of this picture.',
    ])
  })
  it('Serpens South: a bright, nebulous field, so the limit is far brighter', () => {
    // 4.0 mJy at best: nebulous fields reach 0.5 to 4 mJy in one visit (CLAUDE.md, "Distant-world search").
    expect(distantResult(OBJECTS['Serpens South'].di)[1]).toBe('The faintest planet it could catch is about 9 times as bright as WISE 0855.')
  })
  it('the words of the limit', () => {
    expect(faintWords(0.183)).toBe('only half as bright as WISE 0855')
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
      'The faintest planet it could catch is only half as bright as WISE 0855.',
      'At best it could catch one that faint in about two thirds of this picture.',
    ])
  })
})

describe('Asteroids: how many known ones crossed, and that they are known', () => {
  it("Barnard's Star, WISE 0855 and Serpens South: none", () => {
    expect(smallBodiesResult(OBJECTS["Barnard's Star"].sb)).toEqual(['No known asteroid or comet was in this patch during any of the 62 photos we checked.'])
    expect(smallBodiesResult(OBJECTS['WISE 0855'].sb)).toEqual(['No known asteroid or comet was in this patch during any of the 45 photos we checked.'])
    expect(smallBodiesResult(OBJECTS['Serpens South'].sb)).toEqual(['No known asteroid or comet was in this patch during any of the 67 photos we checked.'])
  })
  it('RW Aurigae: one known asteroid in three photos, too faint to show', () => {
    expect(smallBodiesResult(OBJECTS['RW Aurigae'].sb)).toEqual([
      '1 known asteroid crossed this patch, in 3 photos.',
      'It is already known, and NASA predicts where it is.',
      'It does not show in these photos: too faint here, or a little off.',
    ])
  })
})

describe('Other telescopes', () => {
  it('says which survey and when, and the size of the patch against the Moon', () => {
    expect(contextResult('wise', 0.1)).toEqual([
      'WISE took these in 2010 and 2011, long before SPHEREx, so they show what was here before.',
      'The orange square is 0.1 degrees across, about a fifth of the width of the full Moon.',
    ])
    expect(contextResult('dss', 0.5)[1]).toBe('The orange square is 0.5 degrees across, about the width of the full Moon.')
  })
})
