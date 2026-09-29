import { Loader2, RefreshCw, WifiOff } from 'lucide-react'
import type { ServerConnection } from '../lib/serverConnection'

export function ServerConnectionBanner({ status }: { status: ServerConnection | null }) {
  if (!status || status.state === 'ready' || status.state === 'unconfigured') return null
  const busy = status.state === 'checking' || status.state === 'starting'
  return (
    <div className="server-connection-banner" role="status" aria-live="polite">
      {busy ? <Loader2 size={16} className="spin" /> : <WifiOff size={16} />}
      <span>{status.message}</span>
      <button type="button" className="btn-secondary" disabled={busy}
        onClick={() => { void window.cubita.serverRetryConnection?.().catch(() => {}) }}>
        <RefreshCw size={15} /> بررسی دوباره
      </button>
    </div>
  )
}
