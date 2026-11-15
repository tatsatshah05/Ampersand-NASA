// The watchlist screen (address: ?watchlist=1): what the blind searches found, for people to look at.
// Each card: the picture, what the machine saw, what the catalogues say, NEOWISE's second opinion,
// and three vote buttons. Everything is a candidate; a vote is an opinion. The wording is
// src/search.ts's (reused) and src/watchlist.ts's. The bar of features is at the top, as on
// every screen, with Vote as the current one, and the level switch in its dock at the bottom right.
import { useCallback, useEffect, useState } from 'react'
import { chooseUiLevel, DEFAULT_SELECTION, readStoredLevel, storeLevel, TOOLS_ADDRESS, withTool, withUi, type UiLevel } from '../address'
import { newSeed, trainingAddress } from '../training'
import { FeatureBar, type FeatureLinks } from './FeatureBar'
import { LevelDock } from './LevelDock'
import {
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
  EXPORT_CSV_URL,
  exampleSentence,
  fetchWatchlist,
  GROUPS,
  INTRO,
  NEOWISE_NOTE,
  neowiseHeadline,
  neowiseSentence,
  NOTE_MAX,
  ORDER_SENTENCE,
  pictureUrl,
  TABS,
  tallySentence,
  viewerAddress,
  voterId,
  WATCHLIST_ADDRESS,
  type Answer,
  type Group,
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

export function WatchlistView() {
  const [voter] = useState(voterId)
  const [group, setGroup] = useState<Group>('eyes')
  const [tabs, setTabs] = useState<Record<Group, Tab>>({ eyes: empty, known: empty, artefact: empty })
  const [counts, setCounts] = useState<Record<Group, number> | null>(null)
  const [patches, setPatches] = useState<number | null>(null)

  const run = useCallback(
    (g: Group, offset: number, signal?: AbortSignal) => {
      fetchWatchlist(g, offset, PAGE, voter, signal)
        .then((page) => {
          setCounts(page.counts)
          setPatches(page.patches_searched)
          setTabs((t) => ({ ...t, [g]: { rows: offset ? [...t[g].rows, ...page.rows] : page.rows, total: page.total, loading: false, error: null } }))
        })
        .catch((e: unknown) => {
          if (signal?.aborted) return
          setTabs((t) => ({ ...t, [g]: { ...t[g], loading: false, error: e instanceof Error ? e.message : String(e) } }))
        })
    },
    [voter],
  )
  const load = (g: Group, offset: number) => {
    setTabs((t) => ({ ...t, [g]: { ...t[g], loading: true, error: null } }))
    run(g, offset)
  }

  useEffect(() => {
    document.title = 'Vote on what the search found'
    const ctrl = new AbortController()
    for (const g of GROUPS) run(g, 0, ctrl.signal)
    return () => ctrl.abort()
  }, [run])

  const replaceRow = (g: Group, row: WatchRow) =>
    setTabs((t) => ({ ...t, [g]: { ...t[g], rows: t[g].rows.map((r) => (r.id === row.id ? row : r)) } }))

  // The level is the app's: kept in the address and on this device, and carried by every link.
  const [level, setLevel] = useState<UiLevel>(() => chooseUiLevel(window.location.search, readStoredLevel()))
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
  return (
    <>
      <header className="topbar screen-topbar">
        <p className="brand">SPHEREx sky-change viewer</p>
        <FeatureBar level={level} current="vote" links={links} />
      </header>
      <main className="watchlist">
        <header>
          <h1>Vote on what the search found</h1>
          <p className="intro">{INTRO}</p>
          <p className="intro">{ORDER_SENTENCE}</p>
          <p className="hint">
            {patches !== null && `The list covers the ${patches} patches of sky that have been searched so far, and only those. `}
            A search of a new patch takes minutes.
          </p>
          <p>
            <a className="button-link" href={EXPORT_CSV_URL} download>
              For scientists: download the whole list (CSV)
            </a>
          </p>
        </header>

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
              {TABS[g].label} {counts ? `(${counts[g]})` : ''}
            </button>
          ))}
        </div>
        <p className="hint tab-explain">{TABS[group].explain}</p>

        {tab.error && (
          <p role="alert" className="notice">
            The list could not be loaded: {tab.error}{' '}
            <button type="button" onClick={() => load(group, 0)}>
              Try again
            </button>
          </p>
        )}
        {tab.loading && tab.rows.length === 0 && !tab.error && <p role="status">Loading the list…</p>}
        {!tab.loading && !tab.error && tab.rows.length === 0 && (
          <p className="hint">Nothing is in this group yet: the list holds only what real searches have reported.</p>
        )}

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
      </main>
      <LevelDock level={level} onChange={changeLevel} />
    </>
  )
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

function Card({ row, voter, level, onChange }: { row: WatchRow; voter: string; level: UiLevel; onChange: (r: WatchRow) => void }) {
  const o = asObject(row)
  const rejected = asRejected(row)
  const example = exampleSentence(row.group)
  const detail = o && o.evidence.kind === 'changer' ? changeDetail(o.evidence) : null
  const candidate = o && row.group === 'eyes' ? candidateSentence(o) : null
  const single = o && row.group === 'eyes' ? oneDetectorSentence(o) : null
  return (
    <li className={`wl-card ${row.group}`}>
      <p className="wl-kind">
        <span className="rank">#{row.rank_in_group}</span> {kindLabel(row.kind)}
        {row.verdict && <span className={`wl-badge ${row.verdict}`}>{row.verdict === 'clean' ? 'Clean' : 'Caution'}</span>}
        {o && isCandidate(o) && <span className="wl-badge candidate-tag">Candidate</span>}
        {example && <span className="wl-badge example">Example</span>}
      </p>
      <Picture row={row} />
      <p className="hint">
        RA {row.ra.toFixed(5)}°, Dec {row.dec >= 0 ? '+' : '-'}
        {Math.abs(row.dec).toFixed(5)}°
        {row.best_detector ? `, best seen in detector ${row.best_detector}` : ''}. North is up and east is left; the ticks mark the
        candidate.
      </p>
      {example && <p className="hint">{example}</p>}

      {o && (
        <>
          <p className="wl-headline">{headline(o)}</p>
          <p>{strengthSentence(o)}</p>
          {detail && <p className="hint">{detail}</p>}
          <p>
            <strong>Catalogues.</strong> {catalogueSentence(o)}
          </p>
          <p className="hint">{answeredSentence(o.catalogue_status)}</p>
          {candidate && <p className="wl-candidate">{candidate}</p>}
          {single && <p className="wl-candidate">{single}</p>}
          <p>
            <strong>{o.verdict === 'clean' ? 'Verdict: clean.' : 'Verdict: caution.'}</strong> {verdictSentence(o)}
          </p>
          {o.flags.length > 0 && (
            <ul className="wl-flags">
              {o.flags.map((f) => (
                <li key={f}>{flagSentence(f)}</li>
              ))}
            </ul>
          )}
        </>
      )}
      {rejected && (
        <>
          <p className="wl-headline">
            <strong>Set aside.</strong> {rejectedHeadline(rejected)}
          </p>
          <ul className="wl-flags">
            {rejected.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </>
      )}

      {row.neowise && (
        <p className="wl-neowise">
          <strong>Second opinion, NEOWISE.</strong> {row.neowise.state === 'ok' ? neowiseSentence(row.neowise) : neowiseHeadline(row.neowise)}
          {row.neowise.state === 'ok' && <span className="hint"> {NEOWISE_NOTE}</span>}
        </p>
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
