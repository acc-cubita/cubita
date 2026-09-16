import { useMemo, useState, type ReactNode } from 'react'
import { ArrowDownUp, ArrowDown, ArrowUp } from 'lucide-react'

/**
 * مرتب‌سازیِ سمتِ کلاینت برای جدول‌های فهرست — یک حالت، **دو نمایش**.
 *
 * **چرا دو نمایش و این تکرار نیست.** زیرِ ۷۶۰px جدول‌ها کارت می‌شوند و
 * `table.cards-on-mobile thead { display: none }` سرستون‌ها را برمی‌دارد
 * ([App.css](../App.css)). پس کلیک روی سرستون در موبایل **بی‌راه می‌مانَد** —
 * همان تله‌ای که قراردادِ صفحه درباره‌ی کارتِ «فهرست» هشدار می‌دهد. `SortBar`
 * همان `useSort` را می‌خورد و فقط در همان عرض دیده می‌شود؛ دو کنترل نیست، یک
 * کنترل با دو صورت.
 *
 * **متن با `localeCompare('fa')` مرتب می‌شود، نه با `<`.** ترتیبِ کدِ یونیکد
 * «آ» را بعد از «ی» می‌گذارد و «ك»ِ عربی را از «ک»ِ فارسی جدا می‌کند؛ نتیجه‌اش
 * فهرستی است که به‌نظر تصادفی می‌آید و هیچ خطایی هم نمی‌دهد.
 */
export type SortKind = 'text' | 'number'

export interface SortColumn<T> {
  label: string
  get: (row: T) => string | number | null | undefined
  kind?: SortKind
}

export type SortColumns<T> = Record<string, SortColumn<T>>

export type SortDir = 'asc' | 'desc'

export interface SortState<T> {
  key: string
  dir: SortDir
  columns: SortColumns<T>
  /** کلیک روی همان ستون جهت را برمی‌گرداند؛ ستونِ تازه از صعودی شروع می‌کند. */
  toggle: (key: string) => void
  setKey: (key: string) => void
  setDir: (dir: SortDir) => void
  apply: (rows: T[]) => T[]
  /** کلیدِ ریست برای `usePagination` — با تغییرِ مرتب‌سازی به صفحه‌ی اول برگرد. */
  resetKey: string
}

//: مقایسه‌گرِ فارسی. `undefined` به‌عنوان locale یعنی «هرچه مرورگر دارد» — روی
//: ویندوزِ انگلیسی همان ترتیبِ لاتین را می‌داد، پس صریح `fa` داده می‌شود.
const collator = new Intl.Collator('fa', { numeric: true, sensitivity: 'base' })

function compare(a: unknown, b: unknown, kind: SortKind): number {
  //: خالی همیشه **ته** فهرست می‌نشیند، در هر دو جهت. اگر با جهت بچرخد،
  //: کاربر فکر می‌کند ردیف‌ها گم شده‌اند.
  const aEmpty = a === null || a === undefined || a === ''
  const bEmpty = b === null || b === undefined || b === ''
  if (aEmpty && bEmpty) return 0
  if (aEmpty) return 1
  if (bEmpty) return -1
  if (kind === 'number') {
    const na = Number(a)
    const nb = Number(b)
    if (Number.isNaN(na) && Number.isNaN(nb)) return 0
    if (Number.isNaN(na)) return 1
    if (Number.isNaN(nb)) return -1
    return na - nb
  }
  return collator.compare(String(a), String(b))
}

export function useSort<T>(columns: SortColumns<T>, initialKey: string, initialDir: SortDir = 'asc'): SortState<T> {
  const [key, setKey] = useState(initialKey)
  const [dir, setDir] = useState<SortDir>(initialDir)

  const apply = useMemo(
    () => (rows: T[]) => {
      const column = columns[key]
      if (!column) return rows
      const kind = column.kind ?? 'text'
      const sign = dir === 'asc' ? 1 : -1
      //: کپی می‌گیریم؛ `sort` درجا مرتب می‌کند و ورودی معمولاً از `useMemo`ِ
      //: صفحه می‌آید که نباید جابه‌جا شود.
      return [...rows].sort((a, b) => sign * compare(column.get(a), column.get(b), kind))
    },
    [columns, key, dir],
  )

  function toggle(next: string) {
    if (next === key) {
      setDir(dir === 'asc' ? 'desc' : 'asc')
      return
    }
    setKey(next)
    setDir('asc')
  }

  return { key, dir, columns, toggle, setKey, setDir, apply, resetKey: `${key}|${dir}` }
}

/** سرستونِ قابلِ کلیک. در نمای کارتیِ موبایل دیده نمی‌شود — `SortBar` جایش را می‌گیرد. */
export function SortTh<T>({
  sort,
  k,
  children,
  className,
}: {
  sort: SortState<T>
  k: string
  children: ReactNode
  className?: string
}) {
  const active = sort.key === k
  return (
    <th className={className}>
      <button
        type="button"
        className={`sort-th${active ? ' is-active' : ''}`}
        onClick={() => sort.toggle(k)}
        aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
        title={active ? (sort.dir === 'asc' ? 'صعودی — برای نزولی کلیک کنید' : 'نزولی — برای صعودی کلیک کنید') : 'مرتب‌سازی بر این ستون'}
      >
        <span>{children}</span>
        {active ? (
          sort.dir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />
        ) : (
          <ArrowDownUp size={12} className="sort-th-idle" />
        )}
      </button>
    </th>
  )
}

/** همان مرتب‌سازی، برای عرضی که سرستون ندارد. */
export function SortBar<T>({ sort }: { sort: SortState<T> }) {
  return (
    <div className="sort-bar">
      <label className="acc-inline-field">
        مرتب‌سازی
        <select value={sort.key} onChange={(e) => sort.setKey(e.target.value)}>
          {Object.entries(sort.columns).map(([k, c]) => (
            <option key={k} value={k}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        onClick={() => sort.setDir(sort.dir === 'asc' ? 'desc' : 'asc')}
        title={sort.dir === 'asc' ? 'صعودی' : 'نزولی'}
      >
        {sort.dir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />}
        {sort.dir === 'asc' ? 'صعودی' : 'نزولی'}
      </button>
    </div>
  )
}
