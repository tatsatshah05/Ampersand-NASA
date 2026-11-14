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
 * The frames at `url` (see framesUrl in api.ts). `attempt` is a counter: raising it
 * asks again for the same view, for a "try again" button.
 */
export function useFrames(url: string, attempt: number): Load {
  const key = `${attempt} ${url}`
  const [settled, setSettled] = useState<{ key: string; load: Settled } | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    const settle = (load: Settled) => {
      if (!ctrl.signal.aborted) setSettled({ key, load })
    }
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
      ctrl.abort()
    }
  }, [key, url])

  // Until the request for this very view has settled, it is loading.
  return settled?.key === key ? settled.load : { state: 'loading' }
}
