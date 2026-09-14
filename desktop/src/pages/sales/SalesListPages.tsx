import { Fragment, useDeferredValue, useMemo, useRef, useState } from 'react'
import {
  BadgePercent,
  Ban,
  Boxes,
  Calculator,
  ClipboardList,
  Copy,
  Eye,
  FileSpreadsheet,
  Layers,
  Lock,
  PackagePlus,
  PenLine,
  Percent,
  Search,
  Ship,
  Tags,
  TrendingUp,
  Trash2,
  Undo2,
  Users,
  Wallet,
} from 'lucide-react'
import {
  bulkChangePrices,
  fetchBundles,
  fetchCommissionRules,
  fetchCommissionRuns,
  fetchContacts,
  fetchCustoms,
  fetchDiscountGroups,
  fetchNoteDuplicateDraft,
  fetchNotes,
  fetchPriceAnnouncements,
  fetchPricingFactors,
  fetchSaleTypes,
  fetchSalesInvoices,
  fetchSalesReturns,
  ISSUE_RETURN_PREFILL_KEY,
  newIdempotencyKey,
  NOTE_PREFILL_KEY,
  SALES_RETURN_PHYSICAL_LABELS,
  voidNote,
  voidSalesReturn,
  type BulkPriceMode,
  type CreditDebitNote,
  type IssueReturnPrefill,
  type NotePrefill,
  type SaleTypeAccounts,
  type SalesReturnRecord,
} from '../../api'
import type { PageKey } from '../../lib/navModel'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { PriceRuleTable } from '../../components/PriceRuleTable'
import { Pager, usePagination } from '../../components/Pager'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { formatJalali, toFaDigits } from '../../lib/jalali'

/** وضعیتِ مالیِ سندِ برگشت. «باطل» عمداً از «تسویه‌نشده» جداست — یکی پولی است که
 *  هنوز نرفته، دیگری پولی که اصلاً قرار نیست برود. */
const RETURN_STATUS_LABELS: Record<string, string> = {
  unsettled: 'تسویه‌نشده',
  partially_settled: 'تسویهٔ جزئی',
  fully_settled: 'تسویه‌شده',
  voided: 'باطل‌شده',
}
import {
  ActiveChip,
  AsyncBlock,
  Metric,
  Note,
  OpsPage,
  RangeBar,
  fa,
  faAmount,
  faInt,
  useAsync,
  useRange,
  type Msg,
} from '../accounting/kit'

/**
 * دفترهای نظیرِ عملیاتِ فروش — «هر عملیاتِ رکوردساز، یک فهرست».
 *
 * مرزِ این‌ها با صفحه‌های عملیات جدی است: آنجا **ثبت** می‌شود و اینجا **مرور**.
 * پس این صفحه‌ها فرم ندارند (جز کنشِ ابطالِ اعلامیه که خودش رکوردِ تازه نمی‌سازد)،
 * و در عوض بازه، فیلتر، جست‌وجو و جمع دارند.
 *
 * «تخفیف‌ها و عوامل» عمداً یک دفترِ مشترک است، چون دو منوی عملیات در یک جدول
 * می‌نویسند — استثنای دومِ قاعده‌ی نظیر.
 */

// ═══════════════════════ کمکی‌های مشترک ═══════════════════════

/** هفت اسلاتِ حسابِ نوعِ فروش — این‌جا فقط شمرده می‌شوند؛ تنظیمشان در صفحه‌ی عملیات است. */
const SALE_TYPE_ACCOUNT_KEYS = [
  'goods_revenue_account_id',
  'service_revenue_account_id',
  'goods_return_account_id',
  'service_return_account_id',
  'goods_discount_account_id',
  'service_discount_account_id',
  'addition_account_id',
] as const satisfies readonly (keyof SaleTypeAccounts)[]

function inRange(day: string, from?: string, to?: string): boolean {
  if (from && day < from) return false
  if (to && day > to) return false
  return true
}

// ═════════════════ دفترِ فاکتورهای فروش ═════════════════

