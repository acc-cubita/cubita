import { useEffect, useState } from 'react'
import { CONNECTION_EVENT, type ServerConnection } from './serverConnection'

export function useServerConnection(): ServerConnection | null {
  const [status, setStatus] = useState<ServerConnection | null>(null)
  useEffect(() => {
    const bridge = window.cubita
    if (window.cubitaConfig?.edition !== 'enterprise' || !bridge?.serverConnection || !bridge.onServerConnection) return
    let active = true
    let received = false
    const stop = bridge.onServerConnection((next) => { received = true; if (active) setStatus(next) })
    void bridge.serverConnection().then((next) => { if (active && !received) setStatus(next) }).catch(() => {})
    return () => { active = false; stop() }
  }, [])
  return status
}

/** Refresh read-only cards without reloading the app or discarding forms. */
export function useServerReconnect(load: () => void): void {
  useEffect(() => {
    window.addEventListener(CONNECTION_EVENT, load)
    return () => window.removeEventListener(CONNECTION_EVENT, load)
  }, [load])
}
