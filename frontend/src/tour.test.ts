// The guided tour: its steps are data and its logic is plain functions (tour.ts), checked here
// without a page.
import { describe, expect, it } from 'vitest'
import { readAddress, type UiLevel } from './address'
import { CANDIDATE_LINE } from './finds'
import { FEATURES } from './features'
import { STEPS, clearStep, hrefOf, nextStep, parseDemo, pressName, prevStep, readStep, saveStep, withoutDemo, type StorageLike, cardPlace, linkLeadsOn } from './tour'

const LEVELS: UiLevel[] = ['beginner', 'expert']
const SCIENTISTS_WORDS = /\b(sigma|flux|fluxes|epoch|epochs|detector|detectors|centroid|centroids|mJy)\b|σ/i
const FORBIDDEN = /\b(discovery|discovered|new planet|new)\b/i
const textOf = (s: (typeof STEPS)[number]) => `${s.title} ${s.what}`

describe('the steps', () => {
  it('have unique ids and enough of them', () => {
    const ids = STEPS.map((s) => s.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(STEPS.length).toBeGreaterThanOrEqual(18)
    expect(STEPS.length).toBeLessThanOrEqual(26)
  })

  it('ring every feature of the bar at least once', () => {
    for (const f of FEATURES) {
      expect(
        STEPS.some((s) => s.target.includes(`[data-feature="${f.key}"]`)),
        f.key,
      ).toBe(true)
    }
  })

  it('name a page the app reads without a note, at both levels, and are at their own page', () => {
    for (const level of LEVELS) {
      for (const s of STEPS) {
        const url = s.url(level)
        expect(url.startsWith('?'), s.id).toBe(true)
        expect(readAddress(url).notes, `${s.id} ${url}`).toEqual([])
        expect(readAddress(url).selection.ui, s.id).toBe(level)
        expect(s.at({ search: url }, level), `${s.id} is at its own address`).toBe(true)
      }
    }
  })

  it('are not at the page of a step that needs another screen', () => {
    const byId = (id: string) => STEPS.find((s) => s.id === id)!
    expect(byId('watchlist').at({ search: byId('opening').url('beginner') }, 'beginner')).toBe(false)
    expect(byId('opening').at({ search: byId('watchlist').url('beginner') }, 'beginner')).toBe(false)
    expect(byId('barnard-moves').at({ search: byId('opening').url('beginner') }, 'beginner')).toBe(false)
    expect(byId('brightness').at({ search: byId('barnard-moves').url('beginner') }, 'beginner')).toBe(false)
  })

  it('use plain words, and say nothing about a find beyond the allowed sentence', () => {
    for (const s of STEPS) {
      expect(textOf(s), s.id).not.toMatch(SCIENTISTS_WORDS)
      expect(textOf(s), s.id).not.toMatch(FORBIDDEN)
      for (const level of LEVELS) expect(pressName(s, level) ?? '', s.id).not.toMatch(SCIENTISTS_WORDS)
    }
    for (const s of STEPS.filter((x) => /candidate/i.test(x.what))) {
      expect(s.what, s.id).toContain(CANDIDATE_LINE)
    }
  })

  it('say that the practice object is made up', () => {
    const practise = STEPS.find((s) => s.id === 'practise')!
    expect(practise.what).toMatch(/made[- ]up/)
    expect(practise.what).toMatch(/SIMULATION/)
  })

  it('name the visible label of what to press, at each level', () => {
    const watch = STEPS.find((s) => s.id === 'watch')!
    expect(pressName(watch, 'beginner')).toBe('Watch')
    expect(pressName(watch, 'expert')).toBe('Viewer')
    const brightness = STEPS.find((s) => s.id === 'brightness')!
    expect(pressName(brightness, 'expert')).toBe('Light curve')
    expect(pressName(STEPS.find((s) => s.id === 'opening')!, 'beginner')).toBeNull()
  })
})

describe('moving', () => {
  it('stops at both ends', () => {
    const n = STEPS.length
    expect(nextStep(0, n)).toBe(1)
    expect(nextStep(n - 1, n)).toBe(n - 1)
    expect(prevStep(1)).toBe(0)
    expect(prevStep(0)).toBe(0)
  })
})

describe('the address', () => {
  it('reads demo=<n> as step n (1 is the first) and ignores anything else', () => {
    expect(parseDemo('?demo=1')).toBe(0)
    expect(parseDemo('?x=2&demo=5')).toBe(4)
    expect(parseDemo('?demo=0')).toBeNull()
    expect(parseDemo('?demo=abc')).toBeNull()
    expect(parseDemo('?demo=')).toBeNull()
    expect(parseDemo('?ra=1')).toBeNull()
    expect(parseDemo('?demo=9999', 23)).toBe(22)
  })

  it('takes demo out and leaves the rest', () => {
    expect(withoutDemo('?ra=1&demo=3&ui=expert')).toBe('?ra=1&ui=expert')
    expect(withoutDemo('?demo=1')).toBe('')
    expect(withoutDemo('')).toBe('')
  })

  it('makes a link that carries the step', () => {
    expect(hrefOf('/', '?ui=beginner', 3)).toBe('/?ui=beginner&demo=4')
  })
})

describe('storage', () => {
  const memory = (): StorageLike & { data: Record<string, string> } => {
    const data: Record<string, string> = {}
    return {
      data,
      getItem: (k) => data[k] ?? null,
      setItem: (k, v) => void (data[k] = v),
      removeItem: (k) => void delete data[k],
    }
  }
  const broken: StorageLike = {
    getItem: () => {
      throw new Error('blocked')
    },
    setItem: () => {
      throw new Error('blocked')
    },
    removeItem: () => {
      throw new Error('blocked')
    },
  }

  it('keeps the step and clears it', () => {
    const store = memory()
    expect(readStep(store)).toBeNull()
    saveStep(4, store)
    expect(store.data['spherex-tour-step']).toBe('4')
    expect(readStep(store)).toBe(4)
    clearStep(store)
    expect(readStep(store)).toBeNull()
  })

  it('survives a storage that throws, and a getter that throws', () => {
    expect(() => saveStep(2, broken)).not.toThrow()
    expect(() => readStep(broken)).not.toThrow()
    expect(() => clearStep(broken)).not.toThrow()
    expect(() => saveStep(2, () => { throw new Error('no storage') })).not.toThrow()
    expect(readStep(() => { throw new Error('no storage') })).toBe(2)
    clearStep(() => { throw new Error('no storage') })
    expect(readStep(() => { throw new Error('no storage') })).toBeNull()
  })

  it('ignores a stored value that is not a step', () => {
    const store = memory()
    store.data['spherex-tour-step'] = 'abc'
    expect(readStep(store)).toBeNull()
    store.data['spherex-tour-step'] = '-1'
    expect(readStep(store)).toBeNull()
  })
})

describe('where the card goes, so that it does not hide what it is about', () => {
  const win = { width: 1440, height: 900 }
  it('is below a small target in the top half and above one in the bottom half', () => {
    expect(cardPlace({ top: 60, left: 12, width: 160, height: 34 }, win)).toBe('bottom')
    expect(cardPlace({ top: 760, left: 300, width: 600, height: 56 }, win)).toBe('top')
  })
  it('is beside a target too tall to be above or below: right of the picture, left of the words', () => {
    expect(cardPlace({ top: 110, left: 280, width: 640, height: 776 }, win)).toBe('right')
    expect(cardPlace({ top: 100, left: 1020, width: 420, height: 756 }, win)).toBe('left')
  })
  it('in a narrow window is only ever above or below, and at the bottom with no target', () => {
    expect(cardPlace({ top: 60, left: 0, width: 390, height: 700 }, { width: 390, height: 844 })).toBe('bottom')
    expect(cardPlace(null, win)).toBe('bottom')
  })
})

describe('a ringed link that leads to the next step', () => {
  const at = (id: string) => STEPS.findIndex((x) => x.id === id)
  it('the step after "Watch it appear" is the candidate’s own view, at any of the three candidates', () => {
    const view = STEPS[at('watch-it-appear') + 1]
    expect(view.id).toBe('candidate-view')
    expect(view.press).toBeNull()
    for (const place of ['?ra=270.80408&dec=-23.46818&fov=0.1&det=6&pmra=0&pmdec=0', '?ra=253.18038&dec=-44.67697&fov=0.1&det=6&pmra=0&pmdec=0', '?ra=241.70906&dec=-52.20564&fov=0.1&det=6&pmra=0&pmdec=0']) {
      expect(view.at({ search: place }, 'beginner'), place).toBe(true)
    }
    expect(view.at({ search: '?ra=269.446267&dec=4.768222' }, 'beginner')).toBe(false)   // Barnard's Star is not one of them
    expect(view.at({ search: '?watchlist=1' }, 'beginner')).toBe(false)
  })
  it('pressing "Watch it appear" on any card moves the tour on; a link to anywhere else does not', () => {
    const i = at('watch-it-appear')
    expect(linkLeadsOn(i, 'https://example.org/?ra=253.18038&dec=-44.67697&fov=0.1&det=6&pmra=0&pmdec=0&name=Candidate+B&ui=beginner', 'beginner')).toBe(true)
    expect(linkLeadsOn(i, 'https://example.org/?tools=1&ui=beginner', 'beginner')).toBe(false)
    expect(linkLeadsOn(STEPS.length - 1, 'https://example.org/?watchlist=1', 'beginner')).toBe(false)   // no step after the last
    expect(linkLeadsOn(i, 'not an address', 'beginner')).toBe(false)
  })
})
