// The "What is it?" card as it renders, for every saved real answer at both levels. The
// static renderer runs no effects, so the view is rendered with the answer already in hand.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ILLUSTRATION_LABEL, NOTHING_HERE, NOTHING_TITLE, PLATE_TAG, type IdentifyResult } from '../identify'
import { ANSWERS, PRESSES } from '../fixtures/identify/answers'
import { Card, ObjectCardView } from './ObjectCard'

// The stylesheet as text. (A `?raw` import of a .css file comes back empty under vitest, so it
// is read from disk, as tools.test.ts does.)
const fsModule = 'node:fs'
const { readFileSync } = (await import(/* @vite-ignore */ fsModule)) as { readFileSync: (p: URL, encoding: string) => string }
const cssText = readFileSync(new URL('./ObjectCard.css', import.meta.url), 'utf8')

const html = (r: IdentifyResult, level: 'beginner' | 'expert', name?: string, look = false, retry = false) =>
  renderToStaticMarkup(<Card result={r} level={level} name={name} onLook={look ? () => {} : undefined} onRetry={retry ? () => {} : undefined} />)
const text = (h: string) =>
  h
    .replace(/<\/?(span|wbr)[^>]*>/g, '') // the break points inside a column name are not spaces
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
const copy = (r: IdentifyResult): IdentifyResult => JSON.parse(JSON.stringify(r))

