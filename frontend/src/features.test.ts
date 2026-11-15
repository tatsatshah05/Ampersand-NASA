// Every feature in one bar: the list, its words at each level, and the bar it makes.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { FeatureBar, type FeatureLinks } from './components/FeatureBar'
import { NATIVE_PIXEL_ARCSEC } from './api'
import { decimalYear, feature, FEATURES, isToolKey, PRESS_RADIUS_ARCSEC, pressOnPicture, scrollToShow, TOOL_KEYS, type FeatureKey } from './features'

// The words a newcomer must not meet (the same list as the checks of the Beginner panels).
const SCIENTISTS_WORDS = /\b(sigma|flux|fluxes|epoch|epochs|detector|detectors|centroid|centroids|mJy|aperture|photometry|ephemeris|S\/N)\b|σ/
const words = (s: string) => s.split(/\s+/).filter(Boolean).length
const sentences = (s: string) => s.split(/(?<=[.!?])\s+/)

describe('the list of features', () => {
  it('has the ten features, in the order of the bar, with the label of each level', () => {
    expect(FEATURES.map((f) => [f.key, f.label.beginner, f.label.expert])).toEqual([
      ['watch', 'Watch', 'Viewer'],
      ['brightness', 'Brightness', 'Light curve'],
      ['spectrum', 'Colours', 'Spectrum'],
      ['search', 'Find changes', 'Blind search'],
      ['distant', 'Far-off planet', 'Planet X search'],
      ['smallbodies', 'Asteroids', 'Small bodies'],
      ['context', 'What is it?', 'Object card'],
      ['practise', 'Practise', 'Training'],
      ['vote', 'Vote', 'Watchlist'],
      ['tools', 'Three tools', 'Methods'],
    ])
  })

  it('knows which are the picture, the six tools and the three screens', () => {
    expect(FEATURES.map((f) => f.kind)).toEqual(['home', 'tool', 'tool', 'tool', 'tool', 'tool', 'tool', 'screen', 'screen', 'screen'])
    expect(TOOL_KEYS).toEqual(['brightness', 'spectrum', 'search', 'distant', 'smallbodies', 'context'])
    expect(isToolKey('context')).toBe(true)
    expect(isToolKey('watch')).toBe(false)
    expect(isToolKey('vote')).toBe(false)
    expect(isToolKey('Spectrum')).toBe(false)
    expect(feature('distant').label.expert).toBe('Planet X search')
  })

  it('says in one sentence what each one is, at each level, never just its name again', () => {
    for (const f of FEATURES) {
      for (const level of ['beginner', 'expert'] as const) {
        const about = f.about[level]
        expect(sentences(about), about).toHaveLength(1)
        expect(about).toMatch(/\.$/)
        expect(about).not.toBe(f.label[level])
        expect(about, about).not.toMatch(/discover|new planet/i)
      }
    }
  })

  it('writes Beginner’s sentences plainly: 20 words at most and none of the scientist’s words', () => {
    for (const f of FEATURES) {
      expect(words(f.about.beginner), f.about.beginner).toBeLessThanOrEqual(20)
      expect(f.about.beginner, f.about.beginner).not.toMatch(SCIENTISTS_WORDS)
      expect(f.label.beginner).not.toMatch(SCIENTISTS_WORDS)
    }
  })
})

