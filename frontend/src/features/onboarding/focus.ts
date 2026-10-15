import { createContext } from 'react'

/**
 * Whether a new step takes the focus to its heading. Not on the first screen,
 * where the reader has not moved yet; after each step, so that a screen reader
 * reads the new one and the keys keep working.
 */
export const FocusStepContext = createContext(false)
