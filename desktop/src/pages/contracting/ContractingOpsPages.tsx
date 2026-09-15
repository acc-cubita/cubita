import { useEffect, useMemo, useState } from 'react'
import { FilePenLine, FileSignature, RefreshCcw } from 'lucide-react'
import {
  changeContractStatus,
  createContract,
  createContractAmendment,
  fetchContacts,
  fetchContractAmendments,
  fetchContracts,
  fetchCostCenters,
  type ContactRecord,
  type ContractAmendmentRecord,
  type ContractRecord,
  type ContractStatus,
  type CostCenterRecord,
} from '../../api'
import { OpsPage, Note, type Msg } from '../accounting/kit'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { EmptyState } from '../../components/EmptyState'
import { formatJalali, todayIso } from '../../lib/jalali'

const fa = (n: number) => Number(n || 0).toLocaleString('fa-IR')

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
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const [cs, ccs, rs] = await Promise.all([
      fetchContacts(token),
      fetchCostCenters(token),
      fetchContracts(token),
    ])
    setContacts(cs)
    setCostCenters(ccs)
    setRecent(rs.slice(0, 8))
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
      setMsg({ kind: 'err', text: err instanceof Error ? err.message : 'خطای ناشناخته' })
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
              <select value={form.contactId} onChange={(e) => set({ contactId: e.target.value })} required>
                <option value="">— انتخابِ کارفرما —</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
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
              <select value={form.costCenterId} onChange={(e) => set({ costCenterId: e.target.value })}>
                <option value="">— بدونِ مرکزِ هزینه —</option>
                {costCenters.filter((c) => c.is_active).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
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
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const rows = await fetchContracts(token)
    setContracts(rows)
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
      setMsg({ kind: 'err', text: err instanceof Error ? err.message : 'خطای ناشناخته' })
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
            <select
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
            </select>
          </label>
          {selected && (
            <>
              <p className="hint">
                شروع: {formatJalali(selected.start_date)} · وضعیتِ فعلی: {STATUS_LABELS[selected.status]}
              </p>
              <label>
                وضعیتِ تازه
                <select
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
                </select>
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
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const [cs, rs] = await Promise.all([fetchContracts(token), fetchContractAmendments(token)])
    setContracts(cs.filter((c) => !CLOSED_STATUSES.includes(c.status)))
    setRecent(rs.slice(0, 8))
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
      setMsg({ kind: 'err', text: err instanceof Error ? err.message : 'خطای ناشناخته' })
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
              <select value={form.contractId} onChange={(e) => set({ contractId: e.target.value })} required>
                <option value="">— انتخابِ پیمان —</option>
                {contracts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {fa(c.number)} — {c.contact_name}
                  </option>
                ))}
              </select>
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
