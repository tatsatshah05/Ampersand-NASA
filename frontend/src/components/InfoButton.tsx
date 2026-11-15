// A small round "i" button that opens a short explanation of what is going on.
//
// The explanation is drawn in a portal on the page body with position: fixed, placed from
// the button's own rectangle. Not inside the page's own boxes: the side column and the
// fixed text block scroll inside themselves, and the picture's and the player's columns
// are layout containers, so anything positioned inside them would be clipped or moved
// with them. Opening or closing one therefore changes nothing in the page's layout.
//
// Keyboard and mouse: Enter, Space or a click opens it; Escape closes it and puts the focus
// back on the button; a click anywhere else closes it; opening another closes this one.
// The text is always in the page (hidden until opened) so the button can name it as its
// description for screen readers, and it is not counted or read while hidden.
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import { createPortal } from 'react-dom'
import { releaseFocusAfterPointer } from '../focus'
import { placePopover } from '../popover'
import './InfoButton.css'

const OPENED = 'info-popover-opened'

// False while rendering on the server and for the first render in the page, true after.
const noSubscription = () => () => undefined
const inThePage = () => true
const notInThePage = () => false

interface Props {
  /** The button's accessible name, e.g. "About this picture". */
  name: string
  /** The explanation, one string per paragraph. */
  text: string[]
  /** The id of the explanation, when something else points to it (the picture does). */
  id?: string
  className?: string
  /** Called each time it is opened. */
  onOpen?: () => void
}

export function InfoButton({ name, text, id, className, onOpen }: Props) {
  const own = useId()
  const popId = id ?? `info-${own.replace(/:/g, '')}`
  const [open, setOpen] = useState(false)
  // The portal needs the page, so it appears after the first render (never on the server).
  const mounted = useSyncExternalStore(noSubscription, inThePage, notInThePage)
  const button = useRef<HTMLButtonElement>(null)
  const pop = useRef<HTMLDivElement>(null)

  const close = useCallback(() => setOpen(false), [])

  const place = useCallback(() => {
    const b = button.current
    const p = pop.current
    if (!b || !p) return
    const view = { w: document.documentElement.clientWidth, h: window.innerHeight }
    const at = placePopover(b.getBoundingClientRect(), { w: p.offsetWidth, h: p.offsetHeight }, view)
    p.style.left = `${Math.round(at.left)}px`
    p.style.top = `${Math.round(at.top)}px`
  }, [])

  // Placed again after every render while open (the text may have changed with the visit).
  useLayoutEffect(() => {
    if (open) place()
  })

  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node
      if (!button.current?.contains(t) && !pop.current?.contains(t)) close()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      close()
      button.current?.focus()
    }
    const onOther = (e: Event) => {
      if ((e as CustomEvent<string>).detail !== popId) close()
    }
    window.addEventListener('pointerdown', onDown, true)
    window.addEventListener('keydown', onKey)
    document.addEventListener(OPENED, onOther)
    // Scrolling inside any box, or resizing the window, moves the button: follow it.
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      window.removeEventListener('pointerdown', onDown, true)
      window.removeEventListener('keydown', onKey)
      document.removeEventListener(OPENED, onOther)
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [open, close, place, popId])

  return (
    <>
      <button
        ref={button}
        type="button"
        className={className ? `info-button ${className}` : 'info-button'}
        aria-label={name}
        aria-expanded={open}
        aria-controls={popId}
        aria-describedby={open ? popId : undefined}
        onClick={(e) => {
          if (open) setOpen(false)
          else {
            document.dispatchEvent(new CustomEvent(OPENED, { detail: popId }))
            setOpen(true)
            onOpen?.()
          }
          releaseFocusAfterPointer(e.currentTarget)
        }}
      >
        i
      </button>
      {mounted &&
        createPortal(
          <div ref={pop} id={popId} className="info-popover" role="note" hidden={!open}>
            {text.map((p) => (
              <p key={p}>{p}</p>
            ))}
          </div>,
          document.body,
        )}
    </>
  )
}
