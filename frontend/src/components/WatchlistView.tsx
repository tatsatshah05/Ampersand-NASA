// The Observe anomalies screen (address: ?watchlist=1, the address of the watchlist it grew out of, so
// old links still work; `&region=` keeps the chosen region, so Back and reload keep it). From the top:
// what an anomaly is, and a line of links down the page; "Pick a patch of sky" (RegionPicker): type a
// name or coordinates to have that patch searched and kept under watch, or choose a patch already
// watched; then, for one patch, its anomalies (the blind patch searches' three groups) directly under
// the picker and the three candidates of the sweep of the Milky Way's plane (CandidateCards, under "Not
// reported anywhere we could find") after them; for everywhere or the plane, the candidates first and
// then the groups and the sweep's own groups (SweepGroups).
//
// The patch searches' cards are the watchlist's: the picture, what the machine saw, what the catalogues
// say, NEOWISE's second opinion, and three vote buttons. Everything is a candidate; a vote is an
// opinion. Their wording is src/search.ts's (reused) and src/watchlist.ts's. The bar of features is at
// the top, as on every screen, with Observe anomalies as the current one, and the level switch in its
// dock at the bottom right.
import { useCallback, useEffect, useRef, useState } from 'react'
import { chooseUiLevel, DEFAULT_SELECTION, readStoredLevel, storeLevel, TOOLS_ADDRESS, withTool, withUi, type UiLevel } from '../address'
import {
  EVERYWHERE,
  fetchSweep,
  FINDS_HEADING,
  FINDS_ID,
  fetchWatch,
  FINDING_PLACE,
  FIRST_SEARCH_NOTE,
  JUMP_LINKS,
  KEEP_LOOKING,
  lastSearchedLine,
  NOTHING_FOUND,
  patchIsQuiet,
  SEARCH_STARTING,
  PATCHES_CHECKED,
  patchesHeading,
  patchRegionParam,
  PLANE,
  readRegion,
  regionOptions,
  SCREEN_TITLE,
  showsPatches,
  showsSweep,
  WHAT_IS_AN_ANOMALY,
  withRegion,
  type SweepData,
  type WatchInfo,
} from '../anomalies'
import { findPatch, openWatched, searchThisPatch, type Patch } from '../watchPatch'
import { newSeed, trainingAddress } from '../training'
import { CandidateCards } from './CandidateCards'
import { FeatureBar, type FeatureLinks } from './FeatureBar'
import { LevelDock } from './LevelDock'
import { RegionPicker } from './RegionPicker'
import { ScienceFold } from './ScienceFold'
import { SweepGroups } from './SweepGroups'
import {
  atFindLine,
  answeredSentence,
  candidateSentence,
  catalogueSentence,
  changeDetail,
  flagSentence,
  headline,
  isCandidate,
  kindLabel,
  oneDetectorSentence,
  rejectedHeadline,
  strengthSentence,
  verdictSentence,
} from '../search'
import {
  ANSWER_LABEL,
  ANSWERS,
  asObject,
  asRejected,
  castVote,
  emptyGroupSentence,
  EXPORT_CSV_URL,
  exampleSentence,
  fetchRegions,
  fetchWatchlist,
  firstGroupWithRows,
  GROUPS,
  INTRO,
  NEOWISE_NOTE,
  neowiseHeadline,
  neowiseSentence,
  NOTE_MAX,
  ORDER_SENTENCE,
  PLAIN_INTRO,
  PLAIN_TABS,
  pictureUrl,
  plainSetAside,
  TABS,
  tallySentence,
  viewerAddress,
  voterId,
  WATCHLIST_ADDRESS,
  type Answer,
  type Group,
  type PatchRegions,
  type WatchRow,
} from '../watchlist'
import './WatchlistView.css'

const PAGE = 10

interface Tab {
  rows: WatchRow[]
  total: number
  loading: boolean
  error: string | null
}
const empty: Tab = { rows: [], total: 0, loading: true, error: null }

