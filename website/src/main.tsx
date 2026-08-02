import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { CheckoutResultPage } from './pages/CheckoutResultPage.tsx'
import { TermsPage } from './pages/TermsPage.tsx'
import { PrivacyPage } from './pages/PrivacyPage.tsx'
import { ConceptLanding } from './pages/ConceptLanding.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ConceptLanding />} />
        <Route path="/concept" element={<ConceptLanding />} />
        <Route path="/classic" element={<App />} />
        <Route path="/checkout-result" element={<CheckoutResultPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
