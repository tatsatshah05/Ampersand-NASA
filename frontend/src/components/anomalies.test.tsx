// The Observe anomalies screen as it renders: the three candidate cards, their two pictures, the
// region picker and the sweep's groups, at both levels, on real data (the Viewer's frames for the
// candidates in fixtures/frames/, the exported sweep in public/anomalies/sweep.json).
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { EVERYWHERE, findAddress, PATCHES_CHECKED, PLANE, regionOptions, WATCH_LINK, WRITEUP_URL, type SweepData } from '../anomalies'
import type { FramesReady } from '../api'
import { FINDS } from '../finds'
import { MAYBE_PLAIN, NEIGHBOUR_PLAIN } from '../findsInfo'
import framesA from '../fixtures/frames/find_a_d6.json'
import framesB from '../fixtures/frames/find_b_d6.json'
import framesC from '../fixtures/frames/find_c_d6.json'
import { markNearFind, type PatchRegions, type WatchRow } from '../watchlist'
import { CandidateCards, CardPictures } from './CandidateCards'
import { RegionPicker } from './RegionPicker'
import { SweepGroups } from './SweepGroups'
import { Card, WatchlistView } from './WatchlistView'

const fsModule = 'node:fs'
const { readFileSync } = (await import(/* @vite-ignore */ fsModule)) as { readFileSync: (p: URL, encoding: string) => string }
const sweep = JSON.parse(readFileSync(new URL('../../public/anomalies/sweep.json', import.meta.url), 'utf8')) as SweepData

