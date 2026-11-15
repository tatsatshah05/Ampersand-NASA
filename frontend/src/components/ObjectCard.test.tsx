// The "What is it?" card as it renders, for every saved real answer at both levels. The
// static renderer runs no effects, so the view is rendered with the answer already in hand.
import cssText from './ObjectCard.css?raw'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ILLUSTRATION_LABEL, NO_NAME, NOTHING_HERE, type IdentifyResult } from '../identify'
import { ANSWERS } from '../fixtures/identify/answers'
import { Card, ObjectCardView } from './ObjectCard'

const html = (r: IdentifyResult, level: 'beginner' | 'expert', name?: string, look = false) =>
  renderToStaticMarkup(<Card result={r} level={level} name={name} onLook={look ? () => {} : undefined} />)
const text = (h: string) =>
  h
    .replace(/<\/?(span|wbr)[^>]*>/g, '') // the break points inside a column name are not spaces
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')

describe('every test object, both levels', () => {
  for (const [key, r] of Object.entries(ANSWERS)) {
    for (const level of ['beginner', 'expert'] as const) {
      it(`${key}, ${level}`, () => {
        const h = html(r, level)
        const drawn = r.portrait.temperature != null || r.portrait.radius != null || r.derived.distance != null
        // The label is there exactly when something is drawn.
        expect(h.includes(ILLUSTRATION_LABEL)).toBe(drawn)
        expect(h.includes('<svg')).toBe(drawn)
        expect(h).toContain('Catalogues: ESA Gaia DR3; SIMBAD (CDS, Strasbourg).')
      })
    }
  }
})

describe('the picture', () => {
  it("Barnard's Star: a glowing disc to scale beside the Sun, and the distance line", () => {
    const h = html(ANSWERS.barnard, 'beginner', "Barnard's Star")
    expect(h.match(/<radialGradient/g)).toHaveLength(2) // the star and the Sun
    expect(h).toContain('stop-color="#ffbb74"') // 3,100 K at the centre of its disc
    expect(h).toContain('stop-color="#fff1ea"') // the Sun, 5,772 K
    expect(text(h)).toContain('Sun')
    expect(text(h)).not.toContain('Jupiter') // 0.2022 solar radii is not under a fifth
    expect(text(h)).toContain('Nearest star, 4.25')
  })
  it('Epsilon Indi B: one glowing disc, no Sun beside it', () => {
    const h = html(ANSWERS.epsindib, 'beginner')
    expect(h.match(/<radialGradient/g)).toHaveLength(1)
    expect(h).toContain('aria-label="eps Ind B, size not measured"')
  })
  it('WISE 0855, RW Aurigae and R Draconis: no disc at all, only the distance line', () => {
    for (const key of ['wise0855', 'rwaur', 'rdra']) {
      const h = html(ANSWERS[key], 'beginner')
      expect(h).not.toContain('<circle cx="200"')
      expect(h).not.toContain('radialGradient')
      expect(h).toContain('No disc: neither its temperature nor its size is in the catalogues we asked.')
    }
  })
  it('never says "too cool to glow" without a measured temperature', () => {
    for (const r of Object.values(ANSWERS)) expect(html(r, 'beginner')).not.toContain('too cool to glow')
  })
})

