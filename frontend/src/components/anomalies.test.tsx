// The Observe anomalies screen as it renders: the three candidate cards, their two pictures, the
// region picker and the sweep's groups, at both levels, on real data (the Viewer's frames for the
// candidates in fixtures/frames/, the exported sweep in public/anomalies/sweep.json).
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { EVERYWHERE, findAddress, PLANE, regionOptions, WATCH_LINK, WRITEUP_URL, type SweepData } from '../anomalies'
import type { FramesReady } from '../api'
import { FINDS } from '../finds'
import { MAYBE_PLAIN } from '../findsInfo'
import framesA from '../fixtures/frames/find_a_d6.json'
import framesC from '../fixtures/frames/find_c_d6.json'
import { CandidateCards, CardPictures } from './CandidateCards'
import { RegionPicker } from './RegionPicker'
import { SweepGroups } from './SweepGroups'
import { WatchlistView } from './WatchlistView'

const fsModule = 'node:fs'
const { readFileSync } = (await import(/* @vite-ignore */ fsModule)) as { readFileSync: (p: URL, encoding: string) => string }
const sweep = JSON.parse(readFileSync(new URL('../../public/anomalies/sweep.json', import.meta.url), 'utf8')) as SweepData

const BANNED = /\b(sigma|flux|fluxes|epoch|epochs|detector|detectors|centroid|centroids|mJy|aperture|photometry|ephemeris|S\/N)\b|σ/
/** The visible text of some markup, leaving out what sits in a closed <details> (as the checks read it). */
const text = (html: string) =>
  html
    .replace(/<details(?![^>]*\sopen)[^>]*>[\s\S]*?<\/details>/g, (fold) => /<summary[^>]*>([\s\S]*?)<\/summary>/.exec(fold)?.[1] ?? '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, ' ')
const unescape = (s: string) => s.replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"')

afterEach(() => vi.unstubAllGlobals())

describe('the three candidate cards', () => {
  const beginner = renderToStaticMarkup(<CandidateCards level="beginner" sweep={sweep} />)
  const expert = renderToStaticMarkup(<CandidateCards level="expert" sweep={sweep} />)

  it('are A, B and C, each with the allowed sentence, the search for earlier reports and the status, word for word', () => {
    for (const [level, html] of [['beginner', beginner], ['expert', expert]] as const) {
      expect(html.match(/<li class="anomaly-card"/g)).toHaveLength(3)
      const words = text(html)
      for (const f of FINDS) {
        expect(words).toContain(f.name)
        expect(words).toContain(f.allowed)
        expect(words).toContain(f.reportSearch)
        expect(unescape(html)).toContain(`href="${findAddress(f, level)}"`)
      }
      expect(words.match(/Not confirmed\. Not yet reported to astronomers\./g)).toHaveLength(3)
      expect(words.match(new RegExp(WATCH_LINK, 'g'))).toHaveLength(3)
      // No votes on these three.
      expect(html).not.toMatch(/Looks real|Looks like an artefact|Not sure|<textarea/)
    }
  })

  it('say "probably" plainly in Beginner and as the reviewers did in Expert', () => {
    for (const f of FINDS) {
      expect(text(beginner)).toContain(MAYBE_PLAIN[f.key])
      expect(text(beginner)).not.toContain(f.probably)
      expect(text(expert)).toContain(f.probably)
    }
  })

  it('in Expert add the position in both notations, the brightness, the rise, the dates and the write-up', () => {
    const words = text(expert)
    for (const f of FINDS) {
      const row = sweep.survivors.find((s) => s.label === f.key)
      expect(words).toContain(f.brightness)
      expect(words).toContain(`${row?.sexagesimal}`)
      expect(words).toContain(`${row?.rise}`)
      expect(words).toContain(`${row?.last_non_detection}`)
      expect(words).toContain(`${row?.first_detection}`)
    }
    expect(words).toContain('RA 270.80408°, Dec −23.46818°')
    expect(expert.match(new RegExp(`href="${WRITEUP_URL}"`, 'g'))).toHaveLength(3)
    expect(beginner).not.toContain(WRITEUP_URL)
  })

  it('use no scientist’s word in Beginner, and never "discovery" or "never seen before"', () => {
    expect(text(beginner)).not.toMatch(BANNED)
    for (const html of [beginner, expert]) expect(text(html)).not.toMatch(/discover|never seen before/i)
  })
})

describe('a card’s two pictures', () => {
  const ready = (data: unknown) => ({ state: 'ready' as const, data: data as FramesReady })

  it('are the Viewer’s own frames of the last visit not seen and the brightest, dated, with a text alternative', () => {
    const a = FINDS[0]
    const html = renderToStaticMarkup(<CardPictures find={a} level="beginner" pictures={ready(framesA)} />)
    expect([...html.matchAll(/<img src="([^"]+)"/g)].map((m) => m[1])).toEqual(['/frames/d1ec308f1a88dcfd/epoch1.png', '/frames/d1ec308f1a88dcfd/epoch2.png'])
    expect([...html.matchAll(/alt="([^"]+)"/g)].map((m) => unescape(m[1]))).toEqual([
      "SPHEREx picture of Candidate A's place, 24 Aug–4 Sep 2025: nothing is seen at the marked place. North is up.",
      "SPHEREx picture of Candidate A's place, 28 Mar–1 Apr 2026: the source at the marked place at its brightest. North is up.",
    ])
    expect(text(html)).toMatch(/Not seen 24 Aug–4 Sep 2025 At its brightest 28 Mar–1 Apr 2026/)
    const expert = renderToStaticMarkup(<CardPictures find={a} level="expert" pictures={ready(framesA)} />)
    expect(text(expert)).toMatch(/Last visit not detected \(visit 1\) 24 Aug–4 Sep 2025 Brightest visit \(visit 2\) 28 Mar–1 Apr 2026/)
  })

  it('for C are its February–March 2026 visit, never the spoiled April one', () => {
    const html = renderToStaticMarkup(<CardPictures find={FINDS[2]} level="beginner" pictures={ready(framesC)} />)
    expect(html).toContain('/frames/bebfd7e8d91aff80/epoch2.png')
    expect(html).not.toContain('epoch3.png')
  })

  it('say why there is no picture rather than show two that would not show the change', () => {
    const loading = renderToStaticMarkup(<CardPictures find={FINDS[1]} level="beginner" pictures={{ state: 'loading' }} />)
    expect(loading).not.toContain('<img')
    expect(text(loading)).toContain('Loading the picture…')
    const failed = renderToStaticMarkup(<CardPictures find={FINDS[1]} level="beginner" pictures={{ state: 'error', message: 'The server could not be reached.' }} />)
    expect(text(failed)).toContain('No picture: The server could not be reached.')
    const one = { ...(framesA as unknown as FramesReady), frames: (framesA as unknown as FramesReady).frames.slice(1) }
    expect(text(renderToStaticMarkup(<CardPictures find={FINDS[0]} level="beginner" pictures={ready(one)} />))).toContain('No picture: the visits do not show it unseen and then seen.')
  })
})

describe('the sweep’s groups', () => {
  it('list all 14 survivors in four groups, each with its count, place, name and a link to the Viewer', () => {
    for (const level of ['beginner', 'expert'] as const) {
      const html = renderToStaticMarkup(<SweepGroups level={level} sweep={sweep} problem={null} />)
      expect(html.match(/<li class="sweep-item/g)).toHaveLength(14)
      expect([...html.matchAll(/<span class="sweep-count">\((\d+)\)<\/span>/g)].map((m) => Number(m[1]))).toEqual([3, 2, 6, 3])
      expect(html.match(/href="\?ra=/g)).toHaveLength(14)
      expect(html.match(/href="#find-[ABC]"/g)).toHaveLength(3)
      if (level === 'beginner') expect(text(html)).not.toMatch(BANNED)
    }
  })

  it('say when the list could not be had', () => {
    expect(text(renderToStaticMarkup(<SweepGroups level="beginner" sweep={null} problem="the sweep’s list could not be loaded" />))).toContain('could not be loaded')
  })
})

describe('the region picker', () => {
  it('offers everywhere, the plane and each patch with its count, and says what the chosen one is', () => {
    const options = regionOptions(null, sweep)
    const html = renderToStaticMarkup(
      <RegionPicker level="beginner" value={PLANE} options={options} patches={null} sweep={sweep} problem={null} onChange={() => undefined} />,
    )
    expect(text(html)).toContain('Choose a region')
    expect([...html.matchAll(/<option[^>]*>([^<]+)<\/option>/g)].map((m) => unescape(m[1]))).toEqual([
      'Everywhere · 14 found',
      "The Milky Way's plane (472.6 square degrees swept) · 14 found",
    ])
    expect(text(html)).toContain('472.6 square degrees of the Milky Way\'s plane, swept on 14 November 2026.')
    expect(html).toMatch(/<select id="region-choice"/)
    expect(html).toMatch(/<label for="region-choice">Choose a region<\/label>/)
  })
})

describe('the screen', () => {
  const screen = (search: string) => {
    vi.stubGlobal('window', { location: { search }, localStorage: { getItem: () => null, setItem: () => undefined } })
    return renderToStaticMarkup(<WatchlistView />)
  }

  it('is titled Observe anomalies, says what an anomaly is first, then the three, then the region and its groups', () => {
    const html = screen('?watchlist=1&ui=beginner')
    const order = [
      '<h1>Observe anomalies</h1>',
      'An anomaly is something our searches saw change',
      'Not reported anywhere we could find',
      'class="anomaly-card"',
      'Choose a region',
      'Found by searching small patches',
      'role="tablist"',
      'Found by the sweep of the Milky Way’s plane',
    ]
    const at = order.map((s) => html.indexOf(s))
    expect(at.every((i) => i >= 0), JSON.stringify(at)).toBe(true)
    expect([...at].sort((x, y) => x - y)).toEqual(at)
    expect(html).toContain(`<option value="${EVERYWHERE}" selected="">Everywhere · 0 found</option>`)
    // The groups' own words stay as they were.
    expect(html).toContain('In no catalogue')
    expect(html).toContain('Set aside as false alarms')
  })

  it('in Expert names its groups as a scientist would', () => {
    const html = screen('?watchlist=1&ui=expert')
    expect(html).toContain('Blind searches of small patches')
    expect(html).toContain('Needs eyes')
    expect(html).toContain('Set aside as artefacts')
  })
})
