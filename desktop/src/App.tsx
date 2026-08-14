import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { fetchMe, type MeResponse } from './api'
import { loadStoredToken, storeToken } from './lib/session'
import { LoginScreen } from './components/LoginScreen'
import { SignupScreen } from './components/SignupScreen'
import { SetPasswordScreen } from './components/SetPasswordScreen'
import { Dashboard } from './components/Dashboard'
import { TitleBar } from './components/TitleBar'
import { isElectron } from './platform'
import { UpdateBanner } from './components/UpdateBanner'
import { SubscriptionBanner } from './components/SubscriptionBanner'
import { TrialBanner } from './components/TrialBanner'
import { TrialExpiredScreen } from './components/TrialExpiredScreen'
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

/** درِ ورودیِ ترایال از سایتِ مارکتینگ: `acc.cubita.ir/?signup` باید مستقیم روی صفحه‌ی
 *  ثبت‌نام باز شود (نه ورود). این کار ورودِ ترایال را روی prod متمرکز می‌کند به‌جای
 *  اینکه از demo.cubita.ir (دیتابیسِ جدا) رد شود. */
function wantsSignup(): boolean {
  if (typeof window === 'undefined') return false
  const params = new URLSearchParams(window.location.search)
  return params.has('signup') || params.get('action') === 'signup'
}

export default function App() {
  // مقدار اولیه با تابع داده می‌شود تا *قبل از* اولین رندر خوانده شود؛ با useEffect
  // صفحه‌ی ورود یک لحظه ظاهر می‌شد و بعد جایش عوض می‌شد.
  const [pending, setPending] = useState<PendingAction | null>(readPendingAction)
  // توکن از localStorage بازیابی می‌شود (فقط وب) تا رفرش، کاربر را از حساب بیرون نیندازد.
  // وقتی لینکِ بازیابیِ رمز باز است، جلسه‌ی ذخیره‌شده را نادیده می‌گیریم تا آن فلو مقدم بماند.
  const [token, setToken] = useState<string | null>(() => (pending ? null : loadStoredToken()))
  const [me, setMe] = useState<MeResponse | null>(null)
  // توکنِ بازیابی‌شده باید با سرور اعتبارسنجی شود (fetchMe)؛ تا آن زمان به‌جای فلاش‌خوردنِ
  // صفحه‌ی ورود، یک اسپلشِ کوتاه نشان می‌دهیم.
  const [restoring, setRestoring] = useState<boolean>(() => !pending && !!loadStoredToken())
  // درِ ورودیِ ترایال (demo.cubita.ir) با VITE_SIGNUP_FIRST=true مستقیم روی صفحه‌ی
  // ثبت‌نام باز می‌شود؛ اپِ اصلی (acc.cubita.ir) روی ورود.
  const [authView, setAuthView] = useState<'login' | 'signup'>(
    import.meta.env.VITE_SIGNUP_FIRST === 'true' || wantsSignup() ? 'signup' : 'login',
  )

  // با یک توکنِ بازیابی‌شده اما بدونِ `me`، کاربر را از سرور می‌خوانیم. اگر توکن باطل/منقضی
  // شده باشد، پاکش می‌کنیم و به صفحه‌ی ورود برمی‌گردیم (بدونِ حلقه‌ی بی‌پایان).
  useEffect(() => {
    if (!token || me) {
      setRestoring(false)
      return
    }
    if (!restoring) return
    let cancelled = false
    fetchMe(token)
      .then((res) => {
        if (cancelled) return
        setMe(res)
      })
      .catch(() => {
        if (cancelled) return
        setToken(null)
        storeToken(null)
        setMe(null)
      })
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })
    return () => {
      cancelled = true
    }
  }, [token, me, restoring])

  function handleAuthenticated(newToken: string, newMe: MeResponse) {
    setToken(newToken)
    storeToken(newToken)
    setMe(newMe)
    setPending(null)
    setRestoring(false)
    setAuthView('login')
  }

  function handleLogout() {
    setToken(null)
    storeToken(null)
    setMe(null)
    setRestoring(false)
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
        ) : restoring ? (
          <div className="app-boot">
            <Loader2 className="spin" size={28} />
            <p>در حال بازیابی جلسه…</p>
          </div>
        ) : !token || !me ? (
          authView === 'signup' ? (
            <SignupScreen onDone={handleAuthenticated} onBackToLogin={() => setAuthView('login')} />
          ) : (
            <LoginScreen onLoggedIn={handleAuthenticated} onSignup={() => setAuthView('signup')} />
          )
        ) : me.trial_expired ? (
          // آزمایشیِ منقضی: کلِ اپ جایش را به صفحه‌ی قفل می‌دهد. سرور هم مستقل همین را
          // اعمال می‌کند (۴۰۲ روی دفتر)، پس این فقط تجربه‌ی کاربری است نه تنها مرزِ امنیت.
          <TrialExpiredScreen onLogout={handleLogout} />
        ) : (
          <>
            {/* برای حسابِ آزمایشی فقط نوارِ ترایال؛ نوارِ عمومیِ اشتراک تکراری و گیج‌کننده بود. */}
            {me.is_trial ? <TrialBanner me={me} /> : <SubscriptionBanner token={token} />}
            <Dashboard token={token} me={me} onLogout={handleLogout} onMeUpdated={setMe} />
          </>
        )}
      </div>
    </div>
  )
}
