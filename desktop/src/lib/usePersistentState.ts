import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { isElectron } from '../platform'

/**
 * مثلِ useState، اما مقدار را (فقط در وب) در localStorage هم نگه می‌دارد تا «رفرش» یا
 * جابه‌جایی بین صفحه‌ها، پیش‌نویسِ نیمه‌کاره را از بین نبرد.
 *
 * چرا فقط وب: در Electron پنجره رفرش نمی‌شود و مدلِ آفلاین/کشِ محلیِ خودش را دارد؛ آن
 * مسیر دست‌نخورده می‌ماند (مثلِ [[session]] برای توکنِ ورود).
 *
 * پاک‌سازی لازم نیست: با ثبتِ موفق، خودِ هوک فیلدها را به مقدارِ خالی برمی‌گرداند و همان
 * خالی ذخیره می‌شود؛ پس دفعه‌ی بعد فرمِ تمیز بازیابی می‌شود.
 *
 * `disabled`: برای فرم‌هایی که حالتِ «ویرایش/رونوشت» دارند (مثلِ فاکتور/پیش‌فاکتور). وقتی
 * فرم با دیتای موجود پُر شده، نه باید آن دیتا ذخیره شود و نه پیش‌نویسِ ماندگار روی آن بنشیند؛
 * پس در آن حالت مثلِ useStateِ ساده رفتار می‌کند. در «ثبتِ تازه» (disabled=false) ماندگار است.
 */
/**
 * آیا مقدارِ بازیابی‌شده هم‌شکلِ مقدارِ اولیه است؟
 *
 * عمداً **سطحی** است، نه اعتبارسنجیِ کامل. چیزی که واقعاً پیش می‌آید تغییرِ
 * *دسته*ی مقدار است (آرایه ↔ شیء ↔ رشته)، و همان است که `.map` را می‌شکند. یک
 * اسکیمای کامل برای هر پیش‌نویس، هزینه‌ای است که این باگ توجیهش نمی‌کند — و
 * نداشتنش نباید بهانه‌ی نداشتنِ *هیچ* گاردی باشد.
 *
 * `null`ِ اولیه یعنی «هر چیزی مجاز است»، چون چند فرم عمداً با `null` شروع می‌شوند.
 */
function sameShape(value: unknown, initial: unknown): boolean {
  if (initial === null || initial === undefined) return true
  if (Array.isArray(initial)) return Array.isArray(value)
  if (typeof initial === 'object') return typeof value === 'object' && value !== null && !Array.isArray(value)
  return typeof value === typeof initial
}

export function usePersistentState<T>(
  key: string,
  initial: T,
  disabled = false,
): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    if (isElectron || disabled) return initial
    try {
      const raw = localStorage.getItem(key)
      if (raw == null) return initial
      const parsed: unknown = JSON.parse(raw)
      //: **`as T` یک دروغ بود.** `try/catch` فقط JSONِ خراب را می‌گرفت، نه
      //: JSONِ سالمی که *شکلش* عوض شده. پیش‌نویسی که با نسخه‌ی قدیمیِ فرم ذخیره
      //: شده (مثلاً `lines` که آرایه بود و حالا نیست) بی‌اعتبارسنجی برمی‌گشت و
      //: مصرف‌کننده `lines.map(...)` می‌زد ⇒ خطا در **هر** رندر.
      //:
      //: و بدترین بخشش ماندگاری است: مقدارِ بد هر بار از localStorage دوباره
      //: خوانده می‌شود، پس رفرش درستش نمی‌کند و آن صفحه برای آن کاربر **برای
      //: همیشه** خراب می‌ماند — بی هیچ راهِ خروجی از داخلِ برنامه.
      return sameShape(parsed, initial) ? (parsed as T) : initial
    } catch {
      return initial
    }
  })

  // نخستین رندر نوشته نمی‌شود تا مقدارِ تازه‌بازیابی‌شده بی‌جهت روی خودش نوشته نشود.
  const first = useRef(true)
  useEffect(() => {
    if (isElectron || disabled) return
    if (first.current) {
      first.current = false
      return
    }
    try {
      localStorage.setItem(key, JSON.stringify(state))
    } catch {
      /* سهمیه پر بود یا localStorage در دسترس نبود؛ همان جلسه اعمال می‌شود */
    }
  }, [key, state, disabled])

  return [state, setState]
}
