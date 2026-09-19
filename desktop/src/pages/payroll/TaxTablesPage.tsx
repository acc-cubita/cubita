import { useEffect, useState } from 'react'
import { Calculator, Plus, Save, Trash2, X } from 'lucide-react'
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
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { NumberInput } from '../../components/NumberInput'
import { SectionCard } from '../../components/SectionCard'
import { ActionBar, FormField, FormGrid, FormStatus, TabHead } from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
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
//: toFixed: بدونِ آن ۰٫۰۷ × ۱۰۰ می‌شد ۷٫۰۰۰۰۰۰۰۰۰۰۰۰۰۰۱ و همان در فیلد می‌نشست.
const toPercent = (fraction: string) => String(Number((Number(fraction || 0) * 100).toFixed(4)))
//: «۲۳۰۴۰۰۰۰۰۰٫۰۰»ِ سرور ← «۲۳۰۴۰۰۰۰۰۰». صفرهای اعشار در فیلد فقط شلوغی‌اند.
const toAmount = (v: string | null) => (v == null || v === '' ? '' : String(Number(v)))

export function TaxTablesPage({ token }: { token: string }) {
  const [rows, setRows] = useState<TaxTableRecord[] | null>(null)
  const [groups, setGroups] = useState<PayrollTaxGroupRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [listMsg, setListMsg] = useState<Msg>(null)
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
        ? table.brackets.map((b) => ({ up_to: toAmount(b.up_to), rate: toPercent(b.rate) }))
        : EMPTY_BRACKETS,
    )
    setMsg(null)
    document.getElementById('tt-title')?.focus()
  }

  function setBracket(index: number, patch: Partial<BracketDraft>) {
    setBrackets((list) => list.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const missing = firstMissing([
      [title, 'tt-title', 'عنوانِ جدول را وارد کنید.'],
      [effectiveFrom, 'tt-date', 'تاریخِ اجرا را انتخاب کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      } else {
        await createTaxTable(token, body)
      }
      clearForm()
      setMsg({ text: editing ? `«${body.title}» به‌روز شد.` : `«${body.title}» ساخته شد.`, kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function remove(table: TaxTableRecord) {
    setBusy(true)
    setListMsg(null)
    try {
      await deleteTaxTable(token, table.id)
      setListMsg({ text: `«${table.title}» حذف شد.`, kind: 'ok' })
      if (editing?.id === table.id) clearForm()
      await refresh()
    } catch (err) {
      setListMsg({ text: errText(err), kind: 'err' })
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
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          <SectionCard
            icon={Calculator}
            title={editing ? `ویرایش «${editing.title}»` : 'جدول مالیات جدید'}
            tip="سالِ تازه جدولِ تازه می‌گیرد؛ جدولِ پارسال دست نمی‌خورد تا محاسبه‌ی گذشته بازتولیدپذیر بماند."
          >
            <FormGrid>
              <FormField id="tt-title" label="عنوان" required>
                {(id) => <input id={id} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />}
              </FormField>
              <FormField label="عنوان دوم" tip="فقط نمایشی — در انتخاب جدول هیچ نقشی ندارد.">
                {(id) => <input id={id} value={title2} onChange={(e) => setTitle2(e.target.value)} maxLength={200} />}
              </FormField>
              <FormField id="tt-date" label="تاریخ اجرا" required>
                {(id) => <JalaliDatePicker id={id} value={effectiveFrom} onChange={setEffectiveFrom} />}
              </FormField>
              <FormField
                label="گروه مالیاتی"
                tip="هر گروه نرخ‌های خودش را دارد؛ نرخ از همین جدول می‌آید، نه از ضربِ درصد گروه."
              >
                {(id) => (
                  <select id={id} value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                    <option value="">— پیش‌فرض (حکم‌های بدون گروه) —</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                )}
              </FormField>
              <FormField label="نوع محاسبه" required tip="جدولِ حقوق برای عیدی به کار نمی‌رود — آستانه‌هایشان یکی نیست.">
                {(id) => (
                  <select id={id} value={purpose} onChange={(e) => setPurpose(e.target.value)}>
                    {Object.entries(TAX_CALC_PURPOSE_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                )}
              </FormField>
            </FormGrid>

            <div className="ef-block">
              <TabHead
                title="پله‌ها"
                tip="«تا مبلغِ» ردیفِ آخر را خالی بگذارید تا نامحدود شود. سقف‌ها باید صعودی باشند."
                actions={
                  <button type="button" onClick={() => setBrackets((list) => [...list, { up_to: '', rate: '' }])}>
                    <Plus size={14} /> افزودن پله
                  </button>
                }
              />
              {/* audit-r9-exempt: پله‌ها همیشه دستِ‌کم یک ردیف دارند و به‌جای حالتِ خالی
                  دکمه‌ی «افزودن پله» می‌گیرند. */}
              <div className="table-scroll">
                <table className="cards-on-mobile">
                  <thead>
                    <tr>
                      <th>از مبلغ</th>
                      <th>تا مبلغ (ریال)</th>
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
                          <td className="num" data-label="تا مبلغ (ریال)">
                            <NumberInput
                              aria-label="تا مبلغ (ریال)"
                              allowDecimal
                              value={row.up_to}
                              onChange={(v) => setBracket(index, { up_to: v })}
                              placeholder="∞"
                            />
                          </td>
                          <td className="num" data-label="نرخ (٪)">
                            <NumberInput
                              aria-label="نرخ (٪)"
                              allowDecimal
                              value={row.rate}
                              onChange={(v) => setBracket(index, { rate: v })}
                              placeholder="۷٫۵"
                            />
                          </td>
                          <td className="card-actions">
                            <button
                              type="button"
                              className="ef-icon-btn"
                              onClick={() => setBrackets((list) => list.filter((_, i) => i !== index))}
                              disabled={brackets.length === 1}
                              aria-label="حذفِ پله"
                              title="حذفِ پله"
                            >
                              <Trash2 size={15} />
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </SectionCard>
          <ActionBar status={<FormStatus msg={msg} />}>
            {editing && (
              <button type="button" className="ef-btn-secondary" onClick={clearForm} disabled={busy}>
                <X size={15} /> انصراف
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={busy}>
              <Save size={15} /> {busy ? 'در حال ثبت…' : editing ? 'ذخیره تغییرات' : 'ثبت جدول'}
            </button>
          </ActionBar>
        </form>

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
                        <td className="card-title" data-label="عنوان">
                          {table.title}
                        </td>
                        <td data-label="تاریخ اجرا">{formatJalali(table.effective_from)}</td>
                        <td data-label="گروه مالیاتی">{table.tax_group_name || 'پیش‌فرض'}</td>
                        <td data-label="نوع محاسبه">
                          {TAX_CALC_PURPOSE_LABELS[table.calculation_type] ?? table.calculation_type}
                        </td>
                        <td className="num" data-label="پله‌ها">
                          {fa(table.brackets.length)}
                        </td>
                        <td data-label="وضعیت">
                          {table.in_use ? <span className="status-badge tone-success">در استفاده</span> : '—'}
                        </td>
                        <td className="card-actions">
                          <button type="button" onClick={() => edit(table)}>
                            ویرایش
                          </button>
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
          <Note msg={listMsg} />
        </SectionCard>
      </div>
    </OpsPage>
  )
}
