import { useEffect, useState } from 'react'
import { Calculator, Plus, Save, Trash2 } from 'lucide-react'
import {
  TAX_CALC_PURPOSE_LABELS,
  createTaxTable,
  deleteTaxTable,
  fetchPayrollTaxGroups,
  fetchTaxTables,
  updateTaxTable,
  type PayrollTaxGroupRecord,
  type TaxTableRecord,
} from '../../api'
import { EmptyState } from '../../components/EmptyState'
import { SectionCard } from '../../components/SectionCard'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { formatJalali } from '../../lib/jalali'
import { AsyncBlock, Note, OpsPage, type Msg } from '../accounting/kit'

/**
 * جدول‌های مالیاتِ حقوق.
 *
 * **سالِ تازه یعنی جدولِ تازه، نه ویرایشِ جدولِ پارسال.** جدول‌های گذشته می‌مانند
 * تا محاسبه‌ی گذشته بازتولیدپذیر بماند — و همین است که فهرست را چندساله می‌کند.
 *
 * یک سال می‌تواند چند جدول داشته باشد: یکی به‌ازای هر گروهِ مالیاتی، و یکی
 * به‌ازای هر هدفِ محاسبه (حقوق / عیدی). ترکیبِ «تاریخ اجرا + گروه + نوع» یکتاست،
 * وگرنه محاسبه مبهم می‌شود.
 */

const fa = (n: number | string) => Number(n).toLocaleString('fa-IR')

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

type BracketDraft = { up_to: string; rate: string }

const EMPTY_BRACKETS: BracketDraft[] = [{ up_to: '', rate: '' }]

/** درصدِ نمایشی ← کسرِ ذخیره‌شده. ۷٫۵ ⇄ ۰٫۰۷۵ */
const toFraction = (percent: string) => String(Number(percent || 0) / 100)
const toPercent = (fraction: string) => String(Number(fraction || 0) * 100)

