// The "Three tools" screen's words and rules (build spec section 13, and the methods' "do not say"
// lists in docs/reflex.md, docs/colourwalk.md and docs/transits.md).
import { describe, expect, it } from 'vitest'
import colourFile from '../public/lab/colourwalk.json'
import reflexFile from '../public/lab/reflex.json'
import transitFile from '../public/lab/transits.json'
import {
  binFolded,
  colourView,
  fill,
  fold,
  fractionWords,
  halfWord,
  isToolsAddress,
  monthsOf,
  otherVisitsPhrase,
  powerOfTen,
  rangeSentence,
  reflexView,
  screenDirection,
  toolsAddress,
  toolsBackAddress,
  transitView,
  trapezoidDepth,
  yRange,
  type ColourFile,
  type ReflexFile,
  type TransitFile,
} from './tools'
import { PAGE, SCI, T1, T2, T3 } from './toolsWording'

// Vitest gives a stylesheet imported with ?raw back empty, so the file is read from disk.
const fsModule = 'node:fs'
const { readFileSync } = (await import(/* @vite-ignore */ fsModule)) as { readFileSync: (p: URL, encoding: string) => string }
const css = readFileSync(new URL('./components/ToolsView.css', import.meta.url), 'utf8')

// ---------------------------------------------------------------------------------- every string

/** A stand-in for any slot value: it reads as "7" wherever a sentence puts it. */
const SLOT: unknown = new Proxy(
  {},
  {
    get: (_, k) => (k === Symbol.toPrimitive || k === 'toString' ? () => '7' : '7'),
  },
)

function strings(x: unknown): string[] {
  if (typeof x === 'string') return [x]
  if (typeof x === 'function') return strings((x as (...a: unknown[]) => unknown)(...Array(Math.max(1, x.length)).fill(SLOT)))
  if (Array.isArray(x)) return x.flatMap(strings)
  if (x && typeof x === 'object') return Object.values(x).flatMap(strings)
  return []
}

const MAIN = { PAGE, T1, T2, T3 }
const main = strings(MAIN)
const sci = strings(SCI)
const everything = [...main, ...sci]

