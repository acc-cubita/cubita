import { useEffect, useRef, useState } from 'react'
import { Building2, Check, ChevronDown, Loader2 } from 'lucide-react'

import { fetchMyTenants, switchTenant, type TenantMembership } from '../api'
import { storeToken } from '../lib/session'
import { canSwitchTenant } from '../lib/tenantSwitch'

/**
 * تعویضِ کسب‌وکار — برای حسابدارِ مستقلی که دفترِ چند کسب‌وکار را می‌برد.
 *
 * بک‌اندش از مدت‌ها پیش کامل بود (`GET /api/auth/tenants` و
 * `POST /api/auth/switch-tenant`، با تأییدِ دوباره‌ی عضویت) و **صفر مصرف‌کننده**
 * داشت: کاربر باید خارج و دوباره وارد می‌شد، و هیچ‌جا نمی‌دید عضوِ کدام
 * کسب‌وکارهاست.
 *
 * ## چرا پس از تعویض، صفحه بارِ دوباره می‌خورد
 *
 * توکن که عوض شود، هر داده‌ای که در حافظه نشسته مالِ کسب‌وکارِ قبلی است — از
 * فهرستِ حساب‌ها تا آخرین فاکتوری که باز بود. به‌جای دنبال‌کردنِ ده‌ها حالت و
 * جا انداختنِ یکی، صفحه از نو بار می‌شود. کندتر است و **قابلِ اعتماد**.
 *
 * کشِ محلیِ الکترون هم پیش از بارِ دوباره پاک می‌شود؛ آن جدول‌ها ستونِ مستأجر
 * ندارند و بدونِ پاک‌کردن، داده‌ی کسب‌وکارِ قبلی زیرِ نامِ جدید دیده می‌شد.
 */
export function TenantSwitcher({
  token,
  currentTenantId,
  businessName,
}: {
  token: string
  currentTenantId: string
  businessName: string
}) {
  const [open, setOpen] = useState(false)
  const [tenants, setTenants] = useState<TenantMembership[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  //: فهرست فقط وقتی گرفته می‌شود که کاربر بازش کند — اکثرِ کاربران یک کسب‌وکار
  //: دارند و درخواستِ همیشگی برایشان بی‌فایده است.
  useEffect(() => {
    if (!open || tenants !== null) return
    fetchMyTenants(token)
      .then(setTenants)
      .catch((e) => setError(e instanceof Error ? e.message : 'فهرستِ کسب‌وکارها نیامد'))
  }, [open, tenants, token])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  async function pick(target: TenantMembership) {
    setError(null)
    const bridge = typeof window !== 'undefined' ? window.cubita : undefined
    const isDesktop = !!bridge

    //: شمارشِ صف پیش از هر کاری — گاردِ اصلی همین است.
    let pendingOutbox = 0
    if (isDesktop && bridge?.tenantPendingOutbox) {
      try {
        pendingOutbox = await bridge.tenantPendingOutbox()
      } catch {
        pendingOutbox = -1 //: نامعلوم = بسته. اجازه‌دادن با صفِ نامعلوم، ریسکِ سندِ اشتباه است.
      }
      if (pendingOutbox < 0) {
        setError('وضعیتِ صفِ آفلاین خوانده نشد؛ برای احتیاط تعویض انجام نشد.')
        return
      }
    }

    const decision = canSwitchTenant({
      currentTenantId,
      targetTenantId: target.tenant_id,
      pendingOutbox,
      isDesktop,
    })
    if (!decision.allowed) {
      if (decision.reason === 'same') setOpen(false)
      else setError(decision.message)
      return
    }

    setBusy(true)
    try {
      const res = await switchTenant(token, target.tenant_id)
      storeToken(res.access_token)
      //: کش پیش از بارِ دوباره پاک می‌شود، وگرنه صفحه‌ی تازه همان داده‌ی قبلی را
      //: از دیسک می‌خوانَد.
      if (isDesktop && bridge?.tenantClearCaches) {
        try { await bridge.tenantClearCaches() } catch { /* پاک‌نشدنِ کش نباید تعویض را ببندد */ }
      }
      window.location.reload()
    } catch (e) {
      setBusy(false)
      setError(e instanceof Error ? e.message : 'تعویضِ کسب‌وکار انجام نشد')
    }
  }

  return (
    <div className="topnav-org-wrap" ref={boxRef}>
      <button
        type="button"
        className="topnav-org"
        onClick={() => setOpen((v) => !v)}
        title="کسب‌وکارِ جاری — برای تعویض کلیک کنید"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Building2 size={15} />
        <span className="topnav-org-name">{businessName}</span>
        <ChevronDown size={13} />
      </button>

      {open && (
        <div className="topnav-org-menu" role="menu">
          {error && <p className="topnav-org-err">{error}</p>}
          {tenants === null && !error && (
            <p className="topnav-org-hint"><Loader2 size={13} className="spin" /> در حال بارگذاری…</p>
          )}
          {tenants?.length === 1 && (
            <p className="topnav-org-hint">شما فقط به همین کسب‌وکار دسترسی دارید.</p>
          )}
          {tenants?.map((t) => (
            <button
              key={t.tenant_id}
              type="button"
              className={`topnav-org-item${t.tenant_id === currentTenantId ? ' is-current' : ''}`}
              onClick={() => void pick(t)}
              disabled={busy}
              role="menuitem"
            >
              <span className="topnav-org-item-name">{t.tenant_name}</span>
              <span className="topnav-org-item-role">{t.role_name}</span>
              {t.tenant_id === currentTenantId && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
