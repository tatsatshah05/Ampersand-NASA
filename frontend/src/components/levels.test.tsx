// The Beginner / Expert switch: what each level puts on the page.
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Viewer } from '../App'
import { FEATURES } from '../features'
import { GO_FURTHER, INFO_NAMES, levelInfo, NO_PROGRESS } from '../guide'
import { LevelDock } from './LevelDock'
import { EXPERT_ADDS, LevelSwitch, StepGuide } from './LevelSwitch'
import { TrainingView } from './TrainingView'
import { WatchlistView } from './WatchlistView'

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
    expect(html).toContain('Every tool, written in plain words.')
    expect(html).toContain('Every tool written for scientists, with all the numbers, plus the six detectors')
  })

  it('sits in its dock, with its "i" in Beginner only, before it so the switch keeps the corner', () => {
    const beginner = renderToStaticMarkup(<LevelDock level="beginner" onChange={() => undefined} />)
    expect(beginner).toMatch(/^<div class="level-dock"><button[^>]*class="info-button"[^>]*aria-label="About Beginner and Expert"[^>]*>i<\/button><div class="level-switch" role="group" aria-label="How much to show">/)
    const expert = renderToStaticMarkup(<LevelDock level="expert" onChange={() => undefined} />)
    expect(expert).toMatch(/^<div class="level-dock"><div class="level-switch" role="group" aria-label="How much to show">/)
    expect(expert).not.toContain('info-button')
  })
})

