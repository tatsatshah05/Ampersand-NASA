// The blink-comparator page: the strip of visits, and what the picture does while a view loads.
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Frame, FramesReady } from '../api'
import { loadFor, type Load } from '../useFrames'
import { monthYear, visitCaption } from '../wording'
import { VisitStrip } from './Transport'

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
    expect(html).toContain('class="readout-block busy"')
    expect(html).toContain('Visit 1: 2025-01-10 to 2025-01-12, 4 exposures')
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
  it('shows the first visit, marked in the strip, and its sentences in the readout block', () => {
    const html = pageWith({ state: 'ready', data: view('new') })
    expect(html).toContain('class="plate"')
    expect(html).not.toContain('Loading ')
    const strip = html.slice(html.indexOf('class="visit-strip"'))
    expect(strip.split('<button').slice(1, 4).map((b) => b.includes('aria-current="true"'))).toEqual([true, false, false])
    const block = html.slice(html.indexOf('class="readout-block'))
    expect(block).toContain('Visit 1: 2025-01-10 to 2025-01-12, 4 exposures')
    expect(block).toContain('This is where it started. Later frames are measured against it.')
  })

  it('Beginner has an i button on the movement and the detection lines, and the stage is described by the picture\'s', () => {
    const html = pageWith({ state: 'ready', data: view('new') })
    const block = html.slice(html.indexOf('class="readout-block'))
    expect(block).toContain('aria-label="About the movement line"')
    expect(html).toContain('aria-describedby="stage-help"')
    expect(html).toContain('aria-controls="stage-help"')
    expect(html).toContain('aria-label="About this picture"')
    // The strip of visits and the player have theirs, and Expert has none of them.
    expect(html).toContain('class="strip-row"')
    expect(pageWith({ state: 'ready', data: view('new') }, '?ui=expert')).not.toContain('info-button')
  })

  it('Expert has the same readout block, with the tools under it', () => {
    const html = pageWith({ state: 'ready', data: view('new') }, '?ui=expert')
    expect(html).toContain('class="readout-block"')
    expect(html).toContain('aria-label="Search for a distant world (Planet X)"')
    expect(html).toContain('aria-label="Search this patch for anything that moved or changed"')
    expect(html).toContain('>Spectrum of the target<')
    expect(html).toContain('>Brightness over time<')
    expect(html).toContain('>Asteroids and comets<')
  })
})
