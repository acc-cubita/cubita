/**
 * خریدهای سایتِ تجاری (cubita.ir → زرین‌پال).
 *
 * «تحویل» یعنی ساختِ کسب‌وکار یا ارتقای کسب‌وکارِ موجود و فرستادنِ لینکِ
 * راه‌اندازی. عملیاتش idempotent است، ولی دکمه پس از تحویل پنهان می‌شود تا
 * کسی دوباره نزند و بعد دنبالِ اثرش بگردد.
 */
import { useMemo, useState } from 'react'
import { CreditCard, RefreshCw, Search } from 'lucide-react'

import { fetchPurchases, fulfillPurchase } from '../api'
import { textMatches } from '../lib/faText'
import { faCompact } from '../lib/format'
import { formatJalali, toFaDigits } from '../lib/jalali'
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

const PERIOD_LABELS: Record<string, string> = {
  monthly: 'ماهانه',
  semiannual: 'شش‌ماهه',
  yearly: 'سالانه',
}

export default function PurchasesPage({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: (e: unknown) => void
}) {
  const { data, loading, error, reload } = useAsync(() => fetchPurchases(token), [token])
  const [q, setQ] = useState('')
  const [onlyOpen, setOnlyOpen] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'bad'; text: string } | null>(null)

  const rows = data ?? []

  const kpis = useMemo(
    () => ({
      paid: rows.filter((r) => r.status === 'paid').length,
      waiting: rows.filter((r) => r.status === 'paid' && !r.fulfilled_at).length,
      revenue: rows
        .filter((r) => r.status === 'paid')
        .reduce((sum, r) => sum + (r.amount_toman || 0), 0),
    }),
    [rows],
  )

  const shown = useMemo(
    () =>
      rows.filter((r) => {
        if (onlyOpen && (r.status !== 'paid' || r.fulfilled_at)) return false
        return textMatches(`${r.business_name} ${r.customer_email} ${r.customer_name ?? ''}`, q)
      }),
    [rows, q, onlyOpen],
  )

  async function fulfill(id: string, name: string) {
    const note = window.prompt(`یادداشتِ تحویل برای «${name}»:`) ?? ''
    try {
      await fulfillPurchase(token, id, note)
      setMsg({ kind: 'ok', text: `خریدِ «${name}» تحویل شد.` })
      reload()
    } catch (e) {
      onUnauthorized(e)
      setMsg({ kind: 'bad', text: e instanceof Error ? e.message : 'تحویل انجام نشد' })
    }
  }

  return (
    <>
      <PageHeader
        icon={CreditCard}
        title="خریدهای سایت"
        description="پرداخت‌های سایتِ تجاری و تحویلِ اکانت به مشتری."
        actions={
          <button type="button" className="ad-btn" onClick={reload}>
            <RefreshCw size={15} /> تازه‌سازی
          </button>
        }
      />

      <section className="ad-stats">
        <Stat label="خریدِ موفق" value={faInt(kpis.paid)} />
        <Stat
          label="منتظرِ تحویل"
          value={faInt(kpis.waiting)}
          tone={kpis.waiting ? 'warn' : 'ok'}
        />
        <Stat label="مجموعِ دریافتی" value={faCompact(kpis.revenue)} hint="تومان" />
      </section>

      <Note msg={msg} />

      <Card>
        <div className="ad-toolbar">
          <div className="ad-search">
            <Search size={15} />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="نامِ کسب‌وکار یا ایمیل"
              aria-label="جست‌وجو"
            />
          </div>
          <label className="ad-check">
            <input
              type="checkbox"
              checked={onlyOpen}
              onChange={(e) => setOnlyOpen(e.target.checked)}
            />
            فقط منتظرِ تحویل
          </label>
          <span className="ad-count">{faInt(shown.length)} مورد</span>
        </div>

        <AsyncBlock
          loading={loading}
          error={error}
          empty={shown.length === 0}
          emptyText="خریدی با این شرایط نیست."
        >
          <TableScroll>
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>کسب‌وکار</th>
                  <th>مشتری</th>
                  <th>مبلغ</th>
                  <th>دوره</th>
                  <th>وضعیت</th>
                  <th>تاریخ</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shown.map((p) => (
                  <tr key={p.id}>
                    <td className="card-title" data-label="کسب‌وکار">
                      {p.business_name}
                    </td>
                    <td data-label="مشتری">
                      {p.customer_name ?? '—'}
                      <span className="ad-sub" dir="ltr">
                        {p.customer_email}
                      </span>
                    </td>
                    <td className="num" data-label="مبلغ">
                      {fa(p.amount_toman)}
                    </td>
                    <td data-label="دوره">
                      {PERIOD_LABELS[p.billing_period] ?? toFaDigits(p.billing_period)}
                    </td>
                    <td data-label="وضعیت">
                      {p.status !== 'paid' ? (
                        <Chip text="ناموفق" tone="bad" />
                      ) : p.fulfilled_at ? (
                        <Chip text="تحویل‌شده" tone="ok" />
                      ) : (
                        <Chip text="منتظرِ تحویل" tone="warn" />
                      )}
                    </td>
                    <td data-label="تاریخ">{formatJalali(p.created_at)}</td>
                    <td className="card-actions">
                      {p.status === 'paid' && !p.fulfilled_at ? (
                        <button
                          type="button"
                          className="ad-btn small primary"
                          onClick={() => fulfill(p.id, p.business_name)}
                        >
                          تحویل
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
