import { ShoppingCart, BookOpenCheck, Store, Users, ChevronLeft, type LucideIcon } from 'lucide-react'

/** «راهکارها بر اساس حوزه‌ی عملیاتی» — قرینه‌ی کارت‌های راهکارِ رقیب، با پالتِ خودمان. */
const SOLUTIONS: { icon: LucideIcon; title: string; desc: string; href: string }[] = [
  {
    icon: ShoppingCart,
    title: 'فروش، خرید و انبارِ یکپارچه',
    desc: 'فاکتور بزنید و موجودی و سندِ حسابداری خودکار ثبت شود؛ چند انبار، تخفیف و مالیات.',
    href: '#features',
  },
  {
    icon: BookOpenCheck,
    title: 'حسابداری و گزارش‌های مالی',
    desc: 'دفترِ دوطرفه‌ی کامل، تراز، سود و زیان، ترازنامه و گزارش‌های زنده — بدون کارِ دستی.',
    href: '#features',
  },
  {
    icon: Store,
    title: 'فروشگاهِ آنلاین و اتصال به سایت',
    desc: 'سفارش‌های سایت خودکار به فاکتور تبدیل و موجودی و قیمت روی سایت به‌روز می‌ماند.',
    href: '#features',
  },
  {
    icon: Users,
    title: 'حقوق و دستمزد و منابع انسانی',
    desc: 'از حکمِ حقوقی تا فیش، لیستِ بیمه و مزایا — همه بر پایه‌ی تقویمِ شمسی.',
    href: '#features',
  },
]

export function Solutions() {
  return (
    <section id="solutions">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">راهکارها بر اساس نیاز</span>
          <h2>هرچه کسب‌وکارتان لازم دارد، یک‌جا</h2>
          <p>به‌جای چند نرم‌افزارِ جدا، همه‌ی بخش‌ها در یک برنامه‌ی هماهنگ کار می‌کنند.</p>
        </div>

        <div className="solutions-grid">
          {SOLUTIONS.map((s) => (
            <a href={s.href} className="solution-card" key={s.title}>
              <span className="solution-icon">
                <s.icon size={24} />
              </span>
              <div className="solution-body">
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </div>
              <ChevronLeft size={20} className="solution-arrow" />
            </a>
          ))}
        </div>
      </div>
    </section>
  )
}
