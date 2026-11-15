// Issue #5: which frame is on screen, and what moves it on. Three states: playing
// (frame after frame, round and round), blinking (first and last frame in turn, which
// shows a small shift best) and paused. One timer drives both playing and blinking.
import { useCallback, useEffect, useState } from 'react'

export type Playback = 'playing' | 'blinking' | 'paused'

/** Time each frame stays on screen, in milliseconds. */
export const SPEEDS = [
  { label: 'Slow', ms: 1000 },
  { label: 'Normal', ms: 500 },
  { label: 'Fast', ms: 250 },
] as const

const prefersStillness = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true

/**
 * `framesKey` names the set of frames being played and `count` is how many there are.
 * A new set starts again from its first frame; playing or paused carries over.
 */
export function usePlayer(framesKey: string, count: number) {
  // People who ask their system for less motion start paused; play is one key away.
  const [playback, setPlayback] = useState<Playback>(() => (prefersStillness() ? 'paused' : 'playing'))
  const [speedMs, setSpeedMs] = useState<number>(SPEEDS[1].ms)
  const [at, setAt] = useState({ key: framesKey, index: 0 })
  const current = at.key === framesKey && at.index < count ? at.index : 0

  useEffect(() => {
    if (count < 2 || playback === 'paused') return
    const timer = window.setInterval(() => {
      setAt((was) => {
        const index = was.key === framesKey && was.index < count ? was.index : 0
        const next = playback === 'blinking' ? (index === 0 ? count - 1 : 0) : (index + 1) % count
        return { key: framesKey, index: next }
      })
    }, speedMs)
    return () => window.clearInterval(timer)
  }, [playback, speedMs, framesKey, count])

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

  /** Blink starts on the first frame, so the first flip goes to the last. */
  const toggleBlink = useCallback(() => {
    setPlayback((was) => (was === 'blinking' ? 'paused' : 'blinking'))
    setAt((was) => (was.key === framesKey && (was.index === 0 || was.index === count - 1) ? was : { key: framesKey, index: 0 }))
  }, [framesKey, count])

  return { current, playback, speedMs, setSpeedMs, show, step, pause, togglePlay, toggleBlink }
}
