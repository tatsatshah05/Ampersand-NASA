// The first group of Observe anomalies: the three candidates of the sweep of the Milky Way's plane
// (finds.ts), one card each. Two real pictures side by side, the last visit it was not seen in and the
// visit it was brightest in, from the same /api/frames answer the Viewer shows for it, with what the
// pictures are and which star nearby is its steady neighbour; in Expert, right under them, the numbers
// an astronomer judges by (position, brightness, rise, dates, from finds.ts and the exported sweep
// data); then the referee's allowed sentence, "probably", the search for earlier reports (Expert: and
// what was searched) and the status, word for word from finds.ts (Beginner's "probably" and neighbour
// are findsInfo.ts's plain ones). No votes here.
import { useEffect, useState } from 'react'
import type { UiLevel } from '../address'
import {
  cardPair,
  constellationLine,
  findAddress,
  findFramesUrl,
  PICTURE_LABEL,
  pictureAlt,
  PICTURES_NOTE,
  placeWords,
  REPORT_LABEL,
  sweepRowOf,
  WATCH_LINK,
  WRITEUP_URL,
  type CardPair,
  type SweepData,
} from '../anomalies'
import { fetchFrames, hasFrames, type FramesReady } from '../api'
import { FINDS, type Find } from '../finds'
import { MAYBE_PLAIN, NEIGHBOUR_PLAIN } from '../findsInfo'
import { dateSpan } from '../wording'
import './CandidateCards.css'

export type Pictures = { state: 'loading' } | { state: 'ready'; data: FramesReady } | { state: 'error'; message: string }

export function CandidateCards({ level, sweep }: { level: UiLevel; sweep: SweepData | null }) {
  return (
    <ol className="anomaly-cards">
      {FINDS.map((find) => (
        <CandidateCard key={find.key} find={find} level={level} sweep={sweep} />
      ))}
    </ol>
  )
}

function CandidateCard({ find, level, sweep }: { find: Find; level: UiLevel; sweep: SweepData | null }) {
  const [pictures, setPictures] = useState<Pictures>({ state: 'loading' })
  useEffect(() => {
    const ctrl = new AbortController()
    fetchFrames(findFramesUrl(find), ctrl.signal)
      .then((r) => setPictures(hasFrames(r) ? { state: 'ready', data: r } : { state: 'error', message: r.message ?? 'The server has no pictures of this place.' }))
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setPictures({ state: 'error', message: e instanceof Error ? e.message : String(e) })
      })
    return () => ctrl.abort()
  }, [find])
  const row = sweepRowOf(sweep, find)
  const nameId = `find-${find.key}-name`
  return (
    <li className="anomaly-card" id={`find-${find.key}`} aria-labelledby={nameId}>
      <h3 className="anomaly-name" id={nameId}>
        {find.name}
      </h3>
      <p className="anomaly-where">{constellationLine(find)}</p>

      <CardPictures find={find} level={level} pictures={pictures} />

      {level === 'expert' && (
        <dl className="anomaly-facts">
          <dt>Position</dt>
          <dd>
            {placeWords(find.ra, find.dec)}
            {row?.sexagesimal && ` · ${row.sexagesimal}`}
            {row?.position_error_arcsec != null && ` · good to ${row.position_error_arcsec} arcsec`}
          </dd>
          <dt>Brightness</dt>
          <dd>{find.brightness}</dd>
          {row?.rise && (
            <>
              <dt>Rise</dt>
              <dd>{row.rise.charAt(0).toUpperCase() + row.rise.slice(1)}</dd>
            </>
          )}
          <dt>Last seen absent</dt>
          <dd>{row?.last_non_detection ?? `${find.lastNotSeen} UT`}</dd>
          <dt>First seen</dt>
          <dd>{row?.first_detection ?? `${find.firstSeen} UT`}</dd>
          <dt>Write-up</dt>
          <dd>
            <a href={WRITEUP_URL}>docs/sweep.md on GitHub</a>
          </dd>
        </dl>
      )}

      <blockquote className="anomaly-allowed">
        <p>{find.allowed}</p>
      </blockquote>
      <p className="anomaly-probably">{level === 'beginner' ? MAYBE_PLAIN[find.key] : find.probably}</p>
      <div className="anomaly-report">
        <p className="anomaly-label">{REPORT_LABEL[level]}</p>
        <p>{find.reportSearch}</p>
        {level === 'expert' && <p className="anomaly-checked">{find.checked}</p>}
      </div>
      <p className="anomaly-status">{find.status}</p>

      <p className="anomaly-actions">
        <a className="anomaly-watch" href={findAddress(find, level)}>
          {WATCH_LINK}
        </a>
      </p>
    </li>
  )
}

export function CardPictures({ find, level, pictures }: { find: Find; level: UiLevel; pictures: Pictures }) {
  const pair = pictures.state === 'ready' ? cardPair(pictures.data.frames) : null
  const shots: (keyof CardPair)[] = ['before', 'brightest']
  return (
    <div className="anomaly-pair-block">
      <div className="anomaly-pair">
        {shots.map((which) => {
          if (pictures.state !== 'ready' || !pair) {
            const why =
              pictures.state === 'loading'
                ? 'Loading the picture…'
                : pictures.state === 'error'
                  ? `No picture: ${pictures.message}`
                  : 'No picture: the visits do not show it unseen and then seen.'
            return (
              <figure key={which} className="anomaly-shot">
                <div className="anomaly-crop anomaly-crop-empty">
                  <span>{why}</span>
                </div>
                <figcaption>
                  <span className="anomaly-shot-label">{PICTURE_LABEL[level][which]}</span>
                </figcaption>
              </figure>
            )
          }
          const frame = pictures.data.frames[pair[which]]
          const when = dateSpan(frame.date_start, frame.date_end)
          return (
            <figure key={which} className="anomaly-shot">
              <div className="anomaly-crop">
                <img src={frame.image} alt={pictureAlt(find, which, when)} width={pictures.data.size_px} height={pictures.data.size_px} />
                <span className="anomaly-tick anomaly-tick-n" aria-hidden="true" />
                <span className="anomaly-tick anomaly-tick-s" aria-hidden="true" />
                <span className="anomaly-tick anomaly-tick-e" aria-hidden="true" />
                <span className="anomaly-tick anomaly-tick-w" aria-hidden="true" />
              </div>
              <figcaption>
                <span className="anomaly-shot-label">
                  {PICTURE_LABEL[level][which]}
                  {level === 'expert' && frame.epoch !== null && ` (visit ${frame.epoch})`}
                </span>
                <span className="anomaly-shot-date">{when}</span>
              </figcaption>
            </figure>
          )
        })}
      </div>
      <p className="anomaly-pair-note">{PICTURES_NOTE[level]}</p>
      <p className="anomaly-pair-note anomaly-neighbour">{level === 'beginner' ? NEIGHBOUR_PLAIN[find.key] : find.neighbour}</p>
    </div>
  )
}
