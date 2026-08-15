import { Landmark, Save, Send, ShieldCheck, ShieldAlert, FileCheck2, PlugZap } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { formatJalali } from '../lib/jalali'
import { useMoadianPanel, MOADIAN_STATUS_LABEL, MOADIAN_STATUS_TONE, type MoadianPanelState } from '../lib/moadianPanel'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

/** پنلِ کلاسیکِ «سامانه مؤدیان» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ
 *  [useMoadianPanel] است تا با ویزاردِ نسخه‌ی جدید یک‌دست بماند. */
export function MoadianPanel({ token }: { token: string }) {
  const m = useMoadianPanel({ token })

  return (
    <>
      <MoadianStats m={m} />

      <div className="workspace-split">
        <SectionCard
          icon={Landmark}
          title="تنظیمات سامانه مؤدیان"
          description="اعتبارنامه‌ی کارپوشه. کلید خصوصی فقط یک‌بار وارد می‌شود و هرگز از سرور برنمی‌گردد."
        >
          <form
            className="invoice-form form-full"
            onSubmit={(e) => {
              e.preventDefault()
              void m.save()
            }}
          >
            <MoadianCredentialFields m={m} />
            <MoadianToggles m={m} />
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={m.saving}><Save size={14} /> ذخیره تنظیمات</button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => void m.testConnection()}
                disabled={m.testing}
                title="فقط احراز هویت با سامانه را می‌سنجد — بدونِ مصرفِ سریال یا ارسالِ فاکتور"
              >
                <PlugZap size={14} /> {m.testing ? 'در حالِ آزمایش…' : 'تستِ اتصال'}
              </button>
            </div>
            <MoadianHints m={m} />
          </form>
        </SectionCard>

        <SectionCard
          icon={Send}
          title="ارسال صورتحساب"
          description="فاکتور فروشِ ارسال‌نشده را انتخاب و به سامانه بفرستید. هر فاکتور فقط یک‌بار ارسال می‌شود."
        >
          <MoadianSend m={m} />
        </SectionCard>
      </div>

      <MoadianHistory m={m} />
    </>
  )
}

/** چهار KPIِ وضعیتِ مؤدیان — مشترکِ پنل و ویزارد. */
export function MoadianStats({ m }: { m: MoadianPanelState }) {
  return (
    <div className="stat-grid">
      <StatCard
        icon={m.settings?.is_active ? <ShieldCheck size={18} /> : <ShieldAlert size={18} />}
        label="وضعیت ارسال"
        value={m.settings?.is_active ? 'فعال' : 'غیرفعال'}
        tone={m.settings?.is_active ? 'success' : 'warning'}
        hint={m.settings?.is_sandbox ? 'محیط سندباکس' : 'محیط واقعی'}
      />
      <StatCard icon={<FileCheck2 size={18} />} label="ارسال موفق" value={fa(m.sentCount)} tone="success" />
      <StatCard icon={<ShieldAlert size={18} />} label="ردشده / خطا" value={fa(m.failedCount)} tone={m.failedCount ? 'danger' : 'default'} />
      <StatCard icon={<Landmark size={18} />} label="آخرین سریال" value={fa(m.settings?.last_serial ?? 0)} />
    </div>
  )
}

/** ورودی‌های اعتبارنامه (بدونِ سوییچ‌های محیط) — مشترکِ پنل و ویزارد. */
export function MoadianCredentialFields({ m }: { m: MoadianPanelState }) {
  const { form, setForm, settings } = m
  return (
    <>
      <label>
        شناسه یکتای حافظه مالیاتی (۶ کاراکتر)
        <input value={form.memory_id} onChange={(e) => setForm({ ...form, memory_id: e.target.value })} maxLength={6} placeholder="مثلاً A1B2C3" />
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
        <input value={form.base_url_override} onChange={(e) => setForm({ ...form, base_url_override: e.target.value })} placeholder={settings?.effective_base_url ?? ''} />
      </label>
    </>
  )
}

