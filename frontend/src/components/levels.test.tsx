// The Beginner / Expert switch: what each level puts on the page.
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Viewer } from '../App'
import { BeginnerGuide, LevelSwitch } from './LevelSwitch'

const viewerAt = (search: string) => {
  vi.stubGlobal('window', { location: { search }, localStorage: { getItem: () => null, setItem: () => undefined } })
  return renderToStaticMarkup(<Viewer />)
}

afterEach(() => vi.unstubAllGlobals())

describe('the switch', () => {
  it('is two buttons with the current side pressed', () => {
    const html = renderToStaticMarkup(<LevelSwitch level="beginner" onChange={() => undefined} />)
    expect(html).toMatch(/aria-pressed="true"[^>]*>Beginner</)
    expect(html).toMatch(/aria-pressed="false"[^>]*>Expert</)
    expect(html).toContain('Expert adds the six detectors')
  })
})

describe('the page at each level', () => {
  it('Beginner has the search, the practice links and the guide, and none of the expert controls', () => {
    const html = viewerAt('')
    expect(html).toContain('Practise: find a planted object')
    expect(html).toContain('Help check what the search found')
    expect(html).toContain('What am I looking at?')
    expect(html).not.toContain('class="selectors"')
    expect(html).not.toContain('Difference (what changed)')
    expect(html).not.toContain('Field of view')
  })
  it('Expert has the detector, field of view and mode menus and no beginner paragraph', () => {
    const html = viewerAt('?ui=expert')
    expect(html).toContain('class="selectors"')
    expect(html).toContain('Difference (what changed)')
    expect(html).toContain('Field of view')
    expect(html).not.toContain('What am I looking at?')
  })
  it('an old link with a mode opens in Expert', () => {
    expect(viewerAt('?ra=133.759765&dec=-7.242182&det=6&mode=difference')).toContain('class="selectors"')
  })
  it('the beginner guide uses no expert words', () => {
    expect(renderToStaticMarkup(<BeginnerGuide />)).not.toMatch(/detector|epoch|flux/i)
  })
})
