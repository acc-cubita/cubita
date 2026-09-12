import { useEffect, useState } from 'react'
import { Tags } from 'lucide-react'
import {
  fetchContactGroups,
  fetchDiscountGroups,
  fetchItemsLive,
  fetchSaleTypes,
  fetchUnits,
  type ContactGroupRecord,
  type DiscountGroup,
  type ItemRecord,
  type PriceListItemRecord,
  type SaleType,
  type UnitRecord,
} from '../api'
import { EmptyState } from './EmptyState'

const fa = (n: number | string) => Number(n || 0).toLocaleString('fa-IR')

/**
 * نمایِ خواندنیِ ماتریسِ قیمت — **تنها نمای این داده**.
 *
 * دو صفحه همین را نشان می‌دهند (دفترِ اعلامیه‌ها، و تبِ «لیست قیمت»ِ انبار) و
 * هر دو از این یکی می‌آیند. تا امروز هرکدام نمای خودش را داشت، و آن نمای دوم
 * فقط `item_id → price` را می‌فهمید — پس ذخیره‌اش زمینه‌ی ردیف‌ها را می‌بلعید.
 *
 * مِسترها یک‌بار برای کلِ جدول خوانده می‌شوند، نه یک‌بار برای هر ردیف.
 */
export function PriceRuleTable({ token, rules }: { token: string; rules: PriceListItemRecord[] }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [saleTypes, setSaleTypes] = useState<SaleType[]>([])
  const [units, setUnits] = useState<UnitRecord[]>([])
  const [contactGroups, setContactGroups] = useState<ContactGroupRecord[]>([])
  const [itemGroups, setItemGroups] = useState<DiscountGroup[]>([])

  useEffect(() => {
    fetchItemsLive(token).then(setItems).catch(() => {})
    fetchSaleTypes(token).then(setSaleTypes).catch(() => {})
    fetchUnits(token).then(setUnits).catch(() => {})
    fetchContactGroups(token).then(setContactGroups).catch(() => {})
    fetchDiscountGroups(token).then(setItemGroups).catch(() => {})
  }, [token])

  const named = <T extends { id: string; name: string }>(rows: T[], id: string | null) =>
    id ? (rows.find((r) => r.id === id)?.name ?? '—') : 'همه'

  if (rules.length === 0) return <EmptyState icon={Tags} text="قاعده‌ای در این اعلامیه نیست." />

  return (
    <div className="table-scroll">
      <table className="cards-on-mobile acc-table">
        <thead>
          <tr>
            <th>هدف</th>
            <th>نوع فروش</th>
            <th>واحد</th>
            <th>گروه مشتری</th>
            <th>ارز</th>
            <th>فی</th>
            <th>اضافات</th>
            <th>تغییر فی</th>
            <th>تغییر تخفیف</th>
            <th>کاهش/افزایش</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td className="card-title" data-label="هدف">
                {r.item_id
                  ? (items.find((i) => i.id === r.item_id)?.name ?? '—')
                  : `گروه: ${named(itemGroups, r.item_group_id)}`}
              </td>
              <td data-label="نوع فروش">{named(saleTypes, r.sale_type_id)}</td>
              <td data-label="واحد">{named(units, r.unit_id)}</td>
              <td data-label="گروه مشتری">{named(contactGroups, r.contact_group_id)}</td>
              <td data-label="ارز">{r.currency_code}</td>
              <td className="num" data-label="فی">{fa(r.price)}</td>
              <td className="num" data-label="اضافات">
                {Number(r.addition_percent) > 0 ? `${fa(r.addition_percent)}٪` : '—'}
              </td>
              <td data-label="تغییر فی">{r.allow_rate_change ? 'آزاد' : 'قفل'}</td>
              <td data-label="تغییر تخفیف">{r.allow_discount_change ? 'آزاد' : 'قفل'}</td>
              <td className="num" data-label="کاهش/افزایش">
                {r.allow_rate_change
                  ? `${fa(r.max_decrease_percent)}٪ / ${fa(r.max_increase_percent)}٪`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