describe('the bar', () => {
  const links: FeatureLinks = { practise: '?train=7&ui=beginner', vote: '?watchlist=1&ui=beginner', tools: '?tools=1&ui=beginner' }
  const bar = (props: Partial<Parameters<typeof FeatureBar>[0]> = {}) =>
    renderToStaticMarkup(createElement(FeatureBar, { level: 'beginner', current: 'watch', links, onOpen: () => undefined, ...props }))
  /** Each item: its tag, its visible text and its attributes. */
  const items = (html: string) =>
    [...html.matchAll(/<(a|button) ([^>]*)><span class="feature-text" data-text="[^"]*">([^<]*)<\/span><\/\1>/g)].map((m) => ({ tag: m[1], attrs: m[2], text: m[3] }))

  it('is a navigation landmark named "Features", with a list of the ten items in the words of the level', () => {
    const html = bar()
    expect(html).toMatch(/^<nav class="feature-bar" aria-label="Features"><ul class="feature-list">/)
    expect(items(html).map((i) => i.text)).toEqual(FEATURES.map((f) => f.label.beginner))
    expect(items(bar({ level: 'expert' })).map((i) => i.text)).toEqual(FEATURES.map((f) => f.label.expert))
  })

  it('marks exactly one item as the current one', () => {
    for (const current of ['watch', 'spectrum', 'context', 'vote'] as FeatureKey[]) {
      const marked = items(bar({ current })).filter((i) => i.attrs.includes('aria-current="page"'))
      expect(marked.map((i) => i.text)).toEqual([feature(current).label.beginner])
    }
  })

  it('gives each item its sentence as a title, never as its name', () => {
    for (const [i, item] of items(bar()).entries()) {
      expect(item.attrs).toContain(`title="${FEATURES[i].about.beginner.replace(/'/g, '&#x27;')}"`)
      expect(item.attrs).not.toContain('aria-label')
    }
  })

  it('on the viewer: Watch and the tools are buttons, the screens are links that carry the level', () => {
    const all = items(bar())
    expect(all.slice(0, 7).every((i) => i.tag === 'button' && i.attrs.includes('type="button"'))).toBe(true)
    expect(all.slice(7).map((i) => [i.tag, /href="([^"]*)"/.exec(i.attrs)?.[1]])).toEqual([
      ['a', '?train=7&amp;ui=beginner'],
      ['a', '?watchlist=1&amp;ui=beginner'],
      ['a', '?tools=1&amp;ui=beginner'],
    ])
  })

  it('while the first pictures load, the tools are there but cannot be pressed yet; Watch always can', () => {
    const waiting = items(bar({ ready: false }))
    expect(waiting).toHaveLength(10)
    expect(waiting.slice(1, 7).every((i) => i.attrs.includes('aria-disabled="true"'))).toBe(true)
    expect(waiting[0].attrs).not.toContain('aria-disabled')
    expect(items(bar()).some((i) => i.attrs.includes('aria-disabled'))).toBe(false)
  })

  it('off the viewer, Watch and the tools are links back to it, opening the tool pressed', () => {
    const viewer = (tool: string | null) => `?ui=expert${tool ? `&tool=${tool}` : ''}`
    const all = items(bar({ level: 'expert', current: 'vote', onOpen: undefined, links: { ...links, viewer } }))
    expect(all.slice(0, 7).map((i) => /href="([^"]*)"/.exec(i.attrs)?.[1])).toEqual([
      '?ui=expert',
      '?ui=expert&amp;tool=brightness',
      '?ui=expert&amp;tool=spectrum',
      '?ui=expert&amp;tool=search',
      '?ui=expert&amp;tool=distant',
      '?ui=expert&amp;tool=smallbodies',
      '?ui=expert&amp;tool=context',
    ])
    expect(all.find((i) => i.attrs.includes('aria-current="page"'))?.text).toBe('Watchlist')
  })
})

describe('keeping the current item in view inside the bar', () => {
  it('scrolls the bar only when the item is cut off, and never past its start', () => {
    // A 390px bar: an item fully inside needs nothing.
    expect(scrollToShow({ left: 0, width: 390, scrollLeft: 0 }, { left: 100, width: 80 })).toBeNull()
    // An item past the right edge: just enough to show it, with a small margin.
    expect(scrollToShow({ left: 0, width: 390, scrollLeft: 0 }, { left: 646, width: 212 })).toBe(646 + 212 - 390 + 8)
    // An item scrolled off to the left: back to it, not below zero.
    expect(scrollToShow({ left: 0, width: 390, scrollLeft: 500 }, { left: -477, width: 61 })).toBe(500 - 477 - 8)
    expect(scrollToShow({ left: 0, width: 390, scrollLeft: 4 }, { left: -4, width: 61 })).toBe(0)
  })
})

describe('a press on the picture', () => {
  // A picture of 11 August 2026 (MJD 61263.92).
  const mjd = 61263.92
  it('while "What is it?" is the current feature asks the card about that place, on the picture’s date, and never measures a spectrum', () => {
    for (const level of ['beginner', 'expert'] as const) {
      expect(pressOnPicture('context', level, 269.4432123, 4.7957891, mjd)).toEqual({ kind: 'ask', ra: 269.44321, dec: 4.79579, epoch: decimalYear(mjd) })
    }
    // No picture on screen: no date is sent, and the card reads the place as for 2026.0.
    expect(pressOnPicture('context', 'beginner', 10, 5, null)).toEqual({ kind: 'ask', ra: 10, dec: 5, epoch: undefined })
  })
  it('with any other feature current, measures the spectrum there in Expert, as before, and does nothing in Beginner', () => {
    for (const current of ['watch', 'spectrum', 'brightness', 'search', 'distant', 'smallbodies'] as const) {
      expect(pressOnPicture(current, 'expert', 269.4432123, 4.7957891, mjd)).toEqual({ kind: 'spectrum', ra: 269.44321, dec: 4.79579 })
      expect(pressOnPicture(current, 'beginner', 269.4432123, 4.7957891, mjd)).toBeNull()
    }
  })
  it('counts a catalogue entry within two SPHEREx pixels as the thing pressed', () => {
    expect(PRESS_RADIUS_ARCSEC).toBeCloseTo(2 * NATIVE_PIXEL_ARCSEC, 6)
  })
  it('dates the picture as a decimal Julian year', () => {
    expect(decimalYear(51544.5)).toBe(2000)
    expect(decimalYear(51544.5 + 365.25 * 26.5)).toBe(2026.5)
    expect(decimalYear(mjd)).toBe(2026.6103)
  })
})
