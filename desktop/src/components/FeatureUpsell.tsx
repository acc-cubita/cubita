import { Lock, Sparkles } from 'lucide-react'
import { PLANS_URL } from '../api'

/**
 * باکسِ «این قابلیت فقط در پلن‌های کامل هست» که جای ماژولِ قفل‌شده (مودیان/اتصال‌فروشگاه)
 * برای کاربرِ آزمایشی می‌نشیند. دکمه‌اش به صفحه‌ی پلن‌ها می‌رود؛ خرید با همین ایمیل،
 * حسابِ آزمایشی را سرِ جا به واقعی تبدیل می‌کند و دیتا حفظ می‌شود.
 */
const COPY: Record<string, { title: string; desc: string }> = {
  moadian: {
    title: 'سامانه مؤدیان — ویژه‌ی پلن‌های کامل',
    desc: 'ارسالِ خودکارِ صورتحساب به سامانه مؤدیانِ سازمان امور مالیاتی بخشی از پلن‌های حرفه‌ای است و در نسخه‌ی آزمایشیِ رایگان فعال نیست. با تهیه‌ی پلن، این قابلیت به‌همراهِ اتصال فروشگاه باز می‌شود.',
  },
  storefront: {
    title: 'اتصال فروشگاه — ویژه‌ی پلن‌های کامل',
    desc: 'هم‌گام‌سازیِ موجودی و قیمت با سایتِ فروشگاهی و تبدیلِ خودکارِ سفارش‌های آنلاین به فاکتور، بخشی از پلن‌های حرفه‌ای است و در نسخه‌ی آزمایشیِ رایگان فعال نیست. با تهیه‌ی پلن باز می‌شود.',
  },
}

export function FeatureUpsell({ feature }: { feature: 'moadian' | 'storefront' }) {
  const copy = COPY[feature] ?? COPY.moadian
  return (
    <div className="feature-upsell">
      <div className="feature-upsell-icon">
        <Lock size={26} />
      </div>
      <h2>{copy.title}</h2>
      <p>{copy.desc}</p>
      <a className="btn-primary feature-upsell-cta" href={PLANS_URL} target="_blank" rel="noopener noreferrer">
        <Sparkles size={16} /> مشاهده پلن‌ها و ارتقا
      </a>
    </div>
  )
}
