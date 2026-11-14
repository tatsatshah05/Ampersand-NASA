// The target's measured positions, and how far it has moved, from an /api/frames response.
import { NATIVE_PIXEL_ARCSEC, skyOffsetArcsec, type Centroid, type Frame, type FramesReady } from './api'
import type { Point } from './zoom'

/**
 * The API counts picture pixels from the top-left with whole numbers at pixel centres;
 * drawing puts pixel i from i to i+1, so a position moves by half a pixel each way.
 */
export const toPicture = (p: { x: number; y: number }): Point => ({ x: p.x + 0.5, y: p.y + 0.5 })

/**
 * Where the object started: its first measured position. In a difference view against
 * the first visit, that visit is the one subtracted and is not among the frames, so the
 * API reports its details separately as `reference_frame`.
 */
export function startCentroid(data: FramesReady): Centroid | null {
  return data.reference_frame?.centroid ?? data.frames.find((f) => f.centroid)?.centroid ?? null
}

/** Every measured position in time order. A frame with no measured position is skipped. */
export function measuredPath(data: FramesReady): Centroid[] {
  const first = data.reference_frame?.centroid
  const rest = data.frames.flatMap((f) => (f.centroid ? [f.centroid] : []))
  return first ? [first, ...rest] : rest
}

/**
 * A shift smaller than this is not reported as real movement. The pictures are built
 * from 6.15 arcsecond pixels and measured positions of stars that do not move scatter
 * by up to about 1.5 arcseconds (CLAUDE.md, "Step 1 result").
 */
export const SMALL_SHIFT_ARCSEC = NATIVE_PIXEL_ARCSEC / 3

export interface Shift {
  /** Arcseconds on the sky; east and north can be negative (west, south). */
  east: number
  north: number
  total: number
}

export function shiftBetween(from: Centroid, to: Centroid): Shift {
  const { east, north } = skyOffsetArcsec(from, to)
  return { east, north, total: Math.hypot(east, north) }
}

/** How far the object in this frame is from where it started; null when either was not measured. */
export function shiftFromStart(data: FramesReady, frame: Frame): Shift | null {
  const start = startCentroid(data)
  return start && frame.centroid ? shiftBetween(start, frame.centroid) : null
}

/** The shift from the first measured position to the last: null with fewer than two. */
export function overallShift(data: FramesReady): Shift | null {
  const path = measuredPath(data)
  return path.length >= 2 ? shiftBetween(path[0], path[path.length - 1]) : null
}