export function TaxTablesPage({ token }: { token: string }) {
  const [rows, setRows] = useState<TaxTableRecord[] | null>(null)
  const [groups, setGroups] = useState<PayrollTaxGroupRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)

  const [editing, setEditing] = useState<TaxTableRecord | null>(null)
  const [title, setTitle] = useState('')
  const [title2, setTitle2] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [groupId, setGroupId] = useState('')
  const [purpose, setPurpose] = useState('salary')
  const [brackets, setBrackets] = useState<BracketDraft[]>(EMPTY_BRACKETS)

  async function refresh() {
    try {
      const [tables, taxGroups] = await Promise.all([fetchTaxTables(token), fetchPayrollTaxGroups(token)])
      setRows(tables)
      setGroups(taxGroups)
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  function clearForm() {
    setEditing(null)
    setTitle('')
    setTitle2('')
    setEffectiveFrom('')
    setGroupId('')
    setPurpose('salary')
    setBrackets(EMPTY_BRACKETS)
    setMsg(null)
  }

  function edit(table: TaxTableRecord) {
    setEditing(table)
    setTitle(table.title)
    setTitle2(table.title2)
    setEffectiveFrom(table.effective_from)
    setGroupId(table.tax_group_id ?? '')
    setPurpose(table.calculation_type)
    setBrackets(
      table.brackets.length
        ? table.brackets.map((b) => ({ up_to: b.up_to ?? '', rate: toPercent(b.rate) }))
        : EMPTY_BRACKETS,
    )
    setMsg(null)
  }

  function setBracket(index: number, patch: Partial<BracketDraft>) {
    setBrackets((list) => list.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      const body = {
        title: title.trim(),
        title2: title2.trim(),
        effective_from: effectiveFrom,
        tax_group_id: groupId || null,
        calculation_type: purpose,
        brackets: brackets.map((b) => ({
          up_to: b.up_to.trim() === '' ? null : b.up_to.trim(),
          rate: toFraction(b.rate),
        })),
      }
      if (editing) {
        await updateTaxTable(token, editing.id, body)
        setMsg({ text: `«${body.title}» به‌روز شد.`, kind: 'ok' })
      } else {
        await createTaxTable(token, body)
        setMsg({ text: `«${body.title}» ساخته شد.`, kind: 'ok' })
      }
      clearForm()
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function remove(table: TaxTableRecord) {
    setBusy(true)
    setMsg(null)
    try {
      await deleteTaxTable(token, table.id)
      setMsg({ text: `«${table.title}» حذف شد.`, kind: 'ok' })
      if (editing?.id === table.id) clearForm()
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Calculator}
      title="جداول مالیات"
      description="پله‌های مالیات حقوق، به تفکیک تاریخ اجرا، گروه مالیاتی و نوع محاسبه."
    >
      <SectionCard
        icon={Calculator}
        title={editing ? `ویرایش «${editing.title}»` : 'جدول مالیات جدید'}
        description="سالِ تازه جدولِ تازه می‌گیرد؛ جدولِ پارسال دست نمی‌خورد تا محاسبه‌ی گذشته بازتولیدپذیر بماند."
      >
        <form className="cmp-form" onSubmit={submit}>
          <label>
            <span>عنوان *</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
          </label>
          <label>
            <span>عنوان دوم</span>
            <input value={title2} onChange={(e) => setTitle2(e.target.value)} maxLength={200} />
            <span className="field-hint">فقط نمایشی — در انتخاب جدول هیچ نقشی ندارد.</span>
          </label>
          <label>
            <span>تاریخ اجرا *</span>
            <JalaliDatePicker value={effectiveFrom} onChange={setEffectiveFrom} />
          </label>
          <label>
            <span>گروه مالیاتی</span>
            <select value={groupId} onChange={(e) => setGroupId(e.target.value)}>
              <option value="">— پیش‌فرض (حکم‌های بدون گروه) —</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
            <span className="field-hint">
              هر گروه نرخ‌های خودش را دارد؛ نرخ از همین جدول می‌آید، نه از ضربِ درصد گروه.
            </span>
          </label>
          <label>
            <span>نوع محاسبه *</span>
            <select value={purpose} onChange={(e) => setPurpose(e.target.value)}>
              {Object.entries(TAX_CALC_PURPOSE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <span className="field-hint">جدولِ حقوق برای عیدی به کار نمی‌رود — آستانه‌هایشان یکی نیست.</span>
          </label>

          <div className="cmp-form-wide">
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>از مبلغ</th>
                    <th>تا مبلغ</th>
                    <th>نرخ (٪)</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {brackets.map((row, index) => {
                    const previous = index === 0 ? '0' : brackets[index - 1].up_to
                    return (
                      <tr key={index}>
                        {/* «از مبلغ» ورودی نیست: سقفِ پله‌ی قبل است. دو نما از یک عدد نمی‌سازیم. */}
                        <td className="card-title num" data-label="از مبلغ">
                          {previous.trim() === '' ? '—' : fa(previous)}
                        </td>
                        <td className="num" data-label="تا مبلغ">
                          <input
                            dir="ltr"
                            value={row.up_to}
                            onChange={(e) => setBracket(index, { up_to: e.target.value })}
                            placeholder="نامحدود"
                          />
                        </td>
                        <td className="num" data-label="نرخ (٪)">
                          <input
                            dir="ltr"
                            value={row.rate}
                            onChange={(e) => setBracket(index, { rate: e.target.value })}
                            placeholder="۷٫۵"
                          />
                        </td>
                        <td className="card-actions">
                          <button
                            type="button"
                            onClick={() => setBrackets((list) => list.filter((_, i) => i !== index))}
                            disabled={brackets.length === 1}
                          >
                            <Trash2 size={13} /> حذف
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="muted">
              «تا مبلغِ» ردیفِ آخر را خالی بگذارید تا نامحدود شود. سقف‌ها باید صعودی باشند.
            </p>
            <button type="button" onClick={() => setBrackets((list) => [...list, { up_to: '', rate: '' }])}>
              <Plus size={13} /> افزودن پله
            </button>
          </div>

          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !title.trim() || !effectiveFrom.trim()}>
              <Save size={13} /> {editing ? 'ذخیره تغییرات' : 'ثبت جدول'}
            </button>
            {editing ? (
              <button type="button" onClick={clearForm} disabled={busy}>
                انصراف
              </button>
            ) : null}
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard
        icon={Calculator}
        title={rows ? `${fa(rows.length)} جدول مالیات` : 'در حال بارگذاری…'}
        description="جدول‌های سال‌های گذشته عمداً می‌مانند."
      >
        <AsyncBlock
          loading={rows == null}
          error={error}
          empty={rows != null && rows.length === 0}
          emptyText="هنوز جدول مالیاتی ثبت نشده. برای سال جاری یکی بسازید."
        >
          {rows == null || rows.length === 0 ? (
            <EmptyState icon={Calculator} text="هنوز جدول مالیاتی ثبت نشده. برای سال جاری یکی بسازید." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>عنوان</th>
                    <th>تاریخ اجرا</th>
                    <th>گروه مالیاتی</th>
                    <th>نوع محاسبه</th>
                    <th>پله‌ها</th>
                    <th>وضعیت</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((table) => (
                    <tr key={table.id}>
                      <td className="card-title" data-label="عنوان">{table.title}</td>
                      <td data-label="تاریخ اجرا">{formatJalali(table.effective_from)}</td>
                      <td data-label="گروه مالیاتی">{table.tax_group_name || 'پیش‌فرض'}</td>
                      <td data-label="نوع محاسبه">
                        {TAX_CALC_PURPOSE_LABELS[table.calculation_type] ?? table.calculation_type}
                      </td>
                      <td className="num" data-label="پله‌ها">{fa(table.brackets.length)}</td>
                      <td data-label="وضعیت">{table.in_use ? 'در استفاده' : '—'}</td>
                      <td className="card-actions">
                        <button type="button" onClick={() => edit(table)}>ویرایش</button>
                        <button
                          type="button"
                          onClick={() => void remove(table)}
                          disabled={busy || table.in_use}
                          title={table.in_use ? 'فیش‌هایی به این جدول استناد کرده‌اند' : undefined}
                        >
                          <Trash2 size={13} /> حذف
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
