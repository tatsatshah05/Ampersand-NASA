// The words of Beginner's guide and "i" popovers: true to the data, and plain.
import { describe, expect, it } from 'vitest'
import type { Frame, FramesReady } from './api'
import { placePopover } from './popover'
import {
  brightStarInfo,
  dayMonthYear,
  detectionInfo,
  GO_FURTHER,
  guideSteps,
  INFO_NAMES,
  infoFor,
  levelInfo,
  movementInfo,
  NO_PROGRESS,
  pictureInfo,
  playerInfo,
  stepName,
  visitsInfo,
  type InfoKey,
} from './guide'

const frame = (n: number, over: Partial<Frame> = {}): Frame => ({
  epoch: n,
  date_start: `2025-0${n}-10`,
  date_end: `2025-0${n}-12`,
  date_mean: `2025-0${n}-11`,
  mjd_mean: 60000 + n,
  image: `/frames/visit${n}.png`,
  n_exposures: 20 + n,
  wavelength_um: [3.8, 4.4],
  flagged_fraction: 0,
  saturated_pixels: 0,
  rejected_readings: 0,
  centroid: { ra: 10, dec: 20 + n * 0.0001, x: 50, y: 50, err_arcsec: 0.5, snr: 50, fwhm_arcsec: 6 },
  predicted: null,
  detection: 'clear',
  detection_sigma: 25.3,
  ...over,
})

const data = (frames = [frame(1), frame(2), frame(3)]): FramesReady => ({
  key: 'k',
  ra: 10,
  dec: 20,
  fov: 0.1,
  detector: 5,
  mode: 'normal',
  size_px: 100,
  pixel_arcsec: 2,
  target: null,
  frames,
})

const KEYS = Object.keys(INFO_NAMES) as InfoKey[]
const everything = (d: FramesReady | null, f: Frame | null) => KEYS.flatMap((k) => infoFor(k, d, f, [{ gmag: 4.3 }, { gmag: 6.1 }]))
const sentences = (text: string[]) => text.flatMap((p) => p.split(/(?<=[.!?])\s+/))
const words = (s: string) => s.split(/\s+/).filter(Boolean).length

describe('the steps', () => {
  it('start on the first and mark each step as the visitor does it', () => {
    expect(guideSteps(NO_PROGRESS).map((s) => s.state)).toEqual(['now', 'later', 'later'])
    expect(guideSteps({ chose: true, flipped: false, read: false }).map((s) => s.state)).toEqual(['done', 'now', 'later'])
    expect(guideSteps({ chose: true, flipped: true, read: false }).map((s) => s.state)).toEqual(['done', 'done', 'now'])
    expect(guideSteps({ chose: true, flipped: true, read: true }).map((s) => s.state)).toEqual(['done', 'done', 'done'])
  })
  it('keep "you are here" on the first step left undone, even when a later one was done first', () => {
    expect(guideSteps({ chose: false, flipped: true, read: false }).map((s) => s.state)).toEqual(['now', 'done', 'later'])
  })
  it('have a few words each and a name for a screen reader', () => {
    for (const s of guideSteps(NO_PROGRESS)) expect(words(s.label)).toBeLessThanOrEqual(4)
    expect(stepName(guideSteps(NO_PROGRESS)[0])).toBe('Step 1, you are here')
    expect(stepName(guideSteps({ chose: true, flipped: false, read: false })[0])).toBe('Step 1, done')
  })
  it('end with where to go further: Practise, helping check, and Expert', () => {
    expect(GO_FURTHER).toMatch(/practise.*help check.*Expert/)
  })
})

describe('the words', () => {
  const cases: [string, FramesReady | null, Frame | null][] = [
    ['with three visits on screen', data(), data().frames[1]],
    ['on the first visit', data(), data().frames[0]],
    ['with nothing measured', data([frame(1, { centroid: null, detection: 'none', detection_sigma: 0.4 })]), null],
    ['before anything has loaded', null, null],
  ]
  for (const [what, d, f] of cases) {
    it(`are plain ${what}: short sentences, no jargon, no claim of a discovery`, () => {
      const text = everything(d, f)
      for (const s of sentences(text)) expect(words(s), s).toBeLessThanOrEqual(20)
      expect(text.join(' ')).not.toMatch(/sigma|flux|epoch|detector|centroid|discover|new planet/i)
    })
  }
  it('name every button, and say what the explanation is about', () => {
    for (const k of KEYS) expect(INFO_NAMES[k]).toMatch(/^About /)
    expect(GO_FURTHER).not.toMatch(/discover|new planet/i)
  })
})

describe('the picture', () => {
  it('tells the whole story: archive, public copy, cleaned, lined up, averaged per visit', () => {
    const text = pictureInfo(null, null)[0]
    for (const part of ['asked NASA’s archive', 'NASA’s public copy', 'cleaned', 'lined them up', 'averaged the exposures of each visit']) {
      expect(text).toContain(part)
    }
  })
  it('counts the exposures and the dates from the frames on screen', () => {
    const d = data()
    // 21 + 22 + 23 exposures in 3 visits, from 10 Jan to 12 Mar 2025 (the frames' own dates).
    const [story] = pictureInfo(d, d.frames[1])
    expect(story).toContain('In all, 66 exposures went into 3 visit pictures, taken between 10 Jan 2025 and 12 Mar 2025.')
    expect(story).toContain('The one on screen uses 22.')
  })
  it('counts the subtracted visit of a difference view too, and says one when there is one', () => {
    const d = { ...data([frame(2)]), mode: 'difference' as const, reference_frame: { ...frame(1), image: undefined } as never }
    expect(pictureInfo(d, d.frames[0])[0]).toContain('In all, 43 exposures went into 2 visit pictures')
    expect(pictureInfo(data([frame(1, { n_exposures: 1 })]), null)[0]).toContain('In all, 1 exposure went into 1 visit picture')
  })
  it('says how to move around in the picture', () => {
    expect(pictureInfo(null, null)[1]).toContain('Scroll or pinch to zoom')
  })
  it('formats a date from its text, not through a time zone', () => {
    expect(dayMonthYear('2025-08-15')).toBe('15 Aug 2025')
    expect(dayMonthYear('2026-01-01T00:00:00')).toBe('1 Jan 2026')
  })
})