export function SalesInvoiceListPage({ token }: { token: string }) {
  const range = useRange('month')
  const [status, setStatus] = useState<'' | 'open' | 'closed' | 'void'>('')
  const [search, setSearch] = useState('')
  const list = useAsync(() => fetchSalesInvoices(token), [token])
  const contacts = useAsync(() => fetchContacts(token), [token])
  const names = useMemo(
    () => new Map((contacts.data ?? []).map((c) => [c.id, c.name])),
    [contacts.data],
  )

  const rows = useMemo(() => {
    const t = search.trim()
    return (list.data ?? [])
      .filter((i) => inRange(i.invoice_date, range.from, range.to))
      .filter((i) =>
        status === 'open'
          ? !i.closed_at && !i.voided_at
          : status === 'closed'
            ? !!i.closed_at
            : status === 'void'
              ? !!i.voided_at
              : true,
      )
      .filter(
        (i) =>
          !t ||
          String(i.number ?? '').includes(t) ||
          (names.get(i.contact_id ?? '') ?? '').includes(t),
      )
      .sort((a, b) => b.invoice_date.localeCompare(a.invoice_date))
  }, [list.data, range.from, range.to, status, search, names])

  const pg = usePagination(rows, 20, `${range.from}${range.to}${status}${search}`)
  const net = rows.filter((i) => !i.voided_at).reduce((s, i) => s + Number(i.total_amount || 0), 0)

  return (
    <OpsPage
      icon={ClipboardList}
      title="فاکتورهای فروش"
      description="دفترِ کاملِ فاکتورها — باز، بسته و باطل. ثبتِ فاکتورِ تازه از کارتِ «عملیات» انجام می‌شود."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              <label className="acc-inline-field">
                وضعیت
                <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
                  <option value="">همه</option>
                  <option value="open">باز</option>
                  <option value="closed">بسته</option>
                  <option value="void">باطل</option>
                </select>
              </label>
            }
          />
          <div className="cc-summary">
            <Metric icon={<ClipboardList size={14} />} label="فاکتور" value={faInt(rows.length)} />
            <Metric icon={<TrendingUp size={14} />} label="خالص" value={faAmount(net)} tone="in" />
          </div>
        </div>
      }
    >
      <SectionCard icon={ClipboardList} title="فاکتورها" description={`${faInt(rows.length)} ردیف`}>
        <div className="acc-filters">
          <label className="acc-search">
            <Search size={14} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="شماره یا نامِ طرف حساب"
            />
          </label>
        </div>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="فاکتوری با این شرایط پیدا نشد."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>تاریخ</th>
                  <th>طرف حساب</th>
                  <th>خالص</th>
                  <th>مالیات</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((i) => (
                  <tr key={i.id} className={i.voided_at ? 'acc-row--void' : ''}>
                    <td className="card-title" data-label="شماره">
                      {fa(i.number ?? 0)}
                    </td>
                    <td data-label="تاریخ">{formatJalali(i.invoice_date)}</td>
                    <td data-label="طرف حساب">{names.get(i.contact_id ?? '') ?? '—'}</td>
                    <td className="num" data-label="خالص">
                      {faAmount(i.total_amount)}
                    </td>
                    <td className="num" data-label="مالیات">
                      {faAmount(i.tax_amount)}
                    </td>
                    <td data-label="وضعیت">
                      <span
                        className={`status-badge ${
                          i.voided_at ? 'tone-danger' : i.closed_at ? 'tone-default' : 'tone-success'
                        }`}
                      >
                        {i.voided_at ? 'باطل' : i.closed_at ? 'بسته' : 'باز'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ دفترِ برگشت از فروش ═════════════════

/** برگشتِ فیزیکی کنارِ وضعیتِ مالی — دو حقیقتِ مستقل (فصلِ «برگشت خروج انبار» §۲۱). */
function physicalLabel(r: SalesReturnRecord): string {
  const status = r.physical_status ?? 'inline'
  const label = SALES_RETURN_PHYSICAL_LABELS[status] ?? status
  const remaining = Number(r.physical_remaining_qty || 0)
  return remaining > 0 && status !== 'inline'
    ? `${label} · مانده ${remaining.toLocaleString('fa-IR', { maximumFractionDigits: 3 })}`
    : label
}

export function SalesReturnListPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate?: (page: PageKey, section?: string | null) => void
}) {
  const range = useRange('month')
  const list = useAsync(() => fetchSalesReturns(token), [token])
  const rows = useMemo(
    () =>
      (list.data ?? [])
        .filter((r) => inRange(r.return_date, range.from, range.to))
        .sort((a, b) => b.return_date.localeCompare(a.return_date)),
    [list.data, range.from, range.to],
  )
  const pg = usePagination(rows, 20, `${range.from}${range.to}`)
  //: برگشتِ باطل‌شده در جمع نمی‌آید — وگرنه سرصفحه عددی می‌گوید که دفتر نمی‌گوید.
  const total = rows.reduce((s, r) => (r.voided_at ? s : s + Number(r.total_amount || 0)), 0)
  const openTotal = rows.reduce((s, r) => (r.voided_at ? s : s + Number(r.remaining_amount || 0)), 0)

  return (
    <OpsPage
      icon={Undo2}
      title="فاکتورهای برگشتی"
      description="دفترِ برگشت از فروش — سندِ تجاری با سندِ معکوسِ خودش. کالا با «برگشت خروج انبار» به انبار برمی‌گردد و ستونِ «برگشت به انبار» می‌گوید چه مقدار واقعاً برگشته."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<Undo2 size={14} />} label="برگشتی" value={faInt(rows.length)} />
            <Metric icon={<TrendingUp size={14} />} label="جمع" value={faAmount(total)} tone="out" />
            <Metric icon={<Undo2 size={14} />} label="ماندهٔ باز" value={faAmount(openTotal)} />
          </div>
        </div>
      }
    >
      <SectionCard icon={Undo2} title="برگشتی‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="در این بازه برگشتی ثبت نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>تاریخ</th>
                  <th>مبلغ</th>
                  <th>مالیات</th>
                  {/* سه عددِ جدا: جمعِ برگشت، آنچه واقعاً پرداخت شده، و ماندهٔ باز.
                      هیچ‌کدام ستونِ ذخیره‌شده نیستند؛ سرور از منبع می‌خواندشان. */}
                  <th>پرداخت‌شده</th>
                  <th>ماندهٔ برگشت</th>
                  <th>وضعیت</th>
                  <th>برگشت به انبار</th>
                  <th>شرح</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.id} className={r.voided_at ? 'acc-row--void' : ''}>
                    <td className="card-title" data-label="شماره">
                      {fa(r.number ?? 0)}
                    </td>
                    <td data-label="تاریخ">{formatJalali(r.return_date)}</td>
                    <td className="num" data-label="مبلغ">
                      {faAmount(r.total_amount)}
                    </td>
                    <td className="num" data-label="مالیات">
                      {faAmount(r.tax_amount)}
                    </td>
                    <td className="num" data-label="پرداخت‌شده">
                      {faAmount(r.settled_amount)}
                    </td>
                    <td className="num" data-label="ماندهٔ برگشت">
                      {faAmount(r.remaining_amount)}
                    </td>
                    <td data-label="وضعیت">
                      {RETURN_STATUS_LABELS[r.financial_status] ?? r.financial_status}
                    </td>
                    <td data-label="برگشت به انبار">{r.voided_at ? '—' : physicalLabel(r)}</td>
                    <td className="card-wide" data-label="شرح">
                      {r.description || '—'}
                    </td>
                    <td className="card-actions" data-label="عملیات">
                      {!r.voided_at &&
                        onNavigate &&
                        r.stock_mode === 'issue_return' &&
                        Number(r.physical_remaining_qty || 0) > 0 && (
                          <button
                            type="button"
                            onClick={() => {
                              //: فقط زمینه منتقل می‌شود؛ برگشتِ انبار سندِ مستقلِ خودش است.
                              const prefill: IssueReturnPrefill = { kind: 'sales_return', id: r.id, return_type: 'sale' }
                              sessionStorage.setItem(ISSUE_RETURN_PREFILL_KEY, JSON.stringify(prefill))
                              onNavigate('inventory', 'issue-returns')
                            }}
                          >
                            <PackagePlus size={13} /> ثبت برگشت به انبار
                          </button>
                        )}
                      {!r.voided_at && (
                        <button
                          type="button"
                          className="danger"
                          onClick={() => {
                            const reason = window.prompt('دلیلِ ابطالِ این برگشت؟')
                            if (reason === null) return
                            void voidSalesReturn(token, r.id, reason).then(
                              () => list.reload(),
                              (err: unknown) =>
                                window.alert(err instanceof Error ? err.message : 'خطای ناشناخته'),
                            )
                          }}
                        >
                          <Ban size={13} /> ابطال
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
    </OpsPage>
  )
}

