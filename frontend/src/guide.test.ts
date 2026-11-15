// The words of Beginner's guide and "i" popovers: true to the data, and plain.
import { describe, expect, it } from 'vitest'
import type { Frame, FramesReady } from './api'
import barnardJson from './fixtures/frames/barnard_d5.json'
import rwAurJson from './fixtures/frames/rwaur_request_d5.json'
import novaJson from './fixtures/frames/v572vel_d2.json'
import { placePopover } from './popover'
import { motionSentence } from './wording'
import {
  BRIGHTNESS_POINTER,
  brightLine,
  brightStarInfo,
  dayMonthYear,
  detectionInfo,
  GO_FURTHER,
  guideSteps,
  INFO_NAMES,
  infoFor,
  levelInfo,
  coinWords,
  movementInfo,
  NO_PROGRESS,
  pictureInfo,
  playerInfo,
  stepName,
  stepsInfo,
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
  target: { name: 'Test star' } as never,
  frames,
})

const KEYS = Object.keys(INFO_NAMES) as InfoKey[]
const everything = (d: FramesReady | null) => KEYS.flatMap((k) => infoFor(k, d, [{ gmag: 4.3 }, { gmag: 6.1 }]))
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
    for (const s of guideSteps(NO_PROGRESS)) expect(words(s.label)).toBeLessThanOrEqual(5)
    expect(stepName(guideSteps(NO_PROGRESS)[0])).toBe('Step 1, you are here')
    expect(stepName(guideSteps({ chose: true, flipped: false, read: false })[0])).toBe('Step 1, done')
  })
  it('end by pointing to the other tools, in the bar at the top', () => {
    expect(GO_FURTHER).toBe('Then try the other tools in the bar at the top.')
  })
  it('explain the bar, not the two links it replaced, and keep saying no find is confirmed', () => {
    const text = stepsInfo().join(' ')
    expect(text).toContain('The bar at the top lists every tool')
    expect(text).toContain('Practise, Observe anomalies and Three tools open pages of their own.')
    expect(text).toContain('None of those finds is confirmed.')
    // The first three buttons are our own candidates: said to be unconfirmed, never a find.
    expect(text).toContain('nobody has confirmed them yet')
    expect(text).toContain('The last three changed while SPHEREx watched them.')
    expect(text).not.toMatch(/Expert adds more tools/)
  })
})

describe('the words', () => {
  const cases: [string, FramesReady | null][] = [
    ['with three visits', data()],
    ['with one visit not found', data([frame(1), frame(2, { centroid: null, detection: 'none', detection_sigma: 0.4 }), frame(3)])],
    ['with nothing measured', data([frame(1, { centroid: null, detection: 'none', detection_sigma: 0.4 })])],
    ['before anything has loaded', null],
  ]
  for (const [what, d] of cases) {
    it(`are plain ${what}: short sentences, no jargon, no claim of a discovery`, () => {
      const text = everything(d)
      for (const s of sentences(text)) expect(words(s), s).toBeLessThanOrEqual(20)
      expect(text.join(' ')).not.toMatch(/sigma|flux|epoch|detector|centroid|discover|new planet/i)
    })
  }
  it('name every button, and say what the explanation is about', () => {
    for (const k of KEYS) expect(INFO_NAMES[k]).toMatch(/^About /)
    expect(GO_FURTHER).not.toMatch(/discover|new planet/i)
  })
  it('never say "the one on screen", "this visit" or "here it is": no popover depends on the visit shown', () => {
    for (const [, d] of cases) expect(everything(d).join(' ')).not.toMatch(/one on screen uses|in this visit\b|Here the object is|This visit is the starting point/)
  })
})