describe('every test object, both levels', () => {
  for (const [key, r] of Object.entries({ ...ANSWERS, ...PRESSES })) {
    for (const level of ['beginner', 'expert'] as const) {
      it(`${key}, ${level}`, () => {
        const h = html(r, level)
        const drawn = r.portrait.temperature != null || r.portrait.radius != null || r.derived.distance != null
        // The label, and the tag inside the drawing, are there exactly when something is drawn.
        expect(h.includes(ILLUSTRATION_LABEL)).toBe(drawn)
        expect(h.includes(PLATE_TAG)).toBe(drawn)
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
    expect(text(h)).toContain('Nearest star')
    expect(text(h)).toContain('The nearest star, Proxima Centauri, is 4.25 light-years away.')
  })
  it('the figure is named by its label; the drawing says its colour, scale and what is left out; the scale line is not read twice', () => {
    const h = html(ANSWERS.barnard, 'beginner', "Barnard's Star")
    const label = /<p class="oc-plate-label" id="([^"]+)">/.exec(h)![1]
    expect(h).toContain(`<figure class="oc-plate" aria-labelledby="${label}">`)
    expect(h).toContain(
      "aria-label=\"Illustration drawn from measurements, not a photograph. Barnard&#x27;s Star as an orange disc, the colour of a perfect glowing body at 3,100 kelvin, 0.20 times the Sun&#x27;s width, beside the Sun (white with a warm tint) to scale. Not drawn: its 4 planets, surface details.\"",
    )
    expect(h).toMatch(/<svg class="oc-scale"[^>]*aria-hidden="true"/)
  })
  it('Epsilon Indi B: no colour is drawn for a brown-dwarf pair, and no disc without a size', () => {
    const h = html(ANSWERS.epsindib, 'beginner')
    expect(h).not.toContain('radialGradient')
    expect(h).not.toContain('#ff6500') // the 1,417 K blackbody colour
    expect(text(h)).toContain('So no disc is drawn: its size is not measured either.')
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
  it('beginner: name, kind, facts with their sources, what is not known, and what Gaia and SIMBAD are', () => {
    const t = text(html(ANSWERS.barnard, 'beginner', "Barnard's Star"))
    expect(t).toContain("Barnard's Star")
    expect(t).toContain('SIMBAD lists it as an M dwarf: a small, cool star (astronomers call these red dwarfs).')
    expect(t).toContain('It is about 5.96 light-years away. The light we see left it 6 years ago. Gaia')
    expect(t).toContain('SIMBAD lists 924 scientific papers that mention it. SIMBAD')
    expect(t).toContain('Not in the catalogues we asked:')
    expect(t).toContain('Gaia is a space telescope')
    expect(t).not.toMatch(/parallax|proper motion|magnitude|spectral type|effective temperature|teff_|radius_flame/i)
  })
  it('expert: identifiers, how it was chosen, every value with its column, and the neighbours', () => {
    const t = text(html(ANSWERS.barnard, 'expert'))
    expect(t).toContain('Gaia DR3 4472832130942575872')
    expect(t).toContain("NAME Barnard's star")
    expect(t).toContain('Searched within 4 arcsec of RA 269.446267, Dec +4.768222 at 2026.000')
    expect(t).toContain('gaia_source.parallax')
    expect(t).toContain('546.98 mas')
    expect(t).toContain('± 0.04')
    expect(t).toContain('astrophysical_parameters.teff_gspphot')
    expect(t).toContain("Gaia DR3's model estimates, fitted to its light and parallax")
    expect(t).toContain('Quality flag flags_gspspec')
    expect(t).toContain('Gaia DR3 4472835979229621248')
    expect(t).toContain('Other catalogued sources within 15 arcsec')
    expect(t).not.toContain('0.000005') // no digits nobody can use
  })
  it('RW Aurigae: titled as the star it is, the system named, and the pair said at both levels', () => {
    for (const level of ['beginner', 'expert'] as const) {
      const t = text(html(ANSWERS.rwaur, level, 'RW Aurigae'))
      expect(t).toContain('RW Aurigae A')
      expect(t).toContain('It is one of the stars of RW Aurigae, the system you chose.')
      expect(t).toContain('This blur holds 2 catalogued stars, not one: RW Aurigae B, fainter')
    }
  })
  it('R Draconis: the faint sources beside it are called sources and may not be real, at both levels', () => {
    for (const level of ['beginner', 'expert'] as const) {
      const t = text(html(ANSWERS.rdra, level))
      expect(t).toContain('They may not be real')
      expect(t).not.toContain('fainter stars')
    }
    expect(text(html(ANSWERS.rdra, 'expert'))).toContain('possibly not real: 2-parameter solution, 4 visibility periods')
  })
  it('the candidate place: exactly that nothing is listed, how far we looked, the nearest catalogued thing, and no picture', () => {
    for (const level of ['beginner', 'expert'] as const) {
      const h = html(ANSWERS.candidate, level, undefined, true)
      const t = text(h)
      expect(t).toContain(NOTHING_TITLE)
      expect(t).toContain(NOTHING_HERE)
      expect(t).toContain('We looked within 4 arcseconds of the place')
      expect(t).toContain('The nearest catalogued thing is Gaia DR3 5964332607636528768, 4.9 arcseconds away, inside the same SPHEREx pixel.')
      expect(t).toContain('5964332607629792768') // the star about 10 arcsec away, as a neighbour
      expect(t).toContain('Look at this place')
      expect(t).not.toContain('Look at this one')
      expect(h).not.toContain('<svg')
    }
  })
  it('the "Look at this one" button is there only with a callback', () => {
    expect(html(ANSWERS.barnard, 'beginner', undefined, true)).toContain('Look at this one')
    expect(html(ANSWERS.barnard, 'beginner')).not.toContain('Look at this one')
  })
})

describe('states', () => {
  it('loading and failure, with a way to try again', () => {
    expect(renderToStaticMarkup(<ObjectCardView load={{ state: 'loading' }} level="beginner" />)).toContain('Looking this place up in Gaia and SIMBAD')
    const failed = renderToStaticMarkup(
      <ObjectCardView load={{ state: 'error', message: 'The server could not be reached.' }} level="expert" onRetry={() => {}} />,
    )
    expect(failed).toContain('The lookup could not be done. The server could not be reached.')
    expect(failed).toContain('Try again')
  })
  it('a catalogue that did not answer is named, nothing is filled in, and it can be asked again', () => {
    // The saved Barnard's Star answer with Gaia's part taken away, as when Gaia does not answer.
    const r = copy(ANSWERS.barnard)
    r.gaia = null
    r.services.gaia = { ...r.services.gaia, answered: false, via: null, error: 'Gaia DR3 did not answer' }
    r.unreachable = ['Gaia DR3']
    r.portrait = { temperature: null, radius: null, luminosity: null }
    r.derived = { from: null, distance: null, distance_estimate: null, motion: null, speed: null }
    const t = text(html(r, 'beginner', undefined, false, true))
    expect(t).toContain('Gaia DR3 did not answer just now, so this card shows only what SIMBAD has.')
    expect(t).toContain('Try again')
    expect(t).toContain('Not known right now, because Gaia DR3 did not answer: its temperature, its size')
    expect(t).not.toContain('light-years')
    expect(t).not.toContain(ILLUSTRATION_LABEL)
  })
  it('SIMBAD down at the candidate place: Gaia\'s nearest source and neighbours are still shown', () => {
    const r = copy(ANSWERS.candidate)
    r.nothing_catalogued = null
    r.unreachable = ['SIMBAD']
    r.services.simbad = { ...r.services.simbad, answered: false, via: null }
    const t = text(html(r, 'beginner'))
    expect(t).toContain('Gaia lists nothing within 4 arcseconds of the place. SIMBAD did not answer')
    expect(t).toContain('The nearest catalogued thing is Gaia DR3 5964332607636528768')
    expect(t).toContain('10.4 arcseconds away: Gaia DR3 5964332607629792768')
    expect(t).not.toContain(NOTHING_HERE)
  })
  it('nothing could be checked when neither catalogue answered', () => {
    const r = copy(ANSWERS.candidate)
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

describe('colours and layout rules', () => {
  it('the card uses only the page tokens; literal colours appear only in the picture', () => {
    const css = cssText.replace(/\/\*[\s\S]*?\*\//g, '')
    expect(css.length).toBeGreaterThan(1000) // the file was really read
    for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const selector = m[1].trim()
      const literal = /#[0-9a-f]{3,8}\b|rgba?\(/i.test(m[2])
      if (literal) expect(selector, selector).toMatch(/^\.oc-plate/)
    }
    expect(css).toContain('color: var(--on-ink)')
  })
  it('the narrow layout follows the card, not the screen', () => {
    const css = cssText.replace(/\/\*[\s\S]*?\*\//g, '')
    expect(css).toContain('container-type: inline-size')
    expect(css).toContain('@container (max-width: 560px)')
    expect(css).not.toContain('@media (max-width: 560px)')
  })
})
