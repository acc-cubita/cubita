import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Search, X, Plus } from 'lucide-react'

import { placePopover, type Placement } from '../lib/popover'

/** حداقلِ شکلی که برای انتخابِ کالا لازم است.
 *
 * هم `ItemCache` (کشِ آفلاین، بدونِ بارکد) و هم `ItemRecord` (زنده، با بارکد) این
 * شکل را برآورده می‌کنند، پس یک کامپوننتِ واحد در فاکتور/پیش‌فاکتور/برگشت/POS کار
 * می‌کند بی‌آنکه به تایپِ خاصی گره بخورد.
 */
export interface PickableItem {
  id: string
  name: string
  sku: string
  unit?: string
  barcode?: string | null
}

/** نرمال‌سازی برای جست‌وجوی مقاومِ فارسی: ی/ک عربی → فارسی، حذفِ اعرابِ رایج،
 * ارقامِ فارسی/عربی → لاتین، و کوچک‌سازی. بدون این، «كالا» با کِ عربی هرگز با
 * «کالا»ی فارسی جور نمی‌شود و کاربر فکر می‌کند کالا وجود ندارد. */
const AR_FA: Record<string, string> = { 'ي': 'ی', 'ك': 'ک', 'ة': 'ه', 'ۀ': 'ه', 'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ؤ': 'و' }
const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
function norm(s: string): string {
  let out = ''
  for (const ch of (s || '')) {
    if (AR_FA[ch]) out += AR_FA[ch]
    else if (FA_DIGITS.includes(ch)) out += String(FA_DIGITS.indexOf(ch))
    else if (AR_DIGITS.includes(ch)) out += String(AR_DIGITS.indexOf(ch))
    else if ('ًٌٍَُِّْ'.includes(ch)) continue
    else out += ch
  }
  return out.trim().toLowerCase()
}

/** کمبوباکسِ جست‌وجوی کالا — جایگزینِ `<select>`های بلندِ کالا.
 *
 * چرا: `<select>` با صدها کالا عملاً بی‌استفاده است. اینجا کاربر با نام/کد/بارکد
 * تایپ می‌کند، فهرست فیلتر می‌شود، و با کلید یا کلیک انتخاب می‌کند.
 *
 * پاپ‌آور با portal و موقعیتِ fixed رندر می‌شود تا داخلِ جدولِ اسکرول‌دار
 * (`overflow` دارِ .table-scroll) بریده نشود — مشکلِ کلاسیکِ dropdownِ درونِ ظرفِ
 * overflow.
 */
