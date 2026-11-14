// What takes the picture's place while there is no picture to show: loading, nothing
// found, or something went wrong. Never a stand-in image.
import { useEffect, useState, type ReactNode } from 'react'

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
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="stage stage-status loading">
      <div className="status-card" role="status">
        <h2>Getting the pictures…</h2>
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
