// The six tool panels as Beginner sees them, rendered with real saved answers (src/fixtures/tools):
// plain words outside one closed fold, and Expert exactly as before when no level is given.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { LightcurveResponse } from '../lightcurve'
import type { SpectrumResponse } from '../spectrum'
import type { SearchResult } from '../search'
import type { SmallBodiesResponse } from '../smallbodies'
import { SCIENCE_WORDS as BANNED, BRIGHTNESS_LOADING, SCIENCE_FOLD, SMALLBODIES_LOADING, SPECTRUM_LOADING, SEARCH_WAITING, DISTANT_WAITING, brightnessResult } from '../plain'
import { BrightnessPanel, PlainBrightness } from './BrightnessPanel'
import { ContextView } from './ContextView'
import { DistantPanel } from './DistantPanel'
import { ScienceFold } from './ScienceFold'
import { PlainSearch, SearchPanel } from './SearchPanel'
import { PlainSmallBodies, SmallBodiesPanel } from './SmallBodiesPanel'
import { PlainSpectrum, SpectrumPanel } from './SpectrumPanel'
import barnardLc from '../fixtures/tools/barnard_lightcurve.json'
import rwaurLc from '../fixtures/tools/rwaur_lightcurve.json'
import wiseLc from '../fixtures/tools/wise0855_lightcurve.json'
import serpLc from '../fixtures/tools/serpsouth_lightcurve.json'
import barnardSp from '../fixtures/tools/barnard_spectrum.json'
import rwaurSp from '../fixtures/tools/rwaur_spectrum.json'
import wiseSp from '../fixtures/tools/wise0855_spectrum.json'
import serpSp from '../fixtures/tools/serpsouth_spectrum.json'
import barnardSe from '../fixtures/tools/barnard_search.json'
import serpSe from '../fixtures/tools/serpsouth_search.json'
import barnardSb from '../fixtures/tools/barnard_smallbodies.json'
import rwaurSb from '../fixtures/tools/rwaur_smallbodies.json'

