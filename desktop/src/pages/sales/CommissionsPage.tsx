import { useMemo, useRef, useState } from 'react'
import { Calculator, CircleDollarSign, Minus, RefreshCw, Users, Wallet } from 'lucide-react'

import {
  createCommissionRule,
  createCommissionRun,
  fetchCommissionPreview,
  fetchCommissionRules,
  fetchFiscalYears,
  fetchMembers,
  updateCommissionRule,
  type CommissionRow,
  type CommissionRule,
} from '../../api'
import { DefSheet, type DefCol } from '../../components/DefSheet'
import { DocFooter } from '../../components/DocFooter'
import { SectionCard } from '../../components/SectionCard'
import { Tabs } from '../../components/Tabs'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { CountBadge } from '../../components/form/FormKit'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import type { DefSpec, DefValues } from '../../lib/defSheet'
import { formatJalali } from '../../lib/jalali'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { AsyncBlock, Metric, OpsPage, RangeCells, fa, faInt, useAsync, useRange, type Msg } from '../accounting/kit'

/**
 * «پورسانت» — قاعده‌ها و محاسبه در یک صفحه با دو برگه (مرحله‌ی ۲ِ مرتب‌سازیِ زیرمنوها، ۱۴۰۵/۰۷/۱۸).
 *
 * پیش از این دو منو بود («قاعده پورسانت» و «محاسبه پورسانت») به‌اضافه‌ی دفترِ «قواعد پورسانت» که همان جدولِ فرمِ اول را
 * دوباره نشان می‌داد. حالا:
 * - **قاعده‌ها** برگه‌ی اکسلیِ تعریف است (`DefSheet`): هر فروشنده یک ردیف، نرخ و مبنا و وضعیت همان‌جا ویرایش می‌شوند
 *   (سرور تا امروز فقط ساختن داشت، پس نرخِ اشتباه راهِ اصلاح نداشت). دفترِ «قواعد پورسانت» دو نمای یک داده بود و رفت.
 * - **محاسبه** پیش‌نمایشِ سرور است و «ذخیره‌ی محاسبه» (الگوی ج): بازه و شرح در سربرگ، گریدِ فقط‌خواندنی با انتخاب و جمعِ
 *   انتخاب، و نوارِ پایینِ هم‌خط با ستون‌ها. محاسبه‌ی ذخیره‌شده عوض نمی‌شود — دفترش «محاسبه‌های پورسانت» است.
 */
export function CommissionsPage({ token }: { token: string }) {
  return (
    <OpsPage
      canvas
      icon={Wallet}
      title="پورسانت"
      description="نرخِ پورسانتِ هر فروشنده و محاسبه‌ی دوره‌ای‌اش — هر کدام یک برگه. محاسبه‌ی ذخیره‌شده دیگر عوض نمی‌شود."
    >
      <Tabs
        syncPage="commissions"
        tabs={[
          { key: 'rules', label: 'قاعده‌های پورسانت', icon: Wallet, content: <RulesTab token={token} /> },
          { key: 'calc', label: 'محاسبه پورسانت', icon: Calculator, content: <CalcTab token={token} /> },
        ]}
      />
    </OpsPage>
  )
}

// ═══════════════════ قاعده‌ها ═══════════════════

const BASIS_OPTS = [
  { value: 'net', label: 'خالصِ فاکتور' },
  { value: 'profit', label: 'سودِ ناخالص' },
]
const basisLabel = (b: string) => BASIS_OPTS.find((o) => o.value === b)?.label ?? b

const RULE_SPEC: DefSpec = {
  text: ['salesperson_id', 'rate', 'basis', 'description'],
  bools: ['is_active'],
  numeric: ['rate'],
  defaults: { basis: 'net' },
  required: [
    { field: 'salesperson_id', label: 'فروشنده' },
    { field: 'rate', label: 'نرخ' },
  ],
  search: ['salesperson_name', 'description'],
}

const s = (v: unknown) => (v === undefined || v === null ? '' : String(v)).trim()

