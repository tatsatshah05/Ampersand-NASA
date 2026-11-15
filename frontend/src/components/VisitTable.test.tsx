// The table of every visit: its words are the same whichever visit is on screen; only the
// mark (aria-current, the bold name, the hairline) moves.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { FramesReady } from '../api'
import barnardJson from '../fixtures/frames/barnard_d5.json'
import epsIndJson from '../fixtures/frames/epsindib_request_d5.json'
import { VisitTable } from './VisitTable'

const barnard = barnardJson as unknown as FramesReady
const epsInd = epsIndJson as unknown as FramesReady
const table = (data: FramesReady, current: number, expert: boolean) =>
  renderToStaticMarkup(<VisitTable data={data} current={current} expert={expert} disabled={false} onShow={() => undefined} follow={false} />)
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()

describe('the table of visits', () => {
  for (const expert of [false, true]) {
    const level = expert ? 'Expert' : 'Beginner'
    it(`${level}: the same words whichever visit is on screen, and only that one marked`, () => {
      const [a, b, c] = [0, 1, 2].map((i) => table(barnard, i, expert))
      expect(text(a)).toBe(text(b))
      expect(text(b)).toBe(text(c))
      expect(a.match(/aria-current="true"/g)).toHaveLength(1)
      // Without the mark the markup is identical: nothing else depends on the visit shown.
      const unmarked = (h: string) => h.replace(/ aria-current="true"/g, '')
      expect(unmarked(a)).toBe(unmarked(c))
    })
    it(`${level}: a real table, with a button per visit named for it`, () => {
      const html = table(epsInd, 0, expert)
      expect(html).toMatch(expert ? /<caption>/ : /<table class="visit-table" aria-label="/)
      expect(html.match(/<th scope="row">/g)).toHaveLength(4)
      for (const n of [1, 2, 3, 4]) expect(html).toContain(`aria-label="Show visit ${n}"`)
    })
  }
  it('Expert keys the measured and predicted columns to the marks on the picture', () => {
    const html = table(barnard, 0, true)
    expect(html).toContain('<span class="key measured">○</span> Measured')
    expect(html).toContain('<span class="key gaia">+</span> Predicted')
    expect(html).toContain('+ from Gaia.')
  })
})
