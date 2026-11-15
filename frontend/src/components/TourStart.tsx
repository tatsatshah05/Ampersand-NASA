// "Demo mode", at the right end of the top bar of every screen: starts the guided tour (Tour.tsx listens for
// the signal). It is hidden while the tour runs, when the card's own "End tour" is the way out.
import { DEMO_BUTTON, DEMO_BUTTON_ABOUT, TOUR_START_EVENT } from '../tour'
import './Tour.css'

export function TourStart() {
  return (
    <button type="button" className="tour-start" title={DEMO_BUTTON_ABOUT} onClick={() => window.dispatchEvent(new Event(TOUR_START_EVENT))}>
      {DEMO_BUTTON}
    </button>
  )
}
