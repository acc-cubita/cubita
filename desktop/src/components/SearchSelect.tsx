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

import { matchRank, textMatches } from '../lib/faText'
import { toFaDigits } from '../lib/jalali'
import { placePopover, type Placement } from '../lib/popover'
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
 * بریده نشود — همان درسی که `ItemPicker` از آن آمده. جاگذاری‌اش از `placePopover`
 * می‌آید که با هم‌او مشترک است، پس فیلدِ نزدیکِ پایینِ پنجره فهرستش را **بالا** باز
 * می‌کند نه بیرونِ صفحه.
 */

type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'onChange'> & {
  onChange?: (e: { target: { value: string } }) => void
  /** متنِ کادرِ جست‌وجو. پیش‌فرض عمومی است چون این کامپوننت همه‌جا می‌نشیند. */
  searchPlaceholder?: string
}

//: سقفِ ردیف‌های نمایش‌داده‌شده. بریدن لازم است (فهرستِ واحدها ۳۹۳ ردیف است) ولی
//: **بی‌صدا** بریدن نه: با ۹۴ صنف، گروهِ آخر برای کسی که فقط اسکرول می‌کند اصلاً
//: وجود نداشت. حالا هر وقت چیزی بریده شود، خودِ پاپ‌آور می‌گویدش.
const SHOW_LIMIT = 80

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
  const [rect, setRect] = useState<Placement | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  //: حرفی که پاپ‌آور را باز کرد، تا اثرِ `open` به‌جای خالی‌کردن، با آن شروع کند.
  const seedRef = useRef<string | null>(null)

  const current = String(value ?? '')
  const selected = options.find((o) => o.value === current) ?? null

  const { filtered, hidden } = useMemo(() => {
    //: تطبیق‌خورده‌ها رتبه‌بندی می‌شوند (کد/ابتدای نام بالاتر) — مرتب‌سازیِ پایدار، پس
    //: ترتیبِ اصلی داخلِ هر رتبه می‌ماند (`matchRank` در `lib/faText`).
    const hits = query.trim()
      ? options
          .filter((o) => textMatches(o.label, query))
          .map((o, i) => ({ o, i, r: matchRank(o.label, query) }))
          .sort((a, b) => a.r - b.r || a.i - b.i)
          .map((x) => x.o)
      : options
    //: سقفِ نمایش تا فهرست سبک بماند؛ تایپ‌کردن باریکش می‌کند.
    return { filtered: hits.slice(0, SHOW_LIMIT), hidden: Math.max(0, hits.length - SHOW_LIMIT) }
  }, [options, query])

  function reposition() {
    const el = triggerRef.current
    if (!el) return
    setRect(
      placePopover(el.getBoundingClientRect(), {
        width: window.innerWidth,
        height: window.innerHeight,
      }),
    )
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
      //: اگر پاپ‌آور با تایپ باز شده، همان حرف بذرِ جست‌وجوست — وگرنه خالی.
      //: بدونِ این، `setQuery('')`ِ زیر حرفِ اولِ کاربر را بی‌صدا می‌خورد.
      setQuery(seedRef.current ?? '')
      seedRef.current = null
      setActive(Math.max(0, options.findIndex((o) => o.value === current)))
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  useEffect(() => setActive(0), [query])

  useEffect(() => {
    listRef.current?.querySelector('.item-picker-opt.active')?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  /**
   * بستنِ پاپ‌آور، با برگرداندنِ فوکوس به دکمه‌ی خودش.
   *
   * **چرا لازم است.** پاپ‌آور با portal روی `document.body` می‌نشیند، پس وقتی
   * unmount می‌شود فوکوس روی `<body>` می‌افتد — نه روی جایی که کاربر از آن آمده
   * بود. برای یک `<select>`ِ تنها فقط آزاردهنده است، ولی داخلِ یک رابطِ
   * صفحه‌کلیدی مثلِ گریدِ سند **کشنده** است: آن گرید سلولِ جاری را از روی
   * `[data-cell]`ِ عنصرِ فوکوس‌دار پیدا می‌کند، و با فوکوسِ `<body>` از همان
   * لحظه هیچ کلیدی کار نمی‌کند تا کاربر با ماوس جایی کلیک کند. یعنی اولین
   * انتخابِ حساب، کلِ صفحه‌کلیدِ گرید را می‌کُشت.
   *
   * **کلیکِ بیرون عمداً فوکوس را برنمی‌گرداند:** کاربر همان لحظه دارد جای
   * دیگری را انتخاب می‌کند و دزدیدنِ فوکوس از مقصدِ کلیکش بدتر از مسئله است.
   */
  function close(restoreFocus: boolean) {
    setOpen(false)
    if (restoreFocus) triggerRef.current?.focus()
  }

  function pick(opt: Opt) {
    if (opt.disabled) return
    onChange?.({ target: { value: opt.value } })
    close(true)
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
      close(true)
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
        //: تایپ‌کردن روی دکمه، پاپ‌آور را باز می‌کند و همان حرف را می‌نویسد —
        //: همان کاری که `<select>`ِ بومی می‌کند. بدونِ این، کاربری که با
        //: صفحه‌کلید به این سلول رسیده باید Enter بزند و بعد تایپ کند.
        //: تغییردهنده‌دارها رد می‌شوند تا میان‌برها (Ctrl+S…) دست‌نخورده بمانند.
        onKeyDown={(e) => {
          if (e.ctrlKey || e.altKey || e.metaKey || open) return
          if (e.key.length !== 1) return
          e.preventDefault()
          seedRef.current = e.key
          setOpen(true)
        }}
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
            //: یکی از `top`/`bottom` تعریف‌نشده است — سمتی که پاپ‌آور به آن باز
            //: نمی‌شود. React سبکِ تعریف‌نشده را نمی‌نویسد.
            style={{
              position: 'fixed',
              top: rect.top,
              bottom: rect.bottom,
              left: rect.left,
              width: rect.width,
            }}
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
            {hidden > 0 && (
              <p className="item-picker-more">
                {toFaDigits(String(hidden))} گزینه‌ی دیگر هم هست — برای پیدا‌کردنشان تایپ کنید.
              </p>
            )}
          </div>,
          document.body,
        )}
    </>
  )
}
