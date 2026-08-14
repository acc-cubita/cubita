import { useCallback, useEffect, useState } from 'react'
import type { MeResponse } from './api'
import { fetchMe, login } from './api'
import { LOCAL_OWNER_EMAIL, LOCAL_OWNER_PASSWORD } from './localAuth'
import { Dashboard } from './components/Dashboard'
import { TitleBar } from './components/TitleBar'
import { isElectron } from './platform'
import { UpdateBanner } from './components/UpdateBanner'
import './App.css'

// نسخه‌ی محلیِ تک‌کاربر: نه صفحه‌ی ورود/ثبت‌نام، نه ترایال/اشتراک. اپ هنگامِ باز شدن
// خودکار با اکانتِ محلیِ seed‌شده لاگین می‌کند (اعتبارش در localAuth.ts) و مستقیم به
// داشبورد می‌رود. کلِ زنجیره‌ی توکن/principal دست‌نخورده بازاستفاده می‌شود.

type AuthState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; token: string; me: MeResponse }

export default function App() {
  const [auth, setAuth] = useState<AuthState>({ status: 'loading' })

  const authenticate = useCallback(async () => {
    setAuth({ status: 'loading' })
    try {
      const token = await login(LOCAL_OWNER_EMAIL, LOCAL_OWNER_PASSWORD)
      const me = await fetchMe(token)
      setAuth({ status: 'ready', token, me })
    } catch (err) {
      setAuth({
        status: 'error',
        message: err instanceof Error ? err.message : 'اتصال به موتورِ محلی ناموفق بود',
      })
    }
  }, [])

  useEffect(() => {
    void authenticate()
  }, [authenticate])

  return (
    <div className="app-window">
      {isElectron && <TitleBar />}
      {isElectron && <UpdateBanner />}
      <div className="app-window-body">
        {auth.status === 'loading' ? (
          <div className="local-boot">
            <div className="local-boot-spinner" aria-hidden />
            <p>در حال راه‌اندازیِ موتورِ حسابداری…</p>
          </div>
        ) : auth.status === 'error' ? (
          <div className="local-boot local-boot-error">
            <p>راه‌اندازی ناموفق بود.</p>
            <p className="local-boot-detail">{auth.message}</p>
            <button type="button" onClick={() => void authenticate()}>
              تلاش دوباره
            </button>
          </div>
        ) : (
          <Dashboard
            token={auth.token}
            me={auth.me}
            onLogout={() => void authenticate()}
            onMeUpdated={(me) => setAuth((s) => (s.status === 'ready' ? { ...s, me } : s))}
          />
        )}
      </div>
    </div>
  )
}
