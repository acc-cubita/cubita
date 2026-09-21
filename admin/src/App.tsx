import { useCallback, useEffect, useState } from 'react'

import { UnauthorizedError, fetchDiagnostics, fetchMe, type StaffMe } from './api'
import AdminLogin from './components/AdminLogin'
import AdminShell from './components/AdminShell'
import { loadStoredToken, storeToken } from './lib/session'
import { visibleNav, type PageKey } from './nav'
import AccountsPage from './pages/AccountsPage'
import AssurancePage from './pages/AssurancePage'
import ClientErrorsPage from './pages/ClientErrorsPage'
import CommissionsPage from './pages/CommissionsPage'
import PurchasesPage from './pages/PurchasesPage'
import StaffPage from './pages/StaffPage'
import { faInt } from './ui/kit'

import './styles/tokens.css'
import './styles/admin.css'

/**
 * تم پیش از اولین رنگ‌آمیزی اعمال می‌شود تا صفحه پرش نکند.
 *
 * `data-theme` **همیشه** صریح نوشته می‌شود، حتی وقتی چیزی ذخیره نشده: در
 * `tokens.css` حالتِ بی‌صفت همان تیره است، و اگر صفت را ننویسیم دکمه‌ی تم
 * وضعیتِ فعلی را غلط می‌خواند و اولین کلیک هیچ کاری نمی‌کند.
 */
function applyStoredTheme() {
  let saved: string | null = null
  try {
    saved = localStorage.getItem('cubita.admin.theme')
  } catch {
    /* ذخیره‌سازیِ مسدود: پیش‌فرض اعمال می‌شود. */
  }
  document.documentElement.setAttribute('data-theme', saved === 'light' ? 'light' : 'dark')
}
applyStoredTheme()

export default function App() {
  const [token, setToken] = useState<string | null>(() => loadStoredToken())
  const [me, setMe] = useState<StaffMe | null>(null)
  const [booting, setBooting] = useState(true)
  const [page, setPage] = useState<PageKey>('accounts')
  const [env, setEnv] = useState<string | null>(null)

  const signOut = useCallback(() => {
    storeToken(null)
    setToken(null)
    setMe(null)
  }, [])

  /** هر ۴۰۱ یعنی نشست تمام است — یک نقطه، تا هر صفحه خودش تکرارش نکند. */
  const guard = useCallback(
    (err: unknown) => {
      if (err instanceof UnauthorizedError) signOut()
    },
    [signOut],
  )

  useEffect(() => {
    if (!token) {
      setBooting(false)
      return
    }
    let alive = true
    fetchMe(token)
      .then((m) => {
        if (!alive) return
        setMe(m)
        //: اولین صفحه‌ی مجاز — `support` مثلاً «مدیریت اکانت‌ها» را نمی‌بیند.
        const first = visibleNav(m)[0]
        if (first) setPage(first.key)
      })
      .catch((e: unknown) => {
        if (alive) {
          guard(e)
          storeToken(null)
          setToken(null)
        }
      })
      .finally(() => {
        if (alive) setBooting(false)
      })
    return () => {
      alive = false
    }
  }, [token, guard])

  useEffect(() => {
    if (!token || !me) return
    fetchDiagnostics(token)
      .then((d) => setEnv(`${d.database_name} · ${d.alembic_version ?? '—'} · ${faInt(d.tenant_count)} اکانت`))
      .catch(() => setEnv(null))
  }, [token, me])

  function onToken(t: string) {
    storeToken(t)
    setToken(t)
    setBooting(true)
  }

  if (booting) return <p className="ad-boot">در حال بارگذاری…</p>
  if (!token || !me) return <AdminLogin onToken={onToken} />

  const allowed = visibleNav(me).some((i) => i.key === page)

  return (
    <AdminShell
      me={me}
      page={page}
      onNavigate={setPage}
      onLogout={signOut}
      diagnostics={env ? <span className="ad-env" dir="ltr">{env}</span> : null}
    >
      {!allowed ? (
        <p className="ad-note tone-bad">دسترسیِ شما به این بخش باز نیست.</p>
      ) : page === 'accounts' ? (
        <AccountsPage token={token} me={me} onUnauthorized={guard} />
      ) : page === 'assurance' ? (
        <AssurancePage token={token} onUnauthorized={guard} />
      ) : page === 'commissions' ? (
        <CommissionsPage token={token} onUnauthorized={guard} />
      ) : page === 'purchases' ? (
        <PurchasesPage token={token} onUnauthorized={guard} />
      ) : page === 'errors' ? (
        <ClientErrorsPage token={token} onUnauthorized={guard} />
      ) : page === 'staff' ? (
        <StaffPage token={token} me={me} onUnauthorized={guard} />
      ) : (
        //: شاخه‌ی پایانی عمداً صفحه‌ی واقعی نیست: وقتی `staff` اینجا بود، هر
        //: کلیدِ ناشناخته‌ای صفحه‌ی «کاربران ستاد» را باز می‌کرد.
        <p className="ad-note tone-bad">این صفحه پیدا نشد.</p>
      )}
    </AdminShell>
  )
}