describe('the picture', () => {
  it('tells the whole story: archive, public copy, cleaned, lined up, averaged per visit', () => {
    const text = pictureInfo(null)[0]
    for (const part of ['asked NASA’s archive', 'NASA’s public copy', 'cleaned', 'lined them up', 'averaged each visit’s exposures into one picture']) {
      expect(text).toContain(part)
    }
  })
  it('counts the exposures and the dates of every visit, and nothing about the one on screen', () => {
    const d = data()
    // 21 + 22 + 23 exposures in 3 visits, from 10 Jan to 12 Mar 2025 (the frames' own dates).
    const [story] = pictureInfo(d)
    expect(story).toContain('In all, 66 exposures went into 3 visit pictures, taken between 10 Jan 2025 and 12 Mar 2025.')
    expect(story).not.toContain('The one on screen')
  })
  it('counts the subtracted visit of a difference view too, and says one when there is one', () => {
    const d = { ...data([frame(2)]), mode: 'difference' as const, reference_frame: { ...frame(1), image: undefined } as never }
    expect(pictureInfo(d)[0]).toContain('In all, 43 exposures went into 2 visit pictures')
    expect(pictureInfo(data([frame(1, { n_exposures: 1 })]))[0]).toContain('In all, 1 exposure went into 1 visit picture')
  })
  it('says how to read the marks and move around, for every visit at once', () => {
    const d = data()
    expect(pictureInfo(d, 'Barnard’s Star')[1]).toContain('The amber ring circles Barnard’s Star')
    expect(pictureInfo(data([frame(1), frame(2, { centroid: null })]))[1]).toContain('In visit 2 no ring is drawn')
    expect(pictureInfo(data([frame(1, { centroid: null })]))[1]).toContain('No ring is drawn')
    expect(pictureInfo(data([frame(1, { detection: 'marginal' }), frame(2)]))[1]).toContain('A dashed ring')
    expect(pictureInfo(d)[1]).toContain('Scroll or pinch to zoom')
  })
  it('formats a date from its text, not through a time zone', () => {
    expect(dayMonthYear('2025-08-15')).toBe('15 Aug 2025')
    expect(dayMonthYear('2026-01-01T00:00:00')).toBe('1 Jan 2026')
  })
})

describe('the visits and the player', () => {
  it('give the number of visits, their months and their exposures', () => {
    expect(visitsInfo(data()).join(' ')).toContain('Here there are 3 visits, between Jan 2025 and Mar 2025. They hold 21, 22 and 23 exposures.')
  })
  it('say so when there is one visit only', () => {
    expect(visitsInfo(data([frame(1)])).join(' ')).toContain('only one visit')
    expect(playerInfo(data([frame(1)])).join(' ')).toContain('only one visit')
  })
  it('name the first and last visit for Blink', () => {
    expect(playerInfo(data()).join(' ')).toContain('Blink flips between visit 1 and visit 3,')
  })
})

describe('the movement line', () => {
  const d = data()
  it('uses the whole run, first visit with a spot to the last, in arcseconds and in pixels', () => {
    // The test frames sit 0.0001 degrees apart in declination: 0.72 arcseconds from visit 1 to visit 3.
    const small = movementInfo(d).join(' ')
    expect(small).toContain('Its first and last places are from January 2025 and March 2025.')
    expect(small).toContain('Here it moved 0.7 arcseconds, 0.12 of a pixel.')
    expect(small).toContain('within the measuring error')
    expect(small).toContain('6.15 arcseconds across')
  })
  it('says which visits had no spot, and why, once', () => {
    const lost = data([frame(1), frame(2, { centroid: null, detection: 'none' }), frame(3)])
    expect(movementInfo(lost).join(' ')).toContain('In visit 2, no clear spot could be measured there.')
    // "Too far" only when the backend says so, never guessed from how clearly something is seen.
    const far = data([frame(1), frame(2, { centroid: null, detection: 'clear', centroid_reason: 'The nearest source is 9.1 arcsec from the predicted position, too far to be the target.' }), frame(3)])
    expect(movementInfo(far).join(' ')).toContain('In visit 2, a spot was found, but too far from where it should be.')
    const odd = data([frame(1), frame(2, { centroid: null, detection: 'clear', centroid_reason: 'What is at the predicted position is not shaped like a star (width 30 arcsec).' }), frame(3)])
    expect(movementInfo(odd).join(' ')).toContain('In visit 2, the spot there is not shaped like a star.')
    expect(movementInfo(odd).join(' ')).not.toMatch(/too far/)
    expect(movementInfo(data([frame(1), frame(2, { centroid: null })])).join(' ')).toContain('Fewer than two visits have a clear spot here')
  })
  it('says a sum cannot move', () => {
    expect(movementInfo({ ...data([frame(1)]), mode: 'sum' }).join(' ')).toContain('nothing can move in it')
  })
})

