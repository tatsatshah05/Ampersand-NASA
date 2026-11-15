// The bar at the top of every screen: every feature of the app once, in features.ts's order,
// named in the words of the level in use. One item is the current one (aria-current="page"):
// the feature the visitor is in.
//
// On the Viewer, Watch and the six tools are buttons: a tool opens its panel under the picture
// and the page scrolls to it; Watch brings the picture back. While the first pictures are still
// on their way the tools are there but cannot be pressed yet (aria-disabled). On the other
// screens the same items are links back to the Viewer, opening it with that tool. The three
// screens are always links, and every link carries the level.
import { useLayoutEffect, useRef } from 'react'
import type { UiLevel } from '../address'
import { FEATURES, scrollToShow, type FeatureKey, type ToolKey } from '../features'
import { releaseFocusAfterPointer } from '../focus'
import './FeatureBar.css'

export interface FeatureLinks {
  practise: string
  vote: string
  tools: string
  /** Off the Viewer: the Viewer's address, opening the given tool (none for Watch). */
  viewer?: (tool: ToolKey | null) => string
}

interface Props {
  level: UiLevel
  current: FeatureKey
  links: FeatureLinks
  /** On the Viewer: open a tool, or go back to the picture ('watch'); `how` says whether it was pressed from the keyboard. */
  onOpen?: (key: 'watch' | ToolKey, how: 'keyboard' | 'pointer') => void
  /** On the Viewer: false while the first pictures are still loading (the tools wait for them). */
  ready?: boolean
}

export function FeatureBar({ level, current, links, onOpen, ready = true }: Props) {
  const nav = useRef<HTMLElement>(null)
  // The current item is kept in view inside the bar (on a phone the bar scrolls sideways):
  // the bar's own scrollLeft moves, so the page itself never scrolls for it.
  useLayoutEffect(() => {
    const bar = nav.current
    const item = bar?.querySelector<HTMLElement>('[aria-current="page"]')
    if (!bar || !item) return
    const b = bar.getBoundingClientRect()
    const i = item.getBoundingClientRect()
    const to = scrollToShow({ left: b.left, width: bar.clientWidth, scrollLeft: bar.scrollLeft }, { left: i.left, width: i.width })
    if (to !== null) bar.scrollLeft = to
  }, [current, level])
  return (
    <nav className="feature-bar" aria-label="Features" ref={nav}>
      <ul className="feature-list">
        {FEATURES.map((f) => {
          const label = f.label[level]
          const here = f.key === current
          const common = {
            className: f.kind === 'screen' ? 'feature-item feature-screen' : 'feature-item',
            title: f.about[level],
            'aria-current': here ? ('page' as const) : undefined,
          }
          const text = (
            <span className="feature-text" data-text={label}>
              {label}
            </span>
          )
          let item
          if (f.kind === 'screen') {
            item = (
              <a {...common} href={links[f.key as 'practise' | 'vote' | 'tools']}>
                {text}
              </a>
            )
          } else if (onOpen) {
            const key = f.key as 'watch' | ToolKey
            const inert = f.kind === 'tool' && !ready
            item = (
              <button
                {...common}
                type="button"
                aria-disabled={inert || undefined}
                onClick={(e) => {
                  // A click from Enter or Space has no pointer position (detail 0).
                  if (!inert) onOpen(key, e.detail === 0 ? 'keyboard' : 'pointer')
                  releaseFocusAfterPointer(e.currentTarget)
                }}
              >
                {text}
              </button>
            )
          } else {
            const tool = f.kind === 'tool' ? (f.key as ToolKey) : null
            item = (
              <a {...common} href={links.viewer ? links.viewer(tool) : '/'}>
                {text}
              </a>
            )
          }
          return (
            <li key={f.key} className={f.kind === 'screen' && f.key === 'practise' ? 'feature-li feature-first-screen' : 'feature-li'}>
              {item}
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
