// The table of every visit, at the top of the side column: one row per visit, the row of the
// visit on screen marked. The rows never change while the visits play; only the mark moves
// (a hairline and bold weight, so it is seen without colour, plus aria-current). Pressing a
// row's button shows that visit, like pressing its thumbnail.
//
// Beginner: the visit (number and month) and how far it had moved, in plain words.
// Expert: two lines per visit. The first has the measured shift since the start (east, north
// and total), the shift the catalogue predicts and how far the two differ; the second the
// dates, exposures, how clearly it is detected, the position's error and short warnings.
import { useLayoutEffect, useRef } from 'react'
import type { FramesReady } from '../api'
import { releaseFocusAfterPointer } from '../focus'
import { expertCells, plainResult, rowMonth, rowName, tableCaption, tableRows } from '../wording'

interface Props {
  data: FramesReady
  /** The visit on screen: its index among data.frames. */
  current: number
  expert: boolean
  disabled: boolean
  onShow: (index: number) => void
  /** The visitor stepped or chose a visit, so the marked row may be scrolled into the box (never while playing). */
  follow: boolean
}

export function VisitTable({ data, current, expert, disabled, onShow, follow }: Props) {
  const rows = tableRows(data)
  const table = useRef<HTMLTableElement>(null)

  // Keep the marked row inside the readout block when the visitor steps to it. Only the block
  // scrolls, never the page; and never while playing, so nothing moves by itself.
  useLayoutEffect(() => {
    if (!follow) return
    const box = table.current?.closest('.readout-block')
    const row = table.current?.querySelector<HTMLElement>('[aria-current="true"]')
    if (!(box instanceof HTMLElement) || !row) return
    const top = row.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop
    const bottom = top + (row.closest('tbody')?.offsetHeight ?? row.offsetHeight)
    if (top < box.scrollTop) box.scrollTop = top
    else if (bottom > box.scrollTop + box.clientHeight) box.scrollTop = bottom - box.clientHeight
  }, [follow, current])

  const button = (index: number, name: string) => (
    <button
      type="button"
      className="visit-row-button"
      aria-label={`Show ${name.toLowerCase()}`}
      disabled={disabled}
      onClick={(e) => {
        onShow(index)
        releaseFocusAfterPointer(e.currentTarget)
      }}
    >
      {name}
    </button>
  )

  if (!expert) {
    return (
      <table className="visit-table" ref={table} aria-label="Every visit, and how far its marked spot was from its first place">
        <colgroup>
          <col className="c-visit" />
          <col className="c-moved" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">Visit</th>
            {/* "Shift", not "Moved": the sentence over the table says when a shift is not movement. */}
            <th scope="col">Shift (arcseconds)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const index = row.index as number // tableRows keeps only the frames on the player
            const on = index === current
            return (
              <tr key={index} className="visit-row" aria-current={on ? 'true' : undefined}>
                <th scope="row">
                  {button(index, rowName(row.frame, data))} <span className="visit-row-when">{rowMonth(row.frame, data)}</span>
                </th>
                <td>{plainResult(row, data)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    )
  }

  return (
    <table className="visit-table expert" ref={table}>
      <caption>{tableCaption(data)}</caption>
      <colgroup>
        <col className="c-visit" />
        <col className="c-measured" />
        <col className="c-total" />
        <col className="c-predicted" />
        <col className="c-differ" />
      </colgroup>
      <thead>
        <tr>
          <th scope="col">Visit</th>
          <th scope="col">
            <span className="key measured">○</span> Measured
          </th>
          <th scope="col">Total</th>
          <th scope="col">
            <span className="key gaia">+</span> Predicted
          </th>
          <th scope="col">Differ</th>
        </tr>
      </thead>
      {rows.map((row) => {
        const index = row.index as number
        const on = index === current
        const cells = expertCells(row, data)
        return (
          <tbody key={index} className="visit-rows" aria-current={on ? 'true' : undefined}>
            <tr className="visit-row">
              <th scope="row">{button(index, rowName(row.frame, data))}</th>
              <td>{cells.measured}</td>
              <td>{cells.total}</td>
              <td>{cells.predicted}</td>
              <td>{cells.differ}</td>
            </tr>
            <tr className="visit-row-about">
              <td colSpan={5}>{cells.about}</td>
            </tr>
          </tbody>
        )
      })}
    </table>
  )
}