function RulesTab({ token }: { token: string }) {
  const list = useAsync(() => fetchCommissionRules(token), [token])
  const members = useAsync(
    () => fetchMembers(token).then((r) => r.members.map((m) => ({ value: m.user_id, label: m.name || m.email }))),
    [token],
  )
  const rows = list.data ?? null
  //: هر فروشنده یک قاعده دارد (یکتاییِ سرور): ردیفِ تازه فقط کسانی را پیشنهاد می‌دهد که هنوز قاعده ندارند.
  const taken = useMemo(() => new Set((rows ?? []).map((r) => r.salesperson_id)), [rows])
  const cols: DefCol<CommissionRule>[] = [
    {
      id: 'person',
      label: 'فروشنده',
      title: 'کاربرِ برنامه که فاکتور به نامش ثبت می‌شود. هر فروشنده یک قاعده دارد.',
      kind: 'select',
      field: 'salesperson_id',
      emptyOption: '— انتخاب فروشنده —',
      options: (v) => {
        const current = s(v.salesperson_id)
        const free = (members.data ?? []).filter((m) => m.value === current || !taken.has(m.value))
        //: فروشنده‌ای که دیگر عضو نیست هنوز نامش روی قاعده‌اش دیده می‌شود.
        return current && !free.some((m) => m.value === current)
          ? [{ value: current, label: s(v.salesperson_name) || '—' }, ...free]
          : free
      },
      newOnly: 'فروشنده‌ی قاعده‌ی ثبت‌شده عوض نمی‌شود — برای فروشنده‌ی دیگر قاعده‌ی تازه بسازید.',
      enter: true,
    },
    {
      id: 'rate',
      label: 'نرخ (٪)',
      title: 'درصد، از صفر تا صد. تغییرش فقط روی محاسبه‌های بعدی می‌نشیند.',
      kind: 'number',
      field: 'rate',
      decimal: true,
      w: '13%',
      enter: true,
    },
    {
      id: 'basis',
      label: 'مبنا',
      title: 'خالصِ فاکتور یا سودِ ناخالص — انتخابش اثرِ بزرگی روی عدد دارد.',
      kind: 'select',
      field: 'basis',
      options: () => BASIS_OPTS,
      w: '17%',
    },
    { id: 'description', label: 'شرح', kind: 'text', field: 'description', w: '26%', mhide: true, narrow: true },
    { id: 'active', label: 'وضعیت', title: 'قاعده‌ی غیرفعال در محاسبه نمی‌آید.', kind: 'toggle', field: 'is_active', w: '9%' },
  ]
  return (
    <>
      <section className="cc-head">
        <div className="cc-summary">
          <Metric icon={<Users size={14} />} label="فروشنده با قاعده" value={faInt(rows?.length ?? 0)} />
          <Metric icon={<Wallet size={14} />} label="فعال" value={faInt((rows ?? []).filter((r) => r.is_active).length)} tone="in" />
        </div>
      </section>
      <DefSheet<CommissionRule>
        sheetId="commissionrules"
        spec={RULE_SPEC}
        cols={cols}
        autoCol="person"
        slots={[['num', 'person'], ['rate'], ['basis'], ['description'], ['active', 'actions']]}
        rows={rows}
        error={list.error}
        reload={list.reload}
        valuesOf={(r) => ({ ...r, rate: String(Number(r.rate)) }) as DefValues}
        check={(v) => {
          const n = Number(s(v.rate))
          return Number.isFinite(n) && n > 0 && n <= 100 ? null : 'نرخ باید بیشتر از صفر و حداکثر ۱۰۰ باشد.'
        }}
        create={(v) =>
          createCommissionRule(token, {
            salesperson_id: s(v.salesperson_id),
            rate: Number(s(v.rate)),
            basis: s(v.basis) === 'profit' ? 'profit' : 'net',
            is_active: true,
            description: s(v.description),
          })
        }
        update={(r, p) =>
          updateCommissionRule(token, r.id, {
            ...('rate' in p ? { rate: Number(s(p.rate)) } : {}),
            ...('basis' in p ? { basis: s(p.basis) === 'profit' ? 'profit' : 'net' } : {}),
            ...('is_active' in p ? { is_active: Boolean(p.is_active) } : {}),
            ...('description' in p ? { description: s(p.description) } : {}),
          })
        }
        //: سرور حذفِ قاعده را ندارد؛ غیرفعال‌کردن همان اثر را دارد و سابقه را نگه می‌دارد.
        remove={() => Promise.reject(new Error('قاعده‌ی پورسانت حذف نمی‌شود؛ غیرفعالش کنید.'))}
        removeBlock={() => 'قاعده‌ی پورسانت حذف نمی‌شود؛ غیرفعالش کنید تا در محاسبه‌های بعدی نیاید.'}
        labelOf={(v) => s(v.salesperson_name) || 'قاعده‌ی تازه'}
        icon={Wallet}
        title="قاعده‌های پورسانت"
        tip="هر فروشنده یک ردیف: نرخ (درصد) و مبنا — خالصِ فاکتور یا سودِ ناخالص. خانه‌ها همین‌جا ویرایش می‌شوند و «ذخیره تغییرات» (Ctrl+S) همه را یک‌جا می‌فرستد. محاسبه‌ای که قبلاً ذخیره شده نرخِ زمانِ خودش را نگه داشته و با این تغییرها عوض نمی‌شود."
        unit="قاعده"
        newPlaceholder="قاعده‌ی تازه: فروشنده را انتخاب کنید…"
        findPlaceholder="جست‌وجو: فروشنده، شرح"
      />
    </>
  )
}