// The two real rows of the patch search at Candidate B's patch, from the test copy of the database
// (tests/data/watchlist/small.sqlite3), shaped as GET /api/watchlist shapes them (backend/watchlist.py, _row).
// Read with node:sqlite where this Node has it (24 does); elsewhere the tests that need them are skipped.
type Db = { prepare: (sql: string) => { get: (...a: unknown[]) => Record<string, unknown> | undefined } }
const sqliteModule = 'node:sqlite'
const sqlite = (await import(/* @vite-ignore */ sqliteModule).catch(() => null)) as { DatabaseSync: new (p: string, o: object) => Db } | null
const db = sqlite ? new sqlite.DatabaseSync(decodeURIComponent(new URL('../../../tests/data/watchlist/small.sqlite3', import.meta.url).pathname), { readOnly: true }) : null
function realRow(id: string): WatchRow {
  const r = db!.prepare('SELECT * FROM candidates WHERE id = ?').get(id)!
  const machine = JSON.parse(String(r.machine)) as Record<string, unknown>
  const group = r.grp as WatchRow['group']
  const row = {
    ...machine, id: r.id, group, ra: r.ra, dec: r.dec, first_seen: r.first_seen, last_seen: r.last_seen, patches: JSON.parse(String(r.patches)),
    votes: { real: 0, artefact: 0, unsure: 0, total: 0 }, my_vote: null, notes: [], rank_in_group: 1,
    ...(group === 'artefact' ? { best_detector: machine.detector } : { neowise: { state: 'waiting' } }),
  } as unknown as WatchRow
  return markNearFind(row)
}
const card = (row: WatchRow, level: 'beginner' | 'expert') => renderToStaticMarkup(<Card row={row} voter="test" level={level} onChange={() => undefined} />)

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

  it('in Expert put the numbers right under the pictures, then the neighbour and what was searched in their places', () => {
    const words = text(expert)
    for (const f of FINDS) {
      const at = (s: string) => words.indexOf(s)
      const start = at(`${f.name} In the constellation ${f.constellation}`)
      expect(start).toBeGreaterThanOrEqual(0)
      // pictures' note, then the neighbour, then the facts, then the allowed sentence, then the search and what was searched
      const order = ['Detector 6 (4.4–5.0 micrometres)', f.neighbour, 'Position', f.brightness, 'Rise', 'Last seen absent', 'First seen', f.allowed, f.probably, f.reportSearch, f.checked, f.status]
      // Each found after the one before it.
      let from = start
      for (const s of order) {
        const i = words.indexOf(s, from)
        expect(i, s).toBeGreaterThan(from)
        from = i
      }
    }
    // The rise is written as a sentence: capital first.
    expect(words).toContain('Rise More than 100 times within SPHEREx')
  })

  it('in Beginner say which star nearby is the steady neighbour, in the vetted plain words, and where each is', () => {
    for (const f of FINDS) {
      expect(text(beginner)).toContain(NEIGHBOUR_PLAIN[f.key])
      expect(text(beginner)).toContain(`In the constellation ${f.constellation}`)
      expect(text(beginner)).not.toContain(f.neighbour)
      expect(text(beginner)).not.toContain(f.checked)
    }
  })

  it('in Expert add the position in both notations, the brightness, the rise, the dates and the write-up', () => {
    const words = text(expert)
    for (const f of FINDS) {
      const row = sweep.survivors.find((s) => s.label === f.key)
      expect(words).toContain(f.brightness)
      expect(words).toContain(`${row?.sexagesimal}`)
      expect(words.toLowerCase()).toContain(`${row?.rise}`.toLowerCase())
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
  const REGIONS: PatchRegions = {
    regions: [{ key: '253.180380_-44.676970_0.1000', ra: 253.18038, dec: -44.67697, fov: 0.1, area_sq_deg: 0.01, constellation: 'Scorpius', last_searched: '2026-11-15T10:11:15Z', count: 7, counts: { eyes: 2, known: 3, artefact: 2 } }],
    total: 7, counts: { eyes: 2, known: 3, artefact: 2 }, patches_searched: 1, first_searched: '2026-11-15T10:11:15Z', last_searched: '2026-11-15T10:11:15Z',
  }
  const picker = (value: string, regions: PatchRegions | null = REGIONS) =>
    renderToStaticMarkup(<RegionPicker level="beginner" value={value} options={regionOptions(regions, sweep)} patches={regions} sweep={sweep} problem={null} onChange={() => undefined} />)

  it('names the chosen region first in its live lines, and offers "Show everywhere" right after the menu unless it is everywhere', () => {
    const patch = picker('253.180380_-44.676970_0.1000')
    expect(text(patch)).toMatch(/Choose a region .* Show everywhere Showing: Scorpius: Candidate B A patch 0\.1 degrees across/)
    expect(patch).toMatch(/<\/select><button type="button" class="region-everywhere">Show everywhere<\/button>/)
    expect(patch).toMatch(/<div class="region-about" aria-live="polite"><p>Showing: Scorpius: Candidate B<\/p>/)
    expect(text(picker(PLANE))).toContain("Show everywhere Showing: The Milky Way's plane (472.6 square degrees swept)")
    const all = picker(EVERYWHERE)
    expect(all).not.toContain('Show everywhere')
    expect(text(all)).toContain('Showing: Everywhere')
    // A region from the address, before the list of patches has arrived: the menu still holds it, by name, with no count.
    expect(picker('253.180380_-44.676970_0.1000', null)).toContain('<option value="253.180380_-44.676970_0.1000" selected="">A searched patch</option>')
  })

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
      '<label for="region-choice">Choose a region</label>',
      'Found by searching small patches',
      'role="tablist"',
      'Found by the sweep of the Milky Way’s plane',
    ]
    const at = order.map((s) => html.indexOf(s))
    expect(at.every((i) => i >= 0), JSON.stringify(at)).toBe(true)
    expect([...at].sort((x, y) => x - y)).toEqual(at)
    expect(html).toContain(`<option value="${EVERYWHERE}" selected="">Everywhere · 0 found</option>`)
    // Beginner's groups: the first is catalogued at every place, only not as changing.
    expect(html).toContain('Not listed as changing')
    expect(html).not.toContain('In no catalogue')
    expect(html).toContain('Set aside as false alarms')
    // Under the patch searches' heading, first: these are not the three at the top.
    expect(html.indexOf(PATCHES_CHECKED)).toBeGreaterThan(html.indexOf('Found by searching small patches'))
    expect(html.indexOf(PATCHES_CHECKED)).toBeLessThan(html.indexOf('Our computer search marked these spots'))
    // A line of links down the page, under the intro, to the three and to the region menu (which carry those ids).
    expect(text(html)).toContain('Jump to: the three candidates · Choose a region')
    expect(html).toContain('id="the-three-candidates"')
    expect(html).toContain('id="choose-region"')
    expect(html.indexOf('Jump to:')).toBeLessThan(html.indexOf('Not reported anywhere we could find'))
  })

  it('opens on the region the address names', () => {
    const html = screen('?watchlist=1&ui=beginner&region=plane')
    expect(text(html)).toContain("Showing: The Milky Way's plane")
    // The plane has none of the patch searches' groups.
    expect(html).not.toContain('role="tablist"')
  })

  it('in Expert names its groups as a scientist would', () => {
    const html = screen('?watchlist=1&ui=expert')
    expect(html).toContain('Blind searches of small patches')
    expect(html).toContain('Needs eyes')
    expect(html).toContain('Set aside as artefacts')
  })
})

