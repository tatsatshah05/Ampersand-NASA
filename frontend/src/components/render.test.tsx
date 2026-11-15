// Issue #21: responses with missing values must render without an error and without an invented number.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Frame, Target } from '../api'
import { VisitDetails } from './VisitDetails'
import { GaiaOverlay, GaiaReadout } from './GaiaOverlay'

// Hand-built objects, only to exercise rendering; the numbers mean nothing.
const frame = (over: Partial<Frame> = {}): Frame => ({
  epoch: 1,
  date_start: '2025-01-01',
  date_end: '2025-01-01',
  date_mean: '2025-01-01',
  mjd_mean: 60676,
  image: 'x.png',
  n_exposures: 2,
  wavelength_um: null,
  flagged_fraction: 0,
  saturated_pixels: 0,
  rejected_readings: 0,
  centroid: null,
  predicted: { ra: 1, dec: 1, x: 50, y: 50 },
  ...over,
})

const target = (over: Partial<Target> = {}): Target => ({
  origin: 'gaia_nearest',
  ref_epoch: 2016,
  source_id: '123',
  ra: 1,
  dec: 1,
  pmra: null,
  pmdec: null,
  parallax: null,
  gmag: null,
  ...over,
})

const overlay = (t: Target) =>
  renderToStaticMarkup(<GaiaOverlay frames={[frame()]} current={0} sizePx={100} pixelArcsec={2} target={t} />)

describe('missing values', () => {
  it('visit details with no wavelength say so', () => {
    const data = { key: 'k', ra: 1, dec: 1, fov: 0.1, detector: 1, mode: 'normal' as const, size_px: 100, pixel_arcsec: 2, target: null, frames: [frame()] }
    const html = renderToStaticMarkup(<VisitDetails data={data} />)
    expect(html).toContain('not recorded')
    expect(html).not.toContain('NaN')
  })

  it('a star without a Gaia motion gets no arrow and no motion figure', () => {
    expect(overlay(target())).not.toContain('marker-end')
    const text = renderToStaticMarkup(<GaiaReadout target={target()} />)
    expect(text).toContain('lists no motion')
    expect(text).not.toContain('per year')
  })

  it('a target from the request is not called a Gaia star', () => {
    const t = target({ origin: 'request', source_id: null, pmra: 5000, pmdec: 0 })
    const text = renderToStaticMarkup(<GaiaReadout target={t} />)
    expect(text).toContain('motion given')
    expect(text).not.toContain('Gaia DR3')
  })

  it('a motion under one image pixel a year draws no arrow and the readout says so', () => {
    const slow = target({ pmra: 20, pmdec: 10 }) // about 0.02 arcsec a year, a tenth of a pixel
    expect(overlay(slow)).not.toContain('marker-end')
    const text = renderToStaticMarkup(<GaiaReadout target={slow} />)
    expect(text).toContain('too small to draw')
    expect(overlay(target({ pmra: 4000, pmdec: 0 }))).toContain('marker-end') // 2 pixels a year
  })
})
