import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type SelectHTMLAttributes,
} from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, Search } from 'lucide-react'

import { textMatches } from '../lib/commands'
import { flatten, shouldSearch, type Opt } from '../lib/selectOptions'

/**
 * `<select>`ی که وقتی بلند شد، جست‌وجو پیدا می‌کند.
 *
 * **مسئله:** پروژه ۳۶۱ `<select>` دارد که ۳۲۶ تایشان فهرستشان پویاست. فهرستِ
 * واحدهای شمارش ۳۹۳ ردیف است، کالاها صدها، حساب‌ها هزارها. `<select>`ِ بومی با
 * این‌ها یعنی کاربر باید اسکرول کند و چشمی بگردد — همان چیزی که کاربر گفت:
 * «کا را بزند، کارتن بیاید».
 *
 * **جایگزینِ درجاست.** همان `value`، همان `onChange`، و همان فرزندانِ
 * `<option>`. پس تبدیلِ یک `<select>` موجود یعنی عوض‌کردنِ نامِ تگ:
 *
 * ```tsx
 * <SearchSelect value={x} onChange={(e) => setX(e.target.value)}>
 *   {units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
 * </SearchSelect>
 * ```
 *
 * **زیرِ آستانه، `<select>`ِ بومی می‌ماند.** فهرستِ سه‌گزینه‌ای («همه / باز /
 * بسته») کادرِ جست‌وجو نمی‌خواهد، و روی موبایل چرخِ بومیِ سیستم از هر
 * کمبوباکسی بهتر است. پس تصمیم را خودِ کامپوننت در زمانِ اجرا می‌گیرد، نه
 * نویسنده‌ی هر فرم.
 *
 * تطبیق از `textMatches` می‌آید، پس «كارتن» با کافِ عربی و «متر مربع» با
 * نیم‌فاصله هم پیدا می‌شوند.
 *
 * پاپ‌آور با portal و `position: fixed` رندر می‌شود تا داخلِ جدولِ اسکرول‌دار
 * بریده نشود — همان درسی که `ItemPicker` از آن آمده.
 */

type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'onChange'> & {
  onChange?: (e: { target: { value: string } }) => void
  /** متنِ کادرِ جست‌وجو. پیش‌فرض عمومی است چون این کامپوننت همه‌جا می‌نشیند. */
  searchPlaceholder?: string
}

export function SearchSelect({ children, searchPlaceholder, ...rest }: Props) {
  const options = useMemo(() => flatten(children), [children])

  if (!shouldSearch(options.length, { multiple: rest.multiple, size: rest.size })) {
    return (
      <select {...(rest as SelectHTMLAttributes<HTMLSelectElement>)}>{children}</select>
    )
  }
  return <Searchable options={options} searchPlaceholder={searchPlaceholder} {...rest} />
}

function Searchable({
  options,
  value,
  onChange,
  disabled,
  id,
  className,
  searchPlaceholder = 'جست‌وجو…',
  'aria-label': ariaLabel,
}: Props & { options: Opt[] }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [rect, setRect] = useState<{ top: number; left: number; width: number; maxH: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const current = String(value ?? '')
  const selected = options.find((o) => o.value === current) ?? null

  const filtered = useMemo(() => {
    const hits = query.trim() ? options.filter((o) => textMatches(o.label, query)) : options
    //: سقفِ نمایش تا فهرست سبک بماند؛ تایپ‌کردن باریکش می‌کند.
    return hits.slice(0, 80)
  }, [options, query])

  function reposition() {
    const el = triggerRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const m = 8
    const vw = window.innerWidth
    const w = Math.min(Math.max(r.width, 240), vw - m * 2)
    //: لبه‌ی راست به دکمه می‌چسبد — طبیعیِ راست‌به‌چپ.
    let left = r.right - w
    if (left + w > vw - m) left = vw - m - w
    if (left < m) left = m
    const maxH = Math.max(140, Math.min(320, window.innerHeight - r.bottom - m - 48))
    setRect({ top: r.bottom + 4, left, width: w, maxH })
  }

  useLayoutEffect(() => {
    if (!open) return
    reposition()
    //: `capture` تا اسکرولِ هر جدِّ داخلی — نه فقط پنجره — پاپ‌آور را جابه‌جا کند.
    window.addEventListener('scroll', reposition, true)
    window.addEventListener('resize', reposition)
    return () => {
      window.removeEventListener('scroll', reposition, true)
      window.removeEventListener('resize', reposition)
    }
  }, [open])

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

  //: وابستگی عمداً فقط `open` است و `exhaustive-deps` این‌جا اشتباه می‌کند.
  //: بیشترِ فراخوان‌ها `<option>`ها را درجا با `.map` می‌سازند، پس `options` هر
  //: رندر آرایه‌ی تازه‌ای است. اگر در وابستگی‌ها بیاید، این اثر هر رندر اجرا
  //: می‌شود و کادرِ جست‌وجو را **وسطِ تایپِ کاربر** خالی می‌کند.
  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(Math.max(0, options.findIndex((o) => o.value === current)))
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  useEffect(() => setActive(0), [query])

  useEffect(() => {
    listRef.current?.querySelector('.item-picker-opt.active')?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  function pick(opt: Opt) {
    if (opt.disabled) return
    onChange?.({ target: { value: opt.value } })
    setOpen(false)
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const o = filtered[active]
      if (o) pick(o)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setOpen(false)
    }
  }

  return (
    <>
      <button
        type="button"
        id={id}
        ref={triggerRef}
        className={`item-picker-trigger${className ? ` ${className}` : ''}`}
        onClick={() => setOpen((v) => !v)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
      >
        {/* کلاس‌های خودِ ItemPicker: متنِ بلند سه‌نقطه می‌شود و از دکمه بیرون نمی‌زند. */}
        <span className={selected ? 'item-picker-value' : 'item-picker-placeholder'}>
          {selected?.label ?? '— انتخاب کنید —'}
        </span>
        <ChevronDown size={15} />
      </button>

      {open && rect &&
        createPortal(
          <div
            ref={popRef}
            className="item-picker-pop"
            style={{ position: 'fixed', top: rect.top, left: rect.left, width: rect.width }}
            role="listbox"
          >
            <div className="item-picker-search">
              <Search size={15} />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKey}
                placeholder={searchPlaceholder}
                aria-label="جست‌وجو در فهرست"
              />
            </div>
            <ul className="item-picker-list" ref={listRef} style={{ maxHeight: rect.maxH }}>
              {filtered.length === 0 ? (
                <li className="item-picker-empty">چیزی با این نام پیدا نشد.</li>
              ) : (
                filtered.map((o, i) => (
                  <li key={o.value || `__${i}`}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={o.value === current}
                      className={`item-picker-opt${i === active ? ' active' : ''}`}
                      onMouseEnter={() => setActive(i)}
                      onClick={() => pick(o)}
                      disabled={o.disabled}
                    >
                      <span className="item-picker-opt-name">{o.label}</span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>,
          document.body,
        )}
    </>
  )
}
