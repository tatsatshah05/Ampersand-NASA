import { describe, expect, it } from 'vitest'
import { bodyVerdict, groupByBody, plainSummary, whenInWords, type SmallBodyCrossing } from './smallbodies'

// Two crossings as /api/smallbodies returned them for a patch around asteroid 4 Vesta, 2026-07-16
// (detector 5), and one of 4959 Niinoama in the same patch in 2025. Only the fields the helpers
// read are filled in.
const crossing = (over: Partial<SmallBodyCrossing>): SmallBodyCrossing => ({
  id: '000',
  name: '4 Vesta',
  designation: 'A807 FA',
  kind: 'asteroid',
  exposure: { obs_id: '2026W29_2A_0088_2', detector: 5, mjd: 61237.921, time: '2026-07-16T22:05:42Z', visit: 3, wavelength_um: [3.811, 4.43] },
  predicted: { ra: 23.35607, dec: 1.50052, x: 89.21, y: 89.57, observer: 'SPHEREx spacecraft (JPL Horizons -163182)' },
  vmag: 7.7,
  rate_arcsec_per_hour: 40.4,
  measurement: null,
  verdict: 'seen',
  summary: null,
  nearby_gaia_star: null,
  picture: null,
  ...over,
})

describe('whenInWords', () => {
  it('writes the backend time as a date and a UTC time', () => {
    expect(whenInWords('2026-07-16T22:05:42Z')).toBe('16 July 2026, 22:05 UTC')
  })
  it('leaves what it cannot read alone', () => {
    expect(whenInWords('later')).toBe('later')
  })
})

describe('groupByBody', () => {
  it('puts the exposures of one body together, in order of first appearance', () => {
    const list = [crossing({ id: '001', name: '4959 Niinoama' }), crossing({ id: '002' }), crossing({ id: '003', name: '4959 Niinoama' })]
    const groups = groupByBody(list)
    expect(groups.map((g) => g.map((c) => c.id))).toEqual([['001', '003'], ['002']])
  })
  it('gives nothing for nothing', () => {
    expect(groupByBody([])).toEqual([])
  })
})

describe('bodyVerdict', () => {
  it('says how many exposures show a source', () => {
    const group = [crossing({ verdict: 'unmeasurable' }), crossing({ verdict: 'seen' }), crossing({ verdict: 'seen' })]
    expect(bodyVerdict(group)).toBe('A source is seen at the predicted place in 2 of 3 exposures it was predicted in.')
  })
  it('does not call a faint source a detection', () => {
    expect(bodyVerdict([crossing({ verdict: 'possible' }), crossing({ verdict: 'not_seen' })])).toBe(
      'A faint source may be at the predicted place in 1 of 2 exposures; nothing secure.',
    )
  })
  it('does not credit a fixed source to the body', () => {
    expect(bodyVerdict([crossing({ verdict: 'fixed_source' })])).toBe(
      'The source at the predicted place is also there on other days, so it is a star or galaxy, not this body.',
    )
  })
  it('says plainly when nothing is seen, and when nothing could be measured', () => {
    expect(bodyVerdict([crossing({ verdict: 'not_seen' })])).toBe('Nothing is seen at the predicted place in the 1 exposure.')
    expect(bodyVerdict([crossing({ verdict: 'unmeasurable' })])).toBe('Not measured in the 1 exposure.')
  })
})


describe('plainSummary', () => {
  it('says the number in words instead of "sigma"', () => {
    expect(plainSummary('A source is seen here at 5.2 sigma.')).toBe('A source is seen here at 5.2 times its measuring error.')
    expect(plainSummary('A faint source may be here (4.2 sigma), not strong enough to be sure.')).toBe(
      'A faint source may be here (4.2 times its measuring error), not strong enough to be sure.',
    )
    expect(plainSummary('Not measured: a pixel at the place is flagged as bad in this exposure.')).toBe(
      'Not measured: a pixel at the place is flagged as bad in this exposure.',
    )
  })
})
