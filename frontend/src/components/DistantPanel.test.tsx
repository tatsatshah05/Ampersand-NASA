// The distant-world answer as it renders, for each of the three saved answers. The static
// renderer does not run effects, so the answer component is rendered directly.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { DistantResult } from '../distant'
import real from '../fixtures/distant/wise0855_real.json'
import found from './../fixtures/distant/wise0855_planted_found.json'
import missed from '../fixtures/distant/wise0855_planted_missed.json'
import { Answer, DistantMarkers, DistantPanel } from './DistantPanel'

const html = (f: unknown) => renderToStaticMarkup(<Answer result={(f as { result: DistantResult }).result} />)
const result = (f: unknown) => (f as { result: DistantResult }).result

describe('the real answer', () => {
  const h = html(real)
  it('shows the backend headline and the limit table, and no SIMULATION', () => {
    expect(h).toContain(result(real).answer)
    expect(h).toContain('Faintest it could be (mJy)')
    expect(h).toContain(`<td>${result(real).limit[0].distance_au.toLocaleString('en-US')}</td>`)
    expect(h).toContain('Exposures used')
    expect(h).toContain('the densest few days of each visit.')
    expect(h).toContain('chance made no links in this picture')
    expect(h).not.toContain('SIMULATION')
    expect(h).not.toContain('Candidate')
  })
  it('keeps the limits and the credit', () => {
    expect(h).toContain('<details')
    expect(h).toContain('finding nothing is the expected answer')
    expect(h).toContain('Credit: NASA/JPL-Caltech SPHEREx')
  })
  it('never says a forbidden word', () => {
    for (const f of [real, found, missed]) expect(html(f).replace(result(f).notice ?? '', '')).not.toMatch(/sigma|discover(y|ed)|new planet|found a planet|detected/i)
  })
})

describe('the planted object, found', () => {
  const h = html(found)
  it('carries the banner, the planted distance and the candidate', () => {
    expect(h).toContain('SIMULATION.')
    expect(h).toContain(result(found).notice)
    expect(h).toContain('Planted at 2,559 times the Earth-Sun distance')
    expect(h).toContain('Candidate: about 2,558 times the Earth-Sun distance (between 2,534 and 2,583)')
    expect(h).toContain('It is seen in one detector only.')
    expect(h).toContain('Open a view that follows it')
    expect(h).toContain('ui=expert')
  })
})

describe('the planted object, missed', () => {
  it('carries the banner and the backend explanation', () => {
    const h = html(missed)
    expect(h).toContain('SIMULATION.')
    expect(h).toContain(result(missed).answer)
    expect(h).toContain('The truth.')
    expect(h).toContain('Faintest it could be (mJy)')
  })
})

describe('the panel before an answer', () => {
  const panel = renderToStaticMarkup(<DistantPanel query={{ ra: 133.76, dec: -7.24, fov: 0.1 }} onClose={() => undefined} />)
  it('says what it searches, widened to 0.2 degrees, and offers the simulation', () => {
    expect(panel).toContain('0.2 degrees across in detectors 5 and 6')
    expect(panel).toContain('Try it on a planted object (simulation)')
    expect(panel).not.toContain('<strong>SIMULATION.</strong>')
  })
})

describe('the markers', () => {
  const grid = { ra: 133.7598, dec: -7.2422, sizePx: 300, pixelArcsec: 2 }
  const cands = result(found).candidates
  it('draws a ring for each visit inside the picture and emphasises the current one', () => {
    const svg = renderToStaticMarkup(<DistantMarkers candidates={cands} grid={grid} scale={1} epoch={1} simulation />)
    expect(svg).toContain('SIMULATION')
    expect(svg).toContain('distant-ring now')
    expect(svg).toContain('<polyline')
    expect((svg.match(/<circle/g) ?? []).length).toBeGreaterThan(0)
  })
  it('skips positions outside the view and has no SIMULATION label for a real search', () => {
    const far = { ...grid, ra: 10, dec: 40 }
    expect(renderToStaticMarkup(<DistantMarkers candidates={cands} grid={far} scale={1} epoch={null} />)).not.toContain('<circle')
    expect(renderToStaticMarkup(<DistantMarkers candidates={cands} grid={grid} scale={1} epoch={null} />)).not.toContain('>SIMULATION<')
  })
})