/** The visible words of rendered markup, and the words given to screen readers and tooltips. */
function words(html: string) {
  const decode = (t: string) => t.replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  const text = decode(html.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim()
  const attributes = [...html.matchAll(/\s(?:aria-label|alt|title)="([^"]*)"/g)].map((m) => decode(m[1]))
  return { text, attributes }
}
const expectPlain = (html: string) => {
  const { text, attributes } = words(html)
  expect(text).not.toMatch(BANNED)
  expect(text).not.toMatch(/discover|new planet/i)
  for (const a of attributes) expect(a).not.toMatch(BANNED)
}

const request = { kind: 'target' as const, ra: 269.446267, dec: 4.768222 }
const noop = () => undefined

describe('the closed fold', () => {
  it('shows only its summary until it is opened', () => {
    const html = renderToStaticMarkup(
      <ScienceFold>
        <p>flux in mJy per detector</p>
      </ScienceFold>,
    )
    expect(html).toBe(`<details class="fold science-fold"><summary>${SCIENCE_FOLD}</summary></details>`)
  })
})

describe('Brightness in Beginner', () => {
  for (const [name, f] of Object.entries({ barnard: barnardLc, rwaur: rwaurLc, wise: wiseLc, serp: serpLc })) {
    it(`${name}: the sentences and a chart in plain words`, () => {
      const data = f as unknown as LightcurveResponse
      const html = renderToStaticMarkup(<PlainBrightness data={data} />)
      expectPlain(html)
      for (const line of brightnessResult(data)) expect(words(html).text).toContain(line)
      expect(html).toContain('class="brightness-grid"')
      expect(html).toContain('Band ')
      expect(html).not.toMatch(/>D\d</)
    })
  }
  it('the panel itself, while it measures: plain words, the same request', () => {
    const html = renderToStaticMarkup(<BrightnessPanel request={request} onClose={noop} level="beginner" />)
    expectPlain(html)
    expect(html).toContain(BRIGHTNESS_LOADING)
    expect(html).toContain('<h2>Brightness over time</h2>')
  })
  it('Expert is unchanged and is the default', () => {
    const html = renderToStaticMarkup(<BrightnessPanel request={request} onClose={noop} />)
    expect(html).toContain('Measuring the target in every exposure of all six detectors')
    expect(html).not.toContain('plain-')
    expect(renderToStaticMarkup(<BrightnessPanel request={request} onClose={noop} level="expert" />)).toBe(html)
  })
})

describe('Colours in Beginner', () => {
  for (const [name, f] of Object.entries({ barnard: barnardSp, rwaur: rwaurSp, wise: wiseSp, serp: serpSp })) {
    it(`${name}: what the tool states, and the chart's words plain`, () => {
      const html = renderToStaticMarkup(<PlainSpectrum data={f as unknown as SpectrumResponse} />)
      expectPlain(html)
      expect(html).toContain('Infrared colour (micrometres)')
      expect(html).not.toContain('Brightness (mJy)')
    })
  }
  it("Barnard's Star's chart marks the overexposed photos as too bright", () => {
    expect(renderToStaticMarkup(<PlainSpectrum data={barnardSp as unknown as SpectrumResponse} />)).toContain('>too bright<')
  })
  it('the panel while it measures, and Expert unchanged', () => {
    const plain = renderToStaticMarkup(<SpectrumPanel request={request} onClose={noop} level="beginner" />)
    expectPlain(plain)
    expect(plain).toContain(SPECTRUM_LOADING)
    expect(renderToStaticMarkup(<SpectrumPanel request={request} onClose={noop} />)).toContain('Spectrum: brightness at each wavelength')
  })
})

describe('Find changes in Beginner', () => {
  it('numbered lines that match the rings on the picture, in plain words', () => {
    const html = renderToStaticMarkup(<PlainSearch result={(serpSe as unknown as { result: SearchResult }).result} onLook={noop} />)
    expectPlain(html)
    expect(html).toContain('1.</span>')
    expect(html).toContain('4.</span>')
    expect(html).toContain('Only a candidate')
    expectPlain(renderToStaticMarkup(<PlainSearch result={(barnardSe as unknown as { result: SearchResult }).result} onLook={noop} />))
  })
  it('while it runs: one sentence that never changes, and no moving bar', () => {
    const html = renderToStaticMarkup(<SearchPanel query={{ ra: 1, dec: 2, fov: 0.1 }} onClose={noop} onLook={noop} onObjects={noop} level="beginner" />)
    expectPlain(html)
    expect(html).toContain(SEARCH_WAITING)
    expect(html).not.toContain('class="progress"')
    // Expert keeps its progress line and bar.
    expect(renderToStaticMarkup(<SearchPanel query={{ ra: 1, dec: 2, fov: 0.1 }} onClose={noop} onLook={noop} onObjects={noop} />)).toContain('class="progress"')
  })
})

describe('Far-off planet in Beginner', () => {
  it('while it runs: one sentence, plain', () => {
    const html = renderToStaticMarkup(<DistantPanel query={{ ra: 1, dec: 2, fov: 0.1 }} onClose={noop} level="beginner" />)
    expectPlain(html)
    expect(html).toContain(DISTANT_WAITING)
    expect(html).toContain('Is a far-off planet here?')
    expect(renderToStaticMarkup(<DistantPanel query={{ ra: 1, dec: 2, fov: 0.1 }} onClose={noop} />)).toContain('Search for a distant world (Planet X)')
  })
})

describe('Asteroids in Beginner', () => {
  it('each known body with its photos, captioned in plain words', () => {
    const html = renderToStaticMarkup(<PlainSmallBodies data={rwaurSb as unknown as SmallBodiesResponse} />)
    expectPlain(html)
    expect(html).toContain('<h3>Asteroid 103643</h3>')
    expect(html).toContain('15 Sep 2026')
    expectPlain(renderToStaticMarkup(<PlainSmallBodies data={barnardSb as unknown as SmallBodiesResponse} />))
  })
  it('while it looks up', () => {
    const html = renderToStaticMarkup(<SmallBodiesPanel query={{ ra: 1, dec: 2, fov: 0.1, detector: 5 }} onClose={noop} level="beginner" />)
    expectPlain(html)
    expect(html).toContain(SMALLBODIES_LOADING)
  })
})

describe('Other telescopes in Beginner', () => {
  it('plain words, the telescope to choose, the Gaia switch in the closed fold', () => {
    const html = renderToStaticMarkup(<ContextView ra={269.446267} dec={4.768222} fov={0.1} level="beginner" onClose={noop} />)
    expectPlain(html)
    expect(html).toContain('This patch through other telescopes')
    expect(html).toContain('WISE, infrared (2010 and 2011)')
    expect(html).toContain('class="aladin"')
    expect(html).not.toContain('Gaia DR3 stars')
    expect(html).toContain('>Close<')
  })
  it('Expert is unchanged without a Close button', () => {
    const html = renderToStaticMarkup(<ContextView ra={269.446267} dec={4.768222} fov={0.1} />)
    expect(html.startsWith('<section class="panel context" aria-label="Sky context"><h2>Sky context</h2><p class="hint">Other surveys')).toBe(true)
    expect(html).toContain('Gaia DR3 stars')
    expect(html).not.toContain('Close')
  })
})
