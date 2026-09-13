import { useEffect, useMemo, useState } from 'react'
import { Check, Lock, RotateCcw, SlidersHorizontal } from 'lucide-react'
import {
  fetchModules,
  updateModules,
  fetchMe,
  type ModulesState,
  type MeResponse,
} from '../api'
import { NAV_GROUPS, uniqueNavItems } from '../lib/navModel'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'

/**
 * شخصی‌سازیِ پنل — کدام ماژول‌ها در منو دیده شوند.
 *
 * این صفحه یک *فهرست* است، نه یک داشبورد: کاربر می‌آید، چند کلید را می‌زند و می‌رود.
 * پس چگالی مهم‌تر از بزرگیِ اجزاست — همه‌ی ماژول‌ها در یک کارت و یک نگاه جا می‌شوند،
 * به‌جای چهارده کارتِ جدا که بیشترشان یک ردیف بیشتر ندارند.
 *
 * حالتِ «روشن» فقط با کلید نشان داده می‌شود، نه با رنگ‌کردنِ کلِ ردیف. وقتی پیش‌فرضِ
 * تقریباً همه‌چیز روشن است، ردیف‌های رنگی یعنی یک صفحه‌ی یکدست رنگی که در آن هیچ‌چیز
 * برجسته نیست؛ کلیدِ آرام همان اطلاعات را می‌دهد و *خاموش‌ها* را دیدنی می‌کند.
 */

//: برچسبِ فارسیِ صنف‌ها — کلیدها با INDUSTRY_TEMPLATES سمتِ سرور یکی‌اند.
const INDUSTRY_LABELS: Record<string, string> = {
  general: 'عمومی',
  manufacturing: 'تولیدی',
  retail: 'خرده‌فروشی',
  services: 'خدماتی',
  distribution: 'پخش',
}

type Kind = 'core' | 'locked' | 'toggle'

const fa = (n: number) => n.toLocaleString('fa-IR')

