// Loading the frames for a view. A newer request cancels the one before it, and a view
// counts as loaded only once every picture in it is ready to show, so playing never
// reveals a half-loaded frame.
import { useEffect, useState } from 'react'
import { fetchFrames, hasFrames, type FramesReady } from './api'

export type Load =
  | { state: 'loading' }
  | { state: 'ready'; data: FramesReady }
  /** The server answered with no pictures; `message` is its reason. */
  | { state: 'empty'; message: string }
  | { state: 'error'; message: string }

type Settled = Exclude<Load, { state: 'loading' }>

/** Fetch and decode a picture ahead of showing it. */
function preload(src: string): Promise<void> {
  const image = new Image()
  image.src = src
  return image.decode()
}

/**
 * A view that has been made before comes back within a few hundredths of a second. For
 * this long after asking, the previous pictures stay up, so that flipping between
 * detectors or modes does not flash a "loading" message each time.
 */
const KEEP_PREVIOUS_MS = 250

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
            settle({ state: 'error', message: 'The pictures were made, but one of them could not be loaded. Try again.' })
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

  if (settled?.key === key) return settled.load
  // Not answered yet. For a moment the pictures already on screen stay; after that, or
  // when there are none, it is loading.
  if (settled?.load.state === 'ready' && slow !== key) return settled.load
  return { state: 'loading' }
}
