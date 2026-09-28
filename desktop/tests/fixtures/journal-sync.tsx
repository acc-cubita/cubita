// پوسته و فرمِ واقعی؛ حمل‌ونقلِ HTTP/IPC را اسکریپتِ مرورگر شبیه‌سازی می‌کند.
import { createRoot } from 'react-dom/client'
import { Dashboard } from '../../src/components/Dashboard'
import { applyTheme } from '../../src/lib/theme'
import { adoptServerExperience, applyExperience } from '../../src/lib/experienceMode'
import { setTenantScope } from '../../src/lib/tenantScope'
import type { MeResponse } from '../../src/api'
import '../../src/index.css'
import '../../src/App.css'

const params = new URLSearchParams(location.search)
applyTheme(params.get('theme') ?? 'light')
applyExperience('accountant')
adoptServerExperience('accountant')
setTenantScope('fixture-tenant')
const me = {
  id: 'fixture-user', name: 'حسابدار آزمایشی', email: 'fixture@example.invalid', role_key: 'accountant', role_name: 'حسابدار',
  permissions: params.has('stale') ? { '*': ['*'] } : { accounting: ['view', 'create'], checks_bank: ['view'] },
  tenant_id: 'fixture-tenant', tenant_name: 'شرکت آزمایشی', tenant_kind: 'standard',
  is_trial: false, trial_expired: false, locked_features: [], dashboard_cards: [], experience_mode: 'accountant',
  enabled_modules: [], allowed_modules: [], industry: 'general', trade: null, license: null,
} as unknown as MeResponse
createRoot(document.getElementById('root')!).render(<Dashboard token="fixture-only-token" me={me} onLogout={() => {}} onMeUpdated={() => {}} />)