describe('the visits and the player', () => {
  it('give the number of visits, their months and their exposures', () => {
    expect(visitsInfo(data()).join(' ')).toContain('Here there are 3 visits, from Jan 2025 to Mar 2025. They hold 21, 22 and 23 exposures.')
  })
  it('say so when there is one visit only', () => {
    expect(visitsInfo(data([frame(1)])).join(' ')).toContain('only one visit')
    expect(playerInfo(data([frame(1)])).join(' ')).toContain('only one visit')
  })
  it('name the first and last visit for Blink', () => {
    expect(playerInfo(data()).join(' ')).toContain('Blink flips between visit 1 and visit 3.')
  })
})

describe('the movement line', () => {
  const d = data()
  it('uses the visit’s own distance, in arcseconds and in pixels', () => {
    const far = data([frame(1), frame(2, { centroid: { ra: 10, dec: 20, x: 51, y: 51, err_arcsec: 0.5, snr: 50, fwhm_arcsec: 6 } })])
    // The test frames sit 0.0001 degrees apart in declination: 0.36 arcseconds.
    const small = movementInfo(d.frames[1], d).join(' ')
    expect(small).toContain('Here it moved 0.4 arcseconds, which is 0.06 of a pixel.')
    expect(small).toContain('under a third of a pixel')
    expect(small).toContain('One SPHEREx pixel is 6.15 arcseconds wide.')
    expect(movementInfo(far.frames[1], far)).toBeTruthy()
  })
  it('says the first visit is the starting point, and that no spot could be measured when none was', () => {
    expect(movementInfo(d.frames[0], d).join(' ')).toContain('starting point')
    expect(movementInfo(frame(2, { centroid: null }), d).join(' ')).toContain('no clear spot could be measured')
  })
})

describe('the detection line', () => {
  it('gives the visit’s own number and the true thresholds', () => {
    const text = detectionInfo(frame(1)).join(' ')
    expect(text).toContain('Here it is 25 times the scatter.')
    expect(text).toContain('At least 5 times the scatter counts as clear. From 3 to 5 is marginal')
  })
  it('has a line for each outcome', () => {
    expect(detectionInfo(frame(1, { detection: 'saturated', detection_sigma: null })).join(' ')).toContain('overflowed')
    expect(detectionInfo(frame(1, { detection: 'unknown', detection_sigma: null })).join(' ')).toContain('too few empty places')
    expect(detectionInfo(frame(1, { detection: 'none', detection_sigma: 0.2 })).join(' ')).toContain('not above the scatter')
    expect(detectionInfo(frame(1, { detection: 'none', detection_sigma: 2.1 })).join(' ')).toContain('only 2.1 times')
  })
})

describe('the bright-star warning and the switch', () => {
  it('quotes the brightest star near', () => {
    expect(brightStarInfo([{ gmag: 6.1 }, { gmag: 4.3 }])[0]).toContain('a brightness of 4.3')
    expect(brightStarInfo([{ gmag: 4.3 }])[0]).toContain('gives it a brightness of 4.3')
    expect(brightStarInfo(null)[0]).toContain('very bright')
  })
  it('the switch says what Expert adds', () => {
    expect(levelInfo().join(' ')).toContain('distant world (Planet X)')
  })
})

describe('where a popover goes', () => {
  const view = { w: 1000, h: 700 }
  const size = { w: 340, h: 200 }
  it('is above the button, centred on it', () => {
    const at = placePopover({ left: 490, right: 514, top: 400, bottom: 424 }, size, view)
    expect(at).toEqual({ left: 332, top: 192 })
  })
  it('goes below when there is no room above', () => {
    expect(placePopover({ left: 490, right: 514, top: 40, bottom: 64 }, size, view).top).toBe(72)
  })
  it('never leaves the window sideways, so the page cannot grow wider', () => {
    expect(placePopover({ left: 0, right: 24, top: 400, bottom: 424 }, size, view).left).toBe(16)
    expect(placePopover({ left: 976, right: 1000, top: 400, bottom: 424 }, size, view).left).toBe(1000 - 340 - 16)
    const phone = { w: 390, h: 700 }
    const at = placePopover({ left: 350, right: 374, top: 400, bottom: 424 }, { w: 358, h: 200 }, phone)
    expect(at.left + 358).toBeLessThanOrEqual(390)
    expect(at.left).toBeGreaterThanOrEqual(0)
  })
  it('stays inside the window when it fits neither above nor below', () => {
    const at = placePopover({ left: 490, right: 514, top: 300, bottom: 324 }, { w: 340, h: 600 }, view)
    expect(at.top).toBeGreaterThanOrEqual(16)
    expect(at.top + 600).toBeLessThanOrEqual(700)
  })
})
