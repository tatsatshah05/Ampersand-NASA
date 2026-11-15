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

/** One visit's details: a frame, or the subtracted first visit of a difference view (which has no picture). */
export type VisitFrame = Omit<Frame, 'image'>

/**
 * One row of the table of visits: everything the page says about one visit, worked out
 * once for the whole view, so that nothing has to be rewritten when the visit on screen
 * changes. Shifts are measured from the first visit with a measured position (`start`),
 * the same place the motion markers start from, and the prediction from that visit's
 * predicted place, so the two are compared from the same date.
 */
export interface VisitRow {
  /** Where the visit is among `data.frames` (what the player shows); null for the subtracted visit of a difference view. */
  index: number | null
  frame: VisitFrame
  /** The shifts are measured from this visit. */
  start: boolean
  /** Measured shift since the start; null for the start itself and for a visit with no position. */
  shift: Shift | null
  /** The shift the catalogue (or the motion given in the address) predicts since the start; null when nothing is predicted. */
  predicted: { east: number; north: number } | null
  /** How far the measured and the predicted shift differ, in arcseconds. */
  differ: number | null
  /** The measured shift is under SMALL_SHIFT_ARCSEC (a third of a SPHEREx pixel), so it may be measurement error. */
  withinError: boolean
  /** The smallest shift trusted as real from the start to this visit (realShiftBar); null without both positions. */
  bar: number | null
  /** The measured shift is at least `bar`: the only kind the page calls movement. */
  real: boolean
}

/** Every visit of the view in time order (the subtracted one of a difference view first), with its shifts. */
export function visitRows(data: FramesReady): VisitRow[] {
  const all: { frame: VisitFrame; index: number | null }[] = [
    ...(data.reference_frame ? [{ frame: data.reference_frame, index: null }] : []),
    ...data.frames.map((frame, index) => ({ frame, index })),
  ]
  const startAt = all.findIndex((v) => v.frame.centroid)
  const from = startAt >= 0 ? all[startAt].frame : null
  return all.map(({ frame, index }, k) => {
    const start = k === startAt
    const shift = !start && from?.centroid && frame.centroid ? shiftBetween(from.centroid, frame.centroid) : null
    const predicted = !start && from?.predicted && frame.predicted ? skyOffsetArcsec(from.predicted, frame.predicted) : null
    const differ = shift && predicted ? Math.hypot(shift.east - predicted.east, shift.north - predicted.north) : null
    const bar = shift && from?.centroid && frame.centroid ? realShiftBar(from.centroid, frame.centroid) : null
    const real = shift !== null && bar !== null && shift.total >= bar
    return { index, frame, start, shift, predicted, differ, withinError: shift !== null && shift.total < SMALL_SHIFT_ARCSEC, bar, real }
  })
}

/** The rows with a measured position. */
export const measuredRows = (rows: VisitRow[]): VisitRow[] => rows.filter((r) => r.frame.centroid)

/**
 * The smallest shift trusted as real between two measured positions: a third of a pixel, or
 * three times their combined position error when that is larger (a saturated core has an error
 * of 1 to 2 arcseconds, so the bar rises with it).
 */
export function realShiftBar(from: Centroid, to: Centroid): number {
  return Math.max(SMALL_SHIFT_ARCSEC, 3 * Math.hypot(from.err_arcsec ?? 0, to.err_arcsec ?? 0))
}

/** True when the shift from `from` to `to` is larger than the bar above. */
export function isRealShift(from: Centroid, to: Centroid): boolean {
  return shiftBetween(from, to).total >= realShiftBar(from, to)
}

/** The first and last measured positions, or null with fewer than two. */
export function overallEnds(data: FramesReady): [Centroid, Centroid] | null {
  const path = measuredPath(data)
  return path.length >= 2 ? [path[0], path[path.length - 1]] : null
}

/**
 * How far the catalogue says the target should have moved between the start picture and this
 * one (from the predicted positions the frames carry); null when either is missing.
 */
export function expectedShift(data: FramesReady, frame: Frame): Shift | null {
  const start = startCentroid(data)
  const all = data.reference_frame ? [data.reference_frame, ...data.frames] : data.frames
  const first = all.find((f) => f.centroid === start)
  return first?.predicted && frame.predicted ? shiftBetween(first.predicted as Centroid, frame.predicted as Centroid) : null
}
