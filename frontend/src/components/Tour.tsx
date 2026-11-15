// The guided tour's shell: a small "Tour" button while it is off, and while it runs a ring round
// what to press and a card that says what it does. The steps and every decision are in tour.ts.
// Nothing here blocks the page: the ring ignores the pointer, and every press goes through.
// The card changes only when the presenter presses something, never on its own.
import { useEffect, useRef, useState } from 'react'
import { chooseUiLevel, readStoredLevel } from '../address'
import {
  cardPlace,
  clearStep,
  hrefOf,
  linkLeadsOn,
  needsOpening,
  nextStep,
  parseDemo,
  pressName,
  prevStep,
  readStep,
  saveStep,
  STEPS,
  type Step,
  withoutDemo,
} from '../tour'
import './Tour.css'

/** How long the page gets to show what a step rings before the card says it is still loading. */
const LOOK_MS = 6000
/** How long a press (a name looked up, say) gets to bring the page to where the next step needs it. */
const SETTLE_MS = 8000

const levelNow = () => chooseUiLevel(window.location.search, readStoredLevel())

/** The element a step rings, if it is on the page and has a size. */
function findTarget(step: Step): HTMLElement | null {
  const all = Array.from(document.querySelectorAll<HTMLElement>(step.target))
  const el = step.targetText === undefined ? all[0] : all.find((e) => e.textContent?.trim() === step.targetText)
  if (!el) return null
  const r = el.getBoundingClientRect()
  return r.width > 0 && r.height > 0 ? el : null
}

interface Box {
  top: number
  left: number
  width: number
  height: number
}

const GAP = 6
const sameBox = (a: Box | null, b: Box | null) => a === b || (a !== null && b !== null && a.top === b.top && a.left === b.left && a.width === b.width && a.height === b.height)

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el || !el.tagName) return false
  return el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA' || el.isContentEditable
}

