import { useCallback, useEffect, useState } from 'react'
import { CreditCard, Save, Pencil, X, RefreshCw, Plus, Trash2, PlugZap, Monitor } from 'lucide-react'
import {
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

interface Draft {
  label: string
  transport: PosTransport
  host: string
  port: string
  com_port: string
  psp: string
  bank_account_id: string
  is_default: boolean
}
const EMPTY: Draft = {
  label: '',
  transport: 'simulator',
  host: '',
  port: '',
  com_port: '',
  psp: '',
  bank_account_id: '',
  is_default: false,
}

const TRANSPORTS: { value: PosTransport; label: string }[] = [
  { value: 'simulator', label: 'شبیه‌ساز (بدونِ دستگاه)' },
  { value: 'network', label: 'تحت شبکه (IP:Port)' },
  { value: 'serial', label: 'USB / سریال (COM)' },
  { value: 'sdk', label: 'SDK اختصاصیِ PSP' },
]
const transportLabel = (t: PosTransport) => TRANSPORTS.find((x) => x.value === t)?.label ?? t

/**
 * مدیریتِ دستگاه‌های کارتخوان — ساخت/ویرایش/حذف، انتخابِ حسابِ بانکیِ تسویه، و «تستِ
 * اتصال». پیکربندی سرور-ساید است و در هر دو نسخه (وب/دسکتاپ) دیده می‌شود؛ ولی خودِ
 * اتصال به سخت‌افزار (تست/پرداخت) فقط در دسکتاپ رخ می‌دهد.
 */
export function PosTerminalsPanel({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const desktop = typeof window !== 'undefined' && !!window.cubita?.posTerminal
  const [terminals, setTerminals] = useState<PosTerminalRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [form, setForm] = useState<Draft>(EMPTY)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testMsg, setTestMsg] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setTerminals(await fetchPosTerminals(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // صفحه‌بندیِ کارتخوان‌ها (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(terminals ?? [], 10)

  function startEdit(t: PosTerminalRecord) {
    setEditingId(t.id)
    setForm({
      label: t.label,
      transport: t.transport,
      host: t.host,
      port: t.port ? String(t.port) : '',
      com_port: t.com_port,
      psp: t.psp,
      bank_account_id: t.bank_account_id ?? '',
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

  function payload() {
    return {
      label: form.label.trim(),
      transport: form.transport,
      host: form.host.trim(),
      port: Number(form.port) || 0,
      com_port: form.com_port.trim(),
      psp: form.psp.trim(),
      bank_account_id: form.bank_account_id || null,
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
                  placeholder="مثلاً صندوقِ ۱"
                />
              </label>
              <label>
                روشِ اتصال
                <select
                  value={form.transport}
                  onChange={(e) => setForm({ ...form, transport: e.target.value as PosTransport })}
                >
                  {TRANSPORTS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
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
                <input
                  value={form.com_port}
                  onChange={(e) => setForm({ ...form, com_port: e.target.value })}
                  className="ltr-cell"
                  placeholder="COM3"
                />
              </label>
            )}

            <div className="field-row">
              <label>
                حسابِ بانکیِ تسویه
                <select
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
                </select>
              </label>
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
              <table className="entity-table">
                <thead>
                  <tr>
                    <th>دستگاه</th>
                    <th>اتصال</th>
                    <th>وضعیت</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((t) => {
                    const bank = bankAccounts.find((b) => b.id === t.bank_account_id)
                    return (
                      <tr key={t.id}>
                        <td data-label="دستگاه" className="entity-name">
                          {t.label || 'کارتخوان'}
                          {t.is_default && <span className="unit-suffix"> · پیش‌فرض</span>}
                          {bank && <div className="entity-sub">تسویه: {bank.name}</div>}
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
                        <td className="check-actions">
                          <button type="button" onClick={() => startEdit(t)}>
                            <Pencil size={13} /> ویرایش
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
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}
