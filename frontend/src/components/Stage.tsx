// The picture stage: one frame at a time, with zoom and pan.
//
// The frame and everything drawn over it (the Gaia overlay, the motion markers) sit in
// one box that is made larger and moved to zoom and pan. The overlays are SVGs whose
// viewBox is the picture's pixels, so they stay in register with it at every zoom and
// their line widths stay the same on screen.
//
// Wheel or pinch zooms about the pointer, dragging pans, and a click that was not a
// drag reports the sky position under it. Zooming out stops at the whole picture.
// Zoom, markers and blink are ported from the earlier viewer (public/viewer.html,
// issue #8).
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { releaseFocusAfterPointer } from '../focus'
import { pixelToSky, type Grid } from '../projection'
import { maxZoom, panBy, pointAt, zoomAbout, type ZoomBox } from '../zoom'

/**
 * Pixel edges are drawn once a picture pixel is at least this wide on screen. The
 * starting view is at most 8, so the edges come in with the first step of zooming in.
 */
const GRID_FROM_PX = 9
/** A press that moves less than this many screen pixels is a click, not a drag. */
const CLICK_SLOP_PX = 5
const BUTTON_ZOOM = 1.5
/** Share of the view that one Shift+arrow key press moves it. */
const KEY_PAN = 0.15

export interface StageImage {
  key: string
  src: string
}

interface Props {
  /** Where the picture is on the sky and how big it is. */
  grid: Grid
  /** Every frame; all are kept loaded so that stepping between them is instant. */
  images: StageImage[]
  current: number
  /** What the frame on screen is, for people who cannot see it. */
  alt: string
  box: ZoomBox
  onBoxChange: (change: (box: ZoomBox) => ZoomBox) => void
  onReset: () => void
  /** Hard-edged pixels instead of smooth scaling, with pixel edges drawn when zoomed in. */
  showPixels: boolean
  /** Called with the sky position (degrees) of a click that was not a drag. */
  onPick?: (ra: number, dec: number) => void
  /** Id of the text that explains the mouse and keyboard controls. */
  describedBy?: string
  /** Layers drawn over the picture, given the number of screen pixels per picture pixel. */
  children?: (scale: number) => ReactNode
}