describe('the detection line', () => {
  it('gives every visit’s number at once, and the true thresholds', () => {
    const text = detectionInfo(data()).join(' ')
    expect(text).toContain('In every visit the object is 25 times the scatter.')
    expect(text).toContain('At least 5 times the scatter counts as clear. From 3 to 5 it may be real or may be chance')
    const mixed = detectionInfo(data([frame(1, { detection: 'marginal', detection_sigma: 3.39 }), frame(2, { detection_sigma: 14.6 }), frame(3, { detection_sigma: 11.2 })]))
    expect(mixed.join(' ')).toContain('In visits 1, 2 and 3 the object is 3.4, 15 and 11 times the scatter.')
  })
  it('has a line for each outcome', () => {
    expect(detectionInfo(data([frame(1, { detection: 'saturated', detection_sigma: null })])).join(' ')).toContain('overflowed')
    expect(detectionInfo(data([frame(1, { detection: 'unknown', detection_sigma: null })])).join(' ')).toContain('too few empty places')
    expect(detectionInfo(data([frame(1, { detection: 'none', detection_sigma: 0.2 })])).join(' ')).toContain('under 1 times the scatter')
    expect(detectionInfo(data([frame(1), frame(2, { detection: 'none', detection_sigma: 2.1 })])).join(' ')).toContain('25 and 2.1 times')
    const many = data([1, 2, 3, 4, 5].map((n) => frame(n, { detection_sigma: n * 4 })))
    expect(detectionInfo(many).join(' ')).toContain('Across 5 visits the object is 4.0 to 20 times the scatter.')
  })
})

describe('the bright-star warning and the switch', () => {
  it('quotes the brightest star near', () => {
    expect(brightStarInfo([{ gmag: 6.1 }, { gmag: 4.3 }])[0]).toContain('a brightness of 4.3')
    expect(brightStarInfo([{ gmag: 4.3 }])[0]).toContain('gives it a brightness of 4.3')
    expect(brightStarInfo(null)[0]).toContain('very bright')
  })
  it('the switch says both levels have every tool, written differently, and what only Expert adds', () => {
    const text = levelInfo().join(' ')
    expect(text).toContain('Both levels have every tool in the bar at the top.')
    expect(text).toContain('plain words')
    expect(text).toContain('Expert also adds other infrared colours, a picture of what changed, and one sum of all visits.')
    expect(text).toContain('remembered on this device')
  })
})

describe('the corrected claims', () => {
  const at = (ra: number, dec: number, err: number) => ({ ra, dec, x: 50, y: 50, err_arcsec: err, snr: 50, fwhm_arcsec: 6 })
  const target = { name: 'T' } as never
  it('does not call a spot that jumped in a view with no known object real movement', () => {
    const d = { ...data([frame(1, { centroid: at(10, 20, 2) }), frame(2, { centroid: at(10, 20 + 6.3 / 3600, 2) })]), target: null }
    const text = movementInfo(d).join(' ')
    expect(text).toContain('No known object is listed at the centre')
    expect(text).not.toContain('Here it moved')
  })
  it('needs three times the position error before it calls a shift real', () => {
    const d = { ...data([frame(1, { centroid: at(10, 20, 2) }), frame(2, { centroid: at(10, 20 + 6.3 / 3600, 2) })]), target }
    expect(movementInfo(d).join(' ')).toContain('within the measuring error')
    const e = { ...data([frame(1, { centroid: at(10, 20, 1) }), frame(2, { centroid: at(10, 20 + 10.4 / 3600, 1) })]), target }
    const t = movementInfo(e).join(' ')
    expect(t).toContain('Here it moved 10.4 arcseconds, about 1.7 pixels.')
    expect(t).toContain('more than the measuring error')
  })
  it('says the same place when nothing moved, and checks the catalogue motion over the same dates', () => {
    const d = { ...data([frame(1, { centroid: at(10, 20, 1) }), frame(2, { centroid: at(10, 20, 1) })]), target }
    expect(movementInfo(d).join(' ')).toContain('in the same place as at the start')
    const p = (dec: number) => ({ ra: 10, dec, x: 50, y: 50 })
    const moving = { origin: 'gaia_nearest', source_id: '1', pmra: 0, pmdec: 10000 } as never
    const m = {
      ...data([frame(1, { centroid: at(10, 20, 1), predicted: p(20) }), frame(2, { centroid: at(10, 20 + 10 / 3600, 1), predicted: p(20 + 10.2 / 3600) })]),
      target: moving,
    }
    expect(movementInfo(m).join(' ')).toContain('should have moved 10.2 arcseconds by then. That fits what we measured.')
  })
  it('the line beside the picture hedges a jump of a view with no known object, and an error-sized one', () => {
    const none = { ...data([frame(1, { centroid: at(10, 20, 2) }), frame(2, { centroid: at(10, 20 + 6.3 / 3600, 2) })]), target: null }
    expect(motionSentence(none.frames[1], none)).toContain('No known object is listed at the centre')
    const known = { ...none, target }
    expect(motionSentence(known.frames[1], known)).toContain('within the position error')
  })
  it('says where the bright star is', () => {
    expect(brightStarInfo([{ gmag: 6.37, distance_arcmin: 0, inside_picture: true }])[0]).toContain('The star in the middle of this picture')
    expect(brightStarInfo([{ gmag: 6.75, distance_arcmin: 6.8, inside_picture: false }])[0]).toContain('just outside this picture')
    expect(brightStarInfo([{ gmag: 5, distance_arcmin: 1, inside_picture: true }])[0]).toContain('is in this picture')
  })
  it('does not say the sky flickers', () => {
    expect(detectionInfo(null).join(' ')).not.toMatch(/flicker/)
  })
  it('keeps every popover short', () => {
    const d = data()
    for (const k of KEYS) {
      const n = infoFor(k, d, [{ gmag: 4.3 }]).join(' ').split(/\s+/).length
      expect(n, k).toBeLessThanOrEqual(k === 'picture' ? 150 : 115)
    }
  })
})

