// The "Three tools" screen, rendered: its states, its structure for keyboards and screen readers,
// and the words that depend on the files (build spec sections 5, 10 and 13).
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import colourFile from '../../public/lab/colourwalk.json'
import reflexFile from '../../public/lab/reflex.json'
import transitFile from '../../public/lab/transits.json'
import App from '../App'
import type { ColourFile, Load, ReflexFile, TransitFile } from '../tools'
import { PAGE, T1, T2, T3 } from '../toolsWording'
import { ToolsPage } from './ToolsView'

const ready = <T,>(data: T): Load<T> => ({ state: 'ready', data })
const clone = <T,>(x: T): T => structuredClone(x)
const reflex = reflexFile as unknown as ReflexFile
const colour = colourFile as unknown as ColourFile
const transit = transitFile as unknown as TransitFile

const decode = (html: string) =>
  html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')

const page = (r: Load<ReflexFile>, c: Load<ColourFile>, t: Load<TransitFile>) =>
  renderToStaticMarkup(<ToolsPage reflex={r} colourwalk={c} transits={t} back="/" onRetry={() => undefined} />)

/** The files with the parts a try-it needs, made up for this test only: the numbers mean nothing. */
function withTryIts() {
  const r = clone(reflex)
  const track = (k: number) => ({
    track_east: [0, 10 + k, 20, 30 - k],
    track_north: [0, -5, -10 + k, -15],
    linear_east: [0, 10, 20, 30],
    linear_north: [0, -5, -10, -15],
  })
  r.stops = r.stops!.map((s, i) => ({ ...s, ...track(i) }))
  r.wrong_way = { ...r.wrong_way!, ...track(-2) }
  r.demo = { ...r.demo, crop_px: 48, single: { png: 'a.png' }, plain_mean: { png: 'b.png' }, slid: { png: 'c.png' }, marks: { tool_dot_px: [24, 24], nasa_single_px: [24, 23], nasa_mid_px: [24, 24], nasa_path_px: [[30, 20], [24, 24]] } }
  const c = clone(colour)
  c.groups = [
    { name: 'Bluer', east: 0, north: 0, err_east: 0.05, err_north: 0.07, png: 'b.png' },
    { name: 'Middle', east: -0.05, north: -0.01, err_east: 0.05, err_north: 0.07, png: 'm.png' },
    { name: 'Redder', east: -0.11, north: -0.14, err_east: 0.05, err_north: 0.07, png: 'r.png' },
  ]
  const t = clone(transit)
  t.readings = Array.from({ length: 60 }, (_, i) => ({ bjd_tdb: 2460800 + i * 0.37, rel_flux: 1 + ((i % 7) - 3) * 0.002 }))
  t.stops = [4, 4.3, 4.41193868, 4.55, 4.8].map((p, i) => ({ period_d: p, known: i === 2, depth: i === 2 ? 0.0118 : 0.001, err: 0.002 }))
  return { r, c, t }
}

afterEach(() => vi.unstubAllGlobals())

describe('the route', () => {
  it('?tools=1 shows this screen and none of the viewer', () => {
    vi.stubGlobal('window', { location: { search: '?tools=1' }, localStorage: { getItem: () => null, setItem: () => undefined } })
    const html = renderToStaticMarkup(<App />)
    expect(html).toContain(PAGE.title)
    expect(html).not.toContain('class="bench"')
  })
})

describe('while the files load', () => {
  const html = page({ state: 'loading' }, { state: 'loading' }, { state: 'loading' })
  const text = decode(html)
  it('shows the words that need no file, and loading boxes for the rest', () => {
    expect(text).toContain(PAGE.loading)
    expect(text).toContain('Turn a camera to follow a runner.')
    expect(text).toContain('Picture two torches far away')
    expect(text).toContain('like a moth crossing')
    expect(html).toContain('loading-box')
  })
  it('shows no number from a file and no verdict', () => {
    expect(text).not.toMatch(/about \d+ times as far|\d per cent|351|Not proven/)
    expect(html).not.toContain('tl-verdict')
  })
  it('says "loading" once per tool, not once per part', () => {
    expect(text.split(PAGE.loading).length - 1).toBe(3)
  })
})

describe('when a file is missing', () => {
  const html = page(ready(reflex), { state: 'missing' }, ready(transit))
  const tool2 = decode(html.split('id="off-centre-in-red"')[1].split('id="line-up-the-dips"')[0])
  it('says so, offers Try again, and keeps the analogy and the sketch', () => {
    expect(tool2).toContain(PAGE.fileMissing)
    expect(tool2).toContain(PAGE.tryAgain)
    expect(tool2).toContain('Picture two torches far away')
    expect(tool2).toContain(PAGE.sketchLabel)
  })
  it('hides that tool’s numbers, verdicts, try-it and fold-outs', () => {
    expect(tool2).not.toMatch(/351|about 2 times|Walk through the colours|For scientists|Not proven/)
    expect(tool2).not.toContain(T2.tryIt.heading)
  })
  it('says so once per tool, not once per part', () => {
    const all = decode(page({ state: 'missing' }, { state: 'missing' }, { state: 'missing' }))
    expect(all.split(PAGE.fileMissing).length - 1).toBe(3)
    expect(all).not.toMatch(/Try it:/)
  })
})

