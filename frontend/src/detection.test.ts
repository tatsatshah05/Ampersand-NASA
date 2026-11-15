import { describe, expect, it } from 'vitest'
import type { Frame } from './api'
import {
  blendNotes,
  blendSentences,
  circleStarsSentence,
  coreNotes,
  detectionNotes,
  detectionSentence,
  detectionShort,
  isMarginal,
  measuredSentence,
  notFoundSentence,
  positionSentence,
} from './detection'

// A frame with only the fields every response has; the honesty fields are added per test.
// The numbers here are made up for the test and never shown to a visitor.
const base = {
  epoch: 1,
  date_start: '2025-05-06',
  date_end: '2025-05-06',
  date_mean: '2025-05-06',
  mjd_mean: 0,
  image: '',
  n_exposures: 1,
  wavelength_um: null,
  flagged_fraction: 0,
  saturated_pixels: 0,
  rejected_readings: 0,
  centroid: null,
  predicted: null,
} satisfies Frame

const frame = (extra: Partial<Frame>): Frame => ({ ...base, ...extra })
const centroid = (extra: object) => ({ ra: 0, dec: 0, x: 1, y: 1, err_arcsec: 0.1, snr: 5, fwhm_arcsec: 10, ...extra })

describe('detectionSentence', () => {
  it('says clear detections plainly, with whole numbers above 10', () => {
    expect(detectionSentence(frame({ detection: 'clear', detection_sigma: 11.4 }))).toBe(
      'Detected clearly, 11 times the background scatter',
    )
    expect(detectionSentence(frame({ detection: 'clear', detection_sigma: 5.26 }))).toBe(
      'Detected clearly, 5.3 times the background scatter',
    )
  })
  it('does not print a six-figure number for a very bright star', () => {
    expect(detectionSentence(frame({ detection: 'clear', detection_sigma: 95495.2 }))).toBe(
      'Detected clearly, over 1000 times the background scatter',
    )
  })
  it('labels a marginal detection as marginal and asks for care', () => {
    const f = frame({ detection: 'marginal', detection_sigma: 3.4 })
    expect(detectionSentence(f)).toBe('Marginal detection, 3.4 times the background scatter: treat with care')
    expect(isMarginal(f)).toBe(true)
  })
  it('says when nothing is detected', () => {
    const f = frame({ detection: 'none', detection_sigma: 2.5 })
    expect(detectionSentence(f)).toMatch(/^Not detected in this frame/)
    expect(detectionSentence(frame({ detection: 'none', detection_sigma: null }))).toBe('Not detected in this frame')
    // A negative value is noise: it is never shown as "-0.8 times".
    expect(detectionSentence(frame({ detection: 'none', detection_sigma: -0.8 }))).not.toContain('-')
    expect(isMarginal(f)).toBe(false)
  })
  it('says a saturated frame is too bright to measure', () => {
    expect(detectionSentence(frame({ detection: 'saturated', detection_sigma: null }))).toBe(
      'Too bright to measure here (saturated)',
    )
  })
  it('says when the strength could not be worked out', () => {
    expect(detectionSentence(frame({ detection: 'unknown', detection_sigma: null }))).toMatch(/could not be worked out/)
  })
  it('says nothing for a response without the new fields', () => {
    expect(detectionSentence(frame({}))).toBeNull()
    expect(detectionSentence(frame({ detection: null }))).toBeNull()
    expect(isMarginal(frame({}))).toBe(false)
  })
  it('never uses jargon', () => {
    for (const d of ['clear', 'marginal', 'none', 'saturated', 'unknown'] as const) {
      expect(detectionSentence(frame({ detection: d, detection_sigma: 4 }))).not.toMatch(/sigma|S\/N|signal/i)
    }
  })
})

describe('positionSentence', () => {
  it('gives the uncertainty of a saturated core rather than the fit error', () => {
    const f = frame({ centroid: centroid({ saturated_core: true, err_arcsec: 1, err_arcsec_fit: 0.03 }) })
    expect(positionSentence(f)).toContain('good to about 1″')
    expect(positionSentence(f)).not.toContain('0.03')
    const g = frame({ centroid: centroid({ saturated_core: true, err_arcsec: 2 }) })
    expect(positionSentence(g)).toContain('about 2″')
  })
  it('is silent for an unsaturated core, no marker, or an older response', () => {
    expect(positionSentence(frame({ centroid: centroid({ saturated_core: false }) }))).toBeNull()
    expect(positionSentence(frame({ centroid: centroid({}) }))).toBeNull()
    expect(positionSentence(frame({ centroid: null }))).toBeNull()
  })
})

describe('blendSentences', () => {
  it('names the neighbour and its share', () => {
    const f = frame({
      blend: [{ source_id: '1', gmag: 16.31, distance_arcsec: 4.37, light_share: 0.26 }],
    })
    expect(blendSentences(f)).toEqual([
      'About a quarter of the light here comes from a neighbouring star (Gaia G 16.3, 4.4″ away).',
    ])
  })
  it('gives a percentage when the share is not a simple fraction', () => {
    const f = frame({ blend: [{ source_id: '1', gmag: 14, distance_arcsec: 3, light_share: 0.4 }] })
    expect(blendSentences(f)[0]).toMatch(/^About 40 per cent of the light/)
  })
  it('says nearly all when the neighbour has almost every bit of the light', () => {
    const f = frame({ blend: [{ source_id: '1', gmag: 16.3, distance_arcsec: 4.2, light_share: 0.99 }] })
    expect(blendSentences(f)[0]).toMatch(/^Nearly all of the light/)
  })
  it('says a star with no share cannot be separated', () => {
    const f = frame({ blend: [{ source_id: '1', gmag: 12.18, distance_arcsec: 1.66, light_share: null }] })
    const [line] = blendSentences(f)
    expect(line).toContain('1.7″ away')
    expect(line).toContain('too close to separate')
    expect(line).toContain('include its light')
  })
  it('is empty with no neighbours or in an older response', () => {
    expect(blendSentences(frame({ blend: [] }))).toEqual([])
    expect(blendSentences(frame({}))).toEqual([])
  })
})

