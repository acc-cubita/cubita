import { useEffect, useState } from 'react'
import { createCheckDirect, fetchContacts, type ContactRecord } from '../api'
import { isElectron } from '../platform'
import { todayIso } from './jalali'

/** منطقِ مشترکِ «ثبت چک» (دریافتنی/پرداختنی) — مصرف‌شده در فرمِ کلاسیک و ویزارد. */
export function useCheckDraft({ token, onQueued }: { token: string; onQueued: () => void }) {
  const [type, setType] = useState<'receivable' | 'payable'>('receivable')
  const [contactId, setContactId] = useState('')
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [number, setNumber] = useState('')
  const [bankName, setBankName] = useState('')
  const [amount, setAmount] = useState('')
  const [issueDate, setIssueDate] = useState(todayIso())
  const [dueDate, setDueDate] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // طرف‌حساب‌ها زنده خوانده می‌شوند تا چک به شخص وصل شود؛ بدونِ این وصل، سندِ حسابداری
  // حسابِ کنترلِ دریافتنی/پرداختنی را جابه‌جا می‌کند ولی مانده‌ی خودِ شخص تکان نمی‌خورد.
  useEffect(() => {
    fetchContacts(token)
      .then(setContacts)
      .catch(() => setContacts([]))
  }, [token])

  // چکِ دریافتنی به مشتری مربوط است و پرداختنی به تأمین‌کننده؛ «هردو» در هر دو دیده می‌شود.
  const wanted = type === 'receivable' ? 'customer' : 'supplier'
  const contactOptions = contacts.filter((c) => c.type === wanted || c.type === 'both')

  /** با تغییرِ نوعِ چک، فهرستِ طرف‌حساب عوض می‌شود؛ انتخابِ قبلی باید پاک شود. */
  function changeType(next: 'receivable' | 'payable') {
    setType(next)
    setContactId('')
  }

  const valid = !!number && Number(amount) > 0 && !!dueDate

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!valid) {
      setMessage('شماره چک، مبلغ (بزرگ‌تر از صفر) و تاریخ سررسید الزامی است.')
      return false
    }
    const payload = {
      type,
      number,
      bank_name: bankName,
      amount: Number(amount),
      issue_date: issueDate,
      due_date: dueDate,
      description,
      contact_id: contactId || null,
    }
    setSubmitting(true)
    try {
      if (isElectron) {
        await window.cubita.queueCheck(payload)
        setMessage('چک در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.')
      } else {
        await createCheckDirect(token, payload)
        setMessage('چک با موفقیت ثبت شد.')
      }
      setNumber('')
      setBankName('')
      setAmount('')
      setDueDate('')
      setDescription('')
      setContactId('')
      onQueued()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    type,
    changeType,
    contactId,
    setContactId,
    contactOptions,
    number,
    setNumber,
    bankName,
    setBankName,
    amount,
    setAmount,
    issueDate,
    setIssueDate,
    dueDate,
    setDueDate,
    description,
    setDescription,
    message,
    submitting,
    valid,
    submit,
  }
}

export type CheckDraft = ReturnType<typeof useCheckDraft>