describe('when a part of a file is missing', () => {
  it('tool 3 says so in plain words in place of the dial, with no orphaned instructions', () => {
    for (const cut of ['readings', 'stops', 'planet'] as const) {
      const t = clone(transit)
      ;(t as Record<string, unknown>)[cut] = null
      const tool3 = decode(page(ready(reflex), ready(colour), ready(t)).split('id="line-up-the-dips"')[1])
      expect(tool3).toContain(T3.tryIt.heading)
      expect(tool3).toContain(PAGE.partMissing)
      expect(tool3).not.toContain(T3.tryIt.intro)
      expect(tool3).not.toMatch(/Not ready yet|data file/)
    }
  })
  it('tool 1 says so in place of the distance slider', () => {
    const r = clone(reflex)
    r.stops = null
    const tool1 = decode(page(ready(r), ready(colour), ready(transit)).split('id="follow-the-bend"')[1].split('id="off-centre-in-red"')[0])
    expect(tool1).toContain(PAGE.partMissing)
    expect(tool1).not.toContain(T1.distance.intro[0])
  })
})

describe('with the shipped files', () => {
  const html = page(ready(reflex), ready(colour), ready(transit))
  const text = decode(html)
  it('has one h1, three tools as labelled sections, and focusable headings for the jump links', () => {
    expect(html.match(/<h1/g)?.length).toBe(1)
    for (const id of [T1.id, T2.id, T3.id]) {
      expect(html).toContain(`<section class="tool" aria-labelledby="${id}"`)
      expect(html).toMatch(new RegExp(`<h2 id="${id}" tabindex="-1"`))
      expect(html).toContain(`href="#${id}"`)
    }
    expect(html).toContain('lang="en-GB"')
  })
  it('folds How sure, the three answers and For scientists into closed details', () => {
    expect(html).not.toContain('<details open')
    for (const s of [PAGE.foldHowSure, PAGE.foldAnswers, PAGE.foldScientists]) expect(html).toContain(`<summary>${s.replace(/'/g, '&#x27;')}</summary>`)
  })
  it('in Expert opens the three "For scientists" fold-outs when the screen loads, and nothing else; its words are the same', () => {
    const expert = renderToStaticMarkup(
      <ToolsPage reflex={ready(reflex)} colourwalk={ready(colour)} transits={ready(transit)} back="/" onRetry={() => undefined} level="expert" />,
    )
    const open = [...expert.matchAll(/<details class="([^"]*)" open="">/g)].map((m) => m[1])
    expect(open).toEqual(['tl-fold scientists', 'tl-fold scientists', 'tl-fold scientists'])
    expect(decode(expert)).toBe(text)
    // Beginner, given or left out, keeps every fold closed.
    const beginner = renderToStaticMarkup(
      <ToolsPage reflex={ready(reflex)} colourwalk={ready(colour)} transits={ready(transit)} back="/" onRetry={() => undefined} level="beginner" />,
    )
    expect(beginner).toBe(html)
  })
  it('keeps every live region silent until the visitor acts', () => {
    const live = [...html.matchAll(/aria-live="polite"[^>]*>([^<]*)</g)].map((m) => m[1])
    expect(live).toHaveLength(3)
    expect(live.every((t) => t === '')).toBe(true)
  })
  it('labels every sketch, and gives every picture and chart a text alternative', () => {
    const sketches = [...html.matchAll(/<figcaption class="sketch-label">([^<]*)</g)].map((m) => decode(m[1]).trim())
    expect(sketches.length).toBeGreaterThanOrEqual(3)
    expect(sketches.every((s) => s.startsWith('A sketch'))).toBe(true)
    expect(html).not.toMatch(/<img(?![^>]*alt="[^"]+")/)
    const imgRoles = html.match(/<[^>]*role="img"[^>]*>/g) ?? []
    expect(imgRoles.length).toBeGreaterThan(3)
    expect(imgRoles.filter((tag) => !/aria-label="[^"]+"/.test(tag))).toEqual([])
  })
  it('defines a square before its first use, in tool 1 and in tool 2', () => {
    for (const [from, to] of [
      [T1.id, T2.id],
      [T2.id, T3.id],
    ]) {
      const part = decode(html.split(`id="${from}"`)[1].split(`id="${to}"`)[0])
      const defined = part.indexOf('tiny squares, like tiles')
      const used = part.search(/\bsquares?\b/)
      expect(defined).toBeGreaterThan(-1)
      expect(used).toBeGreaterThanOrEqual(defined)
    }
  })
  it('never shows "undefined", "NaN" or a brace', () => {
    expect(text).not.toMatch(/undefined|NaN|[{}]/)
  })
  it('shows the notice for every file that says it is a stand-in, and only then', () => {
    const notices = (h: string) => (h.match(/tools-fixture/g) ?? []).length
    const stand = [reflex, colour, transit].filter((f) => (f as { fixture?: boolean }).fixture === true).length
    expect(notices(html)).toBe(stand)
    const real = page(ready({ ...reflex, fixture: false }), ready({ ...colour, fixture: false }), ready({ ...transit, fixture: false }))
    expect(notices(real)).toBe(0)
  })
  it('shows the "tests so far" line only while a file says it is not final', () => {
    const allFinal = page(ready({ ...reflex, final: true }), ready({ ...colour, final: true }), ready({ ...transit, final: true }))
    expect(decode(allFinal)).not.toContain(PAGE.notFinal)
    const oneNot = page(ready({ ...reflex, final: false }), ready({ ...colour, final: true }), ready({ ...transit, final: true }))
    expect(decode(oneNot)).toContain(PAGE.notFinal)
  })
  it('gives each tool its verdict under its name, with the number that matters; tool 2 in the notice colour', () => {
    expect(html).toContain('<div class="tl-verdict tl-verdict-notice"><p class="tl-verdict-words">Not proven yet</p>')
    const verdicts = [...html.matchAll(/<div class="tl-verdict[^"]*">(.*?)<\/div>/g)].map((m) => decode(m[1]).trim())
    expect(verdicts).toHaveLength(3)
    expect(verdicts[0]).toMatch(/^Found its test world\. Distance only rough\. Our tool: about 111 NASA: 95\.6/)
    expect(verdicts[1]).toMatch(/^Not proven yet The shift: about 2 times our usual error Needed by our rule: 4 times/)
    // The depth never without its give-or-take (docs/transits.md).
    expect(verdicts[2]).toMatch(/^Showed one known planet's dip\. Mixed on a second\. Our tool: about 1\.2 per cent, give or take 0\.5 Published: 1\.23 per cent/)
  })
  it('marks the main button of each try-it with the arrow the key names, and no other button', () => {
    const arrows = [...html.matchAll(/<button[^>]*>([^<]*)<svg class="main-arrow"/g)].map((m) => m[1])
    expect(arrows).toEqual([T1.appear.slide, T2.tryIt.walk, T3.tryIt.useKnown])
  })
  it('has no entry link and no "your patch" search on this screen', () => {
    expect(text).not.toContain('Try our three tools')
    expect(text).not.toContain('Search this patch')
    expect(text).not.toContain('Try it on the patch you were viewing')
  })
})

describe('the try-its, with their parts present', () => {
  const { r, c, t } = withTryIts()
  const html = page(ready(r), ready(c), ready(t))
  it('tool 1: a radio group with a legend, the slider with words for its value, the wrong-way toggle', () => {
    expect(html).toContain(`<legend class="sr-only">${T1.appear.legend}</legend>`)
    expect(html.match(/type="radio" name="t1-add"/g)?.length).toBe(3)
    expect(html).toContain('id="t1-distance" type="range" min="0" max="6" step="1" aria-valuetext="No bend, a straight, steady path" value="0"')
    expect(html).toContain(`aria-pressed="false">${T1.appear.showNasa}`)
    expect(html).toContain(T1.distance.wrongButton)
    expect(html).toContain('class="sketch sketch-bend"')
  })
  it('tool 2: the colour slider starts at Bluer, with the walk button', () => {
    expect(html).toContain('id="t2-colour" type="range" min="0" max="2" step="1" aria-valuetext="Bluer colours" value="0"')
    expect(html).toContain(T2.tryIt.walk)
    expect(html).toContain(T2.tryIt.insetTitle('40'))
  })
  it('tool 3: the dial starts at 4.00 days with the known timetable marked, and a hidden table of the averages', () => {
    expect(html).toContain('id="t3-timetable" type="range" min="0" max="4" step="1" aria-valuetext="4.00 days, a wrong timetable" value="0"')
    expect(html).toContain(T3.tryIt.knownTick)
    expect(html).toContain(T3.tryIt.useKnown)
    expect(html).toContain(`<caption>${T3.tryIt.tableCaption('4.00')}</caption>`)
  })
  it('every picture has its words and the compass', () => {
    expect(html).toMatch(/<img src="\/lab\/a\.png" alt="One SPHEREx picture/)
    expect(html).toContain('tl-compass')
  })
})
