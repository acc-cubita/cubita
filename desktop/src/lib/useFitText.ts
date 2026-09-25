import { useLayoutEffect, useRef } from 'react'

/**
 * ضریبِ کوچک‌کردنِ فونت تا متنی که `need` پیکسل می‌خواهد در `box` پیکسل جا شود.
 *
 * پهنای متن با اندازه‌ی فونت خطی است، پس ضریب همان نسبتِ دو پهناست — دو درصد کمتر تا
 * گردکردنِ زیرپیکسلیِ مرورگر لبه را نبُرد. `min` کفِ خوانایی است: زیرِ آن عدد ریزتر نمی‌شود و
 * باقی‌اش (در عمل هرگز) با `overflow` بریده می‌شود. جعبه‌ی بی‌پهنا (هنوز چیده‌نشده، یا jsdom)
 * یعنی «نمی‌دانیم» — اندازه‌ی کامل.
 */
export function fitScale(box: number, need: number, min = 0.55): number {
  if (box <= 0 || need <= box) return 1
  return Math.max(min, Math.floor((box / need) * 98) / 100)
}

/**
 * متنِ درونِ یک خانه‌ی **ثابت‌عرض** را به‌جای پهن‌کردنِ خانه، کوچک می‌کند.
 *
 * ضریب روی متغیرِ CSSِ `--fit` می‌نشیند و CSS فونت را از آن می‌سازد
 * (`font-size: calc(var(--fs-xl) * var(--fit, 1))`)، پس اندازه‌ی پایه همان توکنِ پوسته
 * می‌ماند. عنصر باید `overflow: hidden` و `white-space: nowrap` داشته باشد تا `scrollWidth`
 * پهنای طبیعیِ متن را بدهد. با هر تغییرِ `text` و هر تغییرِ پهنای خانه (پوسته، زوم، پنجره)
 * دوباره سنجیده می‌شود.
 *
 * مستقیم روی `style` نوشته می‌شود و نه state: یک رندرِ اضافه برای هر کلید در گریدِ سند
 * بی‌دلیل است، و React به `--fit` دست نمی‌زند چون در JSX نیامده.
 */
export function useFitText<T extends HTMLElement>(text: string, min = 0.55) {
  const ref = useRef<T>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const fit = () => {
      el.style.setProperty('--fit', '1')
      el.style.setProperty('--fit', String(fitScale(el.clientWidth, el.scrollWidth, min)))
    }
    fit()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(fit)
    ro.observe(el.parentElement ?? el)
    return () => ro.disconnect()
  }, [text, min])
  return ref
}
