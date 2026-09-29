import { useEffect, useRef } from 'react'
import { createRoot } from 'react-dom/client'
import { ServerConnectionBanner } from '../../src/components/ServerConnectionBanner'
import { ServerBackupCard } from '../../src/components/ServerBackupCard'
import { ServerUpdateCard } from '../../src/components/ServerUpdateCard'
import { useServerConnection } from '../../src/lib/useServerConnection'
import { CONNECTION_EVENT } from '../../src/lib/serverConnection'
import '../../src/index.css'
import '../../src/App.css'

document.documentElement.dataset.theme = new URLSearchParams(location.search).get('theme') ?? 'light'
function Fixture() {
  const status = useServerConnection()
  const wasReady = useRef(false)
  useEffect(() => {
    if (status?.state === 'ready' && !wasReady.current) window.dispatchEvent(new Event(CONNECTION_EVENT))
    wasReady.current = status?.state === 'ready'
  }, [status?.state])
  return <><ServerConnectionBanner status={status} /><div className="page panels">
    <label>شرحِ در حال ویرایش<input aria-label="شرحِ در حال ویرایش" defaultValue="پیش‌نویس" /></label>
    <ServerUpdateCard token="QA-mock-only" /><ServerBackupCard token="QA-mock-only" />
  </div></>
}
createRoot(document.getElementById('root')!).render(<Fixture />)
