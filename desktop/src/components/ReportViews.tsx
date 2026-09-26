import type { CSSProperties, KeyboardEvent, ReactNode } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'

import {
  costCenterKindLabel,
  type AgingReport,
  type BudgetReport,
  type ContactStatement,
  type CostCenterReport,
  type EquityStatement,
  type InventoryReport,
  type SeasonalSection,
} from '../api'
import { formatJalali } from '../lib/jalali'
import { ENTITY_LABEL, equityRows, issueText, type StatementRow } from '../lib/reportSheets'

/**
 * گریدهای فقط‌خواندنیِ صفحه‌ی «گزارش‌ها» (تمِ اکسلی، الگوی «د»). هر گزارش یک گرید است و جمع‌هایش در
 * `tfoot`ِ همان گرید، نه کارتِ خلاصه یا جمله‌ی زیرِ جدول. پوسته، بازه و بارگذاری در `Reports.tsx` است؛ این‌جا
 * فقط نمایش است.
 */

/** حسابی که با کلیک روی ردیف، دفترش باز می‌شود. */
export interface OpenAccount {
  id: string
  code: string
  name: string
}

const fa = (v: string | number) => Number(v || 0).toLocaleString('fa-IR')

/** مبلغِ گزارش: صفر «—»، منفی در پرانتز و قرمز — قراردادِ صورت‌های مالی. */
function Amount({ value }: { value: string | number }) {
  const v = Number(value || 0)
  if (v === 0) return <>—</>
  if (v < 0) return <span className="rp-neg">({fa(-v)})</span>
  return <>{fa(v)}</>
}

/** مانده با سمت: مثبت «بد» (بدهکار)، منفی «بس». */
function SideAmount({ value }: { value: string | number }) {
  const v = Number(value || 0)
  if (v === 0) return <>—</>
  return (
    <>
      {fa(Math.abs(v))} <small className="rp-side">{v > 0 ? 'بد' : 'بس'}</small>
    </>
  )
}

/** نشانِ درستیِ یک تساوی (توازنِ ترازنامه، تطبیقِ حقوقِ صاحبان سهام) — همان نشانِ «جمع»ِ تراز. */
export function CheckChip({ ok, okText, offText }: { ok: boolean; okText: string; offText: string }) {
  return ok ? (
    <span className="xl-check xl-check--ok">
      <CheckCircle2 size={13} aria-hidden="true" /> {okText}
    </span>
  ) : (
    <span className="xl-check xl-check--off" role="alert">
      <AlertTriangle size={13} aria-hidden="true" /> {offText}
    </span>
  )
}

const openable = (id: string | undefined, onOpen: ((a: OpenAccount) => void) | undefined, a: OpenAccount) =>
  id && onOpen
    ? {
        className: 'acc-row--clickable',
        tabIndex: 0,
        title: 'دفترِ این حساب',
        onClick: () => onOpen(a),
        onKeyDown: (e: KeyboardEvent) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            onOpen(a)
          }
        },
      }
    : {}

// ═══════════════════════ صورت‌های مالی ═══════════════════════

/**
 * صورتِ مالی به‌شکلِ برگه‌ی سه‌ستونه: بخش، قلم، جمعِ بخش؛ جمع‌های نهایی در `tfoot`. سه ستون در موبایل هم جا
 * می‌شوند (کد پنهان می‌شود)، پس عمداً کارت نمی‌شود (`table-plain`).
 */
