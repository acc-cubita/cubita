import { Boxes, TrendingUp, Wallet } from 'lucide-react'

export function ProductMockup() {
  return (
    <div className="mockup-wrap">
      <div className="mockup-card">
        <div className="mockup-titlebar">
          <span className="mockup-dot red" />
          <span className="mockup-dot yellow" />
          <span className="mockup-dot green" />
          <span className="mockup-url">acc.cubita.ir</span>
        </div>
        {/* اسکرین‌شات واقعی داشبورد، نه شبیه‌سازی CSS — چیزی که مشتری اینجا می‌بیند
            دقیقاً همان چیزی است که بعد از ورود می‌بیند. eager+fetchPriority چون
            این تصویر بالای تاشدگی است و اولین چیزی است که کاربر نگاهش می‌افتد. */}
        <picture>
          <source srcSet="/screenshots/dashboard.webp" type="image/webp" />
          <img
            src="/screenshots/dashboard.png"
            alt="داشبورد کوبیتا با خلاصه‌ی فروش، موجودی انبار، سود دوره و مانده‌ی نقد و بانک"
            className="mockup-screenshot"
            width={1600}
            height={1000}
            loading="eager"
            fetchPriority="high"
          />
        </picture>
      </div>

      <div className="floating-chip chip-1">
        <span className="floating-chip-icon">
          <Boxes size={16} />
        </span>
        <div>
          <b>۱۲+</b>
          <span>ماژول حسابداری</span>
        </div>
      </div>
      <div className="floating-chip chip-2">
        <span className="floating-chip-icon accent-2">
          <Wallet size={16} />
        </span>
        <div>
          <b>۱۰۰٪</b>
          <span>قابل‌کار آفلاین</span>
        </div>
      </div>
      <div className="floating-chip chip-3">
        <span className="floating-chip-icon">
          <TrendingUp size={16} />
        </span>
        <div>
          <b>زنده</b>
          <span>گزارش‌های مالی</span>
        </div>
      </div>
    </div>
  )
}