const sentences = (text: string) => text.split(/(?<=[.!?])\s+(?=[A-Z"(])/)
const words = (s: string) => s.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w))

const SCIENCE = ['sigma', 'signal to noise', 'S/N', 'flux', 'photometry', 'astrometry', 'ephemeris', 'epoch', 'detector', 'parallax', 'centroid', 'magnitude', 'micron', 'µm', 'arcsecond', 'pixel']
const NOWHERE = ['discovery', 'discovered', 'first', 'breakthrough']
const OLD_PHRASES = [
  'fits our measurement',
  'fits our readings',
  'tends to come out',
  'SPHEREx saw',
  'sections for red light',
  'the true figure is even lower',
  'less than no light',
  'a curve half as big',
  'small copy of the curve',
  'its own drift',
  'drifts on its own',
  'can be off by chance',
  'how far off the dot could be',
  'gives the most light',
  'white-hot',
  'patch of light',
  'waters down',
  'the stars left in',
  'takes the stars out',
  'made-up timetables',
  'one part in',
  'light sensors',
]

const hasWord = (text: string, w: string) => new RegExp(`(^|[^\\p{L}])${w.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}`, 'iu').test(text)

describe('the words', () => {
  it('has no main-screen sentence over 20 words', () => {
    const long = main.flatMap(sentences).filter((s) => words(s).length > 20)
    expect(long).toEqual([])
  })
  it('keeps the science words inside the For scientists fold-outs', () => {
    const found = main.filter((s) => SCIENCE.some((w) => hasWord(s, w)))
    expect(found).toEqual([])
    expect(sci.some((s) => hasWord(s, 'sigma') || s.includes('σ'))).toBe(true)
  })
  it('never says discovery, discovered, first or breakthrough, fold-outs included', () => {
    expect(everything.filter((s) => NOWHERE.some((w) => hasWord(s, w)))).toEqual([])
  })
  it('has none of the phrases revisions 1 and 2 were marked down for', () => {
    expect(everything.filter((s) => OLD_PHRASES.some((p) => s.toLowerCase().includes(p.toLowerCase())))).toEqual([])
  })
  it('says "curved" only of the Earth\'s path, and never "curve"', () => {
    expect(main.filter((s) => /\bcurve\b/i.test(s))).toEqual([])
    const curved = main.filter((s) => /\bcurved\b/i.test(s))
    expect(curved.length).toBeGreaterThan(0)
    expect(curved.every((s) => /Earth's path is curved|Earth's curved path/.test(s))).toBe(true)
  })
  it('never follows "patch" with "of light"', () => {
    expect(everything.filter((s) => /patch(es)? of light/i.test(s))).toEqual([])
  })
  it('says "very likely" only in the range sentence, which always ends "(about 19 chances in 20)"', () => {
    const vl = main.filter((s) => /very likely/i.test(s))
    expect(vl.length).toBeGreaterThan(0)
    for (const s of vl) {
      if (s === T1.rulerBand) continue // the ruler's band label names the same range
      expect(s).toMatch(/^The true answer is very likely .*\(about 19 chances in 20\)\.$/)
    }
  })
  it('says "new planet" only to say something is not one', () => {
    const np = everything.filter((s) => /new planet/i.test(s))
    expect(np.length).toBeGreaterThan(0)
    expect(np.every((s) => /^(Nothing on this screen is a new planet\.|This is not a new planet: )/.test(s))).toBe(true)
  })
  it("keeps to docs/reflex.md's do-not-say list", () => {
    const t1 = [...strings(T1), ...strings(SCI.t1), ...strings(PAGE)]
    for (const bad of ['without being told', 'Planet Nine search', 'finds Planet X', 'precise', '1 sigma 91', '6.8 sigma', '0.75 to 5', '50 to 400', 'V 19 for a grey', 'rate is measured', 'beats WISE', 'anywhere in the sky'])
      expect(t1.filter((s) => s.includes(bad))).toEqual([])
    // "6.8 sigma" never appears without the result with the earliest day left out.
    expect(strings(SCI.t1).some((s) => /left out, at least/.test(s))).toBe(true)
  })
  it("keeps to docs/colourwalk.md's do-not-say list", () => {
    const t2 = [...strings(T2), ...strings(SCI.t2)]
    for (const bad of ['candidate', 'exoplanet', 'size the method predicts', 'works blind', 'independent identification'])
      expect(t2.filter((s) => s.toLowerCase().includes(bad))).toEqual([])
    // The mass is only ever a value from other astronomers.
    expect(t2.filter((s) => /times as heavy as Jupiter/.test(s)).every((s) => s.startsWith('Other astronomers estimate'))).toBe(true)
  })
  it("keeps to docs/transits.md's do-not-say list", () => {
    const t3 = [...strings(T3), ...strings(SCI.t3)]
    for (const bad of ['blind', 'TOI-4055', 'exoplanet imaging', 'agree in colour', 'can find transiting planets'])
      expect(t3.filter((s) => s.toLowerCase().includes(bad.toLowerCase()))).toEqual([])
    expect(t3.filter((s) => /\bconfirmed planet|blend is ruled out/i.test(s))).toEqual([])
  })
  it('defines a square before using it, in each tool', () => {
    const t1 = [...T1.appear.count('7', '7', 'July 2025').split(' '), T1.appear.squares]
    expect(t1.join(' ')).toContain('tiny squares, like tiles')
    expect(T2.squares).toContain('tiny squares, like tiles')
  })
})

// ---------------------------------------------------------------------------------- the files on the screen

const reflex = reflexFile as unknown as ReflexFile
const colour = colourFile as unknown as ColourFile
const transit = transitFile as unknown as TransitFile
const clone = <T>(x: T): T => structuredClone(x)
const textOf = (v: unknown) => strings(JSON.parse(JSON.stringify(v))).join(' ')

describe('every slot is filled from the shipped files', () => {
  for (const [name, view] of [
    ['reflex', reflexView(reflex)],
    ['colourwalk', colourView(colour)],
    ['transits', transitView(transit)],
  ] as const) {
    it(`${name}: no undefined, NaN, braces or placeholders`, () => {
      const t = textOf(view)
      expect(t).not.toMatch(/undefined|NaN|[{}]|Infinity/)
      // "null" appears only in the fold-out's "null test" and its repeat command.
      expect(t).not.toMatch(/\bnull\b(?!\s(test|checks|field|vhs))/i)
    })
  }
  it('an empty file shows no number and no broken sentence', () => {
    // Fixed facts stay ("known since 2015"); no measured number, and nothing broken.
    for (const v of [reflexView({}), colourView({}), transitView({})]) {
      const t = textOf({ ...v, sci: [] })
      expect(t).not.toMatch(/undefined|NaN|[{}]|null/)
      expect(t).not.toMatch(/times as far|per cent|SPHEREx pictures\.|readings of/)
    }
  })
  it('tool 1 numbers come from the file: about 111, more than 76, NASA 95.6, 13 hours, then 118', () => {
    const v = reflexView(reflex)
    expect(v.numbers?.ours).toBe('Our tool: about 111 times as far from the Sun as the Earth is')
    // A lower bound is rounded down (76.5 → 76), so "more than" never claims more than the data.
    expect(v.numbers?.range[0]).toBe('The true answer is very likely more than 76 (about 19 chances in 20).')
    expect(v.numbers?.nasa).toBe("NASA's figure: 95.6")
    expect(v.after.flat().join(' ')).toContain('about 13 hours')
    expect(v.howSure.flat().join(' ')).toContain('put it at 118 times')
    expect(v.howSure.flat().join(' ')).toContain("NASA's figure is inside that run's range too: more than 52.")
    expect(v.chip).toBe(T1.chipFoundRough)
    expect(v.glance).toEqual({ ours: 'Our tool: about 111', known: 'NASA: 95.6', unit: T1.glance.unit })
  })
  it('tool 2 numbers come from the file, and its verdict is "not proven", first', () => {
    const v = colourView(colour)
    expect(v.chip).toBe('Not proven yet')
    expect(v.result).toEqual([T2.resultNotProven, T2.resultRight, T2.resultSmall])
    const t = [...v.test, ...v.howSure].flat().join(' ')
    for (const s of ['351 SPHEREx pictures', 'toward the lower right', 'about 3 centimetres', 'about 2 times our usual error', 'one time in 8', 'asks for 4 times', 'one and a third squares', 'not 2.7'])
      expect(t).toContain(s)
    expect(v.answerLine).toBe(T2.answerNothing)
    expect(v.glance).toEqual({ ours: 'The shift: about 2 times our usual error', known: 'Needed by our rule: 4 times', unit: null })
  })
  it('tool 3 numbers come from the file: 1.2 per cent, 0.6 to 1.7, published 1.23 (1.13 to 1.47)', () => {
    const v = transitView(transit)
    expect(v.numbers).toEqual({
      ours: 'Our tool: about 1.2 per cent',
      range: 'The true answer is very likely between 0.6 and 1.7 (about 19 chances in 20).',
      published: 'Published figure: 1.23 per cent',
      publishedRange: 'Published figures for this dip range from 1.13 to 1.47 per cent.',
    })
    const t = v.test.flat().join(' ')
    for (const s of ['every 4.4 days', 'almost 4 hours', 'about 8,300 pictures', '484 readings', 'Of these, 65', '29 different crossings', 'about 1.4 per cent']) expect(t).toContain(s)
    expect(v.chip).toBe(T3.chipOneMixed)
    expect(v.dialNote.flat()).toContain(T3.howSure.noneDid)
    expect(v.lead).toEqual([T3.oneOfBands('six'), T3.bigPlanet])
    // The depth is never shown without its give-or-take (docs/transits.md), the verdict row included.
    expect(v.glance?.ours).toBe('Our tool: about 1.2 per cent, give or take 0.5')
  })
  it('tools 1 and 3 use the same range sentence, fed about-95% ranges; a lower bound is rounded down', () => {
    expect(rangeSentence({ lo: 0.6, hi: 1.7 }, 1)).toBe(PAGE.rangeBetween('0.6', '1.7'))
    expect(rangeSentence({ lo: 76.5, hi: null })).toBe(PAGE.rangeAbove('76'))
    expect(rangeSentence({ lo: 76.99, hi: null })).toBe(PAGE.rangeAbove('76'))
  })
  it('never shows a backend answer or verdict sentence', () => {
    const f = clone(reflex) as ReflexFile & Record<string, unknown>
    ;(f.candidate as Record<string, unknown>).verdict = 'known distant body: known-answer, not a discovery'
    f.answer = '1 known distant body recovered blind(s)'
    const c = clone(colour) as ColourFile & Record<string, unknown>
    c.status = { chip: 'X', headline: 'backend headline' }
    const t = textOf(reflexView(f)) + textOf(colourView(c))
    expect(t).not.toContain('not a discovery')
    expect(t).not.toContain('recovered blind')
    expect(t).not.toContain('backend headline')
  })
})

// ---------------------------------------------------------------------------------- verdict sentences, each with its opposite case

describe('tool 1 verdicts', () => {
  const base = () => clone(reflex)
  const testOf = (f: ReflexFile) => reflexView(f).test.flat()
  const afterOf = (f: ReflexFile) => reflexView(f).after.flat()
  it('places the dot by its distance from NASA in squares', () => {
    const f = base()
    f.candidate!.separation_arcsec = 6
    expect(testOf(f)).toContain(T1.placeVeryClose)
    f.candidate!.separation_arcsec = 30
    const v = reflexView(f)
    expect(v.test.flat()).toContain(T1.placeMissed)
    expect(v.answerLine).toBe(T1.answerNotFound)
    expect(v.chip).toBe(T1.chipNotFound)
  })
  it('says the check is weak when the range has no far end, and "worked" only for a closed range', () => {
    const open = afterOf(base())
    expect(open).toEqual(expect.arrayContaining([T1.insideOpen, ...T1.openWeak]))
    expect(open).not.toContain(T1.inside)
    const f = base()
    f.candidate!.range_95_au = [80, 150]
    const closed = afterOf(f)
    expect(closed).toEqual(expect.arrayContaining([T1.inside, T1.wide]))
    expect(closed).not.toContain(T1.insideOpen)
  })
  it('says outside and missed when NASA is outside the range', () => {
    const f = base()
    f.candidate!.range_95_au = [100, 140]
    expect(afterOf(f)).toContain(T1.outside)
  })
  it('says narrow and fairly exact when the range is narrow', () => {
    const f = base()
    f.candidate!.range_95_au = [100, 120]
    const v = reflexView(f)
    expect(v.after.flat()).toContain(T1.narrow)
    expect(v.chip).toBe(T1.chipFoundDistance)
    expect(v.numbers?.range).toEqual([PAGE.rangeBetween('100', '120')])
  })
  it('says too near, or either side, for the two runs', () => {
    const f = base()
    f.candidate!.distance_au = 90
    f.shifted!.distance_au = 85
    expect(afterOf(f)).toEqual(expect.arrayContaining([T1.twiceNear, T1.alwaysDoes]))
    f.shifted!.distance_au = 120
    const t = afterOf(f)
    expect(t).toContain(T1.eitherSide)
    expect(t).not.toContain(T1.alwaysDoes)
  })
  it('says the second run missed NASA, and that the answer hardly moved', () => {
    const f = base()
    f.shifted!.range_95_au = [100, 140]
    f.shifted!.distance_au = 113
    const t = reflexView(f).howSure.flat().join(' ')
    expect(t).toContain("NASA's figure is outside that run's range: 100 to 140.")
    expect(t).toContain('The answer hardly moved: 111 and 113.')
  })
  it('says it can also find Eris away from the middle, never "wherever it sits"', () => {
    const t = reflexView(base()).howSure.flat()
    expect(t).toContain(T1.howSure.wherever)
    expect(t.join(' ')).not.toContain('wherever')
  })
  it('says it was partly a practice test while the write-up says the choices came after the answer was seen', () => {
    const f = base()
    expect(testOf(f)).toEqual(expect.arrayContaining(T1.practice))
    expect(testOf(f)).toContain(T1.testWas)
    f.development_object = false
    expect(testOf(f)).not.toContain(T1.practice[0])
  })
  it('names the bright neighbour of the earliest day only while the file gives it', () => {
    const f = base()
    expect(reflexView(f).howSure.flat()).toEqual(expect.arrayContaining([T1.howSure.earliestDay, T1.howSure.neighbour]))
    f.candidate!.first_day = { available: false }
    const t = reflexView(f).howSure.flat()
    expect(t).toContain(T1.howSure.earliestDay)
    expect(t).not.toContain(T1.howSure.neighbour)
  })
  it('says which pictures hold blanked-out patches', () => {
    expect(reflexView(base()).appear.blanks).toEqual([true, true, false])
  })
  it('drops "probably" once an injection test exists, and picks the {half} word', () => {
    const f = base()
    expect(reflexView(f).answers.nothing).toContain('more than half as bright')
    f.limit!.injection_tested = true
    expect(reflexView(f).answers.nothing).toBeNull()
    expect(halfWord(0.02, 0.07)).toBe('a third')
    expect(halfWord(0.06, 0.07)).toBe('as')
  })
  it('keeps the wrong-way control only while it is blurrier than no bend', () => {
    const f = base()
    const s0 = f.stops!.find((s) => s.inv_d === 0)!
    f.wrong_way!.snr = (s0.snr as number) + 1
    expect(reflexView(f).distance?.wrong).toBeNull()
  })
  it('says the Sedna sentence only while Sedna was not found', () => {
    const f = base()
    expect(reflexView(f).sedna).toBe(true)
    f.sedna!.found_blind = true
    expect(reflexView(f).sedna).toBe(false)
  })
  it('says how the patch was chosen from the file', () => {
    const f = base()
    f.field = { ...f.field, centred_on_known: true }
    expect(reflexView(f).test[1]).toEqual([...T1.centred, T1.notGiven])
    f.field = { ...f.field, centred_on_known: false }
    expect(reflexView(f).test[1]).toEqual(T1.notCentred)
  })
  it('chooses the slider lines: sharpest, nearly (in the 68% range), less sharp (still sharper than no bend), blurrier', () => {
    const d = reflexView(base()).distance!
    const lines = d.stops.map((s) => s.line)
    expect(lines[d.bestIndex]).toBe(T1.distance.sharpest('111'))
    // No bend (0), 500 and 200 are sharper than or as sharp as no bend: never "blurrier" there.
    expect(lines.slice(0, 3)).toEqual([T1.distance.lessNearer, T1.distance.lessNearer, T1.distance.lessNearer])
    expect(lines[3]).toBe(T1.distance.nearly)
    expect(lines[5]).toBe(T1.distance.lessFarther)
    expect(lines[6]).toBe(T1.distance.blurrierFarther)
    d.stops.forEach((s) => {
      if (s.line?.startsWith('Blurrier')) expect(s.delta as number).toBeLessThan(0)
      if (s.line?.startsWith('Less sharp')) expect(s.delta as number).toBeGreaterThanOrEqual(0)
    })
    // The opposite case: with no 68% range, no stop is "nearly as sharp".
    const f = base()
    f.candidate!.range_68_au = null
    expect(reflexView(f).distance!.stops.map((s) => s.line)).not.toContain(T1.distance.nearly)
  })
})

describe('tool 2 verdicts', () => {
  const base = () => clone(colour)
  const all = (f: ColourFile) => {
    const v = colourView(f)
    return [...v.test, ...v.howSure].flat()
  }
  it('says it did not point the right way, and how far off, when the angle misses', () => {
    const f = base()
    f.walk!.all!.pa = 120
    const v = colourView(f)
    expect(v.result).toEqual([T2.resultNotProven, T2.resultWrong, T2.resultSmallAnd])
    expect(v.test.flat().some((s) => /lies about \d+ degrees away/.test(s))).toBe(true)
  })
  it('says the shift counts, and "clearly", at 4 times the usual error', () => {
    const f = base()
    f.walk!.all!.sigma = 4.5
    const v = colourView(f)
    expect(v.result[2]).toBe(T2.resultBig)
    const red = v.groups.find((g) => g.name === 'Redder')
    if (red?.caption) expect(red.caption).toContain(T2.tryIt.redderClearly)
  })
  it('puts the verdict first: "not proven", or "passed" only when every check passed', () => {
    expect(colourView(base()).result[0]).toBe(T2.resultNotProven)
    const f = base()
    f.verdict = 'found'
    f.acceptance!.passed = true
    f.null!.acceptance!.passed = true
    f.development_object_note = null
    expect(colourView(f).result[0]).toBe(T2.resultPassed)
  })
  it('drops the turned-round sentence when a visit points elsewhere', () => {
    const f = base()
    expect(all(f)).toContain(T2.turned)
    f.visit_walks![0].sky_angle = 30
    expect(all(f)).not.toContain(T2.turned)
  })
  it('tells the review in "How sure", with the rule unchanged, and drops it when the floor was never changed', () => {
    const f = base()
    expect(colourView(f).howSure.flat()).toEqual(expect.arrayContaining([T2.guessed, T2.guessedNow('2', '2.7'), T2.ruleKept('4')]))
    f.walk!.sigma_guessed_floor = 1
    const t = all(f)
    expect(t).not.toContain(T2.guessed)
    expect(t).not.toContain(T2.ruleKept('4'))
  })
  it('says "if our usual error were right" with the rule', () => {
    expect(colourView(base()).test.flat()).toContain(T2.rule('4'))
    expect(T2.rule('4')).toContain('If our usual error were right')
  })
  it('counts the failed checks, and drops "not clean" when none failed', () => {
    const f = base()
    const names = Object.keys(f.acceptance!.checks!)
    f.acceptance!.checks = Object.fromEntries(names.map((k, i) => [k, i !== 0]))
    expect(all(f)).toContain(T2.checksOne)
    f.acceptance!.checks = Object.fromEntries(names.map((k) => [k, true]))
    f.null!.acceptance!.passed = true
    const t = all(f)
    expect(t).not.toContain(T2.notClean)
    expect(t).not.toContain(T2.nullFailed)
  })
  it('never says it was not told where the partner is (close to "works blind")', () => {
    expect(all(base()).join(' ')).not.toMatch(/not told/)
  })
  it('drops the practice-test sentence without the development note, and answers "found" on a found verdict', () => {
    const f = base()
    f.development_object_note = null
    f.verdict = 'found'
    f.acceptance!.passed = true
    f.null!.acceptance!.passed = true
    const v = colourView(f)
    expect(v.test.flat()).not.toContain(T2.practice)
    expect(v.answerLine).toBe(T2.answerFound)
    expect(v.chip).toBe(T2.chipPassed)
  })
  it('says other stars walked as far, from the null field, in "How sure" and beside the lone star', () => {
    const v = colourView(base())
    expect(v.howSure.flat()).toContain(T2.othersFar)
    expect(v.lone?.line).toEqual([T2.tryIt.lone, T2.tryIt.loneLittle, T2.othersFar, T2.tryIt.loneRule])
    const f = base()
    f.null!.walkers_over_4sigma = [{ walk_arcsec: 0.14, sigma: 4.2, neighbour_kind: 'along' }]
    expect(colourView(f).howSure.flat()).toContain(T2.othersAbout)
    f.null!.walkers_over_4sigma = [{ walk_arcsec: 0.05, sigma: 4.2, neighbour_kind: 'along' }]
    const t = colourView(f)
    expect(t.howSure.flat()).not.toContain(T2.othersFar)
    expect(t.howSure.flat()).not.toContain(T2.othersAbout)
    expect(t.lone?.line).toEqual([T2.tryIt.lone, T2.tryIt.loneLittle, T2.tryIt.loneRule])
  })
  it('chooses the Middle and Redder captions from the groups', () => {
    const f = base()
    f.groups = [
      { name: 'Bluer', east: 0, north: 0, err_east: 0.01, err_north: 0.01 },
      { name: 'Middle', east: -0.1, north: -0.12, err_east: 0.01, err_north: 0.01 },
      { name: 'Redder', east: 0.1, north: 0.1, err_east: 0.01, err_north: 0.01 },
    ]
    const g = colourView(f).groups
    expect(g[1].caption).toBe(T2.tryIt.captionMiddle(T2.tryIt.middleMoved))
    expect(g[2].caption).toBe(T2.tryIt.captionRedder(T2.tryIt.redderHardly))
  })
  it('compares a lone star only when its export exists, by the 0.7 rule', () => {
    const f = base()
    const groups = [
      { name: 'Bluer', east: 0, north: 0, err_east: 0.05, err_north: 0.05 },
      { name: 'Middle', east: 0.01, north: 0, err_east: 0.05, err_north: 0.05 },
      { name: 'Redder', east: 0.02, north: 0.01, err_east: 0.05, err_north: 0.05 },
    ]
    f.groups = groups
    f.lone_star = null
    expect(colourView(f).lone).toBeNull()
    f.lone_star = { walk_size: 0.03, groups }
    expect(colourView(f).lone?.line).toContain(T2.tryIt.loneLittle)
    f.lone_star = { walk_size: 0.17, groups }
    expect(colourView(f).lone?.line).toContain(T2.tryIt.loneFar)
  })
})

describe('tool 3 verdicts', () => {
  const base = () => clone(transit)
  it('says outside, and shallower, when the published depth is above the range', () => {
    const f = base()
    f.planet!.expected_depth = 0.025
    const v = transitView(f)
    expect(v.after.flat()).toContain(T3.publishedOutside)
    expect(v.asPublished).toBe(T3.shallower)
  })
  it('compares the single-reading scatter with the dip', () => {
    const f = base()
    f.d5!.scatter = f.d5!.depth
    expect(transitView(f).test.flat()).toContain(T3.aboutAs)
    f.d5!.scatter = 0.5 * (f.d5!.depth as number)
    expect(transitView(f).test.flat()).toContain(T3.almostAs)
  })
  it('calls it a practice test, not a fair one, and drops that when the method was not built on these readings', () => {
    expect(transitView(base()).after.flat()).toContain(T3.practice)
    expect(T3.practice).toContain('a practice test, not a fair one')
    const f = base()
    f.development_object = false
    expect(transitView(f).after.flat()).not.toContain(T3.practice)
  })
  it('reports the second planet by its bands', () => {
    const f = base()
    f.wasp100!.per_detector = { '3': { depth: 0.0075, empirical_err: 0.002, empirical_sigma: 3.7 }, '5': { depth: 0.0076, empirical_err: 0.002, empirical_sigma: 3.8 } }
    let v = transitView(f)
    expect(v.after.flat()).toContain(T3.secondAll)
    expect(v.chip).toBe(T3.chipTwo)
    f.wasp100!.per_detector = { '3': { depth: 0.001, empirical_err: 0.003, empirical_sigma: 0.3 } }
    v = transitView(f)
    expect(v.after.flat()).toContain(T3.secondNone)
    f.wasp100!.combined = { depth: 0.02, error: 0.002 }
    expect(transitView(f).after.flat()).toContain(T3.secondDeeper)
  })
  it('says "both years together" when a year alone is not clear', () => {
    const f = base()
    f.d5!.years = { '2025': { depth: 0.002, formal_err: 0.003 }, '2026': { depth: 0.011, formal_err: 0.002 } }
    expect(transitView(f).howSure.flat()).toContain(T3.howSure.yearsTogether)
  })
  it('says how many wrong timetables were as deep, under the dial', () => {
    const f = base()
    const d5 = f.d5 as Record<string, unknown>
    delete d5.n_fake_as_deep
    d5.fake_share_as_deep = 3 / (f.d5!.n_fake as number)
    expect(transitView(f).dialNote.flat()).toContain(T3.howSure.someDid('3'))
  })
  it('says the fakes are not that many separate tries ("if chance often"), and their overlap in For scientists', () => {
    const v = transitView(base())
    expect(v.dialNote.flat()).toContain(T3.howSure.wouldShow)
    expect(T3.howSure.wouldShow).toMatch(/^If chance often/)
    expect(v.sci.join(' ')).toContain('0 of 598 fakes as deep (they overlap: 88% of pairs share a reading, about 140 independent')
  })
  it('gives each year its scaled errors, and the WASP-100 b mismatch, in For scientists', () => {
    const t = transitView(base()).sci.join(' ')
    expect(t).toContain('the errors are ± 0.40 and ± 0.35 (3.3σ and 3.1σ)')
    expect(t).toContain('No single detector matches the published depth (D3 1.9σ shallower, D5 1.4σ deeper, D6 0.3σ shallower)')
  })
  it('names the one band of colours only while there are several', () => {
    const f = base()
    f.detectors = { '5': {} }
    f.coverage = { ...f.coverage, per_detector: null }
    expect(transitView(f).lead).toEqual([T3.bigPlanet])
  })
  it('says no clear dip when the known-answer check failed', () => {
    const f = base()
    f.acceptance = { A1: { passed: false } }
    const v = transitView(f)
    expect(v.answerLine).toBe(T3.answerNot)
    expect(v.chip).toBe(T3.chipNone)
  })
})

// ---------------------------------------------------------------------------------- helpers

describe('the address', () => {
  it('is ?tools=1, carrying the place the visitor came from', () => {
    expect(isToolsAddress('?tools=1')).toBe(true)
    expect(isToolsAddress('?ra=1&dec=2')).toBe(false)
    expect(toolsAddress({ ra: 27.4, dec: -0.12, name: 'Eris' })).toBe('?tools=1&ra=27.4&dec=-0.12&name=Eris')
  })
  it('goes back to the place, or to the start', () => {
    expect(toolsBackAddress('?tools=1')).toBe('/')
    expect(toolsBackAddress('?tools=1&ra=27.4&dec=-0.12')).toMatch(/^\?ra=27\.4&dec=-0\.12/)
  })
})

describe('the small rules', () => {
  it('writes distances in squares as fractions', () => {
    expect(fractionWords(8.06 / 6.15)).toBe('one and a third')
    expect(fractionWords(0.5)).toBe('a half')
    expect(fractionWords(1.98)).toBe('two')
  })
  it('turns a position angle into a direction on a north-up, east-left picture', () => {
    expect(screenDirection(218)).toBe('lower right')
    expect(screenDirection(120)).toBe('lower left')
    expect(screenDirection(30)).toBe('upper left')
    expect(screenDirection(300)).toBe('upper right')
  })
  it('names the months of a visit', () => {
    expect(monthsOf(60866.09, 60881.44)).toBe('July 2025')
    expect(monthsOf(60880, 60900)).toBe('July and August 2025')
  })
  it('says when the other visits came', () => {
    expect(otherVisitsPhrase(60866.09, 60881.44, [{ mjd_first: 61035.5, mjd_last: 61060.2 }, { mjd_first: 61232.7, mjd_last: 61243.4 }])).toBe('about half a year later, and again a year later')
    expect(otherVisitsPhrase(60866.09, 60881.44, [{ mjd_first: 60750, mjd_last: 60760 }])).toBe('4 months earlier')
  })
  it('writes small chances as powers of ten', () => {
    expect(powerOfTen(2.086e-7)).toBe('2 × 10⁻⁷')
  })
  it('leaves a sentence out when a value is missing', () => {
    expect(fill((v: { a: string; b: string }) => `${v.a} and ${v.b}`, { a: '1' })).toBeNull()
    expect(fill((v: { a: string }) => `${v.a}.`, { a: '1' })).toBe('1.')
  })
})

describe('folding the readings', () => {
  // A made-up test series, only to check the folding: a 1 per cent box dip every 2 days.
  const readings = Array.from({ length: 400 }, (_, i) => {
    const t = 1000 + i * 0.137
    const phase = (((t - 1000) % 2) + 2) % 2
    const inDip = phase < 0.05 || phase > 1.95
    return { bjd_tdb: t, rel_flux: inDip ? 0.99 : 1 }
  })
  it('lines the dip up on the right timetable and blurs it on a wrong one', () => {
    const right = binFolded(fold(readings, 2, 1000))
    const centre = right.find((b) => Math.abs(b.h) < 0.5)!
    expect(centre.mean).toBeCloseTo(99, 1)
    const wrong = binFolded(fold(readings, 2.3, 1000))
    expect(Math.min(...wrong.map((b) => b.mean))).toBeGreaterThan(99.3)
  })
  it('keeps only readings within the window, in 45-minute slots', () => {
    const pts = fold(readings, 2, 1000, 9)
    expect(pts.every((p) => Math.abs(p.h) <= 9)).toBe(true)
    const slot = (h: number) => (h + 9) / 0.75 - 0.5
    expect(binFolded(pts).every((b) => Math.abs(slot(b.h) - Math.round(slot(b.h))) < 1e-9)).toBe(true)
  })
  it("gives the module's own 45-minute averages on the known timetable (5 readings a slot at least)", () => {
    const t = transitFile as unknown as TransitFile & { d5: { folded: { bin_hours: number[]; bin_mean: number[]; bin_err: number[] } } }
    const known = (t.stops ?? []).find((s) => s.known)!
    const bins = binFolded(fold(t.readings ?? [], known.period_d, t.planet!.t0_bjd_tdb as number, t.window_h as number))
    const f = t.d5.folded
    expect(bins.map((b) => b.h)).toEqual(f.bin_hours)
    bins.forEach((b, i) => {
      expect(b.mean).toBeCloseTo(f.bin_mean[i] * 100, 9)
      expect(b.err as number).toBeCloseTo(f.bin_err[i] * 100, 9)
      expect(b.n).toBeGreaterThanOrEqual(5)
    })
  })
  it('says the dip is not available, with no number, where the module refuses to fit', () => {
    const v = transitView(transitFile as TransitFile)
    const empty = v.dial!.stops.filter((s) => s.readout === null)
    expect(empty.length).toBe((transitFile.stops as { depth: number | null }[]).filter((s) => s.depth === null).length)
    expect(empty.every((s) => s.missing === T3.tryIt.tooFew && !s.lines.includes(T3.tryIt.chance))).toBe(true)
    // Where nothing was measured, the screen does not say the dip "blurs away".
    expect(empty.every((s) => s.lines.length === 1 && s.lines[0] === T3.tryIt.wrongFew && s.bar === null)).toBe(true)
    const noCount = transitView({ ...(transitFile as TransitFile), stops: (transitFile as TransitFile).stops!.map((s) => (s.depth === null ? { ...s, n_in: null } : s)) })
    expect(noCount.dial!.stops.filter((s) => s.readout === null).every((s) => s.missing === T3.tryIt.noDip)).toBe(true)
    expect(v.dial!.stops.filter((s) => s.readout !== null).every((s) => s.missing === null)).toBe(true)
  })
  it('gives the dial\'s "give or take" at about 95%, as the range above: 1.2 give or take 0.5 on the known timetable', () => {
    const v = transitView(transitFile as TransitFile)
    const known = v.dial!.stops[v.dial!.knownIndex]
    expect(known.readout).toBe(T3.tryIt.readout('1.2', '0.5'))
    expect(v.numbers?.range).toBe(PAGE.rangeBetween('0.6', '1.7'))
    const four = v.dial!.stops[0]
    expect(four.readout).toBe(T3.tryIt.readout('−0.3', '1.0'))
    expect(four.lines).toEqual([T3.tryIt.wrong, T3.tryIt.chance])
  })
  it('fixes the y range from the known timetable, rounded out', () => {
    expect(yRange([{ h: 0, y: 98.6 }, { h: 1, y: 100.2 }, { h: 2, y: 101.4 }])).toEqual([98, 102])
  })
  it("draws the module's trapezoid", () => {
    expect(trapezoidDepth(0, 3.79, 0.1109)).toBe(1)
    expect(trapezoidDepth(3, 3.79, 0.1109)).toBe(0)
  })
})

describe('colours', () => {
  it('never uses amber for a slider thumb, the chosen option or a toggle', () => {
    const rules = css.split('}').filter((r) => /slider-thumb|range-thumb|\.seg\.on|button\.toggle|button\.primary/.test(r))
    expect(rules.length).toBeGreaterThan(3)
    expect(rules.filter((r) => r.includes('--measured') || r.includes('--gaia'))).toEqual([])
  })
  it('uses no colour literals', () => {
    const body = css.replace(/\/\*[\s\S]*?\*\//g, '')
    expect(body).not.toMatch(/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|:\s*(white|black)\b|\s(white|black)\s*[;!]/)
  })
  it('prints no word in amber or cyan: those tokens only fill or stroke marks', () => {
    const body = css.replace(/\/\*[\s\S]*?\*\//g, '')
    const colourRules = body.split('}').filter((r) => /(^|[^-])color:\s*var\(--(measured|gaia)/.test(r))
    expect(colourRules).toEqual([])
  })
})
