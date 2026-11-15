// Where a popover goes. Pure, so it can be tested without a browser.

/** The gap kept to the window's edge and to the button. */
const EDGE = 16
const GAP = 8

export interface Box {
  left: number
  top: number
  right: number
  bottom: number
}

/**
 * Where to put a popover of `size` so that it is wholly inside `view` and does not cover
 * its button: above the button if it fits there, else below it, else wherever it fits best.
 * Sideways it is centred on the button and kept inside the window, so it can never make
 * the page wider.
 */
export function placePopover(button: Box, size: { w: number; h: number }, view: { w: number; h: number }): { left: number; top: number } {
  const middle = (button.left + button.right) / 2
  const left = Math.max(EDGE, Math.min(middle - size.w / 2, view.w - size.w - EDGE))
  const above = button.top - GAP - size.h
  const below = button.bottom + GAP
  let top: number
  if (above >= EDGE) top = above
  else if (below + size.h <= view.h - EDGE) top = below
  else top = Math.max(EDGE, Math.min(below, view.h - size.h - EDGE))
  return { left, top }
}
