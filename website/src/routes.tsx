import { Route, Routes } from 'react-router-dom'
import { FEATURES } from './content/features'
import { CheckoutResultPage } from './pages/CheckoutResultPage'
import { ConceptLanding } from './pages/ConceptLanding'
import { DownloadPage } from './pages/DownloadPage'
import { EnterprisePage } from './pages/EnterprisePage'
import { FeaturePage } from './pages/FeaturePage'
import { FeaturesPage } from './pages/FeaturesPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PrivacyPage } from './pages/PrivacyPage'
import { TermsPage } from './pages/TermsPage'
import { CONCEPT_META } from './seo/pages'

/**
 * همه‌ی مسیرها — یک‌بار، برای مرورگر (`main.tsx`) و پیش‌رندر (`entry-server.tsx`). هر مسیرِ این‌جا باید
 * در `ALL_PAGES`ِ `seo/pages.ts` هم باشد؛ `scripts/prerender.mjs` فقط همان‌ها را می‌سازد.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<ConceptLanding />} />
      <Route path="/concept" element={<ConceptLanding meta={CONCEPT_META} />} />
      <Route path="/enterprise" element={<EnterprisePage />} />
      <Route path="/download" element={<DownloadPage />} />
      <Route path="/features" element={<FeaturesPage />} />
      {FEATURES.map((f) => (
        <Route key={f.slug} path={`/features/${f.slug}`} element={<FeaturePage feature={f} />} />
      ))}
      <Route path="/checkout-result" element={<CheckoutResultPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