describe('the patch search’s rows at Candidate B (the real rows of tests/data/watchlist/small.sqlite3)', () => {
  it.skipIf(!db)('the "mover" it set aside 0.7 arcsec from B says first whose place it is, links to B’s card, and is no "Example"', () => {
    const row = realRow('set-aside-mover-253.1807s44.6769')
    expect(row.group).toBe('artefact')
    expect(row.near_find).toMatchObject({ key: 'B', at: true })
    for (const level of ['beginner', 'expert'] as const) {
      const html = card(row, level)
      const words = text(html)
      // First, above the fold: whose place it is, and the way to its card (which carries that id).
      expect(words).toMatch(/^ #\d+ Moved Candidate B's place, 0\.7 arcseconds away\. Its card is at the top of this page\. See its card /)
      expect(html).toContain('<a href="#find-B">See its card</a>')
      expect(html).not.toContain('Example')
      expect(words.indexOf("Candidate B's place")).toBeLessThan(words.indexOf('Set aside.'))
    }
    // The patch search's own reason: in Beginner only inside the closed fold, with one plain line outside it.
    expect(text(card(row, 'beginner'))).not.toContain('its motion is not the same in every colour')
    expect(text(card(row, 'beginner'))).toContain('Set aside. The computer decided this movement was a false alarm.')
    expect(text(card(row, 'expert'))).toContain('its motion is not the same in every colour')
    expect(renderToStaticMarkup(<CandidateCards level="beginner" sweep={sweep} />)).toContain('id="find-B"')
  })

  it.skipIf(!db)('the steady star 10 arcsec from B keeps its caution, in short sentences, with the way to B’s card', () => {
    const row = realRow('changer-253.1838s44.6755')
    expect(row.near_find).toMatchObject({ key: 'B', at: false })
    const beginner = text(card(row, 'beginner'))
    const caution = "Verdict: caution. Candidate B is 10 arcseconds from here. Its light reaches this spot's measurement. So this change is most likely Candidate B's light. Its card is at the top of this page. See its card"
    expect(beginner).toContain(caution)
    expect(text(card(row, 'expert'))).toContain(caution)
    // Never offered as a candidate of its own.
    expect(beginner).not.toContain('Candidate, not a finding')
    expect(card(row, 'beginner')).not.toContain('candidate-tag')
  })
})

describe('the ruling’s "must not say" (docs/sweep/vetting/ruling.json) and the withdrawn positions', () => {
  type Ruling = { rulings: { candidate: string; must_not_say: string }[] }
  const ruling = JSON.parse(readFileSync(new URL('../../../docs/sweep/vetting/ruling.json', import.meta.url), 'utf8')) as Ruling
  const vetted = JSON.parse(readFileSync(new URL('../../../docs/sweep/vetting/candidates.json', import.meta.url), 'utf8')) as {
    candidates: { label: string; first_run_position_withdrawn: [number, number] }[]
  }
  const rendered = (level: 'beginner' | 'expert') => {
    vi.stubGlobal('window', { location: { search: `?watchlist=1&ui=${level}` }, localStorage: { getItem: () => null, setItem: () => undefined } })
    const screen = renderToStaticMarkup(<WatchlistView />)
    vi.unstubAllGlobals()
    const ready = (data: unknown) => ({ state: 'ready' as const, data: data as FramesReady })
    // What is said about the three: their cards and pictures, and the patch search's rows at B.
    const about = [
      renderToStaticMarkup(<CandidateCards level={level} sweep={sweep} />),
      ...[framesA, framesB, framesC].map((d, i) => renderToStaticMarkup(<CardPictures find={FINDS[i]} level={level} pictures={ready(d)} />)),
      ...(db ? [card(realRow('set-aside-mover-253.1807s44.6769'), level), card(realRow('changer-253.1838s44.6755'), level)] : []),
    ]
    const rest = [
      screen,
      renderToStaticMarkup(<SweepGroups level={level} sweep={sweep} problem={null} />),
      ...[EVERYWHERE, PLANE].map((v) =>
        renderToStaticMarkup(<RegionPicker level={level} value={v} options={regionOptions(null, sweep)} patches={null} sweep={sweep} problem={null} onChange={() => undefined} />),
      ),
    ]
    // Every word on screen, folds included (a scientist opens them).
    const words = (parts: string[]) => unescape(parts.join(' ').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ')
    return { all: words([...about, ...rest]), about: words(about) }
  }
  /** The phrases the ruling quotes as not to be said, e.g. 'Ratio 35' or 'A young star's outburst'. */
  const quoted = ruling.rulings
    .flatMap((r) => [...r.must_not_say.matchAll(/(?:^|[\s(])'(.+?)'(?=[\s,.;:)]|$)/g)].map((m) => m[1]))
    // The one quoted phrase that is allowed: the qualifier that may follow "new".
    .filter((p) => !p.startsWith('that we found in no catalogue'))
  /** The sweep's withdrawn values, which the ruling lists after "The sweep's": "153, 187, 17 and 0.2 mJy". */
  const withdrawnMjy = ruling.rulings.flatMap((r) =>
    r.must_not_say
      .split('\n')
      .filter((line) => /the sweep's/i.test(line))
      .flatMap((line) => [...line.matchAll(/((?:[\d,.]+(?:, | and ))*[\d.,]+) mJy/g)].flatMap((m) => m[1].split(/, | and /))),
  )

  it('reads them from the ruling', () => {
    expect(quoted).toEqual(expect.arrayContaining(['Discovery', 'new', 'confirmed', 'first ever seen', 'Ratio 35', "A young star's outburst", '178 and 300 mJy', 'GLIMPSE 4.1 arcsec']))
    expect(withdrawnMjy).toEqual(expect.arrayContaining(['153', '0.2', '644', '2,915', '24', '27.5', '86', '3.9', '8.5']))
    expect(vetted.candidates).toHaveLength(3)
  })

  for (const level of ['beginner', 'expert'] as const) {
    it(`appear nowhere on the screen in ${level}`, () => {
      const { all, about } = rendered(level)
      // The forms the ruling allows: its own qualified "new" (the search sentences, word for word) and "not confirmed".
      const checked = all
        .replace(/a new or brightening object/g, '')
        .replace(/candidates, not discoveries/g, '')
        .replace(/a new patch/g, '')
        .replace(/nobody has confirmed it yet|Not confirmed|not confirmed|None is confirmed|None of them is confirmed|confirmed by nobody/g, '')
      for (const phrase of quoted) {
        if (phrase === 'Discovery') expect(checked).not.toMatch(/discover/i)
        else if (phrase === 'new') expect(checked).not.toMatch(/\bnew\b/i)
        else if (phrase === 'confirmed') expect(checked).not.toMatch(/\bconfirmed\b/i)
        // "A nova" is forbidden as fact: never "is a nova" or "was a nova" (the known novae of the sweep are named as such).
        else if (/^an? (dust-forming )?nova$/i.test(phrase)) expect(checked).not.toMatch(/\b(is|was) an? (dust-forming )?nova\b/i)
        else if (phrase === '9 times') expect(checked).not.toMatch(/(?<![\d,.])9 times/)
        else expect(checked.toLowerCase(), phrase).not.toContain(phrase.toLowerCase())
      }
      // The sweep's withdrawn values, wherever the three are spoken of (other objects of the sweep have numbers of their own).
      for (const n of withdrawnMjy) expect(about, `${n} mJy`).not.toMatch(new RegExp(`(?<![\\d,.])${n.replace(/[.,]/g, '\\$&')} mJy`))
      for (const c of vetted.candidates) {
        const [ra, dec] = c.first_run_position_withdrawn
        // As the sweep wrote them (5 decimals), as whole numbers: "44.67687" never, "44.67697" (the corrected place) of course.
        for (const v of new Set([String(ra), String(Math.abs(dec)), ra.toFixed(5), Math.abs(dec).toFixed(5)]))
          expect(checked, `${c.label}: ${v}`).not.toMatch(new RegExp(`(?<!\\d)${v.replace('.', '\\.')}(?!\\d)`))
      }
      expect(checked).not.toMatch(/never seen before|first ever|new planet/i)
    })
  }
})