// ═══════════════════ محاسبه ═══════════════════

const LAYOUT = { fixed: ['rowhead'], auto: 'person' } as const

/** نوارِ پایین روی گرید: [ردیف…فروشنده] [مبنا، نرخ] [فاکتور] [مبلغِ مبنا] [پورسانت]. */
const CALC_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('rowhead') + w('person'), w('basis') + w('rate'), w('invoices'), w('base'), w('amount')]
}

const sumOf = (rows: readonly CommissionRow[], f: 'base_amount' | 'amount') => rows.reduce((t, r) => t + Number(r[f] || 0), 0)

function CalcTab({ token }: { token: string }) {
  const range = useRange('month')
  const years = useAsync(() => fetchFiscalYears(token), [token])
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const ready = Boolean(range.from && range.to)
  const preview = useAsync(
    () =>
      ready
        ? fetchCommissionPreview(token, range.from as string, range.to as string)
        : Promise.resolve({ date_from: '', date_to: '', total_amount: '0', rows: [] as CommissionRow[] }),
    [token, range.from, range.to, ready],
  )
  const formRef = useRef<HTMLFormElement>(null)
  const cw = useColumnWidths('cubita.grid.commissioncalc.shares', LAYOUT)
  const { selected, click, clear } = useRowSelection()
  useAlignToGrid(formRef, '.jf-foot--cols', { table: '.cm-sheet', slots: CALC_SLOTS })

  const rows = preview.data?.rows ?? []
  const total = Number(preview.data?.total_amount ?? 0)
  const order = rows.map((r) => r.salesperson_id)
  const picked = rows.filter((r) => selected.has(r.salesperson_id))
  const canSave = ready && !preview.loading && rows.length > 0 && !busy

  async function save() {
    if (!canSave) return
    const span = `${formatJalali(range.from as string)} تا ${formatJalali(range.to as string)}`
    if (!window.confirm(`پورسانتِ ${span} با جمعِ ${fa(total)} ریال ذخیره شود؟ محاسبه‌ی ذخیره‌شده دیگر عوض نمی‌شود.`)) return
    setBusy(true)
    try {
      await createCommissionRun(token, { date_from: range.from as string, date_to: range.to as string, note: note.trim() })
      setMsg({ text: `محاسبه‌ی ${span} ذخیره شد — در «محاسبه‌های پورسانت» است.`, kind: 'ok' })
      setNote('')
      clear()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const head = (id: string, label: string, next?: string, num = false) => (
    <th data-col={id} className={num ? 'num' : undefined}>
      {label}
      {next && cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const tone = !ready || rows.length === 0 ? 'empty' : 'ok'

  return (
    <form
      ref={formRef}
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        void save()
      }}
      onKeyDown={(e) => {
        //: Ctrl+S مثلِ بقیه‌ی برگه‌ها — همان دکمه، همان تأیید.
        if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') {
          e.preventDefault()
          void save()
        }
      }}
    >
      <SectionCard
        icon={Calculator}
        title="پیش‌نمایشِ پورسانت"
        tip="پورسانتِ هر فروشنده در بازه، از فاکتورهای ثبت‌شده به نامش و قاعده‌ی فعالش. تا «ذخیره‌ی محاسبه» نزنید چیزی ثبت نمی‌شود. روی شماره‌ی ردیف‌ها کلیک کنید تا جمعِ همان‌ها را ببینید."
        badge={ready ? <CountBadge>{faInt(rows.length)} فروشنده</CountBadge> : undefined}
        actions={
          <button type="button" className="btn-ghost jk-trigger" onClick={preview.reload} title="فاکتور یا قاعده‌ای عوض شده؟ دوباره حساب کنید.">
            <RefreshCw size={15} aria-hidden="true" /> محاسبه‌ی دوباره
          </button>
        }
      >
        <div className="jh-bar jh-bar--report" role="group" aria-label="بازه و شرحِ محاسبه">
          <div className="jh-row rh-row--range">
            <RangeCells range={range} years={years.data ?? []} />
          </div>
          <div className="jh-row jh-row--sub">
            <div className="jh-field jh-field--grow">
              <label className="jh-label" htmlFor="cm-note">
                شرحِ محاسبه
              </label>
              <input
                id="cm-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                //: Enter در این خانه فرم را می‌فرستاد — ذخیره فقط با دکمه یا Ctrl+S.
                onKeyDown={(e) => {
                  if (e.key === 'Enter') e.preventDefault()
                }}
                placeholder="مثلاً «پورسانتِ مهرِ ۱۴۰۵»"
                maxLength={200}
              />
            </div>
          </div>
        </div>

        <AsyncBlock
          loading={preview.loading && !preview.data}
          error={preview.data ? null : preview.error}
          empty={rows.length === 0}
          emptyText={
            ready
              ? 'در این بازه پورسانتی نیست — یا فاکتوری با فروشنده ثبت نشده، یا قاعده‌ی فعالی برای فروشنده‌اش نیست.'
              : 'بازه را انتخاب کنید — پورسانت برای «همه» حساب نمی‌شود.'
          }
        >
          <div className="table-scroll ef-table-wrap">
            <table
              ref={cw.frame}
              className={`cards-on-mobile ef-table xl-grid cm-sheet${preview.loading ? ' is-loading' : ''}`}
            >
              <colgroup>
                <col className="cm-c-rowhead" style={cw.col('rowhead')} />
                <col style={cw.col('person')} />
                <col className="cm-c-basis" style={cw.col('basis')} />
                <col className="cm-c-rate" style={cw.col('rate')} />
                <col className="cm-c-count" style={cw.col('invoices')} />
                <col className="cm-c-money" style={cw.col('base')} />
                <col className="cm-c-money" style={cw.col('amount')} />
              </colgroup>
              <thead>
                <tr>
                  <th className="xl-rowhead card-hide" data-col="rowhead" aria-label="انتخاب" />
                  {head('person', 'فروشنده', 'basis')}
                  {head('basis', 'مبنا', 'rate')}
                  {head('rate', 'نرخ', 'invoices', true)}
                  {head('invoices', 'فاکتور', 'base', true)}
                  {head('base', 'مبلغِ مبنا', 'amount', true)}
                  {head('amount', 'پورسانت', undefined, true)}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const on = selected.has(r.salesperson_id)
                  return (
                    <tr key={r.salesperson_id} className={on ? 'is-selected' : undefined}>
                      <td className="xl-rowhead card-hide">
                        <button
                          type="button"
                          className="xl-rowhead-btn"
                          aria-pressed={on}
                          aria-label={`انتخابِ ${r.salesperson_name}`}
                          onClick={(e) => click(order, r.salesperson_id, modsOf(e))}
                        >
                          {faInt(i + 1)}
                        </button>
                      </td>
                      <td className="card-title" data-label="فروشنده">
                        {r.salesperson_name}
                      </td>
                      <td data-label="مبنا">{basisLabel(r.basis)}</td>
                      <td className="num" data-label="نرخ">
                        {fa(r.rate)}٪
                      </td>
                      <td className="num" data-label="فاکتور">
                        {faInt(r.invoice_count)}
                      </td>
                      <td className="num" data-label="مبلغِ مبنا">
                        {fa(r.base_amount)}
                      </td>
                      <td className="num" data-label="پورسانت">
                        {fa(r.amount)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {picked.length > 0 && (
            <SelectionBar count={picked.length} unit="فروشنده" onClear={clear}>
              <span>
                مبلغِ مبنا <b className="num">{fa(sumOf(picked, 'base_amount'))}</b>
              </span>
              <span>
                پورسانت <b className="num">{fa(sumOf(picked, 'amount'))}</b>
              </span>
            </SelectionBar>
          )}
        </AsyncBlock>
      </SectionCard>

      <DocFooter
        tone={tone}
        columns
        statusEnd
        submitting={busy}
        submittingLabel="در حال ذخیره…"
        submitLabel="ذخیره‌ی محاسبه"
        submitDisabled={!canSave}
        shortcut
        message={msg}
        groupLabel="خلاصه‌ی پورسانت"
        statusLabel="پورسانتِ بازه"
        statusKey={`${tone}-${total}`}
        status={
          preview.loading && !preview.data ? (
            'در حال محاسبه…'
          ) : rows.length > 0 ? (
            <>
              <CircleDollarSign aria-hidden="true" /> پورسانتِ بازه
            </>
          ) : (
            <>
              <Minus aria-hidden="true" /> بی‌پورسانت
            </>
          )
        }
        sub={rows.length > 0 ? { main: fa(total) } : { main: ready ? 'چیزی برای ذخیره نیست' : 'بازه را انتخاب کنید' }}
        stats={[
          { label: 'جمعِ فاکتورها', value: faInt(rows.reduce((t, r) => t + r.invoice_count, 0)), className: 'jb-stat--a' },
          { label: 'جمعِ مبلغِ مبنا', value: fa(sumOf(rows, 'base_amount')), className: 'jb-stat--b' },
        ]}
      />
    </form>
  )
}
