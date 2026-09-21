/**
 * کمیسیونِ ۲٪ بازارِ عمده‌فروشی.
 *
 * تسویه **دستی** است: پولی جابه‌جا نمی‌شود، فقط دوره‌ی یک پخش‌کننده «تسویه‌شده»
 * علامت می‌خورد و مرجعِ بانکی ثبت می‌شود. صفحه همین را صریح می‌گوید تا کسی فکر
 * نکند دکمه واریز می‌کند.
 */
import { useMemo, useState } from 'react'
import { Download, Percent, RefreshCw, Search } from 'lucide-react'

import {
  fetchCommissionOverview,
  fetchCommissions,
  settleCommission,
  type CommissionPeriod,
} from '../api'
import { textMatches } from '../lib/faText'
import { faCompact } from '../lib/format'
import { toFaDigits } from '../lib/jalali'
import {
  AsyncBlock,
  Card,
  Chip,
  Note,
  PageHeader,
  Stat,
  TableScroll,
  fa,
  faInt,
  useAsync,
} from '../ui/kit'

/** CSV با BOM، وگرنه اکسلِ ویندوزی فارسی را جویده نشان می‌دهد. */
function downloadCsv(rows: CommissionPeriod[]): void {
  const head = ['پخش‌کننده', 'دوره', 'تعداد سفارش', 'پایه', 'کمیسیون', 'تسویه‌نشده', 'وضعیت']
  const body = rows.map((r) => [
    r.distributor_name ?? r.distributor_tenant_id,
    r.period,
    r.order_count,
    r.total_base,
    r.total_amount,
    r.pending_amount,
    r.status === 'settled' ? 'تسویه‌شده' : 'در انتظار',
  ])
  const csv = [head, ...body].map((line) => line.map((c) => `"${c}"`).join(',')).join('\n')
  const blob = new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `commissions-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function CommissionsPage({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: (e: unknown) => void
}) {
  const overview = useAsync(() => fetchCommissionOverview(token), [token])
  const list = useAsync(() => fetchCommissions(token), [token])
  const [q, setQ] = useState('')
  const [onlyPending, setOnlyPending] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'bad'; text: string } | null>(null)

  const rows = list.data ?? []

  const shown = useMemo(
    () =>
      rows.filter((r) => {
        if (onlyPending && r.pending_amount <= 0) return false
        return textMatches(`${r.distributor_name ?? ''} ${r.period}`, q)
      }),
    [rows, q, onlyPending],
  )

  async function settle(row: CommissionPeriod) {
    const note = window.prompt(
      `مرجعِ واریز برای «${row.distributor_name ?? '—'}» دوره‌ی ${row.period}:`,
    )
    if (note == null) return
    try {
      const out = await settleCommission(token, row.distributor_tenant_id, row.period, note)
      setMsg({ kind: 'ok', text: `${fa(out.amount)} ریال تسویه‌شده علامت خورد.` })
      list.reload()
      overview.reload()
    } catch (e) {
      onUnauthorized(e)
      setMsg({ kind: 'bad', text: e instanceof Error ? e.message : 'تسویه انجام نشد' })
    }
  }

  const ov = overview.data

  return (
    <>
      <PageHeader
        icon={Percent}
        title="کمیسیون بازار"
        description="کمیسیونِ پلتفرم روی سفارش‌های قطعی‌شده‌ی بازارِ عمده‌فروشی."
        actions={
          <>
            <button type="button" className="ad-btn" onClick={() => downloadCsv(shown)}>
              <Download size={15} /> خروجی CSV
            </button>
            <button
              type="button"
              className="ad-btn"
              onClick={() => {
                list.reload()
                overview.reload()
              }}
            >
              <RefreshCw size={15} /> تازه‌سازی
            </button>
          </>
        }
      />

      <section className="ad-stats">
        <Stat label="کلِ کمیسیون" value={ov ? faCompact(ov.total_amount) : '—'} hint="ریال" />
        <Stat
          label="تسویه‌نشده"
          value={ov ? faCompact(ov.pending_amount) : '—'}
          tone={ov && ov.pending_amount > 0 ? 'warn' : 'ok'}
        />
        <Stat label="تسویه‌شده" value={ov ? faCompact(ov.settled_amount) : '—'} tone="ok" />
        <Stat label="پخش‌کننده" value={ov ? faInt(ov.distributor_count) : '—'} />
        <Stat
          label="نرخ"
          value={ov ? `${toFaDigits((ov.rate * 100).toFixed(1))}٪` : '—'}
          hint="روی هر سفارش اسنپ‌شات می‌شود"
        />
      </section>

      <Note msg={msg} />

      <Card
        description="تسویه انتقالِ بانکیِ دستی است؛ این دکمه فقط دوره را تسویه‌شده علامت می‌زند و مرجع را ثبت می‌کند."
      >
        <div className="ad-toolbar">
          <div className="ad-search">
            <Search size={15} />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="نامِ پخش‌کننده یا دوره"
              aria-label="جست‌وجو"
            />
          </div>
          <label className="ad-check">
            <input
              type="checkbox"
              checked={onlyPending}
              onChange={(e) => setOnlyPending(e.target.checked)}
            />
            فقط تسویه‌نشده‌ها
          </label>
          <span className="ad-count">{faInt(shown.length)} دوره</span>
        </div>

        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={shown.length === 0}
          emptyText="دوره‌ای با این شرایط نیست."
        >
          <TableScroll>
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>پخش‌کننده</th>
                  <th>دوره</th>
                  <th>سفارش</th>
                  <th>پایه</th>
                  <th>کمیسیون</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={`${r.distributor_tenant_id}-${r.period}`}>
                    <td className="card-title" data-label="پخش‌کننده">
                      {r.distributor_name ?? '—'}
                    </td>
                    <td data-label="دوره" dir="ltr">
                      {toFaDigits(r.period)}
                    </td>
                    <td className="num" data-label="سفارش">
                      {faInt(r.order_count)}
                    </td>
                    <td className="num" data-label="پایه">
                      {fa(r.total_base)}
                    </td>
                    <td className="num" data-label="کمیسیون">
                      {fa(r.total_amount)}
                    </td>
                    <td data-label="وضعیت">
                      {r.pending_amount > 0 ? (
                        <Chip text={`${fa(r.pending_amount)} در انتظار`} tone="warn" />
                      ) : (
                        <Chip text="تسویه‌شده" tone="ok" />
                      )}
                    </td>
                    <td className="card-actions">
                      {r.pending_amount > 0 ? (
                        <button type="button" className="ad-btn small" onClick={() => settle(r)}>
                          ثبتِ تسویه
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        </AsyncBlock>
      </Card>
    </>
  )
}
