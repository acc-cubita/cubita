import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

/**
 * پرسش‌وپاسخِ بازوبسته. **همه‌ی پاسخ‌ها در HTML هستند** و بسته‌ها فقط `hidden` می‌گیرند — پیش‌تر
 * پاسخِ بسته اصلاً رندر نمی‌شد، پس خزنده فقط پاسخِ اول را می‌دید و FAQPageِ دادهٔ ساخت‌یافته با متنِ
 * صفحه نمی‌خواند.
 */
export function FaqList({ items, idPrefix }: { items: { q: string; a: string }[]; idPrefix: string }) {
  const [open, setOpen] = useState<number | null>(0)
  return (
    <div className="cc-faq-list">
      {items.map((item, idx) => {
        const isOpen = open === idx
        const answerId = `${idPrefix}-a${idx}`
        return (
          <div className={`cc-faq${isOpen ? ' cc-faq-open' : ''}`} key={item.q}>
            <h3 className="cc-faq-h">
              <button
                type="button"
                className="cc-faq-q"
                aria-expanded={isOpen}
                aria-controls={answerId}
                onClick={() => setOpen(isOpen ? null : idx)}
              >
                {item.q}
                <ChevronDown size={18} className="cc-faq-chev" />
              </button>
            </h3>
            <p className="cc-faq-a" id={answerId} hidden={!isOpen}>
              {item.a}
            </p>
          </div>
        )
      })}
    </div>
  )
}
