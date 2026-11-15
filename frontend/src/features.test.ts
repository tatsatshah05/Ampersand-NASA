// Every feature in one bar: the list, its words at each level, and the bar it makes.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { FeatureBar, type FeatureLinks } from './components/FeatureBar'
import { feature, FEATURES, isToolKey, TOOL_KEYS, type FeatureKey } from './features'

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
      ['context', 'Other telescopes', 'Sky context'],
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
