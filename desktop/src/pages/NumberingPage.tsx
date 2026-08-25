import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Hash, RefreshCw, Save } from 'lucide-react'
import { fetchNumbering, setNumbering, type NumberingRule } from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'

/**
 * روش‌های شماره‌گذاری.
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