// ═════════════════ انواعِ فروش ═════════════════

export function SaleTypeListPage({ token }: { token: string }) {
  const list = useAsync(() => fetchSaleTypes(token), [token])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20)

  return (
    <OpsPage
      icon={Tags}
      title="انواع فروش"
      description="دفترِ نوع‌های تعریف‌شده و پیش‌فرض‌هایشان. تعریفِ نوعِ تازه از کارتِ «عملیات» انجام می‌شود."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Tags size={14} />} label="نوع" value={faInt(rows.length)} />
            <Metric
              icon={<Tags size={14} />}
              label="فعال"
              value={faInt(rows.filter((r) => r.is_active).length)}
              tone="in"
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={Tags} title="نوع‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="نوعی تعریف نشده. از «نوع فروش» در کارتِ عملیات بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>کد</th>
                  <th>مهلتِ تسویه</th>
                  <th>نرخِ مالیات</th>
                  <th>حساب‌ها</th>
                  <th>توضیح</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="نام">
                      {r.name}
                      {r.title2 ? <div className="entity-sub">{r.title2}</div> : null}
                    </td>
                    <td data-label="کد">{r.code || '—'}</td>
                    <td className="num" data-label="مهلتِ تسویه">
                      {r.due_days === 0 ? 'نقدی' : `${faInt(r.due_days)} روز`}
                    </td>
                    <td className="num" data-label="نرخِ مالیات">
                      {r.default_tax_rate == null ? '—' : `${fa(r.default_tax_rate)}٪`}
                    </td>
                    <td className="num" data-label="حساب‌ها">
                      {SALE_TYPE_ACCOUNT_KEYS.filter((k) => r[k]).length === 0 ? (
                        <span className="muted">پیش‌فرض</span>
                      ) : (
                        `${faInt(SALE_TYPE_ACCOUNT_KEYS.filter((k) => r[k]).length)} از ${faInt(
                          SALE_TYPE_ACCOUNT_KEYS.length,
                        )}`
                      )}
                    </td>
                    <td className="card-wide" data-label="توضیح">
                      {r.description || '—'}
                    </td>
                    <td data-label="وضعیت">
                      <ActiveChip active={r.is_active} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════ تخفیف‌ها و عوامل افزاینده — یک دفترِ مشترک با فیلتر ═══════

