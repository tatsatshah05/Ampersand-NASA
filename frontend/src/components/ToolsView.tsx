// "Three tools, three known worlds" (?tools=1): the three SPHEREx methods, each shown on a world
// astronomers already know, for readers who are not scientists. A separate screen: none of the
// viewer is mounted. Build spec: revision 3 (scratchpad lab/spec.md), sections 2 to 10, with the
// reviews of the built screen applied (truth; behaviour and accessibility; two newcomers).
//
// Every number comes from /lab/{reflex,colourwalk,transits}.json through tools.ts, and every
// visible string from toolsWording.ts. Nothing moves unless the visitor asks: the only timed
// sequence is "Walk through the colours", which runs once, on request.
import { createContext, useContext, useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import {
  binFolded,
  fold,
  reflexView,
  colourView,
  transitView,
  toolsBackAddress,
  trapezoidDepth,
  useLab,
  type ColourFile,
  type ColourView,
  type Glance,
  type LabName,
  type Load,
  type ReflexFile,
  type ReflexView,
  type StopView,
  type TransitFile,
  type TransitView,
} from '../tools'
import { PAGE, T1, T2, T3 } from '../toolsWording'
import { chooseUiLevel, readAddress, readStoredLevel, storeLevel, TOOLS_ADDRESS, withTool, withUi, type UiLevel } from '../address'
import { newSeed, trainingAddress } from '../training'
import { WATCHLIST_ADDRESS } from '../watchlist'
import { FeatureBar, type FeatureLinks } from './FeatureBar'
import { LevelDock } from './LevelDock'
import './ToolsView.css'

const TOOL_IDS = [T1.id, T2.id, T3.id]

// ---------------------------------------------------------------------------------- the screen

export function ToolsView() {
  const search = typeof window === 'undefined' ? '' : window.location.search
  const [attempts, setAttempts] = useState<Record<LabName, number>>({ reflex: 0, colourwalk: 0, transits: 0 })
  const reflex = useLab<ReflexFile>('reflex', attempts.reflex)
  const colourwalk = useLab<ColourFile>('colourwalk', attempts.colourwalk)
  const transits = useLab<TransitFile>('transits', attempts.transits)
  useEffect(() => {
    document.title = PAGE.title
  }, [])
  // A shared link to a tool (#line-up-the-dips) lands on it: the browser's own jump runs before the
  // page exists, so it is done here, once on arrival and again once the three files have settled
  // (the page above the tool grows as they load).
  const settled = [reflex, colourwalk, transits].every((l) => l.state !== 'loading')
  const landed = useRef(false)
  useEffect(() => {
    if (landed.current) return
    const id = decodeURIComponent(window.location.hash.slice(1))
    if (!TOOL_IDS.includes(id)) {
      landed.current = true
      return
    }
    goToTool(id, 'auto')
    if (settled) landed.current = true
  }, [settled])
  const retry = (name: LabName) => setAttempts((a) => ({ ...a, [name]: a[name] + 1 }))

  // The level is the app's: kept in the address and on this device, and carried by every link.
  // This screen has one wording; the level changes the bar's words, is passed on, and opens the
  // "For scientists" fold-outs in Expert (closed in Beginner).
  const [level, setLevel] = useState<UiLevel>(() => chooseUiLevel(search, readStoredLevel()))
  const changeLevel = (ui: UiLevel) => {
    storeLevel(ui)
    setLevel(ui)
    try {
      window.history.replaceState(null, '', `${withUi(window.location.search, ui)}${window.location.hash}`)
    } catch {
      // Some places (a page opened as a local file) do not allow it; the screen still works.
    }
  }
  // Back to the sky viewer: the place the visitor came from, in the level in use.
  const backTo = toolsBackAddress(search)
  const back = withUi(backTo === '/' ? '' : backTo, level)
  const [practiceSeed] = useState(newSeed)
  const links: FeatureLinks = {
    practise: withUi(trainingAddress(readAddress(backTo === '/' ? '' : backTo).selection, practiceSeed), level),
    vote: withUi(WATCHLIST_ADDRESS, level),
    tools: withUi(search || TOOLS_ADDRESS, level),
    viewer: (tool) => withTool(back, tool),
  }
  return (
    <>
      <header className="topbar screen-topbar">
        <p className="brand">SPHEREx sky-change viewer</p>
        <FeatureBar level={level} current="tools" links={links} />
      </header>
      <ToolsPage reflex={reflex} colourwalk={colourwalk} transits={transits} back={back} onRetry={retry} level={level} />
      <LevelDock level={level} onChange={changeLevel} />
    </>
  )
}

/** Scroll a tool into view with its "Tool n of 3" line and verdict showing, and focus its heading. */
function goToTool(id: string, behavior: ScrollBehavior = 'auto') {
  const h = document.getElementById(id)
  if (!h) return
  ;(h.closest('section') ?? h).scrollIntoView({ block: 'start', behavior })
  h.focus({ preventScroll: true })
}

interface PageProps {
  reflex: Load<ReflexFile>
  colourwalk: Load<ColourFile>
  transits: Load<TransitFile>
  back: string
  onRetry: (name: LabName) => void
  /** The app's level: in Expert the "For scientists" fold-outs are open when the screen loads. Beginner when left out. */
  level?: UiLevel
}

/** The level in use, for the "For scientists" fold-outs deep inside each tool. */
const LevelOfPage = createContext<UiLevel>('beginner')

/** The whole page from three loads: separate from the fetching so that it renders in tests. */
export function ToolsPage({ level = 'beginner', ...page }: PageProps) {
  return (
    <LevelOfPage.Provider value={level}>
      <Page {...page} />
    </LevelOfPage.Provider>
  )
}

function Page({ reflex, colourwalk, transits, back, onRetry }: Omit<PageProps, 'level'>) {
  const rv = reflex.state === 'ready' ? reflexView(reflex.data) : null
  const cv = colourwalk.state === 'ready' ? colourView(colourwalk.data) : null
  const tv = transits.state === 'ready' ? transitView(transits.data) : null
  const notFinal = [rv, cv, tv].some((v) => v !== null && !v.final)
  return (
    <main className="tools" lang="en-GB">
      <div className="tools-top">
        <a className="quiet tools-back" href={back}>
          {PAGE.back}
        </a>
      </div>
      <header className="tools-header">
        <h1>{PAGE.title}</h1>
        <Paras lines={[PAGE.welcome]} />
        <div className="panel tools-boxed">
          <Paras lines={[PAGE.boxed]} />
        </div>
        <p className="tools-small tools-smallprint">{PAGE.smallPrint.join(' ')}</p>
        {notFinal && <p className="tools-small tools-notfinal">{PAGE.notFinal}</p>}
        <Key />
        <nav aria-label={PAGE.jumpLabel}>
          <ul className="tools-jump">
            {TOOL_IDS.map((id, i) => (
              <li key={id}>
                <JumpLink to={id} className="tools-jump-link">
                  {PAGE.jump[i]}
                </JumpLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <ToolOne load={reflex} view={rv} onRetry={() => onRetry('reflex')} />
      <ToolTwo load={colourwalk} view={cv} onRetry={() => onRetry('colourwalk')} />
      <ToolThree load={transits} view={tv} onRetry={() => onRetry('transits')} />
      <footer className="tools-footer">
        {PAGE.footer.map((s) => (
          <p key={s}>{s}</p>
        ))}
        <a className="quiet tools-back" href={back}>
          {PAGE.back}
        </a>
      </footer>
    </main>
  )
}

/** A link to a tool: moves focus to its heading, which has tabindex -1. */
function JumpLink({ to, className, children }: { to: string; className: string; children: ReactNode }) {
  return (
    <a
      className={className}
      href={`#${to}`}
      onClick={(e) => {
        if (!document.getElementById(to)) return
        e.preventDefault()
        goToTool(to)
        history.replaceState(history.state, '', `${window.location.search}#${to}`)
      }}
    >
      {children}
    </a>
  )
}

function Key() {
  return (
    <section className="tools-key" aria-label={PAGE.keyHeading}>
      <p>
        <Mark kind="measured" /> {PAGE.key.measured}
      </p>
      <p>
        <Mark kind="known" /> {PAGE.key.known}
      </p>
      <p>
        <Mark kind="button" /> {PAGE.key.button}
      </p>
      <p>
        <span className="key-sketch" aria-hidden="true" /> {PAGE.key.sketch}
      </p>
    </section>
  )
}

type MarkKind = 'measured' | 'known' | 'band' | 'grey' | 'greydot' | 'greyband' | 'line' | 'dashed' | 'mline' | 'rule' | 'ring' | 'button'

/** The small marks beside numbers and in keys: an amber dot (measured) or a cyan cross (known), and the rest. */
function Mark({ kind }: { kind: MarkKind }) {
  const w = kind === 'button' ? 20 : 12
  return (
    <svg className={`tl-mark tl-mark-${kind}`} width={w} height="12" viewBox={`0 0 ${w} 12`} aria-hidden="true" focusable="false">
      {kind === 'measured' && <circle cx="6" cy="6" r="4.5" />}
      {kind === 'known' && <path d="M2 2 L10 10 M10 2 L2 10" />}
      {kind === 'band' && <rect x="0" y="3" width="12" height="6" />}
      {kind === 'grey' && <path d="M2 6 H10 M6 2 V10" />}
      {kind === 'greydot' && <circle cx="6" cy="6" r="2" />}
      {kind === 'greyband' && <rect x="0" y="2" width="12" height="8" />}
      {kind === 'line' && <path d="M1 6 H11" />}
      {kind === 'dashed' && <path d="M0 6 H4 M7 6 H11" />}
      {kind === 'mline' && <path d="M1 6 H11" />}
      {kind === 'rule' && <circle cx="6" cy="6" r="4.5" />}
      {kind === 'ring' && <circle cx="6" cy="6" r="4.5" />}
      {kind === 'button' && (
        <>
          <rect x="0.5" y="0.5" width="19" height="11" rx="3" />
          <path d="M6 6 H13 M10.5 3.5 L13 6 L10.5 8.5" />
        </>
      )}
    </svg>
  )
}

/** The arrow that marks the main thing to try (a chosen option and a pressed toggle are filled too). */
const MainArrow = () => (
  <svg className="main-arrow" width="14" height="12" viewBox="0 0 14 12" aria-hidden="true" focusable="false">
    <path d="M1 6 H11 M7 2 L11 6 L7 10" />
  </svg>
)

/** Keeps names such as "WASP-62 b" whole on a phone. */
function Words({ text }: { text: string }) {
  const parts = text.split(/(WASP-\d+ b|VHS 1256(?:-1257 b)?)/)
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <span className="nowrap" key={i}>
            {p}
          </span>
        ) : (
          p
        ),
      )}
    </>
  )
}

