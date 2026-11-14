// Issue #12, part 1: details of the frame on screen, so a visitor can trust and place it.
// Every value comes straight from the /api/frames response.
import type { Frame } from '../api'

export function FrameDetails({ frame, detector }: { frame: Frame; detector: number }) {
  const wave = frame.wavelength_um // null when no exposure recorded a wavelength at the centre
  const dates = frame.date_start === frame.date_end ? frame.date_start : `${frame.date_start} to ${frame.date_end}`
  return (
    <section className="panel" aria-label="Frame details">
      <h2>Frame {frame.epoch} details</h2>
      <dl>
        <dt>Observed</dt>
        <dd>{dates}</dd>
        <dt>Exposures stacked</dt>
        <dd>{frame.n_exposures}</dd>
        <dt>Detector</dt>
        <dd>D{detector}</dd>
        <dt>Wavelength</dt>
        <dd>{wave ? `${wave[0].toFixed(2)} to ${wave[1].toFixed(2)} µm (infrared)` : 'not recorded'}</dd>
        <dt>Flagged pixels</dt>
        <dd>{(frame.flagged_fraction * 100).toFixed(1)}%</dd>
        <dt>Saturated pixels</dt>
        <dd>
          {frame.saturated_pixels}
          {frame.saturated_pixels > 0 && detector <= 4 && ' (star too bright here; try detector 5 or 6)'}
        </dd>
        <dt>Glitchy readings dropped</dt>
        <dd>{frame.rejected_readings}</dd>
      </dl>
    </section>
  )
}