export function ItemPicker({
  items,
  value,
  onChange,
  placeholder = '— انتخاب کالا —',
  disabledIds,
  onCreateNew,
}: {
  items: PickableItem[]
  value: string
  onChange: (itemId: string) => void
  placeholder?: string
  /** شناسه‌هایی که نباید دوباره انتخاب شوند (مثلاً کالایی که در ردیفِ دیگری هست). */
  disabledIds?: Set<string>
  /** اگر داده شود، ته پاپ‌آور دکمه‌ی «ساختِ کالای جدید» می‌آید و با کلیک، متنِ فعلیِ
   *  جست‌وجو را به بالادست می‌دهد (تا فرمِ ساختِ سریع را با همان نام باز کند). فقط
   *  فرم‌هایی که این را می‌دهند (مثلِ خرید) این گزینه را می‌بینند. */
  onCreateNew?: (query: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [rect, setRect] = useState<Placement | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const selected = useMemo(() => items.find((i) => i.id === value) || null, [items, value])

  const filtered = useMemo(() => {
    const q = norm(query)
    const base = q
      ? items.filter((i) => norm(i.name).includes(q) || norm(i.sku).includes(q) || norm(i.barcode || '').includes(q))
      : items
    return base.slice(0, 50) // سقفِ نمایش تا فهرست سبک بماند؛ جست‌وجو باریکش می‌کند
  }, [items, query])

  // موقعیتِ پاپ‌آور را از دکمه می‌گیرد و با اسکرول/تغییرِ اندازه به‌روز می‌کند.
  //
  // روی موبایل ستونِ «کالا» باریک است؛ اگر عرضِ پاپ‌آور را برابرِ همان بگذاریم،
  // جست‌وجو و آیتم‌ها فشرده و بریده می‌شوند. پس عرض را دستِ‌کم ۲۶۰px می‌گیریم.
  // بقیه‌ی حساب (ماندن داخلِ صفحه و پریدن به بالای دکمه وقتی پایین جا نیست) در
  // `placePopover` است — همان‌که `SearchSelect` هم از آن می‌خواند.
  function reposition() {
    const el = triggerRef.current
    if (!el) return
    setRect(
      placePopover(
        el.getBoundingClientRect(),
        { width: window.innerWidth, height: window.innerHeight },
        { minWidth: 260 },
      ),
    )
  }

  useLayoutEffect(() => {
    if (!open) return
    reposition()
    // scroll با capture تا اسکرولِ هر جدِّ داخلی (نه فقط پنجره) هم پاپ‌آور را جابه‌جا کند
    window.addEventListener('scroll', reposition, true)
    window.addEventListener('resize', reposition)
    return () => {
      window.removeEventListener('scroll', reposition, true)
      window.removeEventListener('resize', reposition)
    }
  }, [open])

  // بستن با کلیکِ بیرون — هم دکمه و هم پاپ‌آورِ portal را استثنا می‌کند
  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      const t = e.target as Node
      if (triggerRef.current?.contains(t) || popRef.current?.contains(t)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  // با باز شدن، فوکوس روی ورودی و ری‌ست کوئری/نشانگر
  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
      // بعد از رندرِ portal فوکوس بده
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  // نگه‌داشتنِ آیتمِ فعال در دید هنگام پیمایش با کلید
  useEffect(() => {
    if (!open) return
    const el = listRef.current?.children[active] as HTMLElement | undefined
    el?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  function pick(id: string) {
    onChange(id)
    setOpen(false)
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const it = filtered[active]
      if (it && !(disabledIds?.has(it.id) && it.id !== value)) pick(it.id)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setOpen(false)
    }
  }

  return (
    <div className={`item-picker ${open ? 'open' : ''}`}>
      <button
        ref={triggerRef}
        type="button"
        className="item-picker-trigger"
        onClick={() => setOpen((o) => !o)}
        title={selected ? selected.name : placeholder}
      >
        <span className={selected ? 'item-picker-value' : 'item-picker-placeholder'}>
          {selected ? selected.name : placeholder}
        </span>
        {selected && (
          <span
            className="item-picker-clear"
            role="button"
            tabIndex={-1}
            aria-label="پاک کردن"
            onClick={(e) => {
              e.stopPropagation()
              onChange('')
            }}
          >
            <X size={13} />
          </span>
        )}
      </button>

      {open && rect &&
        createPortal(
          <div
            ref={popRef}
            className="item-picker-pop"
            style={{
              position: 'fixed',
              top: rect.top,
              bottom: rect.bottom,
              left: rect.left,
              width: rect.width,
            }}
          >
            <div className="item-picker-search">
              <Search size={14} />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setActive(0)
                }}
                onKeyDown={onKeyDown}
                placeholder="جست‌وجو با نام، کد یا بارکد…"
              />
            </div>
            <ul className="item-picker-list" ref={listRef} style={{ maxHeight: rect.maxH }}>
              {filtered.length === 0 ? (
                <li className="item-picker-empty">کالایی یافت نشد</li>
              ) : (
                filtered.map((it, i) => {
                  const isDisabled = disabledIds?.has(it.id) && it.id !== value
                  return (
                    <li
                      key={it.id}
                      className={`item-picker-opt ${i === active ? 'active' : ''} ${it.id === value ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}`}
                      onMouseEnter={() => setActive(i)}
                      onMouseDown={(e) => {
                        e.preventDefault()
                        if (!isDisabled) pick(it.id)
                      }}
                    >
                      <span className="item-picker-opt-name">{it.name}</span>
                      <span className="item-picker-opt-meta">
                        {it.sku}
                        {it.barcode ? ` · ${it.barcode}` : ''}
                        {it.unit ? ` · ${it.unit}` : ''}
                      </span>
                    </li>
                  )
                })
              )}
            </ul>
            {onCreateNew && (
              <button
                type="button"
                className="item-picker-create"
                onMouseDown={(e) => {
                  e.preventDefault()
                  onCreateNew(query.trim())
                  setOpen(false)
                }}
              >
                <Plus size={14} />
                {query.trim() ? `ساختِ کالای «${query.trim()}»` : 'ساختِ کالای جدید'}
              </button>
            )}
          </div>,
          document.body,
        )}
    </div>
  )
}
