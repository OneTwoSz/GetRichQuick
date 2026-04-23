import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
// Side-effect import: primes the offline queue so online/offline listeners
// are installed before any page renders. Service worker registration is
// kicked off by the PWA plugin's virtual module, loaded lazily elsewhere.
import './services/offlineQueue'
import './registerSW'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
