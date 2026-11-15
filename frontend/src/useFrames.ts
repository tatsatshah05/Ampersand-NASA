// Loading the frames for a view. A newer request cancels the one before it, and a view
// counts as loaded only once every picture in it is ready to show, so playing never
// reveals a half-loaded frame. While a new view loads, the last one that loaded is kept,
// so the page can leave its pictures on screen (dimmed) instead of emptying the picture.
import { useEffect, useState } from 'react'
import { fetchFrames, hasFrames, type FramesReady } from './api'

export type Load =
  /**
   * Not answered yet. `previous` is the last view that loaded (null when there is none,
   * or the last request failed), for showing while this one comes. `slow` turns true once
   * the request has taken longer than KEEP_PREVIOUS_MS: until then the previous pictures
   * can stay as they are, so that a view that comes back at once does not flash.
   */
  | { state: 'loading'; previous: FramesReady | null; slow: boolean }
  | { state: 'ready'; data: FramesReady }
  /** The server answered with no pictures; `message` is its reason. */
  | { state: 'empty'; message: string }
  | { state: 'error'; message: string }

export type Settled = Exclude<Load, { state: 'loading' }>

/** Fetch and decode a picture ahead of showing it. */
function preload(src: string): Promise<void> {
  const image = new Image()
  image.src = src
  return image.decode()
}

/**
 * A view that has been made before comes back within a few hundredths of a second. For
 * this long after asking, the previous pictures stay up undimmed, so that flipping
 * between detectors or modes does not flash a "loading" message each time.
 */
export const KEEP_PREVIOUS_MS = 250

/**
 * What to show for request `key`, given the last answer that arrived (`settled`, for this
 * request or an earlier one) and the request that has been waited on for longer than
 * KEEP_PREVIOUS_MS (`slow`). Kept apart from the hook so it can be tested without a browser.
 */
export function loadFor(settled: { key: string; load: Settled } | null, key: string, slow: string | null): Load {
  if (settled?.key === key) return settled.load
  const previous = settled?.load.state === 'ready' ? settled.load.data : null
  return { state: 'loading', previous, slow: slow === key }
}

/**
 * The frames at `url` (see framesUrl in api.ts). `attempt` is a counter: raising it
 * asks again for the same view, for a "try again" button.
 */
export function useFrames(url: string, attempt: number): Load {
  const key = `${attempt} ${url}`
  const [settled, setSettled] = useState<{ key: string; load: Settled } | null>(null)
  // The request that has been waited on for longer than KEEP_PREVIOUS_MS, if any.
  const [slow, setSlow] = useState<string | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    const settle = (load: Settled) => {
      if (!ctrl.signal.aborted) setSettled({ key, load })
    }
    const patience = window.setTimeout(() => setSlow(key), KEEP_PREVIOUS_MS)
    // Started on the next tick: in development React mounts every component twice, and
    // this way the first, discarded mount never sends a request to the archive.
    const timer = window.setTimeout(() => {
      fetchFrames(url, ctrl.signal)
        .then(async (body) => {
          if (!hasFrames(body)) {
            settle({ state: 'empty', message: body.message ?? 'SPHEREx has no usable images of this position.' })
            return
          }
          try {
            await Promise.all(body.frames.map((frame) => preload(frame.image)))
          } catch {
            settle({ state: 'error', message: 'The frames were made, but one of them could not be loaded. Try again.' })
            return
          }
          settle({ state: 'ready', data: body })
        })
        .catch((e: unknown) => settle({ state: 'error', message: e instanceof Error ? e.message : String(e) }))
    }, 0)
    return () => {
      window.clearTimeout(timer)
      window.clearTimeout(patience)
      ctrl.abort()
    }
  }, [key, url])

  return loadFor(settled, key, slow)
}
