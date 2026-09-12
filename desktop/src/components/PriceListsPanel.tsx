import { useEffect, useMemo, useState } from 'react'
import { Tags, Trash2 } from 'lucide-react'
import {
  deletePriceList,
  fetchPriceListItems,
  fetchPriceLists,
  updatePriceList,
  type PriceListItemRecord,
  type PriceListRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { PriceRuleTable } from './PriceRuleTable'
import { formatJalali } from '../lib/jalali'

/**
 * اعلامیه‌های قیمت، **خواندنی** — انبار قیمت را نشان می‌دهد، تعیین نمی‌کند.
 *
 * **چرا فرمِ ویرایش از این‌جا برداشته شد.** این پنل قیمت‌ها را در یک نگاشتِ
 * `item_id → price` می‌ریخت: چند قاعده‌ی یک کالا (عمده، خرده، هر واحد، هر گروهِ
 * مشتری) به یکی فرو می‌ریخت و دلبخواه یکی برنده می‌شد. بعد همان را با زمینه‌ی
 * **خالی** پس می‌فرستاد، و اندپوینت پیش از درج همه‌چیز را پاک می‌کرد. یعنی یک
 * بار زدنِ «ذخیره» هر قیمتِ زمینه‌دار و هر حدِ تغییرِ نرخِ آن اعلامیه را برای
 * همیشه می‌برد — بی‌صدا و بی‌ردِ حسابرسی.
 *
 * اندپوینت هم اصلاح شد (دیگر پاک نمی‌کند)، ولی دو ویرایشگر برای یک داده خودش
 * مسئله است. ورودِ قاعده‌ها جای درستش «فروش ← اعلامیه قیمت» است، که تاریخِ اجرا
 * و همه‌ی ابعادِ زمینه را می‌شناسد.
 */
export function PriceListsPanel({ token }: { token: string }) {
  const [lists, setLists] = useState<PriceListRecord[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [rules, setRules] = useState<PriceListItemRecord[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const listsPg = usePagination(lists, 10)

  async function refresh() {
    setError(null)
    try {
      setLists(await fetchPriceLists(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  useEffect(() => {
    if (!selectedId) {
      setRules([])
      return
    }
    fetchPriceListItems(token, selectedId)
      .then(setRules)
      .catch(() => setRules([]))
  }, [token, selectedId])

  const selected = useMemo(() => lists.find((l) => l.id === selectedId), [lists, selectedId])

  async function removeList(id: string) {
    // اعلامیه‌ی قاعده‌دار غیرفعال می‌شود نه حذف — فاکتورِ پارسال باید بتواند
    // بگوید نرخش از کدام قاعده آمد.
    if (!window.confirm('این اعلامیه حذف شود؟ اگر قاعده داشته باشد فقط غیرفعال می‌شود.')) return
    setMsg(null)
    try {
      await deletePriceList(token, id)
      if (selectedId === id) setSelectedId('')
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard
        icon={Tags}
        title="اعلامیه‌های قیمت"
        description="قیمتِ فروش از این‌جا خوانده می‌شود. برای ساختِ اعلامیه‌ی تازه: فروش ← اعلامیه قیمت."
      >
        {error && <div className="error">{error}</div>}
        {lists.length === 0 ? (
          <EmptyState icon={Tags} text="اعلامیه‌ای ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr><th>اعلامیه</th><th>تاریخِ اجرا</th><th>وضعیت</th><th></th></tr>
                </thead>
                <tbody>
                  {listsPg.pageItems.map((l) => (
                    <tr key={l.id} className={l.id === selectedId ? 'row-selected' : ''}>
                      <td className="card-title" data-label="اعلامیه">
                        <button type="button" className="link-like" onClick={() => setSelectedId(l.id)}>
                          <strong className="entity-name">{l.name}</strong>
                        </button>
                      </td>
                      <td data-label="تاریخِ اجرا">{formatJalali(l.effective_from)}</td>
                      <td data-label="وضعیت">
                        <button type="button" onClick={() => void updatePriceList(token, l.id, { is_active: !l.is_active }).then(refresh)}>
                          <span className={`status-badge ${l.is_active ? 'tone-success' : 'tone-warning'}`}>{l.is_active ? 'فعال' : 'غیرفعال'}</span>
                        </button>
                      </td>
                      <td className="card-actions">
                        <button type="button" className="icon-btn-danger" onClick={() => void removeList(l.id)} aria-label="حذف"><Trash2 size={13} /> حذف</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={listsPg.page} pageCount={listsPg.pageCount} onChange={listsPg.setPage} />
          </div>
        )}
        {msg && <div className="hint">{msg}</div>}
      </SectionCard>

      <SectionCard
        icon={Tags}
        title={selected ? `قاعده‌های «${selected.name}»` : 'قاعده‌های قیمت'}
        description={
          selected
            ? 'یک کالا می‌تواند به ازای نوعِ فروش، واحد، گروهِ مشتری و ارز چند قیمت داشته باشد.'
            : 'یک اعلامیه را از سمتِ راست انتخاب کنید.'
        }
      >
        {!selected ? (
          <EmptyState icon={Tags} text="اعلامیه‌ای انتخاب نشده." />
        ) : (
          <PriceRuleTable token={token} rules={rules} />
        )}
      </SectionCard>
    </div>
  )
}
