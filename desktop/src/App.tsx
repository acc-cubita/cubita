import { useState } from 'react'
import type { MeResponse } from './api'
import { LoginScreen } from './components/LoginScreen'
import { Dashboard } from './components/Dashboard'
import { TitleBar } from './components/TitleBar'
import { isElectron } from './platform'
import './App.css'

export default function App() {
  const [token, setToken] = useState<string | null>(null)
  const [me, setMe] = useState<MeResponse | null>(null)

  return (
    <div className="app-window">
      {isElectron && <TitleBar />}
      <div className="app-window-body">
        {!token || !me ? (
          <LoginScreen
            onLoggedIn={(t, m) => {
              setToken(t)
              setMe(m)
            }}
          />
        ) : (
          <Dashboard
            token={token}
            me={me}
            onLogout={() => {
              setToken(null)
              setMe(null)
            }}
          />
        )}
      </div>
    </div>
  )
}
