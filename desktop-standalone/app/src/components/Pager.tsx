import { useEffect, useState } from 'react'
import { ChevronRight, ChevronLeft, MoreHorizontal } from 'lucide-react'
import { toFaDigits } from '../lib/jalali'

/**
 * صفحه‌بندیِ سمتِ کلاینت برای فهرست‌های عمودیِ کارت‌ها (آخرین رویدادها، یادآوری‌ها، …).
 *
 * page‌ درونِ خودِ هوک نگه داشته می‌شود؛ اگر ورودی کوچک‌تر شد (مثلاً با تغییرِ فیلتر) و
 * صفحه‌ی جاری از بازه بیرون افتاد، `safePage` برشِ درست را نشان می‌دهد. با دادنِ `resetKey`
 * (مثلاً دسته‌ی فیلترِ فعال) هر بار که آن عوض شود صفحه به اول برمی‌گردد.
 */
export function usePagination<T>(items: T[], pageSize = 4, resetKey?: unknown) {
  const [page, setPage] = useState(0)
  useEffect(() => {
    setPage(0)
  }, [resetKey])

  const pageCount = Math.max(1, Math.ceil(items.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const start = safePage * pageSize
  return {
    pageItems: items.slice(start, start + pageSize),
    page: safePage,
    setPage,
    pageCount,
    total: items.length,
  }
}

/** فهرستِ شماره‌ی صفحه‌ها با میان‌بُر (…) وقتی صفحه‌ها زیاد شوند. */
function pageWindow(page: number, pageCount: number): (number | 'gap')[] {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i)
  const out: (number | 'gap')[] = [0]
  const left = Math.max(1, page - 1)
  const right = Math.min(pageCount - 2, page + 1)
  if (left > 1) out.push('gap')
  for (let i = left; i <= right; i++) out.push(i)
  if (right < pageCount - 2) out.push('gap')
  out.push(pageCount - 1)
  return out
}

/**
 * کنترلِ صفحه‌بندیِ عددی. فقط وقتی بیش از یک صفحه باشد دیده می‌شود (یعنی بیش از
 * pageSize مورد). RTL: فلشِ راست = صفحه‌ی قبل، فلشِ چپ = صفحه‌ی بعد.
 */
export function Pager({
  page,
  pageCount,
  onChange,
}: {
  page: number
  pageCount: number
  onChange: (p: number) => void
}) {
  if (pageCount <= 1) return null
  const nums = pageWindow(page, pageCount)
  return (
    <nav className="pager" aria-label="صفحه‌بندی">
      <button
        type="button"
        className="pager-arrow"
        disabled={page === 0}
        onClick={() => onChange(page - 1)}
        aria-label="صفحه‌ی قبل"
      >
        <ChevronRight size={16} />
      </button>
      {nums.map((n, i) =>
        n === 'gap' ? (
          <span key={`gap-${i}`} className="pager-ellipsis" aria-hidden="true">
            <MoreHorizontal size={14} />
          </span>
        ) : (
          <button
            type="button"
            key={n}
            className={`pager-num${n === page ? ' is-active' : ''}`}
            onClick={() => onChange(n)}
            aria-current={n === page ? 'page' : undefined}
          >
            {toFaDigits(n + 1)}
          </button>
        ),
      )}
      <button
        type="button"
        className="pager-arrow"
        disabled={page === pageCount - 1}
        onClick={() => onChange(page + 1)}
        aria-label="صفحه‌ی بعد"
      >
        <ChevronLeft size={16} />
      </button>
    </nav>
  )
}
