import { Headphones, MonitorSmartphone, RefreshCw, Rocket, ShieldCheck, WifiOff } from 'lucide-react'

const REASONS = [
  {
    icon: WifiOff,
    title: 'کاملاً آفلاین',
    desc: 'حتی بدون اینترنت هم کار می‌کند؛ به‌محض اتصال، همه‌چیز خودکار همگام‌سازی می‌شود.',
  },
  {
    icon: MonitorSmartphone,
    title: 'دسکتاپ و وب، با یک اشتراک',
    desc: 'روی ویندوز نصب کنید یا مستقیم از مرورگر کار کنید — داده‌ها همیشه یکی است.',
  },
  {
    icon: ShieldCheck,
    title: 'داده‌ی ایزوله و خصوصی',
    desc: 'اطلاعات هر کسب‌وکار در نسخه‌ی جدا و محافظت‌شده‌ی خودش نگهداری می‌شود.',
  },
  {
    icon: RefreshCw,
    title: 'اتصال به فروشگاه اینترنتی',
    desc: 'موجودی نرم‌افزار و سایت فروش شما به‌صورت خودکار با هم هماهنگ می‌شوند.',
  },
  {
    icon: Headphones,
    title: 'ساخته‌شده برای ایران',
    desc: 'رابط کاربری و پشتیبانی کاملاً فارسی و راست‌به‌چپ، متناسب با کسب‌وکار ایرانی.',
  },
  {
    icon: Rocket,
    title: 'راه‌اندازی چنددقیقه‌ای',
    desc: 'بعد از پرداخت، نسخه‌ی اختصاصی شما همان لحظه ساخته می‌شود و آماده‌ی کار است.',
  },
]

export function WhyCubita() {
  return (
    <section id="why">
      <div className="container">
        <div className="why-band">
          <div className="why-head">
            <span className="eyebrow">چرا کوبیتا؟</span>
            <h2>تفاوتی که در همان روز اول حس می‌کنید</h2>
            <p>فقط یک نرم‌افزار حسابداری دیگر نیست؛ برای واقعیتِ کسب‌وکار ایرانی طراحی شده.</p>
          </div>
          <div className="why-grid">
            {REASONS.map((r) => (
              <div className="why-item" key={r.title}>
                <span className="why-icon">
                  <r.icon size={20} />
                </span>
                <div>
                  <h3>{r.title}</h3>
                  <p>{r.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