/** The counts of the patch searches' groups in a region: everywhere's, a patch's, or null (the plane, or not loaded). */
function regionCounts(key: string, regions: PatchRegions | null): Record<Group, number> | null {
  if (!regions) return null
  if (key === EVERYWHERE) return regions.counts
  return regions.regions.find((r) => r.key === key)?.counts ?? null
}

/** Whether a region key names something on the screen: everywhere, the plane, or a searched patch. */
const knownRegion = (key: string, regions: PatchRegions) => key === EVERYWHERE || key === PLANE || regions.regions.some((r) => r.key === key)

/** Write the chosen region into the address in place, so that Back (from the Viewer) and reload keep it. */
function writeRegion(key: string) {
  try {
    window.history.replaceState(null, '', withRegion(window.location.search, key))
  } catch {
    // Some places (a page opened as a local file) do not allow it; the screen still works.
  }
}

export function WatchlistView() {
  const [voter] = useState(voterId)
  const [group, setGroup] = useState<Group>('eyes')
  const [tabs, setTabs] = useState<Record<Group, Tab>>({ eyes: empty, known: empty, artefact: empty })
  const [counts, setCounts] = useState<Record<Group, number> | null>(null)
  const [patches, setPatches] = useState<number | null>(null)
  // The region chosen (anomalies.ts: EVERYWHERE, PLANE or a searched patch's key), the searched
  // patches with their counts, and the sweep of the plane as exported.
  // The region starts as the address says (Back and reload keep it), and is checked once the list of
  // patches has arrived: a key that names no searched patch falls back to Everywhere.
  const [region, setRegion] = useState<string>(() => readRegion(window.location.search))
  const [regions, setRegions] = useState<PatchRegions | null>(null)
  const [regionsProblem, setRegionsProblem] = useState<string | null>(null)
  const [sweep, setSweep] = useState<SweepData | null>(null)
  const [sweepProblem, setSweepProblem] = useState<string | null>(null)
  const regionParam = patchRegionParam(region)
  const regionNow = useRef(region)
  useEffect(() => {
    regionNow.current = region
  }, [region])
  // The patch being watched (typed, or chosen in the menu), what /api/watch says of it and the lines
  // about its search. Its requests share one controller, stopped when the patch changes or the screen goes.
  const [watch, setWatch] = useState<WatchInfo | null>(null)
  const [progress, setProgress] = useState<string | null>(null)
  const [notes, setNotes] = useState<string[]>([])
  const [watchError, setWatchError] = useState<string | null>(null)
  const [rowsTick, setRowsTick] = useState(0)
  const watchCtrl = useRef<AbortController | null>(null)
  const skipOpen = useRef<string | null>(null)
  const regionsNow = useRef<PatchRegions | null>(null)
  const levelNow = useRef<UiLevel>('beginner')
  useEffect(() => {
    regionsNow.current = regions
  }, [regions])
  const beginWatch = () => {
    watchCtrl.current?.abort()
    const ctrl = new AbortController()
    watchCtrl.current = ctrl
    setWatch(null)
    setProgress(null)
    setNotes([])
    setWatchError(null)
    return ctrl
  }
  useEffect(() => () => watchCtrl.current?.abort(), [])
  // The requests of the region on screen; a new region aborts them, so that a "Show more" still on its
  // way never lands in the next region's list.
  const regionRequests = useRef<AbortController | null>(null)

  const run = useCallback(
    (g: Group, offset: number, signal?: AbortSignal) => {
      fetchWatchlist(g, offset, PAGE, voter, signal, regionParam)
        .then((page) => {
          if (signal?.aborted) return // an answer for a region no longer chosen
          setCounts(page.counts)
          setPatches(page.patches_searched)
          setTabs((t) => ({ ...t, [g]: { rows: offset ? [...t[g].rows, ...page.rows] : page.rows, total: page.total, loading: false, error: null } }))
        })
        .catch((e: unknown) => {
          if (signal?.aborted) return
          setTabs((t) => ({ ...t, [g]: { ...t[g], loading: false, error: e instanceof Error ? e.message : String(e) } }))
        })
    },
    [voter, regionParam],
  )
  const load = (g: Group, offset: number) => {
    setTabs((t) => ({ ...t, [g]: { ...t[g], loading: true, error: null } }))
    run(g, offset, regionRequests.current?.signal)
  }

  useEffect(() => {
    document.title = SCREEN_TITLE
    const ctrl = new AbortController()
    fetchRegions(ctrl.signal)
      .then((r) => {
        setRegions(r)
        // The region the address named: kept if it is one of the list's, and opened on its first group with rows.
        const key = regionNow.current
        if (!knownRegion(key, r)) {
          setRegion(EVERYWHERE)
          writeRegion(EVERYWHERE)
          return
        }
        const counts = regionCounts(key, r)
        const first = firstGroupWithRows(counts)
        if (first) setGroup((g) => (counts && counts[g] > 0 ? g : first))
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        setRegionsProblem(e instanceof Error ? e.message : String(e))
        // Without the list a patch cannot be shown: back to everything.
        if (regionNow.current !== EVERYWHERE && regionNow.current !== PLANE) setRegion(EVERYWHERE)
      })
    fetchSweep(ctrl.signal)
      .then(setSweep)
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setSweepProblem(e instanceof Error ? e.message : String(e))
      })
    return () => ctrl.abort()
  }, [])

  // The patch searches' groups, again whenever the region changes (the plane has none of them). A single
  // patch is asked for only once the list of patches has said it exists.
  const patchesShown = showsPatches(region)
  const canAsk = patchesShown && (region === EVERYWHERE || regions !== null)
  useEffect(() => {
    if (!canAsk) return
    const ctrl = new AbortController()
    regionRequests.current = ctrl
    for (const g of GROUPS) run(g, 0, ctrl.signal)
    return () => ctrl.abort()
  }, [run, canAsk, rowsTick])
  // A new region empties the groups at once, so no group of the last region is shown under the new one's
  // name, and opens on the first of its groups that has rows.
  const selectRegion = (key: string, list: PatchRegions | null) => {
    setRegion(key)
    setCounts(null)
    setTabs({ eyes: empty, known: empty, artefact: empty })
    const first = firstGroupWithRows(regionCounts(key, list))
    if (first) setGroup(first)
    writeRegion(key)
  }
  // A choice in the menu: whatever was going on for the last patch stops, and a patch chosen is opened.
  const chooseRegion = (key: string) => {
    if (key === region) return // the same region again: its lists are already there
    watchCtrl.current?.abort()
    setWatch(null)
    setProgress(null)
    setNotes([])
    setWatchError(null)
    selectRegion(key, regions)
  }

  // A patch chosen in the menu, or named by the address: ask what is known of it (never starting a
  // search), and search it again only if the archive now lists pictures the last search did not have.
  const opened = regions?.regions.some((r) => r.key === region) ? region : null
  useEffect(() => {
    if (!opened) return
    if (skipOpen.current === opened) {
      skipOpen.current = null // a search just made this the chosen patch, and has shown its lines
      return
    }
    const entry = regionsNow.current?.regions.find((r) => r.key === opened)
    if (!entry) return
    const patch: Patch = { ra: entry.ra, dec: entry.dec, fov: entry.fov, key: entry.key }
    const ctrl = beginWatch()
    openWatched(patch, levelNow.current, ctrl.signal, setProgress, (line) => setNotes([line]))
      .then((out) => {
        if (ctrl.signal.aborted) return
        setProgress(null)
        setWatch(out.watch)
        if (out.error) setWatchError(out.error)
        if (out.regions) {
          setRegions(out.regions)
          setRowsTick((t) => t + 1)
        }
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setWatchError(e instanceof Error ? e.message : String(e))
      })
    return () => ctrl.abort()
  }, [opened])

  // "Watch this patch": read the typed place, search that patch (a few minutes the first time), then
  // choose it if it found anything, and say how things stand.
  const watchTyped = async (typed: string) => {
    const ctrl = beginWatch()
    const { signal } = ctrl
    setProgress(FINDING_PLACE)
    try {
      const place = await findPatch(typed, signal)
      if (signal.aborted) return
      if (!place.ok) {
        setProgress(null)
        setWatchError(place.text)
        return
      }
      const patch = place.patch
      const before = await fetchWatch(patch.ra, patch.dec, patch.fov, signal).catch(() => null)
      if (signal.aborted) return
      const searchedBefore = before ? before.searched : (regionsNow.current?.regions.some((r) => r.key === patch.key) ?? false)
      if (!searchedBefore) setNotes([FIRST_SEARCH_NOTE])
      setProgress(SEARCH_STARTING)
      const out = await searchThisPatch(patch, levelNow.current, signal, setProgress)
      if (signal.aborted) return
      setProgress(null)
      if (out.kind === 'failed') {
        setWatchError(out.error)
        return
      }
      setNotes([])
      setWatch(out.watch)
      if (out.regions) setRegions(out.regions)
      setRowsTick((t) => t + 1)
      if (out.chosen) {
        if (out.key !== regionNow.current) {
          skipOpen.current = out.key
          selectRegion(out.key, out.regions)
        }
      } else {
        // No rows for this patch: it stays the one watched, under the list of everything.
        if (regionNow.current !== EVERYWHERE) selectRegion(EVERYWHERE, out.regions)
        if (out.nothing) setNotes([out.nothing])
      }
    } catch (e) {
      if (signal.aborted) return
      setProgress(null)
      setWatchError(e instanceof Error ? e.message : String(e))
    }
  }

  const replaceRow = (g: Group, row: WatchRow) =>
    setTabs((t) => ({ ...t, [g]: { ...t[g], rows: t[g].rows.map((r) => (r.id === row.id ? row : r)) } }))

  // The level is the app's: kept in the address and on this device, and carried by every link.
  const [level, setLevel] = useState<UiLevel>(() => chooseUiLevel(window.location.search, readStoredLevel()))
  useEffect(() => {
    levelNow.current = level
  }, [level])
  const changeLevel = (ui: UiLevel) => {
    storeLevel(ui)
    setLevel(ui)
    try {
      window.history.replaceState(null, '', withUi(window.location.search, ui))
    } catch {
      // Some places (a page opened as a local file) do not allow it; the screen still works.
    }
  }
  // The bar: this list is the current feature; Watch and the tools go back to the viewer.
  const [practiceSeed] = useState(newSeed)
  const links: FeatureLinks = {
    practise: withUi(trainingAddress(DEFAULT_SELECTION, practiceSeed), level),
    vote: withUi(WATCHLIST_ADDRESS, level),
    tools: withUi(TOOLS_ADDRESS, level),
    viewer: (tool) => withTool(withUi('', level), tool),
  }

  const tab = tabs[group]
  const tabWords = level === 'beginner' ? PLAIN_TABS : TABS
  const about = (
    <>
      <p className="intro">{INTRO}</p>
      <p className="intro">{ORDER_SENTENCE}</p>
      <p className="hint">
        {patches !== null && region === EVERYWHERE && `The list covers the ${patches} patches of sky that have been searched so far, and only those. `}
        A search of a new patch takes minutes.
      </p>
      <p>
        <a className="button-link" href={EXPORT_CSV_URL} download>
          For scientists: download the whole list (CSV)
        </a>
      </p>
    </>
  )
  // What is said about the patch being watched, in this order: where its search stands, the notes, then
  // the two lines of what /api/watch knows (left out when it did not answer or the patch was never searched).
  const lastLine = watch ? lastSearchedLine(watch) : null
  // A watched patch where nothing was found is chosen like any other, with no groups to show: it says so here.
  const quiet = patchIsQuiet(region, regions)
  const watchLines = [
    ...new Set([
      ...(progress ? [progress] : []),
      ...notes,
      ...(quiet && !progress ? [NOTHING_FOUND] : []),
      ...(lastLine ? [lastLine] : []),
      ...(watch?.searched ? [KEEP_LOOKING] : []),
    ]),
  ]
  const singlePatch = patchRegionParam(region) !== null
  const candidates = (
    <section className="anomaly-finds" id={FINDS_ID} aria-labelledby="anomaly-finds-title">
      <h2 id="anomaly-finds-title" className="anomaly-finds-title">
        {FINDS_HEADING}
      </h2>
      <CandidateCards level={level} sweep={sweep} />
    </section>
  )
  const patchResults = patchesShown && !quiet && (
    <section className="anomaly-patches" aria-labelledby="anomaly-patches-title">
      <h2 id="anomaly-patches-title" className="anomaly-patches-title">
        {patchesHeading(region, level)}
      </h2>
      {level === 'beginner' ? (
        <>
          <p className="intro anomaly-checks">{PATCHES_CHECKED}</p>
          {PLAIN_INTRO.map((line) => (
            <p key={line} className="intro">
              {line}
            </p>
          ))}
          {/* The machine's own words about the order, the votes and the list, for those who want them. */}
          <ScienceFold>{about}</ScienceFold>
        </>
      ) : (
        about
      )}
      {patchGroups()}
    </section>
  )
  return (
    <>
      <header className="topbar screen-topbar">
        <p className="brand">SPHEREx sky-change viewer</p>
        <FeatureBar level={level} current="vote" links={links} />
      </header>
      <main className="watchlist">
        <header>
          <h1>{SCREEN_TITLE}</h1>
          {WHAT_IS_AN_ANOMALY.map((line) => (
            <p key={line} className="intro anomaly-intro">
              {line}
            </p>
          ))}
          <p className="anomaly-jump">
            Jump to:{' '}
            {JUMP_LINKS.map((l, i) => (
              <span key={l.href}>
                {i > 0 && ' · '}
                <a href={l.href}>{l.label}</a>
              </span>
            ))}
          </p>
        </header>

        <RegionPicker
          level={level}
          value={region}
          options={regionOptions(regions, sweep)}
          patches={regions}
          sweep={sweep}
          problem={regionsProblem}
          onChange={chooseRegion}
          onWatch={watchTyped}
          lines={watchLines}
          error={watchError}
        />

        {singlePatch && patchResults}
        {candidates}
        {!singlePatch && patchResults}

        {showsSweep(region) && <SweepGroups level={level} sweep={sweep} problem={sweepProblem} />}
      </main>
      <LevelDock level={level} onChange={changeLevel} />
    </>
  )

  // The patch searches' three groups, as before: a plain function returning elements (not a component
  // of its own, which would be made anew on every render and lose a note being typed).
  function patchGroups() {
    return (
      <>
        <div className="tabs" role="tablist" aria-label="Groups">
          {GROUPS.map((g) => (
            <button
              key={g}
              type="button"
              role="tab"
              aria-selected={g === group}
              className={g === group ? 'tab on' : 'tab'}
              onClick={() => setGroup(g)}
            >
              {tabWords[g].label} {counts ? `(${counts[g]})` : ''}
            </button>
          ))}
        </div>
        <p className="hint tab-explain">{tabWords[group].explain}</p>

        {tab.error && (
          <p role="alert" className="notice">
            The list could not be loaded: {tab.error}{' '}
            <button type="button" onClick={() => load(group, 0)}>
              Try again
            </button>
          </p>
        )}
        {tab.loading && tab.rows.length === 0 && !tab.error && <p role="status">Loading the list…</p>}
        {!tab.loading && !tab.error && tab.rows.length === 0 && <p className="hint">{emptyGroupSentence(region === EVERYWHERE)}</p>}

        <ol className="cards">
          {tab.rows.map((row) => (
            <Card key={row.id} row={row} voter={voter} level={level} onChange={(r) => replaceRow(group, r)} />
          ))}
        </ol>
        {tab.rows.length < tab.total && (
          <p>
            <button type="button" disabled={tab.loading} onClick={() => load(group, tab.rows.length)}>
              Show more ({tab.total - tab.rows.length} left)
            </button>
          </p>
        )}
      </>
    )
  }
}