export function Stage({ grid, images, current, alt, box, onBoxChange, onReset, showPixels, onPick, describedBy, children }: Props) {
  const { sizePx } = grid
  const surface = useRef<HTMLDivElement>(null)
  const [stagePx, setStagePx] = useState(640)
  const [dragging, setDragging] = useState(false)
  // Fingers or mouse buttons currently down on the stage, and whether the press has turned into a drag.
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const press = useRef<{ x: number; y: number; dragged: boolean } | null>(null)

  // The stage's width on screen, for sizes that are in screen pixels.
  useLayoutEffect(() => {
    const el = surface.current
    if (!el) return
    const measure = () => setStagePx(el.clientWidth || 640)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  const scale = (stagePx * box.zoom) / sizePx // screen pixels per picture pixel

  // The wheel listener is added by hand (React's own cannot stop the page from
  // scrolling), so it reads the latest values from here.
  const latest = useRef({ box, sizePx, onBoxChange })
  useEffect(() => {
    latest.current = { box, sizePx, onBoxChange }
  })
  useEffect(() => {
    const el = surface.current
    if (!el) return
    let lastZoom = 0
    const onWheel = (e: WheelEvent) => {
      const { box, sizePx, onBoxChange } = latest.current
      const rect = el.getBoundingClientRect()
      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? rect.height : 1 // lines or pages to pixels
      // A pinch on a trackpad arrives as a wheel event with the control key set.
      const factor = Math.exp(-e.deltaY * unit * (e.ctrlKey ? 0.01 : 0.002))
      const wanted = Math.min(Math.max(box.zoom * factor, 1), maxZoom(sizePx))
      const now = performance.now()
      // Zoomed all the way out (or in): let the page scroll, unless this is the tail of a zoom gesture.
      if (wanted === box.zoom && !e.ctrlKey && now - lastZoom > 300) return
      e.preventDefault()
      lastZoom = now
      if (wanted === box.zoom) return
      const fx = (e.clientX - rect.left) / rect.width
      const fy = (e.clientY - rect.top) / rect.height
      onBoxChange((b) => zoomAbout(b, factor, fx, fy, sizePx))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    // A second finger makes it a pinch, which is never a click.
    press.current = pointers.current.size === 1 ? { x: e.clientX, y: e.clientY, dragged: false } : null
    setDragging(true)
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const before = pointers.current.get(e.pointerId)
    if (!before) return
    const now = { x: e.clientX, y: e.clientY }
    pointers.current.set(e.pointerId, now)
    const rect = e.currentTarget.getBoundingClientRect()
    if (pointers.current.size === 1) {
      const p = press.current
      if (p && !p.dragged) {
        if (Math.hypot(now.x - p.x, now.y - p.y) < CLICK_SLOP_PX) return
        p.dragged = true
      }
      const dfx = -(now.x - before.x) / rect.width
      const dfy = -(now.y - before.y) / rect.height
      onBoxChange((b) => panBy(b, dfx, dfy, sizePx))
    } else if (pointers.current.size === 2) {
      // Two fingers: zoom by how much they moved apart, about the point between them.
      const other = [...pointers.current].find(([id]) => id !== e.pointerId)?.[1]
      if (!other) return
      const spanBefore = Math.hypot(before.x - other.x, before.y - other.y)
      const spanNow = Math.hypot(now.x - other.x, now.y - other.y)
      if (spanBefore < 1 || spanNow < 1) return
      const fx = ((now.x + other.x) / 2 - rect.left) / rect.width
      const fy = ((now.y + other.y) / 2 - rect.top) / rect.height
      const dfx = -(now.x - before.x) / 2 / rect.width
      const dfy = -(now.y - before.y) / 2 / rect.height
      onBoxChange((b) => panBy(zoomAbout(b, spanNow / spanBefore, fx, fy, sizePx), dfx, dfy, sizePx))
    }
  }

  // However a press ends (lifted, cancelled, or its capture lost) it is forgotten here.
  // Only a lift that never turned into a drag is a click.
  function onPointerEnd(e: PointerEvent<HTMLDivElement>) {
    if (!pointers.current.delete(e.pointerId)) return
    const p = press.current
    if (pointers.current.size === 0) {
      press.current = null
      setDragging(false)
    }
    if (e.type !== 'pointerup' || !p || p.dragged || !onPick) return
    const rect = e.currentTarget.getBoundingClientRect()
    const at = pointAt(box, (e.clientX - rect.left) / rect.width, (e.clientY - rect.top) / rect.height, sizePx)
    if (at.x < 0 || at.y < 0 || at.x > sizePx || at.y > sizePx) return
    const sky = pixelToSky(at.x, at.y, grid)
    onPick(sky.ra, sky.dec)
  }

  // With the stage focused: plus and minus zoom, 0 resets, Shift with an arrow key pans.
  // Plain arrow keys and the space bar are left for the player.
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.ctrlKey || e.metaKey || e.altKey) return
    if (e.key === '+' || e.key === '=') onBoxChange((b) => zoomAbout(b, BUTTON_ZOOM, 0.5, 0.5, sizePx))
    else if (e.key === '-' || e.key === '_') onBoxChange((b) => zoomAbout(b, 1 / BUTTON_ZOOM, 0.5, 0.5, sizePx))
    else if (e.key === '0') onReset()
    else if (e.shiftKey && e.key === 'ArrowLeft') onBoxChange((b) => panBy(b, -KEY_PAN, 0, sizePx))
    else if (e.shiftKey && e.key === 'ArrowRight') onBoxChange((b) => panBy(b, KEY_PAN, 0, sizePx))
    else if (e.shiftKey && e.key === 'ArrowUp') onBoxChange((b) => panBy(b, 0, -KEY_PAN, sizePx))
    else if (e.shiftKey && e.key === 'ArrowDown') onBoxChange((b) => panBy(b, 0, KEY_PAN, sizePx))
    else return
    e.preventDefault()
  }

  const zoomButton = (label: string, face: ReactNode, disabled: boolean, change: () => void) => (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(e) => {
        change()
        releaseFocusAfterPointer(e.currentTarget)
      }}
    >
      {face}
    </button>
  )
  const resetIcon = (
    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
      <path d="M3.2 8a4.8 4.8 0 1 0 1.5-3.5M2.6 2.2v3h3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )

  return (
    <div className="stage">
      <div
        ref={surface}
        className={`stage-surface${dragging ? ' dragging' : ''}`}
        tabIndex={0}
        role="group"
        aria-label="The image. Drag to move it; scroll, pinch or press plus and minus to zoom."
        aria-describedby={describedBy}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
        onLostPointerCapture={onPointerEnd}
        onKeyDown={onKeyDown}
      >
        <div
          className="stage-zoom"
          style={{
            width: `${box.zoom * 100}%`,
            height: `${box.zoom * 100}%`,
            left: `${(0.5 - (box.cx / sizePx) * box.zoom) * 100}%`,
            top: `${(0.5 - (box.cy / sizePx) * box.zoom) * 100}%`,
          }}
        >
          {images.map((image, i) => (
            <img
              key={image.key}
              src={image.src}
              alt={i === current ? alt : ''}
              aria-hidden={i !== current}
              className={showPixels ? 'hard-pixels' : undefined}
              style={{ visibility: i === current ? 'visible' : 'hidden' }}
              draggable={false}
            />
          ))}
          {showPixels && scale >= GRID_FROM_PX && <PixelEdges sizePx={sizePx} box={box} />}
          {children?.(scale)}
        </div>
      </div>

      <Compass />
      <ScaleBar arcsecPerScreenPx={grid.pixelArcsec / scale} />
      <div className="stage-buttons">
        {zoomButton('Zoom in', '+', box.zoom >= maxZoom(sizePx), () => onBoxChange((b) => zoomAbout(b, BUTTON_ZOOM, 0.5, 0.5, sizePx)))}
        {zoomButton('Zoom out', '−', box.zoom <= 1, () => onBoxChange((b) => zoomAbout(b, 1 / BUTTON_ZOOM, 0.5, 0.5, sizePx)))}
        {zoomButton('Reset the view', resetIcon, false, onReset)}
      </div>
    </div>
  )
}

/** The edges of the picture's pixels, for the part of the picture in view. */
function PixelEdges({ sizePx, box }: { sizePx: number; box: ZoomBox }) {
  const half = sizePx / (2 * box.zoom)
  const x0 = Math.max(0, Math.floor(box.cx - half))
  const x1 = Math.min(sizePx, Math.ceil(box.cx + half))
  const y0 = Math.max(0, Math.floor(box.cy - half))
  const y1 = Math.min(sizePx, Math.ceil(box.cy + half))
  let d = ''
  for (let x = x0; x <= x1; x++) d += `M${x} ${y0}V${y1}`
  for (let y = y0; y <= y1; y++) d += `M${x0} ${y}H${x1}`
  return (
    <svg className="overlay pixel-edges" viewBox={`0 0 ${sizePx} ${sizePx}`} aria-hidden="true">
      <path d={d} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

/** Which way is north and east. In these pictures north is up and east is left. */
function Compass() {
  return (
    <svg className="compass" viewBox="0 0 60 60" aria-hidden="true">
      <path d="M46 46V18M46 46H18" />
      <path className="tip" d="M46 12l-4.5 8h9zM12 46l8-4.5v9z" />
      <text x="46" y="9" textAnchor="middle">
        N
      </text>
      <text x="5" y="50" textAnchor="middle">
        E
      </text>
    </svg>
  )
}

const BAR_LENGTHS_ARCSEC = [1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200]

/** A bar of a round number of arcseconds, so sizes and shifts in the picture can be judged. */
function ScaleBar({ arcsecPerScreenPx }: { arcsecPerScreenPx: number }) {
  // The longest round length that is no more than 110 screen pixels.
  const fitting = BAR_LENGTHS_ARCSEC.filter((length) => length / arcsecPerScreenPx <= 110)
  const length = fitting.length ? fitting[fitting.length - 1] : BAR_LENGTHS_ARCSEC[0]
  const text = length < 60 ? `${length} arcsec` : `${length / 60} arcmin`
  return (
    <div className="scale-bar" aria-hidden="true">
      <span style={{ width: `${length / arcsecPerScreenPx}px` }} />
      {text}
    </div>
  )
}
