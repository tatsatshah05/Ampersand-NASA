// The blink-comparator page: the strip of visits, and what the picture does while a view loads.
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Frame, FramesReady } from '../api'
import { loadFor, type Load } from '../useFrames'
import { monthYear, visitCaption } from '../wording'
import { VisitStrip } from './Transport'
import { VisitDetails } from './VisitDetails'

// The page's frames come from useFrames; here each test says what it returns.
const held = vi.hoisted(() => ({ load: { state: 'loading', previous: null, slow: false } as unknown }))
vi.mock('../useFrames', async (original) => ({
  ...(await original<typeof import('../useFrames')>()),
  useFrames: () => held.load,
}))
// Imported after the mock is declared (vi.mock is hoisted above the imports anyway).
const { Viewer } = await import('../App')

// Hand-built, only to exercise the page; the numbers mean nothing.
const frame = (n: number): Frame => ({
  epoch: n,
  date_start: `2025-0${n}-10`,
  date_end: `2025-0${n}-12`,
  date_mean: `2025-0${n}-11`,
  mjd_mean: 60000 + n,
  image: `/frames/visit${n}.png`,
  n_exposures: 4,
  wavelength_um: [3.8, 4.4],
  flagged_fraction: 0,
  saturated_pixels: 0,
  rejected_readings: 0,
  centroid: { ra: 10, dec: 20, x: 50, y: 50, err_arcsec: 0.5, snr: 50, fwhm_arcsec: 6 },
  predicted: null,
})

const view = (key: string): FramesReady => ({
  key,
  ra: 10,
  dec: 20,
  fov: 0.1,
  detector: 5,
  mode: 'normal',
  size_px: 100,
  pixel_arcsec: 2,
  target: null,
  frames: [frame(1), frame(2), frame(3)],
})

const pageWith = (load: Load, search = '') => {
  held.load = load
  vi.stubGlobal('window', { location: { search }, localStorage: { getItem: () => null, setItem: () => undefined } })
  return renderToStaticMarkup(<Viewer />)
}

afterEach(() => vi.unstubAllGlobals())

/** The plate's markup: from the plate to the player under it. */
const plate = (html: string) => html.slice(html.indexOf('<div class="plate'), html.indexOf('<div class="transport"'))

describe('the strip of visits', () => {
  const visits = [1, 2, 3].map((n) => ({ src: `/frames/visit${n}.png`, name: `Visit ${n}`, when: `Jun 202${n}`, label: `Visit ${n}: details` }))

  it('has one button per visit, each with its own picture', () => {
    const html = renderToStaticMarkup(<VisitStrip visits={visits} current={1} disabled={false} onShow={() => undefined} />)
    expect(html).toContain('class="visit-strip"')
    expect(html.match(/<button/g)).toHaveLength(3)
    for (const n of [1, 2, 3]) expect(html).toContain(`src="/frames/visit${n}.png"`)
  })

  it('marks the visit on screen, and only that one', () => {
    const html = renderToStaticMarkup(<VisitStrip visits={visits} current={1} disabled={false} onShow={() => undefined} />)
    const buttons = html.split('<button').slice(1)
    expect(buttons.map((b) => b.includes('aria-current="true"'))).toEqual([false, true, false])
    expect(buttons[1]).toContain('Visit 2')
  })

  it('captions a visit by number and month, and a sum by its years', () => {
    expect(monthYear('2025-06-19')).toBe('Jun 2025')
    expect(monthYear('2026-12-31')).toBe('Dec 2026') // read from the text: no time zone can make it January
    const data = view('k')
    expect(visitCaption(data.frames[1], data)).toEqual({ name: 'Visit 2', when: 'Feb 2025' })
    const sum = { ...data, mode: 'sum' as const }
    expect(visitCaption({ ...frame(1), epoch: null, date_start: '2025-03-01', date_end: '2026-04-01' }, sum)).toEqual({
      name: 'All visits',
      when: '2025 to 2026',
    })
  })
})

describe('while a view loads (useFrames)', () => {
  const old = view('old')
  const ready = { key: '0 old-url', load: { state: 'ready' as const, data: old } }

  it('keeps the last view that loaded, undimmed for a moment and then marked slow', () => {
    expect(loadFor(ready, '0 new-url', null)).toEqual({ state: 'loading', previous: old, slow: false })
    expect(loadFor(ready, '0 new-url', '0 new-url')).toEqual({ state: 'loading', previous: old, slow: true })
  })

  it('has nothing to keep on the first load, or after a failed one', () => {
    expect(loadFor(null, '0 url', null)).toEqual({ state: 'loading', previous: null, slow: false })
    const failed = { key: '0 old-url', load: { state: 'error' as const, message: 'no' } }
    expect(loadFor(failed, '0 new-url', '0 new-url')).toEqual({ state: 'loading', previous: null, slow: true })
  })

  it('gives the answer once it is for this request', () => {
    expect(loadFor(ready, '0 old-url', '0 new-url')).toEqual(ready.load)
  })
})

