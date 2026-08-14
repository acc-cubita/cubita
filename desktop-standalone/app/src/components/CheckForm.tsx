import { useEffect, useState } from 'react'
import { Receipt, Save } from 'lucide-react'
import { createCheckDirect, fetchContacts, type ContactRecord } from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'

export function CheckForm({ token, onQueued }: { token: string; onQueued: () => void }) {
  const [type, setType] = useState<'receivable' | 'payable'>('receivable')
  const [contactId, setContactId] = useState('')
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [number, setNumber] = useState('')
  const [bankName, setBankName] = useState('')
  const [amount, setAmount] = useState('')
  const [issueDate, setIssueDate] = useState(new Date().toISOString().slice(0, 10))
  const [dueDate, setDueDate] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState<string | null>(null)

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)

    if (!number || Number(amount) <= 0 || !dueDate) {
      setMessage('شماره چک، مبلغ (بزرگ‌تر از صفر) و تاریخ سررسید الزامی است.')
      return
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

    try {
      await createCheckDirect(token, payload)
      setMessage('چک با موفقیت ثبت شد.')
      setNumber('')
      setBankName('')
      setAmount('')
      setDueDate('')
      setDescription('')
      setContactId('')
      onQueued()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard icon={Receipt} title="ثبت چک دریافتنی/پرداختنی">
      <form className="invoice-form" onSubmit={handleSubmit}>
        <label>
          نوع چک
          <select
            value={type}
            onChange={(e) => {
              setType(e.target.value as 'receivable' | 'payable')
              setContactId('') // با تغییرِ نوع، فهرستِ طرف‌حساب عوض می‌شود
            }}
          >
            <option value="receivable">دریافتنی (از مشتری)</option>
            <option value="payable">پرداختنی (به تأمین‌کننده)</option>
          </select>
        </label>
        <label>
          {type === 'receivable' ? 'مشتری' : 'تأمین‌کننده'}
          <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
            <option value="">— بدون طرف‌حساب —</option>
            {contactOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          شماره چک
          <input type="text" value={number} onChange={(e) => setNumber(e.target.value)} required />
        </label>
        <label>
          نام بانک
          <input type="text" value={bankName} onChange={(e) => setBankName(e.target.value)} />
        </label>
        <label>
          مبلغ
          <NumberInput value={amount} onChange={setAmount} required />
        </label>
        <label>
          تاریخ صدور
          <JalaliDatePicker value={issueDate} onChange={setIssueDate} />
        </label>
        <label>
          تاریخ سررسید
          <JalaliDatePicker value={dueDate} onChange={setDueDate} />
        </label>
        <label>
          توضیحات
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary">
            <Save size={14} /> ثبت چک
          </button>
        </div>
        {message && <div className="hint">{message}</div>}
      </form>
    </SectionCard>
  )
}