type Line = string | null | undefined
/** Paragraphs: a string is one paragraph; an array is one paragraph of sentences that run on. */
const Paras = ({ lines, className }: { lines: (Line | Line[])[]; className?: string }) => (
  <>
    {lines
      .map((l) => (Array.isArray(l) ? l.filter((s): s is string => typeof s === 'string' && s.length > 0).join(' ') : l))
      .filter((s): s is string => typeof s === 'string' && s.length > 0)
      .map((s, i) => (
        <p key={`${i}-${s.slice(0, 40)}`} className={className}>
          <Words text={s} />
        </p>
      ))}
  </>
)

/** Words for the live region: each part a sentence, none said twice, one space between. */
function spoken(parts: Line[]): string {
  const out: string[] = []
  for (const p of parts) {
    if (!p) continue
    const s = /[.!?…:]$/.test(p) ? p : `${p}.`
    if (out.some((o) => o.startsWith(p) || s.startsWith(o.replace(/\.$/, '')))) {
      const i = out.findIndex((o) => s.startsWith(o.replace(/\.$/, '')))
      if (i >= 0) out[i] = s
      continue
    }
    out.push(s)
  }
  return out.join(' ')
}

/** The tool's verdict at once, under its name, with the number that matters (newcomer review). */
function Verdict({ chip, notice, glance, knownMark = 'known' }: { chip: string | null; notice?: boolean; glance: Glance | null; knownMark?: MarkKind }) {
  if (!chip) return null
  return (
    <div className={`tl-verdict${notice ? ' tl-verdict-notice' : ''}`}>
      <p className="tl-verdict-words">{chip}</p>
      {glance && (
        <p className="tl-verdict-numbers">
          <span className="tl-verdict-item">
            <Mark kind="measured" /> {glance.ours}
          </span>
          {glance.known && (
            <span className="tl-verdict-item">
              <Mark kind={knownMark} /> {glance.known}
            </span>
          )}
          {glance.unit && <span className="tl-verdict-unit">{glance.unit}</span>}
        </p>
      )}
    </div>
  )
}

function ToolHeader({ n, id, name, children, fixture, one }: { n: string; id: string; name: string; children?: ReactNode; fixture: boolean; one: string[] }) {
  return (
    <>
      <p className="tool-meta">
        <span className="tool-of">{PAGE.toolOf(n)}</span>
      </p>
      <h2 id={id} tabIndex={-1}>
        {name}
      </h2>
      {children}
      {fixture && <p className="notice tools-fixture">{PAGE.fixture}</p>}
      <Paras lines={[one]} />
    </>
  )
}

/** The one place a tool says its file is loading or could not be loaded. */
function DataState({ load, onRetry, boxes = 1 }: { load: Load<unknown>; onRetry: () => void; boxes?: number }) {
  if (load.state === 'loading')
    return (
      <div className="tools-loading">
        <p className="hint">{PAGE.loading}</p>
        <LoadingBoxes n={boxes} />
      </div>
    )
  if (load.state === 'missing')
    return (
      <p className="tools-missing">
        {PAGE.fileMissing}{' '}
        <button type="button" onClick={onRetry}>
          {PAGE.tryAgain}
        </button>
      </p>
    )
  return null
}

const LoadingBoxes = ({ n }: { n: number }) => (
  <>
    {Array.from({ length: n }, (_, i) => (
      <div key={i} className="picture-box loading-box" aria-hidden="true" />
    ))}
  </>
)

function Fold({ summary, children, className, defaultOpen = false }: { summary: string; children: ReactNode; className?: string; defaultOpen?: boolean }) {
  // Open or closed as the visitor leaves it; `defaultOpen` is only how it starts.
  const [open, setOpen] = useState(defaultOpen)
  return (
    <details className={`tl-fold${className ? ` ${className}` : ''}`} open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>{summary}</summary>
      <div className="tl-fold-body">{children}</div>
    </details>
  )
}

function Answers({ intro, something, nothing, cannot, extra }: { intro?: string; something: string; nothing: string | null; cannot: string | null; extra?: Line[] }) {
  return (
    <Fold summary={PAGE.foldAnswers} className="answers">
      {intro && <p>{intro}</p>}
      <p>
        <strong>{PAGE.foundSomething}</strong> {something}
      </p>
      {nothing && (
        <p>
          <strong>{PAGE.foundNothing}</strong> {nothing}
        </p>
      )}
      {cannot && (
        <p>
          <strong>{PAGE.cannotTell}</strong> {cannot}
        </p>
      )}
      {extra && <Paras lines={[extra]} />}
    </Fold>
  )
}