describe('the words', () => {
  it('beginner: name, kind, facts with their sources, and what is not known', () => {
    const t = text(html(ANSWERS.barnard, 'beginner', "Barnard's Star"))
    expect(t).toContain("Barnard's Star")
    expect(t).toContain('SIMBAD lists it as an M dwarf: a small, cool, red star.')
    expect(t).toContain('It is about 5.96 light-years away. The light we see left it 6 years ago. Gaia')
    expect(t).toContain('SIMBAD lists 924 scientific papers about it. SIMBAD')
    expect(t).toContain('Not in the catalogues we asked:')
    expect(t).not.toMatch(/parallax|proper motion|magnitude|spectral type|effective temperature/i)
  })
  it('expert: identifiers, every value with its column, and the neighbours', () => {
    const t = text(html(ANSWERS.barnard, 'expert'))
    expect(t).toContain('Gaia DR3 4472832130942575872')
    expect(t).toContain("NAME Barnard's star")
    expect(t).toContain('gaiadr3.gaia_source.parallax')
    expect(t).toContain('546.976 mas')
    expect(t).toContain('gaiadr3.astrophysical_parameters.teff_gspphot')
    expect(t).toContain('0.00339771 to 0.00339839') // a range narrower than four digits gets more
    expect(t).toContain('Gaia DR3 4472835979229621248')
    expect(t).toContain('Other catalogued sources within 15 arcsec')
  })
  it('RW Aurigae: both levels say the blur holds two stars', () => {
    for (const level of ['beginner', 'expert'] as const) {
      expect(text(html(ANSWERS.rwaur, level, 'RW Aurigae'))).toContain('This blur holds 2 catalogued stars, not one: RW Aur A, brighter')
    }
  })
  it('the candidate place: exactly that nothing is listed, the nearest catalogued thing, and no picture', () => {
    for (const level of ['beginner', 'expert'] as const) {
      const t = text(html(ANSWERS.candidate, level))
      expect(t).toContain(NO_NAME)
      expect(t).toContain(NOTHING_HERE)
      expect(t).toContain('The nearest catalogued thing is Gaia DR3 5964332607636528768, 4.9 arcseconds away, inside the same SPHEREx pixel.')
      expect(t).toContain('5964332607629792768') // the star about 10 arcsec away, as a neighbour
    }
  })
  it('the "Look at this one" button is there only with a callback', () => {
    expect(html(ANSWERS.barnard, 'beginner', undefined, true)).toContain('Look at this one')
    expect(html(ANSWERS.barnard, 'beginner')).not.toContain('Look at this one')
  })
})

describe('states', () => {
  it('loading and failure', () => {
    expect(renderToStaticMarkup(<ObjectCardView load={{ state: 'loading' }} level="beginner" />)).toContain(
      'Looking this place up in Gaia and SIMBAD',
    )
    const failed = renderToStaticMarkup(<ObjectCardView load={{ state: 'error', message: 'The server could not be reached.' }} level="expert" />)
    expect(failed).toContain('The lookup could not be done. The server could not be reached.')
  })
  it('a catalogue that did not answer is named, and nothing is filled in', () => {
    // The saved Barnard's Star answer with Gaia's part taken away, as when Gaia does not answer.
    const r: IdentifyResult = JSON.parse(JSON.stringify(ANSWERS.barnard))
    r.gaia = null
    r.services.gaia = { ...r.services.gaia, answered: false, via: null, error: 'Gaia DR3 did not answer' }
    r.unreachable = ['Gaia DR3']
    r.portrait = { temperature: null, radius: null, luminosity: null }
    r.derived = { from: null, distance: null, distance_estimate: null, motion: null, speed: null }
    const t = text(renderToStaticMarkup(<Card result={r} level="beginner" />))
    expect(t).toContain('Gaia DR3 did not answer just now, so this card shows only what SIMBAD has.')
    expect(t).not.toContain('light-years')
    expect(t).not.toContain(ILLUSTRATION_LABEL)
  })
  it('nothing could be checked when neither catalogue answered', () => {
    const r: IdentifyResult = JSON.parse(JSON.stringify(ANSWERS.candidate))
    r.nothing_catalogued = null
    r.unreachable = ['Gaia DR3', 'SIMBAD']
    r.services.gaia.answered = false
    r.services.simbad.answered = false
    r.neighbours = []
    r.nearest_catalogued = null
    const t = text(renderToStaticMarkup(<Card result={r} level="beginner" />))
    expect(t).toContain('It could not be checked whether anything is listed here, because Gaia DR3 and SIMBAD did not answer.')
    expect(t).not.toContain(NOTHING_HERE)
  })
})

describe('colours', () => {
  it('the card uses only the page tokens; literal colours appear only in the picture', () => {
    const css = cssText.replace(/\/\*[\s\S]*?\*\//g, '')
    for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const selector = m[1].trim()
      const literal = /#[0-9a-f]{3,8}\b|rgba?\(/i.test(m[2])
      if (literal) expect(selector, selector).toMatch(/^\.oc-plate/)
    }
  })
})