export function PricingFactorListPage({ token }: { token: string }) {
  const [kind, setKind] = useState<'' | 'discount' | 'markup'>('')
  const list = useAsync(() => fetchPricingFactors(token), [token])
  const rows = useMemo(
    () => (list.data ?? []).filter((f) => !kind || f.kind === kind),
    [list.data, kind],
  )
  const pg = usePagination(rows, 20, kind)

  return (
    <OpsPage
      icon={Percent}
      title="تخفیف‌ها و عوامل افزاینده"
      description="یک دفتر برای هر دو، چون در یک جدول ثبت می‌شوند و تنها فرقشان جهتِ اثر است."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <div className="cc-presets">
              {(
                [
                  ['', 'همه'],
                  ['discount', 'تخفیف'],
                  ['markup', 'افزاینده'],
                ] as const
              ).map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  className={kind === k ? 'is-active' : ''}
                  onClick={() => setKind(k)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-summary">
            <Metric
              icon={<Percent size={14} />}
              label="تخفیف"
              value={faInt((list.data ?? []).filter((f) => f.kind === 'discount').length)}
              tone="out"
            />
            <Metric
              icon={<BadgePercent size={14} />}
              label="افزاینده"
              value={faInt((list.data ?? []).filter((f) => f.kind === 'markup').length)}
              tone="in"
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={Percent} title="عامل‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="عاملی تعریف نشده. از «تخفیف جدید» یا «عامل افزاینده جدید» بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>جهت</th>
                  <th>مقدار</th>
                  <th>دامنه</th>
                  <th>اعتبار</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((f) => (
                  <tr key={f.id}>
                    <td className="card-title" data-label="نام">
                      {f.name}
                    </td>
                    <td data-label="جهت">
                      <span className={`status-badge ${f.kind === 'discount' ? 'tone-warning' : 'tone-default'}`}>
                        {f.kind === 'discount' ? 'تخفیف' : 'افزاینده'}
                      </span>
                    </td>
                    <td className="num" data-label="مقدار">
                      {f.mode === 'percent' ? `${fa(f.value)}٪` : faAmount(f.value)}
                    </td>
                    <td data-label="دامنه">
                      {f.scope === 'all' ? 'همه‌ی کالاها' : f.scope === 'item' ? 'یک کالا' : 'یک گروه'}
                    </td>
                    <td data-label="اعتبار">
                      {f.valid_from || f.valid_to
                        ? `${f.valid_from ? formatJalali(f.valid_from) : '…'} تا ${
                            f.valid_to ? formatJalali(f.valid_to) : '…'
                          }`
                        : 'بی‌کران'}
                    </td>
                    <td data-label="وضعیت">
                      <ActiveChip active={f.is_active} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ گروه‌های کالای تخفیف ═════════════════

export function DiscountGroupListPage({ token }: { token: string }) {
  const list = useAsync(() => fetchDiscountGroups(token), [token])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20)

  return (
    <OpsPage
      icon={Layers}
      title="گروه‌های کالای تخفیف"
      description="گروه‌های ساخته‌شده و تعدادِ کالای هرکدام."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Layers size={14} />} label="گروه" value={faInt(rows.length)} />
            <Metric
              icon={<Boxes size={14} />}
              label="مجموعِ عضویت"
              value={faInt(rows.reduce((s, g) => s + g.item_count, 0))}
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={Layers} title="گروه‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="گروهی ساخته نشده. از «گروه کالای تخفیف جدید» بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>تعدادِ کالا</th>
                  <th>توضیح</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((g) => (
                  <tr key={g.id}>
                    <td className="card-title" data-label="نام">
                      {g.name}
                    </td>
                    <td className="num" data-label="تعدادِ کالا">
                      {faInt(g.item_count)}
                    </td>
                    <td className="card-wide" data-label="توضیح">
                      {g.description || '—'}
                    </td>
                    <td data-label="وضعیت">
                      <ActiveChip active={g.is_active} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ اعلامیه‌های قیمت ═════════════════

/** حالت‌های دیالوگِ «تغییر فی»، با برچسبِ فارسی. */
const BULK_MODE_LABELS: Record<BulkPriceMode, string> = {
  increase_percent: 'افزایش — درصدی',
  increase_amount: 'افزایش — مبلغی',
  decrease_percent: 'کاهش — درصدی',
  decrease_amount: 'کاهش — مبلغی',
  fixed: 'مبلغِ ثابت',
  none: 'بدونِ تغییر (فقط رند)',
}

/** دقتِ رند — «رقمِ اعشار» روی قیمتِ ریالیِ صحیح معنا ندارد. */
const ROUNDING_STEPS = [1, 10, 100, 1_000, 10_000]

export function PriceAnnouncementListPage({ token }: { token: string }) {
  const list = useAsync(() => fetchPriceAnnouncements(token), [token])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20)
  const [openId, setOpenId] = useState('')
  const [bulkFor, setBulkFor] = useState('')
  const [mode, setMode] = useState<BulkPriceMode>('increase_percent')
  const [value, setValue] = useState('')
  const [rounding, setRounding] = useState(1)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  // کلید به *این فرمان* گره می‌خورد نه به هر تلاشِ شبکه‌ای: اگر پاسخ گم شود و
  // کاربر دوباره بزند، همان کلید می‌رود و «۲۰٪» دوباره اعمال نمی‌شود.
  const bulkKey = useRef(newIdempotencyKey())

  function openBulk(id: string) {
    setBulkFor(id === bulkFor ? '' : id)
    setMsg(null)
    setValue('')
    bulkKey.current = newIdempotencyKey()
  }

  async function applyBulk(id: string) {
    setBusy(true)
    setMsg(null)
    try {
      const res = await bulkChangePrices(
        token,
        id,
        { mode, value: Number(value) || 0, rounding },
        bulkKey.current,
      )
      setMsg(
        res.replayed
          ? 'این فرمان قبلاً اجرا شده بود؛ دوباره اعمال نشد.'
          : `${faInt(res.changed)} قاعده به‌روزرسانی شد.`,
      )
      if (!res.replayed) bulkKey.current = newIdempotencyKey()
      list.reload()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="اعلامیه‌های قیمت"
      description="همه‌ی اعلامیه‌ها به‌ترتیبِ تاریخِ اجرا. اعلامیه‌ی تازه جای قبلی را نمی‌گیرد؛ کنارش می‌نشیند."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<FileSpreadsheet size={14} />} label="اعلامیه" value={faInt(rows.length)} />
            <Metric
              icon={<Boxes size={14} />}
              label="مجموعِ ردیف"
              value={faInt(rows.reduce((s, p) => s + p.line_count, 0))}
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={FileSpreadsheet} title="اعلامیه‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="اعلامیه‌ای ثبت نشده. از «اعلامیه قیمت» در کارتِ عملیات بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>تاریخِ اجرا</th>
                  <th>تعدادِ قاعده</th>
                  <th>توضیح</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((p) => (
                  <Fragment key={p.id}>
                    <tr className={p.is_active ? '' : 'acc-row--void'}>
                      <td className="card-title" data-label="نام">
                        <button type="button" className="link-like" onClick={() => setOpenId(openId === p.id ? '' : p.id)}>
                          {p.name}
                        </button>
                      </td>
                      <td data-label="تاریخِ اجرا">{formatJalali(p.effective_from)}</td>
                      <td className="num" data-label="تعدادِ قاعده">
                        {faInt(p.line_count)}
                      </td>
                      <td className="card-wide" data-label="توضیح">
                        {p.notes || '—'}
                      </td>
                      <td data-label="وضعیت">
                        <ActiveChip active={p.is_active} />
                      </td>
                      <td className="card-actions">
                        <button type="button" onClick={() => openBulk(p.id)}>
                          <Percent size={13} /> تغییر فی
                        </button>
                      </td>
                    </tr>
                    {bulkFor === p.id && (
                      <tr className="card-full">
                        <td colSpan={6}>
                          <div className="invoice-form form-full">
                            <label>
                              نحوه‌ی تغییر
                              <select value={mode} onChange={(e) => setMode(e.target.value as BulkPriceMode)}>
                                {(Object.keys(BULK_MODE_LABELS) as BulkPriceMode[]).map((m) => (
                                  <option key={m} value={m}>{BULK_MODE_LABELS[m]}</option>
                                ))}
                              </select>
                            </label>
                            <label>
                              مقدار
                              <NumberInput value={value} onChange={setValue} disabled={mode === 'none'} />
                            </label>
                            <label>
                              رندِ فی
                              <select value={rounding} onChange={(e) => setRounding(Number(e.target.value))}>
                                {ROUNDING_STEPS.map((step) => (
                                  <option key={step} value={step}>{`${faInt(step)} ریال`}</option>
                                ))}
                              </select>
                              <span className="field-hint">
                                فی عددِ صحیحِ ریالی است، پس به‌جای رقمِ اعشار، مضربِ رند انتخاب می‌شود.
                              </span>
                            </label>
                            <div className="invoice-form-footer">
                              <button
                                type="button"
                                className="btn-primary"
                                disabled={busy}
                                onClick={() => void applyBulk(p.id)}
                              >
                                اعمال روی همه‌ی قاعده‌های این اعلامیه
                              </button>
                            </div>
                          </div>
                          {msg && <Note msg={{ kind: 'ok', text: msg }} />}
                        </td>
                      </tr>
                    )}
                    {openId === p.id && (
                      <tr className="card-full">
                        <td colSpan={6}>
                          <PriceRuleTable token={token} rules={p.lines} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ بسته‌های محصول ═════════════════

export function BundleListPage({ token }: { token: string }) {
  const list = useAsync(() => fetchBundles(token), [token])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20)

  return (
    <OpsPage
      icon={Boxes}
      title="بسته‌های محصول"
      description="بسته‌های تعریف‌شده و اعضایشان. بسته موجودی ندارد؛ هنگامِ فروش به کالاهای عضو باز می‌شود."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Boxes size={14} />} label="بسته" value={faInt(rows.length)} />
            <Metric
              icon={<Boxes size={14} />}
              label="فعال"
              value={faInt(rows.filter((b) => b.is_active).length)}
              tone="in"
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={Boxes} title="بسته‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="بسته‌ای ساخته نشده. از «بسته محصول جدید» بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>تعدادِ کالا</th>
                  <th>قیمتِ بسته</th>
                  <th>توضیح</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((b) => (
                  <tr key={b.id}>
                    <td className="card-title" data-label="نام">
                      {b.name}
                    </td>
                    <td className="num" data-label="تعدادِ کالا">
                      {faInt(b.lines.length)}
                    </td>
                    <td className="num" data-label="قیمتِ بسته">
                      {b.bundle_price == null ? 'جمعِ اعضا' : faAmount(b.bundle_price)}
                    </td>
                    <td className="card-wide" data-label="توضیح">
                      {b.description || '—'}
                    </td>
                    <td data-label="وضعیت">
                      <ActiveChip active={b.is_active} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ قواعدِ پورسانت ═════════════════

export function CommissionRuleListPage({ token }: { token: string }) {
  const list = useAsync(() => fetchCommissionRules(token), [token])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20)

  return (
    <OpsPage
      icon={Wallet}
      title="قواعد پورسانت"
      description="نرخ و مبنای پورسانتِ هر فروشنده. هر فروشنده یک قاعده دارد."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Users size={14} />} label="فروشنده" value={faInt(rows.length)} />
            <Metric
              icon={<Wallet size={14} />}
              label="فعال"
              value={faInt(rows.filter((r) => r.is_active).length)}
              tone="in"
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={Wallet} title="قاعده‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="قاعده‌ای ثبت نشده. از «پورسانت» در کارتِ عملیات بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>فروشنده</th>
                  <th>نرخ</th>
                  <th>مبنا</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="فروشنده">
                      {r.salesperson_name}
                    </td>
                    <td className="num" data-label="نرخ">
                      {fa(r.rate)}٪
                    </td>
                    <td data-label="مبنا">{r.basis === 'profit' ? 'سودِ ناخالص' : 'خالصِ فاکتور'}</td>
                    <td data-label="وضعیت">
                      <ActiveChip active={r.is_active} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ محاسبه‌های پورسانت ═════════════════

export function CommissionRunListPage({ token }: { token: string }) {
  const list = useAsync(() => fetchCommissionRuns(token), [token])
  const rows = list.data ?? []
  const [openId, setOpenId] = useState<string | null>(null)
  const pg = usePagination(rows, 15)

  return (
    <OpsPage
      icon={Calculator}
      title="محاسبه‌های پورسانت"
      description="محاسبه‌های ذخیره‌شده. عددشان ثابت می‌ماند حتی اگر فاکتوری بعداً باطل شود — چون مبنای پرداخت بوده."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Calculator size={14} />} label="محاسبه" value={faInt(rows.length)} />
            <Metric
              icon={<Wallet size={14} />}
              label="جمعِ کل"
              value={faAmount(rows.reduce((s, r) => s + Number(r.total_amount || 0), 0))}
              tone="out"
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={Calculator} title="محاسبه‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="محاسبه‌ای ذخیره نشده. از «محاسبه پورسانت» انجامش دهید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>بازه</th>
                  <th>فروشنده</th>
                  <th>جمعِ پورسانت</th>
                  <th>توضیح</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="بازه">
                      {formatJalali(r.date_from)} تا {formatJalali(r.date_to)}
                    </td>
                    <td className="num" data-label="فروشنده">
                      {faInt(r.rows.length)}
                    </td>
                    <td className="num" data-label="جمعِ پورسانت">
                      {faAmount(r.total_amount)}
                    </td>
                    <td className="card-wide" data-label="توضیح">
                      {r.note || '—'}
                    </td>
                    <td className="card-actions">
                      <button type="button" onClick={() => setOpenId(openId === r.id ? null : r.id)}>
                        {openId === r.id ? 'بستن' : 'جزئیات'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>

          {openId && (
            <SectionCard
              icon={Users}
              title="سهمِ هر فروشنده"
              description="ارقامِ همان لحظه‌ی محاسبه، نه محاسبه‌ی دوباره."
            >
              <div className="table-scroll">
                <table className="cards-on-mobile acc-table">
                  <thead>
                    <tr>
                      <th>فروشنده</th>
                      <th>فاکتور</th>
                      <th>مبنا</th>
                      <th>مبلغِ مبنا</th>
                      <th>نرخ</th>
                      <th>پورسانت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(rows.find((r) => r.id === openId)?.rows ?? []).map((l) => (
                      <tr key={l.salesperson_id}>
                        <td className="card-title" data-label="فروشنده">
                          {l.salesperson_name}
                        </td>
                        <td className="num" data-label="فاکتور">
                          {faInt(l.invoice_count)}
                        </td>
                        <td data-label="مبنا">{l.basis === 'profit' ? 'سود' : 'خالص'}</td>
                        <td className="num" data-label="مبلغِ مبنا">
                          {faAmount(l.base_amount)}
                        </td>
                        <td className="num" data-label="نرخ">
                          {fa(l.rate)}٪
                        </td>
                        <td className="num" data-label="پورسانت">
                          {faAmount(l.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ اظهارنامه‌های گمرکی ═════════════════

export function CustomsListPage({ token }: { token: string }) {
  const range = useRange('year')
  const list = useAsync(() => fetchCustoms(token), [token])
  const rows = useMemo(
    () => (list.data ?? []).filter((c) => inRange(c.declaration_date, range.from, range.to)),
    [list.data, range.from, range.to],
  )
  const pg = usePagination(rows, 20, `${range.from}${range.to}`)

  return (
    <OpsPage
      icon={Ship}
      title="اظهارنامه‌های گمرکی"
      description="دفترِ اظهارنامه‌های صادراتی و ارزشِ اظهارشده‌ی هرکدام."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<Ship size={14} />} label="اظهارنامه" value={faInt(rows.length)} />
          </div>
        </div>
      }
    >
      <SectionCard icon={Ship} title="اظهارنامه‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="در این بازه اظهارنامه‌ای ثبت نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>تاریخ</th>
                  <th>گمرک</th>
                  <th>مقصد</th>
                  <th>تعرفه</th>
                  <th>ارزش</th>
                  <th>فاکتور</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((c) => (
                  <tr key={c.id}>
                    <td className="card-title" data-label="شماره">
                      <span dir="ltr">{c.declaration_no}</span>
                    </td>
                    <td data-label="تاریخ">{formatJalali(c.declaration_date)}</td>
                    <td data-label="گمرک">{c.customs_office || '—'}</td>
                    <td data-label="مقصد">{c.destination_country || '—'}</td>
                    <td data-label="تعرفه">
                      <span dir="ltr">{c.hs_code || '—'}</span>
                    </td>
                    <td className="num" data-label="ارزش">
                      {faAmount(c.declared_value)} <span dir="ltr">{c.currency_code}</span>
                    </td>
                    <td className="num" data-label="فاکتور">
                      {c.invoice_number ? fa(c.invoice_number) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ اعلامیه‌های بدهکار/بستانکار ═════════════════

/**
 * هر سمتِ اعلامیه، از **ردیف‌هایش**.
 *
 * اعلامیه‌های پیش از مهاجرتِ ۰۱۲۷ ردیف ندارند و سمتشان روی سربرگ بود؛ همان‌ها
 * با `kind` خوانده می‌شوند تا در دفتر گم نشوند.
 */
function noteSide(n: CreditDebitNote, side: 'debit' | 'credit'): string {
  if (n.lines.length === 0) {
    const legacy = (n.kind ?? 'debit') === side
    return legacy ? n.contact_name : '—'
  }
  const names = n.lines.map((l) =>
    side === 'debit'
      ? l.debit_contact_name !== '—'
        ? l.debit_contact_name
        : l.debit_account_name
      : l.credit_contact_name !== '—'
        ? l.credit_contact_name
        : l.credit_account_name,
  )
  return [...new Set(names)].join('، ')
}

/** یک سمتِ یک ردیف: «طرف حساب — کد معین عنوان». */
function lineSide(l: CreditDebitNote['lines'][number], side: 'debit' | 'credit'): string {
  const who = side === 'debit' ? l.debit_contact_name : l.credit_contact_name
  const code = side === 'debit' ? l.debit_account_code : l.credit_account_code
  const name = side === 'debit' ? l.debit_account_name : l.credit_account_name
  return `${who !== '—' ? `${who} — ` : ''}${toFaDigits(code)} ${name}`
}

type NoteAction = { id: string; mode: 'void' | 'correct'; reason: string; date: string }

const NOTE_COLUMNS = 9

export function NoteListPage({ token, onNavigate }: { token: string; onNavigate: (p: PageKey) => void }) {
  const range = useRange('year')
  const [who, setWho] = useState('')
  const [status, setStatus] = useState<'all' | 'active' | 'voided'>('all')
  const [search, setSearch] = useState('')
  const q = useDeferredValue(search.trim())
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [openId, setOpenId] = useState<string | null>(null)
  const [action, setAction] = useState<NoteAction | null>(null)
  const [busy, setBusy] = useState(false)

  const contacts = useAsync(() => fetchContacts(token), [token])
  //: **فیلتر سمتِ سرور.** تا امروز کلِ اعلامیه‌ها کشیده و در مرورگر بریده می‌شدند.
  const list = useAsync(
    () =>
      fetchNotes(token, {
        date_from: range.from || undefined,
        date_to: range.to || undefined,
        contact_id: who || undefined,
        status,
        q: q || undefined,
      }),
    [token, reloadKey, range.from, range.to, who, status, q],
  )
  const rows = list.data ?? []
  const pg = usePagination(rows, 20, `${range.from}${range.to}${who}${status}${q}`)
  const live = rows.filter((n) => !n.voided_at)
  const baseTotal = live.reduce((s, n) => s + Number(n.base_amount || 0), 0)

  const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

  /** «رونوشت» و مرحله‌ی دومِ «اصلاح»: پیش‌نویس از سرور، فرمِ صدور پیش‌پر. */
  async function openDraft(n: CreditDebitNote, corrects: number | null) {
    const draft = await fetchNoteDuplicateDraft(token, n.id)
    const payload: NotePrefill = { draft, corrects }
    try {
      sessionStorage.setItem(NOTE_PREFILL_KEY, JSON.stringify(payload))
    } catch {
      throw new Error('ذخیره‌ی موقتِ مرورگر در دسترس نیست؛ پیش‌نویس به فرم نمی‌رسد.')
    }
    onNavigate('creditnote')
  }

  async function duplicate(n: CreditDebitNote) {
    setMsg(null)
    try {
      await openDraft(n, null)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function confirmAction(n: CreditDebitNote) {
    if (!action) return
    setBusy(true)
    setMsg(null)
    try {
      await voidNote(token, n.id, action.reason.trim(), action.date === n.note_date ? undefined : action.date)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
      setBusy(false)
      return
    }
    setAction(null)
    setReloadKey((k) => k + 1)
    if (action.mode === 'correct') {
      try {
        await openDraft(n, n.number)
        return
      } catch (err) {
        setMsg({
          text: `اعلامیه باطل شد، ولی فرمِ اصلاح باز نشد: ${errText(err)} — از «رونوشت» روی همین ردیف دوباره امتحان کنید.`,
          kind: 'err',
        })
      }
    } else {
      setMsg({ text: `اعلامیه‌ی ${fa(n.number ?? 0)} باطل و سندِ معکوسش ثبت شد.`, kind: 'ok' })
    }
    setBusy(false)
  }

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="اعلامیه‌های بدهکار و بستانکار"
      description="دفترِ اعلامیه‌ها با سندِ حسابداریِ هرکدام. اصلاح با ابطال (سندِ معکوس) و صدورِ دوباره انجام می‌شود، نه با ویرایشِ سند."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              <>
                <label className="acc-inline-field">
                  طرف حساب
                  <select value={who} onChange={(e) => setWho(e.target.value)}>
                    <option value="">همه</option>
                    {(contacts.data ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="acc-inline-field">
                  وضعیت
                  <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
                    <option value="all">همه</option>
                    <option value="active">فعال</option>
                    <option value="voided">باطل‌شده</option>
                  </select>
                </label>
                <label className="acc-inline-field">
                  جست‌وجو
                  <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="شماره یا شرح"
                  />
                </label>
                <button type="button" className="btn-ghost" onClick={() => onNavigate('creditnote')}>
                  <PackagePlus size={14} /> صدورِ اعلامیه
                </button>
              </>
            }
          />
          <div className="cc-summary">
            <Metric icon={<TrendingUp size={14} />} label="جمعِ ریالیِ فعال" value={faAmount(baseTotal)} tone="in" />
            <Metric icon={<FileSpreadsheet size={14} />} label="فعال" value={faInt(live.length)} />
            <Metric icon={<Ban size={14} />} label="باطل‌شده" value={faInt(rows.length - live.length)} />
          </div>
        </div>
      }
    >
      <SectionCard icon={FileSpreadsheet} title="اعلامیه‌ها" description={`${faInt(rows.length)} ردیف`}>
        <Note msg={msg} />
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="با این فیلترها اعلامیه‌ای پیدا نشد. بازه یا طرف حساب را عوض کنید، یا از «صدورِ اعلامیه» یکی بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>تاریخ</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                  <th>مبلغ</th>
                  <th>سند حسابداری</th>
                  <th>شرح</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((n) => (
                  <Fragment key={n.id}>
                    <tr className={n.voided_at ? 'acc-row--void' : ''}>
                      <td className="card-title" data-label="شماره">
                        {fa(n.number ?? 0)}
                      </td>
                      <td data-label="تاریخ">{formatJalali(n.note_date)}</td>
                      <td data-label="بدهکار">{noteSide(n, 'debit')}</td>
                      <td data-label="بستانکار">{noteSide(n, 'credit')}</td>
                      <td className="num" data-label="مبلغ">
                        {n.currency_code === 'IRR' ? (
                          faAmount(n.base_amount)
                        ) : (
                          <>
                            {faAmount(n.amount)} <span dir="ltr">{n.currency_code}</span>
                            <span className="cdn-base">معادل {faAmount(n.base_amount)} ریال</span>
                          </>
                        )}
                      </td>
                      <td data-label="سند حسابداری">
                        {n.journal_entry_number != null
                          ? `${fa(n.journal_entry_number)}${n.journal_entry_date ? ` — ${formatJalali(n.journal_entry_date)}` : ''}`
                          : '—'}
                      </td>
                      <td className="card-wide" data-label="شرح">
                        {n.reason || '—'}
                      </td>
                      <td data-label="وضعیت">
                        {n.voided_at ? (
                          <>
                            <span className="status-badge tone-default">باطل</span>
                            <span className="cdn-void-note">
                              {n.void_entry_number != null && `سندِ معکوس ${fa(n.void_entry_number)}`}
                              {n.void_reason && ` — ${n.void_reason}`}
                              {n.voided_by_name && ` (${n.voided_by_name})`}
                            </span>
                          </>
                        ) : (
                          <span className="status-badge tone-success">فعال</span>
                        )}
                      </td>
                      <td className="card-actions">
                        <button type="button" className="btn-ghost" onClick={() => setOpenId(openId === n.id ? null : n.id)}>
                          <Eye size={13} /> {openId === n.id ? 'بستنِ ردیف‌ها' : 'ردیف‌ها'}
                        </button>
                        {n.lines.length > 0 && (
                          <button type="button" className="btn-ghost" onClick={() => void duplicate(n)}>
                            <Copy size={13} /> رونوشت
                          </button>
                        )}
                        {!n.voided_at && n.lines.length > 0 && (
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => setAction({ id: n.id, mode: 'correct', reason: '', date: n.note_date })}
                          >
                            <PenLine size={13} /> اصلاح
                          </button>
                        )}
                        {!n.voided_at && (
                          <button
                            type="button"
                            className="danger"
                            onClick={() => setAction({ id: n.id, mode: 'void', reason: '', date: n.note_date })}
                          >
                            <Trash2 size={13} /> ابطال
                          </button>
                        )}
                      </td>
                    </tr>
                    {action?.id === n.id && (
                      <tr>
                        <td className="card-full" colSpan={NOTE_COLUMNS}>
                          <div className="cdn-void">
                            <p className="cdn-void-title">
                              {action.mode === 'correct'
                                ? `اصلاحِ اعلامیه‌ی ${fa(n.number ?? 0)}: اول با سندِ معکوس باطل می‌شود، بعد فرمِ صدور با همین ردیف‌ها باز می‌شود تا نسخه‌ی درست را ثبت کنید. سندِ ثبت‌شده ویرایش نمی‌شود.`
                                : `ابطالِ اعلامیه‌ی ${fa(n.number ?? 0)}: یک سندِ معکوس زده می‌شود و اصل سرِ جایش می‌ماند.`}
                            </p>
                            <label>
                              تاریخِ سندِ معکوس
                              <JalaliDatePicker value={action.date} onChange={(d) => setAction({ ...action, date: d })} />
                              <span className="field-hint">پیش‌فرض تاریخِ خودِ اعلامیه است؛ اگر آن دوره بسته شده، تاریخی در دوره‌ی باز بدهید.</span>
                            </label>
                            <label>
                              علتِ ابطال
                              <input
                                type="text"
                                value={action.reason}
                                maxLength={300}
                                onChange={(e) => setAction({ ...action, reason: e.target.value })}
                              />
                              <span className="field-hint">دستِ‌کم سه حرف — در سندِ معکوس و روی اعلامیه می‌ماند.</span>
                            </label>
                            <div className="cdn-void-actions">
                              <button
                                type="button"
                                className="danger"
                                disabled={busy || action.reason.trim().length < 3}
                                onClick={() => void confirmAction(n)}
                              >
                                {action.mode === 'correct' ? 'ابطال و بازکردنِ فرمِ اصلاح' : 'ابطال'}
                              </button>
                              <button type="button" className="btn-ghost" onClick={() => setAction(null)}>
                                انصراف
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                    {openId === n.id && (
                      <tr>
                        <td className="card-full" colSpan={NOTE_COLUMNS}>
                          {n.lines.length === 0 ? (
                            <p className="muted">این اعلامیه از شکلِ قدیمیِ تک‌سمتی است و ردیف ندارد.</p>
                          ) : (
                            <div className="table-scroll">
                              <table className="cards-on-mobile acc-table cdn-lines">
                                <thead>
                                  <tr>
                                    <th>ردیف</th>
                                    <th>بدهکار</th>
                                    <th>بستانکار</th>
                                    <th>مبلغ</th>
                                    <th>معادل ریالی</th>
                                    <th>شرح</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {n.lines.map((l) => (
                                    <tr key={l.id}>
                                      <td className="card-title" data-label="ردیف">
                                        ردیفِ {fa(l.seq)}
                                      </td>
                                      <td data-label="بدهکار">{lineSide(l, 'debit')}</td>
                                      <td data-label="بستانکار">{lineSide(l, 'credit')}</td>
                                      <td className="num" data-label="مبلغ">
                                        {faAmount(l.amount)}
                                      </td>
                                      <td className="num" data-label="معادل ریالی">
                                        {faAmount(l.base_amount)}
                                      </td>
                                      <td className="card-wide" data-label="شرح">
                                        {l.description || '—'}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

export { Lock }