describe('the page while a view loads', () => {
  it('keeps the previous pictures on the plate, dimmed, with the loading message over them', () => {
    const html = pageWith({ state: 'loading', previous: view('old'), slow: true })
    const onPlate = plate(html)
    expect(onPlate).toContain('class="plate busy"')
    expect(onPlate).toContain('class="stage"')
    for (const n of [1, 2, 3]) expect(onPlate).toContain(`src="/frames/visit${n}.png"`)
    expect(onPlate).toContain("Loading Barnard&#x27;s Star…")
  })

  it('keeps the player, the strip and the readout in place, with nothing to press', () => {
    const html = pageWith({ state: 'loading', previous: view('old'), slow: true })
    // Play, or Pause when the player was playing: either way it is there and cannot be pressed.
    expect(html).toMatch(/class="play-button"[^>]*disabled=""[^>]*>(?:(?!<\/button>).)*(Play|Pause)<\/button>/)
    const strip = html.slice(html.indexOf('class="visit-strip"'), html.indexOf('</aside>'))
    expect(strip.match(/class="visit"/g)).toHaveLength(3)
    expect(html).toMatch(/class="visit"[^>]*disabled=""/)
    // The last star's table stays, dimmed, with its rows' buttons switched off until the new one arrives.
    expect(html).toContain('class="readout-block busy"')
    const block = html.slice(html.indexOf('class="readout-block'), html.indexOf('<p class="sr-only" aria-live="polite">'))
    expect(block.match(/aria-label="Show visit \d"/g)).toHaveLength(3)
    expect(block).toMatch(/class="visit-row-button"[^>]*disabled=""/)
  })

  it('a quick answer leaves the pictures as they are: no dimming, no message', () => {
    const html = pageWith({ state: 'loading', previous: view('old'), slow: false })
    expect(html).toContain('class="plate"')
    expect(html).not.toContain('Loading ')
  })

  it('the first load shows an empty plate of the same kind, with the message in it', () => {
    const html = pageWith({ state: 'loading', previous: null, slow: false })
    const onPlate = plate(html)
    expect(onPlate).toContain('class="stage stage-empty"')
    expect(onPlate).toContain('Loading ')
    expect(html).toMatch(/class="play-button"[^>]*disabled=""/)
    expect(html).toContain('class="visit-strip"')
  })

  it('an error is told inside the plate, with a way to try again', () => {
    const html = pageWith({ state: 'error', message: 'The archive did not answer.' })
    const onPlate = plate(html)
    expect(onPlate).toContain('class="stage stage-empty"')
    expect(onPlate).toContain('The frames could not be loaded')
    expect(onPlate).toContain('The archive did not answer.')
    expect(onPlate).toContain('Try again')
  })
})

