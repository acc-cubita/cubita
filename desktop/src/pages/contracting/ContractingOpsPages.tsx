import { useEffect, useMemo, useState } from 'react'
import { FilePenLine, FileSignature, HandCoins, Receipt, RefreshCcw } from 'lucide-react'
import {
  changeContractStatus,
  createContract,
  createContractAmendment,
  createContractSettlement,
  createContractStatement,
  fetchContacts,
  fetchContractAmendments,
  fetchContracts,
  fetchContractSettlements,
  fetchContractStatements,
  fetchCostCenters,
  type ContactRecord,
  type ContractAmendmentRecord,
  type ContractRecord,
  type ContractSettlementRecord,
  type ContractStatementRecord,
  type ContractStatus,
  type CostCenterRecord,
} from '../../api'
import { OpsPage, Note, type Msg } from '../accounting/kit'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { EmptyState } from '../../components/EmptyState'
import { formatJalali, todayIso } from '../../lib/jalali'
import { SearchSelect } from '../../components/SearchSelect'

const fa = (n: number) => Number(n || 0).toLocaleString('fa-IR')

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

const STATUS_LABELS: Record<ContractStatus, string> = {
  draft: 'پیش‌نویس',
  active: 'جاری',
  suspended: 'معلق',
  terminated: 'فسخ‌شده',
  completed: 'تکمیل‌شده',
  cancelled: 'لغوشده',
}

//: عیناً همان گذارِ سرور (`services/contracting.py`) — تکرار عمدی است تا انتخابِ
//: کاربر پیش از ارسال هم محدود به گذارهای واقعی باشد.
const TRANSITIONS: Record<ContractStatus, ContractStatus[]> = {
  draft: ['active', 'cancelled'],
  active: ['suspended', 'terminated', 'completed'],
  suspended: ['active', 'terminated'],
  terminated: [],
  completed: [],
  cancelled: [],
}

const EMPTY_FORM = {
  contactId: '',
  externalReference: '',
  subject: '',
  totalAmount: '',
  startDate: todayIso(),
  endDate: '',
  retentionPercent: '',
  advancePercent: '',
  costCenterId: '',
  notes: '',
}

