import { useEffect, useState } from 'react'
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

export const MOADIAN_STATUS_LABEL: Record<string, string> = {
  pending: 'در انتظار',
  sent: 'ارسال‌شده',
  confirmed: 'تأییدشده',
  rejected: 'ردشده',
  failed: 'خطا',
}

export const MOADIAN_STATUS_TONE: Record<string, string> = {
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

/**
 * منطقِ مشترکِ پنلِ «سامانه مؤدیان» — تنظیماتِ اعتبارنامه، تستِ اتصال، ارسالِ صورتحساب و
 * تاریخچه. هم پنلِ کلاسیک ([MoadianPanel]) و هم ویزاردِ نسخه‌ی جدید ([MoadianWizard]) از
 * این یک منبع می‌خوانند.
 */
export function useMoadianPanel({ token }: { token: string }) {
  const [settings, setSettings] = useState<MoadianSettingsRecord | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [submissions, setSubmissions] = useState<MoadianSubmissionRecord[]>([])
  const [invoices, setInvoices] = useState<SalesInvoiceRecord[]>([])
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [sendMsg, setSendMsg] = useState<string | null>(null)
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [sending, setSending] = useState(false)

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function save(): Promise<boolean> {
    setMsg(null)
    setSaving(true)
    try {
      await updateMoadianSettings(token, form)
      setMsg('تنظیمات ذخیره شد.')
      await refresh()
      return true
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSaving(false)
    }
  }

  async function testConnection() {
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

  async function inquire(id: string) {
    setSendMsg(null)
    try {
      const res = await inquireMoadianStatus(token, id)
      setSendMsg(`وضعیت به‌روز شد: ${MOADIAN_STATUS_LABEL[res.status] ?? res.status}${res.error_message ? ` — ${res.error_message}` : ''}`)
      await refresh()
    } catch (err) {
      setSendMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function submitInvoice(): Promise<boolean> {
    setSendMsg(null)
    if (!selectedInvoiceId) {
      setSendMsg('ابتدا یک فاکتور انتخاب کنید.')
      return false
    }
    setSending(true)
    try {
      const res = await submitInvoiceToMoadian(token, selectedInvoiceId)
      setSendMsg(
        res.status === 'sent' || res.status === 'confirmed'
          ? `ارسال شد — شناسه مالیاتی ${res.tax_id}${res.reference_number ? `، مرجع ${res.reference_number}` : ''}`
          : `وضعیت: ${MOADIAN_STATUS_LABEL[res.status] ?? res.status}${res.error_message ? ` — ${res.error_message}` : ''}`,
      )
      setSelectedInvoiceId('')
      await refresh()
      return true
    } catch (err) {
      setSendMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSending(false)
    }
  }

  const sentCount = submissions.filter((s) => s.status === 'sent' || s.status === 'confirmed').length
  const failedCount = submissions.filter((s) => s.status === 'rejected' || s.status === 'failed').length
  const submittedIds = new Set(
    submissions.filter((s) => s.status === 'sent' || s.status === 'confirmed').map((s) => s.sales_invoice_id),
  )
  const pendingInvoices = invoices.filter((i) => !submittedIds.has(i.id))

  return {
    settings,
    form,
    setForm,
    submissions,
    selectedInvoiceId,
    setSelectedInvoiceId,
    msg,
    sendMsg,
    testMsg,
    testing,
    saving,
    sending,
    refresh,
    save,
    testConnection,
    inquire,
    submitInvoice,
    sentCount,
    failedCount,
    pendingInvoices,
  }
}

export type MoadianPanelState = ReturnType<typeof useMoadianPanel>
