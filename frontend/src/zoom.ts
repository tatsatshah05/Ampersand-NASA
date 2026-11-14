// Which part of the picture the viewer shows. Positions are in image pixels counted
// from the top-left, where pixel i spans i to i+1 (so the API's pixel centres are +0.5).
// The picture is square, sizePx on a side, and so is the stage it is shown in.

export interface ZoomBox {
  /** 1 shows the whole picture; 2 shows half of it across; and so on. */
  zoom: number
  /** The picture point at the middle of the stage. */
  cx: number
  cy: number
}

export interface Point {
  x: number
  y: number
}

/** Image pixels from top to bottom when the view starts zoomed in on the target. */
const START_SPAN_PX = 80
/** Image pixels from top to bottom at the closest zoom. */
const CLOSEST_SPAN_PX = 6

export const maxZoom = (sizePx: number) => Math.max(1, sizePx / CLOSEST_SPAN_PX)

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)

/** Keep the zoom between the whole picture and the closest zoom, and the picture over the whole stage. */
export function clampBox(box: ZoomBox, sizePx: number): ZoomBox {
  const zoom = clamp(box.zoom, 1, maxZoom(sizePx))
  const half = sizePx / (2 * zoom) // half of the visible span, in image pixels
  return { zoom, cx: clamp(box.cx, half, sizePx - half), cy: clamp(box.cy, half, sizePx - half) }
}

/**
 * Where the view starts. Zoomed in on the target's first measured position, about 80
 * image pixels (160 arcseconds at 2 arcseconds a pixel) from top to bottom: a star's
 * image is about 5 pixels wide, so a few neighbours stay in view as a still reference
 * while a shift of a few pixels spans tens of screen pixels. With no measured position,
 * the whole picture.
 */
export function startBox(sizePx: number, target: Point | null): ZoomBox {
  if (!target) return { zoom: 1, cx: sizePx / 2, cy: sizePx / 2 }
  return clampBox({ zoom: Math.max(1, sizePx / START_SPAN_PX), cx: target.x, cy: target.y }, sizePx)
}

/**
 * Zoom by `factor`, keeping the picture point under (fx, fy) where it is. fx and fy
 * are positions within the stage from 0 (left, top) to 1 (right, bottom).
 */
export function zoomAbout(box: ZoomBox, factor: number, fx: number, fy: number, sizePx: number): ZoomBox {
  const zoom = clamp(box.zoom * factor, 1, maxZoom(sizePx))
  const x = box.cx + ((fx - 0.5) * sizePx) / box.zoom // the picture point under the pointer
  const y = box.cy + ((fy - 0.5) * sizePx) / box.zoom
  return clampBox({ zoom, cx: x - ((fx - 0.5) * sizePx) / zoom, cy: y - ((fy - 0.5) * sizePx) / zoom }, sizePx)
}

/** Move the view by a share of the stage's width and height (positive: right, down). */
export function panBy(box: ZoomBox, dfx: number, dfy: number, sizePx: number): ZoomBox {
  return clampBox({ ...box, cx: box.cx + (dfx * sizePx) / box.zoom, cy: box.cy + (dfy * sizePx) / box.zoom }, sizePx)
}

/** The picture point under a position within the stage (0 to 1 each way). */
export function pointAt(box: ZoomBox, fx: number, fy: number, sizePx: number): Point {
  return { x: box.cx + ((fx - 0.5) * sizePx) / box.zoom, y: box.cy + ((fy - 0.5) * sizePx) / box.zoom }
}
