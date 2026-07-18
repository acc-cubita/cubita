import {
  BadgePercent,
  BookOpenCheck,
  Boxes,
  Landmark,
  Laptop,
  ScrollText,
  UsersRound,
  Wallet,
  Wifi,
} from 'lucide-react'

const FEATURES = [
  {
    icon: ScrollText,
    title: 'فاکتور فروش و خرید',
    desc: 'پیش‌فاکتور، فاکتور رسمی، برگشت از فروش/خرید و حواله بین‌انباری — همه با سند حسابداری خودکار.',
  },
  {
    icon: Boxes,
    title: 'انبارداری چندانباره',
    desc: 'موجودی هر انبار به‌صورت لحظه‌ای، بهای تمام‌شده به روش میانگین موزون، تاریخچه‌ی کامل ورود و خروج.',
  },
  {
    icon: BookOpenCheck,
    title: 'حسابداری دوطرفه کامل',
    desc: 'سند دستی و خودکار، دفتر روزنامه و کل، تراز آزمایشی، ترازنامه، سود و زیان، و بستن رسمی دوره مالی.',
  },
  {
    icon: Landmark,
    title: 'چک و بانک',
    desc: 'مدیریت چک‌های دریافتنی و پرداختنی، چند حساب بانکی، و تطبیق بانکی رسمی در برابر صورت‌حساب.',
  },
  {
    icon: Wallet,
    title: 'حقوق و دستمزد',
    desc: 'پرونده پرسنلی، فیش حقوقی، محاسبه بیمه تأمین اجتماعی، و خروجی لیست بیمه آماده‌ی ارسال.',
  },
  {
    icon: Laptop,
    title: 'اپ دسکتاپ آفلاین',
    desc: 'روی ویندوز نصب می‌شود و کاملاً بدون اینترنت کار می‌کند؛ با اتصال مجدد، خودکار هم‌گام‌سازی می‌شود.',
  },
  {
    icon: Wifi,
    title: 'نسخه‌ی وب',
    desc: 'بدون نصب، مستقیم از مرورگر با همان امکانات کامل کار کنید — برای تیم‌هایی که فقط آنلاین کار می‌کنند.',
  },
  {
    icon: UsersRound,
    title: 'چند کاربره با نقش‌بندی',
    desc: 'مدیر، حسابدار، فروشنده، انباردار و مسئول حقوق — هرکس فقط به بخش مربوط به خودش دسترسی دارد.',
  },
  {
    icon: BadgePercent,
    title: 'گزارش‌های مدیریتی',
    desc: 'داشبورد لحظه‌ای فروش، موجودی کم، چک‌های نزدیک‌به‌سررسید، و مانده‌ی صندوق و بانک.',
  },
]

export function Features() {
  return (
    <section id="features">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">امکانات</span>
          <h2>همه‌ی چیزی که یک کسب‌وکار برای حسابداری نیاز دارد</h2>
          <p>از فاکتور روزانه تا بستن رسمی دوره مالی، همه در یک نرم‌افزار یکپارچه.</p>
        </div>
        <div className="features-grid">
          {FEATURES.map((f, idx) => (
            <div className="feature-card" key={f.title}>
              <div className={`feature-icon${idx % 3 === 1 ? ' accent-2' : ''}`}>
                <f.icon size={20} />
              </div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
