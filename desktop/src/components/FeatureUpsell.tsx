import { Lock, Sparkles } from 'lucide-react'
import { ENTERPRISE_PLANS_URL, PLANS_URL } from '../api'

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

//: کوبیتا سازمانی پلن ندارد؛ قابلیتِ پولی با مجوزِ تجاری باز می‌شود (نسخه‌ی رایگان مؤدیان ندارد).
const ENTERPRISE_COPY: Record<string, { title: string; desc: string }> = {
  moadian: {
    title: 'سامانه مؤدیان — ویژه‌ی مجوزِ تجاری',
    desc: 'ارسالِ خودکارِ صورتحساب به سامانه مؤدیانِ سازمان امور مالیاتی در نسخه‌ی رایگانِ کوبیتا سازمانی نیست. با مجوزِ تجاری این قابلیت روی همین سرور باز می‌شود و داده‌ها همان‌طور می‌مانند.',
  },
}

export function FeatureUpsell({ feature }: { feature: 'moadian' | 'storefront' }) {
  const enterprise = window.cubitaConfig?.edition === 'enterprise'
  const copy = (enterprise ? ENTERPRISE_COPY[feature] : undefined) ?? COPY[feature] ?? COPY.moadian
  return (
    <div className="feature-upsell">
      <div className="feature-upsell-icon">
        <Lock size={26} />
      </div>
      <h2>{copy.title}</h2>
      <p>{copy.desc}</p>
      <a
        className="btn-primary feature-upsell-cta"
        href={enterprise ? ENTERPRISE_PLANS_URL : PLANS_URL}
        target="_blank"
        rel="noopener noreferrer"
      >
        <Sparkles size={16} /> {enterprise ? 'مقایسه‌ی رایگان و تجاری' : 'مشاهده پلن‌ها و ارتقا'}
      </a>
    </div>
  )
}
