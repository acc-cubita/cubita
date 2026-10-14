import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Dashboard } from '../../src/components/Dashboard'
import { QuickItemForm } from '../../src/components/QuickItemForm'
import { applyTheme } from '../../src/lib/theme'
import { adoptServerExperience, applyExperience } from '../../src/lib/experienceMode'
import type { MeResponse } from '../../src/api'
import '../../src/index.css'
import '../../src/App.css'

applyTheme('light')
applyExperience('accountant')
adoptServerExperience('accountant')
const me = {
  id: 'fixture-user', name: 'آزمون کالا', email: 'fixture@example.invalid', role_key: 'owner', role_name: 'مدیر',
  permissions: { inventory: ['view', 'create', 'update'], invoices: ['view', 'create'] },
  tenant_id: 'fixture-tenant', tenant_name: 'شرکت آزمایشی', tenant_kind: 'standard',
  is_trial: false, trial_expired: false, locked_features: [], dashboard_cards: [], experience_mode: 'accountant',
  enabled_modules: ['inventory', 'purchases'], allowed_modules: ['inventory', 'purchases'], industry: 'general', trade: null, license: null,
} as unknown as MeResponse
function Fixture() {
  const [quick, setQuick] = useState(false)
  return <>
    <button onClick={() => setQuick(true)}>ساخت سریع آزمون</button>
    {quick && <QuickItemForm token="fixture-only-token" onCreated={() => setQuick(false)} onClose={() => setQuick(false)} />}
    <Dashboard token="fixture-only-token" me={me} onLogout={() => {}} onMeUpdated={() => {}} />
  </>
}
createRoot(document.getElementById('root')!).render(<Fixture />)