function Picture({ row }: { row: WatchRow }) {
  const [failed, setFailed] = useState(false)
  if (failed)
    return (
      <p className="hint no-picture">
        No picture: the SPHEREx images of this patch are not stored on this server. You can still open it in the viewer.
      </p>
    )
  return (
    <div className="strip-wrap">
      <img
        className="strip"
        loading="lazy"
        src={pictureUrl(row.id)}
        alt="The candidate in each visit, side by side, then the last visit minus the first"
        onError={() => setFailed(true)}
      />
    </div>
  )
}

export function Card({ row, voter, level, onChange }: { row: WatchRow; voter: string; level: UiLevel; onChange: (r: WatchRow) => void }) {
  const o = asObject(row)
  const rejected = asRejected(row)
  // At one of the sweep's candidates (within 5 arcsec), whatever the group: that comes first, with the way
  // to its card, and the card is not offered as an example of anything.
  const atFind = row.near_find?.at ? row.near_find : null
  const example = atFind ? null : exampleSentence(row.group)
  const findLine = atFind && (
    <p className="wl-find">
      {atFindLine(atFind)} <a href={`#find-${atFind.key}`}>See its card</a>
    </p>
  )
  const nearFind = row.near_find && !row.near_find.at ? row.near_find : null
  const detail = o && o.evidence.kind === 'changer' ? changeDetail(o.evidence) : null
  const candidate = o && row.group === 'eyes' ? candidateSentence(o) : null
  const single = o && row.group === 'eyes' ? oneDetectorSentence(o) : null
  // The card's words are the watchlist's, unchanged. Beginner reads the headline, the candidate line and
  // the verdict, and finds the machine's numbers (detectors, times the noise, mJy) in one closed fold.
  const place = (
    <p className="hint">
      RA {row.ra.toFixed(5)}°, Dec {row.dec >= 0 ? '+' : '-'}
      {Math.abs(row.dec).toFixed(5)}°
      {row.best_detector ? `, best seen in detector ${row.best_detector}` : ''}. North is up and east is left; the ticks mark the
      candidate.
    </p>
  )
  const strength = o && (
    <>
      <p>{strengthSentence(o)}</p>
      {detail && <p className="hint">{detail}</p>}
      <p>
        <strong>Catalogues.</strong> {catalogueSentence(o)}
      </p>
      <p className="hint">{answeredSentence(o.catalogue_status)}</p>
    </>
  )
  const verdict = o && (
    <p>
      <strong>{o.verdict === 'clean' ? 'Verdict: clean.' : 'Verdict: caution.'}</strong> {verdictSentence(o, true)}
      {nearFind && (
        <>
          {' '}
          <a href={`#find-${nearFind.key}`}>See its card</a>
        </>
      )}
    </p>
  )
  const flags = o && o.flags.length > 0 && (
    <ul className="wl-flags">
      {o.flags.map((f) => (
        <li key={f}>{flagSentence(f)}</li>
      ))}
    </ul>
  )
  const reasons = rejected && (
    <ul className="wl-flags">
      {rejected.reasons.map((reason) => (
        <li key={reason}>{reason}</li>
      ))}
    </ul>
  )
  const neowise = row.neowise && (
    <p className="wl-neowise">
      <strong>Second opinion, NEOWISE.</strong> {row.neowise.state === 'ok' ? neowiseSentence(row.neowise) : neowiseHeadline(row.neowise)}
      {row.neowise.state === 'ok' && <span className="hint"> {NEOWISE_NOTE}</span>}
    </p>
  )
  const kind = (
    <p className="wl-kind">
      <span className="rank">#{row.rank_in_group}</span> {kindLabel(row.kind)}
      {row.verdict && <span className={`wl-badge ${row.verdict}`}>{row.verdict === 'clean' ? 'Clean' : 'Caution'}</span>}
      {o && isCandidate(o) && <span className="wl-badge candidate-tag">Candidate</span>}
      {example && <span className="wl-badge example">Example</span>}
    </p>
  )
  return (
    <li className={`wl-card ${row.group}`}>
      {kind}
      <Picture row={row} />
      {findLine}
      {level === 'expert' ? (
        <>
          {place}
          {example && <p className="hint">{example}</p>}
          {o && (
            <>
              <p className="wl-headline">{headline(o)}</p>
              {strength}
              {candidate && <p className="wl-candidate">{candidate}</p>}
              {single && <p className="wl-candidate">{single}</p>}
              {verdict}
              {flags}
            </>
          )}
          {rejected && (
            <>
              <p className="wl-headline">
                <strong>Set aside.</strong> {rejectedHeadline(rejected)}
              </p>
              {reasons}
            </>
          )}
          {neowise}
        </>
      ) : (
        <>
          {example && <p className="hint">{example}</p>}
          {o && <p className="wl-headline">{headline(o)}</p>}
          {rejected && (
            <p className="wl-headline">
              <strong>Set aside.</strong> {plainSetAside(row.kind)}
            </p>
          )}
          {candidate && <p className="wl-candidate">{candidate}</p>}
          {verdict}
          <ScienceFold>
            {place}
            {strength}
            {single && <p className="wl-candidate">{single}</p>}
            {flags}
            {rejected && <p>{rejectedHeadline(rejected)}</p>}
            {reasons}
            {neowise}
          </ScienceFold>
        </>
      )}

      <Voting row={row} voter={voter} onChange={onChange} />

      <p>
        <a className="button-link" href={withUi(viewerAddress(row), level)}>
          Look at it in the viewer
        </a>
      </p>
    </li>
  )
}

