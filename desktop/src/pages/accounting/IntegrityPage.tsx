import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  ChevronDown,
  Download,
  ListTree,
  Printer,
  Scale,
  ShieldCheck,
  XCircle,
} from 'lucide-react'

import { fetchFiscalYears, fetchIntegrityReport, type IntegrityReport, type ReportFilters } from '../../api'
import { AccountLedgerDrawer } from '../../components/AccountLedgerDrawer'
import { CountBadge } from '../../components/form/FormKit'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { KardexDrawer } from '../../components/KardexDrawer'
import { ReportFilterBar } from '../../components/ReportFilterBar'
import { Amount } from '../../components/ReportViews'
import { SavedViewBar } from '../../components/SavedViewBar'
import { SectionCard } from '../../components/SectionCard'
import { downloadCsv } from '../../lib/csv'
import {
  SEVERITY_LABEL,
  TARGET_LABEL,
  checkTone,
  integrityCsv,
  integritySummary,
  sheetRows,
  targetsOf,
  type CheckTone,
  type Target,
} from '../../lib/integritySheet'
import { formatJalali, todayIso } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { AsyncBlock, OpsPage, RangeCells, faAmount, faInt, useAsync, useRange } from './kit'

const TONE_ICON: Record<CheckTone, typeof CheckCircle2> = { ok: CheckCircle2, error: XCircle, warning: AlertTriangle }
const TONE_CHIP: Record<CheckTone, string> = { ok: 'xl-check--ok', error: 'xl-check--off', warning: 'xl-check--due' }
/** جابه‌جاییِ PageUp/PageDown. */
const PAGE_STEP = 10

/**
 * بررسیِ یکپارچگیِ دفتر — §۲۷، با تمِ اکسلی (الگوی «د» از `cubita-excel-theme`).
 *
 * **گزارش است، نه گارد.** هیچ‌چیز این‌جا مسدود نمی‌شود؛ همان تصمیمی که «خلافِ ماهیت» گرفت. سندِ نامتوازن را نمی‌شود با
 * بستنِ راهِ ثبت درست کرد — آن سند از قبل ثبت شده است. کاری که این‌جا می‌شود پیدا کردن و **بردنِ کاربر به خودِ سند** است؛
 * گزارشی که بگوید «اشکالی هست» ولی نگوید کجا، کارِ حسابدار را بیشتر می‌کند.
 *
 * - **یک گرید برای همه‌ی بررسی‌ها**: هر بررسی ردیفِ سرگروه (وضعیت، عنوان، شمارِ یافته، شرحِ کوتاه) و یافته‌هایش زیرش؛
 *   نُه کارتِ جدا که هفت‌تایشان «چیزی پیدا نکرد» می‌گفتند، یافته‌ی واقعی را ته صفحه می‌بردند.
 * - **«جمعِ دفتر»** در پانویسِ چسبنده: جمعِ بدهکار و بستانکار و اختلاف با نتیجه‌ی کل («سالم» / «نیازمندِ رسیدگی»).
 * - هشدار نتیجه را قرمز نمی‌کند، چون سندِ بی‌ردیف هیچ مبلغی را جابه‌جا نکرده — دیده می‌شود ولی دفتر را ناسالم نمی‌کند.
 */