function Scientists({ paragraphs }: { paragraphs: string[] }) {
  const level = useContext(LevelOfPage)
  if (paragraphs.length === 0) return null
  // Open in Expert, closed in Beginner; a switch of level starts it again in the new level's way.
  return (
    <Fold key={level} summary={PAGE.foldScientists} className="scientists" defaultOpen={level === 'expert'}>
      {paragraphs.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </Fold>
  )
}

function HowSure({ paras }: { paras: string[][] }) {
  if (paras.length === 0) return null
  return (
    <Fold summary={PAGE.foldHowSure}>
      <Paras lines={paras} />
    </Fold>
  )
}

/** A figure's number with its key mark, and its range sentences lined up under the words. */
function Figure({ kind, text, under }: { kind: 'measured' | 'known'; text: string; under?: Line[] }) {
  return (
    <div>
      <p className="figure">
        <Mark kind={kind} /> {text}
      </p>
      {under?.filter(Boolean).map((s) => (
        <p className="figure-range" key={s as string}>
          {s}
        </p>
      ))}
    </div>
  )
}

function Sketch({ label, alt, children, className }: { label: string; alt: string; children: ReactNode; className?: string }) {
  return (
    <figure className={`sketch${className ? ` ${className}` : ''}`} role="img" aria-label={alt}>
      <figcaption className="sketch-label">{label}</figcaption>
      <div className="sketch-body" aria-hidden="true">
        {children}
      </div>
    </figure>
  )
}

/** A real SPHEREx picture: square, pixelated, north up and east left, with marks drawn over it. */
export interface MarkLabel {
  x: number
  y: number
  text: string
  kind: 'measured' | 'known'
  /** Where the words sit from the mark: to its right, to its left, or below it. */
  side: 'right' | 'left' | 'below'
}

function Picture({
  picture,
  alt,
  crop,
  marks,
  labels,
  squareBar = false,
  className,
}: {
  picture: { src: string } | { why: string }
  alt: string
  crop: number | null
  marks?: ReactNode
  labels?: MarkLabel[]
  squareBar?: boolean
  className?: string
}) {
  const [failed, setFailed] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  if ('why' in picture)
    return (
      <div className={`picture-box picture-missing${className ? ` ${className}` : ''}`}>
        <p>{PAGE.pictureNotReady}</p>
      </div>
    )
  const src = attempt > 0 ? `${picture.src}?try=${attempt}` : picture.src
  if (failed === src)
    return (
      <div className={`picture-box picture-missing${className ? ` ${className}` : ''}`}>
        <p>
          {PAGE.pictureMissing}{' '}
          <button type="button" onClick={() => setAttempt((a) => a + 1)}>
            {PAGE.tryAgain}
          </button>
        </p>
      </div>
    )
  const bar = squareBar && crop ? { x0: 0.6, x1: 1.6, y: crop - 0.7 } : null
  return (
    <div className={`picture-box picture${className ? ` ${className}` : ''}`}>
      <img src={src} alt={alt} onError={() => setFailed(src)} />
      {crop && (marks || bar) && (
        <svg className="picture-marks" viewBox={`0 0 ${crop} ${crop}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
          {marks}
          {bar && (
            <>
              <path className="mk-bar-halo" d={`M${bar.x0} ${bar.y} H${bar.x1}`} vectorEffect="non-scaling-stroke" />
              <path className="mk-bar" d={`M${bar.x0} ${bar.y} H${bar.x1}`} vectorEffect="non-scaling-stroke" />
            </>
          )}
        </svg>
      )}
      {crop &&
        labels?.map((l) => (
          <span key={l.text} className={`tl-mark-label tl-mark-label-${l.kind} side-${l.side}`} style={{ left: `${(l.x / crop) * 100}%`, top: `${(l.y / crop) * 100}%` }} aria-hidden="true">
            {l.text}
          </span>
        ))}
      {bar && crop && (
        <span className="tl-square-label" style={{ left: `${((bar.x1 + 0.3) / crop) * 100}%`, top: `${(bar.y / crop) * 100}%` }} aria-hidden="true">
          {PAGE.squareBar}
        </span>
      )}
      <span className="tl-compass" aria-hidden="true">
        <span className="tl-compass-n">{PAGE.compassNorth} ↑</span>
        <span className="tl-compass-e">← {PAGE.compassEast}</span>
      </span>
    </div>
  )
}

/** A native range with stops as tick marks, the value written above it, and labels under it. */
function Stops({
  id,
  label,
  value,
  count,
  onChange,
  valueText,
  spoken: spokenText,
  under,
  ends,
  knownTick,
  knownLabel,
}: {
  id: string
  label: string
  value: number
  count: number
  onChange: (i: number) => void
  valueText: string
  spoken: string
  under?: string[]
  ends?: [string, string]
  knownTick?: number | null
  knownLabel?: string
}) {
  const pos = (i: number) => `calc(11px + (100% - 22px) * ${count > 1 ? i / (count - 1) : 0})`
  return (
    <div className="stops">
      <label htmlFor={id} className="stops-label">
        {label}
      </label>
      <p className="stops-value" aria-hidden="true">
        {valueText}
      </p>
      <div className="stops-track">
        {knownTick !== null && knownTick !== undefined && knownLabel && (
          <span className="known-tick" style={{ left: pos(knownTick) }} aria-hidden="true">
            <span className="known-tick-label">{knownLabel}</span>
            <svg className="known-tick-cross" width="12" height="12" viewBox="0 0 12 12" focusable="false">
              <path d="M2 2 L10 10 M10 2 L2 10" />
            </svg>
          </span>
        )}
        <input id={id} type="range" min={0} max={count - 1} step={1} value={value} aria-valuetext={spokenText} onChange={(e) => onChange(Number(e.target.value))} />
        <span className="tl-ticks" aria-hidden="true">
          {Array.from({ length: count }, (_, i) => (
            <span key={i} className="tl-tick" style={{ left: pos(i) }} />
          ))}
        </span>
      </div>
      {under && (
        <div className="stops-under" aria-hidden="true">
          {under.map((u, i) => (
            <span key={u} style={{ left: pos(i) }} className={i === 0 ? 'first' : i === under.length - 1 ? 'last' : ''}>
              {u}
            </span>
          ))}
        </div>
      )}
      {ends && (
        <div className="stops-ends" aria-hidden="true">
          <span>{ends[0]}</span>
          <span>{ends[1]}</span>
        </div>
      )}
    </div>
  )
}

/** The width of a box, for charts that draw in screen pixels (358 before the page is measured). */
function useWidth(fallback = 358): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null)
  const [w, setW] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setW(Math.max(260, Math.round(el.clientWidth))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

/** A try-it: shown while its file loads (a quiet box) and once it is ready; absent if the file is missing. */
function TryIt({ load, heading, children }: { load: Load<unknown>; heading: string; children: ReactNode }) {
  if (load.state === 'missing') return null
  return (
    <>
      <h3>{heading}</h3>
      {load.state === 'loading' ? <LoadingBoxes n={1} /> : children}
    </>
  )
}

// ---------------------------------------------------------------------------------- tool 1

function ToolOne({ load, view, onRetry }: { load: Load<ReflexFile>; view: ReflexView | null; onRetry: () => void }) {
  const [announce, setAnnounce] = useState('')
  return (
    <section className="tool" aria-labelledby={T1.id}>
      <ToolHeader n="1" id={T1.id} name={T1.name} fixture={view?.fixture ?? false} one={T1.one}>
        <Verdict chip={view?.chip ?? null} glance={view?.glance ?? null} />
      </ToolHeader>
      <h3>{T1.likeThis}</h3>
      <Paras lines={T1.likeThisText} />
      <SketchFinger />

      <h3>{T1.testHeading}</h3>
      {view ? (
        <>
          {view.headline && (
            <p className="result-line">
              <Words text={view.headline} />
            </p>
          )}
          <Paras lines={view.test} />
          {view.numbers && (
            <div className="numbers-row">
              <Figure kind="measured" text={view.numbers.ours} under={[...view.numbers.range, PAGE.explain19]} />
              {view.numbers.nasa && <Figure kind="known" text={view.numbers.nasa} />}
            </div>
          )}
          {view.ruler && <Ruler ruler={view.ruler} />}
          <Paras lines={view.after} />
          <HowSure paras={view.howSure} />
        </>
      ) : (
        <>
          <Paras lines={[T1.eris]} />
          <DataState load={load} onRetry={onRetry} boxes={0} />
        </>
      )}

      <TryIt load={load} heading={T1.appear.heading}>
        {view && <Appear view={view} say={setAnnounce} />}
      </TryIt>

      <TryIt load={load} heading={T1.distance.heading}>
        {view?.distance ? (
          <>
            <Paras lines={[T1.distance.intro]} />
            <Distance d={view.distance} say={setAnnounce} />
          </>
        ) : (
          <p className="hint">{PAGE.partMissing}</p>
        )}
      </TryIt>

      {view && (
        <>
          {view.answerLine && <p className="answer-line">{view.answerLine}</p>}
          <Answers something={view.answers.something} nothing={view.answers.nothing} cannot={view.answers.cannot} extra={[view.answers.near, view.answers.far, view.answers.fainter]} />
        </>
      )}

      <h3>{T1.notMean.heading}</h3>
      <Paras lines={[...T1.notMean.text.slice(0, -1), [...T1.notMean.text[T1.notMean.text.length - 1], view?.sedna ? T1.notMean.sedna : null]]} />
      {view && <Scientists paragraphs={view.sci} />}
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
      <JumpLink to={T2.id} className="quiet next-link">
        {T1.next}
      </JumpLink>
    </section>
  )
}

function Ruler({ ruler }: { ruler: NonNullable<ReflexView['ruler']> }) {
  const at = (x: number) => `${Math.min(100, Math.max(0, (x / ruler.max) * 100))}%`
  const ticks = Array.from({ length: Math.floor(ruler.max / 20) + 1 }, (_, i) => i * 20)
  const hi = ruler.range.hi ?? ruler.max
  const open = ruler.range.hi === null
  return (
    <figure className="chart ruler" role="img" aria-label={ruler.summary ?? T1.rulerTitle}>
      <figcaption>
        <p className="chart-title">{T1.rulerTitle}</p>
      </figcaption>
      <div className="ruler-body" aria-hidden="true">
        <span className="ruler-name" style={{ left: at(1) }}>
          {T1.rulerEarth}
        </span>
        <span className="ruler-name" style={{ left: at(30) }}>
          {T1.rulerNeptune}
        </span>
        <span className="ruler-band-label" style={{ left: at(ruler.range.lo) }}>
          {T1.rulerBand}
          {open ? ' →' : ''}
        </span>
        <span className="ruler-line" />
        <span className="ruler-planet" style={{ left: at(1) }} />
        <span className="ruler-planet" style={{ left: at(30) }} />
        <span className={`ruler-band${open ? ' open' : ''}`} style={{ left: at(ruler.range.lo), width: `calc(${at(hi)} - ${at(ruler.range.lo)})` }} />
        <span className="ruler-dot" style={{ left: at(ruler.best) }} />
        {ruler.r !== null && (
          <svg className="ruler-cross" style={{ left: at(ruler.r) }} width="14" height="14" viewBox="0 0 14 14">
            <path d="M2 2 L12 12 M12 2 L2 12" />
          </svg>
        )}
        {ticks.map((t) => (
          <span key={t} className="ruler-tick" style={{ left: at(t) }}>
            {t}
          </span>
        ))}
      </div>
      <div className="chart-key ruler-key" aria-hidden="true">
        <p>
          <Mark kind="measured" /> {T1.rulerOurs}
        </p>
        <p>
          <Mark kind="band" /> {T1.rulerBand}
          {open ? ` (${T1.rulerOpen})` : ''}
        </p>
        {ruler.r !== null && (
          <p>
            <Mark kind="known" /> {T1.rulerNasa}
          </p>
        )}
      </div>
      <p className="caption">{T1.rulerCaption}</p>
    </figure>
  )
}

function Appear({ view, say }: { view: ReflexView; say: (s: string) => void }) {
  const [opt, setOpt] = useState(0)
  const [nasa, setNasa] = useState(false)
  const a = view.appear
  const nasaWords = (i: number, on: boolean) => (on ? (i < 2 ? T1.appear.nasaCaption : T1.appear.nasaAfter) : null)
  const choose = (i: number) => {
    setOpt(i)
    say(spoken([a.captions[i], nasaWords(i, nasa)]))
  }
  const m = a.marks
  const crossAt = opt === 0 ? m.nasaSingle : opt === 2 ? m.nasaMid : null
  // The cross is four ticks round an empty middle, and the ring wider than the dot, so the dot shows through.
  const cross = (p: number[]) => {
    const [x, y, g, l] = [p[0], p[1], 1.0, 2.4]
    return (
      <path
        className="mk-known"
        d={`M${x - l} ${y - l} L${x - g} ${y - g} M${x + g} ${y + g} L${x + l} ${y + l} M${x + l} ${y - l} L${x + g} ${y - g} M${x - g} ${y + g} L${x - l} ${y + l}`}
        vectorEffect="non-scaling-stroke"
      />
    )
  }
  const marks = (
    <>
      {opt === 2 && m.tool && <circle className="mk-measured" cx={m.tool[0]} cy={m.tool[1]} r="3.6" vectorEffect="non-scaling-stroke" />}
      {nasa && crossAt && cross(crossAt)}
      {nasa && opt === 1 && m.nasaPath && m.nasaPath.length > 1 && <polyline className="mk-known dotted" points={m.nasaPath.map((p) => p.join(',')).join(' ')} vectorEffect="non-scaling-stroke" />}
    </>
  )
  const crop = a.cropPx ?? 1
  const side = (x: number): 'right' | 'left' => (x < crop * 0.6 ? 'right' : 'left')
  const labels: MarkLabel[] = []
  if (opt === 2 && m.tool) labels.push({ x: m.tool[0] + (side(m.tool[0]) === 'right' ? 4.4 : -4.4), y: m.tool[1] - 3.6, text: T1.appear.toolDot, kind: 'measured', side: side(m.tool[0]) })
  const nasaLabelAt = crossAt ?? (opt === 1 && m.nasaPath && m.nasaPath.length ? m.nasaPath[m.nasaPath.length - 1] : null)
  if (nasa && nasaLabelAt) labels.push({ x: nasaLabelAt[0] + (side(nasaLabelAt[0]) === 'right' ? 4.4 : -4.4), y: nasaLabelAt[1] + 3.6, text: T1.appear.nasaMark, kind: 'known', side: side(nasaLabelAt[0]) })
  const alt = [
    (a.differenceImages ? [T1.appear.alt1Diff, T1.appear.alt2Diff, T1.appear.alt3Diff] : [T1.appear.alt1, T1.appear.alt2, T1.appear.alt3])[opt],
    opt === 2 && m.tool ? T1.appear.altRing : null,
    nasa && crossAt ? T1.appear.altCross : null,
    nasa && opt === 1 && m.nasaPath ? T1.appear.altLine : null,
    a.blanks[opt] ? T1.appear.blanks : null,
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <>
      <Paras lines={[[a.count, T1.appear.squares, T1.appear.moon]]} />
      <SketchSlide />
      {/* Moved above the pictures (newcomer review), in body text: what these pictures are. */}
      <Paras lines={[a.differenceImages ? T1.appear.starsNoteDiff : T1.appear.starsNote, T1.appear.choose]} />
      <fieldset className="switch">
        {/* Said in the sentence just above, so read out but not shown twice. */}
        <legend className="sr-only">{T1.appear.legend}</legend>
        {T1.appear.options.map((label, i) => (
          <label key={label} className={`seg${opt === i ? ' on' : ''}`}>
            <input type="radio" name="t1-add" value={i} checked={opt === i} onChange={() => choose(i)} />
            <span>{label}</span>
          </label>
        ))}
      </fieldset>
      <div className="try-actions">
        <button type="button" className="primary" onClick={() => choose(2)}>
          {T1.appear.slide}
          <MainArrow />
        </button>
        <button
          type="button"
          className="toggle"
          aria-pressed={nasa}
          onClick={() => {
            setNasa(!nasa)
            say(spoken([nasaWords(opt, !nasa)]))
          }}
        >
          {T1.appear.showNasa}
        </button>
      </div>
      <Picture picture={a.pictures[opt]} alt={alt} crop={a.cropPx} marks={marks} labels={labels} squareBar />
      <Paras lines={[a.captions[opt], nasaWords(opt, nasa)]} className="caption" />
      {a.blanks[opt] && <p className="caption">{T1.appear.blanks}</p>}
    </>
  )
}

/** Sketch: three pictures added as taken (a smear), or slid to follow the world (one dot). */
function SketchSlide() {
  const s = T1.appear.slideSketch
  const stars: [number, number][] = [
    [14, 14],
    [58, 12],
    [44, 44],
  ]
  const world = (i: number): [number, number] => [18 + i * 18, 34 - i * 6]
  const frame = (x: number, y: number, children: ReactNode, key: string) => (
    <g key={key} transform={`translate(${x} ${y})`}>
      <rect className="sk-thin" x="0" y="0" width="76" height="56" />
      {children}
    </g>
  )
  return (
    <Sketch label={PAGE.sketchLabel} alt={s.alt} className="sketch-slide">
      <svg viewBox="0 0 340 236" width="340" height="236" className="sketch-svg" style={{ maxWidth: 340 }}>
        <text className="sk-text sk-sub" x="0" y="12">
          {s.frames}
        </text>
        {[0, 1, 2].map((i) =>
          frame(
            i * 92,
            22,
            <>
              {stars.map(([sx, sy]) => (
                <circle key={`${sx}`} className="sk-fill" cx={sx} cy={sy} r="2.4" />
              ))}
              <circle className="sk-line sk-soft" cx={world(i)[0]} cy={world(i)[1]} r="3" />
            </>,
            `f${i}`,
          ),
        )}
        {frame(
          0,
          96,
          <>
            {stars.map(([sx, sy]) => (
              <circle key={`${sx}`} className="sk-fill" cx={sx} cy={sy} r="2.4" />
            ))}
            {[0, 1, 2].map((i) => (
              <circle key={i} className="sk-thin sk-dotted" cx={world(i)[0]} cy={world(i)[1]} r="3" />
            ))}
          </>,
          'asTaken',
        )}
        <text className="sk-text" x="88" y="128">
          {s.asTaken}
        </text>
        {frame(
          0,
          170,
          <>
            {/* Slid to follow the world, each star smears into a short streak the other way. */}
            {stars.map(([sx, sy]) => (
              <path key={`${sx}`} className="sk-line" d={`M${sx + 9} ${sy - 3} L${sx - 9} ${sy + 3}`} />
            ))}
            <circle className="sk-fill" cx={world(1)[0]} cy={world(1)[1]} r="5" />
          </>,
          'slid',
        )}
        <text className="sk-text" x="88" y="202">
          {s.slid}
        </text>
      </svg>
    </Sketch>
  )
}

function Distance({ d, say }: { d: NonNullable<ReflexView['distance']>; say: (s: string) => void }) {
  const [stop, setStop] = useState(0)
  const [wrong, setWrong] = useState(false)
  const cur: StopView = wrong && d.wrong ? d.wrong : d.stops[stop]
  const speak = (v: StopView) => say(spoken([v.label, v.line]))
  return (
    <>
      <Stops
        id="t1-distance"
        label={T1.distance.label}
        value={stop}
        count={d.stops.length}
        onChange={(i) => {
          setStop(i)
          setWrong(false)
          speak(d.stops[i])
        }}
        valueText={wrong && d.wrong ? T1.distance.wrongSpoken : d.stops[stop].label}
        spoken={wrong && d.wrong ? T1.distance.wrongSpoken : d.stops[stop].spoken}
        ends={[T1.distance.endLeft, T1.distance.endRight]}
        knownTick={d.nasaTick}
        knownLabel={T1.distance.nasaTick}
      />
      <BendSketch d={d} cur={cur} />
      {d.meter && cur.delta !== null && <Meter min={d.meter.min} max={d.meter.max} value={cur.delta} text={cur.meterText} />}
      {cur.line && <p className="result-small">{cur.line}</p>}
      {d.wrong && (
        <>
          {/* The reason first, then the button (newcomer review: "why would I do that?"). */}
          <Paras lines={[T1.distance.why]} />
          <div className="try-actions">
            <button
              type="button"
              className="toggle"
              aria-pressed={wrong}
              onClick={() => {
                setWrong(!wrong)
                speak(!wrong && d.wrong ? d.wrong : d.stops[stop])
              }}
            >
              {T1.distance.wrongButton}
            </button>
          </div>
        </>
      )}
      <Paras lines={[T1.distance.several]} />
    </>
  )
}

function Meter({ min, max, value, text }: { min: number; max: number; value: number; text: string | null }) {
  const span = max - min || 1
  const at = (x: number) => ((x - min) / span) * 100
  const zero = at(0)
  const v = at(value)
  return (
    <figure className="chart meter" role="img" aria-label={text ?? T1.distance.meterLabel}>
      <figcaption className="meter-label">{T1.distance.meterLabel}</figcaption>
      <div className="meter-body" aria-hidden="true">
        <span className="meter-track" />
        <span className="meter-fill" style={{ left: `${Math.min(zero, v)}%`, width: `${Math.abs(v - zero)}%` }} />
        <span className="meter-zero" style={{ left: `${zero}%` }} />
        <span className="meter-value" style={{ left: `${v}%` }} />
      </div>
      <div className="meter-ends" aria-hidden="true">
        <span>{T1.distance.meterLeft}</span>
        <span className="meter-tick-label" style={{ left: `${zero}%` }}>
          {T1.distance.meterTick}
        </span>
        <span>{T1.distance.meterRight}</span>
      </div>
    </figure>
  )
}

/** Sketch 1-d: the dot's path worked out from the Earth's real path, with the bend made bigger. */
function BendSketch({ d, cur }: { d: NonNullable<ReflexView['distance']>; cur: StopView }) {
  const all = [...d.stops, ...(d.wrong ? [d.wrong] : [])].flatMap((s) => (s.sketch ? [...s.sketch.track, ...s.sketch.linear] : []))
  if (!cur.sketch || all.length === 0 || !d.exaggeration) return null
  const W = 340
  const H = 200
  const xs = all.map((p) => p[0])
  const ys = all.map((p) => p[1])
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const s = Math.min((W - 60) / (x1 - x0 || 1), (H - 56) / (y1 - y0 || 1))
  const cx = (W - (x1 - x0) * s) / 2
  const cy = (H - (y1 - y0) * s) / 2 + 4
  const P = (p: [number, number]) => [cx + (p[0] - x0) * s, cy + (p[1] - y0) * s] as const
  const pts = (q: [number, number][]) => q.map((p) => P(p).join(',')).join(' ')
  // The track is known only at the exposure times, which come in groups with days between them;
  // a smooth curve through every one of those points (Catmull-Rom) draws the path between them
  // without corners that the sampling, not the sky, would put there.
  const smooth = (q: [number, number][]) => {
    // Exposures a few minutes apart sit on one spot; keep one point per spot (3 px apart), and the last.
    const all = q.map(P)
    const s: (readonly [number, number])[] = []
    all.forEach((p, i) => {
      const last = s[s.length - 1]
      if (!last || Math.hypot(p[0] - last[0], p[1] - last[1]) > 3) s.push(p)
      else if (i === all.length - 1) s[s.length - 1] = p
    })
    if (s.length < 3) return `M${s.map((p) => p.join(',')).join(' L')}`
    let d = `M${s[0][0]},${s[0][1]}`
    for (let i = 0; i + 1 < s.length; i++) {
      const p0 = s[Math.max(0, i - 1)]
      const [p1, p2] = [s[i], s[i + 1]]
      const p3 = s[Math.min(s.length - 1, i + 2)]
      d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`
    }
    return d
  }
  const a = P(cur.sketch.track[0])
  const b = P(cur.sketch.track[cur.sketch.track.length - 1])
  // Dates sit just outside the path's two ends, clamped inside the drawing.
  const clampX = (x: number) => Math.min(W - 30, Math.max(30, x))
  const alt = cur.inv_d === 0 ? T1.distance.sketchAltNoBend : cur.inv_d < 0 ? T1.distance.sketchAltWrong : T1.distance.sketchAlt(cur.label)
  return (
    <Sketch label={T1.distance.sketchLabel(d.exaggeration)} alt={alt} className="sketch-bend">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="sketch-svg" style={{ maxWidth: W }}>
        <polyline className="sk-dashed" points={pts(cur.sketch.linear)} />
        <path className="sk-line" d={smooth(cur.sketch.track)} />
        <circle className="sk-dot" cx={a[0]} cy={a[1]} r="3.5" />
        <circle className="sk-dot" cx={b[0]} cy={b[1]} r="3.5" />
        {d.startLabel && (
          <text className="sk-text" x={clampX(a[0])} y={Math.max(14, a[1] - 10)} textAnchor="middle">
            {d.startLabel}
          </text>
        )}
        {d.endLabel && (
          <text className="sk-text" x={clampX(b[0])} y={Math.min(H - 4, b[1] + 20)} textAnchor="middle">
            {d.endLabel}
          </text>
        )}
      </svg>
      {/* The two lines are named in a key under the drawing, so no label sits on a path (behaviour review). */}
      <p className="sk-key">
        <svg width="28" height="8" viewBox="0 0 28 8" focusable="false">
          <path className="sk-line" d="M2 4 H26" />
        </svg>{' '}
        {T1.distance.sketchKeyTrack}
        <span className="sk-key-gap" />
        <svg width="28" height="8" viewBox="0 0 28 8" focusable="false">
          <path className="sk-dashed" d="M2 4 H26" />
        </svg>{' '}
        {T1.sketchA.straight}
      </p>
    </Sketch>
  )
}

/** Sketch 1-a: a finger twice as far shifts half as much; a world twice as far bends half as much. */
function SketchFinger() {
  const s = T1.sketchA
  // Seen from above: heads 24 apart at y 206, fingers at 20 and 40 in front, the wall at y 40.
  // The far finger's shift on a wall this near is about 0.43 of the near one's: "Not to scale".
  return (
    <Sketch label={PAGE.sketchLabelNotToScale} alt={s.alt} className="sketch-pair">
      <div className="sketch-panel">
        <p className="sk-title">{s.finger}</p>
        <svg viewBox="0 0 300 250" width="300" height="250" className="sketch-svg" style={{ maxWidth: 300 }}>
          <line className="sk-line" x1="20" y1="40" x2="280" y2="40" />
          <text className="sk-text" x="280" y="30" textAnchor="end">
            {s.wall}
          </text>
          {/* sight lines through the near finger (150,186) and the far finger (150,166) */}
          <line className="sk-thin" x1="138" y1="206" x2="237.6" y2="40" />
          <line className="sk-thin" x1="162" y1="206" x2="62.4" y2="40" />
          <line className="sk-thin sk-dashed" x1="138" y1="206" x2="187.8" y2="40" />
          <line className="sk-thin sk-dashed" x1="162" y1="206" x2="112.2" y2="40" />
          <path className="sk-line" d="M62.4 50 V58 H237.6 V50" />
          <text className="sk-text" x="150" y="72" textAnchor="middle">
            {s.near}
          </text>
          <path className="sk-line" d="M112.2 84 V92 H187.8 V84" />
          <text className="sk-text" x="150" y="106" textAnchor="middle">
            {s.far}
          </text>
          <circle className="sk-fill" cx="150" cy="186" r="3.5" />
          <circle className="sk-fill" cx="150" cy="166" r="3.5" />
          <circle className="sk-line sk-soft" cx="138" cy="214" r="8" />
          <circle className="sk-line sk-soft" cx="162" cy="214" r="8" />
          <path className="sk-line" d="M128 236 H172 M132 232 L128 236 L132 240 M168 232 L172 236 L168 240" />
          <text className="sk-text" x="182" y="240">
            {s.head}
          </text>
        </svg>
      </div>
      <div className="sketch-panel">
        <p className="sk-title">{s.earth}</p>
        <svg viewBox="0 0 300 250" width="300" height="250" className="sketch-svg" style={{ maxWidth: 300 }}>
          <circle className="sk-line sk-soft" cx="80" cy="50" r="9" />
          <text className="sk-text" x="80" y="30" textAnchor="middle">
            {s.sun}
          </text>
          <circle className="sk-thin" cx="80" cy="50" r="36" />
          {/* about 14 degrees of the orbit, two weeks */}
          <path className="sk-thick" d="M 71.3 84.9 A 36 36 0 0 0 80 86" />
          {/* Two lines, so the label fits a 360 px phone (behaviour review). */}
          <text className="sk-text" x="128" y="70">
            <tspan x="128" dy="0">
              {s.piece[0]}
            </tspan>
            <tspan x="128" dy="15">
              {s.piece[1]}
            </tspan>
          </text>
          <text className="sk-text sk-sub" x="10" y="122">
            {s.stars}
          </text>
          {Array.from({ length: 12 }, (_, i) => (
            <circle key={i} className="sk-fill" cx={18 + i * 24} cy={136} r="1.4" />
          ))}
          {/* near world: the bend is 16; the world twice as far: 8, exactly half */}
          <line className="sk-dashed" x1="30" y1="176" x2="270" y2="176" />
          <path className="sk-line" d="M30 176 Q150 144 270 176" />
          <path className="sk-thin" d="M150 160 V176 M146 160 H154 M146 176 H154" />
          <text className="sk-text" x="158" y="171">
            {s.bend}
          </text>
          <text className="sk-text" x="30" y="194">
            {s.nearWorld}
          </text>
          <text className="sk-text" x="270" y="194" textAnchor="end">
            {s.straight}
          </text>
          <line className="sk-dashed" x1="30" y1="226" x2="270" y2="226" />
          <path className="sk-line" d="M30 226 Q150 210 270 226" />
          <text className="sk-text" x="30" y="244">
            {s.farWorld}
          </text>
        </svg>
      </div>
    </Sketch>
  )
}

// ---------------------------------------------------------------------------------- tool 2

function ToolTwo({ load, view, onRetry }: { load: Load<ColourFile>; view: ColourView | null; onRetry: () => void }) {
  const [announce, setAnnounce] = useState('')
  return (
    <section className="tool" aria-labelledby={T2.id}>
      <ToolHeader n="2" id={T2.id} name={T2.name} fixture={view?.fixture ?? false} one={T2.one}>
        <Verdict chip={view?.chip ?? null} notice={view?.chip === T2.chipNotProven} glance={view?.glance ?? null} knownMark="rule" />
      </ToolHeader>
      <h3>{T2.likeThis}</h3>
      <Paras lines={T2.likeThisA} />
      <SketchTorches />
      <Paras lines={T2.likeThisB} />

      <h3>{T2.testHeading}</h3>
      {view ? (
        <>
          {view.result.length > 0 && (
            <p className="result-line">
              <Words text={view.result.join(' ')} />
            </p>
          )}
          <Paras lines={view.test} />
          <HowSure paras={view.howSure} />
        </>
      ) : (
        <DataState load={load} onRetry={onRetry} boxes={0} />
      )}

      <TryIt load={load} heading={T2.tryIt.heading}>
        {view && view.groups.length > 0 ? (
          <>
            <Paras lines={[T2.tryIt.intro]} />
            <ColourTry view={view} say={setAnnounce} />
          </>
        ) : (
          <p className="hint">{PAGE.partMissing}</p>
        )}
      </TryIt>

      {view && (
        <>
          {view.answerLine && <p className="answer-line">{view.answerLine}</p>}
          <Answers something={T2.answers.something} nothing={T2.answers.nothing} cannot={T2.answers.cannot} />
        </>
      )}
      <h3>{T2.notMean.heading}</h3>
      <Paras lines={T2.notMean.text} />
      {view && <Scientists paragraphs={view.sci} />}
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
      <JumpLink to={T3.id} className="quiet next-link">
        {T2.next}
      </JumpLink>
    </section>
  )
}

function ColourTry({ view, say }: { view: ColourView; say: (s: string) => void }) {
  const groups = view.groups
  const [g, setG] = useState(0)
  const [visited, setVisited] = useState<number[]>([0])
  const [walking, setWalking] = useState(false)
  const [compare, setCompare] = useState(false)
  const timer = useRef<number | null>(null)
  const show = (i: number, lone = compare) => {
    setG(i)
    setVisited((v) => (v.includes(i) ? v : [...v, i]))
    const list = lone && view.lone ? view.lone.groups : groups
    say(spoken([list[i].caption, list[i].insetText]))
  }
  const halt = () => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
    setWalking(false)
  }
  // "Walk through the colours": one second at each stop, then it stops. It never starts by itself,
  // and it steps without any transition, so reduced motion needs nothing different.
  const walk = () => {
    if (walking) return halt()
    setWalking(true)
    show(0)
    let i = 0
    const step = () => {
      i += 1
      show(i)
      if (i >= groups.length - 1) {
        timer.current = null
        setWalking(false)
      } else timer.current = window.setTimeout(step, 1000)
    }
    timer.current = window.setTimeout(step, 1000)
  }
  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )
  const shown = compare && view.lone ? view.lone.groups : groups
  const cur = shown[g]
  const pix = view.pixel
  const crop = view.cropPx
  const host = view.hostPx ?? (crop ? [crop / 2, crop / 2] : null)
  const partnerPx = !compare && view.partner && host ? [host[0] - view.partner.east / pix, host[1] - view.partner.north / pix] : null
  const marks = partnerPx ? <circle className="mk-known dashed" cx={partnerPx[0]} cy={partnerPx[1]} r="0.28" vectorEffect="non-scaling-stroke" /> : null
  const labels: MarkLabel[] = partnerPx ? [{ x: partnerPx[0], y: partnerPx[1] + 0.45, text: T2.tryIt.partner, kind: 'known', side: 'below' }] : []
  return (
    <>
      <Stops
        id="t2-colour"
        label={T2.tryIt.label}
        value={g}
        count={groups.length}
        onChange={(i) => {
          halt()
          show(i)
        }}
        valueText={cur.name}
        spoken={cur.spoken}
        under={groups.map((x) => x.name)}
      />
      <div className="try-actions">
        <button type="button" className="primary" onClick={walk}>
          {walking ? T2.tryIt.stop : T2.tryIt.walk}
          {!walking && <MainArrow />}
        </button>
        {view.lone && (
          <button
            type="button"
            className="toggle"
            aria-pressed={compare}
            onClick={() => {
              const next = !compare
              setCompare(next)
              setVisited([g])
              say(spoken(next && view.lone ? view.lone.line : [groups[g].caption, groups[g].insetText]))
            }}
          >
            {T2.tryIt.compare}
          </button>
        )}
      </div>
      {view.lone && <p className="hint">{T2.tryIt.compareWhy}</p>}
      {/* The drawn shift first and big, where the change can be seen; the real picture after it (newcomer review). */}
      {view.magnification && <Inset view={view} groups={shown} lone={compare} current={g} visited={visited} />}
      {compare && view.lone ? <Paras lines={[view.lone.line]} className="result-small" /> : cur.caption && <p className="caption">{cur.caption}</p>}
      <p className="chart-title picture-title">{T2.tryIt.pictureTitle}</p>
      <Picture
        picture={cur.picture}
        alt={compare ? T2.tryIt.loneAlt(cur.spoken.toLowerCase()) : T2.tryIt.pictureAlt(cur.spoken.toLowerCase())}
        crop={crop}
        marks={marks}
        labels={labels}
        squareBar
        className="picture-small"
      />
    </>
  )
}

/** Inset 2-d: the shift of the centre, drawn bigger, with its usual-error ring and the rule's ring. */
function Inset({ view, groups, lone, current, visited }: { view: ColourView; groups: ColourView['groups']; lone: boolean; current: number; visited: number[] }) {
  const S = 358
  const m = view.magnification as number
  const crop = view.cropPx as number
  const pxPerArcsec = S / (crop * view.pixel)
  const k = m * pxPerArcsec
  const c = S / 2
  const at = (e: number, n: number) => [c - e * k, c - n * k] as const
  const pa = lone ? null : view.partnerPa
  const lineEnd = pa !== null ? [c - Math.sin((pa * Math.PI) / 180) * S * 0.4, c - Math.cos((pa * Math.PI) / 180) * S * 0.4] : null
  const bar = 0.1 * view.pixel * k
  const cur = groups[current]
  const ringShown = cur.errEast !== null && cur.errNorth !== null && cur.east !== null && cur.north !== null
  const rule = view.rule
  const dot = cur.east !== null && cur.north !== null ? at(cur.east, cur.north) : null
  const moved = dot && Math.hypot(dot[0] - c, dot[1] - c) > 10
  const label = [cur.insetText, T2.tryIt.insetMore(String(m), rule !== null ? String(rule) : '')].filter(Boolean).join(' ')
  return (
    <figure className="chart inset" role="img" aria-label={label}>
      <figcaption className="chart-title">{T2.tryIt.insetTitle(String(m))}</figcaption>
      <svg viewBox={`0 0 ${S} ${S}`} className="inset-svg" aria-hidden="true" focusable="false">
        <defs>
          <marker id="tl-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path className="ch-arrowhead" d="M0 0 L10 5 L0 10 Z" />
          </marker>
        </defs>
        <rect className="ch-frame" x="0.5" y="0.5" width={S - 1} height={S - 1} />
        {lineEnd && <line className="ch-known dashed" x1={c} y1={c} x2={lineEnd[0]} y2={lineEnd[1]} />}
        {lineEnd && (
          <text className="ch-text ch-text-strong" x={lineEnd[0] + (lineEnd[0] > c ? -4 : 4)} y={lineEnd[1] + 16} textAnchor={lineEnd[0] > c ? 'end' : 'start'}>
            {T2.tryIt.lineLabel}
          </text>
        )}
        {ringShown && rule !== null && <ellipse className="ch-rule" cx={c} cy={c} rx={rule * (cur.errEast as number) * k} ry={rule * (cur.errNorth as number) * k} />}
        <path className="ch-cross" d={`M${c - 9} ${c} H${c + 9} M${c} ${c - 9} V${c + 9}`} />
        {groups.map((g, i) => {
          if (g.east === null || g.north === null || (!visited.includes(i) && i !== current)) return null
          const [x, y] = at(g.east, g.north)
          return (
            <g key={g.name} className={i === current ? '' : 'faded'}>
              {i === current && g.errEast !== null && g.errNorth !== null && <ellipse className="ch-ring" cx={x} cy={y} rx={g.errEast * k} ry={g.errNorth * k} />}
              <circle className="ch-dot" cx={x} cy={y} r="6" />
            </g>
          )
        })}
        {dot && moved && <line className="ch-arrow" x1={c} y1={c} x2={dot[0] + ((c - dot[0]) * 8) / Math.hypot(dot[0] - c, dot[1] - c)} y2={dot[1] + ((c - dot[1]) * 8) / Math.hypot(dot[0] - c, dot[1] - c)} markerEnd="url(#tl-arrow)" />}
        <path className="ch-axis" d={`M16 ${S - 20} H${16 + bar} M16 ${S - 25} V${S - 15} M${16 + bar} ${S - 25} V${S - 15}`} />
        <text className="ch-text" x={16} y={S - 30}>
          {T2.tryIt.scale}
        </text>
      </svg>
      <div className="chart-key">
        <p>
          <Mark kind="grey" /> {T2.tryIt.keyCross}
        </p>
        <p>
          <Mark kind="measured" /> {T2.tryIt.keyDot}
        </p>
        {ringShown && (
          <p>
            <Mark kind="ring" /> {T2.tryIt.keyRing}
          </p>
        )}
        {ringShown && rule !== null && (
          <p>
            <Mark kind="rule" /> {T2.tryIt.keyRule(String(rule))}
          </p>
        )}
        {!lone && (
          <p>
            <Mark kind="dashed" /> {T2.tryIt.keyLine}
          </p>
        )}
      </div>
    </figure>
  )
}

function SketchTorches() {
  const s = T2.sketch
  const panel = (x: number, title: string, redBright: boolean, crossX: number) => (
    <g>
      <text className="sk-text sk-sub" x={x + 10} y="20">
        {title}
      </text>
      <circle className="sk-line sk-soft" cx={x + 62} cy="80" r="32" />
      <circle className={redBright ? 'sk-line sk-soft' : 'sk-thin sk-dotted'} cx={x + 102} cy="80" r="32" />
      <path className="sk-line" d={`M${crossX - 6} 74 L${crossX + 6} 86 M${crossX + 6} 74 L${crossX - 6} 86`} />
      <text className="sk-text" x={crossX} y="42" textAnchor="middle">
        {s.middle}
      </text>
      <text className="sk-text" x={x + 50} y="132" textAnchor="middle">
        {s.white}
      </text>
      <text className="sk-text" x={x + 116} y="132" textAnchor="middle">
        {s.redTorch}
      </text>
    </g>
  )
  return (
    <Sketch label={PAGE.sketchLabel} alt={s.alt}>
      <svg viewBox="0 0 340 145" width="340" height="145" className="sketch-svg" style={{ maxWidth: 340 }}>
        {panel(0, s.blue, false, 66)}
        {panel(172, s.red, true, 172 + 90)}
      </svg>
    </Sketch>
  )
}

// ---------------------------------------------------------------------------------- tool 3

function ToolThree({ load, view, onRetry }: { load: Load<TransitFile>; view: TransitView | null; onRetry: () => void }) {
  const [announce, setAnnounce] = useState('')
  const ring = view?.ring
  const ringMark = ring ? <circle className="mk-measured" cx={ring.x} cy={ring.y} r={ring.r} vectorEffect="non-scaling-stroke" /> : null
  return (
    <section className="tool" aria-labelledby={T3.id}>
      <ToolHeader n="3" id={T3.id} name={T3.name} fixture={view?.fixture ?? false} one={T3.one}>
        <Verdict chip={view?.chip ?? null} glance={view?.glance ?? null} />
      </ToolHeader>
      <h3>{T3.likeThis}</h3>
      <Paras lines={T3.likeThisText} />
      <SketchDips />

      <h3>{T3.testHeading}</h3>
      {view ? (
        <>
          {(view.headline || view.asPublished) && (
            <p className="result-line">
              <Words text={[view.headline, view.asPublished].filter(Boolean).join(' ')} />
            </p>
          )}
          <Paras lines={[view.lead]} />
          <Picture picture={view.picture} alt={T3.pictureAlt} crop={ring?.crop ?? null} marks={ringMark} className="picture-small" />
          <Paras lines={[T3.pictureCaption]} className="caption" />
          <Paras lines={view.test} />
          {view.numbers && (
            <div className="numbers-row">
              <Figure kind="measured" text={view.numbers.ours} under={[view.numbers.range, PAGE.explain19]} />
              {view.numbers.published && <Figure kind="known" text={view.numbers.published} under={[view.numbers.publishedRange]} />}
            </div>
          )}
          <Paras lines={view.after} />
          <HowSure paras={view.howSure} />
        </>
      ) : (
        <DataState load={load} onRetry={onRetry} />
      )}

      <TryIt load={load} heading={T3.tryIt.heading}>
        {view?.dial ? (
          <>
            <Paras lines={[[T3.tryIt.intro, T3.tryIt.purpose]]} />
            <DipTry dial={view.dial} say={setAnnounce} />
            <Paras lines={view.dialNote} />
          </>
        ) : view?.fallback ? (
          <figure className="chart static-chart">
            <img src={view.fallback} alt={T3.tryIt.staticAlt} />
            <figcaption className="caption">{T3.tryIt.staticCaption}</figcaption>
          </figure>
        ) : (
          <p className="hint">{PAGE.partMissing}</p>
        )}
      </TryIt>

      {view && (
        <>
          {view.answerLine && <p className="answer-line">{view.answerLine}</p>}
          <Answers intro={T3.answers.intro} something={T3.answers.something} nothing={T3.answers.nothing} cannot={T3.answers.cannot} />
        </>
      )}
      <h3>{T3.notMean.heading}</h3>
      <Paras lines={T3.notMean.text} />
      <Fold summary={T3.notMean.otherDips}>
        <Paras lines={T3.notMean.otherDipsText} />
      </Fold>
      {view && <Scientists paragraphs={view.sci} />}
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </section>
  )
}

function DipTry({ dial, say }: { dial: NonNullable<TransitView['dial']>; say: (s: string) => void }) {
  const [i, setI] = useState(0)
  const cur = dial.stops[i]
  const go = (n: number) => {
    setI(n)
    const s = dial.stops[n]
    say(spoken([s.spoken, s.readout ?? s.missing, ...s.lines]))
  }
  return (
    <>
      <Stops
        id="t3-timetable"
        label={T3.tryIt.label}
        value={i}
        count={dial.stops.length}
        onChange={go}
        valueText={cur.label}
        spoken={cur.spoken}
        under={dial.stops.map((s) => s.label.replace(' days', ''))}
        knownTick={dial.knownIndex}
        knownLabel={T3.tryIt.knownTick}
      />
      <div className="try-actions">
        <button type="button" className="primary" onClick={() => go(dial.knownIndex)}>
          {T3.tryIt.useKnown}
          <MainArrow />
        </button>
      </div>
      {cur.readout ? (
        <p className="readout figure-readout">
          <Mark kind="measured" /> {cur.readout}
        </p>
      ) : (
        cur.missing && <p className="readout readout-missing">{cur.missing}</p>
      )}
      <Paras lines={[cur.lines]} className="result-small" />
      <DipBar dial={dial} stop={i} />
      <DipChart dial={dial} stop={i} />
      <Paras lines={[T3.tryIt.grey]} />
    </>
  )
}

/** The dip at this stop as a bar with its give-or-take, against the no-dip line, on one fixed scale. */
function DipBar({ dial, stop }: { dial: NonNullable<TransitView['dial']>; stop: number }) {
  const [ref, width] = useWidth()
  const cur = dial.stops[stop]
  const range = dial.barRange
  if (!range) return null
  const W = Math.min(680, width)
  const H = 70
  const L = 12
  const R = 12
  const X = (v: number) => L + ((v - range[0]) / (range[1] - range[0] || 1)) * (W - L - R)
  const ticks: number[] = []
  for (let v = Math.ceil(range[0] * 2) / 2; v <= range[1] + 1e-9; v += 0.5) ticks.push(Math.round(v * 10) / 10)
  const b = cur.bar
  const y = 30
  const tickText = (v: number) => (v < 0 ? `−${Math.abs(v)}` : `${v}`)
  return (
    <div ref={ref} className="dip-bar-wrap">
      <figure className="chart dip-bar" role="img" aria-label={cur.barSummary ?? T3.tryIt.bar.notMeasured}>
        <figcaption className="chart-title">{T3.tryIt.bar.title}</figcaption>
        <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-hidden="true" focusable="false">
          <line className="ch-axis" x1={L} y1={y + 16} x2={W - R} y2={y + 16} />
          {ticks.map((v) => (
            <g key={v}>
              <line className="ch-axis" x1={X(v)} y1={y + 16} x2={X(v)} y2={y + 20} />
              <text className="ch-text" x={X(v)} y={y + 32} textAnchor="middle">
                {tickText(v)}
              </text>
            </g>
          ))}
          <line className="ch-zero" x1={X(0)} y1={6} x2={X(0)} y2={y + 16} />
          <text className="ch-text ch-text-strong" x={X(0) - 4} y={14} textAnchor="end">
            {T3.tryIt.bar.none}
          </text>
          {b ? (
            <>
              <rect className="ch-bar" x={Math.min(X(0), X(b.depth))} y={y - 6} width={Math.abs(X(b.depth) - X(0))} height={12} />
              <path className="ch-whisker" d={`M${X(b.depth - b.err)} ${y} H${X(b.depth + b.err)} M${X(b.depth - b.err)} ${y - 7} V${y + 7} M${X(b.depth + b.err)} ${y - 7} V${y + 7}`} />
            </>
          ) : (
            <text className="ch-text" x={X(0) + 8} y={y + 4}>
              {T3.tryIt.bar.notMeasured}
            </text>
          )}
          <text className="ch-text" x={W - R} y={14} textAnchor="end">
            {T3.tryIt.bar.unit}
          </text>
        </svg>
        <p className="caption">{T3.tryIt.bar.caption}</p>
      </figure>
    </div>
  )
}

/** Chart 3-c: the real readings folded on the chosen timetable, with 45-minute averages. */
function DipChart({ dial, stop }: { dial: NonNullable<TransitView['dial']>; stop: number }) {
  const [ref, width] = useWidth()
  const cur = dial.stops[stop]
  const win = dial.window
  const points = fold(dial.readings, cur.period, dial.t0, win)
  const bins = binFolded(points, 0.75, win)
  const W = Math.min(680, width)
  const H = 260
  const L = 40
  const R = 10
  const T = 22
  const B = 34
  const [ylo, yhi] = dial.y ?? [96, 104]
  const X = (h: number) => L + ((h + win) / (2 * win)) * (W - L - R)
  const Y = (y: number) => T + ((yhi - y) / (yhi - ylo)) * (H - T - B)
  const clampY = (y: number) => Math.min(yhi, Math.max(ylo, y))
  const yTicks = Array.from({ length: yhi - ylo + 1 }, (_, k) => ylo + k).filter((v) => (yhi - ylo > 8 ? v % 2 === 0 : true))
  const half = dial.t14 !== null ? dial.t14 / 2 : null
  const model = (depthPct: number) =>
    Array.from({ length: 145 }, (_, k) => {
      const h = -win + (k * 2 * win) / 144
      const dd = dial.t14 !== null && dial.rprs !== null ? trapezoidDepth(h, dial.t14, dial.rprs) : 0
      return `${X(h)},${Y(100 - depthPct * dd)}`
    }).join(' ')
  const lines = cur.known && dial.expected !== null && dial.measured !== null
  const dipText = spoken([cur.readout ?? cur.missing, lines ? dial.measuredText : null])
  const edge = points.some((p) => p.y > yhi || p.y < ylo)
  return (
    <div ref={ref} className="dip-chart-wrap">
      <figure className="chart dip-chart" role="img" aria-label={T3.tryIt.chartSummary(cur.label.replace(' days', ''), String(points.length), dipText)}>
        <figcaption className="chart-title">{T3.tryIt.title}</figcaption>
        {/* The key above the chart, so the reader knows where to look before looking (newcomer review). */}
        <div className="chart-key chart-key-top">
          <p>
            <Mark kind="measured" /> {T3.tryIt.keyAmber}
          </p>
          <p>
            <Mark kind="greydot" /> {T3.tryIt.keyGrey}
          </p>
          {lines && (
            <>
              <p>
                <Mark kind="dashed" /> {T3.tryIt.keyLineKnown}
              </p>
              <p>
                <Mark kind="mline" /> {T3.tryIt.keyLineMeasured}
              </p>
            </>
          )}
          <p>
            <Mark kind="greyband" /> {T3.tryIt.keyBand}
          </p>
          {edge && <p>{T3.tryIt.keyEdge}</p>}
        </div>
        <p className="chart-axis-label" aria-hidden="true">
          {T3.tryIt.up}
        </p>
        <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-hidden="true" focusable="false">
          {half !== null && (
            <>
              <rect className="ch-band" x={X(-half)} y={T} width={X(half) - X(-half)} height={H - T - B} />
              <text className="ch-text ch-text-strong" x={X(0)} y={T - 6} textAnchor="middle">
                {T3.tryIt.bandLabel}
              </text>
            </>
          )}
          <line className="ch-axis" x1={L} y1={H - B} x2={W - R} y2={H - B} />
          <line className="ch-axis" x1={L} y1={T} x2={L} y2={H - B} />
          {yTicks.map((v) => (
            <g key={v}>
              <line className="ch-grid" x1={L} y1={Y(v)} x2={W - R} y2={Y(v)} />
              <text className="ch-text" x={L - 6} y={Y(v) + 4} textAnchor="end">
                {v}
              </text>
            </g>
          ))}
          {[-1, -2 / 3, -1 / 3, 0, 1 / 3, 2 / 3, 1].map((f) => Math.round(f * win)).map((h) => (
            <text key={h} className="ch-text" x={X(h)} y={H - B + 16} textAnchor="middle">
              {h > 0 ? `+${h}` : h < 0 ? `−${-h}` : '0'}
            </text>
          ))}
          {points.map((p, k) =>
            p.y > yhi || p.y < ylo ? (
              <path key={k} className="ch-grey-dot" d={p.y > yhi ? `M${X(p.h) - 4.5} ${Y(yhi) + 8} L${X(p.h) + 4.5} ${Y(yhi) + 8} L${X(p.h)} ${Y(yhi)} Z` : `M${X(p.h) - 4.5} ${Y(ylo) - 8} L${X(p.h) + 4.5} ${Y(ylo) - 8} L${X(p.h)} ${Y(ylo)} Z`} />
            ) : (
              <circle key={k} className="ch-grey-dot" cx={X(p.h)} cy={Y(p.y)} r="1.4" />
            ),
          )}
          {lines && <polyline className="ch-measured-line" points={model(dial.measured as number)} />}
          {lines && <polyline className="ch-known dashed" points={model(dial.expected as number)} />}
          {bins.map((b) => (
            <g key={b.h}>
              {b.err !== null && <line className="ch-err" x1={X(b.h)} x2={X(b.h)} y1={Y(clampY(b.mean - b.err))} y2={Y(clampY(b.mean + b.err))} />}
              <circle className="ch-dot" cx={X(b.h)} cy={Y(clampY(b.mean))} r="5" />
            </g>
          ))}
          {lines && half !== null && (
            <>
              <text className="ch-text ch-text-strong" x={X(-half) - 6} y={Y(100 - (dial.measured as number)) + 4} textAnchor="end">
                {T3.tryIt.lineOurs}
              </text>
              <text className="ch-text ch-text-strong" x={X(half) + 6} y={Y(100 - (dial.expected as number)) + 4} textAnchor="start">
                {T3.tryIt.linePublished}
              </text>
            </>
          )}
        </svg>
        <p className="chart-axis-label across" aria-hidden="true">
          {T3.tryIt.across}
        </p>
      </figure>
      <div className="sr-only">
        <table>
          <caption>{T3.tryIt.tableCaption(cur.label.replace(' days', ''))}</caption>
          <thead>
            <tr>
              <th scope="col">{T3.tryIt.tableHours}</th>
              <th scope="col">{T3.tryIt.tableBrightness}</th>
              <th scope="col">{T3.tryIt.tableGiveOrTake}</th>
            </tr>
          </thead>
          <tbody>
            {bins.map((b) => (
              <tr key={b.h}>
                <td>{b.h.toFixed(2)}</td>
                <td>{b.mean.toFixed(2)}</td>
                <td>{b.err === null ? '' : b.err.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SketchDips() {
  const s = T3.sketch
  // A drawing, not data: a fixed pattern of dots, the low ones the crossings.
  const dots = Array.from({ length: 36 }, (_, i) => {
    const wobble = ((i * 37) % 11) - 5
    const low = i % 6 === 2
    // Lined up: the low ones gather under the middle of the line, the others spread either side.
    const phase = (((i * 53) % 36) / 36) * 280 + 30
    const lined = low ? 170 + ((i - 2) / 6 - 2.5) * 10 : phase > 140 && phase < 200 ? phase + (phase < 170 ? -60 : 60) : phase
    return { t: 16 + i * 8.8, lined, y: wobble * 1.6 + (low ? 12 : 0), wobble, low }
  })
  return (
    <Sketch label={PAGE.sketchLabelNotToScale} alt={s.alt}>
      <svg viewBox="0 0 340 250" width="340" height="250" className="sketch-svg" style={{ maxWidth: 340 }}>
        <circle className="sk-line sk-soft" cx="60" cy="38" r="24" />
        <circle className="sk-line sk-fill-soft" cx="66" cy="44" r="5" />
        <text className="sk-text" x="96" y="34">
          {s.star}
        </text>
        <text className="sk-text" x="96" y="52">
          {s.planet}
        </text>
        <text className="sk-text sk-sub" x="10" y="92">
          {s.jumble}
        </text>
        <line className="sk-thin" x1="10" y1="140" x2="330" y2="140" />
        {dots.map((d, i) => (
          <circle key={`a${i}`} className="sk-fill" cx={d.t} cy={112 + d.y} r="2" />
        ))}
        <text className="sk-text sk-sub" x="10" y="166">
          {s.lined}
        </text>
        <line className="sk-thin" x1="10" y1="218" x2="330" y2="218" />
        {dots.map((d, i) => (
          <circle key={`b${i}`} className="sk-fill" cx={d.lined} cy={190 + d.wobble * 0.5 + (d.low ? 14 : 0)} r="2" />
        ))}
        <text className="sk-text" x="170" y="238" textAnchor="middle">
          {s.hours}
        </text>
      </svg>
    </Sketch>
  )
}
