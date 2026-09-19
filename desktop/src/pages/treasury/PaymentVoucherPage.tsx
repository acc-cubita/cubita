import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpFromLine, Ban, Banknote, Landmark, Plus, Save, Trash2, Wallet } from 'lucide-react'
import {
  createPaymentDocument,
  fetchAccountsLive,
  fetchBankAccountsLive,
  fetchCashboxes,
  fetchCheckbooks,
  fetchContacts,
  fetchCurrencies,
  fetchEligibleReceivedCheques,
  fetchLatestRate,
  fetchNextCheckNumber,
  fetchPaymentDocuments,
  openPaymentPrintView,
  voidPaymentDocument,
  newIdempotencyKey,
  type ContactRecord,
  type PaymentBankWithdrawalIn,
  type PaymentCashIn,
  type PaymentPayableChequeIn,
  isPayableParty,
  isReceivableParty,
} from '../../api'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { NumberInput } from '../../components/NumberInput'
import { Pager, usePagination } from '../../components/Pager'
import { SectionCard } from '../../components/SectionCard'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { formatJalali, todayIso } from '../../lib/jalali'
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'
import { SearchSelect } from '../../components/SearchSelect'

type PaymentType = 'supplier' | 'customer' | 'other'
type Instrument = 'cash' | 'bank' | 'payable_cheque' | 'endorsed_cheque'

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

export function PaymentVoucherDocumentPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [journalEntryId, setJournalEntryId] = useState<string | null>(null)
  const requestKey = useRef(newIdempotencyKey())

  const [paymentType, setPaymentType] = useState<PaymentType>('supplier')
  const [contactId, setContactId] = useState('')
  const [date, setDate] = useState(todayIso())
  const [currency, setCurrency] = useState('IRR')
  const [rate, setRate] = useState('1')
  const [counterpartyAccountId, setCounterpartyAccountId] = useState('')
  const [feeAccountId, setFeeAccountId] = useState('')
  const [discountAccountId, setDiscountAccountId] = useState('')
  const [discount, setDiscount] = useState('')
  const [description, setDescription] = useState('')
  const [description2, setDescription2] = useState('')
  const [establishment, setEstablishment] = useState('')

  const [instrument, setInstrument] = useState<Instrument>('cash')
  const [lineAmount, setLineAmount] = useState('')
  const [cashboxId, setCashboxId] = useState('')
  const [bankAccountId, setBankAccountId] = useState('')
  const [withdrawalNo, setWithdrawalNo] = useState('')
  const [bankFee, setBankFee] = useState('')
  const [checkbookId, setCheckbookId] = useState('')
  const [checkNo, setCheckNo] = useState('')
  const [dueDate, setDueDate] = useState(todayIso())
  const [sayadId, setSayadId] = useState('')
  const [endorsedId, setEndorsedId] = useState('')
  const [lineDescription, setLineDescription] = useState('')
  const [relatedPurchaseId, setRelatedPurchaseId] = useState('')
  //: نوعِ سندِ مرتبط — فاکتور خرید یا رسید انبار (§۳۸). فقط مرجع است، نه تخصیص.
  const [relatedDocType, setRelatedDocType] = useState('purchase_invoice')
  //: «جمع مبلغ رسید انبار» پایینِ فرم — برای دیدن، نه قیدِ مبلغ (§۴۰).
  const [referenceNote, setReferenceNote] = useState('')

  const [cash, setCash] = useState<PaymentCashIn[]>([])
  const [withdrawals, setWithdrawals] = useState<PaymentBankWithdrawalIn[]>([])
  const [payableCheques, setPayableCheques] = useState<PaymentPayableChequeIn[]>([])
  const [endorsedCheques, setEndorsedCheques] = useState<{ check_id: string }[]>([])

  useEffect(() => {
    const raw = sessionStorage.getItem('cubita.payment.prefill')
    if (!raw) return
    sessionStorage.removeItem('cubita.payment.prefill')
    try {
      const prefill = JSON.parse(raw) as {
        contactId?: string; documentId?: string; documentType?: string; description?: string
        amount?: string; referenceTotal?: string; referenceLabel?: string
        currency?: string; rate?: string; number?: number | null
      }
      const fxRate = Math.max(Number(prefill.rate ?? 1), 1)
      setPaymentType('supplier')
      setContactId(prefill.contactId ?? '')
      setRelatedPurchaseId(prefill.documentId ?? '')
      setRelatedDocType(prefill.documentType ?? 'purchase_invoice')
      setCurrency(prefill.currency ?? 'IRR')
      setRate(String(fxRate))
      setLineAmount(String(Math.round(Number(prefill.amount ?? 0) / fxRate)))
      setDescription(prefill.description ?? `بابت فاکتور خرید شماره ${prefill.number ?? ''}`)
      if (prefill.referenceTotal) {
        setReferenceNote(
          `${prefill.referenceLabel ?? 'جمع مبلغ سند مرتبط'}: ${Math.round(Number(prefill.referenceTotal)).toLocaleString('fa-IR')} ریال — مبلغ پیشنهادی قابلِ تغییر است و می‌توانید بخش‌بخش پرداخت کنید.`,
        )
      }
    } catch {
      // پیش‌پرکنی کمکی است؛ خرابی داده‌ی نشست نباید فرم پرداخت را از کار بیندازد.
    }
  }, [])

  const data = useAsync(async () => {
    const [contacts, banks, boxes, books, cheques, accounts, currencies, recent] = await Promise.all([
      fetchContacts(token), fetchBankAccountsLive(token), fetchCashboxes(token, false),
      fetchCheckbooks(token), fetchEligibleReceivedCheques(token), fetchAccountsLive(token),
      fetchCurrencies(token), fetchPaymentDocuments(token),
    ])
    return { contacts, banks, boxes, books, cheques, accounts, currencies, recent }
  }, [token, reloadKey])

  const contacts = useMemo(() => {
    const all: ContactRecord[] = data.data?.contacts ?? []
    if (paymentType === 'other') return all
    //: «تأمین‌کننده» این‌جا یعنی *هرکه پولی از ما می‌گیرد* — تأمین‌کننده، واسطه،
    //: سهامدار یا کارمند. تا پیش از مهاجرتِ ۰۱۶۴ هر چهارتا `type='supplier'`
    //: بودند و این فیلتر اتفاقی درست کار می‌کرد؛ حالا صریح است. **بدونِ این،
    //: بک‌اند پرداخت به واسطه را می‌پذیرد ولی رابط اجازه‌ی انتخابش را نمی‌دهد.**
    if (paymentType === 'supplier') return all.filter(isPayableParty)
    return all.filter(isReceivableParty)
  }, [data.data, paymentType])
  const accounts = (data.data?.accounts ?? []).filter((account) => !account.is_group)
  const books = (data.data?.books ?? []).filter((book) => book.is_active && book.remaining_count > 0)
  const currencyBanks = (data.data?.banks ?? []).filter((bank) => bank.currency_code === currency)
  const currencyBoxes = (data.data?.boxes ?? []).filter((box) => box.currency_code === currency)
  const selectedEndorsed = new Set(endorsedCheques.map((row) => row.check_id))
  const eligibleCheques = (data.data?.cheques ?? []).filter((row) => !selectedEndorsed.has(row.id))
  const recent = (data.data?.recent ?? []).slice(0, 20)
  const pg = usePagination(recent, 8)

  const principal = cash.reduce((sum, row) => sum + Number(row.amount), 0)
    + withdrawals.reduce((sum, row) => sum + Number(row.amount), 0)
    + payableCheques.reduce((sum, row) => sum + Number(row.amount), 0)
    + endorsedCheques.reduce((sum, row) => {
      const cheque = data.data?.cheques.find((item) => item.id === row.check_id)
      return sum + Number(cheque?.amount ?? 0) / Math.max(Number(rate || 1), 1)
    }, 0)
  const feeTotal = withdrawals.reduce((sum, row) => sum + Number(row.bank_fee ?? 0), 0)

  function clearLine() {
    setLineAmount('')
    setWithdrawalNo('')
    setBankFee('')
    setCheckNo('')
    setSayadId('')
    setEndorsedId('')
    setLineDescription('')
  }

  async function chooseBook(id: string) {
    setCheckbookId(id)
    if (!id) return
    const book = books.find((row) => row.id === id)
    if (book) setBankAccountId(book.bank_account_id)
    try {
      const next = await fetchNextCheckNumber(token, id)
      setCheckNo(next.number)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function chooseCurrency(code: string) {
    setCurrency(code)
    setCashboxId('')
    setBankAccountId('')
    setCheckbookId('')
    if (code === 'IRR') {
      setRate('1')
      return
    }
    try {
      const latest = await fetchLatestRate(token, code)
      if (latest.rate) setRate(latest.rate)
      else setMsg({ text: `برای ارز ${code} تا امروز نرخی ثبت نشده است.`, kind: 'err' })
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  function addInstrument() {
    setMsg(null)
    const amount = Number(lineAmount || 0)
    if (instrument !== 'endorsed_cheque' && amount <= 0) {
      setMsg({ text: 'مبلغ جزء باید بزرگ‌تر از صفر باشد.', kind: 'err' })
      return
    }
    if (instrument === 'cash') {
      if (currency !== 'IRR' && !cashboxId) return setMsg({ text: 'برای ارز خارجی صندوق همان ارز را انتخاب کنید.', kind: 'err' })
      setCash((rows) => [...rows, { cashbox_id: cashboxId || null, amount, description: lineDescription }])
    } else if (instrument === 'bank') {
      if (!bankAccountId) return setMsg({ text: 'حساب بانکی را انتخاب کنید.', kind: 'err' })
      setWithdrawals((rows) => [...rows, {
        bank_account_id: bankAccountId, amount, bank_fee: Number(bankFee || 0), number: withdrawalNo,
        withdrawal_date: date, description: lineDescription,
      }])
    } else if (instrument === 'payable_cheque') {
      if (!checkNo || !dueDate || !bankAccountId) return setMsg({ text: 'حساب بانکی، شماره و سررسید چک لازم است.', kind: 'err' })
      setPayableCheques((rows) => [...rows, {
        checkbook_id: checkbookId || null, bank_account_id: bankAccountId, number: checkNo, amount, due_date: dueDate,
        sayad_id: sayadId, description: lineDescription,
      }])
    } else {
      if (!endorsedId) return setMsg({ text: 'چک دریافتنی را انتخاب کنید.', kind: 'err' })
      setEndorsedCheques((rows) => [...rows, { check_id: endorsedId }])
    }
    clearLine()
  }

  function remove(kind: Instrument, index: number) {
    if (kind === 'cash') setCash((rows) => rows.filter((_, i) => i !== index))
    if (kind === 'bank') setWithdrawals((rows) => rows.filter((_, i) => i !== index))
    if (kind === 'payable_cheque') setPayableCheques((rows) => rows.filter((_, i) => i !== index))
    if (kind === 'endorsed_cheque') setEndorsedCheques((rows) => rows.filter((_, i) => i !== index))
  }

  /** اعلامیه ویرایش نمی‌شود؛ باطل می‌شود و سندِ معکوس می‌خورد.
   *
   *  تا امروز `voidPaymentDocument` در api بود ولی هیچ دکمه‌ای صدایش نمی‌زد —
   *  یعنی ابطال فقط از API ممکن بود، و ردیفِ `acc-row--void` هرگز دیده نمی‌شد.
   */
  async function voidRow(id: string, number: number) {
    const reason = window.prompt(`ابطالِ اعلامیه شماره ${faInt(number)} — دلیل را بنویسید:`)
    if (reason === null) return
    if (!reason.trim()) {
      setMsg({ text: 'برای ابطال باید دلیلی بنویسید.', kind: 'err' })
      return
    }
    try {
      await voidPaymentDocument(token, id, reason.trim())
      setMsg({ text: `اعلامیه شماره ${faInt(number)} باطل شد و سندِ معکوسش ثبت شد.`, kind: 'ok' })
      setReloadKey((key) => key + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setMsg(null)
    if (!contactId) return setMsg({ text: 'طرف حساب را انتخاب کنید.', kind: 'err' })
    if (principal <= 0) return setMsg({ text: 'دست‌کم یک قلم پرداخت اضافه کنید.', kind: 'err' })
    if (Number(discount || 0) > 0 && !discountAccountId) {
      return setMsg({ text: 'برای تخفیف، حساب تخفیف را انتخاب کنید.', kind: 'err' })
    }
    setBusy(true)
    try {
      await createPaymentDocument(token, {
        payment_type: paymentType, contact_id: contactId, payment_date: date,
        counterparty_account_id: counterpartyAccountId || null,
        bank_fee_account_id: feeAccountId || null,
        discount_account_id: discountAccountId || null,
        currency_code: currency, exchange_rate: Number(rate || 1), discount_amount: Number(discount || 0),
        description, description2, establishment, cash, bank_withdrawals: withdrawals,
        payable_cheques: payableCheques, endorsed_cheques: endorsedCheques,
        related_documents: relatedPurchaseId ? [{
          document_type: relatedDocType, document_id: relatedPurchaseId,
          // این فقط Reference است؛ تخصیص مبلغ تصمیمِ موتور Settlement است.
          allocated_amount: 0,
        }] : [],
      }, requestKey.current)
      setMsg({ text: 'اعلامیه‌ی پرداخت و سند متوازن آن ثبت شد.', kind: 'ok' })
      requestKey.current = newIdempotencyKey()
      setCash([]); setWithdrawals([]); setPayableCheques([]); setEndorsedCheques([])
      setDiscount(''); setDescription(''); setDescription2('')
      setRelatedPurchaseId('')
      setRelatedDocType('purchase_invoice')
      setReferenceNote('')
      setReloadKey((key) => key + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const instrumentRows = [
    ...cash.map((row, index) => ({ kind: 'cash' as const, index, label: 'نقد', detail: data.data?.boxes.find((b) => b.id === row.cashbox_id)?.name ?? 'صندوق پیش‌فرض', amount: row.amount, fee: 0 })),
    ...withdrawals.map((row, index) => ({ kind: 'bank' as const, index, label: 'برداشت بانکی', detail: data.data?.banks.find((b) => b.id === row.bank_account_id)?.name ?? 'بانک', amount: row.amount, fee: row.bank_fee ?? 0 })),
    ...payableCheques.map((row, index) => ({ kind: 'payable_cheque' as const, index, label: 'چک پرداختنی', detail: `شماره ${row.number}`, amount: row.amount, fee: 0 })),
    ...endorsedCheques.map((row, index) => { const ch = data.data?.cheques.find((c) => c.id === row.check_id); return { kind: 'endorsed_cheque' as const, index, label: 'خرج کردن چک', detail: `شماره ${ch?.number ?? '—'}`, amount: Number(ch?.amount ?? 0) / Math.max(Number(rate || 1), 1), fee: 0 } }),
  ]

  return (
    <OpsPage
      icon={ArrowUpFromLine}
      title="اعلامیه پرداخت"
      description="یک پرداخت با چند ابزار؛ نقد، برداشت بانکی، چک پرداختنی و خرج کردن چک دریافتنی."
      head={<div className="cc-head"><div className="cc-summary">
        <Metric icon={<Banknote size={14} />} label="مبلغ پرداخت" value={fa(principal)} tone="out" />
        <Metric icon={<Landmark size={14} />} label="کارمزد بانکی" value={fa(feeTotal)} />
        <Metric icon={<Wallet size={14} />} label="جمع تسویه" value={fa(principal + Number(discount || 0))} />
      </div></div>}
    >
      <Note msg={msg} />
      {referenceNote && <p className="hint">{referenceNote}</p>}
      <form className="invoice-form form-full" onSubmit={submit}>
        <SectionCard icon={Banknote} title="سربرگ اعلامیه" description="نوع، طرف حساب، ارز و حساب‌های تنظیم‌شده">
          <div className="invoice-form form-full">
            <label>نوع پرداخت<SearchSelect value={paymentType} onChange={(e) => { setPaymentType(e.target.value as PaymentType); setContactId('') }}>
              <option value="supplier">پرداخت به تأمین‌کننده</option><option value="customer">پرداخت به مشتری</option><option value="other">سایر پرداخت‌ها</option>
            </SearchSelect></label>
            <label>طرف حساب<SearchSelect value={contactId} onChange={(e) => setContactId(e.target.value)} required><option value="">— انتخاب —</option>{contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</SearchSelect></label>
            <label>تاریخ<JalaliDatePicker value={date} onChange={setDate} /></label>
            <label>ارز<SearchSelect value={currency} onChange={(e) => void chooseCurrency(e.target.value)}><option value="IRR">ریال (IRR)</option>{(data.data?.currencies ?? []).map((item) => <option key={item.id} value={item.code}>{item.name} ({item.code})</option>)}</SearchSelect></label>
            <label>نرخ به ارز پایه<NumberInput value={rate} onChange={setRate} /></label>
            <label>حساب معین<SearchSelect value={counterpartyAccountId} onChange={(e) => setCounterpartyAccountId(e.target.value)}><option value="">خودکار از نوع پرداخت</option>{accounts.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</SearchSelect></label>
            <label>حساب کارمزد بانکی<SearchSelect value={feeAccountId} onChange={(e) => setFeeAccountId(e.target.value)}><option value="">خودکار از تنظیمات حسابداری</option>{accounts.filter((a) => a.type === 'expense').map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</SearchSelect></label>
            <label>تخفیف<NumberInput value={discount} onChange={setDiscount} /></label>
            {Number(discount || 0) > 0 && <label>حساب تخفیف<SearchSelect value={discountAccountId} onChange={(e) => setDiscountAccountId(e.target.value)} required><option value="">— انتخاب —</option>{accounts.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</SearchSelect></label>}
            <label>استقرار<input value={establishment} onChange={(e) => setEstablishment(e.target.value)} /></label>
            <label className="form-wide">شرح<input value={description} onChange={(e) => setDescription(e.target.value)} required /></label>
            <label className="form-wide">شرح دوم<input value={description2} onChange={(e) => setDescription2(e.target.value)} required /></label>
          </div>
        </SectionCard>

        <SectionCard icon={Wallet} title="اقلام پرداخت" description="هر ابزار را جدا اضافه کنید؛ جمع از همین اقلام مشتق می‌شود.">
          <div className="invoice-form form-full">
            <label>ابزار<SearchSelect value={instrument} onChange={(e) => setInstrument(e.target.value as Instrument)}><option value="cash">نقد</option><option value="bank">برداشت بانکی</option><option value="payable_cheque">چک پرداختنی جدید</option><option value="endorsed_cheque">خرج کردن چک دریافتنی</option></SearchSelect></label>
            {instrument !== 'endorsed_cheque' && <label>مبلغ<NumberInput value={lineAmount} onChange={setLineAmount} /></label>}
            {instrument === 'cash' && <label>صندوق<SearchSelect value={cashboxId} onChange={(e) => setCashboxId(e.target.value)}><option value="">صندوق پیش‌فرض</option>{currencyBoxes.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</SearchSelect></label>}
            {instrument === 'bank' && <><label>حساب بانکی<SearchSelect value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}><option value="">— انتخاب —</option>{currencyBanks.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</SearchSelect></label><label>شماره برداشت<input value={withdrawalNo} onChange={(e) => setWithdrawalNo(e.target.value)} /></label><label>کارمزد<NumberInput value={bankFee} onChange={setBankFee} /></label></>}
            {instrument === 'payable_cheque' && <><label>حساب بانکی<SearchSelect value={bankAccountId} onChange={(e) => { setBankAccountId(e.target.value); setCheckbookId('') }}><option value="">— انتخاب —</option>{currencyBanks.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</SearchSelect></label><label>دسته‌چک<SearchSelect value={checkbookId} onChange={(e) => void chooseBook(e.target.value)}><option value="">بدون دسته (طبق سیاست)</option>{books.filter((b) => !bankAccountId || b.bank_account_id === bankAccountId).map((b) => <option key={b.id} value={b.id}>{b.bank_account_name} — {b.serial || `${b.first_number} تا ${b.last_number}`}</option>)}</SearchSelect></label><label>شماره چک<input value={checkNo} dir="ltr" onChange={(e) => setCheckNo(e.target.value)} /></label><label>سررسید<JalaliDatePicker value={dueDate} onChange={setDueDate} /></label><label>کد صیادی<input value={sayadId} maxLength={16} dir="ltr" onChange={(e) => setSayadId(e.target.value.replace(/\D/g, ''))} /></label></>}
            {instrument === 'endorsed_cheque' && <label className="form-wide">چک موجود<SearchSelect value={endorsedId} onChange={(e) => setEndorsedId(e.target.value)}><option value="">— انتخاب چک واجد شرایط —</option>{eligibleCheques.map((c) => <option key={c.id} value={c.id}>شماره {c.number} — {fa(c.amount)} — سررسید {formatJalali(c.due_date)}</option>)}</SearchSelect></label>}
            {instrument !== 'endorsed_cheque' && <label className="form-wide">شرح قلم<input value={lineDescription} onChange={(e) => setLineDescription(e.target.value)} /></label>}
            <div className="invoice-form-footer"><button type="button" onClick={addInstrument}><Plus size={14} /> افزودن قلم</button></div>
          </div>
          {instrumentRows.length > 0 && <div className="table-scroll"><table className="cards-on-mobile"><thead><tr><th>نوع</th><th>جزئیات</th><th>مبلغ</th><th>کارمزد</th><th></th></tr></thead><tbody>{instrumentRows.map((row) => <tr key={`${row.kind}-${row.index}`}><td className="card-title" data-label="نوع">{row.label}</td><td className="card-wide" data-label="جزئیات">{row.detail}</td><td className="num" data-label="مبلغ">{fa(row.amount)}</td><td className="num" data-label="کارمزد">{fa(row.fee)}</td><td className="card-actions" data-label="حذف"><button type="button" onClick={() => remove(row.kind, row.index)}><Trash2 size={13} /></button></td></tr>)}</tbody></table></div>}
          <div className="invoice-form-footer"><button type="submit" className="btn-primary" disabled={busy}><Save size={14} /> {busy ? 'در حال ثبت…' : 'ثبت اعلامیه و صدور سند'}</button></div>
        </SectionCard>
      </form>

      <SectionCard icon={ArrowUpFromLine} title="آخرین اعلامیه‌ها" description="هر ردیف یک Payment Notice مستقل است.">
        <AsyncBlock loading={data.loading} error={data.error} empty={recent.length === 0} emptyText="هنوز اعلامیه‌ای ثبت نشده."><div className="table-scroll"><table className="cards-on-mobile acc-table"><thead><tr><th>شماره</th><th>تاریخ</th><th>طرف حساب</th><th>اقلام</th><th>مبلغ پرداخت</th><th>کارمزد</th><th /></tr></thead><tbody>{pg.pageItems.map((row) => <tr key={row.id} className={row.voided_at ? 'acc-row--void' : ''}><td className="card-title" data-label="شماره">{faInt(row.number)}</td><td data-label="تاریخ">{formatJalali(row.payment_date)}</td><td className="card-wide" data-label="طرف حساب">{row.contact_name}</td><td className="card-wide" data-label="اقلام">{row.items_summary}</td><td className="num" data-label="مبلغ پرداخت">{fa(row.payment_amount)}</td><td className="num" data-label="کارمزد">{fa(row.bank_fee_amount)}</td><td className="card-actions" data-label="عملیات"><button type="button" className="link-button" onClick={() => setJournalEntryId(row.journal_entry_id)}>سند حسابداری</button><button type="button" className="link-button" onClick={() => void openPaymentPrintView(token, row.id)}>چاپ</button>{!row.voided_at && <button type="button" className="link-button" onClick={() => void voidRow(row.id, row.number)}><Ban size={14} /> ابطال</button>}</td></tr>)}</tbody></table><Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} /></div></AsyncBlock>
      </SectionCard>
      {journalEntryId && <JournalEntryDrawer token={token} entryId={journalEntryId} onClose={() => setJournalEntryId(null)} />}
    </OpsPage>
  )
}