/** سوییچ‌های محیطِ سندباکس/فعال‌بودن — مشترکِ پنل و ویزارد. */
export function MoadianToggles({ m }: { m: MoadianPanelState }) {
  const { form, setForm } = m
  return (
    <>
      <label className="cal-check-inline">
        <input type="checkbox" checked={form.is_sandbox} onChange={(e) => setForm({ ...form, is_sandbox: e.target.checked })} />
        محیط سندباکس (آزمایشی)
      </label>
      <label className="cal-check-inline">
        <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
        ارسال فعال باشد
      </label>
    </>
  )
}

/** پیام‌های وضعیت/راهنما زیرِ فرمِ تنظیمات — مشترک. */
export function MoadianHints({ m }: { m: MoadianPanelState }) {
  const { testMsg, settings, form, msg } = m
  return (
    <>
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
          {settings.has_certificate ? '' : ' — گواهی هنوز ثبت نشده'}.
        </div>
      )}
      {!form.is_sandbox && (
        <div className="hint">⚠️ محیط واقعی انتخاب شده — صورتحساب‌ها به سامانه‌ی رسمی سازمان امور مالیاتی ارسال می‌شوند.</div>
      )}
      {msg && <div className="hint">{msg}</div>}
    </>
  )
}

/** انتخابِ فاکتورِ ارسال‌نشده — بدنه‌ی «ارسال». دکمه‌ی ارسال در پنل این‌جاست؛ در ویزارد
 *  دکمه‌ی «ثبت»ِ TaskFlow آن را می‌زند، پس با showButton کنترل می‌شود. */
export function MoadianSend({ m, showButton = true }: { m: MoadianPanelState; showButton?: boolean }) {
  if (m.pendingInvoices.length === 0) {
    return (
      <>
        <EmptyState icon={FileCheck2} text="فاکتور ارسال‌نشده‌ای نیست." />
        {m.sendMsg && <div className="hint">{m.sendMsg}</div>}
      </>
    )
  }
  return (
    <>
      <div className="check-actions">
        <select value={m.selectedInvoiceId} onChange={(e) => m.setSelectedInvoiceId(e.target.value)}>
          <option value="">— انتخاب فاکتور —</option>
          {m.pendingInvoices.map((i) => (
            <option key={i.id} value={i.id}>
              شماره {i.number ?? '—'} — {formatJalali(i.invoice_date)} — {fa(i.total_amount)}
            </option>
          ))}
        </select>
        {showButton && (
          <button type="button" className="btn-primary" onClick={() => void m.submitInvoice()} disabled={m.sending}>
            <Send size={14} /> ارسال به سامانه
          </button>
        )}
      </div>
      {m.sendMsg && <div className="hint">{m.sendMsg}</div>}
    </>
  )
}

/** تاریخچه‌ی ارسال‌ها — مشترکِ پنل و ویزارد. */
export function MoadianHistory({ m }: { m: MoadianPanelState }) {
  // صفحه‌بندیِ تاریخچه (۱۰ ردیف در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(m.submissions, 10)
  return (
    <SectionCard icon={FileCheck2} title="تاریخچه ارسال‌ها" description={`${fa(m.submissions.length)} ارسال`}>
      {m.submissions.length === 0 ? (
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
              {pg.pageItems.map((s) => (
                <tr key={s.id}>
                  <td>{formatJalali(s.invoice_date)}</td>
                  <td>{s.tax_id}</td>
                  <td>{fa(s.serial)}</td>
                  <td>
                    <span className={`status-badge ${MOADIAN_STATUS_TONE[s.status] ?? ''}`}>{MOADIAN_STATUS_LABEL[s.status] ?? s.status}</span>
                  </td>
                  <td>{s.reference_number || '—'}</td>
                  <td>{s.error_message || '—'}</td>
                  <td>
                    {s.reference_number ? (
                      <button type="button" className="btn-ghost btn-sm" onClick={() => void m.inquire(s.id)}>
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
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
    </SectionCard>
  )
}
