// The player's timer, and its rest while nobody can see the picture (D7).
import { describe, expect, it } from 'vitest'
import { INITIAL_PLAYBACK, nextIndex, ticks, watchSight, type SightPage } from './usePlayer'

describe('the timer', () => {
  it('opens still on every machine: nothing moves until the visitor presses Play or Blink', () => {
    expect(INITIAL_PLAYBACK).toBe('paused')
    expect(ticks(INITIAL_PLAYBACK, 3, false)).toBe(false)
  })
  it('runs only with something to flip, not paused, and someone looking', () => {
    expect(ticks('playing', 3, false)).toBe(true)
    expect(ticks('blinking', 3, false)).toBe(true)
    expect(ticks('paused', 3, false)).toBe(false)
    expect(ticks('playing', 1, false)).toBe(false)
    // Resting stops it without changing the state, so Pause keeps its label.
    expect(ticks('playing', 3, true)).toBe(false)
  })
  it('goes round when playing and between the ends when blinking', () => {
    expect([0, 1, 2].map((i) => nextIndex('playing', i, 3))).toEqual([1, 2, 0])
    expect(nextIndex('blinking', 0, 3)).toBe(2)
    expect(nextIndex('blinking', 2, 3)).toBe(0)
  })
})

/** A page whose picture can be scrolled away and whose tab can be hidden, by hand. */
function fakePage() {
  let seen: ((entries: { isIntersecting: boolean; intersectionRatio: number }[]) => void) | null = null
  let onVisibility: (() => void) | null = null
  let watching = 0
  const page: SightPage = {
    IntersectionObserver: class {
      constructor(callback: (entries: { isIntersecting: boolean; intersectionRatio: number }[]) => void) {
        seen = callback
      }
      observe() {
        watching += 1
      }
      disconnect() {
        watching -= 1
      }
    },
    document: {
      hidden: false,
      addEventListener: (_: 'visibilitychange', f: () => void) => {
        onVisibility = f
      },
      removeEventListener: () => {
        onVisibility = null
      },
    },
  }
  return {
    page,
    scroll: (inView: boolean, ratio = inView ? 1 : 0) => seen?.([{ isIntersecting: inView, intersectionRatio: ratio }]),
    tab: (hidden: boolean) => {
      page.document.hidden = hidden
      onVisibility?.()
    },
    watching: () => watching,
    listening: () => onVisibility !== null,
  }
}

describe('resting while the picture is out of sight', () => {
  it('rests when the picture is scrolled away and carries on when it is back', () => {
    const f = fakePage()
    const said: boolean[] = []
    watchSight({} as Element, (r) => said.push(r), f.page)
    f.scroll(false)
    f.scroll(true)
    expect(said).toEqual([false, true, false])
  })
  it('rests when only a sliver of the picture is left in the window (a short tool panel)', () => {
    const f = fakePage()
    const said: boolean[] = []
    watchSight({} as Element, (r) => said.push(r), f.page)
    f.scroll(true, 0.006) // 4 px of a 642 px picture
    f.scroll(true, 0.5)
    expect(said).toEqual([false, true, false])
  })
  it('rests while the tab is hidden, and only says each change once', () => {
    const f = fakePage()
    const said: boolean[] = []
    watchSight({} as Element, (r) => said.push(r), f.page)
    f.tab(true)
    f.scroll(false) // still resting: nothing new to say
    f.tab(false) // the tab is back but the picture is still scrolled away
    f.scroll(true)
    expect(said).toEqual([false, true, false])
  })
  it('stops watching when told to', () => {
    const f = fakePage()
    const stop = watchSight({} as Element, () => undefined, f.page)
    expect(f.watching()).toBe(1)
    expect(f.listening()).toBe(true)
    stop()
    expect(f.watching()).toBe(0)
    expect(f.listening()).toBe(false)
  })
  it('works where the page has no IntersectionObserver (then only the tab counts)', () => {
    const f = fakePage()
    const said: boolean[] = []
    watchSight({} as Element, (r) => said.push(r), { document: f.page.document })
    f.tab(true)
    expect(said).toEqual([false, true])
  })
})