/** The top bar: from the header to its end. */
const topBar = (html: string) => html.slice(html.indexOf('<header class="topbar">'), html.indexOf('</header>') + 9)
/** The bar's items: their visible words, in order. */
const barLabels = (html: string) => [...topBar(html).matchAll(/<span class="feature-text" data-text="[^"]*">([^<]*)<\/span>/g)].map((m) => m[1])

describe('the bar of features at the top', () => {
  it('lists every feature in order, in the words of the level, and nothing else is in the top bar', () => {
    expect(barLabels(viewerAt(''))).toEqual(FEATURES.map((f) => f.label.beginner))
    expect(barLabels(viewerAt('?ui=expert'))).toEqual(FEATURES.map((f) => f.label.expert))
    for (const html of [viewerAt(''), viewerAt('?ui=expert')]) {
      const top = topBar(html)
      expect(top).toMatch(/^<header class="topbar"><h1 class="brand">SPHEREx sky-change viewer<\/h1><nav class="feature-bar" aria-label="Features">/)
      expect(top).not.toContain('role="search"')
      expect(top).not.toContain('level-switch')
    }
  })

  it('marks Watch as the feature on screen when the page opens', () => {
    const top = topBar(viewerAt(''))
    expect(top.match(/aria-current="page"/g)).toHaveLength(1)
    expect(top).toMatch(/aria-current="page"[^>]*><span class="feature-text" data-text="Watch">/)
  })

  it('shows the tools before the first pictures arrive, there but not yet to be pressed', () => {
    const top = topBar(viewerAt('?ui=expert'))
    for (const label of ['Light curve', 'Spectrum', 'Blind search', 'Planet X search', 'Small bodies', 'Sky context']) {
      expect(top).toMatch(new RegExp(`<button [^>]*aria-disabled="true"[^>]*><span class="feature-text" data-text="${label}">`))
    }
  })

  it('links to the three other screens in the level in use', () => {
    const hrefs = (html: string) => [...topBar(html).matchAll(/<a [^>]*href="([^"]*)"/g)].map((m) => m[1].replace(/&amp;/g, '&'))
    const beginner = hrefs(viewerAt(''))
    expect(beginner).toHaveLength(3)
    expect(beginner[0]).toMatch(/^\?ra=269\.446267&dec=4\.768222.*&train=\d+&level=easy&ui=beginner$/)
    expect(beginner.slice(1)).toEqual(['?watchlist=1&ui=beginner', '?tools=1&ui=beginner'])
    expect(hrefs(viewerAt('?ui=expert')).slice(1)).toEqual(['?watchlist=1&ui=expert', '?tools=1&ui=expert'])
  })

  it('has the search field at the start of the target row, before the star buttons, and the switch in the dock', () => {
    const html = viewerAt('')
    const targets = html.slice(html.indexOf('<nav class="targets"'), html.indexOf('<main'))
    expect(targets.indexOf('role="search"')).toBeGreaterThan(0)
    expect(targets.indexOf('role="search"')).toBeLessThan(targets.indexOf('class="target"'))
    expect(targets).not.toContain('Practise spotting a moving object')
    expect(targets).not.toContain('Vote on what the search found')
    expect(html.slice(html.indexOf('</main>'))).toContain('<div class="level-dock">')
  })
})

describe('the page at each level', () => {
  it('Beginner has the search, the bar and the guide, and none of the view settings', () => {
    const html = viewerAt('')
    expect(html).toContain('aria-label="Search the sky"')
    expect(html).toContain('aria-label="Features"')
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
  it('Beginner points to the bar in the guide, and the switch says both levels have every tool', () => {
    const html = viewerAt('')
    expect(html).toContain(`class="guide-further">${GO_FURTHER}<`)
    expect(GO_FURTHER).toBe('Then try the other tools in the bar at the top.')
    expect(html).toContain('aria-label="About Beginner and Expert"')
    expect(levelInfo().join(' ')).toContain('Both levels have every tool')
    expect(EXPERT_ADDS).toContain('the six detectors, the difference and sum views and the overlays')
  })
  it('Beginner no longer has the old "What am I looking at?" paragraph or the line under it', () => {
    const html = viewerAt('')
    expect(html).not.toContain('What am I looking at?')
    expect(html).not.toContain('class="expert-adds"')
  })
  it('Beginner has the steps; Expert has neither the steps nor any i button', () => {
    const beginner = viewerAt('')
    expect(beginner).toContain('class="guide-steps"')
    expect(beginner).toContain('Press a star above')
    expect(beginner).toContain('Press Blink or a visit')
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

describe('the other screens', () => {
  const screenAt = (search: string, screen: 'practice' | 'watchlist', stored: string | null = null) => {
    vi.stubGlobal('window', {
      location: { search },
      localStorage: { getItem: (k: string) => (k === 'spherex-ui-level' ? stored : null), setItem: () => undefined },
    })
    return renderToStaticMarkup(screen === 'practice' ? <TrainingView /> : <WatchlistView />)
  }
  const screenBar = (html: string) => html.slice(html.indexOf('<header class="topbar screen-topbar">'), html.indexOf('</header>') + 9)
  const labels = (html: string) => [...screenBar(html).matchAll(/data-text="([^"]*)"/g)].map((m) => m[1])
  const href = (html: string, label: string) =>
    new RegExp(`href="([^"]*)"[^>]*><span class="feature-text" data-text="${label}">`).exec(screenBar(html))?.[1].replace(/&amp;/g, '&')

  it('the practice screen has the same bar, with Practise current, the level kept, and the dock', () => {
    const html = screenAt('?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal&train=12&level=easy&ui=beginner', 'practice')
    expect(labels(html)).toEqual(FEATURES.map((f) => f.label.beginner))
    expect(screenBar(html)).toMatch(/aria-current="page"[^>]*><span class="feature-text" data-text="Practise">/)
    expect(screenBar(html).match(/aria-current="page"/g)).toHaveLength(1)
    // Watch and the tools go back to this patch of sky in the viewer, opening the tool pressed.
    expect(href(html, 'Watch')).toBe('?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal&ui=beginner')
    expect(href(html, 'Colours')).toBe('?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal&ui=beginner&tool=spectrum')
    expect(href(html, 'Vote')).toBe('?watchlist=1&ui=beginner')
    // The screen's own way back carries the level too.
    expect(html).toContain('href="?ra=269.446267&amp;dec=4.768222&amp;fov=0.1&amp;det=5&amp;mode=normal&amp;ui=beginner">Back to the real sky</a>')
    expect(html).toContain('<div class="level-dock">')
    expect(html).toMatch(/aria-pressed="true"[^>]*>Beginner</)
    // The simulation banner still comes first.
    expect(html.indexOf('class="sim-banner"')).toBeLessThan(html.indexOf('class="topbar screen-topbar"'))
  })

  it('the voting screen has the same bar, with Vote current, in the level the address or this device gives', () => {
    const expert = screenAt('?watchlist=1&ui=expert', 'watchlist')
    expect(labels(expert)).toEqual(FEATURES.map((f) => f.label.expert))
    expect(screenBar(expert)).toMatch(/aria-current="page"[^>]*><span class="feature-text" data-text="Watchlist">/)
    expect(href(expert, 'Viewer')).toBe('?ui=expert')
    expect(href(expert, 'Planet X search')).toBe('?ui=expert&tool=distant')
    expect(href(expert, 'Training')).toMatch(/&train=\d+&level=easy&ui=expert$/)
    expect(expert).toMatch(/aria-pressed="true"[^>]*>Expert</)
    expect(expert).not.toContain('Back to the viewer')
    expect(labels(screenAt('?watchlist=1', 'watchlist', 'expert'))).toEqual(FEATURES.map((f) => f.label.expert))
    expect(labels(screenAt('?watchlist=1', 'watchlist', null))).toEqual(FEATURES.map((f) => f.label.beginner))
  })
})