describe('the page with a view loaded', () => {
  it('shows every visit in one table, the first marked in the strip and in the table', () => {
    const html = pageWith({ state: 'ready', data: view('new') })
    expect(html).toContain('class="plate"')
    expect(html).not.toContain('Loading ')
    const strip = html.slice(html.indexOf('class="visit-strip"'))
    expect(strip.split('<button').slice(1, 4).map((b) => b.includes('aria-current="true"'))).toEqual([true, false, false])
    const block = html.slice(html.indexOf('class="readout-block'), html.indexOf('<p class="sr-only" aria-live="polite">'))
    // A real table: a name, column headers, and one row per visit with a button that shows it.
    expect(block).toMatch(/<table class="visit-table" aria-label="[^"]+">/)
    expect(block.match(/<th scope="col">/g)).toHaveLength(2)
    const rows = block.split('<tr class="visit-row"').slice(1)
    expect(rows).toHaveLength(3)
    expect(rows.map((r) => r.startsWith(' aria-current="true"'))).toEqual([true, false, false])
    expect(rows.map((r) => /aria-label="Show visit (\d)"/.exec(r)?.[1])).toEqual(['1', '2', '3'])
    expect(rows[0]).toContain('<td>start</td>')
    // The whole run, said once, and none of the old sentences about the visit on screen.
    expect(block).toContain('class="result-sentence">No movement seen between January 2025 and March 2025.')
    expect(block).not.toContain('This is where it started')
    expect(block).not.toContain('Visit 1: 2025-01-10')
    expect(block).not.toContain('class="tag"')
  })

  it('says nothing to a screen reader until the visitor steps or chooses a visit', () => {
    const html = pageWith({ state: 'ready', data: view('new') })
    expect(html).toContain('<p class="sr-only" aria-live="polite"></p>')
    expect(html).not.toMatch(/readout-block[^>]*aria-live/)
  })

  it('Beginner has an i button on the movement and the detection lines, and the stage is described by the picture\'s', () => {
    const html = pageWith({ state: 'ready', data: view('new') })
    const block = html.slice(html.indexOf('class="readout-block'), html.indexOf('<p class="sr-only" aria-live="polite">'))
    expect(block).toContain('aria-label="About the movement line"')
    expect(html).toContain('aria-describedby="stage-help"')
    expect(html).toContain('aria-controls="stage-help"')
    expect(html).toContain('aria-label="About this picture"')
    // The strip of visits and the player have theirs, and Expert has none of them.
    expect(html).toContain('class="strip-row"')
    expect(pageWith({ state: 'ready', data: view('new') }, '?ui=expert')).not.toContain('info-button')
  })

  it('Expert has the same readout block holding the full table; its tools are in the bar at the top', () => {
    const html = pageWith({ state: 'ready', data: view('new') }, '?ui=expert')
    expect(html).toContain('class="readout-block"')
    const block = html.slice(html.indexOf('class="readout-block'), html.indexOf('<p class="sr-only" aria-live="polite">'))
    expect(block).toContain('<table class="visit-table expert">')
    expect(block).toContain('<caption>Shift since visit 1 in ″, east and north.</caption>')
    expect(block.match(/<th scope="col">/g)).toHaveLength(5)
    // One tbody per visit: two lines, the first headed by the visit's button.
    const visits = block.split('<tbody class="visit-rows"').slice(1)
    expect(visits).toHaveLength(3)
    expect(visits[0]).toMatch(/^ aria-current="true"/)
    expect(visits[1]).toContain('aria-label="Show visit 2"')
    expect(visits[1]).toContain('10–12 Feb 2025 · 4 exp. · ±0.5″')
    // The six tools are in the bar at the top, each with its sentence as its title, and can be
    // pressed now that the view is here; the side column no longer has a section of tool buttons.
    const top = html.slice(html.indexOf('<header class="topbar">'), html.indexOf('</header>'))
    for (const [label, title] of [
      ['Light curve', 'Light curve: the target&#x27;s brightness'],
      ['Spectrum', 'Spectrum: one brightness measurement per exposure'],
      ['Blind search', 'Blind search: everything in the field that moved or changed brightness'],
      ['Planet X search', 'Planet X search: looks for a body'],
      ['Small bodies', 'Small bodies: known asteroids and comets'],
      ['Object card', 'Catalogue identity and parameters of the object'],
    ]) {
      expect(top).toMatch(new RegExp(`<button class="feature-item" title="${title}[^"]*" type="button"><span class="feature-text" data-text="${label}">`))
    }
    expect(top).not.toContain('aria-disabled')
    expect(html).not.toContain('Measure and search')
    expect(html).not.toContain('tool-buttons')
    // The two folds, closed, with nothing inside them in the page until opened; the sky context is a tool panel now.
    expect(html.match(/<details class="fold"><summary>(Catalogue notes|Visit details)<\/summary><\/details>/g)).toHaveLength(2)
    expect(html).not.toContain('<summary>Sky context</summary>')
    expect(html).not.toContain('Frame details')
    // No tool is open until one is asked for.
    expect(html).toContain('<div class="tool-panels"></div>')
  })

  it('opens the tool the address asks for only once the pictures are ready, at either level', () => {
    // Before the pictures, nothing is open (the tools need them); the address keeps the tool for later.
    for (const ui of ['beginner', 'expert']) {
      const waiting = pageWith({ state: 'loading', previous: null, slow: false }, `?ui=${ui}&tool=brightness`)
      expect(waiting).toContain('<div class="tool-panels"></div>')
      expect(waiting).not.toContain('The address asks to open a tool')
    }
    // An unknown tool is ignored, with a note in the side column as for the other parameters.
    const unknown = pageWith({ state: 'ready', data: view('new') }, '?ui=expert&tool=telescope')
    expect(unknown).toContain('The address asks to open a tool called &quot;telescope&quot;.')
  })

  it('Visit details holds every visit at once, each with its own cautions in detection.ts words', () => {
    const data = view('new')
    data.frames[1] = { ...data.frames[1], detection: 'marginal', detection_sigma: 3.4, centroid: { ...data.frames[1].centroid!, saturated_core: true, err_arcsec: 1 } }
    data.frames[2] = { ...data.frames[2], centroid: null, centroid_reason: 'The predicted position is off the picture.' }
    const html = renderToStaticMarkup(<VisitDetails data={data} />)
    expect(html.match(/class="visit-detail"/g)).toHaveLength(3)
    expect(html).toContain('Marginal detection, 3.4 times the background scatter: treat with care.')
    expect(html).toContain('The core is overexposed, so the position is good to about 1″, not the much smaller error of the fit.')
    expect(html).toContain('No position could be measured in this frame. The predicted position is off the picture.')
  })
})
