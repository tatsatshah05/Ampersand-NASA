// The Beginner / Expert switch: what each level puts on the page.
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Viewer } from '../App'
import { GO_FURTHER, INFO_NAMES, levelInfo, NO_PROGRESS } from '../guide'
import { EXPERT_ADDS, LevelSwitch, StepGuide } from './LevelSwitch'

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
    expect(html).toContain('class="guide-steps"')
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
    expect(renderToStaticMarkup(<StepGuide progress={NO_PROGRESS} />)).not.toMatch(/detector|epoch|flux|sigma|centroid/i)
  })
  it('Beginner points to Practise, helping check and Expert in the guide, and says what Expert adds in the switch', () => {
    const html = viewerAt('')
    expect(html).toContain(`class="guide-further">${GO_FURTHER}<`)
    expect(html).toContain('aria-label="About Beginner and Expert"')
    expect(levelInfo().join(' ')).toContain('a search for a distant world (Planet X)')
    // Expert's own tooltip on the switch is unchanged.
    expect(EXPERT_ADDS).toContain('the search for a distant world (Planet X)')
  })
  it('Beginner no longer has the old "What am I looking at?" paragraph or the line under it', () => {
    const html = viewerAt('')
    expect(html).not.toContain('What am I looking at?')
    expect(html).not.toContain('class="expert-adds"')
  })
  it('Beginner has the steps; Expert has neither the steps nor any i button', () => {
    const beginner = viewerAt('')
    expect(beginner).toContain('class="guide-steps"')
    expect(beginner).toContain('Choose a star above')
    expect(beginner).toContain('Flip through the visits')
    expect(beginner).toContain('Read what changed')
    const expert = viewerAt('?ui=expert')
    expect(expert).not.toContain('class="guide')
    expect(expert).not.toContain('info-button')
  })
  it('Beginner has an i button for the picture, the visits, Play and Blink, and the switch, each with a name', () => {
    const html = viewerAt('')
    for (const name of [INFO_NAMES.picture, INFO_NAMES.visits, INFO_NAMES.player, INFO_NAMES.level]) {
      expect(html).toMatch(new RegExp(`class="info-button[^"]*"[^>]*aria-label="${name}"[^>]*aria-expanded="false"[^>]*aria-controls="`))
    }
  })
  it('Expert keeps its "?" for how to work the picture', () => {
    expect(viewerAt('?ui=expert')).toContain('aria-label="How to move and zoom the picture"')
    expect(viewerAt('')).not.toContain('aria-label="How to move and zoom the picture"')
  })
})

describe('the same frame at both levels', () => {
  // Rendered before any frames arrive: the plate, the player, the strip and the readout block are there all the same.
  for (const [level, search] of [
    ['Beginner', ''],
    ['Expert', '?ui=expert'],
  ]) {
    it(`${level} has the plate, the player, the strip of visits and the readout block of fixed height`, () => {
      const html = viewerAt(search)
      expect(html).toContain('class="stage stage-empty"')
      expect(html).toMatch(/class="play-button"/)
      expect(html).toContain('aria-label="Next frame"')
      expect(html).toContain('class="visit-strip"')
      expect(html).toMatch(/class="readout-block( busy)?"/)
      expect(html).not.toContain('type="range"')
    })
  }

  it('the target row has the five challenge targets and the three of our own, each with its tooltip', () => {
    const html = viewerAt('')
    for (const name of ["Barnard&#x27;s Star", 'Epsilon Indi B', 'WISE 0855', 'RW Aurigae', 'R Draconis']) {
      expect(html).toMatch(new RegExp(`class="target"[^>]*title="[^"]+"[^>]*>${name}</button>`))
    }
    for (const name of ['Young star in Serpens South', 'Nova V462 Lupi', 'Nova V572 Velorum']) {
      expect(html).toMatch(new RegExp(`class="target"[^>]*title="[^"]+"[^>]*aria-label="${name}"`))
    }
    // The address's target is the one marked as on screen.
    expect(html).toMatch(/aria-current="true">Barnard&#x27;s Star</)
  })
})
