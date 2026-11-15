import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// One typeface for the whole page: Atkinson Hyperlegible, drawn for legibility, in its two weights.
import '@fontsource/atkinson-hyperlegible/400.css'
import '@fontsource/atkinson-hyperlegible/700.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
