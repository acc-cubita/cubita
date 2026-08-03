import {
  ShoppingCart,
  PackagePlus,
  Warehouse,
  Landmark,
  Wallet,
  Users,
  BookOpen,
  History,
  type LucideIcon,
} from 'lucide-react'
import type { JournalEntryRecord } from '../api'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'

//: سقفِ رویدادهای «اخیر» که در داشبرد قابلِ ورق‌زدن است (۱۰ صفحه‌ی ۴تایی). دفترِ کامل در «گزارش‌ها».
const MAX_ACTIVITY = 40

const SOURCE_META: Record<string, { label: string; icon: LucideIcon }> = {
  sales_invoice: { label: 'فاکتور فروش', icon: ShoppingCart },
  purchase_invoice: { label: 'فاکتور خرید', icon: PackagePlus },
  stock_adjustment: { label: 'انبارگردانی', icon: Warehouse },
  check: { label: 'چک', icon: Landmark },
  bank: { label: 'بانک', icon: Landmark },
  petty_cash: { label: 'تنخواه‌گردان', icon: Wallet },
  payroll: { label: 'حقوق و دستمزد', icon: Users },
  manual: { label: 'سند دستی', icon: BookOpen },
}

function entryAmount(entry: JournalEntryRecord): number {
  return entry.lines.reduce((sum, l) => sum + Number(l.debit), 0)
}

export function ActivityFeed({ entries }: { entries: JournalEntryRecord[] }) {
  const recent = entries.slice(0, MAX_ACTIVITY)
  const { pageItems, page, setPage, pageCount } = usePagination(recent, 4)

  if (recent.length === 0) {
    return <EmptyState icon={History} text="هنوز سندی ثبت نشده." />
  }

  return (
    <>
      <ul className="activity-feed">
        {pageItems.map((entry) => {
          const meta = SOURCE_META[entry.source_type] ?? SOURCE_META.manual
          const Icon = meta.icon
          return (
            <li key={entry.id} className="activity-item">
              <span className="activity-icon">
                <Icon size={16} />
              </span>
              <div className="activity-body">
                <div className="activity-title">{entry.description || meta.label}</div>
                <div className="activity-meta">
                  {meta.label} · {new Date(entry.entry_date).toLocaleDateString('fa-IR')}
                </div>
              </div>
              <div className="activity-amount">{Math.round(entryAmount(entry)).toLocaleString('fa-IR')}</div>
            </li>
          )
        })}
      </ul>
      <Pager page={page} pageCount={pageCount} onChange={setPage} />
    </>
  )
}
