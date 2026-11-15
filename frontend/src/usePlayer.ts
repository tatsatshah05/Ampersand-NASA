// Issue #5: which frame is on screen, and what moves it on. Three states: playing
// (frame after frame, round and round), blinking (first and last frame in turn, which
// shows a small shift best) and paused. One timer drives both playing and blinking.
//
// A before-and-after pair (one of our sweep's candidates: wording.ts, beforeAfter) changes
// blinking to flip between those two frames, holding each long enough to see what appeared,
// and a new set of frames with a pair opens blinking on its "before" frame (still, on it, for
// people who ask for less motion).
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

/** A blink between a before-and-after pair holds each frame this many times the playing speed (1.2 s at Normal). */
export const PAIR_HOLD = 2.4

/** The two frames a blink flips between: [before, after] indices. */
export type Pair = readonly [number, number]

/** The frame after `index`: the next one round and round, or for a blink the other end (or the other of the pair). */
export const nextIndex = (playback: Playback, index: number, count: number, pair: Pair | null = null): number => {
  if (playback !== 'blinking') return (index + 1) % count
  if (pair) return index === pair[0] ? pair[1] : pair[0]
  return index === 0 ? count - 1 : 0
}

/**
 * `framesKey` names the set of frames being played and `count` is how many there are.
 * A new set starts again from its first frame; playing or paused carries over. While
 * `resting` the timer stops and nothing else changes (useResting says when).
 */
export function usePlayer(framesKey: string, count: number, resting = false, pair: Pair | null = null) {
  // People who ask their system for less motion start paused; play is one key away.
  const [playback, setPlayback] = useState<Playback>(() => (prefersStillness() ? 'paused' : 'playing'))
  const [speedMs, setSpeedMs] = useState<number>(SPEEDS[1].ms)
  const [at, setAt] = useState({ key: framesKey, index: 0 })
  // A set of frames with a before-and-after pair opens on "before", blinking (once per set).
  const [pairedFor, setPairedFor] = useState<string | null>(null)
  const before = pair && pair[0] < count && pair[1] < count ? pair[0] : null
  const after = before !== null && pair ? pair[1] : null
  if (before !== null && framesKey && pairedFor !== framesKey) {
    setPairedFor(framesKey)
    setAt({ key: framesKey, index: before })
    if (!prefersStillness()) setPlayback('blinking')
  }
  const current = at.key === framesKey && at.index < count ? at.index : 0

  useEffect(() => {
    if (!ticks(playback, count, resting)) return
    const flip: Pair | null = before !== null && after !== null ? [before, after] : null
    const timer = window.setInterval(
      () => {
        setAt((was) => {
          const index = was.key === framesKey && was.index < count ? was.index : 0
          return { key: framesKey, index: nextIndex(playback, index, count, flip) }
        })
      },
      playback === 'blinking' && flip ? speedMs * PAIR_HOLD : speedMs,
    )
    return () => window.clearInterval(timer)
  }, [playback, speedMs, framesKey, count, resting, before, after])

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

  /** Stop where it is (a visitor reading an explanation should not have it change under them). */
  const pause = useCallback(() => setPlayback('paused'), [])

  const togglePlay = useCallback(() => setPlayback((was) => (was === 'paused' ? 'playing' : 'paused')), [])

  /** Blink starts on the first frame (or the pair's "before"), so the first flip goes to the last (or "after"). */
  const toggleBlink = useCallback(() => {
    setPlayback((was) => (was === 'blinking' ? 'paused' : 'blinking'))
    const ends = before !== null && after !== null ? [before, after] : [0, count - 1]
    setAt((was) => (was.key === framesKey && ends.includes(was.index) ? was : { key: framesKey, index: ends[0] }))
  }, [framesKey, count, before, after])

  return { current, playback, speedMs, setSpeedMs, show, step, pause, togglePlay, toggleBlink }
}

/** What watchSight needs from the page, so that it can be tested without one. */
export interface SightPage {
  IntersectionObserver?: new (
    callback: (entries: { isIntersecting: boolean; intersectionRatio: number }[]) => void,
    options?: { threshold: number[] },
  ) => { observe(el: Element): void; disconnect(): void }
  document: { hidden: boolean; addEventListener(type: 'visibilitychange', f: () => void): void; removeEventListener(type: 'visibilitychange', f: () => void): void }
}

/**
 * The share of the picture that must be in the window for it to count as seen. A short tool
 * panel can leave a sliver of a few pixels at the top of the window; nobody watches that.
 */
export const SEEN_SHARE = 0.1

/**
 * Tell `onChange` whether the picture should rest: true while less than SEEN_SHARE of `el`
 * is in the window, or the tab is hidden; false when it is back. Returns a function that
 * stops watching.
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
    ? new page.IntersectionObserver(
        (entries) => {
          const last = entries[entries.length - 1]
          if (!last) return
          inView = last.isIntersecting && last.intersectionRatio >= SEEN_SHARE
          report()
        },
        { threshold: [0, SEEN_SHARE] },
      )
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
