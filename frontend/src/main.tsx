import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// The page uses the system's own face (SF Pro on a Mac), so there is no font to load.
import './index.css'
import App from './App.tsx'
// Last, so it wins over the component stylesheets: the look of the newest parts.
import './polish.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
