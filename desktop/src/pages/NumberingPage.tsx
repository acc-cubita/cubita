import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Hash, ListTree, RefreshCw, RotateCcw, Save } from 'lucide-react'
import {
  fetchCodingRule,
  fetchNumbering,
  setCodingRule,
  setNumbering,
  type CodingRule,
  type NumberingRule,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'

/** پیش‌فرضِ سرویس — همان ساختارِ چارتِ کاشته‌شده. */
const DEFAULT_WIDTHS = [1, 1, 2, 2]

/**
 * روش‌های شماره‌گذاری — دو قاعده‌ی متفاوت که هر دو «شماره» تعیین می‌کنند:
 * کدینگِ حساب‌های چارت، و شماره‌ی سریِ اسناد.
 *
 * شمارنده‌ها از قبل وجود داشتند ولی نه دیده می‌شدند نه قابلِ تنظیم بودند؛ پس
 * کسب‌وکاری که با شماره‌ی فاکتور ۱۲۴۰ از سیستمِ قبلی می‌آمد ناچار از ۱ شروع می‌کرد.
 *
 * شماره فقط جلو می‌رود: عقب‌بردنِ شمارنده یعنی شماره‌ی تکراری روی سندِ ثبت‌شده، و
 * سامانه‌ی مؤدیان شماره‌گذاریِ بدونِ شکاف و بدونِ تکرار می‌خواهد. رابط کاربری همین
 * قاعده را همان‌جا نشان می‌دهد تا کاربر پیش از ذخیره بداند، نه بعد از خطا.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

export function NumberingPage({ token }: { token: string }) {
  const [rules, setRules] = useState<NumberingRule[] | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)

  async function refresh() {
    try {
      setRules(await fetchNumbering(token))
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function save(rule: NumberingRule) {
    const raw = drafts[rule.doc_type]
    const value = Number(raw)
    if (!raw || !Number.isFinite(value)) return
    setBusy(rule.doc_type)
    setMsg(null)
    try {
      const updated = await setNumbering(token, rule.doc_type, value)
      setDrafts((d) => {
        const next = { ...d }
        delete next[rule.doc_type]
        return next
      })
      setMsg({
        text: `شماره‌ی بعدیِ «${updated.label}» روی ${fa(updated.next_number)} تنظیم شد.`,
        kind: 'ok',
      })
      await refresh()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={Hash}
        title="روش‌های شماره‌گذاری"
        description="شماره‌ی سریِ هر نوع سند. اگر از سیستمِ قبلی می‌آیید، شماره‌ی شروع را همین‌جا تنظیم کنید تا سری‌تان نشکند."
      />

      {msg && (
        <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{msg.text}</div>
        </div>
      )}

      <CodingRuleCard token={token} onMessage={setMsg} />

      <SectionCard
        icon={Hash}
        title="شماره‌ی سندِ بعدی"
        description="شماره فقط می‌تواند جلو برود — شماره‌ی مصرف‌شده روی سندِ ثبت‌شده نشسته و برگرداندنش شماره‌ی تکراری می‌سازد."
        actions={
          <button type="button" onClick={() => void refresh()} disabled={busy !== null}>
            <RefreshCw size={13} /> به‌روزرسانی
          </button>
        }
      >
        {rules == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rules.length === 0 ? (
          <EmptyState icon={Hash} text="هنوز روشِ شماره‌گذاری‌ای تعریف نشده — هر سند با شماره‌ی خودکارِ پشتِ‌سرِهم صادر می‌شود." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>نوع سند</th>
                  <th>آخرین شماره</th>
                  <th>شماره‌ی بعدی</th>
                  <th>تنظیمِ شماره‌ی بعدی</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => {
                  const draft = drafts[r.doc_type] ?? ''
                  const invalid = draft !== '' && Number(draft) <= r.last_number
                  return (
                    <tr key={r.doc_type}>
                      <td className="card-title" data-label="نوع سند">
                        {r.label}
                      </td>
                      <td data-label="آخرین شماره">
                        {r.last_number === 0 ? 'بدون سند' : fa(r.last_number)}
                      </td>
                      <td data-label="شماره‌ی بعدی">{fa(r.next_number)}</td>
                      <td data-label="تنظیمِ شماره‌ی بعدی">
                        <div className="nm-set">
                          <input
                            type="number"
                            min={r.last_number + 1}
                            value={draft}
                            placeholder={String(r.next_number)}
                            onChange={(e) => setDrafts((d) => ({ ...d, [r.doc_type]: e.target.value }))}
                          />
                          <button
                            type="button"
                            className="btn-primary"
                            disabled={busy !== null || draft === '' || invalid}
                            onClick={() => void save(r)}
                          >
                            <Save size={13} /> ثبت
                          </button>
                        </div>
                        {invalid && (
                          <span className="nm-invalid">باید بزرگ‌تر از {fa(r.last_number)} باشد</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}

/**
 * قاعده‌ی کدینگِ حساب‌ها — چند رقم در هر سطحِ درخت.
 *
 * «رقمِ افزوده» است نه «طولِ کل»: کدِ هر حساب = کدِ پدرش + N رقم. پیش‌نمایشِ زنده
 * همان‌جا نشان می‌دهد که هر تغییر چه کدی می‌سازد، چون نتیجه‌ی چهار عددِ خام برای
 * کسی که هر روز با چارت کار نمی‌کند بدیهی نیست.
 *
 * حساب‌های موجود هرگز بازشماره‌گذاری نمی‌شوند — کدِ حساب روی اسناد و گزارش‌های
 * چاپ‌شده نشسته. قاعده فقط روی حسابِ تازه اعمال می‌شود.
 */
function CodingRuleCard({
  token,
  onMessage,
}: {
  token: string
  onMessage: (m: { text: string; kind: 'ok' | 'err' }) => void
}) {
  const [rule, setRule] = useState<CodingRule | null>(null)
  const [draft, setDraft] = useState<number[] | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void fetchCodingRule(token)
      .then(setRule)
      .catch(() => {})
  }, [token])

  const widths = draft ?? rule?.widths ?? DEFAULT_WIDTHS
  const names = rule?.levels.map((l) => l.name) ?? ['گروه', 'کل', 'معین', 'تفصیلی']
  // پیش‌نمایش محلی محاسبه می‌شود تا با هر تیک زنده عوض شود، نه پس از ذخیره.
  const samples = widths.reduce<string[]>((acc, w, i) => {
    acc.push((acc[i - 1] ?? '') + '1'.padStart(w, '0'))
    return acc
  }, [])
  const dirty = draft != null && JSON.stringify(draft) !== JSON.stringify(rule?.widths)

  async function save() {
    if (!draft) return
    setBusy(true)
    try {
      const next = await setCodingRule(token, draft)
      setRule(next)
      setDraft(null)
      onMessage({ text: 'قاعده‌ی کدینگ ذخیره شد. حساب‌های موجود دست نخوردند.', kind: 'ok' })
    } catch (err) {
      onMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={ListTree}
      title="کدینگِ حساب‌ها"
      description="کدِ هر حساب = کدِ سرفصلش + چند رقم. این‌جا تعیین می‌کنید هر سطح چند رقم بگیرد."
      actions={
        dirty ? (
          <button type="button" onClick={() => setDraft(null)} disabled={busy}>
            <RotateCcw size={13} /> انصراف
          </button>
        ) : undefined
      }
    >
      <div className="cd-levels">
        {widths.map((w, i) => (
          <label key={i} className="cd-level">
            <span className="cd-level-name">{names[i]}</span>
            <input
              type="number"
              min={1}
              max={6}
              value={w}
              onChange={(e) => {
                const next = [...widths]
                next[i] = Number(e.target.value)
                setDraft(next)
              }}
            />
            <span className="cd-level-sample">{samples[i]}</span>
          </label>
        ))}
      </div>

      <p className="bk-hint cd-preview">
        نمونه: {samples.join(' ← ')} — یعنی حسابِ سطحِ «{names[names.length - 1]}»{' '}
        {samples[samples.length - 1].length.toLocaleString('fa-IR')} رقم می‌شود.
      </p>

      <div className="invoice-form-footer">
        <button type="button" className="btn-primary" onClick={() => void save()} disabled={!dirty || busy}>
          <Save size={13} /> ذخیره‌ی قاعده
        </button>
      </div>

      <p className="bk-hint">
        حساب‌های موجود بازشماره‌گذاری نمی‌شوند؛ کدِ حساب روی اسناد و گزارش‌های چاپ‌شده نشسته است.
        قاعده از این پس روی حسابِ تازه اعمال می‌شود و کدِ خارج از قاعده رد خواهد شد.
      </p>
    </SectionCard>
  )
}
