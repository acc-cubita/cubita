import { useEffect, useState } from 'react'
import { History, ArrowDownToLine, ArrowUpFromLine, Boxes } from 'lucide-react'
import { fetchKardex, type KardexReport } from '../api'
import { formatJalali } from '../lib/jalali'
import { ItemPicker, type PickableItem } from './ItemPicker'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'

const fa = (n: number) => n.toLocaleString('fa-IR')
const faQty = (s: string) => (Number(s) || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })

/**
 * تبِ «کاردکس» در انبار — نسخه‌ی درجای همان کاردکسِ کشویی: کالا را از انتخاب‌گر
 * برگزینید و کلِ گردشِ ورود/خروج با موجودیِ در حال اجرا را همان‌جا در صفحه ببینید.
 * منطقِ خواندن (fetchKardex) و کلاس‌های نمایشِ موبایل با KardexDrawer مشترک است.
 */
export function KardexPanel({ token, items }: { token: string; items: PickableItem[] }) {
  const [itemId, setItemId] = useState('')
  const [data, setData] = useState<KardexReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!itemId) {
      setData(null)
      return
    }
    let alive = true
    setLoading(true)
    setError(null)
    fetchKardex(token, itemId)
      .then((r) => { if (alive) setData(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [token, itemId])

  return (
    <SectionCard
      icon={History}
      title="کاردکس کالا"
      description="کالا را انتخاب کنید تا کارتِ حساب آن — همه‌ی ورودها و خروج‌ها با موجودیِ در حال اجرا — نمایش داده شود."
    >
      <div className="kardex-picker">
        <ItemPicker items={items} value={itemId} onChange={setItemId} placeholder="— انتخاب کالا —" />
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <p className="muted">در حال بارگذاری…</p>}

      {!itemId && !loading && (
        <EmptyState icon={History} text="برای دیدنِ کاردکس، یک کالا انتخاب کنید." />
      )}

      {data && !loading && (
        <>
          <div className="kardex-summary">
            <div className="kardex-stat"><span>موجودی اول</span><strong>{faQty(data.opening_qty)}</strong></div>
            <div className="kardex-stat"><ArrowDownToLine size={14} /><span>کل ورود</span><strong className="pos-in">{faQty(data.total_in)}</strong></div>
            <div className="kardex-stat"><ArrowUpFromLine size={14} /><span>کل خروج</span><strong className="pos-out">{faQty(data.total_out)}</strong></div>
            <div className="kardex-stat"><Boxes size={14} /><span>موجودی پایان</span><strong>{faQty(data.closing_qty)}</strong></div>
          </div>

          {data.lines.length === 0 ? (
            <p className="muted">هیچ حرکتی برای این کالا ثبت نشده.</p>
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table kardex-table cards-on-mobile">
                  <thead>
                    <tr>
                      <th>تاریخ</th>
                      <th>شرح</th>
                      <th>ورود</th>
                      <th>خروج</th>
                      <th>بهای واحد</th>
                      <th>مانده</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.lines.map((l, i) => (
                      <tr key={i}>
                        <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                        <td data-label="شرح">{l.source_label}</td>
                        <td data-label="ورود" className="pos-in">{Number(l.qty_in) > 0 ? faQty(l.qty_in) : '—'}</td>
                        <td data-label="خروج" className="pos-out">{Number(l.qty_out) > 0 ? faQty(l.qty_out) : '—'}</td>
                        <td data-label="بهای واحد" className="money-cell">{fa(Number(l.unit_cost))}</td>
                        <td data-label="مانده" className="money-cell"><strong>{faQty(l.balance_qty)}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </SectionCard>
  )
}
