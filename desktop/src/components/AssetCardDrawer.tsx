import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Landmark } from 'lucide-react'
import {
  DEPRECIATION_METHOD_LABELS,
  DISPOSAL_TYPE_LABELS,
  fetchAssetCard,
  type AssetCard,
  type DepreciationMethod,
} from '../api'
import { formatJalali } from '../lib/jalali'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')
const method = (m: string) => DEPRECIATION_METHOD_LABELS[m as DepreciationMethod] ?? m

/**
 * کارتِ داراییِ کامل — زندگیِ یک قلم دارایی از تحصیل تا خروج، در یک نما.
 *
 * پنج دفترِ ماژول (استهلاک، تحویل/جابه‌جایی، تعمیراتِ اساسی، تغییرِ برآورد، خروج) هر
 * کدام تبِ خودشان را دارند و همه‌ی دارایی‌ها را نشان می‌دهند. این کشو **نمای دومِ
 * همان داده نیست**: برشِ یک دارایی است، چیزی که در آن تب‌ها باید با پنج فیلترِ جدا
 * ساخته می‌شد. سؤالی که جواب می‌دهد یکی است: «این قلم از اول تا حالا چه شد؟»
 */
export function AssetCardDrawer({
  token,
  asset,
  onClose,
}: {
  token: string
  asset: { id: string; name: string; category: string }
  onClose: () => void
}) {
  const [data, setData] = useState<AssetCard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchAssetCard(token, asset.id)
      .then((r) => { if (alive) setData(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
    return () => { alive = false }
  }, [token, asset.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <Landmark size={17} />
            <div>
              <div className="drawer-title-main">کارتِ دارایی: {asset.name}</div>
              <div className="drawer-title-sub">{asset.category || 'بدونِ دسته'}</div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
        </div>

        <div className="drawer-body">
          {error && <div className="error">{error}</div>}
          {!data && !error && <p className="muted">در حال بارگذاری…</p>}
          {data && <CardBody data={data} />}
        </div>
      </div>
    </div>,
    document.body,
  )
}

function CardBody({ data }: { data: AssetCard }) {
  const a = data.asset
  return (
    <>
      <section className="drawer-section">
        <h4>مشخصات</h4>
        <div className="live-preview">
          <div className="live-preview-row"><span>تاریخ تحصیل</span><strong>{formatJalali(a.acquired_date)}</strong></div>
          <div className="live-preview-row"><span>بهای تمام‌شده</span><strong>{fa(a.cost)}</strong></div>
          <div className="live-preview-row"><span>ارزش اسقاط</span><strong>{fa(a.salvage_value)}</strong></div>
          <div className="live-preview-row"><span>روش استهلاک</span><strong>{method(a.method)}</strong></div>
          <div className="live-preview-row"><span>عمر مفید</span><strong>{fa(a.useful_life_months)} ماه</strong></div>
          <div className="live-preview-row"><span>دوره‌های ثبت‌شده</span><strong>{fa(a.periods_depreciated)} از {fa(a.useful_life_months)}</strong></div>
          <div className="live-preview-row"><span>استهلاک انباشته</span><strong>{fa(a.accumulated_depreciation)}</strong></div>
          <div className="live-preview-row"><span>محلِ استقرار</span><strong>{[a.custodian_name, a.location, a.cost_center_name].filter(Boolean).join(' · ') || '—'}</strong></div>
          <div className="live-preview-divider" />
          <div className="live-preview-row live-preview-total"><span>ارزش دفتری</span><strong>{fa(a.book_value)}</strong></div>
        </div>
      </section>

      {data.disposal && (
        <section className="drawer-section">
          <h4>خروج از دفاتر</h4>
          <div className="live-preview">
            <div className="live-preview-row"><span>تاریخ</span><strong>{formatJalali(data.disposal.disposal_date)}</strong></div>
            <div className="live-preview-row"><span>نوع</span><strong>{DISPOSAL_TYPE_LABELS[data.disposal.disposal_type]}</strong></div>
            <div className="live-preview-row"><span>مبلغ دریافتی</span><strong>{fa(data.disposal.proceeds)}</strong></div>
            <div className="live-preview-row"><span>ارزش دفتری در خروج</span><strong>{fa(data.disposal.book_value)}</strong></div>
            <div className="live-preview-divider" />
            <div className="live-preview-row live-preview-total">
              <span>{Number(data.disposal.gain_loss) >= 0 ? 'سودِ خروج' : 'زیانِ خروج'}</span>
              <strong>{fa(Math.abs(Number(data.disposal.gain_loss)))}</strong>
            </div>
          </div>
        </section>
      )}

      <CardTable
        title="تحویل‌ها و جابه‌جایی‌ها"
        empty="تحویلی ثبت نشده."
        head={['تاریخ', 'نوع', 'از', 'به']}
        rows={data.assignments.map((r) => [
          formatJalali(r.assignment_date),
          r.kind === 'placement' ? 'تحویل' : 'جابه‌جایی',
          [r.from_custodian_name, r.from_location].filter(Boolean).join(' · ') || '—',
          [r.to_custodian_name, r.to_location, r.to_cost_center_name].filter(Boolean).join(' · ') || '—',
        ])}
      />

      <CardTable
        title="تعمیراتِ اساسی"
        empty="مخارجِ سرمایه‌ای ثبت نشده."
        head={['تاریخ', 'مبلغ', 'افزایشِ عمر', 'سند']}
        rows={data.improvements.map((r) => [
          formatJalali(r.improvement_date),
          fa(r.amount),
          r.extra_life_months ? `${fa(r.extra_life_months)} ماه` : '—',
          r.journal_entry_number != null ? fa(r.journal_entry_number) : '—',
        ])}
      />

      <CardTable
        title="تغییرِ روش یا عمرِ مفید"
        empty="برآوردها دست‌نخورده‌اند."
        head={['تاریخ', 'روش', 'عمر مفید', 'ارزش اسقاط']}
        rows={data.estimate_changes.map((r) => [
          formatJalali(r.change_date),
          r.from_method === r.to_method ? method(r.to_method) : `${method(r.from_method)} ← ${method(r.to_method)}`,
          r.from_useful_life_months === r.to_useful_life_months
            ? `${fa(r.to_useful_life_months)} ماه`
            : `${fa(r.from_useful_life_months)} ← ${fa(r.to_useful_life_months)} ماه`,
          r.from_salvage_value === r.to_salvage_value ? fa(r.to_salvage_value) : `${fa(r.from_salvage_value)} ← ${fa(r.to_salvage_value)}`,
        ])}
      />

      <CardTable
        title="استهلاک‌های ثبت‌شده"
        empty="هنوز استهلاکی ثبت نشده."
        head={['دوره', 'مبلغ', 'سند']}
        rows={data.depreciation_entries.map((r) => [
          formatJalali(r.period_date),
          fa(r.amount),
          r.journal_entry_number != null ? fa(r.journal_entry_number) : '—',
        ])}
      />
    </>
  )
}

/** جدولِ کوچکِ داخلِ کشو — ستون‌ها ثابت‌اند، پس برچسبِ کارتی از همان سرستون می‌آید. */
function CardTable({ title, head, rows, empty }: { title: string; head: string[]; rows: string[][]; empty: string }) {
  return (
    <section className="drawer-section">
      <h4>{title}</h4>
      {rows.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>{head.map((h) => (<th key={h}>{h}</th>))}</tr>
            </thead>
            <tbody>
              {rows.map((cells, i) => (
                <tr key={i}>
                  {cells.map((c, j) => (
                    <td key={j} className={j === 0 ? 'card-title' : undefined} data-label={j === 0 ? undefined : head[j]}>
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
