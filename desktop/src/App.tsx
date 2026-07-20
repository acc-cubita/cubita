import { useState } from 'react'
import type { MeResponse } from './api'
import { LoginScreen } from './components/LoginScreen'
import { SetPasswordScreen } from './components/SetPasswordScreen'
import { Dashboard } from './components/Dashboard'
import { TitleBar } from './components/TitleBar'
import { isElectron } from './platform'
import { UpdateBanner } from './components/UpdateBanner'
import './App.css'

type PendingAction = { action: 'reset-password' | 'accept-invite'; token: string }

/**
 * لینک ایمیل را می‌خواند: `/?action=reset-password&token=...`
 *
 * اپ router ندارد، و لینک هم عمداً روی ریشه است نه یک مسیر جدا — چون روی هاست
 * ایستا هر مسیر دیگری بدون تنظیم fallback خطای ۴۰۴ می‌دهد، و آن خرابی فقط در
 * ایمیلِ مشتریِ قفل‌شده دیده می‌شود، نه در توسعه.
 *
 * توکن بلافاصله از نوار آدرس پاک می‌شود: لینک بازیابی عملاً یک رمز یک‌بارمصرف
 * است و ماندنش در تاریخچه‌ی مرورگر — یا رفتنش در هدر Referer به هر منبع بیرونی
 * صفحه — همان راز را جای دیگری می‌گذارد.
 */
function readPendingAction(): PendingAction | null {
  if (typeof window === 'undefined') return null
  const params = new URLSearchParams(window.location.search)
  const action = params.get('action')
  const token = params.get('token')
  if (!token || (action !== 'reset-password' && action !== 'accept-invite')) return null

  window.history.replaceState({}, '', window.location.pathname)
  return { action, token }
}

export default function App() {
  const [token, setToken] = useState<string | null>(null)
  const [me, setMe] = useState<MeResponse | null>(null)
  // مقدار اولیه با تابع داده می‌شود تا *قبل از* اولین رندر خوانده شود؛ با useEffect
  // صفحه‌ی ورود یک لحظه ظاهر می‌شد و بعد جایش عوض می‌شد.
  const [pending, setPending] = useState<PendingAction | null>(readPendingAction)

  function handleAuthenticated(newToken: string, newMe: MeResponse) {
    setToken(newToken)
    setMe(newMe)
    setPending(null)
  }

  return (
    <div className="app-window">
      {isElectron && <TitleBar />}
      {isElectron && <UpdateBanner />}
      <div className="app-window-body">
        {pending && !token ? (
          <SetPasswordScreen
            action={pending.action}
            token={pending.token}
            onDone={handleAuthenticated}
            onCancel={() => setPending(null)}
          />
        ) : !token || !me ? (
          <LoginScreen onLoggedIn={handleAuthenticated} />
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
