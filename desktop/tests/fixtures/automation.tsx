// رابطِ واقعی با حمل‌ونقلِ شبیه‌سازی‌شده؛ هیچ داده یا توکنِ واقعی لازم نیست.
import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { AutomationPage } from '../../src/pages/automation/AutomationPage'
import type { MeResponse } from '../../src/api'
import '../../src/index.css'
import '../../src/App.css'

function Harness() {
  const [mode, setMode] = useState<'new' | 'inbox' | 'registry'>('new')
  const denied = new URLSearchParams(location.search).has('denied')
  const me = { id: 'self', name: 'همکار آزمایشی', role_key: 'owner', permissions: denied ? {} : { '*': ['*'] } } as MeResponse
  return <main style={{ maxWidth: 1200, width: '100%', padding: 16, margin: 'auto', boxSizing: 'border-box' }}>
    <AutomationPage token="fixture-only-token" me={me} mode={mode} onNavigate={key => setMode(key === 'letternew' ? 'new' : key === 'letterlist' ? 'registry' : 'inbox')} />
  </main>
}
createRoot(document.getElementById('root')!).render(<Harness />)