export function ContractPage({ token }: { token: string }) {
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [recent, setRecent] = useState<ContractRecord[]>([])
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [msg, setMsg] = useState<Msg>(null)
  //: جدا از `msg` عمداً: `submit` بعد از پیامِ موفقیت `refresh` را صدا می‌زند، و
  //: اگر خطای بارگذاری در همان جا بنشیند «ثبت شد» را پاک می‌کند — کاربر فکر
  //: می‌کند ثبت نشده و دوباره می‌فرستد. کلیدِ یکتاسازی هر بار تازه ساخته
  //: می‌شود، پس ارسالِ دوم رکوردِ دوم می‌سازد.
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setLoadError(null)
    try {
      const [cs, ccs, rs] = await Promise.all([
        fetchContacts(token),
        fetchCostCenters(token),
        fetchContracts(token),
      ])
      setContacts(cs)
      setCostCenters(ccs)
      setRecent(rs.slice(0, 8))
    } catch (err) {
      setLoadError(`${errText(err)} — فهرست‌های این صفحه پر نشد؛ صفحه را دوباره باز کنید.`)
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  const set = (patch: Partial<typeof EMPTY_FORM>) => setForm({ ...form, ...patch })

  async function submit() {
    setMsg(null)
    if (!form.contactId) {
      setMsg({ kind: 'err', text: 'کارفرما را انتخاب کنید.' })
      return
    }
    if (!(Number(form.totalAmount) > 0)) {
      setMsg({ kind: 'err', text: 'مبلغِ پیمان باید بزرگ‌تر از صفر باشد.' })
      return
    }
    setBusy(true)
    try {
      await createContract(
        token,
        {
          contact_id: form.contactId,
          external_reference: form.externalReference,
          subject: form.subject,
          total_amount: Number(form.totalAmount),
          start_date: form.startDate,
          end_date: form.endDate || null,
          retention_percent: Number(form.retentionPercent) || 0,
          advance_percent: Number(form.advancePercent) || 0,
          cost_center_id: form.costCenterId || null,
          notes: form.notes,
        },
        `contract-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setMsg({ kind: 'ok', text: 'پیمان ثبت شد.' })
      setForm({ ...EMPTY_FORM })
      void refresh()
    } catch (err) {
      setMsg({ kind: 'err', text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage icon={FileSignature} title="پیمان" description="ثبتِ یک پیمانِ تازه و مفادش.">
      <div className="workspace-split">
        <SectionCard icon={FileSignature} title="پیمانِ تازه">
          <form
            className="invoice-form form-full"
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
          >
            <label>
              کارفرما
              <SearchSelect value={form.contactId} onChange={(e) => set({ contactId: e.target.value })} required>
                <option value="">— انتخابِ کارفرما —</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label>
              شماره‌ی قراردادِ کارفرما
              <input
                value={form.externalReference}
                onChange={(e) => set({ externalReference: e.target.value })}
                placeholder="اختیاری"
              />
            </label>
            <label>
              موضوع
              <input value={form.subject} onChange={(e) => set({ subject: e.target.value })} placeholder="مثلاً ساختِ سوله" />
            </label>
            <label>
              مبلغِ کلِ پیمان
              <NumberInput value={form.totalAmount} onChange={(v) => set({ totalAmount: v })} required />
            </label>
            <label>
              تاریخِ شروع
              <JalaliDatePicker value={form.startDate} onChange={(iso) => set({ startDate: iso })} />
            </label>
            <label>
              تاریخِ پایان
              <JalaliDatePicker value={form.endDate} onChange={(iso) => set({ endDate: iso })} placeholder="اختیاری" />
            </label>
            <label>
              درصدِ سپرده (حسن انجامِ کار)
              <NumberInput value={form.retentionPercent} onChange={(v) => set({ retentionPercent: v })} placeholder="۰" />
            </label>
            <label>
              درصدِ پیش‌پرداخت
              <NumberInput value={form.advancePercent} onChange={(v) => set({ advancePercent: v })} placeholder="۰" />
            </label>
            <label>
              مرکزِ هزینه
              <SearchSelect value={form.costCenterId} onChange={(e) => set({ costCenterId: e.target.value })}>
                <option value="">— بدونِ مرکزِ هزینه —</option>
                {costCenters.filter((c) => c.is_active).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label className="form-full">
              توضیحات
              <textarea value={form.notes} onChange={(e) => set({ notes: e.target.value })} rows={2} />
            </label>
            <div className="form-full">
              <button type="submit" disabled={busy}>
                {busy ? 'در حال ثبت…' : 'ثبتِ پیمان'}
              </button>
            </div>
          </form>
          <Note msg={loadError ? { kind: 'err', text: loadError } : null} />
          <Note msg={msg} />
        </SectionCard>

        <SectionCard icon={FileSignature} title="پیمان‌های اخیر">
          {recent.length === 0 ? (
            <EmptyState icon={FileSignature} text="هنوز پیمانی ثبت نشده." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>کارفرما</th>
                    <th>مبلغ</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((c) => (
                    <tr key={c.id}>
                      <td className="card-title" data-label="شماره">{fa(c.number)}</td>
                      <td data-label="کارفرما">{c.contact_name}</td>
                      <td className="num" data-label="مبلغ">{fa(Number(c.total_amount))}</td>
                      <td data-label="وضعیت">
                        <span className="status-badge">{STATUS_LABELS[c.status]}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </OpsPage>
  )
}

export function ContractStatusPage({ token }: { token: string }) {
  const [contracts, setContracts] = useState<ContractRecord[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [newStatus, setNewStatus] = useState<ContractStatus | ''>('')
  const [msg, setMsg] = useState<Msg>(null)
  //: جدا از `msg` عمداً: `submit` بعد از پیامِ موفقیت `refresh` را صدا می‌زند، و
  //: اگر خطای بارگذاری در همان جا بنشیند «ثبت شد» را پاک می‌کند — کاربر فکر
  //: می‌کند ثبت نشده و دوباره می‌فرستد. کلیدِ یکتاسازی هر بار تازه ساخته
  //: می‌شود، پس ارسالِ دوم رکوردِ دوم می‌سازد.
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setLoadError(null)
    try {
      const rows = await fetchContracts(token)
      setContracts(rows)
    } catch (err) {
      setLoadError(`${errText(err)} — فهرست‌های این صفحه پر نشد؛ صفحه را دوباره باز کنید.`)
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  const selected = useMemo(() => contracts.find((c) => c.id === selectedId) ?? null, [contracts, selectedId])
  const options = selected ? TRANSITIONS[selected.status] : []

  async function submit() {
    if (!selected || !newStatus) return
    setMsg(null)
    setBusy(true)
    try {
      await changeContractStatus(token, selected.id, newStatus)
      setMsg({ kind: 'ok', text: 'وضعیتِ پیمان تغییر کرد.' })
      setNewStatus('')
      void refresh()
    } catch (err) {
      setMsg({ kind: 'err', text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage icon={RefreshCcw} title="تغییر وضعیت پیمان" description="شروع، تعلیق، خاتمه یا فسخِ یک پیمانِ ثبت‌شده.">
      <SectionCard icon={RefreshCcw} title="تغییرِ وضعیت">
        <form
          className="invoice-form form-full"
          onSubmit={(e) => {
            e.preventDefault()
            void submit()
          }}
        >
          <label>
            پیمان
            <SearchSelect
              value={selectedId}
              onChange={(e) => {
                setSelectedId(e.target.value)
                setNewStatus('')
              }}
              required
            >
              <option value="">— انتخابِ پیمان —</option>
              {contracts.map((c) => (
                <option key={c.id} value={c.id}>
                  {fa(c.number)} — {c.contact_name} ({STATUS_LABELS[c.status]})
                </option>
              ))}
            </SearchSelect>
          </label>
          {selected && (
            <>
              <p className="hint">
                شروع: {formatJalali(selected.start_date)} · وضعیتِ فعلی: {STATUS_LABELS[selected.status]}
              </p>
              <label>
                وضعیتِ تازه
                <SearchSelect
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value as ContractStatus)}
                  required
                  disabled={options.length === 0}
                >
                  <option value="">— انتخابِ وضعیتِ تازه —</option>
                  {options.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </SearchSelect>
              </label>
              {options.length === 0 && (
                <p className="hint">این پیمان به وضعیتِ پایانی رسیده و گذارِ دیگری ندارد.</p>
              )}
            </>
          )}
          <div className="form-full">
            <button type="submit" disabled={busy || !selected || !newStatus}>
              {busy ? 'در حال ثبت…' : 'ثبتِ تغییرِ وضعیت'}
            </button>
          </div>
        </form>
        <Note msg={loadError ? { kind: 'err', text: loadError } : null} />
          <Note msg={msg} />
      </SectionCard>
    </OpsPage>
  )
}

//: پیمانی که به وضعیتِ پایانی رسیده متممِ تازه نمی‌پذیرد (سرور هم همین را رد می‌کند) —
//: پس از انتخاب حذفش می‌کنیم تا کاربر خطای بی‌فایده نبیند.
const CLOSED_STATUSES: ContractStatus[] = ['terminated', 'completed', 'cancelled']

const EMPTY_AMENDMENT_FORM = {
  contractId: '',
  date: todayIso(),
  description: '',
  amountDelta: '',
  newEndDate: '',
  notes: '',
}

export function ContractAmendmentPage({ token }: { token: string }) {
  const [contracts, setContracts] = useState<ContractRecord[]>([])
  const [recent, setRecent] = useState<ContractAmendmentRecord[]>([])
  const [form, setForm] = useState({ ...EMPTY_AMENDMENT_FORM })
  const [msg, setMsg] = useState<Msg>(null)
  //: جدا از `msg` عمداً: `submit` بعد از پیامِ موفقیت `refresh` را صدا می‌زند، و
  //: اگر خطای بارگذاری در همان جا بنشیند «ثبت شد» را پاک می‌کند — کاربر فکر
  //: می‌کند ثبت نشده و دوباره می‌فرستد. کلیدِ یکتاسازی هر بار تازه ساخته
  //: می‌شود، پس ارسالِ دوم رکوردِ دوم می‌سازد.
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setLoadError(null)
    try {
      const [cs, rs] = await Promise.all([fetchContracts(token), fetchContractAmendments(token)])
      setContracts(cs.filter((c) => !CLOSED_STATUSES.includes(c.status)))
      setRecent(rs.slice(0, 8))
    } catch (err) {
      setLoadError(`${errText(err)} — فهرست‌های این صفحه پر نشد؛ صفحه را دوباره باز کنید.`)
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  const set = (patch: Partial<typeof EMPTY_AMENDMENT_FORM>) => setForm({ ...form, ...patch })
  const selected = useMemo(() => contracts.find((c) => c.id === form.contractId) ?? null, [contracts, form.contractId])

  async function submit() {
    setMsg(null)
    if (!form.contractId) {
      setMsg({ kind: 'err', text: 'پیمان را انتخاب کنید.' })
      return
    }
    if (!form.description.trim()) {
      setMsg({ kind: 'err', text: 'موضوعِ متمم را بنویسید.' })
      return
    }
    setBusy(true)
    try {
      await createContractAmendment(
        token,
        {
          contract_id: form.contractId,
          date: form.date,
          description: form.description,
          amount_delta: Number(form.amountDelta) || 0,
          new_end_date: form.newEndDate || null,
          notes: form.notes,
        },
        `contract-amendment-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setMsg({ kind: 'ok', text: 'متمم ثبت شد.' })
      setForm({ ...EMPTY_AMENDMENT_FORM })
      void refresh()
    } catch (err) {
      setMsg({ kind: 'err', text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage icon={FilePenLine} title="متمم پیمان" description="افزودنِ تغییرِ مبلغ و/یا تاریخِ پایانِ یک پیمانِ ثبت‌شده.">
      <div className="workspace-split">
        <SectionCard icon={FilePenLine} title="متممِ تازه">
          <form
            className="invoice-form form-full"
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
          >
            <label>
              پیمان
              <SearchSelect value={form.contractId} onChange={(e) => set({ contractId: e.target.value })} required>
                <option value="">— انتخابِ پیمان —</option>
                {contracts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {fa(c.number)} — {c.contact_name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            {selected && (
              <p className="hint">
                مبلغِ اولیه: {fa(Number(selected.total_amount))} ریال
                {selected.end_date ? ` · پایانِ فعلی: ${formatJalali(selected.end_date)}` : ''}
              </p>
            )}
            <label>
              تاریخِ متمم
              <JalaliDatePicker value={form.date} onChange={(iso) => set({ date: iso })} />
            </label>
            <label className="form-full">
              موضوعِ متمم
              <input value={form.description} onChange={(e) => set({ description: e.target.value })} placeholder="مثلاً افزایشِ محدوده‌ی کار" required />
            </label>
            <label>
              تغییرِ مبلغ
              <NumberInput value={form.amountDelta} onChange={(v) => set({ amountDelta: v })} allowNegative placeholder="۰" />
            </label>
            <label>
              تاریخِ پایانِ تازه
              <JalaliDatePicker value={form.newEndDate} onChange={(iso) => set({ newEndDate: iso })} placeholder="اختیاری — بدونِ تغییر" />
            </label>
            <label className="form-full">
              توضیحات
              <textarea value={form.notes} onChange={(e) => set({ notes: e.target.value })} rows={2} />
            </label>
            <div className="form-full">
              <button type="submit" disabled={busy}>
                {busy ? 'در حال ثبت…' : 'ثبتِ متمم'}
              </button>
            </div>
          </form>
          <Note msg={loadError ? { kind: 'err', text: loadError } : null} />
          <Note msg={msg} />
        </SectionCard>

        <SectionCard icon={FilePenLine} title="متمم‌های اخیر">
          {recent.length === 0 ? (
            <EmptyState icon={FilePenLine} text="هنوز متممی ثبت نشده." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>پیمان</th>
                    <th>تغییرِ مبلغ</th>
                    <th>تاریخ</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((a) => (
                    <tr key={a.id}>
                      <td className="card-title" data-label="شماره">{fa(a.number)}</td>
                      <td data-label="پیمان">{a.contract_number != null ? fa(a.contract_number) : '—'}</td>
                      <td className="num" data-label="تغییرِ مبلغ">{fa(Number(a.amount_delta))}</td>
                      <td data-label="تاریخ">{formatJalali(a.date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </OpsPage>
  )
}

const EMPTY_STATEMENT_FORM = {
  contractId: '',
  date: todayIso(),
  grossAmount: '',
  otherDeductions: '',
  notes: '',
}

export function ContractStatementPage({ token }: { token: string }) {
  const [contracts, setContracts] = useState<ContractRecord[]>([])
  const [recent, setRecent] = useState<ContractStatementRecord[]>([])
  const [form, setForm] = useState({ ...EMPTY_STATEMENT_FORM })
  const [msg, setMsg] = useState<Msg>(null)
  //: جدا از `msg` عمداً: `submit` بعد از پیامِ موفقیت `refresh` را صدا می‌زند، و
  //: اگر خطای بارگذاری در همان جا بنشیند «ثبت شد» را پاک می‌کند — کاربر فکر
  //: می‌کند ثبت نشده و دوباره می‌فرستد. کلیدِ یکتاسازی هر بار تازه ساخته
  //: می‌شود، پس ارسالِ دوم رکوردِ دوم می‌سازد.
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setLoadError(null)
    try {
      const [cs, rs] = await Promise.all([fetchContracts(token), fetchContractStatements(token)])
      setContracts(cs.filter((c) => !CLOSED_STATUSES.includes(c.status)))
      setRecent(rs.slice(0, 8))
    } catch (err) {
      setLoadError(`${errText(err)} — فهرست‌های این صفحه پر نشد؛ صفحه را دوباره باز کنید.`)
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  const set = (patch: Partial<typeof EMPTY_STATEMENT_FORM>) => setForm({ ...form, ...patch })
  const selected = useMemo(() => contracts.find((c) => c.id === form.contractId) ?? null, [contracts, form.contractId])

  //: پیش‌نمایشِ سمتِ کلاینت — عددِ رسمی را سرور در پاسخ برمی‌گرداند.
  const preview = useMemo(() => {
    if (!selected) return null
    const gross = Number(form.grossAmount) || 0
    const retentionAmount = Math.round((gross * Number(selected.retention_percent)) / 100)
    const advanceDeduction = Math.round((gross * Number(selected.advance_percent)) / 100)
    const other = Number(form.otherDeductions) || 0
    return { retentionAmount, advanceDeduction, net: gross - retentionAmount - advanceDeduction - other }
  }, [selected, form.grossAmount, form.otherDeductions])

  async function submit() {
    setMsg(null)
    if (!form.contractId) {
      setMsg({ kind: 'err', text: 'پیمان را انتخاب کنید.' })
      return
    }
    if (!(Number(form.grossAmount) > 0)) {
      setMsg({ kind: 'err', text: 'مبلغِ ناخالصِ کارکرد باید بزرگ‌تر از صفر باشد.' })
      return
    }
    setBusy(true)
    try {
      await createContractStatement(
        token,
        {
          contract_id: form.contractId,
          date: form.date,
          gross_amount: Number(form.grossAmount),
          other_deductions: Number(form.otherDeductions) || 0,
          notes: form.notes,
        },
        `contract-statement-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setMsg({ kind: 'ok', text: 'صورت‌وضعیت ثبت شد.' })
      setForm({ ...EMPTY_STATEMENT_FORM })
      void refresh()
    } catch (err) {
      setMsg({ kind: 'err', text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage icon={Receipt} title="صورت وضعیت دریافتی" description="ثبتِ کارکردِ یک دوره و کسوراتش — بدونِ سندِ حسابداری.">
      <div className="workspace-split">
        <SectionCard icon={Receipt} title="صورت‌وضعیتِ تازه">
          <form
            className="invoice-form form-full"
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
          >
            <label>
              پیمان
              <SearchSelect value={form.contractId} onChange={(e) => set({ contractId: e.target.value })} required>
                <option value="">— انتخابِ پیمان —</option>
                {contracts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {fa(c.number)} — {c.contact_name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            {selected && (
              <p className="hint">
                سپرده: {fa(Number(selected.retention_percent))}٪ · پیش‌پرداخت: {fa(Number(selected.advance_percent))}٪
              </p>
            )}
            <label>
              تاریخِ صورت‌وضعیت
              <JalaliDatePicker value={form.date} onChange={(iso) => set({ date: iso })} />
            </label>
            <label>
              مبلغِ ناخالصِ کارکرد
              <NumberInput value={form.grossAmount} onChange={(v) => set({ grossAmount: v })} required />
            </label>
            <label>
              سایرِ کسورات
              <NumberInput value={form.otherDeductions} onChange={(v) => set({ otherDeductions: v })} placeholder="۰" />
            </label>
            {preview && (
              <p className="hint form-full">
                کسرِ سپرده: {fa(preview.retentionAmount)} · کسرِ پیش‌پرداخت: {fa(preview.advanceDeduction)} · مبلغِ خالصِ قابلِ‌پرداخت: {fa(preview.net)}
              </p>
            )}
            <label className="form-full">
              توضیحات
              <textarea value={form.notes} onChange={(e) => set({ notes: e.target.value })} rows={2} />
            </label>
            <div className="form-full">
              <button type="submit" disabled={busy}>
                {busy ? 'در حال ثبت…' : 'ثبتِ صورت‌وضعیت'}
              </button>
            </div>
          </form>
          <Note msg={loadError ? { kind: 'err', text: loadError } : null} />
          <Note msg={msg} />
        </SectionCard>

        <SectionCard icon={Receipt} title="صورت‌وضعیت‌های اخیر">
          {recent.length === 0 ? (
            <EmptyState icon={Receipt} text="هنوز صورت‌وضعیتی ثبت نشده." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>پیمان</th>
                    <th>ناخالص</th>
                    <th>خالص</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((s) => (
                    <tr key={s.id}>
                      <td className="card-title" data-label="شماره">{fa(s.number)}</td>
                      <td data-label="پیمان">{s.contract_number != null ? fa(s.contract_number) : '—'}</td>
                      <td className="num" data-label="ناخالص">{fa(Number(s.gross_amount))}</td>
                      <td className="num" data-label="خالص">{fa(Number(s.net_amount))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </OpsPage>
  )
}

const EMPTY_SETTLEMENT_FORM = {
  contractId: '',
  date: todayIso(),
  notes: '',
}

export function ContractSettlementPage({ token }: { token: string }) {
  const [contracts, setContracts] = useState<ContractRecord[]>([])
  const [settlements, setSettlements] = useState<ContractSettlementRecord[]>([])
  const [recent, setRecent] = useState<ContractSettlementRecord[]>([])
  const [previewStatements, setPreviewStatements] = useState<ContractStatementRecord[]>([])
  const [form, setForm] = useState({ ...EMPTY_SETTLEMENT_FORM })
  const [msg, setMsg] = useState<Msg>(null)
  //: جدا از `msg` عمداً: `submit` بعد از پیامِ موفقیت `refresh` را صدا می‌زند، و
  //: اگر خطای بارگذاری در همان جا بنشیند «ثبت شد» را پاک می‌کند — کاربر فکر
  //: می‌کند ثبت نشده و دوباره می‌فرستد. کلیدِ یکتاسازی هر بار تازه ساخته
  //: می‌شود، پس ارسالِ دوم رکوردِ دوم می‌سازد.
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setLoadError(null)
    try {
      const [cs, ss] = await Promise.all([fetchContracts(token), fetchContractSettlements(token)])
      setContracts(cs)
      setSettlements(ss)
      setRecent(ss.slice(0, 8))
    } catch (err) {
      setLoadError(`${errText(err)} — فهرست‌های این صفحه پر نشد؛ صفحه را دوباره باز کنید.`)
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  const set = (patch: Partial<typeof EMPTY_SETTLEMENT_FORM>) => setForm({ ...form, ...patch })

  //: پیمانی که تسویه‌ی فعال دارد دوباره تسویه نمی‌پذیرد (سرور هم همین را رد می‌کند).
  const settledContractIds = useMemo(
    () => new Set(settlements.filter((s) => !s.voided_at).map((s) => s.contract_id)),
    [settlements],
  )
  const selectable = useMemo(
    () => contracts.filter((c) => !settledContractIds.has(c.id)),
    [contracts, settledContractIds],
  )
  const selected = useMemo(() => contracts.find((c) => c.id === form.contractId) ?? null, [contracts, form.contractId])

  useEffect(() => {
    if (!form.contractId) {
      setPreviewStatements([])
      return
    }
    void fetchContractStatements(token, { contract_id: form.contractId }).then(setPreviewStatements)
  }, [token, form.contractId])

  //: پیش‌نمایشِ سمتِ کلاینت — عددِ رسمی را سرور در پاسخ برمی‌گرداند.
  const preview = useMemo(() => {
    if (previewStatements.length === 0) return null
    const sum = (pick: (s: ContractStatementRecord) => string) =>
      previewStatements.reduce((total, s) => total + Number(pick(s) || 0), 0)
    return {
      gross: sum((s) => s.gross_amount),
      retention: sum((s) => s.retention_amount),
      advance: sum((s) => s.advance_deduction),
      other: sum((s) => s.other_deductions),
      net: sum((s) => s.net_amount),
    }
  }, [previewStatements])

  async function submit() {
    setMsg(null)
    if (!form.contractId) {
      setMsg({ kind: 'err', text: 'پیمان را انتخاب کنید.' })
      return
    }
    if (!preview) {
      setMsg({ kind: 'err', text: 'این پیمان هنوز صورت‌وضعیتی ندارد — چیزی برای تسویه نیست.' })
      return
    }
    setBusy(true)
    try {
      await createContractSettlement(
        token,
        { contract_id: form.contractId, date: form.date, notes: form.notes },
        `contract-settlement-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setMsg({ kind: 'ok', text: 'تسویه‌حساب ثبت شد.' })
      setForm({ ...EMPTY_SETTLEMENT_FORM })
      void refresh()
    } catch (err) {
      setMsg({ kind: 'err', text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={HandCoins}
      title="تسویه حساب پیمان"
      description="ثبتِ تسویه‌ی نهاییِ پیمان — تنها عملیاتِ این ماژول که سندِ حسابداری می‌زند."
    >
      <div className="workspace-split">
        <SectionCard icon={HandCoins} title="تسویه‌حسابِ تازه">
          <form
            className="invoice-form form-full"
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
          >
            <label>
              پیمان
              <SearchSelect value={form.contractId} onChange={(e) => set({ contractId: e.target.value })} required>
                <option value="">— انتخابِ پیمان —</option>
                {selectable.map((c) => (
                  <option key={c.id} value={c.id}>
                    {fa(c.number)} — {c.contact_name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            {selected && (
              <p className="hint">
                مبلغِ قراردادی: {fa(Number(selected.total_amount))} ریال
              </p>
            )}
            <label>
              تاریخِ تسویه
              <JalaliDatePicker value={form.date} onChange={(iso) => set({ date: iso })} />
            </label>
            {form.contractId && !preview && (
              <p className="hint form-full">این پیمان هنوز صورت‌وضعیتی ندارد — چیزی برای تسویه نیست.</p>
            )}
            {preview && (
              <div className="form-full">
                <table className="cards-on-mobile">
                  <thead>
                    <tr>
                      <th>ناخالص</th>
                      <th>سپرده</th>
                      <th>پیش‌پرداخت</th>
                      <th>سایرِ کسورات</th>
                      <th>خالص</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="card-title num" data-label="ناخالص">{fa(preview.gross)}</td>
                      <td className="num" data-label="سپرده">{fa(preview.retention)}</td>
                      <td className="num" data-label="پیش‌پرداخت">{fa(preview.advance)}</td>
                      <td className="num" data-label="سایرِ کسورات">{fa(preview.other)}</td>
                      <td className="num" data-label="خالص">{fa(preview.net)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
            <label className="form-full">
              توضیحات
              <textarea value={form.notes} onChange={(e) => set({ notes: e.target.value })} rows={2} />
            </label>
            <div className="form-full">
              <button type="submit" disabled={busy || !preview}>
                {busy ? 'در حال ثبت…' : 'ثبتِ تسویه‌حساب'}
              </button>
            </div>
          </form>
          <Note msg={loadError ? { kind: 'err', text: loadError } : null} />
          <Note msg={msg} />
        </SectionCard>

        <SectionCard icon={HandCoins} title="تسویه‌حساب‌های اخیر">
          {recent.length === 0 ? (
            <EmptyState icon={HandCoins} text="هنوز تسویه‌حسابی ثبت نشده." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>پیمان</th>
                    <th>خالص</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((s) => (
                    <tr key={s.id}>
                      <td className="card-title" data-label="شماره">{fa(s.number)}</td>
                      <td data-label="پیمان">{s.contract_number != null ? fa(s.contract_number) : '—'}</td>
                      <td className="num" data-label="خالص">{fa(Number(s.net_amount))}</td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${s.voided_at ? 'tone-danger' : 'tone-success'}`}>
                          {s.voided_at ? 'باطل‌شده' : 'ثبت‌شده'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </OpsPage>
  )
}
