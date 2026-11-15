// What takes the picture's place while there is no picture to show: loading, nothing
// found, or something went wrong. Never a stand-in image. StatusCard and LoadingCard are
// boxes of their own (the practice screen); PlateLoading and PlateMessage are laid over
// the main page's picture, which keeps its place and size whatever happens.
import { useEffect, useState, type ReactNode } from 'react'

/** After this long a load is not a quick one, and the plate says why it may take a while. */
const EXPLAIN_AFTER_S = 2

/**
 * Over the picture while a view loads: what is being loaded, a thin moving line, and once
 * it has taken a couple of seconds, why the first time is slow and how long it has been.
 * The pictures already there stay under it, dimmed. Mount it afresh (a new `key`) for
 * each request.
 */
export function PlateLoading({ what }: { what: string }) {
  const seconds = useSeconds()
  return (
    <div className="plate-status loading" role="status">
      <div className="plate-progress" aria-hidden="true">
        <span />
      </div>
      <div className="plate-status-text">
        <p className="plate-status-title">Loading {what}…</p>
        {seconds >= EXPLAIN_AFTER_S && (
          <>
            <p>
              A position, detector or field of view that nobody has asked for before takes about a minute: the exposures
              are fetched from NASA's archive and added together. After that it is quick.
            </p>
            {/* Not read out: a counter that changes every second would drown a screen reader. */}
            <p className="elapsed" aria-hidden="true">
              {seconds} seconds so far
              {seconds >= 90 && '. Longer than usual, but still working.'}
            </p>
          </>
        )}
      </div>
    </div>
  )
}

/** A message over the picture's place: nothing to show here, or something went wrong. */
export function PlateMessage({ title, tone, children }: { title: string; tone?: 'error'; children?: ReactNode }) {
  return (
    <div className={tone === 'error' ? 'plate-status message error' : 'plate-status message'} role={tone === 'error' ? 'alert' : 'status'}>
      <div className="plate-status-text">
        <p className="plate-status-title">{title}</p>
        {children}
      </div>
    </div>
  )
}

/** Whole seconds since the component was mounted. */
function useSeconds() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500)
    return () => window.clearInterval(timer)
  }, [])
  return seconds
}

/** A message in the box where the picture goes. */
export function StatusCard({ title, tone, children }: { title: string; tone?: 'error'; children?: ReactNode }) {
  return (
    <div className="stage stage-status">
      <div className={tone === 'error' ? 'status-card error' : 'status-card'} role={tone === 'error' ? 'alert' : 'status'}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  )
}

/**
 * Shown while frames are being fetched. A view that has been asked for before comes
 * back at once; a new one takes about a minute, so this says so and counts the seconds
 * to show that something is happening. Mount it afresh (a new `key`) for each request.
 */
export function LoadingCard() {
  const seconds = useSeconds()
  return (
    <div className="stage stage-status loading">
      <div className="status-card" role="status">
        <h2>Loading the frames…</h2>
        <p>
          A position, detector or field of view that nobody has asked for before takes about a minute: the exposures
          are fetched from NASA's archive and added together. After that it is quick.
        </p>
        <div className="progress" aria-hidden="true">
          <span />
        </div>
        {/* Not read out: a counter that changes every second would drown a screen reader. */}
        <p className="elapsed" aria-hidden="true">
          {seconds < 1 ? 'Starting…' : `${seconds} ${seconds === 1 ? 'second' : 'seconds'} so far`}
          {seconds >= 90 && '. Longer than usual, but still working.'}
        </p>
      </div>
    </div>
  )
}