export function StatementGrid({
  rows,
  check,
  onOpen,
  label = 'مبلغ',
}: {
  rows: readonly StatementRow[]
  /** نشانِ تساوی کنارِ آخرین جمع. */
  check?: ReactNode
  onOpen?: (a: OpenAccount) => void
  label?: string
}) {
  const body = rows.filter((r) => r.kind !== 'total')
  const totals = rows.filter((r) => r.kind === 'total')
  return (
    <div className="table-scroll ef-table-wrap rp-scroll">
      <table className="ef-table xl-grid table-plain rp-table rp-statement">
        <colgroup>
          <col className="rp-c-code" />
          <col />
          <col className="rp-c-amt" />
        </colgroup>
        <thead>
          <tr>
            <th className="rp-code">کد</th>
            <th>شرح</th>
            <th className="num">{label}</th>
          </tr>
        </thead>
        <tbody>
          {body.map((r, i) =>
            r.kind === 'section' ? (
              <tr key={i} className="rp-sec">
                <td colSpan={3}>{r.label}</td>
              </tr>
            ) : r.kind === 'subtotal' ? (
              <tr key={i} className="rp-sub">
                <td className="rp-code" />
                <td>{r.label}</td>
                <td className="num">
                  <Amount value={r.amount} />
                </td>
              </tr>
            ) : r.kind === 'line' ? (
              <tr
                key={i}
                {...openable(r.accountId, onOpen, { id: r.accountId ?? '', code: r.code ?? '', name: r.label })}
              >
                <td className="rp-code">
                  <span className="ltr-cell">{r.code}</span>
                </td>
                <td className="rp-name">
                  {r.label}
                  {r.note && <small className="rp-note">{r.note}</small>}
                </td>
                <td className="num">
                  <Amount value={r.amount} />
                </td>
              </tr>
            ) : null,
          )}
        </tbody>
        <tfoot>
          {totals.map((r, i) => (
            <tr key={i} className="rp-total">
              <td className="rp-code" />
              <td>
                {r.label}
                {i === totals.length - 1 && check}
              </td>
              <td className="num">{'amount' in r && <Amount value={r.amount} />}</td>
            </tr>
          ))}
        </tfoot>
      </table>
    </div>
  )
}