export function Tour() {
  const [step, setStep] = useState<number | null>(() => {
    const asked = parseDemo(window.location.search)
    if (asked !== null) return asked
    const kept = readStep()
    return kept !== null && kept < STEPS.length ? kept : null
  })
  const [box, setBox] = useState<Box | null>(null)
  const [gaveUp, setGaveUp] = useState(false)
  // Set when a press may still be bringing the page to where the next step needs it.
  const settling = useRef(false)
  // Set while the tour itself presses something, so that its own press is not read as the presenter's.
  const own = useRef(false)

  // `?demo=` has done its work: take it out of the address.
  useEffect(() => {
    if (!new URLSearchParams(window.location.search).has('demo')) return
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${withoutDemo(window.location.search)}${window.location.hash}`)
    } catch {
      // The tour still works; the address keeps its demo parameter.
    }
  }, [])

  const go = (to: number, wait: boolean) => {
    settling.current = wait
    setBox(null)
    setGaveUp(false)
    setStep(to)
  }
  const end = () => {
    clearStep()
    setBox(null)
    setStep(null)
  }
  const next = () => {
    if (step === null) return
    if (step >= STEPS.length - 1) return end()
    const s = STEPS[step]
    const el = findTarget(s)
    // Press it for the presenter, unless it is a link: a link loads a page the next step would load again.
    if (el && s.press !== null && !el.closest('a[href]')) {
      own.current = true
      try {
        el.click()
      } finally {
        own.current = false
      }
      return go(nextStep(step, STEPS.length), true)
    }
    go(nextStep(step, STEPS.length), false)
  }
  const back = () => {
    if (step !== null) go(prevStep(step), false)
  }
  const acts = useRef({ next, back, end })
  useEffect(() => {
    acts.current = { next, back, end }
  })

  // Showing a step: bring the page to where it needs it, then find what it rings.
  useEffect(() => {
    if (step === null) return
    saveStep(step)
    const s = STEPS[step]
    const timers: number[] = []
    const stops: (() => void)[] = []
    let stopped = false

    const here = () => s.at({ search: window.location.search }, levelNow())
    const navigate = () => {
      if (stopped) return
      window.location.assign(hrefOf(window.location.pathname, s.url(levelNow()), step))
    }

    const show = () => {
      const started = Date.now()
      let first = true
      let opened = false
      const measure = () => {
        const el = findTarget(s)
        if (!el) return setBox((b) => (b === null ? b : null))
        if (first) {
          first = false
          el.scrollIntoView({ block: 'center', inline: 'nearest' })
        }
        // A tool's own bar item, pressed once when its tool is not on screen yet.
        if (!opened && needsOpening(s, window.location.search) && el.getAttribute('aria-disabled') !== 'true') {
          opened = true
          own.current = true
          try {
            el.click()
          } finally {
            own.current = false
          }
        }
        const r = el.getBoundingClientRect()
        const b = { top: r.top - GAP, left: r.left - GAP, width: r.width + 2 * GAP, height: r.height + 2 * GAP }
        setBox((old) => (sameBox(old, b) ? old : b))
      }
      measure()
      const id = window.setInterval(() => {
        measure()
        if (first && Date.now() - started > LOOK_MS) setGaveUp(true)
      }, 250)
      timers.push(id)
      const on = () => measure()
      window.addEventListener('scroll', on, true)
      window.addEventListener('resize', on)
      stops.push(() => {
        window.removeEventListener('scroll', on, true)
        window.removeEventListener('resize', on)
      })
    }

    if (here()) show()
    else if (settling.current) {
      const started = Date.now()
      const id = window.setInterval(() => {
        if (here()) {
          window.clearInterval(id)
          show()
        } else if (Date.now() - started > SETTLE_MS) {
          window.clearInterval(id)
          navigate()
        }
      }, 250)
      timers.push(id)
    } else navigate()

    return () => {
      stopped = true
      timers.forEach((t) => window.clearInterval(t))
      stops.forEach((f) => f())
    }
  }, [step])

  // Pressing what is ringed moves on; so do the arrow keys. Neither blocks the page's own reply to a press.
  useEffect(() => {
    if (step === null) return
    const onClick = (e: MouseEvent) => {
      if (own.current) return
      const t = e.target as Element | null
      if (!t || t.closest('.tour-card')) return
      // A link loads its page. Where that page is the next step's own (the candidate's view after "Watch it
      // appear", on any of the three cards and not only the ringed one), the tour goes on to it; otherwise
      // the step stays, and brings its own page back.
      const link = t.closest<HTMLAnchorElement>('a[href]')
      if (link) {
        if (linkLeadsOn(step, link.href, levelNow())) saveStep(step + 1)
        return
      }
      const el = findTarget(STEPS[step])
      if (!el || !el.contains(t)) return
      acts.current.next()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return
      const act = e.key === 'ArrowRight' ? acts.current.next : e.key === 'ArrowLeft' ? acts.current.back : e.key === 'Escape' ? acts.current.end : null
      if (!act) return
      e.preventDefault()
      e.stopImmediatePropagation() // the player's own arrow keys must not step a frame as well
      act()
    }
    document.addEventListener('click', onClick, true)
    window.addEventListener('keydown', onKey, true)
    return () => {
      document.removeEventListener('click', onClick, true)
      window.removeEventListener('keydown', onKey, true)
    }
  }, [step])

  if (step === null) {
    return (
      <button
        type="button"
        className="tour-start"
        onClick={() => {
          saveStep(0)
          go(0, false)
        }}
      >
        Tour
      </button>
    )
  }

  const s = STEPS[step]
  const level = levelNow()
  const press = pressName(s, level)
  const last = step === STEPS.length - 1
  const place = cardPlace(box, { width: window.innerWidth, height: window.innerHeight })
  return (
    <>
      {box && <div className="tour-ring" aria-hidden="true" style={{ top: box.top, left: box.left, width: box.width, height: box.height }} />}
      <section className="tour-card" data-place={place} role="region" aria-label="Guided tour">
        <p className="tour-count">
          Step {step + 1} of {STEPS.length}
        </p>
        <h2 className="tour-title">{s.title}</h2>
        {press && <p className="tour-press">Press: {press}</p>}
        <p className="tour-what">{s.what}</p>
        {box === null && gaveUp && <p className="tour-wait">Still loading…</p>}
        <div className="tour-buttons">
          <button type="button" onClick={back} disabled={step === 0}>
            Back
          </button>
          <button type="button" className="tour-next" onClick={next}>
            {last ? 'Finish' : 'Next'}
          </button>
          <button type="button" className="tour-end" onClick={end}>
            End tour
          </button>
        </div>
      </section>
    </>
  )
}
