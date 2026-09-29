import { createRoot } from 'react-dom/client'
import { LicensePage } from '../../src/pages/LicensePage'
import { applyTheme } from '../../src/lib/theme'
import type { MeResponse } from '../../src/api'
import '../../src/index.css'
import '../../src/App.css'
applyTheme(new URLSearchParams(location.search).get('theme') ?? 'light')
const me = { role_key: 'accountant' } as MeResponse
createRoot(document.getElementById('root')!).render(<main className="app-content"><LicensePage token="qa-only" me={me} onMeUpdated={() => {}} /></main>)
