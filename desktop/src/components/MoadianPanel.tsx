import { useEffect, useState } from 'react'
import { Landmark, Save, Send, ShieldCheck, ShieldAlert, FileCheck2, PlugZap } from 'lucide-react'
import {
  fetchMoadianSettings,
  fetchMoadianSubmissions,
  fetchSalesInvoices,
  inquireMoadianStatus,
  submitInvoiceToMoadian,
  testMoadianConnection,
  updateMoadianSettings,
  type MoadianSettingsRecord,
  type MoadianSubmissionRecord,
  type SalesInvoiceRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { formatJalali } from '../lib/jalali'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

const STATUS_LABEL: Record<string, string> = {
  pending: 'در انتظار',
  sent: 'ارسال‌شده',
  confirmed: 'تأییدشده',
  rejected: 'ردشده',
  failed: 'خطا',
}

const STATUS_TONE: Record<string, string> = {
  pending: 'tone-warning',
  sent: 'tone-success',
  confirmed: 'tone-success',
  rejected: 'tone-danger',
  failed: 'tone-danger',
}

const EMPTY_FORM = {
  memory_id: '',
  economic_code: '',
  national_id: '',
  private_key_pem: '',
  certificate_pem: '',
  default_stuff_id: '',
  is_sandbox: true,
  is_active: false,
  base_url_override: '',
}

export function MoadianPanel({ token }: { token: string }) {
  const [settings, setSettings] = useState<MoadianSettingsRecord | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [submissions, setSubmissions] = useState<MoadianSubmissionRecord[]>([])
  const [invoices, setInvoices] = useState<SalesInvoiceRecord[]>([])
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [sendMsg, setSendMsg] = useState<string | null>(null)
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [testing, setTesting] = useState(false)

  async function refresh() {
    try {
      const [s, subs, inv] = await Promise.all([
        fetchMoadianSettings(token),
        fetchMoadianSubmissions(token),
        fetchSalesInvoices(token),
      ])
      setSettings(s)
      setSubmissions(subs)
      setInvoices(inv.filter((i) => !i.voided_at))
      // کلید عمداً پر نمی‌شود: سرور آن را برنمی‌گرداند و خالی‌ماندنش یعنی «دست نزن».
      setForm({
        memory_id: s.memory_id,
        economic_code: s.economic_code,
        national_id: s.national_id,
        private_key_pem: '',
        certificate_pem: '',
        default_stuff_id: s.default_stuff_id,
        is_sandbox: s.is_sandbox,
        is_active: s.is_active,
        base_url_override: s.base_url_override,
      })
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    try {
      await updateMoadianSettings(token, form)
      setMsg('تنظیمات ذخیره شد.')
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleTestConnection() {
    setTestMsg(null)
    setTesting(true)
    try {
      const res = await testMoadianConnection(token)
      setTestMsg({ ok: res.ok, text: res.message })
    } catch (err) {
      setTestMsg({ ok: false, text: err instanceof Error ? err.message : 'خطای ناشناخته' })
    } finally {
      setTesting(false)
    }
  }

  async function handleInquire(id: string) {
    setSendMsg(null)
    try {
      const res = await inquireMoadianStatus(token, id)
      setSendMsg(
        `وضعیت به‌روز شد: ${STATUS_LABEL[res.status] ?? res.status}${res.error_message ? ` — ${res.error_message}` : ''}`,
      )
      await refresh()
    } catch (err) {
      setSendMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleSubmitInvoice() {
    setSendMsg(null)
    if (!selectedInvoiceId) {
      setSendMsg('ابتدا یک فاکتور انتخاب کنید.')
      return
    }
    try {
      const res = await submitInvoiceToMoadian(token, selectedInvoiceId)
      setSendMsg(
        res.status === 'sent' || res.status === 'confirmed'
          ? `ارسال شد — شناسه مالیاتی ${res.tax_id}${res.reference_number ? `، مرجع ${res.reference_number}` : ''}`
          : `وضعیت: ${STATUS_LABEL[res.status] ?? res.status}${res.error_message ? ` — ${res.error_message}` : ''}`,
      )
      await refresh()
    } catch (err) {
      setSendMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const sentCount = submissions.filter((s) => s.status === 'sent' || s.status === 'confirmed').length
  const failedCount = submissions.filter((s) => s.status === 'rejected' || s.status === 'failed').length
  const submittedIds = new Set(
    submissions.filter((s) => s.status === 'sent' || s.status === 'confirmed').map((s) => s.sales_invoice_id),
  )
  const pendingInvoices = invoices.filter((i) => !submittedIds.has(i.id))

  return (
    <>
      <div className="stat-grid">
        <StatCard
          icon={settings?.is_active ? <ShieldCheck size={18} /> : <ShieldAlert size={18} />}
          label="وضعیت ارسال"
          value={settings?.is_active ? 'فعال' : 'غیرفعال'}
          tone={settings?.is_active ? 'success' : 'warning'}
          hint={settings?.is_sandbox ? 'محیط سندباکس' : 'محیط واقعی'}
        />
        <StatCard icon={<FileCheck2 size={18} />} label="ارسال موفق" value={fa(sentCount)} tone="success" />
        <StatCard icon={<ShieldAlert size={18} />} label="ردشده / خطا" value={fa(failedCount)} tone={failedCount ? 'danger' : 'default'} />
        <StatCard icon={<Landmark size={18} />} label="آخرین سریال" value={fa(settings?.last_serial ?? 0)} />
      </div>

      <div className="workspace-split">
        <SectionCard
          icon={Landmark}
          title="تنظیمات سامانه مؤدیان"
          description="اعتبارنامه‌ی کارپوشه. کلید خصوصی فقط یک‌بار وارد می‌شود و هرگز از سرور برنمی‌گردد."
        >
          <form className="invoice-form form-full" onSubmit={handleSave}>
            <label>
              شناسه یکتای حافظه مالیاتی (۶ کاراکتر)
              <input
                value={form.memory_id}
                onChange={(e) => setForm({ ...form, memory_id: e.target.value })}
                maxLength={6}
                placeholder="مثلاً A1B2C3"
              />
            </label>
            <label>
              شناسه ملی / کد ملی مؤدی
              <input value={form.national_id} onChange={(e) => setForm({ ...form, national_id: e.target.value })} />
            </label>
            <label>
              شماره اقتصادی
              <input value={form.economic_code} onChange={(e) => setForm({ ...form, economic_code: e.target.value })} />
            </label>
            <label>
              شناسه‌ی پیش‌فرضِ کالا/خدمت (۱۳ رقمی)
              <input
                value={form.default_stuff_id}
                onChange={(e) => setForm({ ...form, default_stuff_id: e.target.value })}
                placeholder="اختیاری — برای کالاهایی که کدِ اختصاصی ندارند"
                inputMode="numeric"
              />
              <span className="field-hint">هر کالا می‌تواند کدِ خودش را داشته باشد؛ این کد فقط جایگزینِ کالاهای بدونِ کد است.</span>
            </label>
            <label>
              کلید خصوصی (PEM)
              <textarea
                rows={4}
                value={form.private_key_pem}
                onChange={(e) => setForm({ ...form, private_key_pem: e.target.value })}
                placeholder={settings?.has_private_key ? '••• کلید ثبت شده — برای تغییر، کلید تازه را بچسبانید' : '-----BEGIN PRIVATE KEY-----'}
              />
            </label>
            <label>
              گواهیِ امضا (Certificate — PEM)
              <textarea
                rows={4}
                value={form.certificate_pem}
                onChange={(e) => setForm({ ...form, certificate_pem: e.target.value })}
                placeholder={settings?.has_certificate ? '••• گواهی ثبت شده — برای تغییر، گواهی تازه را بچسبانید' : '-----BEGIN CERTIFICATE-----'}
              />
            </label>
            <label>
              آدرس پایه (اختیاری — خالی یعنی پیش‌فرضِ محیط)
              <input
                value={form.base_url_override}
                onChange={(e) => setForm({ ...form, base_url_override: e.target.value })}
                placeholder={settings?.effective_base_url ?? ''}
              />
            </label>
            <label className="cal-check-inline">
              <input
                type="checkbox"
                checked={form.is_sandbox}
                onChange={(e) => setForm({ ...form, is_sandbox: e.target.checked })}
              />
              محیط سندباکس (آزمایشی)
            </label>
            <label className="cal-check-inline">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              ارسال فعال باشد
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={14} /> ذخیره تنظیمات</button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => void handleTestConnection()}
                disabled={testing}
                title="فقط احراز هویت با سامانه را می‌سنجد — بدونِ مصرفِ سریال یا ارسالِ فاکتور"
              >
                <PlugZap size={14} /> {testing ? 'در حالِ آزمایش…' : 'تستِ اتصال'}
              </button>
            </div>
            {testMsg && (
              <div className={`hint ${testMsg.ok ? 'tone-success' : 'tone-danger'}`}>
                {testMsg.ok ? '✅ ' : '⚠️ '}
                {testMsg.text}
              </div>
            )}
            {settings && (!settings.has_private_key || !settings.has_certificate) && (
              <div className="hint">
                برای ارسال، هم «کلید خصوصی» و هم «گواهیِ امضا» لازم است
                {settings.has_private_key ? '' : ' — کلید هنوز ثبت نشده'}
                {settings.has_certificate ? '' : ' — گواهی هنوز ثبت نشده'}
                .
              </div>
            )}
            {!form.is_sandbox && (
              <div className="hint">
                ⚠️ محیط واقعی انتخاب شده — صورتحساب‌ها به سامانه‌ی رسمی سازمان امور مالیاتی ارسال می‌شوند.
              </div>
            )}
            {msg && <div className="hint">{msg}</div>}
          </form>
        </SectionCard>

        <SectionCard
          icon={Send}
          title="ارسال صورتحساب"
          description="فاکتور فروشِ ارسال‌نشده را انتخاب و به سامانه بفرستید. هر فاکتور فقط یک‌بار ارسال می‌شود."
        >
          {pendingInvoices.length === 0 ? (
            <EmptyState icon={FileCheck2} text="فاکتور ارسال‌نشده‌ای نیست." />
          ) : (
            <div className="check-actions">
              <select value={selectedInvoiceId} onChange={(e) => setSelectedInvoiceId(e.target.value)}>
                <option value="">— انتخاب فاکتور —</option>
                {pendingInvoices.map((i) => (
                  <option key={i.id} value={i.id}>
                    شماره {i.number ?? '—'} — {formatJalali(i.invoice_date)} — {fa(i.total_amount)}
                  </option>
                ))}
              </select>
              <button type="button" className="btn-primary" onClick={() => void handleSubmitInvoice()}>
                <Send size={14} /> ارسال به سامانه
              </button>
            </div>
          )}
          {sendMsg && <div className="hint">{sendMsg}</div>}
        </SectionCard>
      </div>

      <SectionCard icon={FileCheck2} title="تاریخچه ارسال‌ها" description={`${fa(submissions.length)} ارسال`}>
        {submissions.length === 0 ? (
          <EmptyState icon={FileCheck2} text="هنوز صورتحسابی ارسال نشده." />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>تاریخ فاکتور</th>
                  <th>شناسه مالیاتی</th>
                  <th>سریال</th>
                  <th>وضعیت</th>
                  <th>شماره مرجع</th>
                  <th>توضیح</th>
                  <th>استعلام</th>
                </tr>
              </thead>
              <tbody>
                {submissions.map((s) => (
                  <tr key={s.id}>
                    <td>{formatJalali(s.invoice_date)}</td>
                    <td>{s.tax_id}</td>
                    <td>{fa(s.serial)}</td>
                    <td>
                      <span className={`status-badge ${STATUS_TONE[s.status] ?? ''}`}>
                        {STATUS_LABEL[s.status] ?? s.status}
                      </span>
                    </td>
                    <td>{s.reference_number || '—'}</td>
                    <td>{s.error_message || '—'}</td>
                    <td>
                      {s.reference_number ? (
                        <button type="button" className="btn-ghost btn-sm" onClick={() => void handleInquire(s.id)}>
                          استعلام وضعیت
                        </button>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  )
}
