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
import { OfflineBanner } from './components/OfflineBanner'
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
  // وقتی لینکِ بازیابیِ رمز (`pending`) یا درِ ورودیِ ترایال (`?signup`) باز است، جلسه‌ی
  // ذخیره‌شده را نادیده می‌گیریم تا آن صفحه مقدم بماند — وگرنه بازیابیِ جلسه، بازدیدکننده‌ی
  // واردشده را مستقیم به داشبورد می‌برد و فرمِ ثبت‌نام/ورود هرگز باز نمی‌شود. توکن در
  // localStorage دست‌نخورده می‌ماند (پاک نمی‌شود)، فقط برای رندرِ اولیه کنار گذاشته می‌شود.
  // Electron هیچ‌وقت توکن را با loadStoredToken بازیابی نمی‌کند (آن مسیر عمداً
  // فقط وب است، پایینِ همین فایل توضیح داده شده) — نشستش با یک IPC آسنکرون
  // (restoreSession) در افکتِ زیر بازیابی می‌شود، پس این‌جا همیشه null شروع می‌کند.
  const forceAuthScreen = pending != null || wantsSignup()
  const [token, setToken] = useState<string | null>(() =>
    forceAuthScreen || isElectron ? null : loadStoredToken(),
  )
  const [me, setMe] = useState<MeResponse | null>(null)
  // آفلاینِ دسکتاپ: true یعنی نشستِ نمایش‌داده‌شده از کشِ محلی آمده و آخرین
  // تلاشِ رفرشِ خاموش به قطعیِ شبکه خورده، نه اینکه چیزی نامعتبر است.
  const [offline, setOffline] = useState(false)
  // توکنِ بازیابی‌شده باید با سرور اعتبارسنجی شود؛ تا آن زمان به‌جای فلاش‌خوردنِ
  // صفحه‌ی ورود، یک اسپلشِ کوتاه نشان می‌دهیم. Electron همیشه یک تلاش می‌کند —
  // حتی بدونِ نشستِ ذخیره‌شده، چون خودِ IPC این را سریع و بدونِ شبکه می‌فهمد.
  const [restoring, setRestoring] = useState<boolean>(() => {
    if (forceAuthScreen) return false
    return isElectron || !!loadStoredToken()
  })
  // درِ ورودیِ ترایال (demo.cubita.ir) با VITE_SIGNUP_FIRST=true مستقیم روی صفحه‌ی
  // ثبت‌نام باز می‌شود؛ اپِ اصلی (acc.cubita.ir) روی ورود.
  const [authView, setAuthView] = useState<'login' | 'signup'>(
    import.meta.env.VITE_SIGNUP_FIRST === 'true' || wantsSignup() ? 'signup' : 'login',
  )

  // وب: با یک توکنِ بازیابی‌شده از localStorage اما بدونِ `me`، کاربر را از سرور
  // می‌خوانیم. اگر توکن باطل/منقضی شده باشد، پاکش می‌کنیم و به صفحه‌ی ورود
  // برمی‌گردیم. **این مسیر عمداً برای Electron اجرا نمی‌شود** — افکتِ بعدی
  // مسئولِ آن است؛ اگر این‌جا هم اجرا می‌شد، با تفاوتِ زمانِ این دو افکتِ
  // آسنکرون، صفحه‌ی ورود یک لحظه (نادرست) روی نشستِ آفلاینِ معتبر ظاهر می‌شد.
  useEffect(() => {
    if (isElectron) return
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

  // Electron: بازیابیِ خاموشِ نشست از دیسکِ محلی — بدونِ نیازِ شبکه برای اصلِ
  // ورود. رفرشِ خاموش را main process می‌زند (authSession.ts)؛ خطای شبکه در
  // آن‌جا هرگز نشست را پاک نمی‌کند، فقط `offline:true` برمی‌گرداند. تنها یک‌بار
  // در بدو اجرا اجرا می‌شود؛ اگر لینکِ بازیابیِ رمز/درِ ترایال باز بود، این
  // بازیابی عمداً رد می‌شود — دقیقاً همان تصمیمی که وب با forceAuthScreen در
  // مقدارِ اولیه‌ی token می‌گیرد.
  useEffect(() => {
    if (!isElectron || forceAuthScreen) return
    let cancelled = false
    window.cubita
      .restoreSession()
      .then((result) => {
        if (cancelled) return
        if (result) {
          setToken(result.session.access_token)
          setMe(result.session.me as MeResponse)
          setOffline(result.offline)
        }
      })
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- عمداً یک‌بار؛ forceAuthScreen مقدارِ لحظه‌ی mount را می‌گیرد، هم‌الگو با مقداردهیِ اولیه‌ی token در وب.
  }, [])

  function handleAuthenticated(newToken: string, newMe: MeResponse) {
    setToken(newToken)
    storeToken(newToken)
    setMe(newMe)
    setOffline(false)
    setPending(null)
    setRestoring(false)
    setAuthView('login')
  }

  function handleLogout() {
    setToken(null)
    storeToken(null)
    setMe(null)
    setOffline(false)
    setRestoring(false)
    if (isElectron) void window.cubita.clearSession()
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
            {isElectron && offline && <OfflineBanner />}
            {/* برای حسابِ آزمایشی فقط نوارِ ترایال؛ نوارِ عمومیِ اشتراک تکراری و گیج‌کننده بود. */}
            {me.is_trial ? <TrialBanner me={me} /> : <SubscriptionBanner token={token} />}
            <Dashboard
              token={token}
              me={me}
              onLogout={handleLogout}
              onMeUpdated={setMe}
              onTokenRenewed={(t, refreshToken) => {
                setToken(t)
                storeToken(t)
                // تغییرِ رمز نسلِ توکن را جلو می‌برد و رفرشِ آفلاینِ قبلی را
                // باطل می‌کند؛ بدونِ ذخیره‌ی تازه، نشستِ آفلاینِ دسکتاپ همین‌جا
                // می‌شکست — درست همان چیزی که این کل تغییر قرار بود جلویش را بگیرد.
                if (isElectron && refreshToken) void window.cubita.persistSession(t, refreshToken, me)
              }}
            />
          </>
        )}
      </div>
    </div>
  )
}