describe('measuredSentence and circleStarsSentence', () => {
  it('uses the backend description', () => {
    expect(measuredSentence({ description: 'The object at the requested position.' })).toBe('The object at the requested position.')
    expect(measuredSentence({})).toBeNull()
    expect(measuredSentence(undefined)).toBeNull()
  })
  const circle = {
    radius_arcsec: 15.38,
    known: true,
    stars: [{ source_id: '1', gmag: 16.31, nearest_arcsec: 4.26, farthest_arcsec: 11.36, epochs: [1, 2, 3] }],
  }
  it('names the stars in the circle and says their light is included', () => {
    const text = circleStarsSentence(circle)
    expect(text).toContain('Gaia G 16.3')
    expect(text).toContain('4.3″ to 11.4″')
    expect(text).toContain('visits 1, 2 and 3')
    expect(text).toContain('light is included')
  })
  it('says so when Gaia did not answer', () => {
    expect(circleStarsSentence({ known: false })).toMatch(/not known/)
  })
  it('is silent with no stars or in an older response', () => {
    expect(circleStarsSentence({ known: true, stars: [] })).toBeNull()
    expect(circleStarsSentence(undefined)).toBeNull()
  })
})

// The words for the table of every visit: a short word per row, and notes said once.
describe('detectionShort, for a row', () => {
  it('says the class and the number, with ">1000" for a very bright star', () => {
    expect(detectionShort(frame({ detection: 'clear', detection_sigma: 95495 }))).toBe('clear, >1000×')
    expect(detectionShort(frame({ detection: 'clear', detection_sigma: 14.64 }))).toBe('clear, 15×')
    expect(detectionShort(frame({ detection: 'marginal', detection_sigma: 3.39 }))).toBe('marginal, 3.4×')
    expect(detectionShort(frame({ detection: 'none', detection_sigma: 2.1 }))).toBe('not seen, 2.1×')
    expect(detectionShort(frame({ detection: 'none', detection_sigma: -0.8 }))).toBe('not seen')
    expect(detectionShort(frame({ detection: 'saturated', detection_sigma: null }))).toBe('saturated')
    expect(detectionShort(frame({}))).toBeNull()
  })
})

describe('notes said once for the visits they apply to', () => {
  const at = (epoch: number, extra: Partial<Frame>) => frame({ epoch, ...extra })
  it('one note for the overexposed cores that share an error', () => {
    const fs = [1, 2, 3].map((n) => at(n, { centroid: centroid({ saturated_core: n < 3, err_arcsec: n < 3 ? 1 : 0.02 }) }))
    expect(coreNotes(fs)).toEqual(['The core is overexposed in visits 1 and 2, so each position is good to about 1″, not the much smaller error of the fit.'])
    expect(coreNotes([at(1, { centroid: centroid({}) })])).toEqual([])
  })
  it('one note per neighbouring star, with the visits and its share', () => {
    const star = (share: number | null, d = 4.37) => [{ source_id: '7', gmag: 16.31, distance_arcsec: d, light_share: share }]
    expect(blendNotes([at(1, {}), at(2, {}), at(3, { blend: star(0.25) })])).toEqual([
      'Visit 3: a neighbouring star (Gaia G 16.3, 4.4″ away) supplies about a quarter of the light.',
    ])
    expect(blendNotes([at(1, { blend: star(null, 1.66) }), at(2, { blend: star(null, 1.64) })])).toEqual([
      'Visits 1 and 2: a star 1.6″ to 1.7″ away (Gaia G 16.3) is too close to separate from the target, so the position and brightness include its light.',
    ])
  })
  it('marginal, not seen and unknown, each once', () => {
    const fs = [at(1, { detection: 'marginal' }), at(2, { detection: 'none' }), at(3, { detection: 'unknown' }), at(4, { detection: 'clear' })]
    expect(detectionNotes(fs)).toEqual([
      'Only a marginal detection in visit 1 (3 to 5 times the background scatter; 5 or more is clear): treat it with care.',
      'Not detected in visit 2: at least 3 times the background scatter is needed.',
      'How strongly it is detected could not be worked out in visit 3: too few empty places to compare with.',
    ])
  })
})

describe('notFoundSentence', () => {
  it("gives the backend's reason and what was found instead", () => {
    const reason = 'The nearest source is 7.2 arcsec from the predicted position, too far to be the target.'
    const f = frame({
      centroid: null,
      centroid_reason: reason,
      nearest_source: { ra: 0, dec: 0, x: 1, y: 1, offset_arcsec: { east: 7, north: 1, total: 7.2 }, detection: 'clear', detection_sigma: 12 },
    })
    expect(notFoundSentence(f)).toBe(`No position could be measured in this frame. ${reason} That source: detected clearly, 12 times the background scatter.`)
    expect(notFoundSentence(frame({ centroid: null }))).toBe('No position could be measured in this frame.')
    expect(notFoundSentence(frame({ centroid: centroid({}) }))).toBeNull()
  })
})
