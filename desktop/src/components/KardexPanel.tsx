import { useEffect, useState } from 'react'
import { History } from 'lucide-react'
import { fetchKardex, type KardexReport } from '../api'
import { ItemPicker, type PickableItem } from './ItemPicker'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { KardexSummary, KardexTable } from './KardexTable'

/**
 * تبِ «کاردکس» در انبار — نسخه‌ی درجای همان کاردکسِ کشویی: کالا را از انتخاب‌گر
 * برگزینید و کلِ گردشِ ورود/خروج با موجودی و ارزشِ در حال اجرا را همان‌جا در صفحه ببینید.
 * خلاصه و جدول با KardexDrawer و گزارش‌ها مشترک است (`KardexTable`).
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
      description="کالا را انتخاب کنید تا همه‌ی ورودها و خروج‌هایش — به ترتیبِ تاریخ، با موجودی، بها و ارزشِ در حال اجرا — نمایش داده شود."
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
          <KardexSummary data={data} />
          <KardexTable data={data} />
        </>
      )}
    </SectionCard>
  )
}
