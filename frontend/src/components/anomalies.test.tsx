// The Observe anomalies screen as it renders: the three candidate cards, their two pictures, the
// region picker and the sweep's groups, at both levels, on real data (the Viewer's frames for the
// candidates in fixtures/frames/, the exported sweep in public/anomalies/sweep.json).
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { findPatch, openWatched, searchThisPatch } from '../watchPatch'
import { AGAIN_LINE, EVERYWHERE, findAddress, KEEP_LOOKING, NOTHING_FOUND, FIRST_SEARCH_NOTE, lastSearchedLine, patchIsQuiet, patchKey, PATCHES_CHECKED, PLANE, regionOptions, WATCH_LINK, WRITEUP_URL, type SweepData } from '../anomalies'
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
    expect(text(patch)).toMatch(/Pick a patch of sky .* Show everywhere Showing: Scorpius: Candidate B A patch 0\.1 degrees across/)
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
    expect(text(html)).toContain('Pick a patch of sky')
    expect([...html.matchAll(/<option[^>]*>([^<]+)<\/option>/g)].map((m) => unescape(m[1]))).toEqual([
      'Everywhere · 14 found',
      "The Milky Way's plane (472.6 square degrees swept) · 14 found",
    ])
    expect(text(html)).toContain('472.6 square degrees of the Milky Way\'s plane, swept on 14 November 2026.')
    expect(html).toMatch(/<select id="region-choice"/)
    expect(html).toMatch(/<label for="region-choice">[^<]*<\/label>/)
    expect(text(html)).toContain('Or choose a patch that is already being watched:')
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
      'Pick a patch of sky',
      'Type a star’s name or a place in the sky.',
      'A name or coordinates',
      'Watch this patch',
      'Coordinates are right ascension (RA) first, then declination (Dec): both in degrees, 269.4463\u00a04.7682,',
      'Or choose a patch that is already being watched:',
      'Not reported anywhere we could find',
      'class="anomaly-card"',
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
    expect(text(html)).toContain('Jump to: Pick a patch of sky · the three candidates')
    expect(html).toContain('id="the-three-candidates"')
    expect(html).toContain('id="choose-region"')
    expect(html.indexOf('Jump to:')).toBeLessThan(html.indexOf('Pick a patch of sky'))
  })

  it('opens on the region the address names', () => {
    const html = screen('?watchlist=1&ui=beginner&region=plane')
    expect(text(html)).toContain("Showing: The Milky Way's plane")
    // The plane has none of the patch searches' groups.
    expect(html).not.toContain('role="tablist"')
  })

  it('has the Demo mode button in its top bar, as every screen does', () => {
    const html = screen('?watchlist=1&ui=beginner')
    const top = html.slice(html.indexOf('<header class="topbar'), html.indexOf('</header>'))
    expect(top).toContain('class="tour-start"')
    expect(top).toContain('>Demo mode</button>')
  })

  it('puts a single chosen patch’s results under the picker, before the three candidates', () => {
    const html = screen('?watchlist=1&ui=beginner&region=253.180380_-44.676970_0.1000')
    const order = ['Pick a patch of sky', 'Found by searching this patch', 'role="tablist"', 'Not reported anywhere we could find']
    const at = order.map((o) => html.indexOf(o))
    expect(at.every((i) => i >= 0), JSON.stringify(at)).toBe(true)
    expect([...at].sort((x, y) => x - y)).toEqual(at)
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
        .replace(/new pictures/g, '')
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

// ---- watching a patch: the flows, against a mocked server ----------------------------------------------

describe('watching a patch', () => {
  const B = { ra: 253.18038, dec: -44.67697 }
  const KEY = patchKey(B.ra, B.dec, 0.1)
  const regionEntry = { key: KEY, ...B, fov: 0.1, area_sq_deg: 0.01, constellation: 'Scorpius', last_searched: '2026-11-15T19:02:11Z', count: 2, counts: { eyes: 1, known: 1, artefact: 0 } }
  const regionsWith = (list: object[]) => ({ regions: list, total: 2, counts: { eyes: 1, known: 1, artefact: 0 }, patches_searched: list.length, first_searched: null, last_searched: null })
  const watchAnswer = (over: object = {}) => ({
    key: KEY, ...B, fov: 0.1, searched: true, last_searched: '2026-11-15T19:02:11Z', pictures_until: '2026-09-22', exposures: 364, new_pictures: false, ...over,
  })
  const done = { status: 'done', seconds: 5, detector_now: null, detectors_done: 6, detectors_total: 6, searches_ahead: 0, searching_again: false, result: { field: {}, objects: [], rejected: [], summary: {}, limits: '' } }

  /** A fake server: answers by path; every request is logged. */
  function server(routes: Record<string, () => unknown | { status: number; body: unknown }>) {
    const calls: string[] = []
    vi.stubGlobal('fetch', async (input: string) => {
      const url = String(input)
      calls.push(url)
      const path = url.split('?')[0]
      const route = routes[path]
      if (!route) return new Response('{}', { status: 404 })
      const out = route() as { status?: number; body?: unknown } & Record<string, unknown>
      const failed = typeof out.status === 'number' && 'body' in out
      return new Response(JSON.stringify(failed ? out.body : out), { status: failed ? (out.status as number) : 200 })
    })
    return calls
  }
  const noop = () => undefined

  it('typing a name runs the search, then the patch is chosen from the regions list', async () => {
    const calls = server({
      '/api/resolve': () => ({ name: 'NAME Scorpius B', ra: B.ra, dec: B.dec, source: 'SIMBAD' }),
      '/api/search': () => done,
      '/api/watchlist/regions': () => regionsWith([regionEntry]),
      '/api/watch': () => watchAnswer(),
    })
    const place = await findPatch('Candidate Zed')
    expect(place).toMatchObject({ ok: true, ra: B.ra, dec: B.dec })
    if (!place.ok) return
    const seen: string[] = []
    const out = await searchThisPatch(place.patch, 'beginner', new AbortController().signal, (line) => seen.push(line))
    expect(out.kind).toBe('done')
    if (out.kind !== 'done') return
    expect(out.key).toBe(KEY)
    expect(out.regions?.regions.map((r) => r.key)).toContain(KEY)
    expect(out.chosen).toBe(true)
    expect(out.watch?.searched).toBe(true)
    expect(calls.some((u) => u.startsWith('/api/search?') && u.includes('detectors=123456') && u.includes('fov=0.1'))).toBe(true)
    // Search first, then the regions, and the patch's watch lines.
    expect(calls.findIndex((u) => u.startsWith('/api/search'))).toBeLessThan(calls.findIndex((u) => u.startsWith('/api/watchlist/regions')))
    expect(calls.some((u) => u.startsWith('/api/watch?'))).toBe(true)
  })

  it('reads coordinates without asking the name service, and says why a typed position cannot be read', async () => {
    const calls = server({})
    const p = await findPatch('253.18038389 -44.67697')
    expect(p.ok).toBe(true)
    if (p.ok) {
      expect(p.ra).toBeCloseTo(253.18038, 5)
      expect(p.patch.key).toBe(patchKey(p.ra, p.dec, 0.1))
      expect(p.patch.fov).toBe(0.1)
    }
    expect(calls).toEqual([])
    expect(await findPatch('   ')).toEqual({ ok: false, text: 'Type a name or coordinates first.' })
    const bad = await findPatch('400 10')
    expect(bad.ok).toBe(false)
    server({ '/api/resolve': () => ({ status: 404, body: { detail: 'SIMBAD does not know that name.' } }) })
    expect(await findPatch('Nowhereville')).toEqual({ ok: false, text: 'SIMBAD does not know that name.' })
  })

  it('a search that finds nothing says so, keeps the patch as the one watched, and still has the watch lines', async () => {
    server({
      '/api/search': () => done,
      '/api/watchlist/regions': () => regionsWith([]),
      '/api/watch': () => watchAnswer(),
    })
    const out = await searchThisPatch({ ...B, fov: 0.1, key: KEY }, 'beginner', new AbortController().signal, noop)
    expect(out.kind).toBe('done')
    if (out.kind !== 'done') return
    expect(out.chosen).toBe(false)
    expect(out.nothing).toBe(NOTHING_FOUND)
    expect(NOTHING_FOUND).toBe('Nothing moved or changed in this patch in SPHEREx’s pictures so far.')
    expect(lastSearchedLine(out.watch!)).toBe('Last searched on 15 November 2026, with SPHEREx’s pictures up to 22 September 2026.')
    expect(KEEP_LOOKING).toContain('We keep looking')
    expect(FIRST_SEARCH_NOTE).toContain('nobody has searched before')
  })

  it('a quiet patch that the list holds with nothing in it is chosen, and still says that nothing was found', async () => {
    const quiet = { ...regionEntry, count: 0, counts: { eyes: 0, known: 0, artefact: 0 } }
    server({
      '/api/search': () => done,
      '/api/watchlist/regions': () => regionsWith([quiet]),
      '/api/watch': () => watchAnswer(),
    })
    const out = await searchThisPatch({ ...B, fov: 0.1, key: KEY }, 'beginner', new AbortController().signal, noop)
    expect(out.kind).toBe('done')
    if (out.kind !== 'done') return
    expect(out.chosen).toBe(true)
    expect(out.nothing).toBe(NOTHING_FOUND)
    // The screen says so for a quiet patch however it was opened, and for no other choice.
    expect(patchIsQuiet(KEY, regionsWith([quiet]) as never)).toBe(true)
    expect(patchIsQuiet(KEY, regionsWith([regionEntry]) as never)).toBe(false)
    expect(patchIsQuiet(EVERYWHERE, regionsWith([quiet]) as never)).toBe(false)
    expect(patchIsQuiet(KEY, null)).toBe(false)
  })

  it('shows a failed search’s own error, and survives /api/watch failing', async () => {
    server({ '/api/search': () => ({ ...done, status: 'failed', error: 'The archive did not answer.', result: undefined }) })
    const failed = await searchThisPatch({ ...B, fov: 0.1, key: KEY }, 'beginner', new AbortController().signal, noop)
    expect(failed).toEqual({ kind: 'failed', error: 'The archive did not answer.' })
    server({ '/api/search': () => done, '/api/watchlist/regions': () => regionsWith([regionEntry]), '/api/watch': () => ({ status: 500, body: { detail: 'x' } }) })
    const out = await searchThisPatch({ ...B, fov: 0.1, key: KEY }, 'beginner', new AbortController().signal, noop)
    expect(out).toMatchObject({ kind: 'done', chosen: true, watch: null })
  })

  it('opening a patch whose /api/watch says new_pictures searches it again, with the “new pictures” line', async () => {
    let asked = 0
    const calls = server({
      '/api/watch': () => watchAnswer(asked++ === 0 ? { new_pictures: true } : { pictures_until: '2027-03-01' }),
      '/api/search': () => ({ ...done, searching_again: true }),
      '/api/watchlist/regions': () => regionsWith([regionEntry]),
    })
    const lines: string[] = []
    const out = await openWatched({ ...B, fov: 0.1, key: KEY }, 'beginner', new AbortController().signal, (l) => lines.push(l), (l) => lines.push(`note: ${l}`))
    expect(lines).toContain(`note: ${AGAIN_LINE}`)
    expect(AGAIN_LINE).toBe('NASA’s archive has new pictures of this patch. Searching it again…')
    expect(out.searchedAgain).toBe(true)
    expect(out.regions?.regions).toHaveLength(1)
    expect(out.watch?.pictures_until).toBe('2027-03-01')
    expect(calls.filter((u) => u.startsWith('/api/search'))).toHaveLength(1)
    expect(calls.filter((u) => u.startsWith('/api/watch?'))).toHaveLength(2)
  })

  it('opening a patch with new_pictures false never asks /api/search', async () => {
    const calls = server({ '/api/watch': () => watchAnswer(), '/api/search': () => done })
    const out = await openWatched({ ...B, fov: 0.1, key: KEY }, 'expert', new AbortController().signal, noop, noop)
    expect(out.searchedAgain).toBe(false)
    expect(out.watch?.searched).toBe(true)
    expect(calls.some((u) => u.startsWith('/api/search'))).toBe(false)
    // A patch nobody has searched is not searched merely because it was opened, either.
    const none = server({ '/api/watch': () => watchAnswer({ searched: false, last_searched: null, pictures_until: null, exposures: null }), '/api/search': () => done })
    await openWatched({ ...B, fov: 0.1, key: KEY }, 'expert', new AbortController().signal, noop, noop)
    expect(none.some((u) => u.startsWith('/api/search'))).toBe(false)
  })

  it('a failing /api/watch leaves an opened patch with no watch lines and no search', async () => {
    const calls = server({ '/api/watch': () => ({ status: 502, body: { detail: 'down' } }), '/api/search': () => done })
    const out = await openWatched({ ...B, fov: 0.1, key: KEY }, 'beginner', new AbortController().signal, noop, noop)
    expect(out.watch).toBeNull()
    expect(calls.some((u) => u.startsWith('/api/search'))).toBe(false)
  })
})