export function IntegrityPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const range = useRange('year')
  const [filters, setFilters] = useState<ReportFilters>({})
  const [onlyFindings, setOnlyFindings] = useState(false)
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set())
  const [entryId, setEntryId] = useState<string | null>(null)
  const [drill, setDrill] = useState<{ id: string; code: string; name: string } | null>(null)
  const [kardexItem, setKardexItem] = useState<{ id: string; sku: string; name: string } | null>(null)

  const years = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  const scope: ReportFilters = { ...filters, dateFrom: range.from, dateTo: range.to }
  const report = useAsync<IntegrityReport>(
    () => fetchIntegrityReport(token, scope),
    [token, range.from, range.to, JSON.stringify(filters)],
  )
  const data = report.data
  const checks = useMemo(() => data?.checks ?? [], [data])
  const summary = integritySummary(checks)
  const rows = useMemo(() => sheetRows(checks, { onlyFindings, closed }), [checks, onlyFindings, closed])

  const open = (t: Target) => {
    if (t.kind === 'entry') setEntryId(t.id)
    else if (t.kind === 'item') setKardexItem({ id: t.id, sku: t.sku, name: t.name })
    else setDrill({ id: t.id, code: t.code, name: t.name })
  }
  const toggle = (key: string) =>
    setClosed((s) => {
      const next = new Set(s)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  // ── صفحه‌کلید: ↑↓ روی سرگروه‌ها و یافته‌ها؛ Enter سرگروه را باز/بسته و یافته را باز می‌کند ──
  const gridRef = useRef<HTMLDivElement>(null)
  const [activeRow, setActiveRow] = useState(0)
  const active = Math.min(activeRow, Math.max(0, rows.length - 1))
  const scopeKey = JSON.stringify([range.from, range.to, filters, onlyFindings])
  useEffect(() => setActiveRow(0), [scopeKey])
  const followActive = useRef(false)
  useEffect(() => {
    if (!followActive.current) return
    followActive.current = false
    document.getElementById(`ig-row-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])
  const moveTo = (i: number) => {
    followActive.current = true
    setActiveRow(Math.max(0, Math.min(rows.length - 1, i)))
  }
  const activate = (i: number) => {
    const r = rows[i]
    if (!r) return
    if (r.kind === 'check') {
      if (!r.check.ok) toggle(r.check.key)
    } else if (r.kind === 'finding') {
      const [first] = targetsOf(r.row)
      if (first) open(first)
    }
  }
  const drawerOpen = entryId !== null || drill !== null || kardexItem !== null
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    //: کشوها کیبوردِ خودشان را دارند (Esc)؛ این‌جا نباید همان کلید را دوباره بخورد.
    if (drawerOpen || rows.length === 0) return
    const last = rows.length - 1
    switch (e.key) {
      case 'ArrowDown':
      case 'ArrowUp':
        e.preventDefault()
        moveTo(active + (e.key === 'ArrowDown' ? 1 : -1))
        break
      case 'PageDown':
      case 'PageUp':
        e.preventDefault()
        moveTo(active + (e.key === 'PageDown' ? PAGE_STEP : -PAGE_STEP))
        break
      case 'Home':
      case 'End':
        e.preventDefault()
        moveTo(e.key === 'Home' ? 0 : last)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        activate(active)
        break
    }
  }

  //: چاپ همه‌ی یافته‌ها را می‌خواهد، نه فقط سرگروه‌های باز؛ اول همه باز می‌شوند و بعد از نقش‌بستن چاپ می‌شود.
  const [printPending, setPrintPending] = useState(false)
  useEffect(() => {
    if (!printPending) return
    setPrintPending(false)
    window.print()
  }, [printPending])
  const print = () => {
    setClosed(new Set())
    setPrintPending(true)
  }
  const exportCsv = () => {
    const csv = integrityCsv(checks)
    downloadCsv(`yekparchegi-${range.from ?? 'all'}`, csv.headers, csv.rows)
  }

  const rangeText = range.from
    ? `${formatJalali(range.from)} تا ${formatJalali(range.to ?? todayIso())}`
    : `از ابتدای دفتر تا ${formatJalali(range.to ?? todayIso())}`
  const verdict =
    summary.errors > 0
      ? `${faInt(summary.errors)} خطا${summary.warnings ? ` و ${faInt(summary.warnings)} هشدار` : ''}`
      : summary.warnings > 0
        ? `${faInt(summary.warnings)} هشدار`
        : `همه‌ی ${faInt(checks.length)} بررسی سالم`

  return (
    <OpsPage
      canvas
      icon={ShieldCheck}
      title="بررسی یکپارچگی"
      description="دفتر را از چند زاویه می‌سنجد و ناسازگاری‌ها را نشان می‌دهد. چیزی مسدود نمی‌شود؛ تصمیم با شماست."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="بازه و فیلترهای بررسی یکپارچگی">
          <div className="jh-row rh-row--range">
            <RangeCells range={range} years={years.data ?? []} />
          </div>
          <div className="jh-row jh-row--sub rh-row--filters">
            <ReportFilterBar token={token} filters={filters} onChange={setFilters} variant="cells" />
          </div>
          <div className="jh-row jh-row--sub rh-row--tools">
            <div className="jh-field rh-views">
              <span className="jh-label">نماهای ذخیره‌شده</span>
              <SavedViewBar token={token} viewKey="accounting.integrity" filters={filters} range={range} setFilters={setFilters} />
            </div>
            {onNavigate && (
              <div className="jh-field rh-go">
                <span className="jh-label">رفتن به</span>
                <div className="rh-links">
                  <button type="button" onClick={() => onNavigate('acctchart')}>
                    <ListTree size={14} aria-hidden="true" /> درختواره حساب‌ها
                  </button>
                  <button type="button" onClick={() => onNavigate('balancereport')}>
                    <Scale size={14} aria-hidden="true" /> گزارش ترازها
                  </button>
                  <button type="button" onClick={() => onNavigate('ledgerreport')}>
                    <BookOpenCheck size={14} aria-hidden="true" /> گزارش دفتر
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      }
    >
      <SectionCard
        icon={ShieldCheck}
        title="نتیجه‌ی بررسی‌ها"
        description={data ? `${rangeText} · ${verdict}` : rangeText}
        badge={
          data && summary.findings > 0 ? <CountBadge accent>{faInt(summary.findings)} یافته</CountBadge> : undefined
        }
        tip="هر بررسی یک ردیفِ سرگروه است و یافته‌هایش زیرش؛ روی سرگروه کلیک کنید (یا Enter) تا یافته‌هایش باز یا بسته شوند. روی هر یافته کلیک کنید تا خودِ سند، کاردکسِ کالا یا دفترِ حساب باز شود. «خطا» دفتر را «نیازمندِ رسیدگی» می‌کند و «هشدار» فقط دیده می‌شود."
        actions={
          <div className="jg-head-actions">
            <div className="cc-presets ig-view" role="group" aria-label="نمایشِ بررسی‌ها">
              <button
                type="button"
                className={onlyFindings ? '' : 'is-active'}
                aria-pressed={!onlyFindings}
                onClick={() => setOnlyFindings(false)}
              >
                همه‌ی بررسی‌ها
              </button>
              <button
                type="button"
                className={onlyFindings ? 'is-active' : ''}
                aria-pressed={onlyFindings}
                onClick={() => setOnlyFindings(true)}
              >
                فقط یافته‌ها
              </button>
            </div>
            <button type="button" className="ef-btn-secondary" onClick={exportCsv} disabled={!data}>
              <Download size={14} /> خروجی CSV
            </button>
            <button type="button" className="ef-btn-secondary" onClick={print} disabled={!data}>
              <Printer size={14} /> چاپ
            </button>
          </div>
        }
      >
        <AsyncBlock loading={report.loading && !data} error={data ? null : report.error}>
          {data && (
            <>
              <div
                ref={gridRef}
                tabIndex={rows.length > 0 ? 0 : -1}
                className={`table-scroll ef-table-wrap rp-scroll lr-scroll${report.loading ? ' is-loading' : ''}`}
                onKeyDown={onKey}
                aria-label="بررسی‌های یکپارچگی — ↑↓ حرکت، Enter بازوبستنِ بررسی یا بازکردنِ یافته"
              >
                <table className="ef-table xl-grid cards-on-mobile rp-table ig-sheet">
                  <colgroup>
                    <col className="ig-c-num" />
                    <col className="ig-c-label" />
                    <col />
                    <col className="ig-c-amt" />
                    <col className="ig-c-amt" />
                    <col className="ig-c-amt" />
                    <col className="ig-c-go" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th className="xl-rowhead" aria-label="ردیف" />
                      <th>مورد</th>
                      <th>توضیح</th>
                      <th className="num">بدهکار</th>
                      <th className="num">بستانکار</th>
                      <th className="num">اختلاف</th>
                      <th aria-label="رفتن به" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.length === 0 ? (
                      <tr>
                        <td className="card-full rp-status" colSpan={7}>
                          هیچ بررسی‌ای یافته‌ای ندارد — دفتر در این دامنه سالم است.
                        </td>
                      </tr>
                    ) : (
                      rows.map((r, i) => {
                        const on = i === active ? ' is-active' : ''
                        if (r.kind === 'check') {
                          const c = r.check
                          const tone = checkTone(c)
                          const Icon = TONE_ICON[tone]
                          return (
                            <tr
                              key={c.key}
                              id={`ig-row-${i}`}
                              className={`ig-check ig-check--${tone}${c.ok ? '' : ' acc-row--clickable'}${on}`}
                              aria-expanded={c.ok ? undefined : r.open}
                              //: شرحِ بررسیِ سالم فقط راهنماست؛ هفت شرحِ «چیزی پیدا نشد» یافته‌ی واقعی را زیرِ خود می‌بردند.
                              title={c.ok ? c.description : undefined}
                              onClick={() => {
                                setActiveRow(i)
                                if (!c.ok) toggle(c.key)
                              }}
                            >
                              <td className="card-full" colSpan={7}>
                                <div className="ig-head">
                                  <span className="ig-toggle" aria-hidden="true">
                                    {!c.ok && <ChevronDown size={14} />}
                                  </span>
                                  <Icon size={15} className="ig-icon" aria-hidden="true" />
                                  <b className="ig-title">{c.title}</b>
                                  <span className={`xl-check ${TONE_CHIP[tone]}`}>
                                    {c.ok ? 'بدونِ یافته' : `${faInt(c.count)} مورد · ${SEVERITY_LABEL[c.severity]}`}
                                  </span>
                                </div>
                                {!c.ok && c.description && <p className="ig-desc">{c.description}</p>}
                              </td>
                            </tr>
                          )
                        }
                        if (r.kind === 'more')
                          return (
                            <tr key={`${r.check.key}-more`} className="ig-more">
                              <td className="card-full rp-status" colSpan={7}>
                                {`${faInt(r.check.rows.length)} مورد از ${faInt(r.check.count)} نشان داده شده؛ برای دیدنِ بقیه بازه یا فیلتر را محدودتر کنید.`}
                              </td>
                            </tr>
                          )
                        const f = r.row
                        const targets = targetsOf(f)
                        return (
                          <tr
                            key={`${r.check.key}-${f.entry_id ?? f.account_id ?? f.item_id ?? ''}-${r.index}`}
                            id={`ig-row-${i}`}
                            className={`ig-finding${targets.length ? ' acc-row--clickable' : ''}${on}`}
                            title={targets.length ? `بازکردنِ ${TARGET_LABEL[targets[0].kind]}` : undefined}
                            onClick={() => {
                              setActiveRow(i)
                              if (targets[0]) open(targets[0])
                            }}
                          >
                            <td className="xl-rowhead card-hide">{faInt(r.index + 1)}</td>
                            <td className="card-title" title={f.label}>
                              {f.label}
                            </td>
                            <td className="card-wide" data-label="توضیح">
                              {f.detail || '—'}
                            </td>
                            <td className="num" data-label="بدهکار">
                              {faAmount(f.debit)}
                            </td>
                            <td className="num" data-label="بستانکار">
                              {faAmount(f.credit)}
                            </td>
                            <td className="num" data-label="اختلاف">
                              <Amount value={f.difference} />
                            </td>
                            <td className="card-actions">
                              <span className="ig-go">
                                {targets.map((t) => (
                                  <button
                                    key={t.kind}
                                    type="button"
                                    tabIndex={-1}
                                    onClick={(ev) => {
                                      ev.stopPropagation()
                                      setActiveRow(i)
                                      open(t)
                                    }}
                                  >
                                    {TARGET_LABEL[t.kind]}
                                  </button>
                                ))}
                              </span>
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                  <tfoot>
                    <tr className="rp-total">
                      <td className="xl-rowhead card-hide" />
                      <td className="card-title" colSpan={2}>
                        جمعِ دفتر
                        <span className={`xl-check ${data.ok ? 'xl-check--ok' : 'xl-check--off'}`} role={data.ok ? undefined : 'alert'}>
                          {data.ok ? <CheckCircle2 size={13} aria-hidden="true" /> : <AlertTriangle size={13} aria-hidden="true" />}{' '}
                          {data.ok ? 'سالم' : 'نیازمندِ رسیدگی'}
                        </span>
                      </td>
                      <td className="num" data-label="جمعِ بدهکار">
                        {faAmount(data.total_debit)}
                      </td>
                      <td className="num" data-label="جمعِ بستانکار">
                        {faAmount(data.total_credit)}
                      </td>
                      <td className="num" data-label="اختلاف">
                        <Amount value={data.difference} />
                      </td>
                      <td className="card-hide" />
                    </tr>
                  </tfoot>
                </table>
              </div>
              {rows.length > 0 && (
                <p className="ab-keys lr-keys">
                  <kbd>↑</kbd>
                  <kbd>↓</kbd> ردیف · <kbd>Enter</kbd> یا کلیک بازوبستنِ بررسی یا بازکردنِ یافته
                </p>
              )}
            </>
          )}
        </AsyncBlock>
      </SectionCard>

      {entryId && <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />}
      {drill && (
        //: کشوی دفتر همان دامنه‌ی بررسی را می‌گیرد، وگرنه کاربر عددی را باز می‌کرد و دفتری می‌دید که با آن نمی‌خواند.
        <AccountLedgerDrawer token={token} account={drill} filters={scope} onClose={() => setDrill(null)} />
      )}
      {kardexItem && <KardexDrawer token={token} item={kardexItem} onClose={() => setKardexItem(null)} />}
    </OpsPage>
  )
}
