import { useEffect, useMemo, useState } from 'react'
import { SlidersHorizontal, Lock, Check } from 'lucide-react'
import {
  fetchModules,
  updateModules,
  fetchMe,
  type ModulesState,
  type MeResponse,
} from '../api'
import { NAV_GROUPS } from '../lib/navModel'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'

//: برچسبِ فارسیِ صنف‌ها — کلیدها با INDUSTRY_TEMPLATES سمتِ سرور یکی‌اند.
const INDUSTRY_LABELS: Record<string, string> = {
  general: 'عمومی',
  manufacturing: 'تولیدی',
  retail: 'خرده‌فروشی',
  services: 'خدماتی',
  distribution: 'پخش',
}

type Kind = 'core' | 'locked' | 'toggle'

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

  const dirty = useMemo(() => {
    if (enabled.size !== baseline.size) return true
    for (const k of enabled) if (!baseline.has(k)) return true
    return false
  }, [enabled, baseline])

  function kindOf(key: string): Kind {
    if (!state) return 'toggle'
    if (state.core.includes(key)) return 'core'
    if (state.restricted.includes(key) && !state.allowed.includes(key)) return 'locked'
    return 'toggle'
  }

  function toggle(key: string) {
    setMessage(null)
    setEnabled((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
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

  // فقط گروه‌هایی که ماژولِ کسب‌وکار دارند (همه‌ی NAV_GROUPS دارند).
  const groups = state
    ? NAV_GROUPS.map((g) => ({
        heading: g.heading,
        items: g.items.filter((i) => state.core.includes(i.key) || state.optional.includes(i.key)),
      })).filter((g) => g.items.length > 0)
    : []

  return (
    <div className="page panels">
      <PageHeader
        icon={SlidersHorizontal}
        title="شخصی‌سازیِ پنل"
        description="ماژول‌های موردِنیازِ کسب‌وکارتان را روشن یا خاموش کنید. خاموش‌کردن فقط از منو پنهان می‌کند و هیچ داده‌ای پاک نمی‌شود."
      />

      {error && <div className="error">{error}</div>}

      {state && (
        <div className="hint" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span>
            صنفِ کسب‌وکار: <strong>{INDUSTRY_LABELS[state.industry] ?? state.industry}</strong>
          </span>
          <span className="muted">— تغییرِ صنف و بازکردنِ ماژول‌های ویژه توسطِ پشتیبانی انجام می‌شود.</span>
        </div>
      )}

      {!isOwner && (
        <div className="hint">فقط مالکِ کسب‌وکار می‌تواند ماژول‌های پنل را تغییر دهد. این صفحه برای شما فقط‌خواندنی است.</div>
      )}

      {groups.map((g) => (
        <SectionCard key={g.heading} icon={SlidersHorizontal} title={g.heading}>
          <div className="module-grid">
            {g.items.map((item) => {
              const kind = kindOf(item.key)
              const on = kind === 'core' || enabled.has(item.key)
              return (
                <div key={item.key} className={`module-row${on ? ' on' : ''}${kind === 'locked' ? ' locked' : ''}`}>
                  <span className="module-row-icon">{item.icon}</span>
                  <span className="module-row-label">{item.label}</span>
                  {kind === 'core' && (
                    <span className="module-badge">
                      <Check size={13} /> همیشه فعال
                    </span>
                  )}
                  {kind === 'locked' && (
                    <span className="module-badge locked" title="برای فعال‌سازی با پشتیبانی تماس بگیرید">
                      <Lock size={13} /> نیازمندِ فعال‌سازی
                    </span>
                  )}
                  {kind === 'toggle' && (
                    <button
                      type="button"
                      role="switch"
                      aria-checked={on}
                      className={`module-toggle${on ? ' on' : ''}`}
                      disabled={!isOwner || saving}
                      onClick={() => toggle(item.key)}
                    >
                      <span className="module-toggle-knob" />
                      <span className="module-toggle-text">{on ? 'روشن' : 'خاموش'}</span>
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </SectionCard>
      ))}

      {isOwner && state && (
        <div className="module-save-bar">
          <button type="button" className="btn-primary" disabled={!dirty || saving} onClick={() => void save()}>
            {saving ? 'در حال ذخیره…' : 'ذخیره‌ی تغییرات'}
          </button>
          {dirty && !saving && <span className="muted">تغییراتِ ذخیره‌نشده دارید.</span>}
          {message && <span className="hint">{message}</span>}
        </div>
      )}
    </div>
  )
}