export function ModulesPage({
  token,
  me,
  onMeUpdated,
}: {
  token: string
  me: MeResponse
  onMeUpdated: (me: MeResponse) => void
}) {
  const isOwner = me.role_key === 'owner'
  const [state, setState] = useState<ModulesState | null>(null)
  const [enabled, setEnabled] = useState<Set<string>>(new Set())
  const [baseline, setBaseline] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function applyState(s: ModulesState) {
    setState(s)
    // فقط اختیاری‌های روشن را در استیتِ محلی نگه می‌داریم؛ core همیشه روشن است.
    const on = new Set(s.enabled.filter((k) => s.optional.includes(k)))
    setEnabled(on)
    setBaseline(new Set(on))
  }

  async function load() {
    try {
      applyState(await fetchModules(token))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function kindOf(key: string): Kind {
    if (!state) return 'toggle'
    if (state.core.includes(key)) return 'core'
    if (state.restricted.includes(key) && !state.allowed.includes(key)) return 'locked'
    return 'toggle'
  }

  // فقط گروه‌هایی که ماژولِ کسب‌وکار دارند (همه‌ی NAV_GROUPS دارند).
  const groups = useMemo(
    () =>
      state
        ? NAV_GROUPS.map((g) => ({
            heading: g.heading,
            items: g.items.filter(
              (i) => state.core.includes(i.key) || state.optional.includes(i.key),
            ),
          })).filter((g) => g.items.length > 0)
        : [],
    [state],
  )

  // شمارشِ کلیدهای *قابلِ تغییر* — core همیشه روشن است و قفل‌شده‌ها دستِ کاربر نیستند،
  // پس آوردنشان در شمارش عددی می‌سازد که کاربر نمی‌تواند تغییرش دهد.
  const toggleable = useMemo(
    () =>
      uniqueNavItems(groups).filter((i) => kindOf(i.key) === 'toggle').map((i) => i.key),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [groups, state],
  )
  const onCount = toggleable.filter((k) => enabled.has(k)).length

  const changed = useMemo(() => {
    const keys = new Set([...enabled, ...baseline])
    return [...keys].filter((k) => enabled.has(k) !== baseline.has(k)).length
  }, [enabled, baseline])

  function toggle(key: string) {
    setMessage(null)
    setEnabled((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function setAll(on: boolean) {
    setMessage(null)
    setEnabled(on ? new Set(toggleable) : new Set())
  }

  async function save() {
    setSaving(true)
    setMessage(null)
    try {
      const fresh = await updateModules(token, Array.from(enabled))
      applyState(fresh)
      // ناوبری باید زنده به‌روز شود → me را تازه می‌کنیم.
      onMeUpdated(await fetchMe(token))
      setMessage('تغییرات ذخیره شد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setSaving(false)
    }
  }

  const industry = state ? INDUSTRY_LABELS[state.industry] ?? state.industry : ''

  return (
    <div className="page panels">
      <PageHeader
        icon={SlidersHorizontal}
        title="شخصی‌سازیِ پنل"
        description="ماژول‌های موردِنیازِ کسب‌وکارتان را روشن یا خاموش کنید. خاموش‌کردن فقط از منو پنهان می‌کند و هیچ داده‌ای پاک نمی‌شود."
      />

      {error && <div className="error">{error}</div>}

      <SectionCard
        icon={SlidersHorizontal}
        title="ماژول‌های پنل"
        description={
          state
            ? `صنفِ ${industry} — ${fa(onCount)} از ${fa(toggleable.length)} ماژولِ اختیاری روشن است.`
            : 'در حال بارگذاری…'
        }
        actions={
          isOwner && state ? (
            <>
              <button type="button" disabled={saving} onClick={() => setAll(true)}>
                همه
              </button>
              <button type="button" disabled={saving} onClick={() => setAll(false)}>
                هیچ‌کدام
              </button>
            </>
          ) : undefined
        }
      >
        {!isOwner && (
          <p className="mp-note-line">
            فقط مالکِ کسب‌وکار می‌تواند ماژول‌های پنل را تغییر دهد؛ این صفحه برای شما فقط‌خواندنی است.
          </p>
        )}

        {state && (
          <div className="mp-groups">
            {groups.map((g) => (
              <div key={g.heading} className="mp-group">
                <h3 className="mp-group-title">{g.heading}</h3>
                <div className="mp-items">
                  {g.items.map((item) => {
                    const kind = kindOf(item.key)
                    const on = kind === 'core' || enabled.has(item.key)

                    if (kind === 'toggle') {
                      return (
                        <button
                          key={item.key}
                          type="button"
                          role="switch"
                          aria-checked={on}
                          className={`mp-item${on ? ' is-on' : ''}`}
                          disabled={!isOwner || saving}
                          onClick={() => toggle(item.key)}
                        >
                          <span className="mp-item-ico">{item.icon}</span>
                          <span className="mp-item-name">{item.label}</span>
                          <span className="mp-switch" aria-hidden="true">
                            <span className="mp-switch-knob" />
                          </span>
                        </button>
                      )
                    }

                    return (
                      <div key={item.key} className={`mp-item is-static is-${kind}`}>
                        <span className="mp-item-ico">{item.icon}</span>
                        <span className="mp-item-name">{item.label}</span>
                        {kind === 'core' ? (
                          <span className="mp-tag" title="ستونِ فقراتِ برنامه — خاموش‌شدنی نیست">
                            <Check size={12} /> همیشه
                          </span>
                        ) : (
                          <span className="mp-tag is-lock" title="برای فعال‌سازی با پشتیبانی تماس بگیرید">
                            <Lock size={12} /> فعال‌سازی
                          </span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* نوارِ ذخیره فقط وقتی چیزی عوض شده — یک نوارِ همیشه‌حاضرِ غیرفعال هم جا می‌گیرد
          هم به کاربر می‌گوید «کاری هست که نکرده‌ای»، در حالی که کاری نیست. */}
      {isOwner && changed > 0 && (
        <div className="mp-savebar">
          <span className="mp-savebar-count">{fa(changed)} تغییرِ ذخیره‌نشده</span>
          <button type="button" disabled={saving} onClick={() => setEnabled(new Set(baseline))}>
            <RotateCcw size={13} /> انصراف
          </button>
          <button type="button" className="btn-primary" disabled={saving} onClick={() => void save()}>
            {saving ? 'در حال ذخیره…' : 'ذخیره‌ی تغییرات'}
          </button>
        </div>
      )}

      {message && <p className="mp-note-line">{message}</p>}
    </div>
  )
}