function Voting({ row, voter, onChange }: { row: WatchRow; voter: string; onChange: (r: WatchRow) => void }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  const vote = (answer: Answer) => {
    setBusy(true)
    setProblem(null)
    castVote(row.id, answer, note, voter)
      .then((out) => {
        onChange({ ...row, votes: out.votes, my_vote: out.my_vote })
        setNote('')
      })
      .catch((e: unknown) => setProblem(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false))
  }

  return (
    <div className="wl-vote" role="group" aria-label="Your opinion">
      <p className="hint">
        What do you think the pictures show? Your vote is an opinion, not a confirmation. You can change it.
      </p>
      <div className="vote-buttons">
        {ANSWERS.map((a) => (
          <button key={a} type="button" disabled={busy} aria-pressed={row.my_vote === a} className={row.my_vote === a ? 'on' : ''} onClick={() => vote(a)}>
            {ANSWER_LABEL[a]} ({row.votes[a]})
          </button>
        ))}
      </div>
      <label className="note">
        Optional note ({note.length}/{NOTE_MAX})
        <textarea value={note} maxLength={NOTE_MAX} rows={2} onChange={(e) => setNote(e.target.value)} placeholder="What did you see? Plain text only." />
      </label>
      <p className="hint">{row.my_vote ? `You voted: ${ANSWER_LABEL[row.my_vote].toLowerCase()}. ` : ''}{tallySentence(row.votes)}</p>
      {problem && (
        <p role="alert" className="notice">
          {problem}
        </p>
      )}
      {row.notes.length > 0 && (
        <details>
          <summary>Notes from volunteers ({row.notes.length})</summary>
          <ul>
            {row.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