export function EquityView({ data, onOpen }: { data: EquityStatement; onOpen?: (a: OpenAccount) => void }) {
  return (
    <>
      <StatementGrid
        rows={equityRows(data)}
        check={
          <CheckChip
            ok={data.reconciled}
            okText="تطبیق دارد"
            offText="«اول دوره + تغییرات» با «پایان دوره» نمی‌خواند — مبنا نگیرید و گزارش کنید"
          />
        }
      />
      <p className="hint rp-after">
        سود/زیانِ دوره بیرونِ این تساوی است (تا سندِ اختتامیه به حسابی نرفته): <b>{fa(data.net_profit)}</b>
      </p>

      <h4 className="rp-subhead">اجزای حقوق صاحبان سهام</h4>
      {data.components.length === 0 ? (
        <p className="hint">هیچ حسابِ حقوق صاحبان سهامی در این بازه حرکتی نداشت.</p>
      ) : (
        <div className="table-scroll ef-table-wrap rp-scroll">
          <table className="ef-table xl-grid cards-on-mobile rp-table">
            <thead>
              <tr>
                <th className="rp-code">کد</th>
                <th>حساب</th>
                <th className="num">اول دوره</th>
                <th className="num">تغییر</th>
                <th className="num">پایان دوره</th>
              </tr>
            </thead>
            <tbody>
              {data.components.map((c) => (
                <tr
                  key={c.account_id}
                  {...openable(c.account_id, onOpen, { id: c.account_id, code: c.account_code, name: c.account_name })}
                >
                  <td className="card-hide rp-code">
                    <span className="ltr-cell">{c.account_code}</span>
                  </td>
                  <td className="card-title">
                    <span className="rp-code-inline">{c.account_code}</span>
                    {c.account_name}
                  </td>
                  <td className="num" data-label="اول دوره">
                    <Amount value={c.opening} />
                  </td>
                  <td className="num" data-label="تغییر">
                    <Amount value={c.change} />
                  </td>
                  <td className="num" data-label="پایان دوره">
                    <Amount value={c.closing} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4 className="rp-subhead">به تفکیکِ شریک</h4>
      {data.partner_rows.length === 0 ? (
        <p className="hint">
          آورده یا برداشتی از مسیرِ «تراکنش شریک» ثبت نشده. آورده‌ای که با سندِ دستی ثبت شده در جمع‌های بالا هست ولی
          نامِ شریکش در دفتر نیامده، پس این‌جا دیده نمی‌شود.
        </p>
      ) : (
        <div className="table-scroll ef-table-wrap rp-scroll">
          <table className="ef-table xl-grid cards-on-mobile rp-table">
            <thead>
              <tr>
                <th>شریک</th>
                <th className="num">آورده</th>
                <th className="num">برداشت</th>
              </tr>
            </thead>
            <tbody>
              {data.partner_rows.map((r) => (
                <tr key={r.contact_id}>
                  <td className="card-title">{r.contact_name}</td>
                  <td className="num pos-in" data-label="آورده">
                    <Amount value={r.contributed} />
                  </td>
                  <td className="num pos-out" data-label="برداشت">
                    <Amount value={r.withdrawn} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

// ═══════════════════════ مدیریتی ═══════════════════════

export function BudgetGrid({ data, onOpen }: { data: BudgetReport; onOpen?: (a: OpenAccount) => void }) {
  return (
    <div className="table-scroll ef-table-wrap rp-scroll">
      <table className="ef-table xl-grid cards-on-mobile rp-table rp-budget">
        <thead>
          <tr>
            <th className="rp-code">کد</th>
            <th>حساب</th>
            <th className="num">بودجه</th>
            <th className="num">عملکرد</th>
            <th className="num">انحراف</th>
            <th className="num">درصد</th>
            <th>وضعیت</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr
              key={r.account_id}
              {...openable(r.account_id, onOpen, { id: r.account_id, code: r.account_code, name: r.account_name })}
            >
              <td className="card-hide rp-code">
                <span className="ltr-cell">{r.account_code}</span>
              </td>
              <td className="card-title">
                <span className="rp-code-inline">{r.account_code}</span>
                {r.account_name}
              </td>
              <td className="num" data-label="بودجه">
                <Amount value={r.budget} />
              </td>
              <td className="num" data-label="عملکرد">
                <Amount value={r.actual} />
              </td>
              <td className="num" data-label="انحراف">
                <Amount value={r.variance} />
              </td>
              <td className="num" data-label="درصد">
                {r.variance_pct != null ? `${fa(r.variance_pct)}٪` : '—'}
              </td>
              <td data-label="وضعیت">
                <span className={`status-badge ${r.favorable ? 'tone-success' : 'tone-danger'}`}>
                  {r.favorable ? 'مطلوب' : 'نامطلوب'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="rp-total">
            <td className="card-hide rp-code" />
            <td className="card-title">جمع</td>
            <td className="num" data-label="جمعِ بودجه">
              <Amount value={data.total_budget} />
            </td>
            <td className="num" data-label="جمعِ عملکرد">
              <Amount value={data.total_actual} />
            </td>
            <td className="num" data-label="جمعِ انحراف">
              <Amount value={data.total_variance} />
            </td>
            <td className="card-hide" />
            <td className="card-hide" />
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

export function CostCenterGrid({ data }: { data: CostCenterReport }) {
  return (
    <div className="table-scroll ef-table-wrap rp-scroll">
      <table className="ef-table xl-grid cards-on-mobile rp-table rp-cc">
        <thead>
          <tr>
            <th className="rp-code">کد</th>
            <th>مرکز / پروژه</th>
            <th className="num">درآمد</th>
            <th className="num">هزینه</th>
            <th className="num">سود مستقیم</th>
            <th className="num">با زیرمجموعه</th>
            <th className="num">انحراف از بودجه</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.cost_center_id ?? 'none'} className={r.cost_center_id ? undefined : 'rp-row--muted'}>
              <td className="card-hide rp-code">
                <span className="ltr-cell">{r.cost_center_code || '—'}</span>
              </td>
              <td className="card-title rp-tree" style={{ '--rp-depth': r.depth } as CSSProperties}>
                {r.cost_center_name}
                {r.cost_center_id && <small className="rp-note">{costCenterKindLabel(r.kind)}</small>}
              </td>
              <td className="num" data-label="درآمد">
                <Amount value={r.income} />
              </td>
              <td className="num" data-label="هزینه">
                <Amount value={r.expense} />
              </td>
              <td className="num" data-label="سود مستقیم">
                <Amount value={r.profit} />
              </td>
              <td className="num rp-strong" data-label="با زیرمجموعه">
                <Amount value={r.rollup_profit} />
              </td>
              <td className="num" data-label="انحراف از بودجه">
                {r.profit_variance == null ? '—' : <Amount value={r.profit_variance} />}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="rp-total">
            <td className="card-hide rp-code" />
            <td className="card-title">جمع</td>
            <td className="num" data-label="جمعِ درآمد">
              <Amount value={data.total_income} />
            </td>
            <td className="num" data-label="جمعِ هزینه">
              <Amount value={data.total_expense} />
            </td>
            <td className="num" data-label="جمعِ سود مستقیم">
              <Amount value={data.total_profit} />
            </td>
            <td className="card-hide" />
            <td className="card-hide" />
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

// ═══════════════════════ اشخاص ═══════════════════════

export function AgingGrid({ data }: { data: AgingReport }) {
  const who = data.kind === 'receivable' ? 'مشتری' : 'تأمین‌کننده'
  return (
    <div className="table-scroll ef-table-wrap rp-scroll">
      <table className="ef-table xl-grid cards-on-mobile rp-table rp-aging">
        <thead>
          <tr>
            <th>{who}</th>
            <th className="num">جاری (۰–۳۰)</th>
            <th className="num">۳۱–۶۰ روز</th>
            <th className="num">۶۱–۹۰ روز</th>
            <th className="num">بالای ۹۰ روز</th>
            <th className="num">جمع</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.contact_id}>
              <td className="card-title">{r.contact_name}</td>
              <td className="num" data-label="جاری (۰–۳۰)">
                <Amount value={r.current} />
              </td>
              <td className="num" data-label="۳۱–۶۰ روز">
                <Amount value={r.d31_60} />
              </td>
              <td className="num" data-label="۶۱–۹۰ روز">
                <Amount value={r.d61_90} />
              </td>
              <td className={`num${Number(r.over_90) > 0 ? ' rp-late' : ''}`} data-label="بالای ۹۰ روز">
                <Amount value={r.over_90} />
              </td>
              <td className="num rp-strong" data-label="جمع">
                <Amount value={r.total} />
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="rp-total">
            <td className="card-title">جمع</td>
            <td className="num" data-label="جاری (۰–۳۰)">
              <Amount value={data.total_current} />
            </td>
            <td className="num" data-label="۳۱–۶۰ روز">
              <Amount value={data.total_31_60} />
            </td>
            <td className="num" data-label="۶۱–۹۰ روز">
              <Amount value={data.total_61_90} />
            </td>
            <td className="num" data-label="بالای ۹۰ روز">
              <Amount value={data.total_over_90} />
            </td>
            <td className="num" data-label="جمعِ کل">
              <Amount value={data.grand_total} />
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

/** صورت‌حسابِ شخص: «مانده‌ی ابتدای دوره» ردیفِ اول، جمعِ گردش و مانده‌ی پایان در `tfoot`. مانده با سمت. */
export function ContactStatementGrid({ data }: { data: ContactStatement }) {
  const closing = Number(data.closing_balance)
  return (
    <div className="table-scroll ef-table-wrap rp-scroll">
      <table className="ef-table xl-grid cards-on-mobile rp-table rp-stmt">
        <thead>
          <tr>
            <th>تاریخ</th>
            <th>شرح</th>
            <th>شماره</th>
            <th className="num">بدهکار</th>
            <th className="num">بستانکار</th>
            <th className="num">مانده</th>
          </tr>
        </thead>
        <tbody>
          <tr className="rp-carry">
            <td className="card-title" colSpan={5}>
              مانده‌ی ابتدای دوره
            </td>
            <td className="num" data-label="مانده">
              <SideAmount value={data.opening_balance} />
            </td>
          </tr>
          {data.lines.length === 0 ? (
            <tr>
              <td className="card-full rp-status" colSpan={6}>
                در این بازه گردشی ندارد.
              </td>
            </tr>
          ) : (
            data.lines.map((l, i) => (
              <tr key={i}>
                <td data-label="تاریخ">{formatJalali(l.txn_date)}</td>
                <td className="card-title" title={l.description}>
                  {l.description}
                </td>
                <td data-label="شماره">{l.number != null ? fa(l.number) : '—'}</td>
                <td className="num" data-label="بدهکار">
                  <Amount value={l.debit} />
                </td>
                <td className="num" data-label="بستانکار">
                  <Amount value={l.credit} />
                </td>
                <td className="num rp-strong" data-label="مانده">
                  <SideAmount value={l.balance} />
                </td>
              </tr>
            ))
          )}
        </tbody>
        <tfoot>
          <tr className="rp-total">
            <td className="card-title" colSpan={3}>
              جمع و مانده‌ی پایان
              <small className="rp-note">
                {closing > 0 ? 'بدهکار به ما' : closing < 0 ? 'طلبکار از ما' : 'تسویه'}
              </small>
            </td>
            <td className="num" data-label="جمعِ بدهکار">
              <Amount value={data.total_debit} />
            </td>
            <td className="num" data-label="جمعِ بستانکار">
              <Amount value={data.total_credit} />
            </td>
            <td className="num" data-label="مانده‌ی پایان">
              <SideAmount value={closing} />
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

// ═══════════════════════ انبار ═══════════════════════

/** ارزشِ موجودی: سرستونِ دوطبقه مثلِ تراز (اول دوره / ورود / خروج / پایان دوره)؛ کد و نام میخ‌اند. */
export function InventoryGrid({ data }: { data: InventoryReport }) {
  return (
    <div className="table-scroll ef-table-wrap rp-scroll">
      <table className="ef-table xl-grid cards-on-mobile rp-table rp-inv">
        <colgroup>
          <col className="rp-c-sku" />
          <col />
          <col className="rp-c-unit" />
          {Array.from({ length: 9 }, (_, i) => (
            <col key={i} className="rp-c-amt" />
          ))}
        </colgroup>
        <thead>
          <tr>
            <th className="rp-pin rp-pin--sku" rowSpan={2}>
              کد
            </th>
            <th className="rp-pin rp-pin--name" rowSpan={2}>
              کالا
            </th>
            <th rowSpan={2}>واحد</th>
            <th className="rp-group rp-gs" colSpan={2}>
              اول دوره
            </th>
            <th className="rp-group rp-gs" colSpan={2}>
              ورود
            </th>
            <th className="rp-group rp-gs" colSpan={2}>
              خروج
            </th>
            <th className="rp-group rp-gs" colSpan={3}>
              پایان دوره
            </th>
          </tr>
          <tr>
            <th className="num rp-gs">تعداد</th>
            <th className="num">ارزش</th>
            <th className="num rp-gs">تعداد</th>
            <th className="num">ارزش</th>
            <th className="num rp-gs">تعداد</th>
            <th className="num">ارزش</th>
            <th className="num rp-gs">موجودی</th>
            <th className="num">بهای میانگین</th>
            <th className="num">ارزش</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.item_id}>
              <td className="card-hide rp-pin rp-pin--sku">
                <span className="ltr-cell">{r.sku}</span>
              </td>
              <td className="card-title rp-pin rp-pin--name" title={r.name}>
                <span className="rp-code-inline">{r.sku}</span>
                {r.name}
                {r.stale_from && (
                  <span className="status-badge tone-warning">منقضی از {formatJalali(r.stale_from)}</span>
                )}
              </td>
              <td data-label="واحد">{r.unit}</td>
              <td className="num rp-gs" data-label="اول دوره">
                <Amount value={r.opening_qty} />
              </td>
              <td className="num" data-label="ارزش اول دوره">
                <Amount value={r.opening_value} />
              </td>
              <td className="num rp-gs pos-in" data-label="ورود">
                <Amount value={r.in_qty} />
              </td>
              <td className="num" data-label="ارزش ورود">
                <Amount value={r.in_value} />
              </td>
              <td className="num rp-gs pos-out" data-label="خروج">
                <Amount value={r.out_qty} />
              </td>
              <td className="num" data-label="ارزش خروج">
                <Amount value={r.out_value} />
              </td>
              <td className="num rp-gs rp-strong" data-label="موجودی">
                <Amount value={r.qty_on_hand} />
              </td>
              <td className="num" data-label="بهای میانگین">
                <Amount value={Math.round(Number(r.unit_cost))} />
              </td>
              <td className="num rp-strong" data-label="ارزش">
                <Amount value={r.stock_value} />
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="rp-total">
            <td className="card-hide rp-pin rp-pin--sku" />
            <td className="card-title rp-pin rp-pin--name">جمع ({fa(data.item_count)} قلم)</td>
            <td className="card-hide" />
            <td className="card-hide rp-gs" />
            <td className="num" data-label="ارزش اول دوره">
              <Amount value={data.total_opening_value} />
            </td>
            <td className="card-hide rp-gs" />
            <td className="num" data-label="ارزش ورود">
              <Amount value={data.total_in_value} />
            </td>
            <td className="card-hide rp-gs" />
            <td className="num" data-label="ارزش خروج">
              <Amount value={data.total_out_value} />
            </td>
            <td className="card-hide rp-gs" />
            <td className="card-hide" />
            <td className="num" data-label="ارزش پایان دوره">
              <Amount value={data.total_value} />
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

// ═══════════════════════ مالیات ═══════════════════════

export function SeasonalGrid({
  title,
  section,
  onlyIncomplete,
}: {
  title: string
  section: SeasonalSection
  onlyIncomplete: boolean
}) {
  const rows = onlyIncomplete ? section.rows.filter((r) => r.issues.length > 0) : section.rows
  return (
    <>
      <h4 className="rp-subhead">
        {title}
        <small>
          {fa(section.ready_count)} آماده
          {section.incomplete_count > 0 && (
            <>
              {' · '}
              <b className="rp-late">{fa(section.incomplete_count)} ناقص</b> — سامانه ردیفِ ناقص را رد می‌کند
            </>
          )}
        </small>
      </h4>
      {rows.length === 0 ? (
        <p className="hint">{onlyIncomplete ? 'همه‌ی ردیف‌های این بخش آماده‌اند.' : 'در این فصل معامله‌ای ثبت نشده.'}</p>
      ) : (
        <div className="table-scroll ef-table-wrap rp-scroll">
          <table className="ef-table xl-grid cards-on-mobile rp-table rp-seasonal">
            <thead>
              <tr>
                <th>طرف حساب</th>
                <th>شخص</th>
                <th>کد/شناسه ملی</th>
                <th>کد اقتصادی</th>
                <th className="num">تعداد</th>
                <th className="num">خالص</th>
                <th className="num">مالیات و عوارض</th>
                <th className="num">مبلغ کل</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.contact_id ?? `agg-${i}`} className={r.issues.length > 0 ? 'rp-row--warn' : undefined}>
                  <td className="card-title">
                    {r.contact_name}
                    {r.issues.length > 0 && <small className="rp-note rp-late">ناقص: {issueText(r.issues)}</small>}
                  </td>
                  <td data-label="شخص">{ENTITY_LABEL[r.entity_type]}</td>
                  <td data-label="کد/شناسه ملی">
                    <span className="ltr-cell">{r.national_id ?? '—'}</span>
                  </td>
                  <td data-label="کد اقتصادی">
                    <span className="ltr-cell">{r.economic_code ?? '—'}</span>
                  </td>
                  <td className="num" data-label="تعداد">
                    {fa(r.invoice_count)}
                  </td>
                  <td className="num" data-label="خالص">
                    <Amount value={r.net} />
                  </td>
                  <td className="num" data-label="مالیات و عوارض">
                    <Amount value={r.vat} />
                  </td>
                  <td className="num rp-strong" data-label="مبلغ کل">
                    <Amount value={r.total} />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="rp-total">
                <td className="card-title" colSpan={5}>
                  جمعِ {title}
                </td>
                <td className="num" data-label="خالص">
                  <Amount value={section.total_net} />
                </td>
                <td className="num" data-label="مالیات و عوارض">
                  <Amount value={section.total_vat} />
                </td>
                <td className="num" data-label="مبلغ کل">
                  <Amount value={section.total_total} />
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </>
  )
}
