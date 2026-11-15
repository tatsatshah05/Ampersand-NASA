// Issue #5: which frame is on screen, and what moves it on. Three states: playing
// (frame after frame, round and round), blinking (first and last frame in turn, which
// shows a small shift best) and paused. One timer drives both playing and blinking.
//
// Resting: when nobody can see the picture (scrolled out of the window, or the tab hidden)
// the timer rests. The state does not change, so Play or Pause keeps its label and nothing
// on the page changes; when the picture is back in sight the visits carry on by themselves.
// A visitor's own Pause is a state, so it stays paused.
import { useCallback, useEffect, useState, type RefObject } from 'react'

export type Playback = 'playing' | 'blinking' | 'paused'

/** Time each frame stays on screen, in milliseconds. */
export const SPEEDS = [
  { label: 'Slow', ms: 1000 },
  { label: 'Normal', ms: 500 },
  { label: 'Fast', ms: 250 },
] as const

const prefersStillness = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true

/** Whether the timer runs: something to flip between, not paused, and someone can see it. */
export const ticks = (playback: Playback, count: number, resting: boolean): boolean => count >= 2 && playback !== 'paused' && !resting

/** The frame after `index`: the next one round and round, or for a blink the other end. */
export const nextIndex = (playback: Playback, index: number, count: number): number =>
  playback === 'blinking' ? (index === 0 ? count - 1 : 0) : (index + 1) % count

/**
 * `framesKey` names the set of frames being played and `count` is how many there are.
 * A new set starts again from its first frame; playing or paused carries over. While
 * `resting` the timer stops and nothing else changes (useResting says when).
 */
export function usePlayer(framesKey: string, count: number, resting = false) {
  // People who ask their system for less motion start paused; play is one key away.
  const [playback, setPlayback] = useState<Playback>(() => (prefersStillness() ? 'paused' : 'playing'))
  const [speedMs, setSpeedMs] = useState<number>(SPEEDS[1].ms)
  const [at, setAt] = useState({ key: framesKey, index: 0 })
  const current = at.key === framesKey && at.index < count ? at.index : 0

  useEffect(() => {
    if (!ticks(playback, count, resting)) return
    const timer = window.setInterval(() => {
      setAt((was) => {
        const index = was.key === framesKey && was.index < count ? was.index : 0
        return { key: framesKey, index: nextIndex(playback, index, count) }
      })
    }, speedMs)
    return () => window.clearInterval(timer)
  }, [playback, speedMs, framesKey, count, resting])

  /** Show one frame and stop there. */
  const show = useCallback(
    (index: number) => {
      if (count === 0) return
      setPlayback('paused')
      setAt({ key: framesKey, index: Math.min(Math.max(index, 0), count - 1) })
    },
    [framesKey, count],
  )

  /** Step forward (1) or back (-1), going round at the ends, and stop there. */
  const step = useCallback(
    (by: number) => {
      if (count === 0) return
      setPlayback('paused')
      setAt((was) => {
        const index = was.key === framesKey && was.index < count ? was.index : 0
        return { key: framesKey, index: (index + by + count) % count }
      })
    },
    [framesKey, count],
  )

  const togglePlay = useCallback(() => setPlayback((was) => (was === 'paused' ? 'playing' : 'paused')), [])

  /** Blink starts on the first frame, so the first flip goes to the last. */
  const toggleBlink = useCallback(() => {
    setPlayback((was) => (was === 'blinking' ? 'paused' : 'blinking'))
    setAt((was) => (was.key === framesKey && (was.index === 0 || was.index === count - 1) ? was : { key: framesKey, index: 0 }))
  }, [framesKey, count])

  return { current, playback, speedMs, setSpeedMs, show, step, togglePlay, toggleBlink }
}

/** What watchSight needs from the page, so that it can be tested without one. */
export interface SightPage {
  IntersectionObserver?: new (callback: (entries: { isIntersecting: boolean }[]) => void) => { observe(el: Element): void; disconnect(): void }
  document: { hidden: boolean; addEventListener(type: 'visibilitychange', f: () => void): void; removeEventListener(type: 'visibilitychange', f: () => void): void }
}

/**
 * Tell `onChange` whether the picture should rest: true while `el` is entirely out of the
 * window or the tab is hidden, false when it is back. Returns a function that stops watching.
 */
export function watchSight(el: Element, onChange: (resting: boolean) => void, page: SightPage): () => void {
  let inView = true
  let hidden = page.document.hidden
  let said: boolean | null = null
  const report = () => {
    const resting = hidden || !inView
    if (resting !== said) onChange(resting)
    said = resting
  }
  const observer = page.IntersectionObserver
    ? new page.IntersectionObserver((entries) => {
        const last = entries[entries.length - 1]
        if (!last) return
        inView = last.isIntersecting
        report()
      })
    : null
  observer?.observe(el)
  const onVisibility = () => {
    hidden = page.document.hidden
    report()
  }
  page.document.addEventListener('visibilitychange', onVisibility)
  report()
  return () => {
    observer?.disconnect()
    page.document.removeEventListener('visibilitychange', onVisibility)
  }
}

/** True while nobody can see the element `ref` points to (the picture): usePlayer's `resting`. */
export function useResting(ref: RefObject<Element | null>): boolean {
  const [resting, setResting] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof document === 'undefined') return
    const observer = typeof IntersectionObserver === 'undefined' ? undefined : IntersectionObserver
    return watchSight(el, setResting, { IntersectionObserver: observer, document })
  }, [ref])
  return resting
}
