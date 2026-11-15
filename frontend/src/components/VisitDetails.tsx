// Issue #12, part 1: the details of every visit, so a visitor can trust and place each one.
// One block per visit, all shown at once, so nothing here changes while the visits play
// (it used to describe only the visit on screen). Each block ends with that visit's
// cautions in detection.ts's own full sentences; the table says them in a word or two.
// Every value comes straight from the /api/frames response.
import type { FramesReady } from '../api'
import { blendSentences, detectionSentence, notFoundSentence, positionSentence } from '../detection'
import { visitRows } from '../motion'
import { dateSpan, rowName } from '../wording'

export function VisitDetails({ data }: { data: FramesReady }) {
  const rows = visitRows(data)
  return (
    <section className="panel visit-details" aria-label="Visit details">
      <h2>Visit details</h2>
      <p className="readout">All visits: detector D{data.detector}.</p>
      {rows.map(({ frame, index }) => {
        const wave = frame.wavelength_um // null when no exposure recorded a wavelength at the centre
        const dates = frame.date_start === frame.date_end ? frame.date_start : `${frame.date_start} to ${frame.date_end}`
        const cautions = [detectionSentence(frame), positionSentence(frame), ...blendSentences(frame), notFoundSentence(frame)].filter((l): l is string => !!l)
        const name = rowName(frame, data)
        return (
          <div className="visit-detail" key={`${frame.epoch} ${frame.date_start}`}>
            <h3>
              {name}
              {index === null ? ', the one subtracted' : ''}
              <span className="visit-detail-when">{dateSpan(frame.date_start, frame.date_end)}</span>
            </h3>
            <dl>
              <dt>Observed</dt>
              <dd>{dates}</dd>
              <dt>Exposures stacked</dt>
              <dd>{frame.n_exposures}</dd>
              <dt>Wavelength</dt>
              <dd>{wave ? `${wave[0].toFixed(2)} to ${wave[1].toFixed(2)} µm (infrared)` : 'not recorded'}</dd>
              <dt>Flagged pixels</dt>
              <dd>{(frame.flagged_fraction * 100).toFixed(1)}%</dd>
              <dt>Saturated pixels</dt>
              <dd>
                {frame.saturated_pixels}
                {/* "The target's core" only when the fit says so; the advice about detectors 5 and 6 only outside them. */}
                {frame.saturated_pixels > 0 &&
                  ` (${frame.centroid?.saturated_core ? "the target's core is overexposed here" : 'some bright pixels are overexposed'}${
                    data.detector <= 4 ? '; detectors 5 and 6 are often, not always, better' : ''
                  })`}
              </dd>
              <dt>Glitchy readings dropped</dt>
              <dd>{frame.rejected_readings}</dd>
            </dl>
            {cautions.map((line) => (
              <p key={line} className="visit-detail-note">
                {/[.!?]$/.test(line) ? line : `${line}.`}
              </p>
            ))}
          </div>
        )
      })}
    </section>
  )
}