describe('what the side column says in its "i" instead (real saved answers)', () => {
  const barnard = barnardJson as unknown as FramesReady
  const rwAur = rwAurJson as unknown as FramesReady
  const nova = novaJson as unknown as FramesReady
  it('a mover the catalogue agrees with: the "i" says it is drifting across the sky', () => {
    const text = movementInfo(barnard).join(' ')
    expect(text).toContain('That fits what we measured. This nearby object really is drifting across the sky.')
    expect(text).not.toContain(BRIGHTNESS_POINTER)
  })
  it('no movement, or a spot that may be another one: the "i" points to Brightness in the bar', () => {
    expect(movementInfo(rwAur)).toContain(BRIGHTNESS_POINTER)
    expect(movementInfo(rwAur).join(' ')).not.toContain('drifting')
    expect(movementInfo(nova)).toContain(BRIGHTNESS_POINTER)
    expect(BRIGHTNESS_POINTER).toBe('To see if it got brighter or fainter, press Brightness in the bar at the top.')
  })
  it('the bright-star warning on the page is one sentence and keeps its caution; the "i" says exactly where', () => {
    const middle = [{ gmag: 6.37, distance_arcmin: 0, inside_picture: true }]
    const inside = [{ gmag: 5, distance_arcmin: 1, inside_picture: true }]
    const outside = [{ gmag: 6.75, distance_arcmin: 6.8, inside_picture: false }]
    expect(brightLine(middle)).toBe('The star in the middle is so bright that its rings can look like movement.')
    expect(brightLine(inside)).toBe('A very bright star in this picture can leave rings that look like movement.')
    expect(brightLine(outside)).toBe('A very bright star nearby can leave rings that look like movement.')
    expect(brightLine(null)).toBe('A very bright star nearby can leave rings that look like movement.')
    expect(brightStarInfo(outside)[0]).toContain('just outside this picture')
    for (const b of [middle, inside, outside, null]) expect(brightLine(b)).toMatch(/rings .*look like movement\.$/)
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

describe('an angle a newcomer can picture', () => {
  it("Barnard's 10.4 arcseconds is a coin seen from about half a kilometre", () => {
    // 2.4 cm at 476 m covers 10.4 arcseconds.
    expect(coinWords(10.4)).toBe('That is about the width of a coin seen from 500 metres away.')
    expect(coinWords(6.3)).toBe('That is about the width of a coin seen from 800 metres away.')
    expect(coinWords(1)).toBe('That is about the width of a coin seen from 5 kilometres away.')
    expect(movementInfo(barnardJson as unknown as FramesReady).join(' ')).toContain('That is about the width of a coin seen from 500 metres away.')
  })
  it('the steps explanation names the three that changed while SPHEREx watched', () => {
    expect(stepsInfo().join(' ')).toContain('The last three changed while SPHEREx watched them.')
  })
})
