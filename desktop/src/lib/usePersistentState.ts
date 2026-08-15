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
export function usePersistentState<T>(
  key: string,
  initial: T,
  disabled = false,
): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    if (isElectron || disabled) return initial
    try {
      const raw = localStorage.getItem(key)
      return raw != null ? (JSON.parse(raw) as T) : initial
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
