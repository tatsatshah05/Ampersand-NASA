// Beginner's tool panels: the plain words first, and everything else of the panel (the tables of
// numbers, the technical controls, the method notes: what Expert shows) in one closed fold.
// What the fold holds is in the page only while it is open, so a closed fold has nothing to
// read, count or lay out, as with the folds of Expert's side column.
import { useState, type ReactNode } from 'react'
import { SCIENCE_FOLD } from '../plain'
import './PlainPanel.css'

export function ScienceFold({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <details className="fold science-fold" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>{SCIENCE_FOLD}</summary>
      {open && <div className="science-fold-body">{children}</div>}
    </details>
  )
}

/** The plain sentences about the object, as one paragraph, and the cautions under them. */
export function PlainWords({ lines, cautions = [] }: { lines: string[]; cautions?: string[] }) {
  return (
    <>
      {lines.length > 0 && <p className="plain-result">{lines.join(' ')}</p>}
      {cautions.map((c) => (
        <p key={c} className="plain-caution">
          {c}
        </p>
      ))}
    </>
  )
}
