import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchMoadianPending,
  fetchMoadianReadiness,
  fetchMoadianSettings,
  fetchMoadianSubmissions,
  inquireMoadianStatus,
  submitMoadianBatch,
  testMoadianConnection,
  updateMoadianSettings,
  type MoadianBatchResult,
  type MoadianPendingInvoice,
  type MoadianReadiness,
  type MoadianSettingsRecord,
  type MoadianSubmissionRecord,
} from '../api'

export const MOADIAN_STATUS_LABEL: Record<string, string> = {
  pending: 'در انتظار',
  sent: 'ارسال‌شده',
  confirmed: 'تأییدشده',
  rejected: 'ردشده',
  failed: 'خطا',
  skipped: 'ارسال نشد',
}

export const MOADIAN_STATUS_TONE: Record<string, string> = {
  pending: 'tone-warning',
  sent: 'tone-success',
  confirmed: 'tone-success',
  rejected: 'tone-danger',
  failed: 'tone-danger',
  skipped: 'tone-warning',
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
 * داده و کنش‌های ماژولِ «سامانه مؤدیان» — یک منبع برای هر چهار بخشِ صفحه.
 *
 * **چرا صف و چک‌لیست از سرور می‌آیند و اینجا محاسبه نمی‌شوند:** شرطِ ارسال (کلیدِ
 * خواندنی، گواهی، کدِ ۱۳رقمیِ کالا، فعال‌بودن) در سرویسِ ارسال زندگی می‌کند. اگر
 * فرانت همان قاعده را دوباره می‌نوشت، دو نسخه‌ی جدا از «آماده است» می‌داشتیم که
 * دیر یا زود از هم فاصله می‌گرفتند — و بدترین حالتش این است که رابط «آماده» بگوید
 * و ارسال شکست بخورد، آن هم بعد از مصرفِ سریال.
 */
export function useMoadianPanel({ token }: { token: string }) {
  const [settings, setSettings] = useState<MoadianSettingsRecord | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [submissions, setSubmissions] = useState<MoadianSubmissionRecord[]>([])
  const [pending, setPending] = useState<MoadianPendingInvoice[]>([])
  const [readiness, setReadiness] = useState<MoadianReadiness | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchResults, setBatchResults] = useState<MoadianBatchResult[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<string | null>(null)
  const [sendMsg, setSendMsg] = useState<string | null>(null)
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [sending, setSending] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [s, subs, queue, ready] = await Promise.all([
        fetchMoadianSettings(token),
        fetchMoadianSubmissions(token),
        fetchMoadianPending(token),
        fetchMoadianReadiness(token),
      ])
      setSettings(s)
      setSubmissions(subs)
      setPending(queue)
      setReadiness(ready)
      // انتخاب‌هایی که دیگر در صف نیستند (ارسال شدند) پاک می‌شوند.
      setSelected((prev) => new Set([...prev].filter((id) => queue.some((r) => r.id === id))))
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
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

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
      setSendMsg(
        `وضعیت به‌روز شد: ${MOADIAN_STATUS_LABEL[res.status] ?? res.status}${res.error_message ? ` — ${res.error_message}` : ''}`,
      )
      await refresh()
    } catch (err) {
      setSendMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const sendable = useMemo(() => pending.filter((r) => !r.blocked_reason), [pending])

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  /** انتخاب/لغوِ همه‌ی ردیف‌های *قابلِ ارسال*؛ ردیفِ مسدود هرگز انتخاب نمی‌شود. */
  function toggleAll() {
    setSelected((prev) => (prev.size >= sendable.length ? new Set() : new Set(sendable.map((r) => r.id))))
  }

  /** ارسالِ انتخاب‌شده‌ها در یک درخواست؛ نتیجه‌ی هر فاکتور جدا برمی‌گردد. */
  async function submitSelected(): Promise<boolean> {
    const ids = sendable.filter((r) => selected.has(r.id)).map((r) => r.id)
    setSendMsg(null)
    setBatchResults(null)
    if (ids.length === 0) {
      setSendMsg('هیچ فاکتورِ قابلِ ارسالی انتخاب نشده است.')
      return false
    }
    setSending(true)
    try {
      const results = await submitMoadianBatch(token, ids)
      setBatchResults(results)
      const ok = results.filter((r) => r.ok).length
      setSendMsg(
        ok === results.length
          ? `${results.length} فاکتور با موفقیت ارسال شد.`
          : `${ok} از ${results.length} فاکتور ارسال شد؛ جزئیاتِ بقیه پایین آمده.`,
      )
      await refresh()
      return ok > 0
    } catch (err) {
      setSendMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSending(false)
    }
  }

  const sentCount = submissions.filter((s) => s.status === 'sent' || s.status === 'confirmed').length
  const failedCount = submissions.filter((s) => s.status === 'rejected' || s.status === 'failed').length

  return {
    settings,
    form,
    setForm,
    submissions,
    pending,
    sendable,
    readiness,
    selected,
    toggle,
    toggleAll,
    batchResults,
    loading,
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
    submitSelected,
    sentCount,
    failedCount,
  }
}

export type MoadianPanelState = ReturnType<typeof useMoadianPanel>
