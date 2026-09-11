/**
 * رسید دریافت — یک رویداد، چند ابزار، یک سند.
 *
 * قرینه‌ی «اعلامیه پرداخت» است و عمداً: دو سندِ خواهر که یکی تخفیف داشته باشد و
 * دیگری نه، کاربر را مجبور می‌کند یادش بماند کدام کدام است.
 *
 * **چرا چهار آرایه‌ی جدا و نه یک آرایه با فیلدهای اختیاری:** هر ابزار
 * اعتبارسنجیِ خودش را دارد — کارت‌خوان کد پیگیری لازم دارد، چک سررسید، حواله
 * حسابِ بانکی. یک شکلِ مشترک یعنی همه‌ی این‌ها اختیاری شوند و خطا به سرور برسد.
 *
 * **جمع مشتق است.** «مبلغ دریافت» از اجزا حساب می‌شود و کاربر تایپش نمی‌کند؛
 * وگرنه دو عدد داریم که می‌توانند نخوانند.
 */
import { useMemo, useRef, useState } from 'react'
import { ArrowDownToLine, Ban, Banknote, CreditCard, Landmark, Plus, Save, ScrollText, Trash2 } from 'lucide-react'
import {
  createReceiptDocument,
  fetchAccountsLive,
  fetchBankAccountsLive,
  fetchCashboxes,
  fetchContacts,
  fetchCurrencies,
  fetchLatestRate,
  fetchPosTerminals,
  fetchReceiptDocuments,
  newIdempotencyKey,
  previewRas,
  openReceiptPrintView,
  voidReceiptDocument,
  RECEIPT_TYPE_LABELS,
  type ContactRecord,
  type RasResult,
  type ReceiptCardIn,
  type ReceiptCashIn,
  type ReceiptChequeIn,
  type ReceiptTransferIn,
  type ReceiptType,
} from '../../api'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { NumberInput } from '../../components/NumberInput'
import { Pager, usePagination } from '../../components/Pager'
import { SectionCard } from '../../components/SectionCard'
import { formatJalali, todayIso } from '../../lib/jalali'
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'

type Instrument = 'cash' | 'transfer' | 'cheque' | 'card'

const INSTRUMENT_LABELS: Record<Instrument, string> = {
  cash: 'وجه نقد',
  transfer: 'حواله',
  cheque: 'چک',
  card: 'کارت‌خوان',
}

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

export function ReceiptVoucherDocumentPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  //: کلید به *عملیات* گره می‌خورد نه به تلاشِ شبکه — اگر کاربر بعد از خطا دوباره
  //: دکمه را بزند، همان کلید می‌رود و رسیدِ دوم ساخته نمی‌شود (§۴۰).
  const requestKey = useRef(newIdempotencyKey())

  const [receiptType, setReceiptType] = useState<ReceiptType>('customer')
  const [contactId, setContactId] = useState('')
  const [date, setDate] = useState(todayIso())
  const [currency, setCurrency] = useState('IRR')
  const [rate, setRate] = useState('1')
  const [discountAccountId, setDiscountAccountId] = useState('')
  const [discount, setDiscount] = useState('')
  const [description, setDescription] = useState('')
  const [description2, setDescription2] = useState('')
  const [establishment, setEstablishment] = useState('')

  const [instrument, setInstrument] = useState<Instrument>('cash')
  const [lineAmount, setLineAmount] = useState('')
  const [cashboxId, setCashboxId] = useState('')
  const [bankAccountId, setBankAccountId] = useState('')
  const [terminalId, setTerminalId] = useState('')
  const [referenceNo, setReferenceNo] = useState('')
  const [traceNo, setTraceNo] = useState('')
  const [checkNo, setCheckNo] = useState('')
  const [sayadId, setSayadId] = useState('')
  const [backNumber, setBackNumber] = useState('')
  const [chequeBank, setChequeBank] = useState('')
  const [branchName, setBranchName] = useState('')
  const [branchCode, setBranchCode] = useState('')
  const [accountNumber, setAccountNumber] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [dueDate, setDueDate] = useState(todayIso())
  const [lineDescription, setLineDescription] = useState('')

  const [cash, setCash] = useState<ReceiptCashIn[]>([])
  const [transfers, setTransfers] = useState<ReceiptTransferIn[]>([])
  const [cards, setCards] = useState<ReceiptCardIn[]>([])
  const [cheques, setCheques] = useState<ReceiptChequeIn[]>([])

  const [ras, setRas] = useState<RasResult | null>(null)
  const [rasSameDay, setRasSameDay] = useState(true)

  const data = useAsync(async () => {
    const [contacts, banks, boxes, terminals, accounts, currencies, recent] = await Promise.all([
      fetchContacts(token),
      fetchBankAccountsLive(token),
      fetchCashboxes(token, false),
      fetchPosTerminals(token, { activeOnly: true }),
      fetchAccountsLive(token),
      fetchCurrencies(token),
      fetchReceiptDocuments(token),
    ])
    return { contacts, banks, boxes, terminals, accounts, currencies, recent }
  }, [token, reloadKey])

  const contacts = useMemo(() => {
    const all: ContactRecord[] = data.data?.contacts ?? []
    if (receiptType === 'customer') return all.filter((c) => c.type === 'customer' || c.type === 'both')
    if (receiptType === 'supplier') return all.filter((c) => c.type === 'supplier' || c.type === 'both')
    return all
  }, [data.data, receiptType])

  const accounts = (data.data?.accounts ?? []).filter((account) => !account.is_group)
  const currencyBanks = (data.data?.banks ?? []).filter((bank) => bank.currency_code === currency)
  const currencyBoxes = (data.data?.boxes ?? []).filter((box) => box.currency_code === currency)
  const currencyTerminals = (data.data?.terminals ?? []).filter((t) => t.currency_code === currency)
  const recent = (data.data?.recent ?? []).slice(0, 20)
  const pg = usePagination(recent, 8)

  const received =
    cash.reduce((sum, row) => sum + Number(row.amount), 0) +
    transfers.reduce((sum, row) => sum + Number(row.amount), 0) +
    cards.reduce((sum, row) => sum + Number(row.amount), 0) +
    cheques.reduce((sum, row) => sum + Number(row.amount), 0)
  const settlement = received + Number(discount || 0)
  const rowCount = cash.length + transfers.length + cards.length + cheques.length

  function clearLine() {
    setLineAmount('')
    setReferenceNo('')
    setTraceNo('')
    setCheckNo('')
    setSayadId('')
    setBackNumber('')
    setChequeBank('')
    setBranchName('')
    setBranchCode('')
    setAccountNumber('')
    setOwnerName('')
    setLineDescription('')
  }

  async function chooseCurrency(code: string) {
    setCurrency(code)
    setCashboxId('')
    setBankAccountId('')
    setTerminalId('')
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
    setRas(null)
    const amount = Number(lineAmount || 0)
    if (amount <= 0) {
      setMsg({ text: 'مبلغ جزء باید بزرگ‌تر از صفر باشد.', kind: 'err' })
      return
    }
    if (instrument === 'cash') {
      if (currency !== 'IRR' && !cashboxId) {
        setMsg({ text: 'برای ارز خارجی صندوق همان ارز را انتخاب کنید.', kind: 'err' })
        return
      }
      setCash((rows) => [...rows, { cashbox_id: cashboxId || null, amount, description: lineDescription }])
    } else if (instrument === 'transfer') {
      if (!bankAccountId) {
        setMsg({ text: 'حساب بانکی مقصد را انتخاب کنید.', kind: 'err' })
        return
      }
      setTransfers((rows) => [
        ...rows,
        { bank_account_id: bankAccountId, amount, reference_no: referenceNo, description: lineDescription },
      ])
    } else if (instrument === 'card') {
      if (!terminalId) {
        setMsg({ text: 'دستگاه کارت‌خوان را انتخاب کنید.', kind: 'err' })
        return
      }
      if (!referenceNo.trim()) {
        setMsg({ text: 'کد پیگیری کارت‌خوان لازم است؛ بدون آن تطبیق با تسویه ممکن نیست.', kind: 'err' })
        return
      }
      setCards((rows) => [
        ...rows,
        {
          pos_terminal_id: terminalId,
          amount,
          reference_no: referenceNo.trim(),
          trace_no: traceNo,
          description: lineDescription,
        },
      ])
    } else {
      if (!checkNo.trim() || !dueDate) {
        setMsg({ text: 'شماره چک و تاریخ سررسید لازم است.', kind: 'err' })
        return
      }
      setCheques((rows) => [
        ...rows,
        {
          number: checkNo.trim(),
          amount,
          due_date: dueDate,
          bank_name: chequeBank,
          sayad_id: sayadId,
          back_number: backNumber,
          branch_name: branchName,
          branch_code: branchCode,
          account_number: accountNumber,
          owner_name: ownerName,
          description: lineDescription,
        },
      ])
    }
    clearLine()
  }

  function remove(kind: Instrument, index: number) {
    setRas(null)
    if (kind === 'cash') setCash((rows) => rows.filter((_, i) => i !== index))
    if (kind === 'transfer') setTransfers((rows) => rows.filter((_, i) => i !== index))
    if (kind === 'card') setCards((rows) => rows.filter((_, i) => i !== index))
    if (kind === 'cheque') setCheques((rows) => rows.filter((_, i) => i !== index))
  }

  /** راس‌گیری محاسبه است، نه تراکنش (§۲۸) — سرور چیزی ذخیره نمی‌کند. */
  async function computeRas() {
    setMsg(null)
    const rows = [
      ...cash.map((row) => ({ amount: Number(row.amount), due_date: date })),
      ...transfers.map((row) => ({ amount: Number(row.amount), due_date: date })),
      ...cards.map((row) => ({ amount: Number(row.amount), due_date: date })),
      ...cheques.map((row) => ({ amount: Number(row.amount), due_date: row.due_date })),
    ]
    if (!rows.length) {
      setMsg({ text: 'برای راس‌گیری دست‌کم یک قلم لازم است.', kind: 'err' })
      return
    }
    try {
      setRas(await previewRas(token, date, rows, rasSameDay))
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  /** §۳۹ — رسید ویرایش نمی‌شود؛ باطل می‌شود و سندِ معکوس می‌خورد.
   *
   *  دلیلِ خواستنِ *دلیل*: سندِ معکوس در دفتر می‌ماند و کسی که سالِ بعد نگاهش
   *  می‌کند باید بفهمد چرا، نه فقط اینکه چیزی برگشت خورده.
   */
  async function voidRow(id: string, number: number) {
    const reason = window.prompt(`ابطالِ رسید شماره ${fa(number)} — دلیل را بنویسید:`)
    if (reason === null) return
    if (!reason.trim()) {
      setMsg({ text: 'برای ابطال باید دلیلی بنویسید.', kind: 'err' })
      return
    }
    try {
      await voidReceiptDocument(token, id, reason.trim())
      setMsg({ text: `رسید شماره ${fa(number)} باطل شد و سندِ معکوسش ثبت شد.`, kind: 'ok' })
      setReloadKey((key) => key + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setMsg(null)
    if (!contactId) return setMsg({ text: 'طرف حساب را انتخاب کنید.', kind: 'err' })
    if (received <= 0) return setMsg({ text: 'دست‌کم یک قلم دریافت اضافه کنید.', kind: 'err' })
    if (Number(discount || 0) > 0 && !discountAccountId) {
      return setMsg({ text: 'برای تخفیف، حساب تخفیف را انتخاب کنید.', kind: 'err' })
    }
    setBusy(true)
    try {
      const saved = await createReceiptDocument(
        token,
        {
          receipt_type: receiptType,
          contact_id: contactId,
          receipt_date: date,
          currency_code: currency,
          exchange_rate: Number(rate || 1),
          discount_amount: Number(discount || 0),
          discount_account_id: discountAccountId || null,
          description,
          description2,
          establishment,
          cash,
          transfers,
          cards,
          cheques,
        },
        requestKey.current,
      )
      setMsg({ text: `رسید دریافت شماره ${fa(saved.number)} و سند آن ثبت شد.`, kind: 'ok' })
      requestKey.current = newIdempotencyKey()
      setCash([])
      setTransfers([])
      setCards([])
      setCheques([])
      setDiscount('')
      setDescription('')
      setDescription2('')
      setRas(null)
      setReloadKey((key) => key + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const lineRows: { kind: Instrument; label: string; amount: number; extra: string }[] = [
    ...cash.map((row) => ({
      kind: 'cash' as const,
      label: currencyBoxes.find((b) => b.id === row.cashbox_id)?.name ?? 'صندوق پیش‌فرض',
      amount: Number(row.amount),
      extra: row.description ?? '',
    })),
    ...transfers.map((row) => ({
      kind: 'transfer' as const,
      label: currencyBanks.find((b) => b.id === row.bank_account_id)?.name ?? '',
      amount: Number(row.amount),
      extra: row.reference_no ?? '',
    })),
    ...cards.map((row) => ({
      kind: 'card' as const,
      label: currencyTerminals.find((t) => t.id === row.pos_terminal_id)?.label ?? '',
      amount: Number(row.amount),
      extra: row.reference_no,
    })),
    ...cheques.map((row) => ({
      kind: 'cheque' as const,
      label: `${row.number}${row.bank_name ? ` — ${row.bank_name}` : ''}`,
      amount: Number(row.amount),
      extra: `سررسید ${formatJalali(row.due_date)}`,
    })),
  ]

  const indexIn = (kind: Instrument, position: number) =>
    lineRows.slice(0, position).filter((row) => row.kind === kind).length

  return (
    <OpsPage
      icon={ArrowDownToLine}
      title="رسید دریافت"
      description="یک رسید می‌تواند هم‌زمان نقد، حواله، کارت‌خوان و چک داشته باشد؛ همه در یک سند."
    >
      <div className="workspace-split">
        <SectionCard icon={ArrowDownToLine} title="ثبت رسید" description="اجزا را یکی‌یکی اضافه کنید؛ جمع خودش حساب می‌شود.">
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              نوع دریافت
              <select value={receiptType} onChange={(e) => { setReceiptType(e.target.value as ReceiptType); setContactId('') }}>
                {(Object.keys(RECEIPT_TYPE_LABELS) as ReceiptType[]).map((key) => (
                  <option key={key} value={key}>{RECEIPT_TYPE_LABELS[key]}</option>
                ))}
              </select>
            </label>
            <label>
              طرف مقابل
              <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
                <option value="">— انتخاب کنید —</option>
                {contacts.map((contact) => (
                  <option key={contact.id} value={contact.id}>{contact.name}</option>
                ))}
              </select>
            </label>
            <label>
              تاریخ
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
            <label>
              ارز
              <select value={currency} onChange={(e) => void chooseCurrency(e.target.value)}>
                <option value="IRR">ریال</option>
                {(data.data?.currencies ?? []).filter((c) => c.code !== 'IRR').map((c) => (
                  <option key={c.code} value={c.code}>{c.name} ({c.code})</option>
                ))}
              </select>
            </label>
            {currency !== 'IRR' && (
              <label>
                نرخ تسعیر
                <NumberInput value={rate} onChange={setRate} allowDecimal />
                <span className="field-hint">سند به ریال ثبت می‌شود؛ این نرخ معادل ریالی را می‌سازد.</span>
              </label>
            )}

            <fieldset className="form-wide">
              <legend>افزودن قلم</legend>
              <div className="inline-fields">
                <label>
                  ابزار
                  <select value={instrument} onChange={(e) => { setInstrument(e.target.value as Instrument); clearLine() }}>
                    {(Object.keys(INSTRUMENT_LABELS) as Instrument[]).map((key) => (
                      <option key={key} value={key}>{INSTRUMENT_LABELS[key]}</option>
                    ))}
                  </select>
                </label>
                <label>
                  مبلغ
                  <NumberInput value={lineAmount} onChange={setLineAmount} />
                </label>
                {instrument === 'cash' && (
                  <label>
                    صندوق
                    <select value={cashboxId} onChange={(e) => setCashboxId(e.target.value)}>
                      <option value="">صندوق پیش‌فرض</option>
                      {currencyBoxes.map((box) => (
                        <option key={box.id} value={box.id}>{box.name}</option>
                      ))}
                    </select>
                  </label>
                )}
                {instrument === 'transfer' && (
                  <>
                    <label>
                      حساب بانکی
                      <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
                        <option value="">— انتخاب کنید —</option>
                        {currencyBanks.map((bank) => (
                          <option key={bank.id} value={bank.id}>{bank.name}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      شماره حواله
                      <input value={referenceNo} onChange={(e) => setReferenceNo(e.target.value)} dir="ltr" />
                      <span className="field-hint">در مغایرت بانکی از همین پیدا می‌شود.</span>
                    </label>
                  </>
                )}
                {instrument === 'card' && (
                  <>
                    <label>
                      دستگاه
                      <select value={terminalId} onChange={(e) => setTerminalId(e.target.value)}>
                        <option value="">— انتخاب کنید —</option>
                        {currencyTerminals.map((term) => (
                          <option key={term.id} value={term.id}>{term.label}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      کد پیگیری
                      <input value={referenceNo} onChange={(e) => setReferenceNo(e.target.value)} dir="ltr" />
                    </label>
                    <label>
                      شماره رسید دستگاه
                      <input value={traceNo} onChange={(e) => setTraceNo(e.target.value)} dir="ltr" />
                    </label>
                  </>
                )}
                {instrument === 'cheque' && (
                  <>
                    <label>
                      شماره چک
                      <input value={checkNo} onChange={(e) => setCheckNo(e.target.value)} dir="ltr" />
                    </label>
                    <label>
                      کد صیادی
                      <input value={sayadId} onChange={(e) => setSayadId(e.target.value)} dir="ltr" maxLength={16} />
                      <span className="field-hint">شانزده رقم؛ جدا از شماره چک.</span>
                    </label>
                    <label>
                      سررسید
                      <JalaliDatePicker value={dueDate} onChange={setDueDate} />
                    </label>
                    <label>
                      بانک
                      <input value={chequeBank} onChange={(e) => setChequeBank(e.target.value)} />
                    </label>
                    <label>
                      پشت نمره
                      <input value={backNumber} onChange={(e) => setBackNumber(e.target.value)} dir="ltr" />
                    </label>
                    <label>
                      شعبه
                      <input value={branchName} onChange={(e) => setBranchName(e.target.value)} />
                    </label>
                    <label>
                      کد شعبه
                      <input value={branchCode} onChange={(e) => setBranchCode(e.target.value)} dir="ltr" />
                    </label>
                    <label>
                      شماره حساب
                      <input value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} dir="ltr" />
                    </label>
                    <label>
                      صاحب چک
                      <input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} />
                      <span className="field-hint">اگر چک شخص ثالث است، نامِ صادرکننده.</span>
                    </label>
                  </>
                )}
                <label>
                  شرح قلم
                  <input value={lineDescription} onChange={(e) => setLineDescription(e.target.value)} />
                </label>
              </div>
              <button type="button" className="btn-secondary" onClick={addInstrument}>
                <Plus size={15} /> افزودن قلم
              </button>
            </fieldset>

            {rowCount > 0 && (
              <div className="form-wide table-scroll">
                <table className="cards-on-mobile">
                  <thead>
                    <tr>
                      <th>ابزار</th>
                      <th>مشخصات</th>
                      <th className="num">مبلغ</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {lineRows.map((row, position) => (
                      <tr key={`${row.kind}-${position}`}>
                        <td className="card-title" data-label="ابزار">{INSTRUMENT_LABELS[row.kind]}</td>
                        <td data-label="مشخصات">{row.label}{row.extra ? ` · ${row.extra}` : ''}</td>
                        <td className="num" data-label="مبلغ">{faInt(row.amount)}</td>
                        <td className="card-actions">
                          <button type="button" className="link-button" onClick={() => remove(row.kind, indexIn(row.kind, position))}>
                            <Trash2 size={14} /> حذف
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <label>
              تخفیف تسویه
              <NumberInput value={discount} onChange={setDiscount} />
              <span className="field-hint">پولی دریافت نمی‌شود؛ فقط مطالبه بسته می‌شود.</span>
            </label>
            {Number(discount || 0) > 0 && (
              <label>
                حساب تخفیف
                <select value={discountAccountId} onChange={(e) => setDiscountAccountId(e.target.value)}>
                  <option value="">— انتخاب کنید —</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>{account.code} — {account.name}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="form-wide">
              بابت
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <label className="form-wide">
              توضیحات
              <input value={description2} onChange={(e) => setDescription2(e.target.value)} />
            </label>
            <label>
              استقرار
              <input value={establishment} onChange={(e) => setEstablishment(e.target.value)} />
            </label>

            <div className="form-wide kpi-row">
              <Metric icon={<Banknote size={16} />} label="مبلغ دریافت" value={faInt(received)} tone="in" />
              <Metric icon={<ScrollText size={16} />} label="تخفیف" value={faInt(Number(discount || 0))} />
              <Metric icon={<Landmark size={16} />} label="جمع کل" value={faInt(settlement)} />
            </div>

            <fieldset className="form-wide">
              <legend>راس‌گیری</legend>
              <p className="muted">
                تاریخ متوسط وزنی اقلام. محاسبه است و چیزی ثبت نمی‌کند.
              </p>
              <label className="checkbox-row">
                <input type="checkbox" checked={rasSameDay} onChange={(e) => { setRasSameDay(e.target.checked); setRas(null) }} />
                چک‌های روز در محاسبه راس در نظر گرفته شوند
              </label>
              <button type="button" className="btn-secondary" onClick={computeRas}>
                <ScrollText size={15} /> محاسبه راس
              </button>
              {ras && (
                <p className="fy-note">
                  تاریخ راس: <strong>{formatJalali(ras.ras_date)}</strong> · میانگین {fa(ras.average_days)} روز
                  {ras.skipped_rows > 0 ? ` · ${fa(ras.skipped_rows)} قلم کنار گذاشته شد` : ''}
                </p>
              )}
            </fieldset>

            <Note msg={msg} />
            <div className="invoice-form-footer">
              <button className="btn-primary" disabled={busy}>
                <Save size={15} /> {busy ? 'در حال ثبت…' : 'ثبت رسید'}
              </button>
            </div>
          </form>
        </SectionCard>

        <SectionCard icon={Landmark} title="آخرین رسیدها" description="بیست رسید اخیر؛ دفتر کامل در «دریافت‌ها و پرداخت‌ها».">
          <AsyncBlock
            loading={data.loading}
            error={data.error}
            empty={recent.length === 0}
            emptyText="هنوز رسیدی ثبت نشده است. اولین رسید را از فرم کنار ثبت کنید."
          >
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>تاریخ</th>
                    <th>طرف مقابل</th>
                    <th>اقلام</th>
                    <th className="num">مبلغ</th>
                    <th>وضعیت</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((row) => (
                    <tr key={row.id}>
                      <td className="card-title" data-label="شماره">{fa(row.number)}</td>
                      <td data-label="تاریخ">{formatJalali(row.receipt_date)}</td>
                      <td data-label="طرف مقابل">{row.contact_name}</td>
                      <td data-label="اقلام">{row.items_summary}</td>
                      <td className="num" data-label="مبلغ">{faInt(Number(row.base_currency_amount))}</td>
                      <td data-label="وضعیت">{row.voided_at ? 'باطل‌شده' : 'ثبت‌شده'}</td>
                      <td className="card-actions">
                        <button type="button" className="link-button" onClick={() => void openReceiptPrintView(token, row.id)}>
                          چاپ
                        </button>
                        {!row.voided_at && (
                          <button type="button" className="link-button" onClick={() => void voidRow(row.id, row.number)}>
                            <Ban size={14} /> ابطال
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          </AsyncBlock>
        </SectionCard>
      </div>

      <SectionCard icon={Banknote} title="چطور کار می‌کند" description="">
        <ul className="muted">
          <li>یک رسید می‌تواند هم‌زمان نقد، حواله، کارت‌خوان و چک داشته باشد و همه‌شان <strong>یک</strong> سند حسابداری می‌سازند.</li>
          <li>هر ابزار به حساب ماهیت خودش می‌خورد: نقد به صندوق، حواله به بانک، چک به «چک‌های دریافتنی» و کارت‌خوان به حساب تسویه دستگاه.</li>
          <li>دریافت چک یعنی چک نزد شماست، نه اینکه پول به بانک رسیده باشد؛ ادامه‌اش در «عملیات بانکی چک دریافتنی».</li>
          <li>رسید اشتباه ویرایش نمی‌شود؛ باطل کنید و دوباره ثبت کنید تا سابقه بماند.</li>
        </ul>
        <p className="muted">
          <CreditCard size={14} /> پرداخت کارتی با تسویه‌ی بانکی یکی نیست: مبلغ کارت‌خوان تا «تسویه کارت خوان» تسویه‌نشده می‌ماند.
        </p>
      </SectionCard>
    </OpsPage>
  )
}
