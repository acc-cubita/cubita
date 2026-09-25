import type { ReactNode } from 'react'

import { useFitText } from '../lib/useFitText'

/**
 * متنِ یک خانه‌ی ثابت‌عرض — به‌جای پهن‌کردنِ خانه، کوچک می‌شود ([useFitText]). `text` کلیدِ
 * سنجشِ دوباره است؛ `children` اگر باشد به‌جایش رندر می‌شود (برای بخشی که CSS در موبایل پنهان
 * می‌کند — سنجش از پهنای واقعاً رندرشده است). خانه‌های نوارِ پایینِ سند و برگه‌ها.
 */
export function FitText({ className, min, text, children }: { className: string; min?: number; text: string; children?: ReactNode }) {
  const ref = useFitText<HTMLSpanElement>(text, min)
  return (
    <span ref={ref} className={`${className} jb-fit`}>
      {children ?? text}
    </span>
  )
}
