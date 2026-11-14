// The space bar and the arrow keys drive the player, but they also operate whatever
// control has the keyboard focus. Someone who clicks a button or picks from a menu with
// the mouse does not expect that control to keep the focus and swallow those keys, so
// after a mouse or touch action the control lets go of it. Someone working with the
// keyboard keeps the focus where they put it.

let lastInputWasKeyboard = false

if (typeof window !== 'undefined') {
  window.addEventListener(
    'keydown',
    () => {
      lastInputWasKeyboard = true
    },
    true,
  )
  window.addEventListener(
    'pointerdown',
    () => {
      lastInputWasKeyboard = false
    },
    true,
  )
}

/** Call from a control's click or change handler. */
export function releaseFocusAfterPointer(control: HTMLElement) {
  if (!lastInputWasKeyboard) control.blur()
}

/**
 * Whether a key press should be left to the element it was typed into. Text boxes and
 * menus keep every key. Buttons, links and tick boxes keep the space bar (it presses
 * them) and a slider keeps the arrow keys (they move it).
 */
export function keyBelongsToControl(e: KeyboardEvent): boolean {
  const el = e.target instanceof HTMLElement ? e.target : null
  if (!el) return false
  const tag = el.tagName
  const type = el instanceof HTMLInputElement ? el.type : ''
  const pressable = tag === 'BUTTON' || tag === 'A' || tag === 'SUMMARY' || ['checkbox', 'radio', 'button', 'submit', 'reset'].includes(type)
  if (tag === 'SELECT' || tag === 'TEXTAREA' || el.isContentEditable) return true
  if (tag === 'INPUT' && type !== 'range' && !pressable) return true
  if (e.key === ' ') return pressable
  return type === 'range' || type === 'radio'
}
