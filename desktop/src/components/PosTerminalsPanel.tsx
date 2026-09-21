import { useCallback, useEffect, useState } from 'react'
import { CreditCard, Save, Pencil, X, RefreshCw, Plus, Trash2, PlugZap, Monitor } from 'lucide-react'
import {
  fetchAnalytics,
  fetchPosTerminals,
  createPosTerminal,
  updatePosTerminal,
  deletePosTerminal,
  type PosTerminalRecord,
  type PosTransport,
} from '../api'
import type { BankAccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { SearchSelect } from '../components/SearchSelect'
import { FormField } from './form/FormKit'

interface Draft {
  label: string
  name2: string
  terminal_no: string
  currency_code: string
  transport: PosTransport
  host: string
  port: string
  com_port: string
  psp: string
  bank_account_id: string
  analytic_id: string
  is_default: boolean
}
const EMPTY: Draft = {
  label: '',
  name2: '',
  terminal_no: '',
  currency_code: 'IRR',
  transport: 'simulator',
  host: '',
  port: '',
  com_port: '',
  psp: '',
  bank_account_id: '',
  analytic_id: '',
  is_default: false,
}

const TRANSPORTS: { value: PosTransport; label: string }[] = [
  { value: 'simulator', label: 'شبیه‌ساز (بدونِ دستگاه)' },
  { value: 'network', label: 'تحت شبکه (IP:Port)' },
  { value: 'serial', label: 'USB / سریال (COM)' },
  { value: 'sdk', label: 'SDK اختصاصیِ PSP' },
]
/** صفر خط تیره می‌شود تا چشم از ارقامِ واقعی منحرف نشود. */
const faAmount = (v: string) => {
  const n = Math.round(Number(v) || 0)
  return n === 0 ? '—' : n.toLocaleString('fa-IR')
}
const transportLabel = (t: PosTransport) => TRANSPORTS.find((x) => x.value === t)?.label ?? t

/**
 * مدیریتِ دستگاه‌های کارتخوان — ساخت/ویرایش/حذف، انتخابِ حسابِ بانکیِ تسویه، و «تستِ
 * اتصال». پیکربندی سرور-ساید است و در هر دو نسخه (وب/دسکتاپ) دیده می‌شود؛ ولی خودِ
 * اتصال به سخت‌افزار (تست/پرداخت) فقط در دسکتاپ رخ می‌دهد.
 */
export function PosTerminalsPanel({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const desktop = typeof window !== 'undefined' && !!window.cubita?.posTerminal
  const [terminals, setTerminals] = useState<PosTerminalRecord[] | null>(null)
  const [analytics, setAnalytics] = useState<{ id: string; code: string; name: string }[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [form, setForm] = useState<Draft>(EMPTY)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testMsg, setTestMsg] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  //: `null` یعنی «این‌جا دسکتاپ نیست» و همان ورودیِ متنی می‌ماند؛ آرایه‌ی خالی
  //: یعنی دسکتاپ هست ولی هیچ درگاهی پیدا نشد — دو چیزِ متفاوت با دو پیامِ متفاوت.
  const [serialPorts, setSerialPorts] = useState<{ path: string; label: string }[] | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setTerminals(await fetchPosTerminals(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => {
    fetchAnalytics(token).then(setAnalytics).catch(() => setAnalytics([]))
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  //: فهرست یک بار موقعِ باز شدن گرفته می‌شود. کاربری که وسطِ کار کابل را می‌زند،
  //: با دکمه‌ی «تستِ اتصال» می‌فهمد درگاهش نیست — پیامش همان را می‌گوید.
  useEffect(() => {
    const bridge = typeof window !== 'undefined' ? window.cubita?.posTerminal : undefined
    if (!bridge?.serialPorts) return
    bridge.serialPorts().then(setSerialPorts).catch(() => setSerialPorts([]))
  }, [])

  // صفحه‌بندیِ کارتخوان‌ها (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(terminals ?? [], 10)

  function startEdit(t: PosTerminalRecord) {
    setEditingId(t.id)
    setForm({
      label: t.label,
      name2: t.name2,
      terminal_no: t.terminal_no,
      currency_code: t.currency_code,
      transport: t.transport,
      host: t.host,
      port: t.port ? String(t.port) : '',
      com_port: t.com_port,
      psp: t.psp,
      bank_account_id: t.bank_account_id ?? '',
      analytic_id: t.analytic_id ?? '',
      is_default: t.is_default,
    })
    setMessage(null)
    setTestMsg(null)
  }
  function resetForm() {
    setForm(EMPTY)
    setEditingId(null)
    setMessage(null)
    setTestMsg(null)
  }

  async function toggleActive(t: PosTerminalRecord) {
    //: §۲۰ — دستگاهِ جمع‌آوری‌شده باید بتواند غیرفعال شود. تا امروز هیچ راهی در
    //: رابط نبود، در حالی که ستونِ وضعیت نمایش داده می‌شد.
    try {
      await updatePosTerminal(token, t.id, { is_active: !t.is_active })
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  function payload() {
    //: `is_active` عمداً اینجا نیست. PATCH حالا `exclude_unset` است، پس فیلدی که
    //: نفرستیم دست نمی‌خورد — و همین بود که دستگاهِ غیرفعال را بی‌صدا فعال می‌کرد.
    //: وضعیت فقط با دکمه‌ی صریحِ فعال/غیرفعال عوض می‌شود.
    return {
      label: form.label.trim(),
      name2: form.name2.trim(),
      terminal_no: form.terminal_no.trim(),
      currency_code: form.currency_code,
      transport: form.transport,
      host: form.host.trim(),
      port: Number(form.port) || 0,
      com_port: form.com_port.trim(),
      psp: form.psp.trim(),
      bank_account_id: form.bank_account_id || null,
      analytic_id: form.analytic_id || null,
      is_default: form.is_default,
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!form.bank_account_id) {
      setMessage('حسابِ بانکیِ تسویه را انتخاب کنید — رسیدِ پرداخت به معینِ همان می‌خورد.')
      return
    }
    setSaving(true)
    try {
      if (editingId) {
        await updatePosTerminal(token, editingId, payload())
        setMessage('کارتخوان ویرایش شد.')
      } else {
        await createPosTerminal(token, payload())
        setMessage('کارتخوان ثبت شد.')
      }
      resetForm()
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setSaving(false)
    }
  }

  async function remove(t: PosTerminalRecord) {
    if (!window.confirm(`دستگاهِ «${t.label || 'کارتخوان'}» حذف شود؟`)) return
    try {
      await deletePosTerminal(token, t.id)
      if (editingId === t.id) resetForm()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function testConnection() {
    setTestMsg(null)
    if (!window.cubita?.posTerminal) {
      setTestMsg('تستِ اتصال فقط در نسخه‌ی دسکتاپ ممکن است.')
      return
    }
    setTesting(true)
    try {
      const res = await window.cubita.posTerminal.status({
        transport: form.transport,
        host: form.host.trim() || undefined,
        port: Number(form.port) || undefined,
        comPort: form.com_port.trim() || undefined,
        psp: form.psp.trim() || undefined,
      })
      setTestMsg((res.online ? '✅ ' : '⛔ ') + (res.message || (res.online ? 'در دسترس' : 'در دسترس نیست')))
    } catch (err) {
      setTestMsg('⛔ ' + (err instanceof Error ? err.message : 'خطا در تستِ اتصال'))
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="page-block">
      {!desktop && (
        <div className="card-pay-note">
          <Monitor size={16} /> اتصال و پرداخت با کارتخوان فقط در «نسخه‌ی دسکتاپِ» کوبیتا انجام می‌شود؛ ولی همین‌جا در
          مرورگر می‌توانید دستگاه‌ها و حسابِ تسویه‌شان را تنظیم کنید تا در دسکتاپ آماده باشند.
        </div>
      )}
      <div className="workspace-split">
        <SectionCard
          icon={editingId ? Pencil : Plus}
          title={editingId ? 'ویرایش کارتخوان' : 'کارتخوانِ جدید'}
          description={
            editingId ? 'تنظیماتِ این دستگاه را به‌روزرسانی کنید.' : 'یک دستگاهِ کارتخوان و حسابِ تسویه‌اش را ثبت کنید.'
          }
          actions={
            editingId ? (
              <button onClick={resetForm}>
                <X size={13} /> انصراف
              </button>
            ) : undefined
          }
        >
          <form className="invoice-form form-full" onSubmit={handleSubmit}>
            <div className="field-row">
              <label>
                نامِ دستگاه
                <input
                  value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })}
                  placeholder="مثلاً کارتخوانِ شعبه مرکزی"
                />
              </label>
              <label>
                روشِ اتصال
                <SearchSelect
                  value={form.transport}
                  onChange={(e) => setForm({ ...form, transport: e.target.value as PosTransport })}
                >
                  {TRANSPORTS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </SearchSelect>
              </label>
            </div>

            {form.transport === 'network' && (
              <div className="field-row">
                <label>
                  آدرسِ دستگاه (IP یا host)
                  <input
                    value={form.host}
                    onChange={(e) => setForm({ ...form, host: e.target.value })}
                    className="ltr-cell"
                    placeholder="192.168.1.50"
                  />
                </label>
                <label>
                  پورت
                  <NumberInput value={form.port} onChange={(v) => setForm({ ...form, port: v })} placeholder="8888" />
                </label>
              </div>
            )}
            {form.transport === 'serial' && (
              <label>
                پورتِ COM
                {/* فهرست از خودِ سیستم می‌آید و نه تایپِ دستی: «COM3» را حدس‌زدن یعنی
                    خطایی که کاربر نمی‌فهمد از کجاست. در وب این پل وجود ندارد، پس
                    همان ورودیِ متنی می‌ماند. */}
                {serialPorts === null ? (
                  <input
                    value={form.com_port}
                    onChange={(e) => setForm({ ...form, com_port: e.target.value })}
                    className="ltr-cell"
                    placeholder="COM3"
                  />
                ) : (
                  <SearchSelect
                    value={form.com_port}
                    onChange={(e) => setForm({ ...form, com_port: e.target.value })}
                    className="ltr-cell"
                  >
                    <option value="">— انتخاب کنید —</option>
                    {serialPorts.map((p) => (
                      <option key={p.path} value={p.path}>{p.label}</option>
                    ))}
                    {/* پورتی که قبلاً ذخیره شده ولی الان وصل نیست، نباید بی‌صدا پاک شود. */}
                    {form.com_port && !serialPorts.some((p) => p.path === form.com_port) && (
                      <option value={form.com_port}>{form.com_port} (وصل نیست)</option>
                    )}
                  </SearchSelect>
                )}
                <span className="field-hint">
                  {serialPorts !== null && serialPorts.length === 0
                    ? 'هیچ درگاهِ سریالی پیدا نشد — درایورِ کارتخوان روی این رایانه نصب شده است؟'
                    : 'درگاهی که کارتخوان با آن دیده می‌شود.'}
                </span>
              </label>
            )}

            <div className="field-row">
              <FormField label="شماره پایانه" tip="شماره‌ای که خودِ دستگاه گزارش می‌کند — با شماره‌ی کارتِ بانکی یکی نیست.">
                {(id) => (
                  <input
                    id={id}
                    value={form.terminal_no}
                    onChange={(e) => setForm({ ...form, terminal_no: e.target.value })}
                    dir="ltr"
                    inputMode="numeric"
                  />
                )}
              </FormField>
              <label>
                عنوان دوم
                <input value={form.name2} onChange={(e) => setForm({ ...form, name2: e.target.value })} />
              </label>
            </div>

            <div className="field-row">
              <FormField label="ارز" tip="باید با ارزِ حسابِ تسویه یکی باشد.">
                {(id) => (
                  <SearchSelect
                    id={id}
                    value={form.currency_code}
                    onChange={(e) => setForm({ ...form, currency_code: e.target.value })}
                  >
                    {['IRR', 'USD', 'EUR', 'AED'].map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </SearchSelect>
                )}
              </FormField>
              <FormField
                label="حسابِ بانکیِ تسویه"
                tip="مقصدِ تسویه است، نه جایی که کارت‌کشی می‌نشیند: کارت‌کشی به «وجوهِ در راهِ کارت‌خوان» می‌رود و تسویه آن را به اینجا می‌آورد."
              >
                {(id) => (
                  <SearchSelect
                    id={id}
                    value={form.bank_account_id}
                    onChange={(e) => setForm({ ...form, bank_account_id: e.target.value })}
                  >
                    <option value="">— انتخاب —</option>
                    {bankAccounts.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                        {b.bank_name ? ` · ${b.bank_name}` : ''}
                      </option>
                    ))}
                  </SearchSelect>
                )}
              </FormField>
              <FormField
                label="تفصیلیِ وجوهِ در راه"
                tip="بدونِ تفصیلی، وجوهِ در راهِ این دستگاه از بقیه جدا نمی‌شود. دستگاهِ باسابقه تفصیلی‌اش عوض نمی‌شود."
              >
                {(id) => (
                  <SearchSelect
                    id={id}
                    value={form.analytic_id}
                    onChange={(e) => setForm({ ...form, analytic_id: e.target.value })}
                  >
                    <option value="">— بدونِ تفصیلی (فقط برای دستگاهِ اول) —</option>
                    {analytics.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.code} — {a.name}
                      </option>
                    ))}
                  </SearchSelect>
                )}
              </FormField>
              <label>
                شرکتِ پرداخت (اختیاری)
                <input
                  value={form.psp}
                  onChange={(e) => setForm({ ...form, psp: e.target.value })}
                  placeholder="مثلاً به‌پرداخت"
                />
              </label>
            </div>

            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              />
              دستگاهِ پیش‌فرض (در پرداخت‌ها خودکار انتخاب شود)
            </label>

            <div className="invoice-form-footer">
              <button type="button" className="btn-ghost" onClick={() => void testConnection()} disabled={testing}>
                <PlugZap size={14} /> تستِ اتصال
              </button>
              <button type="submit" className="btn-primary" disabled={saving}>
                <Save size={14} /> {editingId ? 'ذخیره' : 'ثبت دستگاه'}
              </button>
            </div>
            {testMsg && <div className="hint">{testMsg}</div>}
            {message && <div className="hint">{message}</div>}
          </form>
        </SectionCard>

        <SectionCard
          icon={CreditCard}
          title="کارتخوان‌ها"
          description={terminals ? `${terminals.length.toLocaleString('fa-IR')} دستگاه` : ''}
          actions={
            <button onClick={() => void refresh()}>
              <RefreshCw size={13} /> به‌روزرسانی
            </button>
          }
        >
          {error && <div className="error">{error}</div>}
          {terminals == null ? (
            <p className="muted">در حال بارگذاری…</p>
          ) : terminals.length === 0 ? (
            <EmptyState icon={CreditCard} text="هنوز کارتخوانی ثبت نشده." />
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table cards-on-mobile">
                  <thead>
                    <tr>
                      <th>شماره پایانه</th>
                      <th>دستگاه</th>
                      <th>حساب بانکی</th>
                      <th>کد تفصیلی</th>
                      <th>تسویه‌نشده</th>
                      <th>ارز</th>
                      <th>اتصال</th>
                      <th>وضعیت</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pg.pageItems.map((t) => {
                      return (
                        <tr key={t.id} className={t.is_active ? '' : 'acc-row--idle'}>
                          <td data-label="شماره پایانه" dir="ltr">
                            {t.terminal_no || '—'}
                          </td>
                          <td data-label="دستگاه" className="entity-name card-title">
                            {t.label || 'کارتخوان'}
                            {t.is_default && <span className="unit-suffix"> · پیش‌فرض</span>}
                            {t.name2 && <div className="entity-sub">{t.name2}</div>}
                          </td>
                          <td data-label="حساب بانکی">
                            {t.bank_account_name ?? '—'}
                            {t.bank_account_name2 && (
                              <div className="entity-sub">{t.bank_account_name2}</div>
                            )}
                          </td>
                          {/* بدونِ تفصیلی، وجوهِ در راهِ این دستگاه در دفتر از بقیه جدا نیست. */}
                          <td data-label="کد تفصیلی" dir="ltr">
                            {t.analytic_code ?? '—'}
                          </td>
                          <td data-label="تسویه‌نشده" className="num">
                            {faAmount(t.unsettled_balance)}
                          </td>
                          <td data-label="ارز" dir="ltr">
                            {t.currency_code}
                          </td>
                          <td data-label="اتصال">
                            {transportLabel(t.transport)}
                            {t.transport === 'network' && t.host ? (
                              <div className="entity-sub ltr-cell">
                                {t.host}:{t.port}
                              </div>
                            ) : null}
                          </td>
                          <td data-label="وضعیت">
                            <span className={`status-badge ${t.is_active ? 'tone-success' : 'tone-warning'}`}>
                              {t.is_active ? 'فعال' : 'غیرفعال'}
                            </span>
                          </td>
                          <td className="check-actions card-actions">
                            <button type="button" onClick={() => startEdit(t)}>
                              <Pencil size={13} /> ویرایش
                            </button>
                            <button type="button" onClick={() => void toggleActive(t)}>
                              {t.is_active ? 'غیرفعال' : 'فعال'}
                            </button>
                            <button type="button" className="icon-btn-danger" onClick={() => void remove(t)}>
                              <Trash2 size={13} /> حذف
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}
